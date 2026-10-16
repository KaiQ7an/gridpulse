import pandas as pd

from pitlens.sources.openf1 import track_status_by_lap


def test_deleted_laps_use_time_and_completion_and_respect_reinstatement():
    from pitlens.sources.openf1 import deleted_lap_mask

    laps = pd.DataFrame({"driver_number": [11, 11, 1, 1, 1], "lap_number": [12, 16, 14, 17, 19],
                         "lap_duration": [128.539, 73.334, 95.081, 94.718, 94.718],
                         "date_start": ["2023-10-20T21:10:00Z", "2023-10-20T21:20:00Z",
                                        "2023-10-20T21:50:03Z", "2023-10-20T21:58:46Z", "2023-10-20T22:05:00Z"]})
    messages = pd.DataFrame([
        {"date": "2023-10-20T21:13:00Z", "message": "CAR 11 (PER) TIME 2:08.539 DELETED - LAP 16"},
        {"date": "2023-10-20T22:00:22Z", "message": "CAR 1 (VER) TIME 1:34.718 DELETED - LAP 18"},
    ])
    assert deleted_lap_mask(laps, messages).tolist() == [True, False, False, True, False]
    restored = pd.DataFrame([{"date": "2023-10-20T22:01:00Z",
                              "message": "CAR 1 (VER) TIME 1:34.718 WILL BE REINSTATED"}])
    assert deleted_lap_mask(laps, pd.concat([restored, messages])).tolist() == [True, False, False, False, False]


def test_onboard_never_selects_a_deleted_fastest_lap(monkeypatch):
    from pitlens.onboard.data import OpenF1Weekend
    from pitlens.sources import openf1

    weekend = OpenF1Weekend.__new__(OpenF1Weekend)
    weekend.session = {"session_key": 1}
    weekend.stints = pd.DataFrame()
    weekend.laps = pd.DataFrame({"name_acronym": ["VER", "VER"], "driver_number": [1, 1],
                                "team_name": ["Red Bull"] * 2, "lap_duration": [94.718, 95.008],
                                "lap_number": [17, 11], "Deleted": [True, False],
                                "duration_sector_1": [25, 25], "duration_sector_2": [38, 38],
                                "duration_sector_3": [31.718, 32.008], "date_start": ["2023-10-20T21:00Z"] * 2})
    monkeypatch.setattr(openf1, "lap_telemetry", lambda *args: pd.DataFrame())
    assert weekend.fastest_lap("VER").lap_time.total_seconds() == 95.008


def rc(rows):
    return pd.DataFrame(
        [dict(date=f"2026-01-01T12:{i:02d}:00", lap_number=lap, category=cat, flag=flag, scope=scope, sector=sector,
              message=msg) for i, (lap, cat, flag, scope, sector, msg) in enumerate(rows)]
    )


def test_safety_car_and_vsc_periods():
    status = track_status_by_lap(rc([
        (3, "SafetyCar", None, None, None, "SAFETY CAR DEPLOYED"),
        (5, "SafetyCar", None, None, None, "SAFETY CAR IN THIS LAP"),
        (8, "SafetyCar", None, None, None, "VSC DEPLOYED"),
        (9, "SafetyCar", None, None, None, "VSC ENDING"),
    ]), total_laps=10)
    assert status[2] == "1"
    assert "4" in status[3] and status[4] == "4" and "4" in status[5]
    assert status[6] == "1"
    assert "6" in status[8] and "7" in status[9]
    assert status[10] == "1"


def test_red_flag_overrides_safety_car_and_ends_at_restart():
    # Monaco 2026: SC out, red flag before it came in, standing restart two laps later.
    status = track_status_by_lap(rc([
        (66, "SafetyCar", None, None, None, "SAFETY CAR DEPLOYED"),
        (68, "Other", None, None, None, "RED FLAG - RACE SUSPENDED"),
        (73, "Other", None, None, None, "FIA STEWARDS: INCIDENT INVOLVING CAR 6 (HAD) - RED FLAG INFRINGEMENT"),
        (70, "Other", None, None, None, "STANDING START"),
    ]), total_laps=78)
    assert "4" in status[66] and status[67] == "4"
    assert "5" in status[68] and status[69] == "5"
    assert status[71] == "1" and status[78] == "1"


def test_sector_yellows_until_cleared():
    status = track_status_by_lap(rc([
        (4, "Flag", "YELLOW", "Sector", 5, "YELLOW IN TRACK SECTOR 5"),
        (5, "Flag", "CLEAR", "Sector", 5, "CLEAR IN TRACK SECTOR 5"),
    ]), total_laps=6)
    assert "2" in status[4]
    assert status[6] == "1"


def test_stints_on_the_same_tyres_are_merged():
    from pitlens.sources.openf1 import merge_continuing_stints

    stints = pd.DataFrame(
        [
            dict(driver_number=77, stint_number=1, lap_start=1, lap_end=26, compound="MEDIUM", tyre_age_at_start=0),
            dict(driver_number=77, stint_number=2, lap_start=27, lap_end=36, compound="SOFT", tyre_age_at_start=0),
            # sent through the pit lane behind the safety car: same softs, age carries on
            dict(driver_number=77, stint_number=3, lap_start=37, lap_end=49, compound="SOFT", tyre_age_at_start=10),
            dict(driver_number=63, stint_number=1, lap_start=1, lap_end=36, compound="SOFT", tyre_age_at_start=0),
            dict(driver_number=63, stint_number=2, lap_start=37, lap_end=51, compound="SOFT", tyre_age_at_start=0),
        ]
    )
    merged = merge_continuing_stints(stints)
    bot = merged[merged["driver_number"] == 77]
    assert bot["stint_number"].tolist() == [1, 2]
    assert bot["lap_end"].tolist() == [26, 49]
    assert len(merged[merged["driver_number"] == 63]) == 2  # fresh softs: a real stop


def test_stationary_times():
    from pitlens.sources.openf1 import stationary_from

    pits = pd.DataFrame({"driver_number": [44, 1, 16], "lap_number": [11, 12, 13], "stop_duration": [2.2, None, 3.1]})
    out = stationary_from(pits, {44: "HAM", 1: "VER", 16: "LEC"})
    assert out.to_dict("records") == [{"Driver": "HAM", "Lap": 11, "Stationary": 2.2},
                                      {"Driver": "LEC", "Lap": 13, "Stationary": 3.1}]


def test_stop_lap_is_the_in_lap_where_the_pit_lane_crosses_the_line():
    from pitlens.sources.openf1 import in_laps

    # Baku: boxes before the line, stop on lap 20, new tyres from lap 21.
    # Montreal: the stop falls on lap 2, which the new stint starts.
    pits = pd.DataFrame({"driver_number": [55, 1, 81], "lap_number": [20, 2, 1]})
    stints = pd.DataFrame({"driver_number": [55, 55, 1, 1, 81, 81], "lap_start": [1, 21, 1, 2, 1, 12]})
    assert in_laps(pits, stints).tolist() == [20, 1, 0]  # 0: started from the pit lane


def test_a_stop_at_the_end_of_lap_1_is_not_a_pit_lane_start():
    from pitlens.sources.openf1 import first_lap_stops, in_laps

    # Monaco 2025: Tsunoda pits at the end of lap 1 and leaves the pits on lap 2, but OpenF1 ends his
    # soft stint at lap 0 and starts the hards on lap 1. Gasly really does start from the pit lane.
    stints = pd.DataFrame({"driver_number": [22, 22, 10, 10], "stint_number": [1, 2, 1, 2],
                           "lap_start": [1, 1, 1, 1], "lap_end": [0, 72, 0, 70],
                           "compound": ["SOFT", "HARD", "SOFT", "HARD"]})
    out_laps = {(22, 2), (10, 1)}
    fixed = first_lap_stops(stints, out_laps)
    assert fixed[fixed["driver_number"] == 22][["lap_start", "lap_end"]].values.tolist() == [[1, 1], [2, 72]]
    assert fixed[fixed["driver_number"] == 10][["lap_start", "lap_end"]].values.tolist() == [[1, 0], [1, 70]]
    pits = pd.DataFrame({"driver_number": [22, 10], "lap_number": [1, 1]})
    assert in_laps(pits, fixed, out_laps).tolist() == [1, 0]


def test_a_stop_at_the_end_of_lap_1_without_pit_records():
    from pitlens.sources.openf1 import first_lap_stops, pits_from_stints

    # Monaco 2023, before OpenF1 had pit records: Perez's first stint reads lap 1 to 1 and the next
    # starts on lap 1 as well; he left the pits on lap 2.
    stints = pd.DataFrame({"driver_number": [11, 11], "stint_number": [1, 2], "lap_start": [1, 1],
                           "lap_end": [1, 34], "compound": ["MEDIUM", "HARD"]})
    fixed = first_lap_stops(stints, {(11, 2)})
    assert fixed[["lap_start", "lap_end"]].values.tolist() == [[1, 1], [2, 34]]
    laps = pd.DataFrame({"driver_number": [11, 11], "lap_number": [1, 2],
                         "date_start": ["2023-05-28T13:03:00", "2023-05-28T13:05:00"]})
    assert pits_from_stints(fixed, laps)["lap_number"].tolist() == [1]


def test_stops_from_stints_when_there_are_no_pit_records():
    from pitlens.sources.openf1 import pits_from_stints

    stints = pd.DataFrame({"driver_number": [1, 1, 44], "stint_number": [1, 2, 1], "lap_start": [1, 15, 1]})
    laps = pd.DataFrame({"driver_number": [1, 1], "lap_number": [14, 15],
                         "date_start": ["2023-03-05T15:40:00+00:00", "2023-03-05T15:41:40+00:00"]})
    pits = pits_from_stints(stints, laps)
    assert pits[["driver_number", "lap_number", "date"]].values.tolist() == [[1, 14, "2023-03-05T15:41:40+00:00"]]
    assert pits["lane_duration"].isna().all()


def test_starting_grid_comes_from_the_matching_qualifying(monkeypatch):
    from pitlens.sources import openf1

    grids = [{"position": 1, "driver_number": 63, "session_key": 10}, {"position": 2, "driver_number": 1, "session_key": 10},
             {"position": 1, "driver_number": 1, "session_key": 20}]
    sessions = [{"session_key": 10, "session_name": "Qualifying"}, {"session_key": 20, "session_name": "Sprint Qualifying"}]
    monkeypatch.setattr(openf1, "get", lambda endpoint, **p: grids if endpoint == "starting_grid" else sessions)
    assert openf1.starting_grid({"meeting_key": 7}, "Race") == {63: 1, 1: 2}
    assert openf1.starting_grid({"meeting_key": 7}, "Sprint") == {1: 1}
