"""Offline circuit reference: sourced layout facts and venue-level historical records."""

import json
from functools import lru_cache
from pathlib import Path

REGIONS = {
    "world": {"name": "World", "title": "A world built for racing.", "center": [20, 20]},
    "europe": {"name": "Europe & Caucasus", "title": "The heartland of Grand Prix racing.",
               "center": [16, 48], "bounds": [-16, 33, 54, 62]},
    "americas": {"name": "The Americas", "title": "From the Strip to the Senna S.",
                 "center": [-85, 8], "bounds": [-130, -38, -35, 58]},
    "asia-pacific": {"name": "Asia-Pacific", "title": "From first light to the night race.",
                     "center": [120, 3], "bounds": [80, -46, 157, 48]},
    "middle-east": {"name": "Middle East", "title": "Racing under desert skies.",
                    "center": [47, 26], "bounds": [34, 17, 59, 33]},
}


@lru_cache(maxsize=1)
def _catalog(revision: int) -> list[dict]:
    return json.loads(Path(__file__).with_name("atlas.json").read_text())["circuits"]


def catalog() -> list[dict]:
    return _catalog(Path(__file__).with_name("atlas.json").stat().st_mtime_ns)


def circuit_fact(slug: str | None) -> dict | None:
    aliases = {"monaco": "monte-carlo", "singapore": "marina-bay", "sepang": "kuala-lumpur",
               "abu-dhabi": "yas-island", "miami": "miami-gardens", "sao-paolo": "sao-paulo"}
    slug = aliases.get(slug, slug)
    return next((c for c in catalog() if c["slug"] == slug), None)


def in_region(region: str) -> list[dict]:
    return [c for c in catalog() if region == "world" or c["region"] == region]


def browse_circuits(region: str, search: str = "", kind: str = "All", sort: str = "Atlas order") -> list[dict]:
    """Filter a region's venues without changing the shared reference catalog."""
    query = search.strip().casefold()
    facts = [c for c in in_region(region)
             if (kind == "All" or c["kind"] == kind)
             and query in f"{c['name']} {c['city']} {c['country']} {c['slug']}".casefold()]
    order = {"Name": lambda c: c["city"].casefold(), "Longest first": lambda c: -c["length_km"],
             "Oldest first": lambda c: (c["first_gp"], c["city"])}
    return sorted(facts, key=order[sort]) if sort in order else facts


def record_holders(records: list[dict]) -> str:
    return " / ".join(r["driver"] for r in records) or "No classified result yet"
