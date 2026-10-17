"""A replay must give the same analysis even when future laps change."""

from dataclasses import replace

import pandas as pd
import pytest

from gridpulse.pitwall.data import load_race
from gridpulse.undercut.analysis import pair_gap
from gridpulse.undercut.charts import battle_chart


@pytest.fixture
def race(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    return load_race(2026, 17)


def test_future_fastest_laps_cannot_change_the_replay_clean_laps(race):
    lap = 12
    expected = race.clean_through(lap)
    changed = race.laps.copy()
    changed.loc[changed["LapNumber"] > lap, "LapTime"] *= 0.7
    pd.testing.assert_frame_equal(replace(race, laps=changed).clean_through(lap), expected)
    pd.testing.assert_frame_equal(
        replace(race, laps=race.laps[race.laps["LapNumber"] <= lap]).clean_through(lap), expected)


def test_stop_measurements_wait_for_the_out_lap_without_changing_the_race(race):
    stop = race.stops.dropna(subset=["Loss"]).iloc[0]
    lap = int(stop["Lap"])
    columns = ["LaneTime", "Stationary", "Loss", "PosAfter"]
    now = race.stops_through(lap)
    assert now.loc[now["Lap"] == lap, columns].isna().all().all()
    after = race.stops_through(lap + 1)
    assert after.loc[stop.name, "Loss"] == stop["Loss"]
    assert race.stops.loc[stop.name, "Loss"] == stop["Loss"]


def test_battle_chart_does_not_reveal_five_future_laps(race):
    battle = race.battles.query("FirstStop == 'HAM' and Rival == 'ANT'").iloc[0]
    current = int(battle["RivalStopLap"]) + 1
    gap = pair_gap(race.laps, battle["FirstStop"], battle["Rival"])
    replay = battle_chart(gap, battle, race.total_laps, through_lap=current)
    report = battle_chart(gap, battle, race.total_laps)
    assert max(replay.data[0].x) == current
    assert max(report.data[0].x) > current  # complete reports still show the whole battle


def test_an_unknown_grid_does_not_fall_back_to_the_final_classification(race):
    from gridpulse.pitwall.app import starting_order

    results = race.results.assign(GridPosition=float("nan"))
    unknown_grid = replace(race, results=results)
    assert starting_order(unknown_grid) == sorted(race.entrants["Driver"])
