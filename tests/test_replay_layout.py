"""The compact replay retains live sectors/weather and starts without upstream requests."""

import pandas as pd
from streamlit.testing.v1 import AppTest

from gridpulse.pitwall import app


def test_first_visit_and_season_changes_use_snapshots_until_calendar_refresh(monkeypatch):
    monkeypatch.delenv('GRIDPULSE_OFFLINE', raising=False)
    calls = []

    def online(year):
        calls.append(year)
        saved = app.snapshots.races(year)
        extra = saved.iloc[0].copy()
        extra['RoundNumber'] = 99
        return pd.concat([saved, extra.to_frame().T], ignore_index=True)

    online.clear = lambda: None
    monkeypatch.setattr(app, 'cached_races', online)
    at = AppTest.from_string('from gridpulse.pitwall.app import choose_race\nchoose_race()')
    at.run()
    assert not at.exception and not calls
    year = at.selectbox(key='race_year').value
    assert at.selectbox(key='race_pick').value == app.snapshots.races(year).RoundNumber.max()
    at.selectbox(key='race_pick').set_value(int(app.snapshots.races(year).RoundNumber.max())).run()
    at.selectbox(key='race_year').set_value(2021).run()
    assert not at.exception and not calls  # stale round 17 must not trigger an online request
    assert at.selectbox(key='race_pick').value in app.snapshots.races(2021).RoundNumber.values
    at.button(key='refresh_calendar').click().run()
    assert not at.exception and calls == [2021]


def test_explicit_link_to_unsaved_round_can_still_fetch_calendar(monkeypatch):
    monkeypatch.delenv('GRIDPULSE_OFFLINE', raising=False)
    calls = []

    def online(year):
        calls.append(year)
        saved = app.snapshots.races(year)
        extra = saved.iloc[0].copy()
        extra['RoundNumber'] = 99
        return pd.concat([saved, extra.to_frame().T], ignore_index=True)

    monkeypatch.setattr(app, 'cached_races', online)
    at = AppTest.from_string('from gridpulse.pitwall.app import choose_race\nchoose_race()')
    at.query_params.update(year='2021', round='99')
    at.run()
    assert not at.exception and calls == [2021]
    # Match reset_for_new_race consuming the link after the first successful load.
    at.session_state['pending_replay'] = {}
    at.run()
    assert not at.exception and calls == [2021, 2021]
    assert at.selectbox(key='race_pick').value == 99


def test_compact_status_uses_only_sectors_and_weather_known_at_replay_lap(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    race = app.cached_race(2025, 4)
    at = AppTest.from_string('''
from gridpulse.pitwall.app import status_strip
from gridpulse.pitwall.timing import timing_tower
import streamlit as st
r = st.session_state.test_race
status_strip(r, r.laps[r.laps.LapNumber <= 12], timing_tower(r.laps, 12, r.retired, r.entrants, stops=r.stops), 12)
''')
    at.session_state.test_race = race
    at.run()
    assert not at.exception
    markup = ''.join(h.proto.body for h in at.get('html'))
    assert 'pl-replay-status' in markup
    assert all(f'Best S{i}' in markup for i in (1, 2, 3))
    assert 'Track temp' in markup and 'Air temp' in markup and 'Rain' in markup
    assert len(at.expander) == 0
    for ranking in app.fastest_sectors(race.laps[race.laps.LapNumber <= 12], top=3):
        assert all(lap <= 12 for _, _, lap in ranking)


def test_radio_reads_cache_without_loading_models(monkeypatch):
    from gridpulse.pitwall import views

    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')
    def forbidden(*args, **kwargs):
        raise AssertionError('The web view must never load a model or inspect optional engines')

    monkeypatch.setattr(views.transcribe, 'Transcriber', forbidden)
    monkeypatch.setattr(views.transcribe, 'available', forbidden)
    monkeypatch.setattr(views.translate, 'make', forbidden)
    monkeypatch.setattr(views.translate, 'available_engines', forbidden)
    monkeypatch.setattr(views.transcribe, 'cached', lambda url: None)
    at = AppTest.from_string('''
from gridpulse.pitwall.app import cached_race
from gridpulse.pitwall.views import radio_view
radio_view(cached_race(2025, 4), 30, ['HAM'])
''', default_timeout=60).run()
    assert not at.exception
    assert not any(b.key in ('transcribe_btn', 'translate_btn') for b in at.button)
    assert any('--transcribe --translate' in c.value for c in at.code)
