"""Season-specific GT3 models, with independently attributed reference photos.

The live classification's `car` field only identifies the manufacturer. The
official season entry lists resolve the model, including the 2025/2026 upgrades.
Photos illustrate a model and are not claimed as each driver's exact livery.
"""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(Path(__file__).with_name("cars.json").read_text())


def profile(year: int, manufacturer: str) -> dict:
    book = catalog()
    model_id = book["seasons"].get(str(year), {}).get(manufacturer)
    if not model_id:
        return {"name": "Model not confirmed", "photo": None}
    return {**book["models"][model_id], "sources": book["sources"][str(year)]}


def model(year: int, manufacturer: str) -> str:
    return profile(year, manufacturer)["name"]
