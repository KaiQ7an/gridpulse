"""A short answer to what this DTM weekend changed, with reconstruction limits."""

import html

import pandas as pd
import streamlit as st

from gridpulse.dtm.impact import weekend_impact
from gridpulse.pitwall import ui


def render(season, round_number):
    impact = weekend_impact(season, round_number)
    ui.label('What changed this weekend?')
    if impact.table.empty or not impact.races:
        st.caption('The points impact appears when race allocations are published.')
        return
    if impact.complete and impact.lead:
        if impact.gap == 0:
            st.write(f'**{impact.lead}** and **{impact.rival}** share the points lead in this reconstruction. '
                     'No countback tiebreak is applied here.')
        else:
            st.write(f'**{impact.lead}** leads this reconstruction by **{impact.gap:g} points** over {impact.rival}.')
        if impact.previous_gap is not None:
            change = impact.gap - impact.previous_gap
            before = ('was level on points' if impact.previous_gap == 0 else
                      f'led by {impact.previous_gap:g}' if impact.previous_gap > 0 else
                      f'trailed by {abs(impact.previous_gap):g}')
            st.caption(f'Against the same rival, {impact.lead} {before} before this weekend. '
                       f'Their advantage changed by {change:+g} point{"s" if abs(change) != 1 else ""}.')
    else:
        st.info('Some races or points are unpublished. Weekend allocations are shown where known; '
                'cumulative totals and rank changes are withheld.')
    table = impact.table
    leaders = table.sort_values(['Weekend points', 'Driver'], ascending=[False, True], na_position='last').head(5)
    rows = []
    for row in leaders.to_dict('records'):
        earned = '—' if pd.isna(row['Weekend points']) else f"{row['Weekend points']:g}"
        move = '—' if pd.isna(row['Places gained']) else f"{row['Places gained']:+g}"
        rows.append(f'<tr><th scope="row">{html.escape(row["Driver"])}</th><td>{earned}</td><td>{move}</td></tr>')
    st.html('<div class="impact-scroll"><table class="impact-table"><caption>Five highest weekend points allocations</caption>'
            '<thead><tr><th scope="col">Driver</th><th scope="col">Earned</th><th scope="col">Rank Δ</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table></div>')
    st.caption('Top five by weekend points. Rank Δ: positive means places gained in the points-only order; '
               'a dash means no comparable earlier entry or incomplete data.')
    with st.expander('Weekend points & championship movement', expanded=not impact.complete):
        st.dataframe(table, hide_index=True, width='stretch', height=min(530, 40 + 36 * len(table)),
                     column_config={key: st.column_config.NumberColumn(format='%d') for key in table.columns if key != 'Driver'})
    st.caption('Reconstructed from published race allocations through this round, including qualifying points once. '
               'Points ties share a rank; official countback and separate administrative deductions are not reconstructed. '
               'The season’s official standings remain authoritative.')
