"""PitLens pit wall: replay any race lap by lap, the way a strategy desk sees it.

Run with `pitlens pitwall` (or `streamlit run pitlens/pitwall/app.py`).
"""

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts
from pitlens.pitwall.data import FIRST_SEASON, RaceData, completed_races, load_race
from pitlens.pitwall.timing import gap_to_leader, leader_times, stint_timeline, timing_tower, track_status
from pitlens.stints.pace import stint_degradation
from pitlens.style import COMPOUND_COLORS

SPEEDS = {"Slow · 2 s per lap": 2.0, "Normal · 1 s per lap": 1.0, "Fast · 0.4 s per lap": 0.4}
DARK_TEXT_COMPOUNDS = {"MEDIUM", "HARD", "UNKNOWN"}


@st.cache_data(ttl=3600, show_spinner=False)
def cached_races(year: int) -> pd.DataFrame:
    return completed_races(year)


@st.cache_resource(show_spinner=False, max_entries=6)
def cached_race(year: int, round_number: int) -> RaceData:
    return load_race(year, round_number)


def choose_race() -> tuple[int, int]:
    st.sidebar.title("PitLens")
    st.sidebar.caption("Pit wall · race replay")
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
    if ss.get("race_key") != key:
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


def style_tower(tower: pd.DataFrame, colors: dict[str, str]):
    view = pd.DataFrame(
        {
            "": "",
            "Pos": tower["Pos"],
            "Driver": tower["Driver"],
            "Gap": tower["Gap"],
            "Int": tower["Interval"],
            "Last lap": tower["LastLap"],
            "Tyre": [
                "PIT" if pit else f"{c[0]} {'' if pd.isna(a) else a}".strip()
                for c, a, pit in zip(tower["Compound"], tower["TyreAge"], tower["Pit"])
            ],
            "Stops": tower["Stops"],
        }
    )

    def team_bar(col):
        return [f"background-color: {colors.get(d, '#999')}" for d in tower["Driver"]]

    def tyre_cell(col):
        out = []
        for c in tower["Compound"]:
            text = "#111" if c in DARK_TEXT_COMPOUNDS else "#fff"
            out.append(f"background-color: {COMPOUND_COLORS.get(c, '#999')}; color: {text}; font-weight: 600")
        return out

    return view.style.apply(team_bar, subset=[""]).apply(tyre_cell, subset=["Tyre"])


def weather_at(race: RaceData, time) -> pd.Series | None:
    w = race.weather[race.weather["Time"] <= time]
    return w.iloc[-1] if not w.empty else None


def race_view(race: RaceData) -> None:
    ss = st.session_state
    if ss.playing:
        ss.lap = min(ss.lap + 1, race.total_laps)
        if ss.lap >= race.total_laps:
            ss.playing = False
            st.rerun()  # full rerun so the timer stops and the button reads "Play"

    lap = st.slider("Lap", 1, race.total_laps, key="lap", disabled=ss.playing)
    focus = ss.focus

    laps = race.laps[race.laps["LapNumber"] <= lap]
    tower = timing_tower(race.laps, lap, race.retired)
    lead_time = leader_times(race.laps).get(lap)
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
        st.dataframe(
            style_tower(tower, race.team_colors),
            hide_index=True,
            width="stretch",
            height=36 * len(tower) + 40,
            column_config={
                "": st.column_config.TextColumn(width=6),
                "Pos": st.column_config.NumberColumn(width=36),
                "Driver": st.column_config.TextColumn(width=50),
                "Gap": st.column_config.TextColumn(width=70),
                "Int": st.column_config.TextColumn(width=62),
                "Last lap": st.column_config.TextColumn(width=72),
                "Tyre": st.column_config.TextColumn(width=48),
                "Stops": st.column_config.NumberColumn(width=44),
            },
        )

    with right:
        trace, positions, tyres, pace, control = st.tabs(["Race trace", "Positions", "Tyres", "Pace", "Race control"])
        with trace:
            st.caption("Seconds behind the leader at the end of each lap. Flat lines hold the gap; dips are pit stops.")
            st.plotly_chart(charts.gap_chart(gap_to_leader(laps), focus, race.team_colors, race.total_laps), width="stretch")
        with positions:
            st.plotly_chart(charts.position_chart(laps, focus, race.team_colors, race.total_laps), width="stretch")
        with tyres:
            st.caption("Tyre stints in the current running order.")
            st.plotly_chart(
                charts.strategy_chart(stint_timeline(laps), tower["Driver"].tolist(), race.total_laps),
                width="stretch",
            )
            clean = race.clean_laps[(race.clean_laps["LapNumber"] <= lap) & race.clean_laps["Driver"].isin(focus)]
            deg = stint_degradation(clean)
            st.markdown("**Degradation of the focus drivers so far**")
            if deg.empty:
                st.caption("Not enough clean laps yet (a stint needs five green-flag laps).")
            else:
                st.plotly_chart(charts.degradation_chart(deg), width="stretch")
                with st.expander("Table"):
                    st.dataframe(deg, hide_index=True, width="stretch")
        with pace:
            clean = race.clean_laps[race.clean_laps["LapNumber"] <= lap]
            if focus:
                st.caption("Representative laps only: no pit laps, safety cars or yellow flags.")
                st.plotly_chart(charts.pace_chart(clean, focus, race.total_laps), width="stretch")
        with control:
            msgs = race.messages[race.messages["Lap"].fillna(0) <= lap]
            if not st.checkbox("Show blue flags", value=False):
                msgs = msgs[msgs["Flag"] != "BLUE"]
            msgs = msgs.sort_values("Time", ascending=False)[["Lap", "Category", "Flag", "Message"]]
            st.dataframe(msgs, hide_index=True, width="stretch", height=420)


def main() -> None:
    st.set_page_config(page_title="PitLens · Pit wall", page_icon="🏁", layout="wide")
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

    st.fragment(race_view, run_every=interval if st.session_state.playing else None)(race)


if __name__ == "__main__":
    main()
