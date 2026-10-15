"""PitLens pit wall: replay any race lap by lap, the way a strategy desk sees it.

Run with `pitlens pitwall` (or `streamlit run pitlens/pitwall/app.py`).
"""

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, onboard_page
from pitlens.pitwall.data import FIRST_SEASON, RaceData, completed_races, load_race
from pitlens.pitwall.timing import neutralised_periods, stint_timeline, timing_tower, track_status
from pitlens.pitwall.tower import timing_tower as tower_component
from pitlens.stints.pace import stint_degradation

SPEEDS = {"Slow · 2 s per lap": 2.0, "Normal · 1 s per lap": 1.0, "Fast · 0.5 s per lap": 0.5}
VIEWS = ["Race trace", "Positions", "Tyres", "Pace", "Race control"]

# Streamlit dims elements while a rerun is in flight; during a replay that is
# every tick, which reads as stutter. Keep them at full opacity instead.
NO_STALE_FADE = """<style>
[data-stale="true"], .stale-element { opacity: 1 !important; transition: none !important; }
</style>"""


@st.cache_data(ttl=3600, show_spinner=False)
def cached_races(year: int) -> pd.DataFrame:
    return completed_races(year)


@st.cache_resource(show_spinner=False, max_entries=6)
def cached_race(year: int, round_number: int) -> RaceData:
    return load_race(year, round_number)


def choose_race() -> tuple[int, int]:
    st.sidebar.title("PitLens")
    st.sidebar.caption("Race replay · lap by lap")
    this_year = pd.Timestamp.now().year
    year = st.sidebar.selectbox("Season", range(this_year, FIRST_SEASON - 1, -1))
    races = cached_races(year)
    if races.empty:
        st.info(f"No {year} races have finished yet. Pick an earlier season.")
        st.stop()
    labels = [f"R{r.RoundNumber} · {r.EventName}" for r in races.itertuples()]
    i = st.sidebar.selectbox("Race", range(len(races)), index=len(races) - 1, format_func=lambda i: labels[i])
    return year, int(races.loc[i, "RoundNumber"])


def reset_for_new_race(key, race: RaceData) -> None:
    """Jump to the final lap and focus on the podium whenever the race changes."""
    ss = st.session_state
    # Widget state is dropped while another page is open, so also reset if it's gone.
    if ss.get("race_key") != key or "lap" not in ss or "focus" not in ss:
        ss.race_key = key
        ss.lap = race.total_laps
        ss.playing = False
        ss.focus = race.finish_order[:3]


def replay_controls(total_laps: int) -> float:
    ss = st.session_state

    def toggle_play():
        if not ss.playing and ss.lap >= total_laps:
            ss.lap = 1
        ss.playing = not ss.playing

    def restart():
        ss.lap, ss.playing = 1, False

    st.sidebar.subheader("Replay")
    left, right = st.sidebar.columns(2)
    left.button("⏮ Lap 1", on_click=restart, width="stretch")
    right.button("⏸ Pause" if ss.playing else "▶ Play", on_click=toggle_play, width="stretch", type="primary")
    speed = st.sidebar.selectbox("Speed", list(SPEEDS), index=1)
    return SPEEDS[speed]


def weather_at(race: RaceData, time) -> pd.Series | None:
    w = race.weather[race.weather["Time"] <= time]
    return w.iloc[-1] if not w.empty else None


def race_view(race: RaceData, interval: float | None) -> None:
    ss = st.session_state
    if ss.playing:
        ss.lap = min(ss.lap + 1, race.total_laps)
        if ss.lap >= race.total_laps:
            ss.playing = False
            st.rerun()  # full rerun so the timer stops and the button reads "Play"

    lap = st.slider("Lap", 1, race.total_laps, key="lap", disabled=ss.playing)
    focus = ss.focus

    laps = race.laps[race.laps["LapNumber"] <= lap]
    periods = neutralised_periods(laps)
    tower = timing_tower(race.laps, lap, race.retired)
    lead_time = race.lead_times.get(lap)
    leader_lap = laps[(laps["Driver"] == tower.loc[0, "Driver"]) & (laps["LapNumber"] == lap)]
    status = track_status(leader_lap["TrackStatus"].iloc[0]) if not leader_lap.empty else "Unknown"
    weather = weather_at(race, lead_time) if lead_time is not None else None

    m = st.columns(5)
    m[0].metric("Lap", f"{lap} / {race.total_laps}")
    m[1].metric("Leader", tower.loc[0, "Driver"])
    m[2].metric("Track", status)
    m[3].metric("Track temp", f"{weather['TrackTemp']:.1f} °C" if weather is not None else "–")
    m[4].metric("Rain", ("Yes" if weather["Rainfall"] else "No") if weather is not None else "–")

    left, right = st.columns([6, 7], gap="medium")
    with left:
        st.subheader("Timing tower")
        # Rows slide and gaps count over most of the tick, so motion is continuous while playing.
        move_ms = int(interval * 1000 * 0.85) if ss.playing and interval else 450
        tower_component(tower, race.team_colors, lap, move_ms)

    with right:
        # Only the chosen view is drawn each tick (tabs would redraw all five).
        view = st.segmented_control("View", VIEWS, default=VIEWS[0], key="view", label_visibility="collapsed") or VIEWS[0]
        if view == "Race trace":
            st.caption(
                "Seconds behind the leader at the end of each lap. Flat lines hold the gap; dips are pit stops; "
                "shaded laps ran under safety car or VSC."
            )
            gaps = race.gaps[race.gaps["LapNumber"] <= lap]
            fig = charts.gap_chart(gaps, focus, race.team_colors, race.total_laps)
            st.plotly_chart(charts.shade_periods(fig, periods), width="stretch", key="chart_trace")
        elif view == "Positions":
            fig = charts.position_chart(laps, focus, race.team_colors, race.total_laps)
            st.plotly_chart(charts.shade_periods(fig, periods), width="stretch", key="chart_positions")
        elif view == "Tyres":
            st.caption("Tyre stints in the current running order.")
            st.plotly_chart(
                charts.strategy_chart(stint_timeline(laps), tower["Driver"].tolist(), race.total_laps),
                width="stretch",
                key="chart_stints",
            )
            clean = race.clean_laps[(race.clean_laps["LapNumber"] <= lap) & race.clean_laps["Driver"].isin(focus)]
            deg = stint_degradation(clean)
            st.markdown("**Degradation of the focus drivers so far**")
            if deg.empty:
                st.caption("Not enough clean laps yet (a stint needs five green-flag laps).")
            else:
                st.plotly_chart(charts.degradation_chart(deg), width="stretch", key="chart_deg")
                with st.expander("Table"):
                    st.dataframe(deg, hide_index=True, width="stretch")
        elif view == "Pace":
            clean = race.clean_laps[race.clean_laps["LapNumber"] <= lap]
            if focus:
                st.caption("Representative laps only: no pit laps, safety cars or yellow flags.")
                st.plotly_chart(charts.pace_chart(clean, focus, race.total_laps), width="stretch", key="chart_pace")
        else:
            msgs = race.messages[race.messages["Lap"].fillna(0) <= lap]
            if not st.checkbox("Show blue flags", value=False):
                msgs = msgs[msgs["Flag"] != "BLUE"]
            msgs = msgs.sort_values("Time", ascending=False)[["Lap", "Category", "Flag", "Message"]]
            st.dataframe(msgs, hide_index=True, width="stretch", height=420)


def race_page() -> None:
    st.session_state.setdefault("playing", False)

    year, round_number = choose_race()
    with st.spinner("Loading race data. The first load of a race takes up to a minute; after that it's cached."):
        try:
            race = cached_race(year, round_number)
        except Exception as exc:  # FastF1 raises a variety of errors for missing data
            st.error(f"Couldn't load this race: {exc}")
            st.stop()

    reset_for_new_race((year, round_number), race)
    st.sidebar.multiselect("Focus drivers", race.finish_order, key="focus", max_selections=6)
    interval = replay_controls(race.total_laps)
    st.sidebar.divider()
    st.sidebar.caption("Unofficial. Timing data from the public F1 archive via FastF1.")

    st.title(race.name)
    st.caption(f"{race.date:%d %B %Y} · {race.total_laps} laps · press Play to replay the race lap by lap")

    st.fragment(race_view, run_every=interval if st.session_state.playing else None)(race, interval)


def main() -> None:
    st.set_page_config(page_title="PitLens · Pit wall", page_icon="🏁", layout="wide")
    st.markdown(NO_STALE_FADE, unsafe_allow_html=True)
    pages = [
        st.Page(race_page, title="Race replay", icon=":material/sports_score:", default=True),
        st.Page(onboard_page.render, title="Onboard", icon=":material/speed:", url_path="onboard"),
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
