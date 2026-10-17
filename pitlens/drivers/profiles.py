"""Offline biographical facts. Season teams and results always come from race data."""

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit


@lru_cache(maxsize=2)
def catalog(series: str) -> dict:
    if series not in ("f1", "dtm"):
        raise ValueError("Unsupported driver catalogue")
    return json.loads(Path(__file__).with_name(f"{series}.json").read_text())


def profile(series: str, driver: str) -> dict:
    return catalog(series).get(driver, {})


def birth_date(value: str) -> str:
    for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, pattern).strftime("%d %B %Y")
        except (TypeError, ValueError):
            continue
    return "Not published"


def public_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in ("https", "http") and parsed.netloc else None
