"""Compare two drivers' laps along the track, metre by metre.

Inputs are FastF1 lap telemetry frames (Distance in metres, Time since the
start of the lap, Speed, Throttle, Brake, nGear, X, Y). Both laps are put on
one distance grid so their times, speeds and inputs can be compared at the
same point on track.
"""

import numpy as np
import pandas as pd


def _seconds(time) -> np.ndarray:
    if pd.api.types.is_timedelta64_dtype(time):
        return time.dt.total_seconds().to_numpy()
    return np.asarray(time, dtype=float)


def project_onto(ref: pd.DataFrame, other: pd.DataFrame, window: float = 0.08) -> np.ndarray:
    """Where along `ref`'s lap each `other` sample is, found by position on track.

    Each car's Distance is integrated from its own speed trace, so it drifts by
    tens of metres over a lap. At a slow corner that's half a second of fake
    gap. Matching each of `other`'s X/Y points to the nearest point of `ref`'s
    path (searching near where it should be, so hairpins that pass close to
    another part of the track can't confuse it) gives both laps one distance
    scale.
    """
    ref_d = ref["Distance"].to_numpy(dtype=float)
    path_d = np.arange(0.0, ref_d.max(), 1.0)  # densify ref's path to 1 m
    path_x = np.interp(path_d, ref_d, ref["X"].astype(float))
    path_y = np.interp(path_d, ref_d, ref["Y"].astype(float))

    own_d = other["Distance"].to_numpy(dtype=float)
    ox, oy = other["X"].to_numpy(dtype=float), other["Y"].to_numpy(dtype=float)
    progress = own_d / own_d.max()
    half = int(window * len(path_d))
    nearest_d = np.empty(len(ox))
    for i, (x, y, f) in enumerate(zip(ox, oy, progress)):
        centre = int(f * (len(path_d) - 1))
        lo, hi = max(0, centre - half), min(len(path_d), centre + half + 1)
        nearest = np.argmin((path_x[lo:hi] - x) ** 2 + (path_y[lo:hi] - y) ** 2)
        nearest_d[i] = path_d[lo + nearest]

    # GPS points are only good to a few metres, so taken one by one they'd make
    # the gap trace jitter. Distance drift builds up slowly, so keep the car's
    # own (smooth) distance and only correct it by the smoothed difference.
    correction = pd.Series(nearest_d - own_d).rolling(31, center=True, min_periods=1).median()
    correction = correction.rolling(15, center=True, min_periods=1).mean().to_numpy()
    return np.maximum.accumulate(own_d + correction)  # a car never goes backwards along the lap


def align(ref: pd.DataFrame, other: pd.DataFrame, step: float = 5.0) -> pd.DataFrame:
    """Both laps on a common distance grid, with the time delta between them.

    With X/Y positions, `other` is placed on `ref`'s distance scale by position
    on track (see `project_onto`); without them its distance is scaled to
    `ref`'s lap length. Delta > 0 means `other` is behind `ref` at that point.
    """
    ref_d = ref["Distance"].to_numpy(dtype=float)
    if {"X", "Y"} <= set(ref.columns) and {"X", "Y"} <= set(other.columns):
        other_d = project_onto(ref, other)
    else:
        other_d = other["Distance"].to_numpy(dtype=float) * (ref_d.max() / other["Distance"].max())
    grid = np.arange(0.0, ref_d.max(), step)

    out = pd.DataFrame({"Distance": grid})
    out["RefTime"] = np.interp(grid, ref_d, _seconds(ref["Time"]))
    out["OtherTime"] = np.interp(grid, other_d, _seconds(other["Time"]))
    out["Delta"] = out["OtherTime"] - out["RefTime"]
    for col in ("Speed", "Throttle", "Brake", "nGear"):
        if col in ref and col in other:
            out[f"Ref{col}"] = np.interp(grid, ref_d, ref[col].astype(float))
            out[f"Other{col}"] = np.interp(grid, other_d, other[col].astype(float))
    return out


def minisectors(aligned: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    """Split the lap into `n` equal-length sectors and time each driver through them."""
    edges = np.linspace(0, aligned["Distance"].max(), n + 1)
    ref_t = np.interp(edges, aligned["Distance"], aligned["RefTime"])
    other_t = np.interp(edges, aligned["Distance"], aligned["OtherTime"])
    out = pd.DataFrame(
        {
            "Sector": np.arange(1, n + 1),
            "Start": edges[:-1],
            "End": edges[1:],
            "RefTime": np.diff(ref_t),
            "OtherTime": np.diff(other_t),
        }
    )
    out["Gain"] = out["OtherTime"] - out["RefTime"]  # > 0: ref was quicker here
    out["Faster"] = np.where(out["Gain"] >= 0, "ref", "other")
    return out


def corner_speeds(ref: pd.DataFrame, other: pd.DataFrame, corners: pd.DataFrame, window: float = 60.0) -> pd.DataFrame:
    """Minimum speed of each driver around every corner, plus time gained through it.

    `corners` is FastF1's circuit info (Number, Letter, Distance). The window
    is +/- `window` metres around the corner's apex marker.
    """
    aligned = align(ref, other, step=2.0)
    rows = []
    for _, c in corners.iterrows():
        lo, hi = c["Distance"] - window, c["Distance"] + window
        part = aligned[(aligned["Distance"] >= lo) & (aligned["Distance"] <= hi)]
        if part.empty:
            continue
        rows.append(
            {
                "Corner": f"{int(c['Number'])}{c.get('Letter') or ''}",
                "Distance": round(float(c["Distance"])),
                "RefMinSpeed": round(float(part["RefSpeed"].min())),
                "OtherMinSpeed": round(float(part["OtherSpeed"].min())),
                # Change in the gap across the corner window: > 0, ref gained time.
                "Gain": round(float(part["Delta"].iloc[-1] - part["Delta"].iloc[0]), 3),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["SpeedDiff"] = out["RefMinSpeed"] - out["OtherMinSpeed"]
    return out


def rotate(x, y, degrees: float) -> tuple[np.ndarray, np.ndarray]:
    """Rotate track coordinates so the map matches the official orientation."""
    a = np.radians(degrees)
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    return x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)
