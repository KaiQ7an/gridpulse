"""PitLens pit wall: replay any race lap by lap, the way a strategy desk sees it.

Run with `pitlens pitwall` (or `streamlit run pitlens/pitwall/app.py`).
"""

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, onboard_page, ui
from pitlens.pitwall.data import FIRST_SEASON, RaceData, completed_races, load_race
from pitlens.pitwall.timing import format_lap_time, neutralised_periods, stint_timeline, timing_tower, track_status
from pitlens.pitwall.tower import timing_tower as tower_component
from pitlens.stints.pace import stint_degradation
from pitlens.undercut.analysis import pair_gap, rejoin_projection
from pitlens.undercut.charts import battle_chart, pit_loss_chart

SPEEDS = {"1×": 2.0, "2×": 1.0, "4×": 0.5}  # seconds per lap
VIEWS = ["Gaps", "Positions", "Tyres", "Strategy", "Pace", "Radio", "Messages"]


@st.cache_data(ttl=3600, show_spinner=False)
def cached_races(year: int) -> pd.DataFrame:
    return completed_races(year)


@st.cache_resource(show_spinner=False, max_entries=6)
def cached_race(year: int, round_number: int) -> RaceData:
    return load_race(year, round_number)


def choose_race() -> tuple[int, int]:
    this_year = pd.Timestamp.now().year
    year = st.sidebar.selectbox("Season", range(this_year, FIRST_SEASON - 1, -1), key="race_year")
    races = cached_races(year)
    if races.empty:
        st.info(f"No {year} races have finished yet. Pick an earlier season.")
        st.stop()
    labels = [f"R{r.RoundNumber} · {r.EventName}" for r in races.itertuples()]
    i = st.sidebar.selectbox("Grand Prix", range(len(races)), index=len(races) - 1, format_func=lambda i: labels[i])
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


def weather_at(race: RaceData, time) -> pd.Series | None:
    w = race.weather[race.weather["Time"] <= time]
    return w.iloc[-1] if not w.empty else None


def replay_controls(total_laps: int) -> None:
    """Media-player style bar: restart, play/pause, speed, lap slider."""
    ss = st.session_state

    def toggle_play():
        if not ss.playing and ss.lap >= total_laps:
            ss.lap = 1
        ss.playing = not ss.playing

    def restart():
        ss.lap, ss.playing = 1, False

    with st.container(horizontal=True, vertical_alignment="center", key="controls", gap="small"):
        st.button("Lap 1", icon=":material/skip_previous:", on_click=restart, help="Back to the start")
        st.button(
            "Pause" if ss.playing else "Play",
            icon=":material/pause:" if ss.playing else ":material/play_arrow:",
            on_click=toggle_play,
            type="primary",
            width=104,
        )
        st.segmented_control("Speed", list(SPEEDS), key="speed", required=True, label_visibility="collapsed",
                             help="Replay speed: 1× is two seconds per lap")
        st.slider("Lap", 1, total_laps, key="lap", disabled=ss.playing, label_visibility="collapsed", width="stretch")


def status_strip(race: RaceData, laps: pd.DataFrame, tower: pd.DataFrame, lap: int) -> None:
    leader = tower.loc[0, "Driver"]
    leader_lap = laps[(laps["Driver"] == leader) & (laps["LapNumber"] == lap)]
    status = track_status(leader_lap["TrackStatus"].iloc[0]) if not leader_lap.empty else "Unknown"
    lead_time = race.lead_times.get(lap)
    weather = weather_at(race, lead_time) if lead_time is not None else None

    timed = laps.dropna(subset=["LapTime"])
    if "Deleted" in timed:
        timed = timed[timed["Deleted"] != True]  # noqa: E712 (column holds True/False/NaN)
    fastest = timed.loc[timed["LapTime"].idxmin()] if not timed.empty else None

    stats = [
        ui.stat("Lap", f"{lap}", small=f"/ {race.total_laps}"),
        ui.stat("Leader", "", value_html=ui.driver_dot(race.team_colors.get(leader, "#999")) + leader),
        ui.stat("Track", "", value_html=ui.status_pill(status)),
        ui.stat(
            "Fastest lap",
            f"{fastest['Driver']} {format_lap_time(fastest['LapTime'])}" if fastest is not None else "–",
            small=f"L{int(fastest['LapNumber'])}" if fastest is not None else "",
        ),
    ]
    if weather is not None:
        stats += [
            ui.stat("Track temp", f"{weather['TrackTemp']:.1f}°"),
            ui.stat("Air temp", f"{weather['AirTemp']:.1f}°"),
            ui.stat("Rain", "Wet" if weather["Rainfall"] else "Dry"),
        ]
    ui.strip(stats)


def race_view(race: RaceData) -> None:
    ss = st.session_state
    interval = SPEEDS[ss.speed]
    if ss.get("timer") != (ss.playing, interval):
        st.rerun()  # play/pause or speed changed: rebuild the fragment with the right timer
    if ss.playing:
        ss.lap = min(ss.lap + 1, race.total_laps)
        if ss.lap >= race.total_laps:
            ss.playing = False
            st.rerun()

    replay_controls(race.total_laps)
    lap = ss.lap
    focus = ss.focus

    laps = race.laps[race.laps["LapNumber"] <= lap]
    periods = neutralised_periods(laps)
    tower = timing_tower(race.laps, lap, race.retired)
    status_strip(race, laps, tower, lap)

    left, right = st.columns([5, 7], gap="medium")
    with left, st.container(border=True, key="card-tower"):
        ui.label("Timing")
        # Rows slide and gaps count over most of the tick, so motion is continuous while playing.
        move_ms = int(interval * 1000 * 0.85) if ss.playing else 450
        on_radio = set(race.radio.loc[race.radio["Lap"] == lap, "Driver"])
        tower_component(tower, race.team_colors, lap, move_ms, on_radio, focus)

    with right, st.container(border=True, key="card-views"):
        # Only the chosen view is drawn each tick (tabs would redraw all of them).
        view = st.segmented_control("View", VIEWS, key="view", required=True, label_visibility="collapsed",
                                    width="stretch")
        if view == "Gaps":
            ui.note("Seconds behind the leader at the end of each lap. Flat lines hold the gap, dips are pit "
                    "stops, shaded laps ran under safety car or VSC.")
            gaps = race.gaps[race.gaps["LapNumber"] <= lap]
            fig = charts.gap_chart(gaps, focus, race.team_colors, race.total_laps)
            st.plotly_chart(charts.shade_periods(fig, periods), width="stretch", key="chart_trace")
        elif view == "Positions":
            ui.note("Running order at the end of each lap.")
            fig = charts.position_chart(laps, focus, race.team_colors, race.total_laps)
            st.plotly_chart(charts.shade_periods(fig, periods), width="stretch", key="chart_positions")
        elif view == "Tyres":
            tyres_view(race, laps, tower, lap, focus)
        elif view == "Strategy":
            strategy_view(race, tower, lap, focus)
        elif view == "Pace":
            ui.note("Representative laps only: no pit laps, safety cars or yellow flags.")
            if focus:
                clean = race.clean_laps[race.clean_laps["LapNumber"] <= lap]
                st.plotly_chart(charts.pace_chart(clean, focus, race.total_laps), width="stretch", key="chart_pace")
        elif view == "Radio":
            radio_view(race, lap, focus)
        else:
            messages_view(race, lap)


def tyres_view(race: RaceData, laps: pd.DataFrame, tower: pd.DataFrame, lap: int, focus: list[str]) -> None:
    ui.label("Stints")
    ui.note("Tyre stints in the current running order.")
    st.plotly_chart(
        charts.strategy_chart(stint_timeline(laps), tower["Driver"].tolist(), race.total_laps),
        width="stretch",
        key="chart_stints",
    )
    ui.label("Degradation so far")
    clean = race.clean_laps[(race.clean_laps["LapNumber"] <= lap) & race.clean_laps["Driver"].isin(focus)]
    deg = stint_degradation(clean)
    if deg.empty:
        ui.note("Not enough clean laps yet: a stint needs five green-flag laps.")
    else:
        ui.note("Fuel-corrected seconds lost per lap of tyre age, focus drivers.")
        st.plotly_chart(charts.degradation_chart(deg), width="stretch", key="chart_deg")


def radio_view(race: RaceData, lap: int, focus: list[str]) -> None:
    clips = race.radio[race.radio["Lap"].notna() & (race.radio["Lap"] <= lap)]
    if st.toggle("Focus drivers only", value=False, key="radio_focus"):
        clips = clips[clips["Driver"].isin(focus)]
    ui.note(f"{len(clips)} clips up to lap {lap}, newest first. A red microphone in the timing tower marks a "
            "driver with a clip on the current lap.")
    for clip in clips.sort_values("SessionTime", ascending=False).head(12).itertuples():
        new = ' <span class="pl-pill" style="background:rgba(225,6,0,.14);color:#E10600">this lap</span>' \
            if clip.Lap == lap else ""
        st.html(f'<div style="margin-top:6px">{ui.driver_dot(race.team_colors.get(clip.Driver, "#999"))}'
                f"<b>{clip.Driver}</b> <span style='opacity:.6'>· lap {clip.Lap}</span>{new}</div>")
        st.audio(clip.Url, format="audio/mpeg")


def messages_view(race: RaceData, lap: int) -> None:
    msgs = race.messages[race.messages["Lap"].fillna(0) <= lap]
    if not st.toggle("Show blue flags", value=False, key="blue_flags"):
        msgs = msgs[msgs["Flag"] != "BLUE"]
    msgs = msgs.sort_values("Time", ascending=False)[["Lap", "Category", "Flag", "Message"]]
    st.dataframe(msgs, hide_index=True, width="stretch", height=460,
                 column_config={"Lap": st.column_config.NumberColumn(width=50),
                                "Category": st.column_config.TextColumn(width=90),
                                "Flag": st.column_config.TextColumn(width=80)})


def strategy_view(race: RaceData, tower: pd.DataFrame, lap: int, focus: list[str]) -> None:
    stops = race.stops[race.stops["Lap"] <= lap]
    battles = race.battles[race.battles["RivalStopLap"] + 1 <= lap]
    last = stops.iloc[-1] if not stops.empty else None
    ui.strip([
        ui.stat("Typical pit loss", f"{race.pit_loss:.1f} s" if race.pit_loss else "–"),
        ui.stat("Stops so far", str(len(stops))),
        ui.stat("Latest stop", f"{last['Driver']}" if last is not None else "–",
                small=f"lap {last['Lap']}" if last is not None else ""),
        ui.stat("Battles", str(len(battles))),
    ])

    if race.pit_loss:
        ui.label("If they pit at the end of this lap")
        everyone = st.toggle("All cars on the lead lap", value=False, key="rejoin_all")
        proj = rejoin_projection(tower, race.pit_loss)
        if not everyone:
            proj = proj[proj["Driver"].isin(focus)]
        st.dataframe(
            pd.DataFrame(
                {
                    "Driver": proj["Driver"],
                    "Now": "P" + proj["Now"].astype(str),
                    "Rejoins": "P" + proj["Rejoin"].astype(str),
                    "Behind": [f"{c} by {g:.1f} s" if c else "–" for c, g in zip(proj["CarAhead"], proj["GapAhead"])],
                    "Ahead of": [f"{c} by {g:.1f} s" if c else "–" for c, g in zip(proj["CarBehind"], proj["GapBehind"])],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    ui.label("Undercuts and overcuts so far")
    if battles.empty:
        ui.note("None yet: a battle needs two cars within 3.5 s to pit within six laps of each other.")
    else:
        labels = [f"Lap {b.Lap} · {b.FirstStop} vs {b.Rival} · {b.Verdict}" for b in battles.itertuples()]
        i = st.selectbox("Battle", range(len(battles)), index=len(battles) - 1, format_func=lambda i: labels[i],
                         label_visibility="collapsed")
        battle = battles.iloc[i]
        ui.note(
            f"{battle.FirstStop} pitted on lap {battle.Lap} from {abs(battle.GapBefore):.2f} s "
            f"{'behind' if battle.GapBefore > 0 else 'ahead of'} {battle.Rival}; {battle.Rival} answered on lap "
            f"{battle.RivalStopLap}. Afterwards {battle.FirstStop} was {abs(battle.GapAfter):.2f} s "
            f"{'behind' if battle.GapAfter > 0 else 'ahead'}."
        )
        gap = pair_gap(race.laps, battle.FirstStop, battle.Rival)
        st.plotly_chart(battle_chart(gap, battle, race.total_laps), width="stretch", key="chart_battle")

    if not stops.empty:
        ui.label("What each stop cost")
        st.plotly_chart(pit_loss_chart(stops, race.pit_loss, race.total_laps), width="stretch", key="chart_pitloss")


def race_page() -> None:
    ss = st.session_state
    ss.setdefault("playing", False)
    ss.setdefault("speed", "2×")
    ss.setdefault("view", VIEWS[0])

    ui.sidebar_brand("Race replay, lap by lap")
    year, round_number = choose_race()
    with st.spinner("Loading race data. The first load of a race takes up to a minute; after that it's cached."):
        try:
            race = cached_race(year, round_number)
        except Exception as exc:  # FastF1 raises a variety of errors for missing data
            st.error(f"Couldn't load this race: {exc}")
            st.stop()

    reset_for_new_race((year, round_number), race)
    st.sidebar.multiselect("Focus drivers", race.finish_order, key="focus", max_selections=6,
                           help="Highlighted in the tower and drawn in team colours on the charts")
    ui.sidebar_footer()

    ui.header(
        f"{race.year} · Round {race.round_number} · {race.location}",
        race.event_name,
        f"{race.date:%-d %B %Y} · {race.total_laps} laps · press Play to replay it lap by lap",
    )
    interval = SPEEDS[ss.speed]
    ss.timer = (ss.playing, interval)  # what the fragment's timer is built with
    st.fragment(race_view, run_every=interval if ss.playing else None)(race)


def main() -> None:
    st.set_page_config(page_title="PitLens · Pit wall", page_icon="🏁", layout="wide")
    ui.inject_css()
    pages = [
        st.Page(race_page, title="Race replay", icon=":material/sports_score:", default=True),
        st.Page(onboard_page.render, title="Onboard", icon=":material/speed:", url_path="onboard"),
    ]
    st.navigation(pages, position="top").run()


if __name__ == "__main__":
    main()
