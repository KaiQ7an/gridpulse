"""The championship tables worked out from the saved races, against the official final standings.

Points come from the results where F1's archive gives them and are worked out otherwise (OpenF1
doesn't carry them), including the 2019-2024 point for the fastest lap, so this checks the
results, the sprints and every fastest lap that scored together.
"""

from dataclasses import replace

import pytest

from gridpulse.season.data import driver_standings, load_season, standings

OFFICIAL = {
    2023: ({"VER": 575, "PER": 285, "HAM": 234, "ALO": 206, "LEC": 206, "NOR": 205, "SAI": 200, "RUS": 175,
            "PIA": 97, "STR": 74, "GAS": 62, "OCO": 58, "ALB": 27, "TSU": 17, "BOT": 10, "HUL": 9, "RIC": 6,
            "ZHO": 6, "MAG": 3, "LAW": 2, "SAR": 1, "DEV": 0},
           {"Red Bull Racing": 860, "Mercedes": 409, "Ferrari": 406, "McLaren": 302, "Aston Martin": 280}),
    2024: ({"VER": 437, "NOR": 374, "LEC": 356, "PIA": 292, "SAI": 290, "RUS": 245, "HAM": 223, "PER": 152,
            "ALO": 70, "GAS": 42, "HUL": 41, "TSU": 30, "STR": 24, "OCO": 23, "MAG": 16, "ALB": 12, "RIC": 12,
            "BEA": 7, "COL": 5, "ZHO": 4, "LAW": 4, "BOT": 0, "SAR": 0, "DOO": 0},
           {"McLaren": 666, "Ferrari": 652, "Red Bull Racing": 589, "Mercedes": 468}),
    2025: ({"NOR": 423, "VER": 421, "PIA": 410, "RUS": 319, "LEC": 242, "HAM": 156},
           {"McLaren": 833, "Mercedes": 469, "Red Bull Racing": 451, "Ferrari": 398}),
}


@pytest.mark.parametrize("year", sorted(OFFICIAL))
def test_final_standings_match_the_official_ones(year, monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    season = load_season(year)
    assert not season.missing
    drivers, teams = OFFICIAL[year]
    ours = driver_standings(season).set_index("Driver")["Points"]
    assert {d: ours.get(d) for d in drivers} == drivers
    assert list(ours.index[:len(drivers)]) == list(drivers)
    ours = standings(season).set_index("Team")["Points"]
    assert {t: ours.get(t) for t in teams} == teams


def test_poles_go_to_the_car_that_starts_first(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    poles = driver_standings(load_season(2023)).set_index("Driver")["Poles"]
    # Verstappen was fastest in qualifying 13 times, but a gearbox penalty in Belgium gave Leclerc pole.
    assert poles[poles > 0].to_dict() == {"VER": 12, "LEC": 5, "PER": 2, "SAI": 2, "HAM": 1}


def test_partial_season_and_missing_sprint_do_not_claim_a_champion(monkeypatch):
    from gridpulse.pitwall.season_page import headline
    from gridpulse.season.data import round_winners

    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    season = load_season(2025)
    assert season.complete
    partial = replace(season, results=season.results[season.results["Round"] <= 19],
                      rounds=season.rounds[season.rounds["Round"] <= 19])
    assert not partial.complete
    text = " ".join(headline(2025, driver_standings(partial), standings(partial), round_winners(partial),
                             complete=partial.complete))
    assert "champion " not in text and "final standings" not in text and "Oscar Piastri leads" in text
    missing_sprint = replace(season, results=season.results[~((season.results["Round"] == 23)
                                                              & (season.results["Kind"] == "S"))])
    assert missing_sprint.missing_sprints == [23]
    assert not missing_sprint.complete


def test_missing_rounds_are_found_against_the_completed_calendar(monkeypatch):
    from gridpulse import snapshots

    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    saved = snapshots.races(2025)
    monkeypatch.setattr(snapshots, "races", lambda year: saved[saved.RoundNumber != 24])
    season = load_season(2025)
    assert season.missing == [24] and not season.complete
