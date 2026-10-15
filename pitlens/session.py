"""Loading FastF1 sessions with a local, gitignored cache."""

import json
import time
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
    # FastF1 logs every request, and a warning for each part of a session the archive refuses; PitLens
    # reports that itself (and falls back to OpenF1), so only its errors are worth showing.
    fastf1.set_log_level("ERROR")


def load_session(year: int, event: str | int, kind: str = "R", telemetry: bool = False):
    """Load a session (e.g. kind="R" race, "Q" qualifying) with laps and results.

    Telemetry (car data / position) is skipped by default because lap-level
    analysis doesn't need it and it is by far the slowest part to download.
    """
    enable_cache()
    session = fastf1.get_session(year, event, kind)
    session.load(laps=True, telemetry=telemetry, weather=True, messages=True)
    try:
        session.laps  # noqa: B018 (FastF1 logs a warning and carries on when timing fails; fail loudly instead)
    except DataNotLoadedError:
        raise TimingUnavailable(
            f"F1's live-timing archive didn't return timing data for {session.event['EventName']} "
            f"{session.name}. The archive may be refusing requests for now; sessions opened before "
            "still work from the local cache, so try one of those or come back later."
        ) from None
    return session


class TimingUnavailable(RuntimeError):
    """The F1 archive returned no lap timing for a session (network error, or access refused)."""


class ResultsUnavailable(TimingUnavailable):
    """The session loaded but its classification didn't (a passing failure of the results API)."""


# When F1's archive refuses a session, asking again costs several seconds of failed requests,
# so the refusal is remembered for a while and callers go straight to OpenF1.
REFUSALS = CACHE_DIR / "archive_refusals.json"
REFUSAL_TTL_HOURS = 12


def refused_recently(key: str) -> bool:
    try:
        when = json.loads(REFUSALS.read_text()).get(key)
    except (OSError, ValueError):
        return False
    return when is not None and time.time() - when < REFUSAL_TTL_HOURS * 3600


def remember_refusal(key: str) -> None:
    try:
        seen = json.loads(REFUSALS.read_text()) if REFUSALS.exists() else {}
    except (OSError, ValueError):
        seen = {}
    seen[key] = time.time()
    REFUSALS.parent.mkdir(parents=True, exist_ok=True)
    REFUSALS.write_text(json.dumps(seen))
