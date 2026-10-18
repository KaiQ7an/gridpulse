import numpy as np
import pandas as pd
import pytest

from gridpulse.onboard import compare
from gridpulse.onboard.compare import (
    align,
    corner_speeds,
    minisectors,
    project_onto,
    rotate,
    sector_distances,
    summarise,
)


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


def scalar_projection(ref, other, window):
    """Point-by-point oracle for the original local nearest-point search."""
    path = np.arange(0.0, ref["Distance"].max(), 1.0)
    x = np.interp(path, ref["Distance"], ref["X"])
    y = np.interp(path, ref["Distance"], ref["Y"])
    own = other["Distance"].to_numpy()
    half = int(window * len(path))
    projected = []
    for d, px, py in other[["Distance", "X", "Y"]].itertuples(index=False, name=None):
        centre = int(d / own.max() * (len(path) - 1))
        lo, hi = max(0, centre - half), min(len(path), centre + half + 1)
        projected.append(path[lo + np.argmin((x[lo:hi] - px) ** 2 + (y[lo:hi] - py) ** 2)])
    correction = pd.Series(projected - own).rolling(31, center=True, min_periods=1).median()
    correction = correction.rolling(15, center=True, min_periods=1).mean().to_numpy()
    return np.maximum.accumulate(own + correction)


@pytest.mark.parametrize("length,points,window,start", [
    (1000, 7, 0.0, 0),       # one candidate, including both ends of the lap
    (1000, 601, 0.08, 0),    # several batches and a partial last batch
    (1000, 901, 0.5, 0),     # overlapping windows near the start and finish
    (1000, 42, 3.0, 0),      # wider than the entire reference path
    (1000, 42, 3.0, -2),     # full-path window with negative opening progress
    (1, 10, 0.08, 0),        # a one-point densified reference
    (1000, 801, 0.08, -2),   # an interpolated sample just before the start line
])
def test_projection_matches_scalar_search_at_window_boundaries(length, points, window, start):
    ref = with_circle_xy(make_lap([250, 90, 250, 120, 250], length=length, points=points))
    other = ref.copy()
    distance = other["Distance"].to_numpy()
    other["Distance"] += 0.03 * distance * (1 - distance / length)
    other.loc[0, "Distance"] = start
    rng = np.random.default_rng(17)
    other["X"] += rng.normal(0, 2, len(other))
    other["Y"] += rng.normal(0, 2, len(other))
    actual = project_onto(ref, other, window)
    np.testing.assert_array_equal(actual, scalar_projection(ref, other, window))
    assert np.all(np.diff(actual) >= 0)


def test_projection_does_not_jump_to_another_section_at_a_track_crossing():
    ref = make_lap([200, 100, 200], points=801)
    phase = ref["Distance"].to_numpy() / ref["Distance"].max() * 2 * np.pi
    ref = ref.assign(X=100 * np.sin(phase), Y=100 * np.sin(2 * phase))
    actual = project_onto(ref, ref)
    np.testing.assert_array_equal(actual, scalar_projection(ref, ref, 0.08))
    assert np.abs(actual - ref["Distance"]).max() < 3


def test_projection_uses_earliest_candidate_when_positions_tie():
    ref = make_lap([200, 200], points=601).assign(X=0.0, Y=0.0)
    np.testing.assert_array_equal(project_onto(ref, ref), scalar_projection(ref, ref, 0.08))


def test_projection_is_independent_of_batch_size(monkeypatch):
    ref = with_circle_xy(make_lap([250, 100, 250], length=6000, points=700))
    other = ref.copy()
    other["X"] += np.sin(other["Distance"]) * 3
    expected = scalar_projection(ref, other, 0.08)
    monkeypatch.setattr(compare, "_PROJECTION_CANDIDATES", 31)  # one search window per batch
    np.testing.assert_array_equal(project_onto(ref, other), expected)


def test_sector_distances_follow_official_split_times():
    lap = make_lap([180, 180], length=900)  # constant 50 m/s
    d = sector_distances(lap, (pd.to_timedelta(6, unit="s"),) * 3)
    assert d == pytest.approx([300, 600], abs=1)


def test_summarise_names_sectors_and_corners():
    corners = pd.DataFrame({"Corner": ["1", "4", "7", "9"], "Gain": [0.10, 0.05, -0.08, 0.0]})
    text = summarise("VER", "LEC", 0.054, [0.023, -0.130, 0.161], corners)
    assert text.startswith("VER was 0.054 s quicker than LEC.")
    assert "VER took sectors 1 and 3; LEC was 0.130 s faster in sector 2." in text
    assert "VER's biggest gains came at T1 and T4" in text
    assert "LEC's biggest gains came at T7" in text
