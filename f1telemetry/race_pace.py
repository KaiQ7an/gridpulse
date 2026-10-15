"""Race pace & tyre degradation report for one race.

Usage:
    python -m f1telemetry.race_pace --year 2025 --event Hungary
"""

import argparse

from f1telemetry.pace import (
    DEFAULT_FUEL_EFFECT_S_PER_LAP,
    add_fuel_corrected_time,
    clean_race_laps,
    stint_degradation,
)
from f1telemetry.plots import plot_degradation, plot_pace_by_driver
from f1telemetry.session import OUTPUT_DIR, load_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--event", default="Hungary", help="Event name, location or round number")
    parser.add_argument("--top", type=int, default=10, help="Analyse the top N finishers")
    parser.add_argument(
        "--fuel-effect",
        type=float,
        default=DEFAULT_FUEL_EFFECT_S_PER_LAP,
        help="Seconds gained per lap from fuel burn (0 to disable)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    event = int(args.event) if str(args.event).isdigit() else args.event

    session = load_session(args.year, event, "R")
    name = f"{session.event.year} {session.event['EventName']}"
    slug = f"{session.event.year}_{session.event['EventName'].lower().replace(' ', '_')}"

    finishers = session.results.sort_values("Position")["Abbreviation"].head(args.top).tolist()
    laps = clean_race_laps(session, finishers)
    laps = add_fuel_corrected_time(laps, int(session.total_laps), args.fuel_effect)
    deg = stint_degradation(laps)

    out_dir = OUTPUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    laps.to_csv(out_dir / "clean_laps.csv", index=False)
    deg.to_csv(out_dir / "stint_degradation.csv", index=False)
    plot_pace_by_driver(laps, finishers, f"{name}: race pace of the top {len(finishers)}", out_dir / "pace_by_driver.png")
    plot_degradation(deg, f"{name}: tyre degradation per stint", out_dir / "stint_degradation.png")

    print(f"\n{name}: {len(laps)} clean laps, {len(deg)} stints fitted")
    print(deg.groupby("Compound")["DegPerLap"].describe()[["count", "mean", "min", "max"]].round(3))
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()
