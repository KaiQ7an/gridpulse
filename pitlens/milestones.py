"""Sourced first-points and first-win records, independent of saved season coverage."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(Path(__file__).with_name("milestones.json").read_text())


def profile(series: str, kind: str, identity: str) -> dict:
    return catalog().get(series, {}).get(kind, {}).get(identity, {})


def milestone(series: str, kind: str, identity: str, name: str, year: int) -> tuple[str, dict | None]:
    """Missing older history is unknown, not evidence that a first has not happened."""
    entry = profile(series, kind, identity)
    record = entry.get(name)
    if record and record.get("verified_first"):
        return ("achieved", record) if record["year"] <= year else ("not_yet", None)
    return ("not_yet", None) if entry.get("complete") and not record else ("unverified", None)
