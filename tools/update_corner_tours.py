"""Build offline corner tours from saved races and their cached/open telemetry sources.

Run from the repository root: .venv/bin/python tools/update_corner_tours.py
Only the labelled reference lap supplies speed, gear and brake measurements.
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pitlens import snapshots
from pitlens.season.atlas import catalog
from pitlens.season.circuits import circuits, saved_races
from pitlens.season.tours import build_tour
from pitlens.session import enable_cache
from pitlens.sources import openf1


def main():
    enable_cache()
    index = circuits(saved_races()).set_index("Circuit")
    output = {}
    for fact in catalog():
        if fact["key"] not in index.index:
            print(f"No saved race for {fact['slug']}", flush=True)
            continue
        row = index.loc[fact["key"]]
        year, round_number = int(row["Year"]), int(row["Round"])
        meta = snapshots.race_metadata(year, round_number)
        track = meta.get("track")
        if not track:
            print(f"No outline for {fact['slug']}", flush=True)
            continue
        try:
            circuit = openf1._circuit(fact["key"], year)
        except Exception:
            circuit = {"corners": [], "rotation": track.get("rotation", 0)}
        telemetry = None
        reference = {"year": year, "event": row["Event"], "source": "MultiViewer circuit geometry", "driver": None}
        try:
            session = openf1.find_session(year, pd.Timestamp(meta.get("race_utc") or meta["date"]))
            laps = openf1.session_laps(session["session_key"])
            laps = laps.dropna(subset=["duration_sector_1", "duration_sector_2", "duration_sector_3"])
            laps = laps[laps["lap_number"] > 1]
            lap = laps.loc[laps["lap_duration"].idxmin()]
            telemetry = openf1.lap_telemetry(session["session_key"], int(lap["driver_number"]),
                                             lap["date_start"], float(lap["lap_duration"]))
            reference.update(driver=lap["name_acronym"], lap=int(lap["lap_number"]),
                             time=float(lap["lap_duration"]), source="OpenF1 reference lap")
        except Exception as exc:
            print(f"Telemetry unavailable for {fact['slug']}: {exc}", flush=True)
        output[fact["slug"]] = build_tour(circuit, telemetry, track, reference, fact["slug"])
        print(f"{fact['slug']}: {len(output[fact['slug']]['corners'])} markers, telemetry={telemetry is not None}", flush=True)
    path = Path(__file__).resolve().parents[1] / "pitlens" / "season" / "corner_tours.json"
    path.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
