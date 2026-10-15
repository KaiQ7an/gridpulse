import pandas as pd
import pytest

from pitlens.pitwall.timing import (
    format_lap_time,
    gap_to_leader,
    neutralised_periods,
    retired_drivers,
    stint_timeline,
    timing_tower,
    track_status,
)


def make_driver(driver, lap_time, n_laps, offset=0.0, pit_after=None):
    rows = []
    for lap in range(1, n_laps + 1):
        stint = 1 if pit_after is None or lap <= pit_after else 2
        rows.append(
            {
                "Driver": driver,
                "Team": "Team " + driver,
                "LapNumber": lap,
                "Time": pd.to_timedelta(offset + lap * lap_time, unit="s"),
                "LapTime": pd.to_timedelta(lap_time, unit="s"),
                "Stint": stint,
                "Compound": "MEDIUM" if stint == 1 else "HARD",
                "TyreLife": lap if stint == 1 else lap - pit_after,
                "PitInTime": pd.to_timedelta(1, unit="s") if lap == pit_after else pd.NaT,
            }
        )
    return rows


@pytest.fixture
def race():
    # AAA leads at 80 s/lap; BBB is 2 s behind and pits after lap 10;
    # CCC runs 85 s/lap and gets lapped; DDD retires after lap 5.
    rows = (
        make_driver("AAA", 80, 20)
        + make_driver("BBB", 80, 20, offset=2, pit_after=10)
        + make_driver("CCC", 85, 19)
        + make_driver("DDD", 81, 5)
    )
    return pd.DataFrame(rows)


def test_tower_orders_and_gaps(race):
    tower = timing_tower(race, 10, retired={"DDD"})
    assert tower["Driver"].tolist() == ["AAA", "BBB", "CCC", "DDD"]
    assert tower.loc[0, "Gap"] == "Leader"
    assert tower.loc[1, "Gap"] == "+2.000"
    assert tower.loc[1, "Interval"] == "+2.000"
    assert tower.loc[2, "Gap"] == "+50.000"
    assert tower.loc[2, "Interval"] == "+48.000"
    assert tower.loc[3, "Gap"] == "OUT"


def test_tower_marks_pit_stop_and_new_stint(race):
    at_pit = timing_tower(race, 10).set_index("Driver")
    assert at_pit.loc["BBB", "Pit"]
    assert at_pit.loc["BBB", "Stops"] == 0
    after = timing_tower(race, 11).set_index("Driver")
    assert after.loc["BBB", "Stops"] == 1
    assert after.loc["BBB", "Compound"] == "HARD"
    assert after.loc["BBB", "TyreAge"] == 1


def test_tower_shows_lapped_cars(race):
    # CCC finishes lap 17 at 1445 s, after AAA finished lap 18 (1440 s).
    tower = timing_tower(race, 17, retired={"DDD"}).set_index("Driver")
    assert tower.loc["CCC", "Gap"] == "+1 lap"
    assert tower.loc["CCC", "Interval"] == ""
    # On the final lap CCC never completes lap 20 but did take the flag.
    final = timing_tower(race, 20, retired={"DDD"}).set_index("Driver")
    assert final.loc["CCC", "Gap"] == "+1 lap"
    assert final.loc["DDD", "Gap"] == "OUT"


def test_gap_to_leader(race):
    gaps = gap_to_leader(race).set_index(["Driver", "LapNumber"])["Gap"]
    assert gaps[("AAA", 5)] == 0
    assert gaps[("BBB", 5)] == pytest.approx(2)
    assert gaps[("CCC", 10)] == pytest.approx(50)


def test_stint_timeline(race):
    stints = stint_timeline(race).set_index(["Driver", "Stint"])
    assert stints.loc[("BBB", 1), "EndLap"] == 10
    assert stints.loc[("BBB", 2), "StartLap"] == 11
    assert stints.loc[("BBB", 2), "Compound"] == "HARD"
    assert stints.loc[("BBB", 2), "Laps"] == 10


def test_track_status_picks_most_severe():
    assert track_status("1") == "Green"
    assert track_status("124") == "Safety car"
    assert track_status("26") == "VSC"
    assert track_status(None) == "Unknown"


def test_retired_drivers():
    results = pd.DataFrame({"Abbreviation": ["A", "B", "C", "D"], "Status": ["Finished", "Lapped", "+1 Lap", "Retired"]})
    assert retired_drivers(results) == {"D"}


def test_format_lap_time():
    assert format_lap_time(pd.to_timedelta(81.3456, unit="s")) == "1:21.346"
    assert format_lap_time(pd.NaT) == ""


def test_neutralised_periods_groups_consecutive_laps():
    laps = pd.DataFrame(
        {
            "LapNumber": [1, 2, 3, 4, 5, 6, 7, 7],
            "TrackStatus": ["1", "14", "4", "41", "1", "6", "1", "67"],
        }
    )
    assert neutralised_periods(laps) == [("Safety car", 2, 4), ("VSC", 6, 7)]
