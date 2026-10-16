import pandas as pd
import pytest

from pitlens.teams.season import Season, points_for, standings, teammate_battles


def season_with(results, quali=None):
    return Season(year=2026, rounds=pd.DataFrame({"Round": [1, 2], "Event": ["A", "B"], "Location": ["a", "b"],
                                                  "Sprint": [False, False]}),
                  results=pd.DataFrame(results), quali=pd.DataFrame(quali or []), stops=pd.DataFrame(),
                  colors={}, missing=[])


def row(rnd, driver, team, pos, classified=True, kind="R"):
    return {"Round": rnd, "Kind": kind, "Driver": driver, "FullName": driver, "Team": team, "Grid": 1,
            "Position": pos, "Status": "Finished" if classified else "Retired", "Points": points_for(pos, kind),
            "Classified": classified, "Dsq": False}


def test_points():
    assert points_for(1, "R") == 25 and points_for(10, "R") == 1 and points_for(11, "R") == 0
    assert points_for(1, "S") == 8 and points_for(9, "S") == 0 and points_for(float("nan"), "R") == 0


def test_standings_add_up_both_cars_and_sprints():
    s = season_with([row(1, "A", "T1", 1), row(1, "B", "T1", 4), row(1, "C", "T2", 2), row(1, "A", "T1", 1, kind="S"),
                     row(2, "C", "T2", 1), row(2, "A", "T1", 3)])
    table = standings(s).set_index("Team")
    assert table.loc["T1", "Points"] == 25 + 12 + 8 + 15 and table.loc["T1", "Wins"] == 1
    assert table.loc["T2", "Podiums"] == 2


def test_teammate_battle_counts_a_retirement_as_behind_and_follows_swaps():
    results = [row(1, "A", "T1", 5), row(1, "B", "T1", 3),
               row(2, "A", "T1", 7), row(2, "B", "T1", None, classified=False)]
    quali = [{"Round": 1, "Driver": "A", "Team": "T1", "Position": 2, "Q1": 90.0, "Q2": 89.5, "Q3": 89.0},
             {"Round": 1, "Driver": "B", "Team": "T1", "Position": 4, "Q1": 90.2, "Q2": 89.7, "Q3": 89.3}]
    battles = teammate_battles(season_with(results, quali), "T1").set_index("Driver")
    assert (battles.loc["A", "RaceWon"], battles.loc["A", "RaceOf"]) == (1, 2)
    assert (battles.loc["B", "QualiWon"], battles.loc["B", "QualiOf"]) == (0, 1)
    assert battles.loc["A", "QualiGap"] == pytest.approx(-0.3)  # Q3: 89.0 against 89.3
