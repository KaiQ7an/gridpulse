# Telemetry projection

`gridpulse/onboard/compare.py::project_onto` puts two laps on one distance scale. It densifies
the reference path to one metre and searches near each sample's normalized lap progress. The
default search radius is 8% of the reference path; an unrestricted nearest-point search could
jump to a different section at a hairpin or crossing.

The search uses NumPy sliding-window views with repeated endpoint padding. Repeating the endpoints
keeps the original clipped search and its earliest-point tie break. Each batch copies at most
131,072 candidates per coordinate, or one complete window when wider. The two floating-point
distance buffers therefore use about 2 MiB at the normal batch limit. The padded reference and
output arrays are additional storage; no samples-by-entire-track matrix is materialized.

The 31-sample median, 15-sample mean and final monotonic accumulation are unchanged. The work
remains O(samples × local window width); vectorization reduces Python overhead rather than
changing the algorithm's complexity or using a coarser search.

## Correctness

`tests/test_compare.py` compares the vectorized implementation exactly with a scalar oracle for
lap boundaries, zero-width and full-path searches, a sample before distance zero, crossing
trajectories, tied positions and different batch sizes. The existing drift and GPS-noise checks
also remain in place.

On the cached real laps below, both comparison directions produced exactly the same projected
distances, aligned time gaps, telemetry channels and mini-sector results as the scalar search.

## Local benchmark, 18 October 2026

| Cached qualifying laps | Reference / other samples | Scalar | Vectorized | Speedup |
| --- | ---: | ---: | ---: | ---: |
| 2026 Singapore, VER L11 / LEC L24 | 680 / 690 | 2.20 ms | 1.27 ms | 1.73× |
| 2025 Hungary, NOR L8 / PIA L8 | 573 / 556 | 1.74 ms | 0.94 ms | 1.85× |

Measured on macOS arm64 with Python 3.14.8, NumPy 2.5.4 and pandas 2.3.3. Each figure is the
median of seven repeats of 20 complete `project_onto` calls, including interpolation and
smoothing. Session loading, network access and chart rendering are excluded. These are local
kernel timings, not a claim about end-to-end page-load speed.

Open these sessions in Onboard first to populate FastF1's local cache, then run:

```bash
.venv/bin/python tools/benchmark_projection.py --year 2026 --round 17 --drivers VER LEC
.venv/bin/python tools/benchmark_projection.py --year 2025 --round 14 --drivers NOR PIA
```

The benchmark enables FastF1's offline mode and asserts exact array equality before timing.
It retains the previous scalar search as the baseline and prints environment, lap and timing
metadata as JSON. Missing cached telemetry is an error; the benchmark does not download a session.
