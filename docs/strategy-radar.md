# Undercut radar and model ranges

The Strategy view contains two distinct calculations. The pit window compares one driver's
alternative final stops. The radar compares a short response scenario for two cars that are
adjacent in the current timing tower. Neither calculation chooses a team's actual strategy.

## Replay boundary and eligibility

The fit receives only `race.clean_through(lap)`. The tower and out-lap exclusions use timing
known at that lap. No future stop, fastest later lap or final result supplies driver pace.
The existing clean-lap filter excludes pit laps, neutralisations and suspect timing; the fit
also trims large residual outliers.

The radar scans original neighbours before filtering, so excluding a pitting car cannot turn
two non-adjacent cars into a battle. Both cars must be on the lead lap, running dry tyres,
not in/out of the pits, have finite tyre ages and gaps, and have observed driver pace. Their
gap must be at most 3.5 seconds. Any status other than known Green suspends the scenario.
There must be enough laps left for both out-laps to finish.

The zero-observation tyre prior can draw a relative pit window, because a single driver's
baseline cancels between plans. It cannot supply relative pace for two drivers; the radar
therefore waits for observations instead of substituting a field-average baseline.

## Response clock

At the end of replay lap L, let A be the car ahead and B the chaser. B stops at the end of
L+1. A responds d laps later, at the end of L+1+d, with d in {1, 2, 3}. Compare after lap
L+d+2, when both out-laps have completed. Both fit the selected fresh dry compound C.

For n = d+2 forecast laps and current tyre ages a and b:

- A runs its old compound at ages a+1 through a+n−1, then C at age 1.
- B runs its old compound at age b+1, then C at ages 1 through n−1.
- `Gain = sum(A lap times) − sum(B lap times) − ExtraCost`.
- `Margin = Gain − current gap`. Positive means B would be ahead after this response.

Driver pace differences apply across **all n forecast laps**. The shared fuel/track trend
cancels because the clocks span the same race laps. Equal total stop costs, including equal
warm-up effects, cancel too. The optional ExtraCost is an additional cost to B relative to A;
no generic warm-up penalty is subtracted twice.

Example with equal 80 s baselines, Medium wear 0.10 s/lap, Hard offset +0.40 s and wear
0.03 s/lap: from age 20, a one-lap response gives A `M21 + M22 + H1` and B `M21 + H1 + H2`.
The gain is `82.20 − 80.46 = 1.74 s`. From a 1.20 s gap the margin is +0.54 s. Adding an
extra 0.80 s cost changes it to −0.26 s.

This assumes clear air, constant fitted linear wear, equal total pit costs unless adjusted,
and an available fresh set. Traffic, tyre inventory, team decisions, future flags and changing
weather are not simulated.

## What the ranges mean

The existing penalized least-squares point fit is unchanged. Its parameters are driver
baselines, Soft/Hard offsets relative to Medium, three wear slopes and a shared race-lap trend.
Typical offsets/wear/trend act as Gaussian penalty rows. With augmented matrix A, the
unscaled information inverse is `(AᵀA)⁻¹`, computed by SVD rather than forming normal equations.

We scale it by `s²`, where `s = max(0.3 s, 1.4826 × MAD(retained residuals))`:

```
Σ = (AᵀA)⁻¹ s²
SD(parameter contrast) = sqrt(wᵀΣw)
90% model range = estimate ± 1.644854 × SD
```

This retains correlations between shared parameters; adding independent error bars for
each plan would miss the cancellations. The residual scale inflates a **fixed penalized fit**;
we do not refit its prior weights when the scale grows. It is an approximate conditional
Gaussian range after filtering/trimming, not a claim of fully calibrated Bayesian inference.

For the pit window, w is a plan's coefficient vector minus that of the point-estimate best
reference. It expresses uncertainty in relative expected plan cost, without future lap noise.
The selected reference necessarily has zero relative range. Negative bounds on other plans
mean they could beat that reference; they are not a confidence interval on the true optimum.
The separately coloured stopping window still means within one second at the point estimate.

For the radar, w is A's scenario vector minus B's. We additionally include independent future
lap noise from both drivers:

```
SD(radar margin) = sqrt(wᵀΣw + 2n s²)
```

This does not model serially correlated laps or uncertainty in current timing, extra pit cost,
traffic or the linear model itself. The ranges are not measured probabilities of an actual
overtake. If a fitted wear slope is clipped to its physical bounds [0, 0.4], Gaussian ranges
are withheld, rather than pairing a clipped estimate with its unconstrained covariance.

The distinction between parameter uncertainty and future observation uncertainty follows
[Gaussian linear-model inference](https://statproofbook.github.io/P/blrkc-post.html) and
[posterior predictive checks](https://mc-stan.org/docs/2_28/stan-users-guide/sampling-from-the-posterior-predictive-distribution.html).

## Evidence labels and controls

| Label | Meaning |
| --- | --- |
| Learning | Either driver has fewer than five retained clean laps |
| Range unavailable | No covariance is available, or a wear estimate was clipped |
| Prior-led | At least one relevant compound lacks measured offset or wear evidence |
| Model edge | Both drivers/compounds have evidence and the whole range is above zero |
| No edge | Both drivers/compounds have evidence and the whole range is below zero |
| Uncertain | Measured comparison whose range includes zero |

Compound offset evidence requires eight clean laps across the field; wear requires five
clean laps in a stint. These gates describe evidence, not guaranteed prediction accuracy.
The radar defaults to the six strongest point-estimate margins. Focus and All expose other
eligible battles. Hover reveals full names, gap, gain, range and sample counts; clicking a
point selects the chaser in the pit window. Native Streamlit controls retain tyre, reply-delay,
extra-cost and scope choices across view changes.

## Reproducible validation

```bash
.venv/bin/pytest -q tests/test_radar.py tests/test_window_uncertainty.py \
  tests/test_window.py tests/test_strategy_start.py
```

The tests reconcile the clock example above, check driver pace over the full horizon,
preserve adjacency, suspend non-green scenarios, exercise missing/pit/wet/lapped states,
and modify or remove future race laps while requiring identical current results. Application
tests cover controls, view changes and the early-lap learning state.

Seeded Gaussian simulations check the contrast scale against known generated parameters.
This is an algebra/assumption check on synthetic data, **not real-race coverage calibration**.
The existing 625-stop backtest measures the point-estimate pit window's timing; it does
not validate the new radar or the coverage of its ranges.
