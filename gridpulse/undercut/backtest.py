"""`gridpulse pitwindow`: backtest the pit window model against the stops teams actually made.

For every driver's last green-flag stop of each race in a season, the model is fitted on the
laps up to ten laps before it and asked for the best lap to stop; that is compared with the lap
the team chose, next to a rule of thumb (split the remaining laps evenly between the two stints).
"""

import argparse

import pandas as pd

from gridpulse.pitwall.data import completed_races, load_race
from gridpulse.session import TimingUnavailable
from gridpulse.undercut.window import backtest


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--horizon", type=int, default=10, help="Laps ahead of the stop the model has to decide")


def summary(errors: pd.Series) -> str:
    e = errors.abs()
    return f"median {e.median():.0f} laps off, {(e <= 3).mean():.0%} within 3, {(e <= 5).mean():.0%} within 5"


def run(args: argparse.Namespace) -> None:
    results = []
    for r in completed_races(args.year).itertuples():
        try:
            race = load_race(args.year, int(r.RoundNumber))
        except TimingUnavailable as exc:
            print(f"{args.year} R{r.RoundNumber:>2} {r.EventName}: couldn't load ({exc})")
            continue
        bt = backtest(race, args.horizon)
        if bt.empty:
            continue
        results.append(bt)
        print(f"{race.name:40} {len(bt):>2} stops  model: {summary(bt['Error'])}", flush=True)
    if not results:
        return
    every = pd.concat(results)
    print(f"\n{len(every)} stops, deciding {args.horizon} laps ahead")
    print(f"  pit window model: {summary(every['Error'])}; the actual stop inside its one-second window "
          f"{every['InWindow'].mean():.0%} of the time")
    print(f"  even split rule:  {summary(every['EvenSplitError'])}")
