"""`pitlens check`: compare each replayed race's finish with the official result.

The replay is built from lap timing (F1's archive or OpenF1), the result
from the classification. For every race this checks that the final timing
tower has the same winner, the same top ten in the same order, and every
classified finisher the same number of laps down.
"""

import argparse

import pandas as pd

from pitlens.pitwall.data import completed_races, load_race
from pitlens.pitwall.timing import timing_tower
from pitlens.session import TimingUnavailable


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--round", type=int, help="Only this round (default: every finished race of the season)")
    parser.add_argument("--sprint", action="store_true", help="Check the sprints instead of the Grands Prix")


def check_race(race) -> list[str]:
    """Problems with a race's final timing tower against its result (empty when it matches)."""
    tower = timing_tower(race.laps, race.total_laps, race.retired, race.entrants, stops=race.stops)
    running = tower[~tower["Out"]]
    classified = race.results.dropna(subset=["Position"])
    official = classified[~classified["Abbreviation"].isin(race.retired)]["Abbreviation"].tolist()
    ours = running["Driver"].tolist()

    problems = []
    if ours[:1] != official[:1]:
        problems.append(f"winner {ours[:1]} but the result says {official[:1]}")
    for pos, (mine, theirs) in enumerate(zip(ours[:10], official[:10]), start=1):
        if mine != theirs:
            problems.append(f"P{pos} is {mine}, the result has {theirs}")
    if "Laps" in race.results:
        laps = race.results.set_index("Abbreviation")["Laps"]
        full = laps.max()
        for r in running.itertuples():
            if r.Driver in laps.index and pd.notna(laps[r.Driver]) and r.LapsDown != full - laps[r.Driver]:
                problems.append(f"{r.Driver} {r.LapsDown} laps down, the result has {int(full - laps[r.Driver])}")
    return problems


def run(args: argparse.Namespace) -> None:
    races = completed_races(args.year)
    if args.round:
        races = races[races["RoundNumber"] == args.round]
    if args.sprint:
        races = races[races["EventFormat"].astype(str).str.contains("sprint")]
    failed = 0
    for r in races.itertuples():
        label = f"{args.year} R{r.RoundNumber:>2} {r.EventName}" + (" Sprint" if args.sprint else "")
        try:
            race = load_race(args.year, int(r.RoundNumber), "S" if args.sprint else "R")
        except TimingUnavailable as exc:
            print(f"{label}: couldn't load ({exc})")
            continue
        problems = check_race(race)
        failed += bool(problems)
        print(f"{label:40} {race.source:15} " + ("ok" if not problems else "; ".join(problems)), flush=True)
    print(f"\n{len(races) - failed} of {len(races)} {'sprints' if args.sprint else 'races'} match the official result.")
    if failed:
        raise SystemExit(1)
