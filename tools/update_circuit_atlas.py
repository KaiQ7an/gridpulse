"""Refresh the bundled circuit facts and historical records; the UI never needs these requests.

Run from the repository root: .venv/bin/python tools/update_circuit_atlas.py --as-of YYYY-MM-DD
F1 supplies layout facts and its published race lap record. Jolpica supplies venue-level
Grand Prix wins and race starting grids, including ties and shared wins, from 1950 onward.
"""

import argparse
import html
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "atlas"
DATA = ROOT / "gridpulse" / "season" / "atlas.json"
REFRESH = False


def fetch(url: str) -> str:
    import hashlib

    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".txt")
    if path.exists() and not REFRESH:
        return path.read_text()
    for attempt in range(4):
        response = requests.get(url, timeout=40, headers={"User-Agent": "GridPulse/0.1 circuit reference updater"})
        if response.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 * (attempt + 1))
            continue
        response.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(response.text)
        return response.text
    raise RuntimeError(f"Source unavailable: {url}")


def leaders(races: list[dict], cutoff: str) -> list[dict]:
    drivers = {}
    years = defaultdict(list)
    for race in races:
        if race["date"] > cutoff:
            continue
        for result in race["Results"]:
            driver = result["Driver"]
            key = driver["driverId"]
            drivers[key] = f"{driver['givenName']} {driver['familyName']}"
            years[key].append(int(race["season"]))
    maximum = max(map(len, years.values()), default=0)
    return [{"driver": drivers[d], "count": len(y), "years": y} for d, y in sorted(years.items())
            if len(y) == maximum]


def race_list(url: str) -> list[dict]:
    payload = json.loads(fetch(url))['MRData']
    races = payload["RaceTable"]["Races"]
    if int(payload["total"]) > int(payload["limit"]):
        raise ValueError(f"Pagination required before publishing complete records: {url}")
    return races


def update(circuit: dict, cutoff: str, locations: dict) -> dict:
    out = dict(circuit)
    location = locations[out["jolpica_id"]]["Location"]
    out.update(lat=float(location["lat"]), lon=float(location["long"]))
    url = "https://www.formula1.com/en/racing/" + out["f1_path"]
    page = fetch(url) if not out.get("facts_override") else ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script[\s\S]*?</script>", "", page)))
    text = " ".join(text.split())

    def extract(pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else None

    length = extract(r"Circuit Length\s+([\d.]+)\s*km")
    first = extract(r"First Grand Prix\s+(\d{4})")
    laps = extract(r"Number of Laps\s+(\d+)")
    record = extract(r"(?:Fastest lap time|Lap Record)\s+(\d+:\d{2}\.\d{3})")
    holder = re.search(r"(?:Fastest lap time|Lap Record)\s+\d+:\d{2}\.\d{3}\s+(.+?)\s*\((\d{4})\)", text)
    if out.get("facts_override"):
        out.update(out["facts_override"])
    elif not all((length, first, laps)):
        raise ValueError(f"Circuit facts missing: {out['slug']} ({url})")
    else:
        out.update(length_km=float(length), first_gp=int(first), laps=int(laps), facts_source=url,
                   record={"time": record, "driver": holder[1] if holder else None,
                           "year": int(holder[2]) if holder else None})
    base = f"https://api.jolpi.ca/ergast/f1/circuits/{out['jolpica_id']}/"
    wins_url, poles_url = base + "results/1.json?limit=100", base + "grid/1/results.json?limit=100"
    wins, poles = race_list(wins_url), race_list(poles_url)
    out["history"] = {"wins": leaders(wins, cutoff), "poles": leaders(poles, cutoff), "as_of": cutoff,
                      "wins_source": wins_url, "poles_source": poles_url,
                      "races": len([r for r in wins if r["date"] <= cutoff]),
                      "first_year": min((int(r['season']) for r in wins if r['date'] <= cutoff), default=None)}
    print(f"Updated {out['slug']}: {out['history']['races']} Grands Prix", flush=True)
    return out


def main():
    global REFRESH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--refresh", action="store_true", help="Re-fetch reference responses instead of the local cache")
    args = parser.parse_args()
    REFRESH = args.refresh
    date.fromisoformat(args.as_of)
    data = json.loads(DATA.read_text())
    payload = json.loads(fetch("https://api.jolpi.ca/ergast/f1/circuits.json?limit=100"))["MRData"]
    locations = {c["circuitId"]: c for c in payload["CircuitTable"]["Circuits"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(lambda c: update(c, args.as_of, locations), data["circuits"]))
    DATA.write_text(json.dumps({"updated": args.as_of, "circuits": records}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
