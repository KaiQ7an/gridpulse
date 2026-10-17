"""Facts about each team that the timing data doesn't carry: base, power unit, history.

Kept to what changes rarely, as of the 2026 season (checked in October 2026). Power units are
per season, since 2026 brought new engine rules and several teams changed supplier. Titles are
constructors' championships verified through 2025 and filtered to the selected year.
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
    "Haas F1 Team": {"base": "Kannapolis, United States, and Banbury, United Kingdom", "since": "2016", "titles": 0,
                     "power": {2025: "Ferrari", 2026: "Ferrari"}},
    "Cadillac": {"base": "Fishers, United States, and Silverstone, United Kingdom", "since": "2026", "titles": 0,
                 "power": {2026: "Ferrari"}},
}


def facts(team: str, year: int) -> dict | None:
    """The facts for `team` with its power unit in `year`, or None for a team not listed."""
    entry = TEAMS.get(team)
    if entry is None:
        return None
    founded, slug, history, championships = HISTORY[team]
    honours_through = min(year, 2025)  # no championship inferred from an unfinished live season
    years = [y for y in championships if y <= honours_through]
    return {**{k: v for k, v in entry.items() if k != "power"}, "power": entry["power"].get(year),
            "founded": founded, "history": history, "title_years": years, "titles": len(years),
            "honours_through": honours_through, "source": f"https://www.formula1.com/en/teams/{slug}"}

# Explicit constructor identities: predecessor titles are described, never inherited.
HISTORY = {
    "McLaren": ("1963", "mclaren", "Bruce McLaren founded the racing organisation in 1963 and made its F1 debut in 1966. The Woking team became a title-winning constructor with Emerson Fittipaldi, James Hunt, Niki Lauda, Alain Prost and Ayrton Senna, and later returned to the front with its modern Mercedes-powered programme.", [1974, 1984, 1985, 1988, 1989, 1990, 1991, 1998, 2024, 2025]),
    "Ferrari": ("1929 (Scuderia)", "ferrari", "Enzo Ferrari’s Scuderia predates Formula 1 and has contested the championship since 1950. Its Maranello operation combines chassis and engine development. Championship eras include Alberto Ascari, Niki Lauda and Michael Schumacher; the constructors’ record below belongs to Ferrari itself.", [1961, 1964, 1975, 1976, 1977, 1979, 1982, 1983, 1999, 2000, 2001, 2002, 2003, 2004, 2007, 2008]),
    "Red Bull Racing": ("2005", "red-bull-racing", "Red Bull acquired Jaguar’s Milton Keynes operation and entered under its own name in 2005. Sebastian Vettel delivered four consecutive drivers’ titles, followed by another championship era with Max Verstappen. Jaguar and Stewart results are not included in Red Bull’s title record.", [2010, 2011, 2012, 2013, 2022, 2023]),
    "Mercedes": ("2010 (current works team)", "mercedes", "The modern Mercedes works team took over Brawn GP for 2010. Its Brackley organisation has roots in Tyrrell, BAR and Honda. The hybrid era brought eight consecutive constructors’ championships from 2014 to 2021; Brawn’s 2009 title remains a separate constructor’s achievement.", list(range(2014, 2022))),
    "Aston Martin": ("2021 (current identity)", "aston-martin", "The Silverstone organisation became Aston Martin in 2021 after racing as Racing Point and Force India, with roots in Jordan. This is the current team’s lineage, separate from Aston Martin’s brief 1959–60 Formula 1 programme.", []),
    "Alpine": ("2021 (current identity)", "alpine", "Renault renamed its Enstone F1 team Alpine for 2021. The operation’s earlier identities include Toleman, Benetton, Renault and Lotus. Benetton’s 1995 and Renault’s 2005–06 constructors’ championships are predecessor honours, not Alpine constructors’ titles.", []),
    "Williams": ("1977", "williams", "Frank Williams and Patrick Head established Williams Grand Prix Engineering in 1977. The Grove team became a leading constructor through its work with engine partners including Honda and Renault. Its nine constructors’ championships span the 1980s and 1990s.", [1980, 1981, 1986, 1987, 1992, 1993, 1994, 1996, 1997]),
    "Racing Bulls": ("2025 (Racing Bulls name)", "racing-bulls", "Red Bull’s Faenza-based sister team follows the Minardi, Toro Rosso, AlphaTauri and RB identities. It develops young drivers alongside experienced racers. Toro Rosso’s 2008 and AlphaTauri’s 2020 Italian Grand Prix victories belong to those earlier identities.", []),
    "Kick Sauber": ("1993 (Sauber F1 entry)", "audi", "Peter Sauber’s Swiss racing organisation entered Formula 1 in 1993. It later raced with BMW ownership and Alfa Romeo branding before the Kick Sauber seasons of 2024–25. The Hinwil operation became Audi’s works team for 2026; BMW Sauber’s 2008 race win is a predecessor result.", []),
    "Audi": ("2026 (Audi F1 identity)", "audi", "Audi entered Formula 1 in 2026 through its acquisition of the Sauber operation. Chassis work is based in Hinwil, with the Audi power-unit programme in Neuburg. Sauber’s earlier Formula 1 history is part of the operation’s background rather than an Audi title record.", []),
    "Haas F1 Team": ("2016 (F1 debut)", "haas", "Gene Haas’s American team joined Formula 1 in 2016. It operates across Kannapolis and Banbury, using Ferrari power units and a technical model built around specialist partners. Its debut season began with points in Australia.", []),
    "Cadillac": ("2026 (F1 debut)", "cadillac", "The Cadillac programme joined Formula 1 as the grid’s eleventh team in 2026. Its US and UK operation began with Ferrari power units while General Motors developed a future works engine programme. Cadillac’s sports-car honours are separate from this F1 constructor’s record.", []),
    "AlphaTauri": ("2020 (AlphaTauri name)", "racing-bulls", "Toro Rosso was renamed AlphaTauri for 2020. The Faenza operation scored its first victory under that name with Pierre Gasly at the 2020 Italian Grand Prix. It raced as AlphaTauri through 2023 before the RB identity followed.", []),
    "RB": ("2024 (RB name)", "racing-bulls", "The Faenza team raced as RB in 2024 after the AlphaTauri identity. Its roots reach back through Toro Rosso to Minardi. The constructor name in this profile follows the selected season instead of retroactively applying the Racing Bulls name.", []),
    "Alfa Romeo": ("2019 (Sauber branding)", "audi", "Sauber’s Hinwil operation raced with Alfa Romeo branding from 2019 to 2023. This modern partnership is distinct from Alfa Romeo’s 1950s works team and its drivers’ championships. The operation returned to Sauber branding before becoming Audi in 2026.", []),
}
TEAMS["Racing Bulls"]["since"] = "2025 (from RB, AlphaTauri, Toro Rosso and Minardi)"
TEAMS["AlphaTauri"] = {"base": "Faenza, Italy", "since": "2020 (from Toro Rosso)", "titles": 0,
                       "power": {2023: "Honda RBPT"}}
TEAMS["RB"] = {"base": "Faenza, Italy", "since": "2024 (from AlphaTauri)", "titles": 0,
               "power": {2024: "Honda RBPT"}}
TEAMS["Alfa Romeo"] = {"base": "Hinwil, Switzerland", "since": "2019 (Sauber operation)", "titles": 0,
                       "power": {2023: "Ferrari"}}
for _team, _entry in TEAMS.items():
    if _team not in ("AlphaTauri", "RB", "Alfa Romeo", "Audi", "Cadillac"):
        _entry["power"].update({2023: _entry["power"].get(2025), 2024: _entry["power"].get(2025)})
