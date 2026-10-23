"""Reconstruct a weekend's points impact from allocations published through that round.

These are not intermediate official standings: deductions applied outside a race
allocation and official countback are unavailable. Ties share a points rank.
Race-row total_points already includes qualifying; qualifying rows are never added.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from numbers import Real

import pandas as pd


@dataclass
class WeekendImpact:
    table: pd.DataFrame
    complete: bool
    races: int
    lead: str | None = None
    rival: str | None = None
    gap: float | None = None
    previous_gap: float | None = None


def points(value):
    return float(value) if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) else None


def ranks(totals):
    """Competition rank by points only: ties are 1, 1, 3, not arbitrary name order."""
    return {d: 1 + sum(v > total for v in totals.values()) for d, total in totals.items()}


def weekend_impact(season: dict, round_number: int) -> WeekendImpact:
    before, earned = defaultdict(float), defaultdict(float)
    names, before_names, missing, complete, selected_races = {}, set(), set(), True, 0
    for event in sorted(season['events'], key=lambda e: e['round']):
        if event['round'] > round_number:
            continue
        sessions = [s for s in event['sessions'] if s['kind'] == 'race']
        # A DTM weekend has two races. In-progress/missing weekends cannot be
        # presented as a complete cumulative championship reconstruction.
        if len(sessions) != 2 or any(not s['rows'] for s in sessions):
            complete = False
        for session in sessions:
            if event['round'] == round_number:
                selected_races += 1
            for row in session['rows']:
                driver = row['driver']
                names[driver] = row['name']
                value = points(row.get('total_points'))
                if event['round'] < round_number:
                    before_names.add(driver)
                if value is None:
                    complete = False
                    if event['round'] == round_number:
                        missing.add(driver)
                    continue
                (earned if event['round'] == round_number else before)[driver] += value
    after = {d: before[d] + earned[d] for d in names}
    rb, ra = ranks({d: before[d] for d in before_names}), ranks(after)
    order = sorted(names, key=lambda d: (-after[d], names[d])) if complete else sorted(names, key=lambda d: (-earned[d], names[d]))
    rows = [{'Driver': names[d], 'Weekend points': None if d in missing else earned[d],
             'Before': before[d] if complete else None, 'After': after[d] if complete else None,
             'Points rank before': rb.get(d) if complete else None,
             'Points rank after': ra[d] if complete else None,
             'Places gained': rb[d] - ra[d] if complete and d in rb else None} for d in order]
    result = WeekendImpact(pd.DataFrame(rows), complete, selected_races)
    if complete and len(order) >= 2:
        lead, rival = order[:2]
        result.lead, result.rival = names[lead], names[rival]
        result.gap = after[lead] - after[rival]
        if lead in before_names and rival in before_names:
            result.previous_gap = before[lead] - before[rival]
    return result
