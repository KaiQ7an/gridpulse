"""`pitlens radio`: list (and optionally download) a session's team radio clips."""

import argparse

import fastf1
import pandas as pd

from pitlens.pitwall.data import load_race
from pitlens.radio.clips import download, team_radio
from pitlens.session import OUTPUT_DIR, load_session


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--event", default="Hungary", help="Event name, location or round number")
    parser.add_argument("--session", default="R", help="Session, e.g. R, Q, S (default race)")
    parser.add_argument("--drivers", nargs="+", metavar="DRV", help="Only these drivers, e.g. NOR PIA")
    parser.add_argument("--download", action="store_true", help="Save the mp3s to outputs/radio/")


def run(args: argparse.Namespace) -> None:
    event = int(args.event) if str(args.event).isdigit() else args.event
    print(f"Loading {args.year} {args.event} {args.session}...")
    if args.session == "R":  # races also work through the OpenF1 fallback
        round_number = event if isinstance(event, int) else int(fastf1.get_event(args.year, event)["RoundNumber"])
        race = load_race(args.year, round_number)
        clips, name = race.radio, f"{race.name} Race"
    else:
        session = load_session(args.year, event, args.session)
        clips, name = team_radio(session), f"{session.event.year} {session.event['EventName']} {session.name}"
    if args.drivers:
        clips = clips[clips["Driver"].isin([d.upper() for d in args.drivers])]

    print(f"\n{name}: {len(clips)} team radio clips\n")
    for c in clips.itertuples():
        lap = f"lap {int(c.Lap):>2}" if pd.notna(c.Lap) else "  –   "
        print(f"{lap}  {c.Driver}  {c.Url}")

    if args.download and len(clips):
        folder = OUTPUT_DIR / "radio" / name.lower().replace(" ", "_")
        saved = download(clips, folder)
        print(f"\nSaved {len(saved)} clips to {folder}")
