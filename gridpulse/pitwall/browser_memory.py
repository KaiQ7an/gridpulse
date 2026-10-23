"""Small, versioned browser memory through Streamlit's public v2 component API.

Only selections are stored. No race data, account information, transcripts or
future-result switches leave Python. Browser data is untrusted and allowlisted.
Explicit URLs always win; hydration never mutates live widget keys.
"""

import json
import re
from datetime import date

import streamlit as st
from streamlit.components.v2 import component

VERSION = 1
STORAGE = 'gridpulse.preferences.v1'
SLUG = re.compile(r'[a-zA-Z0-9-]{1,80}\Z')
PIN = re.compile(r'(?:f1|dtm)-20[0-9]{2}-[0-9]{1,2}\Z')
VIEWS = {'Gaps', 'Strategy', 'Tyres', 'Positions', 'Pit stops', 'Pace', 'Radio', 'Messages'}


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def validated(value):
    """Bound size, keys and values before restoring any external state."""
    if not isinstance(value, dict) or value.get('version') != VERSION:
        return {}
    try:
        if len(json.dumps(value)) > 16_384:
            return {}
    except (TypeError, ValueError, RecursionError, OverflowError):
        return {}
    out = {'version': VERSION}
    pins = value.get('home_pins', [])
    if 'home_pins' in value and isinstance(pins, list):
        out['home_pins'] = list(dict.fromkeys(p for p in pins if isinstance(p, str) and PIN.fullmatch(p)))[:4]
    replay = value.get('saved_replay', {})
    if isinstance(replay, dict):
        clean = {}
        for key, low, high in (('race_year', 2021, date.today().year), ('race_pick', 1, 30), ('lap', 1, 200)):
            if integer(replay.get(key), low, high):
                clean[key] = replay[key]
        for key, options in (('race_session', {'Race', 'Sprint'}), ('view', VIEWS), ('speed', {'1×', '2×', '4×'})):
            if isinstance(replay.get(key), str) and replay[key] in options:
                clean[key] = replay[key]
        # Memory must not silently turn off spoiler protection on a new visit.
        clean['no_spoilers'] = True
        focus = replay.get('focus', [])
        if isinstance(focus, list):
            clean['focus'] = list(dict.fromkeys(d for d in focus if isinstance(d, str) and re.fullmatch('[A-Z]{3}', d)))[:6]
        if all(k in clean for k in ('race_year', 'race_pick', 'lap')):
            out['saved_replay'] = clean
    dtm = value.get('dtm_saved', {})
    if 'dtm_saved' in value and isinstance(dtm, dict):
        clean = {}
        for key, low, high in (('dtm_year', 2023, date.today().year), ('dtm_event', 1, 30)):
            if integer(dtm.get(key), low, high):
                clean[key] = dtm[key]
        for key, options in (('dtm_view', {'championship', 'weekend', 'teams', 'drivers', 'circuits', 'compare'}),
                             ('dtm_category', {'drivers', 'teams', 'manufacturers'})):
            if isinstance(dtm.get(key), str) and dtm[key] in options:
                clean[key] = dtm[key]
        for key in ('dtm_session', 'dtm_team', 'dtm_profile', 'dtm_circuit', 'dtm_region'):
            if isinstance(dtm.get(key), str) and SLUG.fullmatch(dtm[key]):
                clean[key] = dtm[key]
        drivers = dtm.get('dtm_drivers', [])
        if isinstance(drivers, list):
            clean['dtm_drivers'] = list(dict.fromkeys(d for d in drivers if isinstance(d, str) and SLUG.fullmatch(d)))[:4]
        out['dtm_saved'] = clean
    radar = value.get('radar_preferences', {})
    if 'radar_preferences' in value and isinstance(radar, dict):
        clean = {}
        for key, options in (('compound', {'SOFT', 'MEDIUM', 'HARD'}), ('scope', {'Top 6', 'Focus', 'All'})):
            if isinstance(radar.get(key), str) and radar[key] in options:
                clean[key] = radar[key]
        if integer(radar.get('delay'), 1, 3):
            clean['delay'] = radar['delay']
        if type(radar.get('extra')) in (float, int) and 0 <= radar['extra'] <= 5:
            clean['extra'] = float(radar['extra'])
        out['radar_preferences'] = clean
    followed = value.get('dtm_followed')
    if isinstance(followed, dict):
        out['dtm_followed'] = {k: list(dict.fromkeys(d for d in selected
                                      if isinstance(d, str) and SLUG.fullmatch(d)))[:6]
                              for k, selected in list(followed.items())[:16]
                              if isinstance(k, str) and re.fullmatch(r'(drivers|teams|manufacturers)-20[0-9]{2}', k)
                              and isinstance(selected, list)}
    return out


def snapshot(state):
    return validated({'version': VERSION, **{k: state[k] for k in
                     ('saved_replay', 'dtm_saved', 'home_pins', 'radar_preferences', 'dtm_followed') if k in state}})


def restore(state, incoming):
    """Restore durable copies only. Widget values and explicit links are untouched."""
    for key, value in validated(incoming).items():
        if key != 'version' and key not in state:
            state[key] = value


_reader = component('gridpulse_memory_read', js='''
export default function({data, setStateValue}) {
  if (data.ready) return;
  try {
    const raw = localStorage.getItem('gridpulse.preferences.v1');
    let saved = null;
    if (raw && raw.length <= 16384) { try { saved = JSON.parse(raw); } catch (_) {} }
    setStateValue('loaded', {ok:true, saved});
  } catch (_) { setStateValue('loaded', {ok:false}); }
}
''')
_writer = component('gridpulse_memory_write', js='''
export default function({data, setStateValue}) {
  try {
    if (data.clear) localStorage.setItem('gridpulse.preferences.v1', JSON.stringify({version:1, disabled:true}));
    else if (data.ready) localStorage.setItem('gridpulse.preferences.v1', JSON.stringify(data.saved));
  } catch (_) { setStateValue('failed', true); }
}
''')


def received():
    ss = st.session_state
    message = ss['_memory_read'].loaded
    if not isinstance(message, dict) or ss.get('memory_ready'):
        return
    ss.memory_ready = True
    ss.memory_available = message.get('ok') is True
    if ss.memory_available:
        saved = message.get('saved')
        ss.memory_disabled = isinstance(saved, dict) and saved.get('version') == VERSION and saved.get('disabled') is True
        if not ss.memory_disabled:
            restore(ss, saved)


def read():
    _reader(key='_memory_read', data={'ready': st.session_state.get('memory_ready', False)},
            height=0, on_loaded_change=received)


def failed():
    st.session_state.memory_available = False


def write():
    ss = st.session_state
    _writer(key='_memory_write', data={'ready': ss.get('memory_ready', False),
                                      'clear': ss.get('memory_disabled', False), 'saved': snapshot(ss)},
            height=0, on_failed_change=failed)


def forget():
    ss = st.session_state
    for key in ('saved_replay', 'dtm_saved', 'home_pins', 'radar_preferences', 'dtm_followed'):
        ss.pop(key, None)
    ss.memory_disabled = True


def settings():
    ss = st.session_state
    with st.expander('Saved on this browser', key='browser-memory-settings'):
        st.caption('Your pinned weekends, last replay, followed drivers and radar settings stay on this browser. '
                   'No login or server-side profile. Results remain hidden when you return; explicit links take priority. '
                   'Other devices and private browsing have separate storage. Multiple tabs use the latest saved selection.')
        if ss.get('memory_disabled'):
            st.info('Browser memory is off. Your previous saved selections have been removed.')
            st.button('Remember future selections', key='memory-enable', on_click=lambda: ss.update(memory_disabled=False))
        elif ss.get('memory_available') is False:
            st.info('Browser storage is unavailable. Selections still work for this session.')
        st.button('Forget saved selections on this browser', key='memory-forget', on_click=forget)
