"""PitLens pit wall: replay any race lap by lap, the way a strategy desk sees it.

Run with `pitlens pitwall` (or `streamlit run pitlens/pitwall/app.py`).
"""

import time

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, onboard_page, ui
from pitlens.session import TimingUnavailable
from pitlens.pitwall.data import FIRST_SEASON, RaceData, completed_races, lap_clock, load_race
from pitlens.sources.weather import rain_at
from pitlens.pitwall.events import fastest_lap_candidates, fastest_sectors, neutralised_banner, situation
from pitlens.pitwall.timing import format_lap_time, neutralised_periods, stint_timeline, timing_tower
from pitlens.pitwall.tower import timing_tower as tower_component
from pitlens.radio import transcribe, translate
from pitlens.stints.pace import stint_degradation
from pitlens.undercut.analysis import pair_gap, pit_loss_now, rejoin_projection
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


NOTE_SECONDS = 4.8


def notify(race: RaceData, lap: int) -> None:
    """Pop up new fastest laps and retirements as the replay moves forward one lap at a time."""
    ss = st.session_state
    now = time.monotonic()
    notes = [n for n in ss.get("notes", []) if n["until"] > now and n["race"] == ss.race_key]
    if ss.get("shown_lap") == lap - 1:
        team_of = dict(zip(race.entrants["Driver"], race.entrants["Team"]))
        for e in race.events[(race.events["Lap"] == lap) & race.events["Kind"].isin(["FL", "OUT"])].itertuples():
            detail = (f'<span style="color:#A855F7;font-weight:700">{e.Text.partition(", ")[2]}</span> · lap {lap}'
                      if e.Kind == "FL" else f"Out of the race on lap {lap}")
            notes.insert(0, {"kind": e.Kind, "name": race.full_names.get(e.Driver, e.Driver),
                             "team": team_of.get(e.Driver, ""), "color": race.team_colors.get(e.Driver, "#888"),
                             "detail": detail, "until": now + NOTE_SECONDS, "race": ss.race_key})
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
    tower = timing_tower(race.laps, lap, race.retired, race.entrants)
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
            st.plotly_chart(charts.circuit_map(race.track), width="stretch", key="chart_circuit",
                            config={"displayModeBar": False, "staticPlot": True})

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


@st.cache_resource(show_spinner=False)
def whisper() -> "transcribe.Transcriber":
    return transcribe.Transcriber()


@st.cache_resource(show_spinner=False)
def translator(engine: str):
    return translate.make(engine)


def radio_view(race: RaceData, lap: int, focus: list[str]) -> None:
    clips = race.radio[race.radio["Lap"].notna() & (race.radio["Lap"] <= lap)]
    with st.container(horizontal=True, vertical_alignment="center"):
        only_focus = st.toggle("Focus drivers only", value=False, key="radio_focus")
        chinese = st.toggle("中文", value=st.session_state.get("radio_zh", False), key="radio_zh",
                            help="Show a Chinese translation under each transcript")
    if only_focus:
        clips = clips[clips["Driver"].isin(focus)]
    shown = clips.sort_values("SessionTime", ascending=False).head(12)
    texts = {c.Url: (transcribe.cached(c.Url) or {}).get("text") for c in shown.itertuples()}
    missing = [c for c in shown.itertuples() if texts[c.Url] is None]
    engines = translate.available_engines()

    ui.note(f"{len(clips)} clips up to lap {lap}, newest first. A red microphone in the timing tower marks a "
            "driver with a clip on the current lap.")
    if missing:
        if transcribe.available():
            if st.button(f"Transcribe {len(missing)} clip{'s' if len(missing) > 1 else ''}",
                         icon=":material/subtitles:", key="transcribe_btn",
                         help="Runs Whisper on this computer. The first time downloads the model (about 0.5 GB)."):
                bar = st.progress(0.0, text="Loading the speech model...")
                model = whisper()
                for i, c in enumerate(missing, start=1):
                    bar.progress(i / len(missing), text=f"Transcribing {c.Driver}, lap {c.Lap} ({i}/{len(missing)})")
                    texts[c.Url] = model.transcribe(c.Url, race.first_names.get(c.Driver))
                bar.empty()
                st.rerun(scope="fragment")  # redraw with the new transcripts and without the button
        else:
            ui.note('To turn clips into text, install the speech model: pip install -e ".[transcribe]"')

    if chinese:
        untranslated = [c for c in shown.itertuples() if texts[c.Url] and translate.cached(c.Url) is None]
        if not engines:
            ui.note('To translate, install the translation model: pip install -e ".[translate]"')
        elif untranslated:
            with st.container(horizontal=True, vertical_alignment="center"):
                engine = st.segmented_control(
                    "Engine", engines, key="zh_engine", required=True, default=engines[0],
                    format_func={"offline": "Offline", "claude": "Claude (API key)"}.get,
                    label_visibility="collapsed",
                    help="Offline runs a small model on this computer. Claude translates F1 radio far better but "
                         "needs an Anthropic API key and costs a fraction of a cent per clip.",
                )
                go = st.button(f"Translate {len(untranslated)} clip{'s' if len(untranslated) > 1 else ''}",
                               icon=":material/translate:", key="translate_btn")
            if go:
                try:
                    tr = translator(engine)
                    for c in untranslated:
                        translate.translate_clip(c.Url, tr, race.first_names.get(c.Driver))
                except Exception as exc:  # missing key, network, model download...
                    st.warning(f"Translation failed: {exc}")
                else:
                    st.rerun(scope="fragment")

    for clip in shown.itertuples():
        new = ' <span class="pl-pill" style="background:rgba(225,6,0,.14);color:#E10600">this lap</span>' \
            if clip.Lap == lap else ""
        st.html(f'<div style="margin-top:8px">{ui.driver_dot(race.team_colors.get(clip.Driver, "#999"))}'
                f"<b>{clip.Driver}</b> <span style='opacity:.6'>· lap {clip.Lap}</span>{new}</div>")
        st.audio(clip.Url, format="audio/mpeg")
        if texts.get(clip.Url):
            ui.quote(texts[clip.Url], translate.cached(clip.Url) if chinese else None)


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
    status = race.lap_status.get(lap, "Green")
    loss, loss_source = pit_loss_now(stops, status, race.pit_loss_ref)
    ref = race.pit_loss_ref
    ui.strip([
        ui.stat("Pit loss now", f"{loss:.1f} s" if loss else "–", small=loss_source),
        ui.stat("Circuit reference", f"{ref['normal']:.1f} s" if ref else "–",
                small=f"VSC {ref['vsc']:.1f} · SC {ref['sc']:.1f}" if ref and "vsc" in ref and "sc" in ref else ""),
        ui.stat("Stops so far", str(len(stops))),
        ui.stat("Latest stop", f"{last['Driver']}" if last is not None else "–",
                small=f"lap {last['Lap']}" if last is not None else ""),
        ui.stat("Battles", str(len(battles))),
    ])

    if loss:
        ui.label("If they pit at the end of this lap")
        ui.note(f"Uses a pit loss of {loss:.1f} s ({loss_source}). Under a safety car or VSC a stop costs less, "
                "which is why teams pit then.")
        everyone = st.toggle("All cars on the lead lap", value=False, key="rejoin_all")
        proj = rejoin_projection(tower, loss)
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
