"""Check exact projection parity and time cached laps, without network access.

Run from the repository root after opening the session in Onboard:
    .venv/bin/python tools/benchmark_projection.py --year 2026 --round 17 --drivers VER LEC
"""

import argparse
import json
import platform
import sys
from functools import partial
from pathlib import Path
from statistics import median
from timeit import repeat

import fastf1
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gridpulse.onboard.compare import project_onto
from gridpulse.onboard.data import fastest_lap
from gridpulse.session import enable_cache, load_session


def scalar_projection(ref, other, window=0.08):
    """The point-by-point search used before the vectorization, including smoothing."""
    ref_d = ref["Distance"].to_numpy(dtype=float)
    path = np.arange(0.0, ref_d.max(), 1.0)
    x = np.interp(path, ref_d, ref["X"].astype(float))
    y = np.interp(path, ref_d, ref["Y"].astype(float))
    own = other["Distance"].to_numpy(dtype=float)
    ox, oy = other["X"].to_numpy(dtype=float), other["Y"].to_numpy(dtype=float)
    progress = own / own.max()
    half = int(window * len(path))
    projected = np.empty(len(other))
    for i, (px, py, fraction) in enumerate(zip(ox, oy, progress)):
        centre = int(fraction * (len(path) - 1))
        lo, hi = max(0, centre - half), min(len(path), centre + half + 1)
        projected[i] = path[lo + np.argmin((x[lo:hi] - px) ** 2 + (y[lo:hi] - py) ** 2)]
    correction = pd.Series(projected - own).rolling(31, center=True, min_periods=1).median()
    correction = correction.rolling(15, center=True, min_periods=1).mean().to_numpy()
    return np.maximum.accumulate(own + correction)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--session", default="Q")
    parser.add_argument("--drivers", nargs=2, required=True)
    args = parser.parse_args()
    enable_cache()
    fastf1.Cache.offline_mode(True)
    session = load_session(args.year, args.round, args.session, telemetry=True)
    laps = [fastest_lap(session, driver) for driver in args.drivers]
    ref, other = (lap.telemetry for lap in laps)
    expected = scalar_projection(ref, other)
    actual = project_onto(ref, other)
    np.testing.assert_array_equal(actual, expected)
    timings = {
        name: median(repeat(partial(fn, ref, other), repeat=7, number=20)) / 20 * 1000
        for name, fn in (("scalar_ms", scalar_projection), ("vectorized_ms", project_onto))
    }
    print(json.dumps({
        "platform": platform.platform(), "python": platform.python_version(),
        "numpy": np.__version__, "pandas": pd.__version__,
        "session": f"{args.year} {session.event['EventName']} {session.name}",
        "laps": [{"driver": lap.driver, "lap": lap.lap_number, "rows": len(lap.telemetry)} for lap in laps],
        "reference_metres": float(ref["Distance"].max()),
        "method": "median of 7 repeats, 20 full projections each; load excluded",
        "exact_match": True,
        **timings, "speedup": timings["scalar_ms"] / timings["vectorized_ms"],
    }, indent=2))


if __name__ == "__main__":
    main()
