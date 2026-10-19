"""Visitors can identify a venue and read a score without deciphering presentation details."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from gridpulse import snapshots
from gridpulse.pitwall import app, dtm_page, event_names, home_data

APP = str(Path(app.__file__))


def test_malaysia_host_context_is_sourced_and_does_not_rewrite_historical_bahrain():
    before = snapshots.race_metadata(2026, 16)
    event = next(e for e in home_data.weekends(2026, '2026-10-19') if e['key'] == 'f1-2026-16')
    assert event['title'] == 'Bahrain Grand Prix in Malaysia'
    assert event['place'] == 'Sepang International Circuit · Malaysia'
    assert event['venue_source'] == event_names.MALAYSIA_SOURCE and event['venue_note']
    older = next(e for e in home_data.weekends(2025, '2026-10-19') if e['key'] == 'f1-2025-4')
    assert older['title'] == 'Bahrain Grand Prix'
    assert older['place'] == 'Bahrain International Circuit · Bahrain' and not older['venue_note']
    assert snapshots.race_metadata(2026, 16) == before  # no silent source-data correction
    assert event_names.title(2025, 'Bahrain Grand Prix', 'Kuala Lumpur') == 'Bahrain Grand Prix'


def test_current_dtm_season_opens_saved_data_and_only_refresh_reaches_the_network(monkeypatch):
    dtm_page.load.clear()
    calls = []

    def fetch(year):
        calls.append(year)
        return dtm_page.data.saved(year)

    monkeypatch.setattr(dtm_page.data, 'fetch', fetch)
    season, source = dtm_page.load(2026, False, False)
    assert not calls and season['year'] == 2026 and source == 'Saved snapshot'
    dtm_page.load(2026, True, False)
    assert calls == [2026]
    dtm_page.load.clear()


def test_standings_keep_name_and_score_adjacent_and_pin_them(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    at = AppTest.from_string('from gridpulse.pitwall.dtm_page import render\nrender()', default_timeout=60)
    at.query_params.update(year='2026', view='championship')
    at.run()
    assert not at.exception
    board = at.dataframe[0]
    assert list(board.proto.column_order) == ['Pos', 'Name', 'Points', 'Team']
    settings = json.loads(board.proto.columns)
    assert all(settings[c]['pinned'] for c in ['Pos', 'Name', 'Points'])
    assert board.value.iloc[0]['Name'] == 'Thomas Preining' and board.value.iloc[0]['Points'] == 225
    assert any(e.label == 'Full classification & points breakdown' for e in at.expander)


def test_more_replay_tools_keep_deep_links_and_primary_selection_in_sync(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update(year='2025', round='4', lap='23', view='Messages', mode='replay')
    at.run()
    assert not at.exception
    assert at.selectbox(key='view_more').value == 'Messages'
    assert at.segmented_control(key='view_primary').value is None
    at.segmented_control(key='view_primary').set_value('Tyres').run()
    assert at.selectbox(key='view_more').value == 'More' and at.query_params['view'] == 'Tyres'
    at.selectbox(key='view_more').set_value('Radio').run()
    assert at.session_state['view'] == 'Radio' and at.query_params['view'] == 'Radio'
    assert at.segmented_control(key='view_primary').value is None


def test_dtm_atlas_starts_in_europe_and_respects_an_explicit_world_link(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    at = AppTest.from_string('from gridpulse.pitwall.dtm_page import render\nrender()', default_timeout=60)
    at.query_params.update(year='2026', view='circuits')
    at.run()
    assert not at.exception and at.session_state['dtm_region'] == 'europe'
    at = AppTest.from_string('from gridpulse.pitwall.dtm_page import render\nrender()', default_timeout=60)
    at.query_params.update(year='2026', view='circuits', region='world')
    at.run()
    assert not at.exception and at.session_state['dtm_region'] == 'world'


def test_dtm_map_marker_opens_facts_without_mutating_an_instantiated_selector(monkeypatch):
    from gridpulse.pitwall import dtm_circuits

    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')

    def marker(region, selected=None, **kwargs):
        return {'kind': 'circuit', 'value': 'nurburgring', 'id': 'marker-click'} if selected is None else None

    monkeypatch.setattr(dtm_circuits, 'atlas_map', marker)
    at = AppTest.from_string('from gridpulse.pitwall.dtm_page import render\nrender()', default_timeout=60)
    at.query_params.update(year='2026', view='circuits')
    at.run()
    assert not at.exception
    assert at.selectbox(key='dtm_circuit').value == 'nurburgring'
    assert at.query_params['year'] == '2026' and at.query_params['circuit'] == 'nurburgring'
    assert 'DTM circuit file' in ''.join(h.proto.body for h in at.get('html'))


def test_replay_view_survives_retiring_the_previous_navigation_widget():
    at = AppTest.from_string('''
import streamlit as st
from gridpulse.pitwall import replay_navigation
if not st.session_state.get('upgraded'):
    st.segmented_control('View', replay_navigation.VIEWS, key='view', default='Messages')
    st.button('Upgrade', on_click=lambda: st.session_state.update(upgraded=True))
else:
    replay_navigation.render()
''').run()
    at.button[0].click().run()
    at.run()
    assert not at.exception
    assert at.session_state['view'] == 'Messages'
    assert at.selectbox(key='view_more').value == 'Messages'
