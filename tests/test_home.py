"""Home routing, spoiler boundaries and native navigation keep the workbench usable."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.pitwall import app, home_data, home_page

APP = str(Path(app.__file__))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')


def text(at):
    return ''.join(h.proto.body for h in at.get('html'))


def test_clean_root_is_home_and_never_builds_a_race_or_fetches_data(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('The home page must work entirely from small saved summaries')

    monkeypatch.setattr(app, 'cached_race', forbidden)
    import requests

    monkeypatch.setattr(requests, 'get', forbidden)
    at = AppTest.from_string('from gridpulse.pitwall.app import main\nmain()', default_timeout=60).run()
    assert not at.exception
    assert 'Choose your series' in text(at) and 'Around the paddock' in text(at)
    assert 'Formula 1' in text(at) and 'DTM' in text(at)
    assert len(at.slider) == 0
    assert at.toggle(key='home_show_results').value is False
    assert [l.label for l in at.sidebar.get('page_link')] == ['GridPulse', 'Home', 'Race replay', 'DTM', 'Circuits', 'About']
    assert at.sidebar.get('page_link')[0].proto.help == 'Return to GridPulse home'


def test_home_filter_results_and_shortlist(monkeypatch):
    real = home_data.podiums
    calls = []

    def podiums(event):
        calls.append(event['key'])
        return real(event)

    monkeypatch.setattr(home_data, 'podiums', podiums)
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.selectbox(key='home_recent_year').set_value(2025).run()
    at.segmented_control(key='home_recent_series').set_value('DTM').run()
    at.text_input(key='home_search').set_value('Norisring').run()
    assert not at.exception and not calls
    pins = [b for b in at.button if b.key.startswith('home-pin-')]
    assert len(pins) == 1
    key = pins[0].key.removeprefix('home-pin-')
    pins[0].click().run()
    assert at.session_state['home_pins'] == [key] and 'Your shortlist' in text(at)
    at.toggle(key='home_show_results').set_value(True).run()
    assert calls == [key] and 'classified podium' in text(at)
    at.segmented_control(key='home_recent_series').set_value('Formula 1').run()
    assert 'No matching weekends' in ' '.join(i.value for i in at.info)
    assert at.session_state['home_pins'] == [key]  # shortlist outlives the filter
    at.button(key='home-unpin-' + key).click().run()
    assert not at.session_state['home_pins']


def test_resume_targets_preserve_lap_focus_and_dtm_detail_without_result_spoilers():
    state = {'saved_replay': {'race_year': 2025, 'race_pick': 4, 'lap': 23, 'focus': ['HAM', 'LEC'],
                              'view': 'Tyres', 'no_spoilers': True},
             'dtm_saved': {'dtm_year': 2024, 'dtm_view': 'circuits', 'dtm_circuit': 'nurburgring', 'dtm_region': 'europe'}}
    f1, dtm = home_data.resume_targets(state)
    assert f1['params'] == {'year': '2025', 'round': '4', 'lap': '23', 'drivers': 'HAM,LEC', 'view': 'Tyres', 'mode': 'replay'}
    assert dtm['params'] == {'year': '2024', 'view': 'circuits', 'circuit': 'nurburgring', 'region': 'europe'}
    assert 'winner' not in str([f1, dtm]).lower()


def test_dtm_map_sends_no_race_classifications_and_opens_its_own_circuit_page(monkeypatch):
    captured = []

    def map_click(region, **kwargs):
        captured.append(kwargs['circuit_data'])
        return {'kind': 'circuit', 'value': 'nurburgring', 'id': 'home-test'} if kwargs['series'] == 'DTM' else None

    monkeypatch.setattr(home_page, 'atlas_map', map_click)
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.segmented_control(key='home_map_series').set_value('DTM').run()
    assert not at.exception
    assert at.query_params['view'] == 'circuits' and at.query_params['circuit'] == 'nurburgring'
    assert at.radio(key='dtm_view').value == 'circuits'
    assert at.selectbox(key='racing_series').value == 'DTM'
    assert all('event' not in pin and 'rows' not in pin and 'races' not in pin for batch in captured for pin in batch)


def test_legacy_root_link_still_replays_and_new_replay_route_is_registered():
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update(year='2025', round='4', lap='23', drivers='HAM,LEC', mode='replay')
    at.run()
    assert not at.exception and at.slider(key='lap').value == 23
    assert at.toggle(key='no_spoilers').value
    pages = at.session_state['sidebar_pages']
    assert next(p for p in pages if p.title == 'Race replay').url_path == 'replay'


@pytest.mark.parametrize('series', ['Formula 1', 'DTM'])
def test_home_series_switcher_enters_either_championship(series):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert at.selectbox(key='home_series_picker').value == 'All series'
    at.selectbox(key='home_series_picker').set_value(series).run()
    assert not at.exception
    assert at.selectbox(key='racing_series').value == series
    assert len(at.slider) == 1 if series == 'Formula 1' else at.radio(key='dtm_view').value == 'championship'
