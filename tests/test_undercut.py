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
