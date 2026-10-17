"""Small adapter for the public JSON feeds used by dtm.com itself.

Published championship positions and points are authoritative, including deductions
and qualifying points. Never infer a race grid from qualifying groups or manufacture
lap-by-lap telemetry from a classification. Bundled snapshots keep every page usable
when the upstream service is unavailable.
"""

import json
import math
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from gridpulse.dtm.cars import model

API = "https://api.dtm.com/data"
ROOT = Path(__file__).parent / "snapshots"
YEARS = (2026, 2025, 2024, 2023)
COLORS = {"Mercedes-AMG": "#27D9C3", "Porsche": "#F4CC48", "BMW": "#55A8FF",
          "Ferrari": "#F65A60", "Lamborghini": "#9DDA40", "Audi": "#C4CAD3",
          "McLaren": "#FF8B32", "Ford": "#6889FF", "Aston Martin": "#41BC98"}
MANUFACTURERS = {"Mercedes": "Mercedes-AMG", "BMW M": "BMW", "BMW-Motorsport": "BMW",
                 "Audi-Sport": "Audi", "Aston Martin Racing": "Aston Martin", "Mclaren": "McLaren", "mclaren": "McLaren"}


def key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def number(value):
    try:
        value = float(str(value).replace(",", "."))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def seconds(value) -> float | None:
    """Timing strings only; a DNF, a lap gap or a blank is never a numeric time."""
    if not value or not re.fullmatch(r"\d+(?::\d+){0,2}[.,]\d+", str(value)):
        return None
    parts = str(value).replace(",", ".").split(":")
    result = 0.0
    for part in parts:
        result = 60 * result + float(part)
    return result if result > 0 else None


def normalize(year: int, results: dict, standings: dict, calendar: dict,
              drivers: dict, *, fetched_at: str | None = None) -> dict:
    """Normalize a complete response bundle. Missing/invalid feeds must not replace a snapshot."""
    names = {}
    for driver in drivers.get("drivers", []):
        first, last = driver.get("firstName", ""), driver.get("lastName", "")
        names[key(f"{last} {first}")] = f"{first} {last}".strip()

    def display(raw):
        return names.get(key(raw), raw)  # retain official spelling if the catalogue has no match

    events = {}
    for item in calendar.get("events", []):
        if not item.get("startTime", "").startswith(str(year)) or "DTM" not in item.get("raceSeries", []):
            continue
        if item.get("hideOnOverview") or not item.get("eventNumber"):
            continue
        round_ = int(item["eventNumber"])
        track = item.get("racetrack") or item.get("racetrackEvents") or {}
        events[round_] = {"round": round_, "name": item["name"], "start": item["startTime"][:10],
                          "end": item["endTime"][:10], "country": (item.get("country") or {}).get("name", ""),
                          "length_m": track.get("length"),
                          "url": f"https://www.dtm.com/en/events/{item['slug']}", "sessions": {}}
    rows = results.get("wigeResultses", [])
    tables = standings.get("wigeStandingses", [])
    if not events or not rows or not tables:
        raise ValueError("DTM returned an incomplete season bundle")
    for record in rows:
        if record.get("raceSeries") != "DTM":
            continue
        doc = json.loads(record["jsonText"])
        descriptor = next((s for s in doc.get("sessions", []) if s["sessionid"] == doc["sessionid"]), None)
        if not descriptor or not doc.get("result"):
            continue
        round_ = int(record["wigeEventId"]) % 100
        if round_ not in events:
            raise ValueError("DTM result has no matching calendar weekend")
        title = descriptor["name"]
        # The feed also lists Safari and pit-stop challenges as training sessions.
        if not title.startswith(("Race ", "Qualifying ", "Free Practice")):
            continue
        kind = "race" if title.startswith("Race ") else "qualifying" if title.startswith("Qualifying ") else "practice"
        classification = []
        for row in doc["result"]:
            classification.append({
                "driver": key(row["name"]), "name": display(row["name"]), "number": str(row.get("number") or ""),
                "position": number(row.get("position")), "team": row.get("team") or "",
                "manufacturer": MANUFACTURERS.get(row.get("car"), row.get("car") or ""),
                "nationality": row.get("nationality") or "",
                "time": row.get("time"), "gap": row.get("gap"), "status": row.get("status") or "",
                "laps": number(row.get("laps")), "pitstops": number(row.get("pitstops")),
                "fastest_lap": row.get("fastestlap"),
                "race_points": number(row.get("racepoints")),
                "qualifying_points": number(row.get("qualifyingpoints")),
                "total_points": number(row.get("totalpoints")),
            })
        # DTM can publish more than one version of a session in the same response.
        # Match its website: the later record replaces the earlier classification.
        events[round_]["sessions"][key(title)] = {"key": key(title), "name": title, "kind": kind,
                                            "start": descriptor.get("timeStart") or "",
                                            "provisional": str(doc.get("provision", "")).lower() == "provisional",
                                            "rows": classification}
    documents = [json.loads(row["jsonText"]) for row in tables]
    if len(documents) != 1:
        raise ValueError("Unexpected multiple DTM championship tables")
    doc = documents[0]
    boards = {}
    for category in ("drivers", "teams", "manufacturers"):
        boards[category] = [{
            "key": key(row["name"]), "name": display(row["name"]) if category == "drivers" else row["name"],
            "position": number(row.get("position")), "points": number(row.get("totalpoints")),
            "race_points": number(row.get("racepoints")), "qualifying_points": number(row.get("qualifyingpoints")),
            "rounds": [{"name": r["name"], "points": number(r.get("points")),
                        "race_points": number(r.get("racepoints")),
                        "qualifying_points": number(r.get("qualifyingpoints"))} for r in row.get("races", [])],
        } for row in doc.get(category, [])]
        boards[category].sort(key=lambda r: r["position"] or 999)
        if not boards[category] or any(row["points"] is None for row in boards[category]):
            raise ValueError("DTM standings are missing published points")
    for event in events.values():
        event["sessions"] = sorted(event["sessions"].values(), key=lambda s: (s["start"], s["name"]))
    if not any(s["kind"] == "race" for e in events.values() for s in e["sessions"]):
        raise ValueError("DTM returned no race classifications")
    return {"schema": 1, "year": year, "fetched_at": fetched_at or datetime.now(UTC).isoformat(),
            "source": "https://www.dtm.com/en/results", "standings_url": "https://www.dtm.com/en/standings",
            "provisional": str(doc.get("provision", "")).lower() == "provisional",
            "events": sorted(events.values(), key=lambda e: e["round"]), "standings": boards}


def fetch(year: int) -> dict:
    if year not in YEARS:
        raise ValueError("Unsupported DTM season")

    def query(name):
        params = {"query": name}
        if name.startswith("wige"):
            params.update(raceSeries="DTM", startDate=f"{year}-01-01", endDate=f"{year}-12-31")
        response = requests.get(API, params=params, timeout=(5, 15))
        response.raise_for_status()
        return response.json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results, standings, calendar, drivers = pool.map(
            query, ["wigeResults", "wigeStandings", "eventsRacetrack", "driversShort"])
    return normalize(year, results, standings, calendar, drivers)


def saved(year: int) -> dict:
    if year not in YEARS:
        raise ValueError("Unsupported DTM season")
    return json.loads((ROOT / f"{year}.json").read_text())


def race_rows(season: dict) -> pd.DataFrame:
    rows = [{**row, "model": model(season["year"], row["manufacturer"]),
             "round": e["round"], "event": e["name"], "session": s["name"], "start": s["start"]}
            for e in season["events"] for s in e["sessions"] if s["kind"] == "race" for row in s["rows"]]
    return pd.DataFrame(rows)


def entrants(season: dict) -> dict:
    """Latest published race identity; race tables always retain the identity at that event."""
    return {row["driver"]: row for row in race_rows(season).sort_values("start").to_dict("records")}


def progress(season: dict, category: str = "drivers") -> pd.DataFrame:
    rows = []
    for entry in season["standings"][category]:
        total = 0.0
        for i, race in enumerate(entry["rounds"], 1):
            # Feed 'points' is this race's allocation, not a running total.
            if race["points"] is None:
                continue
            total += race["points"]
            rows.append({"key": entry["key"], "name": entry["name"], "race": i,
                         "event": race["name"], "points": total, "earned": race["points"]})
    return pd.DataFrame(rows)


def comparison(season: dict, selected: list[str]) -> pd.DataFrame:
    races = race_rows(season)
    entries = entrants(season)
    rows = []
    for driver in selected:
        table = next(r for r in season["standings"]["drivers"] if r["key"] == driver)
        results = races[races.driver == driver]
        classified = results[(results.status == "") & results.position.notna()]
        meta = entries.get(driver, {})
        rows.append({"Driver": table["name"], "Team": meta.get("team", "–"),
                     "Manufacturer": meta.get("manufacturer", "–"), "Car model": meta.get("model", "–"),
                     "Points": table["points"],
                     "Race points": table["race_points"], "Qualifying points": table["qualifying_points"],
                     "Appearances": len(results), "Wins": int((classified.position == 1).sum()),
                     "Podiums": int(classified.position.le(3).sum()),
                     "Best finish": classified.position.min() if not classified.empty else None,
                     "DNF / DNS / DSQ": int(results.status.ne("").sum())})
    return pd.DataFrame(rows)
