"""A short primary view row and a native selector for supporting replay tools."""

import streamlit as st

PRIMARY = ['Gaps', 'Strategy', 'Tyres', 'Positions']
SECONDARY = ['Pit stops', 'Pace', 'Radio', 'Messages']
VIEWS = PRIMARY + SECONDARY


def select_primary():
    if st.session_state.view_primary:
        st.session_state.view = st.session_state.view_primary


def select_more():
    if st.session_state.view_more != 'More':
        st.session_state.view = st.session_state.view_more


def render() -> str:
    ss = st.session_state
    active = ss.get('view', 'Gaps')
    ss.view = active  # Detach an old `view` widget value before Streamlit cleans up the retired widget.
    ss.view_primary = active if active in PRIMARY else None
    ss.view_more = active if active in SECONDARY else 'More'
    primary, more = st.columns([3.3, 1.5], gap='small', vertical_alignment='bottom')
    primary.segmented_control('Main replay views', PRIMARY, key='view_primary', on_change=select_primary,
                              format_func=lambda v: 'Order' if v == 'Positions' else v,
                              label_visibility='collapsed', width='stretch', wrap=False)
    more.selectbox('More replay views', ['More', *SECONDARY], key='view_more', on_change=select_more,
                   label_visibility='collapsed')
    return active
