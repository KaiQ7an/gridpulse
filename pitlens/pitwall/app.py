"""PitLens pit wall: replay any race lap by lap, the way a strategy desk sees it.

Run with `pitlens pitwall` (or `streamlit run pitlens/pitwall/app.py`).
"""

import time

import pandas as pd
import streamlit as st

from pitlens import snapshots
from pitlens.pitwall import (
    about_page,
    charts,
    circuits_page,
    drivers_page,
    onboard_page,
    quali_page,
    season_page,
    teams_page,
    ui,
    views,
)
from pitlens.pitwall.data import FIRST_SEASON, RaceData, completed_races, lap_clock, load_race
from pitlens.pitwall.events import fastest_lap_candidates, fastest_sectors, neutralised_banner, situation
from pitlens.pitwall.navigation import driver_codes, integer, replay_params, select_season, url
from pitlens.pitwall.timeline import event_timeline, known_events
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


def cached_race(year: int, round_number: int, kind: str = "R") -> RaceData:
    return _cached_race(year, round_number, kind, snapshots.revision(year))


@st.cache_resource(show_spinner=False, max_entries=6)
def _cached_race(year: int, round_number: int, kind: str, revision: tuple) -> RaceData:
    return load_race(year, round_number, kind)


def apply_link() -> None:
    """Open the race a link names (?year=2026&round=15, &session=sprint), once per link."""
    ss = st.session_state
    params = st.query_params
    wanted = tuple(sorted(dict(params).items()))
    if not params.get("year") or ss.get("link_applied") == wanted:
        return
    ss.link_applied = wanted
    try:
        year = int(params["year"])
        round_number = int(params["round"]) if params.get("round") else None
    except ValueError:
        return
    if FIRST_SEASON <= year <= pd.Timestamp.now().year:
        ss.race_year = year
        if round_number:
            ss.race_pick = round_number
        ss.race_session = "Sprint" if params.get("session") == "sprint" else "Race"
        ss.no_spoilers = params.get("mode") == "replay"
        ss.pending_replay = dict(params)


def choose_race() -> tuple[int, int, str]:
    ss = st.session_state
    apply_link()
    this_year = pd.Timestamp.now().year
    year = select_season(range(this_year, FIRST_SEASON - 1, -1), key="race_year")
    races = cached_races(year)
    if races.empty:
        st.info(f"No {year} races have finished yet. Pick an earlier season.")
        st.stop()
    rounds = races["RoundNumber"].astype(int).tolist()
    labels = {int(r.RoundNumber): f"R{r.RoundNumber} · {r.EventName}" for r in races.itertuples()}
    if ss.get("race_pick") not in rounds:
        ss.race_pick = rounds[-1]  # the latest race
    round_number = st.sidebar.selectbox("Grand Prix", rounds, format_func=labels.get, key="race_pick")
    kind = "R"
    if "sprint" in str(races.set_index("RoundNumber").loc[round_number, "EventFormat"]):
        ss.setdefault("race_session", "Race")  # set here, not as a default, since a link may set it too
        session = st.sidebar.segmented_control("Session", ["Race", "Sprint"], key="race_session", required=True)
        kind = "S" if session == "Sprint" else "R"
    ss.selected_race = (year, round_number, kind)
    return year, round_number, kind


def restore_replay() -> None:
    """Keep a non-widget copy: Streamlit removes widgets when another page opens."""
    ss = st.session_state
    saved = ss.get("saved_replay", {})
    if not saved or "lap" in ss:
        return
    for key, value in saved.items():
        if key not in ss:
            ss[key] = value
    ss.playing = False


def remember_replay() -> None:
    ss = st.session_state
    keys = ("race_year", "race_pick", "race_session", "no_spoilers", "lap", "focus", "view", "speed")
    ss.saved_replay = {key: ss[key] for key in keys if key in ss}


def reset_for_new_race(key, race: RaceData) -> None:
    """Start an analysis at the flag, or a spoiler-free replay at the start."""
    ss = st.session_state
    # Widget state is dropped while another page is open, so also reset if it's gone.
    mode = ss.get("no_spoilers", False)
    if ss.get("race_key") != key or ss.get("replay_mode") != mode or "lap" not in ss or "focus" not in ss:
        ss.race_key = key
        ss.replay_mode = mode
        ss.lap = 1 if mode else race.total_laps
        ss.playing = False
        ss.focus = starting_order(race)[:3] if mode else race.finish_order[:3]
        ss.pop("goto_lap", None)
        ss.pop("window_actual", None)
    pending = ss.pop("pending_replay", {})
    if integer(pending.get("year")) == race.year and integer(pending.get("round")) == race.round_number:
        if "lap" in pending:
            ss.lap = min(max(integer(pending["lap"], ss.lap), 1), race.total_laps)
        if "drivers" in pending:
            ss.focus = [d for d in driver_codes(pending["drivers"]) if d in set(race.entrants["Driver"])]
        if pending.get("view") in VIEWS:
            ss.view = pending["view"]


def starting_order(race: RaceData) -> list[str]:
    results = race.results
    if "GridPosition" in results:
        grid = pd.to_numeric(results["GridPosition"], errors="coerce")
        results = results.assign(_grid=grid.where(grid > 0).fillna(999))
        results = results.sort_values(["_grid", "Abbreviation"], kind="stable")
        return [d for d in results["Abbreviation"] if d in set(race.entrants["Driver"])]
    return race.entrants["Driver"].sort_values().tolist()


def sync_replay_link(race: RaceData) -> None:
    ss = st.session_state
    params = replay_params(race.year, race.round_number, "S" if race.session_name == "Sprint" else "R",
                           lap=ss.lap, focus=ss.focus, view=ss.view, no_spoilers=ss.no_spoilers)
    if dict(st.query_params) != params:
        st.query_params.from_dict(params)
    ss.link_applied = tuple(sorted(params.items()))
    remember_replay()


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
    ui.strip(stats)
    ui.strip(ui.sector_stats(fastest_sectors(laps, top=3), race.team_colors))
    if weather is not None:
        details = [
            ui.stat("Track temp", f"{weather['TrackTemp']:.1f}°"),
            ui.stat("Air temp", f"{weather['AirTemp']:.1f}°"),
            rain_stat(race, lap, bool(weather["Rainfall"])),
        ]
        with st.expander("Weather"):
            ui.strip(details)


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
    pending = ss.pop("timeline_jump", None)
    if pending and pending[0] == ss.race_key:
        ss.lap = pending[1]
        ss.notes = []
        ss.shown_lap = None
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
    with st.container(border=True, key="card-event-timeline"):
        events = known_events(race.events, lap, ss.no_spoilers)
        action = event_timeline(events, lap, race.total_laps, ss.no_spoilers, key=f"timeline-{ss.race_key}")
        allowed = {(e["event"], e["lap"]) for e in events}
        if isinstance(action, dict) and action.get("id") and action["id"] != ss.get("timeline_click") \
                and (action.get("event"), action.get("lap")) in allowed:
            ss.timeline_click = action["id"]
            ss.timeline_jump = (ss.race_key, action["lap"])
            ss.playing = False
            st.rerun()

    left, right = st.columns([6, 7], gap="large")
    with left, st.container(border=True, key="card-tower"):
        ui.label("Timing")
        # Rows slide and gaps count over most of the tick, so motion is continuous while playing.
        move_ms = int(interval * 1000 * 0.85) if ss.playing else 450
        on_radio = set(race.radio.loc[race.radio["Lap"] == lap, "Driver"])
        banner = neutralised_banner(race.lap_status, lap)
        clicked = tower_component(tower, race.team_colors, lap, move_ms, on_radio, focus, banner,
                                  places_gained(race, tower, lap), year=race.year)
        if isinstance(clicked, dict) and clicked.get("driver") in set(race.entrants["Driver"]) \
                and clicked.get("id") != ss.get("tower_click"):
            ss.tower_click = clicked.get("id")
            ss.playing = False
            remember_replay()
            st.switch_page(about_page.pages["Drivers"],
                           query_params={"year": str(race.year), "driver": clicked["driver"]})

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
                                    width="stretch", wrap=True)
        if view == "Gaps":
            ui.note("Seconds behind the leader at the end of each lap. Flat lines hold the gap, dips are pit "
                    "stops, shaded laps ran under safety car or VSC.")
            gaps = race.gaps[race.gaps["LapNumber"] <= lap]
            fig = charts.gap_chart(gaps, focus, race.team_colors, race.total_laps)
            st.plotly_chart(charts.shade_periods(fig, periods, lap), width="stretch", key="chart_trace")
        elif view == "Positions":
            ui.note("Running order at the end of each lap.")
            fig = charts.position_chart(laps, focus, race.team_colors, race.total_laps)
            st.plotly_chart(charts.shade_periods(fig, periods, lap), width="stretch", key="chart_positions")
        elif view == "Tyres":
            views.tyres_view(race, laps, tower, lap, focus)
        elif view == "Pit stops":
            views.pits_view(race, lap, focus)
        elif view == "Strategy":
            views.strategy_view(race, tower, lap, focus)
        elif view == "Pace":
            ui.note("Representative laps only: no pit laps, safety cars or yellow flags.")
            if focus:
                clean = race.clean_through(lap)
                st.plotly_chart(charts.pace_chart(clean, focus, race.total_laps), width="stretch", key="chart_pace")
        elif view == "Radio":
            views.radio_view(race, lap, focus)
        else:
            views.messages_view(race, lap)

    with right, st.container(border=True, key="card-feed"):
        ui.label("Race feed")
        feed = with_radio(race.events, race.radio, lap).iloc[::-1]
        ui.race_feed(situation(tower, lap, race.total_laps), feed, lap)
    sync_replay_link(race)


def places_gained(race: RaceData, tower: pd.DataFrame, lap: int) -> dict[str, int]:
    """Places each running car gained (+) or lost (-) on this lap; on lap 1, against the grid."""
    if lap > 1:
        before = timing_tower(race.laps, lap - 1, race.retired, race.entrants, stops=race.stops)
        before = dict(zip(before.loc[~before["Out"], "Driver"], before.loc[~before["Out"], "Pos"]))
    elif "GridPosition" in race.results:  # F1's archive has the grid; OpenF1's results don't
        grid = race.results.set_index("Abbreviation")["GridPosition"]
        before = {d: int(g) for d, g in grid.items() if pd.notna(g) and g > 0}  # 0: started from the pit lane
    else:
        return {}
    return {r.Driver: int(before[r.Driver] - r.Pos) for r in tower.itertuples() if not r.Out and r.Driver in before}


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
    restore_replay()
    ss.setdefault("playing", False)
    ss.setdefault("speed", "2×")
    ss.setdefault("view", VIEWS[0])

    ui.sidebar_brand("Race replay, lap by lap")
    year, round_number, kind = choose_race()
    st.sidebar.toggle("No spoilers", key="no_spoilers",
                      help="Start on lap 1, focus on the starting grid and hide future pit-stop overlays")
    with st.spinner("Loading race data. The first load of a race takes up to a minute; after that it's cached."):
        try:
            race = cached_race(year, round_number, kind)
        except TimingUnavailable as exc:
            st.warning(str(exc), icon=":material/cloud_off:")
            st.stop()
        except Exception as exc:  # FastF1 raises a variety of errors for missing data
            st.error(f"Couldn't load this race: {exc}")
            st.stop()

    reset_for_new_race((year, round_number, kind), race)
    options = starting_order(race) if ss.no_spoilers else ui.driver_order(race.entrants, race.finish_order)
    st.sidebar.multiselect("Focus drivers", options, key="focus", max_selections=6,
                           help="Highlighted in the tower and drawn in team colours on the charts")
    ui.team_colored_picker("Focus drivers", options, race.team_colors, dict(zip(race.entrants["Driver"], race.entrants["Team"])))
    if len(ss.focus) == 2:
        st.sidebar.link_button("Compare these drivers", url("onboard", year=year, round=round_number,
                                                         session=kind, drivers=",".join(ss.focus)),
                               icon=":material/compare_arrows:")
    ui.sidebar_footer()

    sprint = race.session_name == "Sprint"
    day = race.start_utc if race.start_utc is not None else race.date
    ui.header(
        f"{race.year} · Round {race.round_number} · {race.location}" + (" · Sprint" if sprint else ""),
        race.event_name + (" Sprint" if sprint else ""),
        f"{day:%-d %B %Y} · {race.total_laps} laps · data: {race.source} · press Play to replay it lap by lap",
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
        st.Page(quali_page.render, title="Qualifying", icon=":material/timer:", url_path="qualifying"),
        st.Page(onboard_page.render, title="Onboard", icon=":material/speed:", url_path="onboard"),
        st.Page(season_page.render, title="Season", icon=":material/emoji_events:", url_path="season"),
        st.Page(teams_page.render, title="Teams", icon=":material/groups:", url_path="teams"),
        st.Page(drivers_page.render, title="Drivers", icon=":material/sports_motorsports:", url_path="drivers"),
        st.Page(circuits_page.render, title="Circuits", icon=":material/route:", url_path="circuits"),
        st.Page(about_page.render, title="About", icon=":material/info:", url_path="about"),
    ]
    about_page.pages = {page.title: page for page in pages}
    st.navigation(pages, position="top").run()


if __name__ == "__main__":
    main()
