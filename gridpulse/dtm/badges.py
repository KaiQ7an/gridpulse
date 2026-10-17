"""Sourced identity marks; affiliations always come from selected-season results."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(Path(__file__).with_name("badges.json").read_text())


def marks(year: int, team_id: str, manufacturers: list[str]) -> list[dict]:
    result = []
    team = catalog()["teams"].get(team_id)
    if team and year in team.get("years", [year]):
        result.append({**team, "label": "Team identity", "scope": "Published team mark; logo design is not a historical reconstruction."})
    for manufacturer in sorted(set(manufacturers)):
        brand = catalog()["manufacturers"].get(manufacturer)
        if brand:
            result.append({**brand, "label": f"{year} car manufacturer", "scope": "Car brand, not a claim of factory-team status."})
    return result
