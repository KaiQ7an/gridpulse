import pandas as pd
import pytest

from pitlens.season.data import (
    Season,
    driver_highlights,
    driver_season,
    driver_standings,
    points_by_round,
    points_for,
    pole_sitters,
    standings,
    teammate_battles,
)

QUALI_COLUMNS = ["Round", "Driver", "Team", "Position", "Q1", "Q2", "Q3"]


def season_with(results, quali=None, fastest=None, rounds=2):
    return Season(year=2026, rounds=pd.DataFrame({"Round": range(1, rounds + 1),
                                                  "Event": [f"E{i} Grand Prix" for i in range(1, rounds + 1)],
                                                  "Location": [f"e{i}" for i in range(1, rounds + 1)],
                                                  "Sprint": [False] * rounds}),
                  results=pd.DataFrame(results), quali=pd.DataFrame(quali or [], columns=QUALI_COLUMNS),
                  stops=pd.DataFrame(), led=pd.DataFrame(columns=["Round", "Kind", "Driver", "Laps"]),
                  fastest=pd.DataFrame(fastest or [], columns=["Round", "Driver", "LapTime"]), colors={}, missing=[])


def row(rnd, driver, team, pos, classified=True, kind="R", grid=1):
    return {"Round": rnd, "Kind": kind, "Driver": driver, "FullName": driver, "Team": team, "Grid": grid,
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


def test_drivers_standings_and_points_progress():
    s = season_with([row(1, "A", "T1", 1), row(1, "B", "T2", 2), row(1, "B", "T2", 1, kind="S"),
                     row(2, "A", "T1", 2), row(2, "B", "T2", 1)],
                    fastest=[{"Round": 1, "Driver": "B", "LapTime": 80.0}])
    table = driver_standings(s).set_index("Driver")
    assert list(table.index) == ["B", "A"]  # 18 + 8 + 25 against 25 + 18
    assert table.loc["B", "Points"] == 51 and table.loc["B", "FastestLaps"] == 1 and table.loc["A", "Wins"] == 1
    progress = points_by_round(s)
    assert progress.loc[1, "B"] == 26 and progress.loc[2, "A"] == 43


def test_pole_goes_to_the_car_that_starts_first():
    results = [row(1, "A", "T1", 1, grid=6), row(1, "B", "T1", 2, grid=1),
               row(2, "A", "T1", 1, grid=None), row(2, "B", "T1", 2, grid=None)]
    quali = [{"Round": r, "Driver": "A", "Team": "T1", "Position": 1, "Q1": 90.0, "Q2": 89.5, "Q3": 89.0}
             for r in (1, 2)]
    s = season_with(results, quali)  # round 1: A fastest, but a grid penalty puts B first; round 2: no grid
    assert pole_sitters(s).to_dict() == {1: "B", 2: "A"}
    assert driver_standings(s).set_index("Driver")["Poles"].to_dict() == {"A": 1, "B": 1}


def test_driver_season_and_highlights():
    results = [row(1, "A", "T1", 1, grid=1), row(1, "A", "T1", 3, kind="S"),
               row(2, "A", "T1", 4, grid=12), row(3, "A", "T1", 1, grid=5),
               row(4, "A", "T1", None, classified=False, grid=2)]
    quali = [{"Round": r, "Driver": "A", "Team": "T1", "Position": p, "Q1": 90.0, "Q2": 89.5, "Q3": 89.0}
             for r, p in ((1, 1), (2, 12), (3, 5), (4, 2))]
    s = season_with(results, quali, fastest=[{"Round": 1, "Driver": "A", "LapTime": 80.0}], rounds=4)
    rows = driver_season(s, "A")
    assert rows["Event"].tolist() == ["E1", "E2", "E3", "E4"]
    assert rows.loc[0, "Points"] == 25 + 6 and rows.loc[0, "Sprint"] == 3 and rows.loc[0, "Pole"]
    found = {label: (value, detail) for label, value, detail in driver_highlights(rows)}
    assert found["Best comeback"] == ("+8 places", "E2: P12 to P4")
    assert found["Win from furthest back"] == ("P5", "E3")
    assert found["Poles turned into wins"][0] == "1 of 1"
    assert found["Hat-tricks"][0] == "1"
    assert found["Longest run in the points"] == ("3 races", "E1 to E3")
    assert found["Lowest finish"] == ("P4", "E2")
