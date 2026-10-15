"""Loading FastF1 sessions with a local, gitignored cache."""

from pathlib import Path

import fastf1

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def enable_cache() -> None:
    """Point FastF1 at ./cache so repeat runs don't re-download data."""
    CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))


def load_session(year: int, event: str | int, kind: str = "R", telemetry: bool = False):
    """Load a session (e.g. kind="R" race, "Q" qualifying) with laps and results.

    Telemetry (car data / position) is skipped by default because lap-level
    analysis doesn't need it and it is by far the slowest part to download.
    """
    enable_cache()
    session = fastf1.get_session(year, event, kind)
    session.load(laps=True, telemetry=telemetry, weather=True, messages=True)
    return session
