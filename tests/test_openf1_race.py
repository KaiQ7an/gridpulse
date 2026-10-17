"""race_parts end to end on a tiny fake race: two cars, five laps, one stop each."""

import pandas as pd
import pytest

from gridpulse.sources import openf1

T0 = pd.Timestamp("2026-06-01T13:00:00Z")


def at(seconds: float) -> str:
    return (T0 + pd.to_timedelta(seconds, unit="s")).isoformat()


def fake_api(endpoint: str, **params):
    laps = []
    for n, offset in ((1, 0.0), (44, 1.0)):
        for lap in range(1, 6):
            laps.append({"driver_number": n, "lap_number": lap, "date_start": at(60 + offset + 90 * (lap - 1)),
                         "lap_duration": 90.0, "duration_sector_1": 30.0, "duration_sector_2": 30.0,
                         "duration_sector_3": 30.0, "is_pit_out_lap": False})
    data = {
        "sessions": [{"session_key": 1, "meeting_key": 7, "date_start": T0.isoformat(), "location": "Testville",
                      "circuit_key": None}],
        "meetings": [{"meeting_name": "Test Grand Prix"}],
        "drivers": [{"driver_number": 1, "name_acronym": "VER", "team_name": "Red Bull Racing", "team_colour": "3671C6",
                     "first_name": "Max", "last_name": "VERSTAPPEN"},
                    {"driver_number": 44, "name_acronym": "HAM", "team_name": "Ferrari", "team_colour": "E8002D",
                     "first_name": "Lewis", "last_name": "HAMILTON"}],
        "laps": laps,
        # VER: boxes before the line, stop recorded on lap 2, new tyres from lap 3.
        # HAM: pit lane crosses the line, stop recorded on lap 3, which the new stint starts.
        "stints": [{"driver_number": 1, "stint_number": 1, "lap_start": 1, "lap_end": 2, "compound": "MEDIUM", "tyre_age_at_start": 0},
                   {"driver_number": 1, "stint_number": 2, "lap_start": 3, "lap_end": 5, "compound": "HARD", "tyre_age_at_start": 0},
                   {"driver_number": 44, "stint_number": 1, "lap_start": 1, "lap_end": 2, "compound": "MEDIUM", "tyre_age_at_start": 0},
                   {"driver_number": 44, "stint_number": 2, "lap_start": 3, "lap_end": 5, "compound": "HARD", "tyre_age_at_start": 0}],
        "pit": [{"driver_number": 1, "lap_number": 2, "date": at(200), "lane_duration": 21.0, "pit_duration": 21.0, "stop_duration": 2.4},
                {"driver_number": 44, "lap_number": 3, "date": at(240), "lane_duration": 22.0, "pit_duration": 22.0, "stop_duration": None}],
        "session_result": [{"driver_number": 1, "position": 1, "gap_to_leader": 0, "number_of_laps": 5},
                           {"driver_number": 44, "position": 2, "gap_to_leader": 1.0, "number_of_laps": 5}],
    }
    return data.get(endpoint, [])


@pytest.fixture
def parts(monkeypatch):
    monkeypatch.setattr(openf1, "get", lambda endpoint, cache=True, refresh=False, **params: fake_api(endpoint, **params))
    return openf1.race_parts(2026, T0)


def test_laps_have_fastf1_columns(parts):
    laps = parts["laps"]
    assert set(laps["Driver"]) == {"VER", "HAM"}
    assert laps.groupby("Driver")["LapNumber"].max().to_dict() == {"HAM": 5, "VER": 5}
    ver = laps[laps["Driver"] == "VER"].set_index("LapNumber")
    assert ver.loc[1, "Time"] == pd.to_timedelta(150, unit="s")  # the next lap's start
    assert ver.loc[3, "Compound"] == "HARD" and ver.loc[3, "TyreLife"] == 1


def test_stops_land_on_their_in_lap(parts):
    laps = parts["laps"]
    pit_in = laps[laps["PitInTime"].notna()].set_index("Driver")["LapNumber"].to_dict()
    pit_out = laps[laps["PitOutTime"].notna()].set_index("Driver")["LapNumber"].to_dict()
    assert pit_in == {"VER": 2, "HAM": 2}
    assert pit_out == {"VER": 3, "HAM": 3}
    assert parts["stationary"].to_dict("records") == [{"Driver": "VER", "Lap": 2, "Stationary": 2.4}]


def test_results(parts):
    res = parts["results"].set_index("Abbreviation")
    assert res.loc["VER", "Position"] == 1 and res.loc["HAM", "GapToLeader"] == 1.0
    assert res.loc["HAM", "Laps"] == 5 and res.loc["HAM", "Status"] == "Finished"
    assert res.loc["HAM", "LastName"] == "Hamilton"
    assert parts["total_laps"] == 5
