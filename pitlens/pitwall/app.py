"""PitLens pit wall: replay any race lap by lap, the way a strategy desk sees it.

Run with `pitlens pitwall` (or `streamlit run pitlens/pitwall/app.py`).
"""

import time

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, onboard_page, ui, views
from pitlens.pitwall.data import FIRST_SEASON, RaceData, completed_races, lap_clock, load_race
from pitlens.pitwall.events import fastest_lap_candidates, fastest_sectors, neutralised_banner, situation
from pitlens.pitwall.timing import format_lap_time, neutralised_periods, timing_tower
from pitlens.pitwall.tower import timing_tower as tower_component
from pitlens.radio import transcribe, translate
from pitlens.session import TimingUnavailable
from pitlens.sources.weather import rain_at

SPEEDS = {"1×": 2.0, "2×": 1.0, "4×": 0.5}  # seconds per lap
VIEWS = ["Gaps", "Positions", "Tyres", "Pit stops", "Strategy", "Pace", "Radio", "Messages"]


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

    def jump():
        if ss.get("goto_lap"):
            ss.lap = int(min(max(ss.goto_lap, 1), total_laps))
            ss.goto_lap = None  # clear the box so the slider stays the source of truth

    with st.container(horizontal=True, vertical_alignment="center", key="controls", gap="medium"):
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
        st.number_input("Go to lap", 1, total_laps, value=None, step=1, key="goto_lap", on_change=jump,
                        placeholder="Lap…", label_visibility="collapsed", width=96, disabled=ss.playing,
                        help="Type a lap number and press Enter")
        st.slider("Lap", 1, total_laps, key="lap", disabled=ss.playing, label_visibility="collapsed", width="stretch")


def status_strip(race: RaceData, laps: pd.DataFrame, tower: pd.DataFrame, lap: int) -> None:
    leader = tower.loc[0, "Driver"]
    status = race.lap_status.get(lap, "Unknown")
    lead_time = race.lead_times.get(lap)
    weather = weather_at(race, lead_time) if lead_time is not None else None

    timed = fastest_lap_candidates(laps)
    fastest = timed.loc[timed["LapTime"].idxmin()] if not timed.empty else None

    stats = [
        ui.stat("Lap", f"{lap}", small=f"/ {race.total_laps}"),
        ui.stat("Leader", "", value_html=ui.driver_dot(race.team_colors.get(leader, "#999")) + leader),
        ui.stat("Track", "", value_html=ui.status_pill(status)),
        ui.stat(
            "Fastest lap", "–" if fastest is None else "",
            value_html=None if fastest is None else
            ui.driver_dot(race.team_colors.get(fastest["Driver"], "#999")) + fastest["Driver"]
            + f' <span style="color:#A855F7">{format_lap_time(fastest["LapTime"])}</span>',
            small=f"L{int(fastest['LapNumber'])}" if fastest is not None else "",
        ),
    ]
    stats += ui.sector_stats(fastest_sectors(laps, top=3), race.team_colors)
    if weather is not None:
        stats += [
            ui.stat("Track temp", f"{weather['TrackTemp']:.1f}°"),
            ui.stat("Air temp", f"{weather['AirTemp']:.1f}°"),
            rain_stat(race, lap, bool(weather["Rainfall"])),
        ]
    ui.strip(stats)


def rain_stat(race: RaceData, lap: int, track_wet: bool) -> str:
    """Rainfall in mm/h this hour (a weather-model estimate), with the track's own wet/dry sensor below."""
    mm = rain_at(race.rain_mm, lap_clock(race, lap))
    sensor = "track wet" if track_wet else "track dry"
    if mm is None:
        return ui.stat("Rain", "Wet" if track_wet else "Dry")
    return ui.stat("Rain", f"{mm:.1f} mm/h", small=sensor,
                   tip="Rainfall this hour around the circuit, estimated by a weather model (Open-Meteo). "
                       "F1's own feed only reports whether the track sensor detects rain.")


NOTE_SECONDS = 3.9


def notify(race: RaceData, lap: int) -> None:
    """Pop up fastest laps, retirements, race control and the winner as the replay moves forward a lap at a time."""
    ss = st.session_state
    now = time.monotonic()
    notes = [n for n in ss.get("notes", []) if n["until"] > now and n["race"] == ss.race_key]
    if ss.get("shown_lap") == lap - 1:
        team_of = dict(zip(race.entrants["Driver"], race.entrants["Team"]))
        for e in race.events[(race.events["Lap"] == lap) & race.events["Kind"].isin(["FL", "OUT", "SC", "GREEN"])].itertuples():
            if e.Kind in ("SC", "GREEN"):  # race control: safety car, VSC, red flag, back to green
                kind = "RED" if e.Text == "Red flag" else e.Kind
                name = "Green flag" if e.Kind == "GREEN" else e.Text
                note = {"kind": kind, "name": name, "team": "Racing resumes" if e.Kind == "GREEN" else "Deployed",
                        "color": {"SC": "#F5B700", "RED": "#E10600", "GREEN": "#16A34A"}[kind]}
            else:
                note = {"kind": e.Kind, "name": race.last_names.get(e.Driver) or e.Driver,
                        "team": team_of.get(e.Driver, ""), "color": race.team_colors.get(e.Driver, "#888")}
            note["right"] = e.Text.partition(", ")[2] if e.Kind == "FL" else f"LAP {lap}"
            notes.insert(0, {**note, "until": now + NOTE_SECONDS, "race": ss.race_key})
        if lap == race.total_laps:  # the chequered flag: who won
            won = race.events[(race.events["Lap"] == lap) & race.events["Text"].str.contains(r" wins( by |$)")]
            if not won.empty:
                d = won.iloc[0]["Driver"]
                notes.insert(0, {"kind": "WIN", "name": race.last_names.get(d) or d, "team": team_of.get(d, ""),
                                 "color": race.team_colors.get(d, "#888"), "right": "P1",
                                 "until": now + NOTE_SECONDS, "race": ss.race_key})
    ss.notes = notes[:3]
    ss.shown_lap = lap
    if ss.notes:
        ui.notifications(ss.notes)


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
    notify(race, lap)

    laps = race.laps[race.laps["LapNumber"] <= lap]
    periods = neutralised_periods(laps)
    tower = timing_tower(race.laps, lap, race.retired, race.entrants, stops=race.stops)
    status_strip(race, laps, tower, lap)

    left, right = st.columns([6, 7], gap="large")
    with left, st.container(border=True, key="card-tower"):
        ui.label("Timing")
        # Rows slide and gaps count over most of the tick, so motion is continuous while playing.
        move_ms = int(interval * 1000 * 0.85) if ss.playing else 450
        on_radio = set(race.radio.loc[race.radio["Lap"] == lap, "Driver"])
        banner = neutralised_banner(race.lap_status, lap)
        tower_component(tower, race.team_colors, lap, move_ms, on_radio, focus, banner)

    if race.track:
        with left, st.container(border=True, key="card-map"):
            ui.label(f"Circuit · {race.location}")
            map_col, list_col = st.columns([3, 2], gap="small")
            with map_col:
                st.plotly_chart(charts.circuit_map(race.track), width="stretch", key="chart_circuit",
                                config={"displayModeBar": False, "staticPlot": True})
            with list_col:
                ui.sector_list(fastest_sectors(laps, top=2), race.team_colors)

    with right, st.container(border=True, key="card-views"):
        # Only the chosen view is drawn each tick (tabs would redraw all of them).
        view = st.segmented_control("View", VIEWS, key="view", required=True, label_visibility="collapsed",
                                    width="stretch", wrap=False)
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
            views.tyres_view(race, laps, tower, lap, focus)
        elif view == "Pit stops":
            views.pits_view(race, lap, focus)
        elif view == "Strategy":
            views.strategy_view(race, tower, lap, focus)
        elif view == "Pace":
            ui.note("Representative laps only: no pit laps, safety cars or yellow flags.")
            if focus:
                clean = race.clean_laps[race.clean_laps["LapNumber"] <= lap]
                st.plotly_chart(charts.pace_chart(clean, focus, race.total_laps), width="stretch", key="chart_pace")
        elif view == "Radio":
            views.radio_view(race, lap, focus)
        else:
            views.messages_view(race, lap)

    with right, st.container(border=True, key="card-feed"):
        ui.label("Race feed")
        feed = with_radio(race.events, race.radio, lap).iloc[::-1]
        ui.race_feed(situation(tower, lap, race.total_laps), feed, lap)


def with_radio(events: pd.DataFrame, radio: pd.DataFrame, lap: int) -> pd.DataFrame:
    """Race events up to `lap`, plus any team radio that has been transcribed, in lap order."""
    rows = []
    for c in radio[radio["Lap"].notna() & (radio["Lap"] <= lap)].itertuples():
        text = (transcribe.cached(c.Url) or {}).get("text")
        if text and st.session_state.get("radio_zh"):
            text = translate.cached(c.Url) or text
        if text:
            short = text if len(text) <= 90 else text[:87].rsplit(" ", 1)[0] + "..."
            rows.append({"Lap": int(c.Lap), "Kind": "RADIO", "Driver": c.Driver, "Text": f"{c.Driver}: “{short}”"})
    feed = pd.concat([events[events["Lap"] <= lap], pd.DataFrame(rows)], ignore_index=True)
    return feed.sort_values("Lap", kind="stable")


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
        except TimingUnavailable as exc:
            st.warning(str(exc), icon=":material/cloud_off:")
            st.stop()
        except Exception as exc:  # FastF1 raises a variety of errors for missing data
            st.error(f"Couldn't load this race: {exc}")
            st.stop()

    reset_for_new_race((year, round_number), race)
    options = ui.driver_order(race.entrants, race.finish_order)
    st.sidebar.multiselect("Focus drivers", options, key="focus", max_selections=6,
                           help="Highlighted in the tower and drawn in team colours on the charts")
    ui.team_colored_picker("Focus drivers", options, race.team_colors, dict(zip(race.entrants["Driver"], race.entrants["Team"])))
    ui.sidebar_footer()

    ui.header(
        f"{race.year} · Round {race.round_number} · {race.location}",
        race.event_name,
        f"{race.date:%-d %B %Y} · {race.total_laps} laps · data: {race.source} · press Play to replay it lap by lap",
    )
    if race.coverage is not None and race.coverage < 0.95:
        st.warning(f"{race.source} is missing about {1 - race.coverage:.0%} of this race's laps, so the replay has "
                   "gaps: on those laps cars can look out of order or a lap down.", icon=":material/warning:")
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
