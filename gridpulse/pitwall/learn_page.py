"""A small, skippable lesson: recognise the people, change one decision, explain the trade-off."""

import streamlit as st

from gridpulse.pitwall import about_page, explain, styles, ui
from gridpulse.pitwall.data import load_race
from gridpulse.pitwall.featured import FEATURED
from gridpulse.pitwall.timing import timing_tower
from gridpulse.session import TimingUnavailable

MOMENT = FEATURED[0]


@st.cache_resource(show_spinner=False, max_entries=1)
def lesson_race():
    return load_race(MOMENT.year, MOMENT.round)


def move(step: int):
    st.session_state.learn_step = step


def render():
    styles.inject('learn.css')
    ui.sidebar_brand('A first look at race strategy')
    ui.sidebar_footer()
    st.session_state.playing = False
    step = st.session_state.get('learn_step', 0)
    if step not in (0, 1, 2):
        step = 0
    ui.header('A two-minute race guide · no results revealed', 'Why stop when you are leading?',
              'Meet two drivers. Try one decision. See what you trade away.')
    st.progress((step + 1) / 3, text=f'Step {step + 1} of 3 · ' + ['Meet the drivers', 'Try a different stop', 'What you learned'][step])
    with ui.loading('Opening the guided example', 'Reading a saved race. No live timing request is needed.'):
        try:
            race = lesson_race()
        except (TimingUnavailable, OSError, ValueError):
            st.warning('The saved example could not be opened. You can still browse results or try the replay.')
            st.page_link(about_page.pages['Race replay'], label='Open race replay')
            return
    lap, driver = MOMENT.lap, MOMENT.drivers[0]
    tower = timing_tower(race.laps, lap, race.retired, race.entrants, stops=race.stops)
    if step == 0:
        st.subheader('Hungary 2025 · the end of lap 18')
        st.write(explain.situation(race, tower, lap))
        teams = dict(zip(race.entrants.Driver, race.entrants.Team))
        cols = st.columns(2)
        for col, code in zip(cols, MOMENT.drivers[:2]):
            row = tower[tower.Driver == code].iloc[0]
            with col, st.container(border=True):
                st.markdown(f'**{explain.name(race, code)}** · {teams.get(code, "")}')
                st.write('Leading the race' if code == driver else f'{row.GapSeconds:.1f} seconds behind the leader')
                st.caption(f'{code} is the short code used on timing screens.')
        st.info('A pit stop means leaving the racing track to change tyres. You lose time during the stop; '
                'the fresh tyres may help you go faster afterwards.')
        st.write('Oscar Piastri is pitting. Charles Leclerc has a choice: stop soon too, or keep racing on his current tyres. '
                 'New tyres can offer grip, but stopping too early leaves them more laps to wear out.')
        st.button('Try Leclerc’s decision', key='learn-next', type='primary', on_click=move, args=(1,))
    elif step == 1:
        experiment(race, tower, lap, driver)
        st.button('What should I take away?', key='learn-next', type='primary', on_click=move, args=(2,))
    else:
        st.subheader('A stop trades time now for fresher tyres later')
        tried = st.session_state.get('learn_result')
        if tried and tried['wait'] == 3:
            st.markdown(f'**You tried waiting two more laps: {tried["delta"]:+.1f} seconds versus stopping next lap.**')
        st.write('You compared two stop timings while keeping the driver, replacement tyre and estimated stop loss fixed. '
                 'Waiting keeps the old tyres on for longer, but leaves the new set fewer laps to wear out.')
        st.write('The time difference is a model estimate of that trade-off. '
                 'It does not establish whether Leclerc could beat Piastri: traffic, rival reactions and future safety cars can change the decision.')
        st.info('When you open the full replay, start with the plain-language summary. '
                '“Gap” means time behind the leader. “Interval” means time behind the car immediately ahead.')
        st.page_link(about_page.pages['Race replay'], label='Explore this moment in the full replay',
                     query_params=MOMENT.params, icon=':material/arrow_forward:')
        st.page_link(about_page.pages['DTM'], label='Just want results? Open DTM standings',
                     query_params={'view': 'championship'}, icon=':material/emoji_events:')
        st.button('Start again', on_click=move, args=(0,))
    if step:
        st.button('Back one step', key='learn-back', on_click=move, args=(step - 1,))
    with st.expander('Skip the guide'):
        st.page_link(about_page.pages['Race replay'], label='Open the full workbench', query_params=MOMENT.params)


def experiment(race, tower, lap, driver):
    context = explain.prepare(race, tower, lap)
    best, window = explain.plan(race, tower, lap, driver, context)
    st.subheader('Change just one decision: when to stop')
    if best is None:
        st.info('There is not enough dry-tyre information for this example. The full replay remains available below.')
        return
    compound = best.Compound
    if 'learn_wait' not in st.session_state:
        st.session_state.learn_wait = st.session_state.get('learn_result', {}).get('wait', 1)
    choice = st.segmented_control('Leclerc’s stop', [1, 3], required=True, key='learn_wait',
                                  format_func=lambda k: f'Lap {lap + k} · ' + ('next lap' if k == 1 else 'wait two more laps'))
    result = explain.comparison(window, compound, choice)
    st.caption(f'Both choices fit fresh {compound.lower()} tyres and use the same {context.loss:.1f}-second stop loss. '
               f'Only laps 1–{lap} are used to fit the model.')
    if result is None:
        st.info('That stop is outside the model’s available window.')
        return
    st.session_state.learn_result = {'wait': choice, 'delta': result['delta']}
    if choice == 1:
        st.markdown(f'**Your baseline: stop on lap {lap + 1}.**')
        st.write('Now select “wait two more laps” to see how the estimate changes. The race itself stays paused at lap 18.')
    else:
        delta = result['delta']
        st.metric('Change versus stopping next lap', f'{delta:+.1f} s')
        if abs(delta) < .05:
            st.write('These two timings are effectively equal in this model (less than 0.05 seconds apart).')
        else:
            st.write(f'In this model, waiting two more laps is estimated to be **{abs(delta):.1f} seconds '
                     f'{"quicker" if delta < 0 else "slower"}** over the remaining race, using the same fresh tyre. '
                     'A negative number means less total time.')
        st.write('Why it changes: you spend two more laps on worn tyres, while the replacement set has two fewer laps to wear out. '
                 'The model balances those costs; waiting is not always better.')
    st.caption('One further stop, then that set to the finish. Clear track assumed; no rival response, '
               'future safety car or tyre-stock check. These are scenarios, not the actual result.')
