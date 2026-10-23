"""Weekend insight never imports later rounds or counts qualifying twice."""

from copy import deepcopy

import pandas as pd
import pytest

from gridpulse.dtm import data
from gridpulse.dtm.impact import weekend_impact


def race(*rows):
    return {'kind': 'race', 'rows': [{'driver': d, 'name': name, 'total_points': pts} for d, name, pts in rows]}


def test_weekend_points_use_race_totals_and_future_rounds_cannot_change_the_past():
    season = data.saved(2026)
    result = weekend_impact(season, 2)
    row = result.table.set_index('Driver').loc['Thomas Preining']
    assert row['Weekend points'] == 17 and row.Before == 29 and row.After == 46
    later = deepcopy(season)
    for event in later['events']:
        for session in event['sessions']:
            for allocation in session['rows']:
                if event['round'] > 2 or session['kind'] == 'qualifying':
                    allocation['total_points'] = 9999
    for row in later['standings']['drivers']:
        row['points'] = 99999
    pd.testing.assert_frame_equal(result.table, weekend_impact(later, 2).table)


def test_ties_share_rank_and_a_new_entry_has_no_invented_previous_position():
    first = race(('a', 'Alice', 10), ('b', 'Bob', 0))
    second = race(('a', 'Alice', 0), ('b', 'Bob', 10), ('c', 'Chris', 5))
    season = {'events': [{'round': 1, 'sessions': [first, first]}, {'round': 2, 'sessions': [second, second]}]}
    result = weekend_impact(season, 2)
    rows = result.table.set_index('Driver')
    assert result.complete and result.gap == 0
    assert rows.loc['Alice', 'Points rank after'] == rows.loc['Bob', 'Points rank after'] == 1
    assert pd.isna(rows.loc['Chris', 'Points rank before']) and pd.isna(rows.loc['Chris', 'Places gained'])


@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), '25', True])
def test_unknown_allocations_are_not_zero_points_or_false_standings(bad):
    season = {'events': [{'round': 1, 'sessions': [race(('a', 'Alice', bad)), race(('a', 'Alice', 5))]}]}
    result = weekend_impact(season, 1)
    assert not result.complete and result.gap is None
    assert result.table.After.isna().all() and result.table['Weekend points'].isna().all()


def test_missing_prior_race_withholds_totals_but_keeps_published_weekend_points():
    season = {'events': [{'round': 1, 'sessions': []},
                         {'round': 2, 'sessions': [race(('a', 'Alice', 12)), race(('a', 'Alice', 8))]}]}
    result = weekend_impact(season, 2)
    assert not result.complete and result.table.iloc[0]['Weekend points'] == 20
    assert result.table.After.isna().all()


def test_first_weekend_does_not_claim_a_previous_lead():
    result = weekend_impact(data.saved(2026), 1)
    assert result.complete and result.lead and result.previous_gap is None
