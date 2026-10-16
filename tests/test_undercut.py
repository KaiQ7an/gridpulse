import pandas as pd
import pytest

from pitlens.undercut.analysis import pair_gap, pit_battles, pit_loss, pit_stops, rejoin_projection


def make_car(driver, lap_times, offset=0.0, pit_in=None, status=None):
    """Laps for one car from a list of lap times; pits at the end of lap `pit_in`."""
    rows, t = [], offset
    for n, lt in enumerate(lap_times, start=1):
        t += lt
        stint = 1 if pit_in is None or n <= pit_in else 2
        rows.append(
            {
                "Driver": driver,
                "LapNumber": n,
                "Time": pd.to_timedelta(t, unit="s"),
                "LapTime": pd.to_timedelta(lt, unit="s"),
                "PitInTime": pd.to_timedelta(t - 5, unit="s") if n == pit_in else pd.NaT,
                "PitOutTime": pd.to_timedelta(t - lt + 17, unit="s") if pit_in and n == pit_in + 1 else pd.NaT,
                "Compound": "MEDIUM" if stint == 1 else "HARD",
                "TyreLife": n if stint == 1 else n - pit_in,
                "Stint": stint,
                "TrackStatus": (status or {}).get(n, "1"),
            }
        )
    return rows


@pytest.fixture
def undercut_race():
    # B leads A by 1.5 s. A pits first (lap 10) and its fresh tyres are a
    # second a lap quicker, so by the time B pits (lap 12) A is ahead.
    a = make_car("A", [80] * 9 + [90, 92] + [79] * 9, pit_in=10)
    b = make_car("B", [80] * 9 + [80.5, 80.5, 90.5, 92.5] + [79] * 7, offset=-1.5, pit_in=12)
    return pd.DataFrame(a + b)


def test_pit_stops_and_loss(undercut_race):
    stops = pit_stops(undercut_race).set_index("Driver")
    assert stops.loc["A", "Lap"] == 10
    assert stops.loc["B", "Lap"] == 12
    assert stops.loc["A", "From"] == "MEDIUM" and stops.loc["A", "To"] == "HARD"
    # A's two pit laps (182 s) against B staying out on worn tyres (161 s).
    assert stops.loc["A", "Loss"] == pytest.approx(21.0)
    # B's (183 s) against A, now on fresh tyres (158 s).
    assert stops.loc["B", "Loss"] == pytest.approx(25.0)
    assert not stops["Neutralised"].any()
    assert pit_loss(stops.reset_index()) == pytest.approx(23.0)


def test_undercut_that_works(undercut_race):
    battles = pit_battles(undercut_race, pit_stops(undercut_race))
    row = battles.iloc[0]
    assert (row["FirstStop"], row["Rival"], row["RivalStopLap"]) == ("A", "B", 12)
    assert row["GapBefore"] == pytest.approx(1.5)
    assert row["GapAfter"] == pytest.approx(-2.5)
    assert row["Gained"] == pytest.approx(4.0)
    assert row["Verdict"] == "Undercut worked"


def test_safety_car_stops_are_left_out(undercut_race):
    laps = undercut_race.copy()
    laps.loc[(laps["Driver"] == "A") & (laps["LapNumber"] == 10), "TrackStatus"] = "14"
    stops = pit_stops(laps)
    assert stops.set_index("Driver").loc["A", "Neutralised"]
    assert pit_loss(stops) == pytest.approx(25.0)  # only B's green-flag stop counts
    assert pit_battles(laps, stops).empty  # A's stop was under SC, so no undercut to judge


def test_rejoin_projection():
    tower = pd.DataFrame(
        {
            "Pos": [1, 2, 3, 4, 5],
            "Driver": ["A", "B", "C", "D", "E"],
            "GapSeconds": [0.0, 5.0, 15.0, 30.0, None],
            "Out": [False, False, False, False, True],
        }
    )
    proj = rejoin_projection(tower, loss=20.0).set_index("Driver")
    assert proj.loc["A", "Rejoin"] == 3
    assert proj.loc["A", "CarAhead"] == "C" and proj.loc["A", "GapAhead"] == pytest.approx(5.0)
    assert proj.loc["A", "CarBehind"] == "D" and proj.loc["A", "GapBehind"] == pytest.approx(10.0)
    assert proj.loc["D", "Rejoin"] == 4 and proj.loc["D", "CarBehind"] == ""
    assert "E" not in proj.index  # retired cars aren't projected


def test_rejoin_projection_leaves_out_lapped_cars():
    tower = pd.DataFrame(
        {
            "Pos": [1, 2, 3],
            "Driver": ["A", "B", "L"],
            "GapSeconds": [0.0, 5.0, 95.0],  # L crossed the line a lap and a bit behind
            "LapsDown": [0, 0, 1],
            "Out": [False, False, False],
        }
    )
    proj = rejoin_projection(tower, loss=20.0).set_index("Driver")
    assert "L" not in proj.index
    assert proj.loc["A", "Rejoin"] == 2 and proj.loc["B", "CarBehind"] == ""


def test_pair_gap(undercut_race):
    gap = pair_gap(undercut_race, "A", "B").set_index("LapNumber")["Gap"]
    assert gap[9] == pytest.approx(1.5)
    assert gap[13] == pytest.approx(-2.5)


def test_stop_under_vsc_is_measured_against_cars_also_under_vsc():
    # Everyone laps in 100 s under VSC on laps 10-11; C pits then and loses 12 s, not 50.
    slow = [80] * 9 + [100, 100] + [80] * 4
    c = make_car("C", [80] * 9 + [106, 106] + [80] * 4, pit_in=10, status={10: "6", 11: "6"})
    others = [make_car(d, slow, offset=o, status={10: "6", 11: "6"}) for d, o in (("D", 5), ("E", 10))]
    laps = pd.DataFrame(c + others[0] + others[1])
    stop = pit_stops(laps).iloc[0]
    assert stop["Neutralised"]
    assert stop["Loss"] == pytest.approx(12.0)


def test_pit_loss_now_starts_from_the_circuit_reference_and_switches_to_this_race():
    from pitlens.undercut.analysis import pit_loss_now

    ref = {"normal": 22.0, "vsc": 15.0, "sc": 11.0}
    none = pd.DataFrame(columns=["Loss", "Neutralised"])
    assert pit_loss_now(none, "Green", ref) == (22.0, "circuit reference")
    assert pit_loss_now(none, "Safety car", ref) == (11.0, "circuit reference under safety car")

    three = pd.DataFrame({"Loss": [20.0, 21.0, 24.0], "Neutralised": [False] * 3})
    assert pit_loss_now(three, "Green", ref) == (21.0, "median of 3 green-flag stops")
    value, source = pit_loss_now(three, "VSC", ref)
    assert value == pytest.approx(21.0 * 15 / 22, abs=0.05) and "scaled" in source

    assert pit_loss_now(none, "Green", None) == (None, "no estimate yet")


def test_pit_stops_carry_stationary_time_and_places(undercut_race):
    laps = undercut_race.copy()
    # Positions: B ahead until A's undercut works.
    laps["Position"] = [1.0 if (d == "B") == (n < 11) else 2.0 for d, n in zip(laps["Driver"], laps["LapNumber"])]
    stationary = pd.DataFrame({"Driver": ["A"], "Lap": [10], "Stationary": [2.4]})
    stops = pit_stops(laps, stationary).set_index("Driver")
    assert stops.loc["A", "Stationary"] == pytest.approx(2.4)
    assert pd.isna(stops.loc["B", "Stationary"])
    assert (stops.loc["A", "PosBefore"], stops.loc["A", "PosAfter"]) == (2, 1)
    assert (stops.loc["B", "PosBefore"], stops.loc["B", "PosAfter"]) == (2, 2)


def test_drive_through_on_the_same_tyres_is_not_a_stop(undercut_race):
    laps = undercut_race.copy()
    b = laps["Driver"] == "B"
    laps.loc[b, "Stint"] = 1  # B goes through the pit lane but keeps its tyres
    stops = pit_stops(laps)
    assert stops["Driver"].tolist() == ["A"]


def test_tyre_change_while_the_race_is_stopped_is_not_a_stop(undercut_race):
    laps = undercut_race.copy()
    b_in = laps["PitInTime"].notna() & (laps["Driver"] == "B")
    laps["TrackStatus"] = laps["TrackStatus"].astype(str)
    laps.loc[b_in, "TrackStatus"] = "15"  # red flag on B's in-lap: into the pit lane because the race stopped
    assert pit_stops(laps)["Driver"].tolist() == ["A"]


def test_implausibly_short_pit_lane_times():
    from pitlens.undercut.analysis import plausible_lane_times

    stops = pd.DataFrame({"LaneTime": [20.6, 20.9, 21.3, 15.1, 23.6, 2154.1]})
    assert plausible_lane_times(stops).tolist() == [True, True, True, False, True, False]


def test_rejoin_projection_with_no_timed_cars_is_an_empty_table():
    tower = pd.DataFrame({"Pos": [1], "Driver": ["A"], "GapSeconds": [None], "LapsDown": [0], "Out": [False]})
    proj = rejoin_projection(tower, loss=20.0)
    assert proj.empty and "Driver" in proj


def test_long_stationary_times_are_not_ordinary_stops():
    from pitlens.undercut.analysis import ordinary_stationary_times

    stops = pd.DataFrame({"Stationary": [2.3, 2.5, 2.8, 10.4, None, 16.9]})
    assert ordinary_stationary_times(stops).tolist() == [True, True, True, False, True, False]


def test_race_without_any_pit_records(undercut_race):
    laps = undercut_race.assign(PitInTime=pd.NaT, PitOutTime=pd.NaT)
    assert pit_stops(laps).empty


def test_stop_without_a_pit_lane_time(undercut_race):
    # Worked out from tyre stints alone: in and out times coincide, so the pit lane time is unknown.
    laps = undercut_race.copy()
    a_out = (laps["Driver"] == "A") & (laps["LapNumber"] == 11)
    a_in = (laps["Driver"] == "A") & (laps["LapNumber"] == 10)
    laps.loc[a_out, "PitOutTime"] = laps.loc[a_in, "PitInTime"].values
    stop = pit_stops(laps).set_index("Driver").loc["A"]
    assert pd.isna(stop["LaneTime"]) and stop["Loss"] == pytest.approx(21.0)
