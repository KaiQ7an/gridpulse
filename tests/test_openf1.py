import pandas as pd

from pitlens.sources.openf1 import track_status_by_lap


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
