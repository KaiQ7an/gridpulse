import numpy as np
import pandas as pd
import pytest

from pitlens.onboard.compare import align, corner_speeds, minisectors, project_onto, rotate


def make_lap(speeds_kmh, length=1000.0, points=201):
    """A lap of `length` metres where speed changes piecewise along the lap."""
    distance = np.linspace(0, length, points)
    speed = np.interp(distance, np.linspace(0, length, len(speeds_kmh)), speeds_kmh)
    seconds = np.concatenate([[0], np.cumsum(np.diff(distance) / (speed[1:] / 3.6))])
    return pd.DataFrame(
        {
            "Distance": distance,
            "Time": pd.to_timedelta(seconds, unit="s"),
            "Speed": speed,
            "Throttle": 100.0,
            "Brake": False,
            "nGear": 7,
        }
    )


def test_identical_laps_have_zero_delta():
    lap = make_lap([200, 200])
    aligned = align(lap, lap)
    assert np.allclose(aligned["Delta"], 0)


def test_delta_grows_where_the_other_car_is_slower():
    ref = make_lap([200, 200, 200])
    other = make_lap([200, 100, 200])  # slower through the middle
    aligned = align(ref, other)
    first_quarter = aligned[aligned["Distance"] < 100]["Delta"]
    assert first_quarter.abs().max() < 0.2
    assert aligned["Delta"].iloc[-1] > 3  # loses several seconds overall


def test_other_distance_is_scaled_to_ref_lap_length():
    ref = make_lap([200, 200], length=1000)
    other = make_lap([200, 200], length=1010)  # same speed, GPS says 1% longer
    other["Time"] = ref["Time"]  # same lap time
    assert align(ref, other)["Delta"].abs().max() == pytest.approx(0, abs=1e-9)


def test_minisectors_sum_to_lap_delta():
    ref = make_lap([200, 150, 220, 180])
    other = make_lap([190, 160, 210, 185])
    aligned = align(ref, other, step=1.0)
    sectors = minisectors(aligned, n=10)
    assert len(sectors) == 10
    assert sectors["Gain"].sum() == pytest.approx(aligned["Delta"].iloc[-1], abs=0.01)
    assert set(sectors["Faster"]) <= {"ref", "other"}


def test_corner_speeds_reports_min_speed_and_gain():
    ref = make_lap([250, 80, 250])
    other = make_lap([250, 70, 250])
    corners = pd.DataFrame({"Number": [1], "Letter": [""], "Distance": [500.0]})
    table = corner_speeds(ref, other, corners, window=100)
    row = table.iloc[0]
    assert row["Corner"] == "1"
    assert row["RefMinSpeed"] > row["OtherMinSpeed"]
    assert row["SpeedDiff"] > 0
    assert row["Gain"] > 0  # ref gained time through the corner


def test_rotate_quarter_turn():
    x, y = rotate([1.0], [0.0], 90)
    assert x[0] == pytest.approx(0, abs=1e-12)
    assert y[0] == pytest.approx(1)


def with_circle_xy(lap, radius=None):
    """Give a lap X/Y on a circle so that position follows its true distance."""
    length = lap["Distance"].max()
    radius = radius or length / (2 * np.pi)
    angle = lap["Distance"] / radius
    return lap.assign(X=radius * np.cos(angle), Y=radius * np.sin(angle))


def test_position_alignment_ignores_distance_drift():
    ref = with_circle_xy(make_lap([250, 90, 250, 120, 250]))
    other = ref.copy()
    # Same lap, but this car's integrated distance runs 3% long mid-lap
    # (and is back to the true length at the line).
    true_d = other["Distance"].to_numpy()
    other["Distance"] = true_d + 0.03 * true_d * (1 - true_d / true_d.max())
    projected = project_onto(ref, other)
    assert np.abs(projected - true_d).max() < 3  # within a few metres
    assert align(ref, other)["Delta"].abs().max() < 0.05
    # Distance-only alignment would show a fake gap mid-lap.
    plain = align(ref.drop(columns=["X", "Y"]), other.drop(columns=["X", "Y"]))
    assert plain["Delta"].abs().max() > 0.1


def test_position_alignment_is_robust_to_gps_noise():
    ref = with_circle_xy(make_lap([250, 90, 250, 120, 250], points=601))
    other = ref.copy()
    rng = np.random.default_rng(0)
    other["X"] += rng.normal(0, 3, len(other))  # ~3 m GPS noise
    other["Y"] += rng.normal(0, 3, len(other))
    assert align(ref, other)["Delta"].abs().max() < 0.05
