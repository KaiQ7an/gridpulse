"""Early strategy is useful without inventing measurements or reading future laps."""

from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.pitwall import app
from gridpulse.pitwall.data import load_race
from gridpulse.pitwall.featured import FEATURED
from gridpulse.undercut.window import fit_tyre_model, pit_window


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')


def html(at):
    return ''.join(h.proto.body for h in at.get('html'))


def replay(params):
    at = AppTest.from_file(str(Path(app.__file__)), default_timeout=60)
    at.query_params.update(params)
    return at.run()


@pytest.mark.parametrize('lap', [1, 2, 4])
def test_early_dry_strategy_and_tyres_render_with_explicit_evidence(lap):
    at = replay(dict(year='2025', round='4', lap=str(lap), drivers='HAM,LEC', view='Strategy', mode='replay'))
    assert not at.exception
    assert any(chart.key == 'chart_window' for chart in at.get('plotly_chart'))
    assert all(toggle.key != 'window_actual' for toggle in at.toggle)
    if lap == 1:
        assert 'Pre-race prior window' in html(at) and '0 clean laps' in html(at)
        assert 'Catch estimates wait' in html(at)
    at.segmented_control(key='view').set_value('Tyres').run()
    assert not at.exception and 'Typical wear reference · not measured' in html(at)
    assert any(chart.key == 'chart_deg_prior' for chart in at.get('plotly_chart'))


def test_wet_start_does_not_invent_a_slick_strategy(monkeypatch):
    race = load_race(2025, 4)
    wet = replace(race, laps=race.laps.assign(Compound='INTERMEDIATE'))
    monkeypatch.setattr(app, 'cached_race', lambda *args: wet)
    at = AppTest.from_string('from gridpulse.pitwall.app import main\nmain()', default_timeout=60)
    at.query_params.update(year='2025', round='4', lap='1', view='Strategy', mode='replay')
    at.run()
    assert not at.exception and 'Pre-race prior window' not in html(at)
    assert not any(chart.key == 'chart_window' for chart in at.get('plotly_chart'))
    at.segmented_control(key='view').set_value('Tyres').run()
    assert not any(chart.key == 'chart_deg_prior' for chart in at.get('plotly_chart'))


@pytest.mark.parametrize('lap', [1, 3])
def test_prior_and_early_fit_do_not_read_future_pace(lap):
    race = load_race(2025, 4)
    future = race.laps.copy()
    future.loc[future.LapNumber > lap, 'LapTime'] *= .5
    model = fit_tyre_model(race.clean_through(lap), allow_prior=True)
    changed = fit_tyre_model(replace(race, laps=future).clean_through(lap), allow_prior=True)
    assert model == changed
    pd.testing.assert_frame_equal(pit_window(model, 'HAM', 'MEDIUM', lap, 57 - lap, 20., ['HARD']),
                                  pit_window(changed, 'HAM', 'MEDIUM', lap, 57 - lap, 20., ['HARD']))


def test_home_and_about_share_exact_strategy_links():
    at = AppTest.from_file(str(Path(app.__file__)), default_timeout=60).run()
    for moment in FEATURED:
        link = next(link for link in at.get('page_link') if link.label == moment.title)
        assert parse_qs(link.proto.query_string) == {k: [v] for k, v in moment.params.items()}
    from gridpulse.pitwall.about_page import FEATURED as about_featured

    assert about_featured is FEATURED


@pytest.mark.parametrize('moment', FEATURED, ids=lambda m: m.title)
def test_every_featured_link_opens_a_live_window_at_its_lap_and_focus(moment):
    at = AppTest.from_file(str(Path(app.__file__)), default_timeout=60)
    at.session_state['window_driver'] = 'VER'  # a previous analysis must not hijack the featured driver
    at.query_params.update(moment.params)
    at.run()
    assert not at.exception
    assert at.slider(key='lap').value == moment.lap
    assert at.multiselect(key='focus').value == list(moment.drivers)
    assert at.segmented_control(key='view').value == 'Strategy'
    assert at.selectbox(key='window_driver').value == moment.drivers[0]
    assert at.toggle(key='no_spoilers').value
    assert any(chart.key == 'chart_window' for chart in at.get('plotly_chart'))
