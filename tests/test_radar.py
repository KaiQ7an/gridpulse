"""Short-horizon scenarios must reconcile clocks, retain actual neighbours and never read future pace."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.undercut.radar import undercut_radar
from gridpulse.undercut.window import DRY, TyreModel, fit_tyre_model


@pytest.fixture
def model():
    return TyreModel(base={'A': 80., 'B': 80., 'C': 80.}, offset={'SOFT': -.6, 'MEDIUM': 0., 'HARD': .4},
                     deg={'SOFT': .1, 'MEDIUM': .1, 'HARD': .03}, measured=set(DRY), deg_measured=set(DRY),
                     driver_samples={'A': 10, 'B': 10, 'C': 10}, parameter_drivers=('A', 'B', 'C'),
                     covariance=tuple(map(tuple, np.eye(9) * 1e-8)), noise_sd=.05)


@pytest.fixture
def tower():
    return pd.DataFrame({'Pos': [1, 2], 'Driver': ['A', 'B'], 'GapSeconds': [0., 1.2],
                         'Out': [False, False], 'Pit': [False, False], 'PitOut': [False, False],
                         'LapsDown': [0, 0], 'Compound': ['MEDIUM', 'MEDIUM'], 'TyreAge': [20., 20.]})


def scan(model, tower, **kwargs):
    return undercut_radar(model, tower, status=kwargs.pop('status', 'Green'), laps_left=kwargs.pop('laps_left', 30), **kwargs)


def test_response_clock_matches_hand_calculation_and_extra_cost(model, tower):
    # A: M21 + M22 + H1. B: M21 + H1 + H2. Equal pit costs and H1 cancel.
    # Advantage = M22 - H2 = 82.20 - 80.46 = 1.74; gap before the stops is 1.20.
    r = scan(model, tower).iloc[0]
    assert r.Gain == pytest.approx(1.74)
    assert r.Margin == pytest.approx(.54)
    assert r.Status == 'Model edge' and r.Low > 0
    assert scan(model, tower, disadvantage=.8).iloc[0].Margin == pytest.approx(-.26)
    # Waiting a second lap adds M23 - H3 to the gain.
    assert scan(model, tower, delay=2).iloc[0].Gain == pytest.approx(3.55)
    # Real observed driver pace applies on ALL three forecast laps, not only on the out-lap.
    slower = replace(model, base={**model.base, 'B': 80.2})
    assert scan(slower, tower).iloc[0].Gain == pytest.approx(1.14)
    common = replace(model, base={d: b + 500 for d, b in model.base.items()})
    pd.testing.assert_frame_equal(scan(common, tower), scan(model, tower), atol=1e-9)


@pytest.mark.parametrize('status', ['Yellow', 'VSC', 'VSC ending', 'Safety car', 'Red flag', 'Unknown'])
def test_radar_suspends_when_green_running_is_not_known(model, tower, status):
    assert scan(model, tower, status=status).empty


@pytest.mark.parametrize('column,value', [('Out', True), ('Pit', True), ('PitOut', True), ('LapsDown', 1),
                                         ('Compound', 'WET'), ('TyreAge', np.nan), ('GapSeconds', np.nan),
                                         ('Compound', pd.NA), ('Out', pd.NA), ('Pit', pd.NA),
                                         ('PitOut', pd.NA), ('LapsDown', np.nan)])
def test_ineligible_car_cannot_create_an_edge(model, tower, column, value):
    altered = tower.copy()
    if value is pd.NA:
        altered[column] = altered[column].astype(object)
    altered.loc[1, column] = value
    assert scan(model, altered).empty


def test_filtering_does_not_invent_adjacency_across_an_ineligible_middle_car(model, tower):
    third = tower.iloc[[1]].assign(Pos=3, Driver='C', GapSeconds=2.)
    tower = pd.concat([tower, third], ignore_index=True)
    tower.loc[1, 'Pit'] = True
    assert scan(model, tower).empty  # A -> C would have looked close after filtering B out


def test_evidence_and_missing_model_are_distinct_from_a_measured_edge(model, tower):
    assert scan(replace(model, driver_samples={'A': 4, 'B': 20}), tower).iloc[0].Status == 'Learning'
    assert scan(replace(model, measured={'MEDIUM'}), tower).iloc[0].Status == 'Prior-led'
    assert scan(replace(model, bounded_wear=True), tower).iloc[0].Status == 'Range unavailable'
    assert scan(replace(model, base={'A': 80.}), tower).empty
    assert scan(replace(model, prior_only=True), tower).empty
    assert scan(model, tower, laps_left=2).empty
    tower.loc[1, 'GapSeconds'] = 4.
    assert scan(model, tower).empty


def test_parameter_range_and_future_lap_noise_both_contribute(model, tower):
    certain = scan(model, tower).iloc[0]
    noisy = scan(replace(model, noise_sd=.7), tower).iloc[0]
    assert noisy.High - noisy.Low > certain.High - certain.Low
    assert noisy.Status == 'Uncertain'  # same point estimate, insufficient certainty


def test_replay_radar_is_invariant_to_modified_or_removed_future_laps(monkeypatch):
    from gridpulse.pitwall.data import load_race
    from gridpulse.pitwall.timing import timing_tower

    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    race, lap = load_race(2025, 4), 23

    def analyze(r):
        known = r.laps[r.laps.LapNumber <= lap]
        current = timing_tower(known, lap, r.retired, r.entrants, official=False, stops=r.stops_through(lap))
        fitted = fit_tyre_model(r.clean_through(lap), allow_prior=True)
        return scan(fitted, current)

    expected = analyze(race)
    assert not expected.empty
    future = race.laps.copy()
    future.loc[future.LapNumber > lap, 'LapTime'] *= .1
    future.loc[future.LapNumber > lap, 'TyreLife'] = 100.
    future.loc[future.LapNumber > lap, 'Compound'] = 'WET'
    pd.testing.assert_frame_equal(analyze(replace(race, laps=future)), expected)
    pd.testing.assert_frame_equal(analyze(replace(race, laps=race.laps[race.laps.LapNumber <= lap])), expected)


def test_strategy_controls_and_learning_states_render_without_future_stops(monkeypatch):
    from pathlib import Path

    from gridpulse.pitwall import app

    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    at = AppTest.from_file(str(Path(app.__file__)), default_timeout=60)
    at.query_params.update(year='2025', round='4', lap='23', view='Strategy', mode='replay')
    at.run()
    assert not at.exception and any(c.key == 'chart_undercut_radar' for c in at.get('plotly_chart'))
    at.selectbox(key='radar_compound').set_value('MEDIUM').run()
    at.selectbox(key='radar_delay').set_value(2).run()
    at.number_input(key='radar_extra').set_value(1.5).run()
    assert not at.exception and at.number_input(key='radar_extra').value == 1.5
    at.segmented_control(key='view_primary').set_value('Tyres').run()
    at.segmented_control(key='view_primary').set_value('Strategy').run()
    assert not at.exception
    assert at.selectbox(key='radar_compound').value == 'MEDIUM'
    assert at.selectbox(key='radar_delay').value == 2
    assert at.number_input(key='radar_extra').value == 1.5
    at.toggle(key='window_ranges').set_value(False).run()
    assert not at.exception
    at.slider(key='lap').set_value(1).run()
    assert not at.exception
    assert not any(c.key == 'chart_undercut_radar' for c in at.get('plotly_chart'))


def test_invalid_scenarios_are_rejected(model, tower):
    for kwargs in [{'compound': 'WET'}, {'delay': 0}, {'disadvantage': np.nan}, {'max_gap': -1.}]:
        with pytest.raises(ValueError):
            scan(model, tower, **kwargs)
