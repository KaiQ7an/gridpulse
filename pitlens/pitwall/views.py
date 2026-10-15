"""The pit wall's views beside the timing tower: tyres, pit stops, strategy, radio and race control.

Each takes the loaded race and the lap being shown, and draws only what
happened up to that lap.
"""

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, ui
from pitlens.pitwall.data import RaceData
from pitlens.pitwall.timing import stint_timeline
from pitlens.radio import transcribe, translate
from pitlens.stints.pace import stint_degradation
from pitlens.undercut.analysis import (
    ordinary_stationary_times,
    pair_gap,
    pit_loss_now,
    plausible_lane_times,
    rejoin_projection,
)
from pitlens.undercut.charts import battle_chart, pit_loss_chart


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


def short_source(loss_source: str) -> str:
    """A few words for where the pit loss figure comes from (the full text goes in the tooltip)."""
    if loss_source.startswith("median"):
        return "race median"
    if loss_source.startswith("circuit"):
        return "circuit ref" + (" (SC)" if "safety" in loss_source else " (VSC)" if "VSC" in loss_source else "")
    return "scaled for SC/VSC" if "scaled" in loss_source else loss_source


def pits_view(race: RaceData, lap: int, focus: list[str]) -> None:
    """Every pit stop so far: how long it took, what it cost, places lost, and the quickest crews."""
    stops = race.stops.assign(LaneOk=plausible_lane_times(race.stops), StillOk=ordinary_stationary_times(race.stops))
    stops = stops[stops["Lap"] <= lap]
    still = race.stops["Stationary"].notna().any()
    status = race.lap_status.get(lap, "Green")
    loss, loss_source = pit_loss_now(stops, status, race.pit_loss_ref)

    def quickest(key: str, column: str, tip: str) -> str:
        timed = stops.dropna(subset=[column])
        timed = timed[timed["LaneOk" if column == "LaneTime" else "StillOk"]]
        if timed.empty:
            return ui.stat(key, "–")
        best = timed.sort_values([column, "Lap"]).iloc[0]
        return ui.stat(key, "", small=f"L{best['Lap']}", tip=tip, value_html=(
            ui.driver_dot(race.team_colors.get(best["Driver"], "#999")) + best["Driver"]
            + f' <span style="color:#A855F7">{best[column]:.1f} s</span>'))

    neutral = int(stops["Neutralised"].sum())
    stats = [ui.stat("Stops", str(len(stops)), small=f"{neutral} under SC/VSC" if neutral else "",
                     tip="Stops with a tyre change; drive-throughs on the same tyres aren't counted")]
    if still:
        stats.append(quickest("Quickest stop", "Stationary", "Shortest time stood still in the pit box"))
    stats += [
        quickest("Quickest pit lane", "LaneTime", "Shortest time from pit entry to pit exit"),
        ui.stat("Typical cost", f"{loss:.1f} s" if loss else "–", tip=f"Pit loss now: {loss_source}",
                small=short_source(loss_source) if loss else ""),
    ]
    ui.strip(stats)
    if stops.empty:
        ui.note("No stops yet.")
        return

    with st.container(horizontal=True, vertical_alignment="center"):
        ui.label("Every stop, newest first")
        only_focus = st.toggle("Focus drivers only", value=False, key="pits_focus")
    shown = stops[stops["Driver"].isin(focus)] if only_focus else stops
    ui.note("Pit lane is pit entry to pit exit. "
            + ("Stopped is the time stood still in the box. " if still else
               "The timing feed has no stationary times for this race. ")
            + "Cost is the time lost against the cars that stayed out; places are the end of the lap before "
            "the stop against the end of the out-lap. The quickest times are purple; grey ones are rough or "
            "doubtful (hover for why).")
    if shown.empty:
        ui.note("None of the focus drivers has stopped yet.")
    else:
        ui.pit_table(shown, race.team_colors, lap)

    column = "Stationary" if still and stops["Stationary"].notna().any() else "LaneTime"
    with st.container(horizontal=True, vertical_alignment="center"):
        if st.session_state.get("pits_rank") == "Teams":
            ui.label("Typical stop by team" if column == "Stationary" else "Typical pit lane time by team")
        else:
            ui.label("Quickest stops" if column == "Stationary" else "Quickest through the pit lane")
        by = st.segmented_control("Rank", ["Stops", "Teams"], key="pits_rank", required=True, default="Stops",
                                  label_visibility="collapsed")
    ranked = stops[stops["LaneOk" if column == "LaneTime" else "StillOk"]]
    if by == "Teams":
        teams = dict(zip(race.entrants["Driver"], race.entrants["Team"]))
        fig = charts.team_stop_times(ranked, race.team_colors, teams, column)
    else:
        fig = charts.quickest_stops(ranked, race.team_colors, column)
    st.plotly_chart(fig, width="stretch", key="chart_pit_rank", config={"displayModeBar": False})

    ui.label("What each stop cost")
    ui.note("Time lost to each stop against the cars that stayed out, by lap. Stops under a safety car or VSC "
            "(grey) cost far less, which is why teams pit then.")
    st.plotly_chart(pit_loss_chart(stops, loss, race.total_laps), width="stretch", key="chart_pitloss")


def strategy_view(race: RaceData, tower: pd.DataFrame, lap: int, focus: list[str]) -> None:
    stops = race.stops[race.stops["Lap"] <= lap]
    battles = race.battles[race.battles["RivalStopLap"] + 1 <= lap]
    last = stops.iloc[-1] if not stops.empty else None
    status = race.lap_status.get(lap, "Green")
    loss, loss_source = pit_loss_now(stops, status, race.pit_loss_ref)
    ref = race.pit_loss_ref
    ui.strip([
        ui.stat("Pit loss now", f"{loss:.1f} s" if loss else "–", small=short_source(loss_source) if loss else "",
                tip=loss_source),
        ui.stat("Circuit reference", f"{ref['normal']:.1f} s" if ref else "–",
                small=f"VSC {ref['vsc']:.1f} · SC {ref['sc']:.1f}" if ref and "vsc" in ref and "sc" in ref else "",
                tip="Typical pit loss at this circuit (MultiViewer): green flag, under VSC and under safety car"),
        ui.stat("Stops", str(len(stops)),
                small=f"latest {last['Driver']} L{last['Lap']}" if last is not None else ""),
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

    ui.label(f"Undercuts and overcuts so far · {len(battles)}" if len(battles) else "Undercuts and overcuts so far")
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
