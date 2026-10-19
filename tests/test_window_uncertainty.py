"""Model ranges must propagate shared parameters, not sum marginal standard errors."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from gridpulse.undercut.window import (
    MODEL_Z,
    PRIOR_SD,
    TYPICAL_DEG,
    TYPICAL_OFFSET,
    fit_tyre_model,
    lap_coefficients,
    pit_window,
)


def observations(seed=0, laps=25):
    rng = np.random.default_rng(seed)
    rows = []
    for j, driver in enumerate(['A', 'B', 'C', 'D']):
        for stint, compound in enumerate(['SOFT', 'MEDIUM'], 1):
            for age in range(1, laps + 1):
                lap = age + (stint - 1) * laps + j
                seconds = 80 + j * .2 + TYPICAL_OFFSET[compound] + TYPICAL_DEG[compound] * age - .06 * lap
                rows.append(dict(Driver=driver, Stint=stint, Compound=compound, TyreLife=float(age), LapNumber=lap,
                                 LapTime=seconds + rng.normal(0, .1)))
    return pd.DataFrame(rows)


def test_covariance_is_psd_and_contracts_as_clean_laps_accumulate():
    data = observations()
    early = fit_tyre_model(data[data.LapNumber <= 10])
    later = fit_tyre_model(data)
    covariance = np.asarray(later.covariance)
    np.testing.assert_allclose(covariance, covariance.T, atol=1e-12)
    assert np.linalg.eigvalsh(covariance).min() > 0
    for model in [early, later]:
        assert not model.bounded_wear
    def wear_sd(model, compound):
        return model.contrast_sd(lap_coefficients(model, None, compound, 1)
                                 - lap_coefficients(model, None, compound, 0))
    assert wear_sd(later, 'SOFT') < wear_sd(early, 'SOFT')
    assert wear_sd(later, 'HARD') == pytest.approx(PRIOR_SD['deg'])  # no hard observations


def test_reference_plan_has_zero_relative_uncertainty_and_base_pace_cancels():
    model = fit_tyre_model(observations())
    window = pit_window(model, 'A', 'MEDIUM', 20, 25, 20., ['SOFT', 'HARD'])
    best = window.loc[window.Total.idxmin()]
    assert best.Lost == best.LostLow == best.LostHigh == 0
    assert (window.LostLow <= window.Lost).all() and (window.LostHigh >= window.Lost).all()
    shifted = replace(model, base={d: b + 500 for d, b in model.base.items()})
    alternative = pit_window(shifted, 'A', 'MEDIUM', 20, 25, 20., ['SOFT', 'HARD'])
    np.testing.assert_allclose(window[['Lost', 'LostLow', 'LostHigh']], alternative[['Lost', 'LostLow', 'LostHigh']], atol=1e-8)


def test_shared_parameters_are_propagated_as_a_contrast_not_independent_plan_errors():
    model = fit_tyre_model(observations())
    one = lap_coefficients(model, None, 'SOFT', np.arange(1, 10))
    two = lap_coefficients(model, None, 'SOFT', np.arange(2, 11))
    n = len(model.parameter_drivers)
    # Same compound offset cancels. Only 9 laps of additional tyre age remain.
    assert one[n] == two[n] == 9
    expected = 9 * np.sqrt(model.covariance[n + 2][n + 2])
    assert model.contrast_sd(two - one) == pytest.approx(expected)
    assert model.contrast_sd(two - one) < np.hypot(model.contrast_sd(one), model.contrast_sd(two))


def test_prior_ranges_work_with_no_driver_pace_and_clipped_wear_suppresses_ranges():
    empty = observations().iloc[:0]
    prior = fit_tyre_model(empty, allow_prior=True)
    window = pit_window(prior, 'A', 'MEDIUM', 1, 40, 20., ['SOFT', 'HARD'])
    assert 'LostLow' in window and np.isfinite(window.LostHigh).all()
    assert not prior.base and prior.prior_only
    clipped = replace(prior, bounded_wear=True)
    assert clipped.contrast_sd(np.ones(6)) is None
    assert 'LostLow' not in pit_window(clipped, 'A', 'MEDIUM', 1, 40, 20., ['SOFT', 'HARD'])


def test_approximate_gaussian_ranges_have_expected_synthetic_coverage():
    # Synthetic assumptions match the Gaussian priors and independent 0.3 s lap noise.
    # This checks the algebra/scale; it deliberately does NOT claim real-race coverage.
    from gridpulse.undercut.window import _design

    rng = np.random.default_rng(1901)
    design = observations()
    drivers = sorted(design.Driver.unique())
    n = len(drivers)
    x = _design(design, drivers)
    centers = np.array([80 + i * .2 for i in range(n)] + [-.5, .4, .09, .06, .04, -.06])
    sd = np.array([0.] * n + [.4, .4, .01, .01, .01, .03])
    covered, checked = 0, 0
    for _ in range(100):
        truth = centers + rng.normal(size=n + 6) * sd
        sample = design.assign(LapTime=x @ truth + rng.normal(0, .3, len(design)))
        model = fit_tyre_model(sample)
        weights = lap_coefficients(model, None, 'SOFT', [20, 21]) - lap_coefficients(model, None, 'HARD', [1, 2])
        half = MODEL_Z * model.contrast_sd(weights)
        estimate = sum(model.lap_time('A', 'SOFT', np.array([20, 21]))) - sum(model.lap_time('A', 'HARD', np.array([1, 2])))
        covered += abs(estimate - weights @ truth) <= half
        checked += 1
    assert .80 <= covered / checked <= .98
