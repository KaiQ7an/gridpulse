import numpy as np
import pandas as pd
import pytest

from gridpulse.quali.data import eliminated_in, ideal_laps

nan = np.nan


def test_eliminated_in_follows_the_classification():
    # 22 cars (2026): 16 reach Q2, 10 reach Q3. P9 made Q3 without a Q3 time, P16 made Q2 without a
    # Q2 time, and P22 never set a time.
    q1 = [90.0 + i * 0.1 for i in range(21)] + [nan]
    q2 = [89.0 + i * 0.1 for i in range(15)] + [nan] * 7
    q3 = [88.0 + i * 0.1 for i in range(8)] + [nan] * 14
    results = pd.DataFrame({"Position": range(1, 23), "Q1": q1, "Q2": q2, "Q3": q3})
    out = eliminated_in(results).tolist()
    assert out[:10] == [""] * 10
    assert out[10:16] == ["Q2"] * 6
    assert out[16:] == ["Q1"] * 6


def test_ideal_lap_adds_up_the_best_sectors_and_skips_deleted_laps():
    laps = pd.DataFrame({
        "Driver": ["A", "A", "A", "B"],
        "LapTime": [90.0, 90.2, 88.0, 90.5],
        "S1": [30.0, 29.8, 29.0, 30.1],
        "S2": [30.0, 30.2, 29.0, 30.2],
        "S3": [30.0, 30.2, 30.0, 30.2],
        "Deleted": [False, False, True, False],  # A's 88.0 was deleted for track limits
    })
    ideal = ideal_laps(laps).set_index("Driver")
    assert ideal.loc["A", "Best"] == 90.0
    assert ideal.loc["A", "Ideal"] == pytest.approx(29.8 + 30.0 + 30.0)
    assert ideal.loc["A", "LeftOnTable"] == pytest.approx(0.2)


def test_saved_openf1_validity_matches_the_stewards_not_offset_lap_numbers():
    from gridpulse import snapshots

    spain = snapshots.load_quali(2023, 7, "Q")
    assert ideal_laps(spain.laps).set_index("Driver").loc["PER", "Best"] == 73.334
    austin = snapshots.load_quali(2023, 18, "Q")
    ver = austin.laps[austin.laps.Driver == "VER"]
    assert ver.loc[ver.LapTime == 94.718, "Deleted"].all()
    assert ideal_laps(austin.laps).set_index("Driver").loc["VER", "Best"] == 95.008
