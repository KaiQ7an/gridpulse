"""Loading FastF1 sessions with a local, gitignored cache."""

from pathlib import Path

import fastf1
from fastf1.exceptions import DataNotLoadedError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def enable_cache() -> None:
    """Point FastF1 at ./cache so repeat runs don't re-download data."""
    CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    fastf1.set_log_level("WARNING")  # FastF1's per-request INFO logs drown out our own output


def load_session(year: int, event: str | int, kind: str = "R", telemetry: bool = False):
    """Load a session (e.g. kind="R" race, "Q" qualifying) with laps and results.

    Telemetry (car data / position) is skipped by default because lap-level
    analysis doesn't need it and it is by far the slowest part to download.
    """
    enable_cache()
    session = fastf1.get_session(year, event, kind)
    session.load(laps=True, telemetry=telemetry, weather=True, messages=True)
    try:
        session.laps  # FastF1 logs a warning and carries on when timing fails; fail loudly instead
    except DataNotLoadedError:
        raise TimingUnavailable(
            f"F1's live-timing archive didn't return timing data for {session.event['EventName']} "
            f"{session.name}. The archive may be refusing requests for now; sessions opened before "
            "still work from the local cache, so try one of those or come back later."
        ) from None
    return session


class TimingUnavailable(RuntimeError):
    """The F1 archive returned no lap timing for a session (network error, or access refused)."""
