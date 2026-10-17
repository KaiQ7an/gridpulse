"""DTM venue reference and explicitly scoped records from the available archive."""

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from gridpulse.dtm import data


@lru_cache(maxsize=1)
def catalog() -> list[dict]:
    return json.loads(Path(__file__).with_name("circuits.json").read_text())


def event_key(event: dict) -> str:
    return event["url"].rstrip("/").split("/")[-1].rsplit("-", 1)[0]


def venues(season: dict) -> list[dict]:
    events = {event_key(e): e for e in season["events"]}
    return [{**c, "event": events[c["event_key"]],
             "length_km": events[c["event_key"]].get("length_m") / 1000 if events[c["event_key"]].get("length_m") else c["length_km"]}
            for c in catalog() if c["event_key"] in events]


def history(fact: dict, year: int, current: dict, *, archive: dict | None = None) -> dict:
    wins, poles, laps, weekends = Counter(), Counter(), [], []
    for season_year in sorted(y for y in data.YEARS if y <= year):
        season = archive[season_year] if archive is not None else current if season_year == year else data.saved(season_year)
        for event in season["events"]:
            if event_key(event) != fact["event_key"]:
                continue
            weekend = {"Year": season_year, "Round": event["round"], "Date": event["start"]}
            for session in event["sessions"]:
                valid = [r for r in session["rows"] if r["status"] not in ("DSQ", "DNS")]
                winner = next((r for r in valid if r["position"] == 1 and not r["status"]), None)
                if session["kind"] == "race":
                    weekend[session["name"]] = winner["name"] if winner else "Not published"
                    if winner:
                        wins[winner["name"]] += 1
                    for row in valid:
                        if (time := data.seconds(row.get("fastest_lap"))) is not None:
                            laps.append({**row, "seconds": time, "year": season_year, "session": session["name"]})
                elif session["kind"] == "qualifying" and "Group" not in session["name"] and winner:
                    poles[winner["name"]] += 1
                    weekend[session["name"]] = winner["name"]
            weekends.append(weekend)
    return {"wins": wins, "poles": poles, "fastest": min(laps, key=lambda r: r["seconds"]) if laps else None,
            "weekends": weekends, "races": sum(wins.values()), "start": min(data.YEARS), "end": year}
