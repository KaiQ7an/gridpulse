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


def test_photo_finish_follows_the_official_result():
    # 2026 Azerbaijan: lap timing had VER 0.003 s ahead at the flag; RUS won by 0.196 s.
    from pitlens.pitwall.timing import classify_finish

    laps = pd.DataFrame(make_driver("RUS", 80, 3, offset=0.003) + make_driver("VER", 80, 3) + make_driver("HAD", 80, 3, offset=10))
    laps["Position"] = float("nan")
    results = pd.DataFrame({"Abbreviation": ["RUS", "VER", "HAD"], "Position": [1.0, 2.0, 3.0],
                            "GapToLeader": [0.0, 0.196, 10.704]})
    fixed = classify_finish(laps, results, total_laps=3)
    tower = timing_tower(fixed, 3)
    assert tower["Driver"].tolist() == ["RUS", "VER", "HAD"]
    assert tower.loc[1, "Gap"] == "+0.196"
    assert tower.loc[2, "Gap"] == "+10.704"
    # Earlier laps keep their own timing.
    assert timing_tower(fixed, 2)["Driver"].tolist()[0] == "VER"


def test_official_gaps_from_fastf1_results():
    from pitlens.pitwall.timing import official_gaps

    # FastF1 (2026 Singapore): lapped cars carry a Time too, but it isn't a gap to the winner.
    results = pd.DataFrame({"Abbreviation": ["A", "B", "C", "D"], "Position": [1.0, 2.0, 3.0, 4.0],
                            "Time": pd.to_timedelta([5400.0, 1.5, 2.171, None], unit="s"),
                            "Laps": [62.0, 62.0, 61.0, 36.0], "Status": ["Finished", "Finished", "Lapped", "Retired"]})
    gaps = official_gaps(results)
    assert gaps.to_dict() == {"A": 0.0, "B": 1.5}


def test_near_tie_follows_the_running_position():
    # B's lap end time is 0.1 s earlier than A's, but the timing feed has A ahead: trust the feed.
    laps = pd.DataFrame(make_driver("A", 80, 2) + make_driver("B", 80, 2, offset=-0.1) + make_driver("C", 80, 2, offset=3))
    laps["Position"] = laps["Driver"].map({"A": 1.0, "B": 2.0, "C": 3.0})
    tower = timing_tower(laps, 2)
    assert tower["Driver"].tolist() == ["A", "B", "C"]
    assert tower.loc[1, "GapSeconds"] >= 0
    assert tower.loc[2, "Gap"] == "+3.000"
    # Further apart than the tie window, the clock wins whatever the position column says.
    laps["Time"] = laps["Time"] - pd.to_timedelta((laps["Driver"] == "B") * 2.0, unit="s")
    assert timing_tower(laps, 2)["Driver"].tolist() == ["B", "A", "C"]


def test_non_starters():
    from pitlens.pitwall.timing import non_starters

    results = pd.DataFrame({"Status": ["Finished", "Retired", "Did not start", None, "Lapped"],
                            "ClassifiedPosition": ["1", "R", "W", "W", "2"]})
    assert non_starters(results).tolist() == [False, False, True, True, False]


def test_missing_last_lap_times_are_filled_from_the_result():
    # Like OpenF1 for the 2026 Australian GP: no time for anyone's last lap, and no last lap at all for B.
    from pitlens.pitwall.timing import complete_final_laps

    laps = pd.DataFrame(make_driver("A", 80, 5) + make_driver("B", 80, 4, offset=3) + make_driver("C", 85, 4))
    laps["LapStartTime"] = laps["Time"] - laps["LapTime"]
    laps.loc[(laps["Driver"] == "A") & (laps["LapNumber"] == 5), ["Time", "LapTime"]] = pd.NaT
    laps.loc[(laps["Driver"] == "C") & (laps["LapNumber"] == 4), ["Time", "LapTime"]] = pd.NaT
    results = pd.DataFrame({"Abbreviation": ["A", "B", "C"], "Position": [1.0, 2.0, 3.0],
                            "GapToLeader": [0.0, 2.5, None], "Status": ["Finished", "Finished", "Lapped"]})
    done = complete_final_laps(laps, results, total_laps=5)
    tower = timing_tower(done, 5)
    assert tower["Driver"].tolist() == ["A", "B", "C"]
    assert tower.loc[0, "Gap"] == "Leader" and tower.loc[1, "Gap"] == "+2.500"
    assert tower.loc[2, "Gap"] == "+1 lap"
    a5 = done[(done["Driver"] == "A") & (done["LapNumber"] == 5)]["Time"].iloc[0]
    assert a5 == pd.to_timedelta(400, unit="s")  # lap 5 start (320 s) plus A's usual 80 s


def test_laps_beyond_the_classified_count_are_dropped():
    from pitlens.pitwall.timing import trim_to_classified_laps

    laps = pd.DataFrame(make_driver("A", 80, 5) + make_driver("B", 85, 5))
    results = pd.DataFrame({"Abbreviation": ["A", "B"], "Laps": [5.0, 4.0]})
    trimmed = trim_to_classified_laps(laps, results)
    assert trimmed.groupby("Driver")["LapNumber"].max().to_dict() == {"A": 5, "B": 4}


def test_lap_coverage():
    from pitlens.pitwall.timing import lap_coverage

    laps = pd.DataFrame(make_driver("A", 80, 10) + make_driver("B", 80, 5))
    results = pd.DataFrame({"Abbreviation": ["A", "B", "C"], "Laps": [10.0, 10.0, 0.0]})
    assert lap_coverage(laps, results) == pytest.approx(0.75)


def test_tower_counts_stops_from_the_stop_list_when_given(race):
    # BBB's stint number says one stop; the stop list also has an earlier stop the stints missed.
    stops = pd.DataFrame({"Driver": ["BBB", "BBB"], "Lap": [4, 10]})
    tower = timing_tower(race, 11, stops=stops).set_index("Driver")
    assert tower.loc["BBB", "Stops"] == 2 and tower.loc["AAA", "Stops"] == 0
    assert timing_tower(race, 10, stops=stops).set_index("Driver").loc["BBB", "Stops"] == 1  # in-lap 10 not done yet
