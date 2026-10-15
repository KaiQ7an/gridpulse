import pandas as pd
import pytest

from pitlens.stints.pace import MIN_LAPS_FOR_FIT, add_fuel_corrected_time, stint_degradation


def make_stint(driver="AAA", stint=1, start_lap=2, n=10, base=80.0, deg=0.1, compound="MEDIUM"):
    tyre_life = list(range(1, n + 1))
    return pd.DataFrame(
        {
            "Driver": driver,
            "Team": "Team",
            "LapNumber": list(range(start_lap, start_lap + n)),
            "Stint": stint,
            "Compound": compound,
            "TyreLife": tyre_life,
            "LapTime": [base + deg * t for t in tyre_life],
        }
    )


def test_fuel_correction_is_zero_on_last_lap():
    laps = make_stint(start_lap=1, n=5)
    out = add_fuel_corrected_time(laps, total_laps=5, fuel_effect=0.06)
    last = out[out["LapNumber"] == 5].iloc[0]
    first = out[out["LapNumber"] == 1].iloc[0]
    assert last["LapTimeFuelCorr"] == pytest.approx(last["LapTime"])
    assert first["LapTime"] - first["LapTimeFuelCorr"] == pytest.approx(4 * 0.06)


def test_degradation_slope_recovers_known_rate():
    laps = pd.concat([make_stint(stint=1, deg=0.05), make_stint(stint=2, start_lap=20, deg=0.12, compound="HARD")])
    deg = stint_degradation(laps, time_col="LapTime").set_index("Stint")
    assert deg.loc[1, "DegPerLap"] == pytest.approx(0.05, abs=1e-3)
    assert deg.loc[2, "DegPerLap"] == pytest.approx(0.12, abs=1e-3)
    assert deg.loc[2, "Compound"] == "HARD"


def test_short_stints_are_skipped():
    laps = make_stint(n=MIN_LAPS_FOR_FIT - 1)
    assert stint_degradation(laps, time_col="LapTime").empty
