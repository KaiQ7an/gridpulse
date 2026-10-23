"""Browser state is small, optional, untrusted and never a future-result switch."""

from gridpulse.pitwall.browser_memory import restore, snapshot, validated


def test_remembers_only_bounded_selections_and_always_reenables_spoiler_protection():
    state = {'saved_replay': {'race_year': 2025, 'race_pick': 14, 'lap': 18, 'focus': ['LEC', 'PIA'],
                              'view': 'Strategy', 'no_spoilers': False, 'window_actual': True},
             'home_pins': ['dtm-2025-2', 'dtm-2025-2', '<script>'],
             'dtm_saved': {'dtm_year': 2026, 'dtm_view': 'compare', 'dtm_drivers': ['engel-maro'], 'dtm_category': 'drivers'},
             'radar_preferences': {'compound': 'HARD', 'delay': 2, 'extra': .5, 'scope': 'Focus'},
             'home_show_results': True, 'password': 'should-never-leave-python'}
    saved = snapshot(state)
    assert saved['saved_replay']['no_spoilers'] is True
    assert 'window_actual' not in saved['saved_replay'] and 'home_show_results' not in saved and 'password' not in saved
    assert saved['home_pins'] == ['dtm-2025-2']
    restored = {}
    restore(restored, saved)
    assert restored['saved_replay']['focus'] == ['LEC', 'PIA']
    assert restored['dtm_saved']['dtm_drivers'] == ['engel-maro']
    assert restored['radar_preferences']['delay'] == 2


def test_restoration_does_not_overwrite_current_widget_values_or_a_new_selection():
    state = {'lap': 24, 'focus': ['NOR'], 'saved_replay': {'lap': 24}, 'home_pins': ['f1-2025-3']}
    restore(state, {'version': 1, 'saved_replay': {'race_year': 2025, 'race_pick': 14, 'lap': 18},
                    'home_pins': ['dtm-2026-1']})
    assert state == {'lap': 24, 'focus': ['NOR'], 'saved_replay': {'lap': 24}, 'home_pins': ['f1-2025-3']}


def test_malformed_and_oversized_browser_data_cannot_seed_invalid_widget_options():
    for bad in (None, [], {'version': 2}, {'version': 1, 'garbage': 'x' * 17_000}):
        assert validated(bad) == {}
    saved = validated({'version': 1, 'saved_replay': {'race_year': True, 'race_pick': -1, 'lap': '12'},
                       'dtm_saved': {'dtm_drivers': ['bad<script>', {}, 'valid-slug']},
                       'radar_preferences': {'delay': 99, 'compound': [], 'extra': float('nan')}})
    assert 'saved_replay' not in saved
    assert saved['dtm_saved']['dtm_drivers'] == ['valid-slug']
    assert saved['radar_preferences'] == {}


def test_followed_dtm_entries_are_separate_per_season_and_category_and_bounded():
    value = {'version': 1, 'dtm_followed': {'drivers-2026': ['engel-maro', 'preining-thomas'],
                                           'manufacturers-2025': ['Mercedes-AMG', 'Porsche'],
                                           'drivers-2024': ['invalid<script>', 'auer-lucas'],
                                           'unknown-2026': ['a']}}
    out = {}
    restore(out, value)
    assert out['dtm_followed'] == {'drivers-2026': ['engel-maro', 'preining-thomas'],
                                    'manufacturers-2025': ['Mercedes-AMG', 'Porsche'], 'drivers-2024': ['auer-lucas']}


def test_json_round_trip_of_zero_cost_retains_a_float_for_native_number_input():
    import json

    # Browser JSON does not preserve 0.0 versus 0, unlike a direct Python round trip.
    browser = json.loads('{"version":1,"radar_preferences":{"extra":0,"delay":1}}')
    assert type(validated(browser)['radar_preferences']['extra']) is float
