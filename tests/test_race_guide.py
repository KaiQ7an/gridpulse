"""A first-time visitor can complete a lesson without future results or changing a replay."""

from dataclasses import replace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.pitwall import app, explain, learn_page, tables
from gridpulse.pitwall.timing import timing_tower


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('GRIDPULSE_OFFLINE', '1')


def lesson():
    return AppTest.from_string('''
import streamlit as st
from gridpulse.pitwall import learn_page, about_page
def unused(): pass
pages = [st.Page(learn_page.render, title='Race guide', default=True),
         st.Page(unused, title='Race replay', url_path='replay'),
         st.Page(unused, title='DTM', url_path='dtm')]
about_page.pages = {p.title:p for p in pages}
st.navigation(pages).run()
''', default_timeout=60)


def test_guide_finishes_and_feedback_matches_the_real_window_without_changing_a_replay(monkeypatch):
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError('The saved guide must not fetch data')

    learn_page.lesson_race.clear()
    monkeypatch.setattr(requests, 'get', forbidden)
    at = lesson()
    saved = {'race_year': 2026, 'race_pick': 15, 'lap': 35, 'view': 'Tyres', 'focus': ['RUS']}
    at.session_state.saved_replay = saved.copy()
    at.run()
    assert not at.exception
    assert 'Charles Leclerc' in ' '.join(m.value for m in at.markdown)
    at.button(key='learn-next').click().run()
    assert not at.exception
    at.segmented_control(key='learn_wait').set_value(3).run()
    race = learn_page.lesson_race()
    tower = timing_tower(race.laps, 18, race.retired, race.entrants, stops=race.stops)
    context = explain.prepare(race, tower, 18)
    best, window = explain.plan(race, tower, 18, 'LEC', context)
    expected = explain.comparison(window, best.Compound, 3)['delta']
    assert at.metric[0].value == f'{expected:+.1f} s'
    assert at.session_state['saved_replay'] == saved
    at.button(key='learn-next').click().run()
    assert not at.exception
    assert any('You tried waiting two more laps' in m.value for m in at.markdown)
    assert not at.toggle  # no future-result reveal control in this lesson
    assert any(link.proto.query_string.endswith('mode=replay') for link in at.get('page_link')
               if link.label == 'Explore this moment in the full replay')
    at.button(key='learn-back').click().run()
    assert at.segmented_control(key='learn_wait').value == 3


def test_strategy_explanation_and_experiment_ignore_changed_future_laps():
    race = app.cached_race(2025, 14)
    tower = timing_tower(race.laps, 18, race.retired, race.entrants, stops=race.stops)
    context = explain.prepare(race, tower, 18)
    future = race.laps.copy()
    future.loc[future.LapNumber > 18, 'LapTime'] *= .4
    changed = replace(race, laps=future)
    other = explain.prepare(changed, tower, 18)
    a, first = explain.plan(race, tower, 18, 'LEC', context)
    b, second = explain.plan(changed, tower, 18, 'LEC', other)
    pd.testing.assert_frame_equal(first, second)
    assert explain.comparison(first, a.Compound, 3) == explain.comparison(second, b.Compound, 3)
    assert explain.takeaway(race, tower, 18, 'LEC', context) == explain.takeaway(changed, tower, 18, 'LEC', other)


def test_model_explanations_do_not_offer_wet_or_finished_plans():
    race = app.cached_race(2025, 14)
    tower = timing_tower(race.laps, 18, race.retired, race.entrants, stops=race.stops)
    wet = tower.assign(Compound='INTERMEDIATE')
    context = explain.prepare(race, tower, 18)
    assert explain.plan(race, wet, 18, 'LEC', context) == (None, None)
    assert explain.plan(race, tower, race.total_laps, 'LEC', context) == (None, None)
    assert explain.plan(race, tower, 18, 'UNKNOWN', context) == (None, None)


def test_saved_example_failure_has_an_escape_route(monkeypatch):
    def unavailable():
        raise OSError('saved file unavailable')

    monkeypatch.setattr(learn_page, 'lesson_race', unavailable)
    at = lesson().run()
    assert not at.exception and at.warning
    assert any(p.label == 'Open race replay' for p in at.get('page_link'))


def test_primary_score_table_escapes_names_and_does_not_dim_identity():
    table = pd.DataFrame([{'Pos': 1, 'Name': '<script>alert(1)</script>', 'Points': 25, 'Team': 'A & B'}])
    markup = tables.standings_html(table, 'drivers', 2026)
    assert '<script>' not in markup and '&lt;script&gt;' in markup and 'A &amp; B' in markup
    assert '<th scope="row">' in markup and '<td class="points">25</td>' in markup


def test_replay_keeps_driver_codes_in_urls_but_renders_full_names_and_plain_summary():
    at = AppTest.from_file(app.__file__, default_timeout=60)
    at.query_params.update(year='2025', round='14', lap='18', drivers='LEC,PIA', view='Strategy', mode='replay')
    at.run()
    assert not at.exception
    assert at.multiselect(key='focus').value == ['LEC', 'PIA']
    assert 'Charles Leclerc' in at.multiselect(key='focus').options
    markup = ''.join(h.proto.body for h in at.get('html'))
    assert 'What is happening?' in markup and 'Charles Leclerc leads Oscar Piastri' in markup
    assert at.query_params['drivers'] == 'LEC,PIA'
