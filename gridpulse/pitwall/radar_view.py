"""Interactive undercut scenarios; model and current-tower eligibility live in the data layer."""

import pandas as pd
import streamlit as st

from gridpulse.pitwall import charts, explain, ui
from gridpulse.undercut.radar import undercut_radar
from gridpulse.undercut.window import DRY


def inspect_chaser(running: set[str]) -> None:
    """Plotly's native selection callback runs before the pit-window widget is remounted."""
    points = st.session_state.get('chart_undercut_radar', {}).get('selection', {}).get('points', [])
    if points and points[-1].get('customdata'):
        driver = points[-1]['customdata'][0]
        if driver in running:
            st.session_state.window_driver = driver


def render(race, tower: pd.DataFrame, lap: int, model, focus: list[str]) -> None:
    ui.label('Undercut radar')
    status = race.lap_status.get(lap, 'Unknown')
    if status != 'Green':
        ui.note(f'{status}: the green-flag undercut radar is suspended.')
        return
    if model is None or model.prior_only:
        ui.note('Learning: undercut comparisons wait for observed dry pace from both drivers.')
        return
    if race.total_laps - lap < 3:
        ui.note('Not enough laps remain for both cars to complete the scenario.')
        return

    prefs = st.session_state.setdefault('radar_preferences', {})
    a, b, c = st.columns([1, 1, 1.2])
    compound = a.selectbox('Fresh tyre', DRY, index=DRY.index(prefs.get('compound', 'HARD')),
                            format_func=str.title, key='radar_compound')
    delay = b.selectbox('Reply after', [1, 2, 3], format_func=lambda n: f'{n} lap' + ('s' if n > 1 else ''),
                        index=[1, 2, 3].index(prefs.get('delay', 1)), key='radar_delay',
                        help='How many laps later the car ahead responds to the first stop.')
    extra = c.number_input('Extra cost (s)', min_value=0.0, max_value=5.0, value=float(prefs.get('extra', 0.0)), step=0.1,
                           key='radar_extra', help='Extra stop or warm-up cost for the first stopper relative to the rival. '
                           'Equal total pit costs cancel; they are not deducted twice.')
    current = race.laps[race.laps.LapNumber == lap]
    outlaps = set(current.loc[current.PitOutTime.notna(), 'Driver'])
    pairs = undercut_radar(model, tower.assign(PitOut=tower.Driver.isin(outlaps)), status=status,
                           laps_left=race.total_laps - lap, compound=compound, delay=delay, disadvantage=extra)
    prefs.update(compound=compound, delay=delay, extra=extra)
    ui.note(f'Within 3.5 s · first stop L{lap + 1}, reply L{lap + 1 + delay}, compare after L{lap + 2 + delay}. '
            f'Both fit fresh {compound.lower()}s. Equal stop costs and clear air assumed; tyre availability is unknown.')
    if pairs.empty:
        ui.note('No eligible adjacent lead-lap pair has both measured pace and a gap within 3.5 s. '
                'Wet tyres, pit laps, out-laps and missing timing are excluded.')
        return
    scope = st.segmented_control('Show battles', ['Top 6', 'Focus', 'All'], default=prefs.get('scope', 'Top 6'),
                                 required=True, key='radar_scope', label_visibility='collapsed')
    prefs['scope'] = scope
    shown = pairs.head(6) if scope == 'Top 6' else pairs
    if scope == 'Focus':
        shown = pairs[pairs.Chaser.isin(focus) | pairs.Ahead.isin(focus)]
    if shown.empty:
        ui.note('No current eligible battle involves a focus driver. Choose Top 6 or All to scan the field.')
        return
    if (shown.Status == 'Model edge').any():
        edge = shown[shown.Status == 'Model edge'].iloc[0]
        ui.insight(f'{explain.name(race, edge.Chaser)} → {explain.name(race, edge.Ahead)}: {edge.Margin:+.2f} s after the response in this scenario. '
                   'The model range is above break-even; traffic and actual stop performance can change the outcome.')
    else:
        ui.note('No clear measured edge in these battles. Blue/grey dots use priors, are still learning or lack a range; '
                'amber ranges cross break-even.')
    st.plotly_chart(charts.readable(charts.undercut_radar_chart(shown, race.full_names), race.full_names), width='stretch', key='chart_undercut_radar',
                    on_select=lambda: inspect_chaser(set(tower.loc[~tower.Out & (tower.LapsDown == 0), 'Driver'])),
                    selection_mode='points')
    ui.note(f'Showing {len(shown)} of {len(pairs)} eligible battles. '
            'Hover for gains, ranges and sample counts. Click a dot to inspect the chaser in the pit window above. '
            'Ranges include model parameter uncertainty and lap noise, not a calibrated chance of overtaking.')
    with st.expander('Radar details'):
        detail = pairs[['Chaser', 'Ahead', 'Gap', 'Margin', 'Low', 'High', 'Status', 'ChaserSamples', 'AheadSamples']]
        detail = detail.assign(Chaser=detail.Chaser.map(explain.names(race)), Ahead=detail.Ahead.map(explain.names(race)))
        st.dataframe(detail.rename(columns={'Margin': 'Ahead after response (s)', 'Low': 'Model low (s)',
                                            'High': 'Model high (s)'}), hide_index=True, width='stretch')
