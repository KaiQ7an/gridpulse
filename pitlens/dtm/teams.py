"""Operating teams behind the season-specific sponsored DTM entrant names."""

import json
from functools import lru_cache
from pathlib import Path

from pitlens.dtm import data

ALIASES = {
    "Manthey": "manthey", "Manthey EMA": "manthey", "Manthey Junior Team": "manthey",
    "Schubert Motorsport": "schubert", "ABT Sportsline": "abt", "Red Bull Team ABT": "abt",
    "EMIL FREY RACING": "emil-frey", "HRT Ford Racing": "hrt", "HRT Ford Performance": "hrt",
    "Mercedes-AMG Team HRT": "hrt", "Comtoyou Racing": "comtoyou",
    "Doerr Motorsport": "doerr", "Dörr Motorsport": "doerr",
    "Land Motorsport": "land", "Land-Motorsport": "land", "Mercedes-AMG Team Landgraf": "landgraf",
    "Mercedes-AMG Team BWT": "landgraf", "Landgraf Motorsport": "landgraf",
    "Mercedes-AMG Team WINWARD": "winward", "Mercedes-AMG Team Winward Racing": "winward",
    "Mercedes-AMG Team RAVENOL": "winward", "Winward Racing": "winward", "WINWARD RACING": "winward",
    "GRT Grasser-Racing-Team": "grasser", "TGI Team by GRT": "grasser",
    "TGI Team Lamborghini by GRT": "grasser", "Lamborghini Team Liqui Moly by GRT": "grasser",
    "Lamborghini Team TGI by GRT": "grasser", "Paul Motorsport": "paul", "SSR Performance": "ssr",
    "Team75 Motorsport": "team75", "KÜS Team Bernhard": "team75", "Project 1": "project1",
    "Toksport WRT": "toksport", "Tresor Orange 1": "attempto", "Tresor Attempto Racing": "attempto",
    "LIQUI MOLY Team Engstler": "engstler", "Liqui Moly Team Engstler": "engstler",
    "Seyffarth Motorsport": "seyffarth",
}


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(Path(__file__).with_name("teams.json").read_text())


def identity(year: int, entrant: str) -> str:
    # The sponsor moved from Landgraf to Winward after 2023; it is not a fixed team identity.
    if entrant == "Mercedes-AMG Team MANN-FILTER":
        return "landgraf" if year == 2023 else "winward"
    return ALIASES.get(entrant, data.key(entrant))


def participants(season: dict) -> dict:
    """Only actual race entrants in this season, including guests, grouped by operator."""
    rows = data.race_rows(season)
    result = {}
    for entrant in rows.team.unique():
        team_id = identity(season["year"], entrant)
        info = catalog().get(team_id, {"name": entrant, "history": "Profile research pending.", "sources": []})
        result.setdefault(team_id, {**info, "entries": []})["entries"].append(entrant)
    return dict(sorted(result.items(), key=lambda item: item[1]["name"].casefold()))
