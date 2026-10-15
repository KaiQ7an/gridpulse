"""Race pace & tyre degradation report for one race."""

import argparse
import platform
import subprocess

from pitlens.session import OUTPUT_DIR, load_session
from pitlens.stints.pace import (
    DEFAULT_FUEL_EFFECT_S_PER_LAP,
    add_fuel_corrected_time,
    clean_race_laps,
    stint_degradation,
)
from pitlens.stints.plots import plot_degradation, plot_pace_by_driver


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--event", default="Hungary", help="Event name, location or round number")
    parser.add_argument("--top", type=int, default=10, help="Analyse the top N finishers")
    parser.add_argument(
        "--fuel-effect",
        type=float,
        default=DEFAULT_FUEL_EFFECT_S_PER_LAP,
        help="Seconds gained per lap from fuel burn (0 to disable)",
    )
    parser.add_argument("--open", action="store_true", help="Open the charts when done (macOS)")


def run(args: argparse.Namespace) -> None:
    event = int(args.event) if str(args.event).isdigit() else args.event

    print(f"Loading {args.year} {args.event} race (first run downloads data, later runs use the cache)...")
    session = load_session(args.year, event, "R")
    name = f"{session.event.year} {session.event['EventName']}"
    slug = f"{session.event.year}_{session.event['EventName'].lower().replace(' ', '_')}"

    finishers = session.results.sort_values("Position")["Abbreviation"].head(args.top).tolist()
    laps = clean_race_laps(session, finishers)
    laps = add_fuel_corrected_time(laps, int(session.total_laps), args.fuel_effect)
    deg = stint_degradation(laps)

    out_dir = OUTPUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    charts = [out_dir / "pace_by_driver.png", out_dir / "stint_degradation.png"]
    laps.to_csv(out_dir / "clean_laps.csv", index=False)
    deg.to_csv(out_dir / "stint_degradation.csv", index=False)
    plot_pace_by_driver(laps, finishers, f"{name}: race pace of the top {len(finishers)}", charts[0])
    plot_degradation(deg, f"{name}: tyre degradation per stint", charts[1])

    print(f"\n{name}: {len(laps)} clean laps, {len(deg)} stints fitted")
    print(deg.groupby("Compound")["DegPerLap"].describe()[["count", "mean", "min", "max"]].round(3))
    print(f"\nSaved to {out_dir}")

    if args.open and platform.system() == "Darwin":
        subprocess.run(["open", *map(str, charts)], check=False)
