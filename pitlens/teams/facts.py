"""Facts about each team that the timing data doesn't carry: base, power unit, history.

Kept to what changes rarely, as of the 2026 season. Power units are per season, since 2026
brought new engine rules and several teams changed supplier.
"""

TEAMS = {
    "McLaren": {"base": "Woking, United Kingdom", "since": "1966", "titles": 10,
                "power": {2025: "Mercedes", 2026: "Mercedes"}},
    "Ferrari": {"base": "Maranello, Italy", "since": "1950", "titles": 16,
                "power": {2025: "Ferrari", 2026: "Ferrari"}},
    "Red Bull Racing": {"base": "Milton Keynes, United Kingdom", "since": "2005", "titles": 6,
                        "power": {2025: "Honda RBPT", 2026: "Red Bull Ford"}},
    "Mercedes": {"base": "Brackley, United Kingdom", "since": "2010 (from Tyrrell, BAR, Honda and Brawn)",
                 "titles": 8, "power": {2025: "Mercedes", 2026: "Mercedes"}},
    "Aston Martin": {"base": "Silverstone, United Kingdom", "since": "2021 (from Jordan, 1991)", "titles": 0,
                     "power": {2025: "Mercedes", 2026: "Honda"}},
    "Alpine": {"base": "Enstone, United Kingdom", "since": "2021 (from Toleman, Benetton and Renault)",
               "titles": 0, "note": "two more as Renault, 2005 and 2006",
               "power": {2025: "Renault", 2026: "Mercedes"}},
    "Williams": {"base": "Grove, United Kingdom", "since": "1977", "titles": 9,
                 "power": {2025: "Mercedes", 2026: "Mercedes"}},
    "Racing Bulls": {"base": "Faenza, Italy", "since": "2024 (from Minardi, 1985, and Toro Rosso)", "titles": 0,
                     "power": {2025: "Honda RBPT", 2026: "Red Bull Ford"}},
    "Kick Sauber": {"base": "Hinwil, Switzerland", "since": "1993 (as Sauber)", "titles": 0,
                    "power": {2025: "Ferrari"}},
    "Audi": {"base": "Hinwil, Switzerland", "since": "2026 (from Sauber, 1993)", "titles": 0,
             "power": {2026: "Audi"}},
    "Haas F1 Team": {"base": "Kannapolis, United States", "since": "2016", "titles": 0,
                     "power": {2025: "Ferrari", 2026: "Ferrari"}},
    "Cadillac": {"base": "Fishers, United States", "since": "2026", "titles": 0,
                 "power": {2026: "Ferrari"}},
}


def facts(team: str, year: int) -> dict | None:
    """The facts for `team` with its power unit in `year`, or None for a team not listed."""
    entry = TEAMS.get(team)
    if entry is None:
        return None
    return {**{k: v for k, v in entry.items() if k != "power"}, "power": entry["power"].get(year)}
