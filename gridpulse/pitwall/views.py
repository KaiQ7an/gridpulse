"""The pit wall's views beside the timing tower: tyres, pit stops, strategy, radio and race control.

Each takes the loaded race and the lap being shown, and draws only what
happened up to that lap.
"""

import pandas as pd
import streamlit as st

from gridpulse.pitwall import charts, ui
from gridpulse.pitwall.data import RaceData
from gridpulse.pitwall.timing import stint_timeline
from gridpulse.radio import transcribe, translate
from gridpulse.stints.pace import stint_degradation
from gridpulse.undercut.analysis import (
    ordinary_stationary_times,
    pair_gap,
    pit_loss_now,
    plausible_lane_times,
    rejoin_projection,
)
from gridpulse.undercut.charts import battle_chart, pit_loss_chart
from gridpulse.undercut.window import (
    DRY,
    best_plan,
    compounds_allowed,
    fit_tyre_model,
    laps_to_catch,
    pit_window,
    stay_out_time,
)


def tyres_view(race: RaceData, laps: pd.DataFrame, tower: pd.DataFrame, lap: int, focus: list[str]) -> None:
    ui.label("Stints")
    ui.note("Tyre stints in the current running order.")
    st.plotly_chart(
        charts.strategy_chart(stint_timeline(laps), tower["Driver"].tolist(), race.total_laps),
        width="stretch",
        key="chart_stints",
    )
    ui.label("Degradation so far")
    clean = race.clean_through(lap)
    clean = clean[clean["Driver"].isin(focus)]
    deg = stint_degradation(clean)
    if deg.empty:
        if tower.loc[tower['Driver'].isin(focus), 'Compound'].isin(DRY).any():
            ui.label("Typical wear reference · not measured")
            ui.note("A measured stint needs five clean green-flag laps. Until then, these typical dry-tyre rates "
                    "are a reference only; they do not describe this race's measured degradation.")
            st.plotly_chart(charts.tyre_prior_chart(), width="stretch", key="chart_deg_prior")
        else:
            ui.note("No measured dry-tyre stint yet. The typical slick-tyre reference does not model wet tyres.")
    else:
        ui.note("Fuel-corrected seconds lost per lap of tyre age, focus drivers.")
        st.plotly_chart(charts.degradation_chart(deg), width="stretch", key="chart_deg")


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
    ui.note(f"{len(clips)} clips up to lap {lap}, newest first. A red microphone in the timing tower marks a "
            "driver with a clip on the current lap. Transcripts and translations are read from the prepared cache.")
    if any(not text for text in texts.values()):
        with st.expander("Prepare missing transcripts offline"):
            st.caption("Run this on your own computer before opening the replay. Model downloads and inference run in the CLI.")
            st.code(f"gridpulse radio --year {race.year} --event {race.round_number} "
                    f"--session {'S' if race.session_name == 'Sprint' else 'R'} --transcribe --translate", language="bash")
    elif chinese and any(translate.cached(url) is None for url in texts):
        ui.note("Chinese translations have not been prepared for every clip; the original transcript is shown where needed.")

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
    stops = race.stops_through(lap)
    stops = stops.assign(LaneOk=plausible_lane_times(stops), StillOk=ordinary_stationary_times(stops))
    still = stops["Stationary"].notna().any()
    status = race.lap_status.get(lap, "Green")
    loss, loss_source = pit_loss_now(stops[stops["Lap"] < lap], status, race.pit_loss_ref)

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
    ranked = stops[stops["LaneOk" if column == "LaneTime" else "StillOk"]].dropna(subset=[column])
    if ranked.empty:
        ui.note(f"{race.source} has no pit lane times for this race, only which lap each car stopped on.")
    elif by == "Teams":
        teams = dict(zip(race.entrants["Driver"], race.entrants["Team"]))
        fig = charts.team_stop_times(ranked, race.team_colors, teams, column)
    else:
        fig = charts.quickest_stops(ranked, race.team_colors, column)
    if not ranked.empty:
        st.plotly_chart(fig, width="stretch", key="chart_pit_rank", config={"displayModeBar": False})

    ui.label("What each stop cost")
    ui.note("Time lost to each stop against the cars that stayed out, by lap. Stops under a safety car or VSC "
            "(grey) cost far less, which is why teams pit then.")
    st.plotly_chart(pit_loss_chart(stops, loss, race.total_laps), width="stretch", key="chart_pitloss")


def _tyres(race: RaceData, tower: pd.DataFrame, driver: str, lap: int) -> tuple[str, float, set[str]]:
    """A car's compound and tyre age now, and every compound it has run so far."""
    row = tower.set_index("Driver").loc[driver]
    age = float(row["TyreAge"]) if pd.notna(row["TyreAge"]) else float("nan")
    used = set(race.laps[(race.laps["Driver"] == driver) & (race.laps["LapNumber"] <= lap)]["Compound"].dropna())
    return row["Compound"], age, used


def _plan(race: RaceData, tower: pd.DataFrame, model, lap: int, loss: float, driver: str):
    """The model's quickest plan for `driver` (and the full window), or None if it can't say."""
    compound, age, used = _tyres(race, tower, driver, lap)
    laps_left = race.total_laps - lap
    if model is None or compound not in DRY or pd.isna(age) or laps_left < 2:
        return None, None
    window = pit_window(model, driver, compound, age, laps_left, loss, compounds_allowed(used))
    return best_plan(window), window


def catch_text(race: RaceData, tower: pd.DataFrame, model, lap: int, loss: float, rejoin) -> str:
    """"in 4 laps": how long a car stopping now would take to close on the car it rejoins behind."""
    if not rejoin.CarAhead or model is None or rejoin.Driver not in model.base or rejoin.CarAhead not in model.base:
        return "–"
    best, _ = _plan(race, tower, model, lap, loss, rejoin.Driver)
    ahead_compound, ahead_age, _ = _tyres(race, tower, rejoin.CarAhead, lap)
    if best is None or ahead_compound not in DRY or pd.isna(ahead_age):
        return "–"
    n = laps_to_catch(model, rejoin.Driver, best["Compound"], 0, rejoin.CarAhead, ahead_compound, ahead_age,
                      rejoin.GapAhead, race.total_laps - lap)
    return "not before the flag" if n is None else f"in {n} lap{'s' if n != 1 else ''}"


def pit_window_view(race: RaceData, tower: pd.DataFrame, lap: int, focus: list[str], loss: float, model) -> None:
    """When the model says a car should make its (last) stop, and what waiting or stopping now costs."""
    ui.label("Pit window")
    if model is None:
        ui.note("The pit window needs dry running: there are no clean laps on slicks yet.")
        return
    running = tower.loc[~tower["Out"] & (tower["LapsDown"] == 0), "Driver"].tolist()
    options = [d for d in focus if d in running] + [d for d in running if d not in focus]
    if not options:
        return
    driver = st.selectbox("Driver", options, key="window_driver", label_visibility="collapsed")
    compound, age, used = _tyres(race, tower, driver, lap)
    best, window = _plan(race, tower, model, lap, loss, driver)
    if best is None:
        ui.note(f"{driver} is on {str(compound).title()} tyres; the model covers slicks with laps still to run.")
        return

    if model.prior_only:
        ui.label("Pre-race prior window · no measured dry laps")

    laps_left = race.total_laps - lap
    rule_done = len(used & set(DRY)) >= 2
    stay = stay_out_time(model, driver, compound, age, laps_left) - window["Total"].min() if rule_done else None
    first = window[(window["Compound"] == best["Compound"]) & (window["LapsMore"] == 1)]["Lost"].iloc[0]
    if stay is not None and stay <= 0:
        verdict = (f"Quickest is no more stops: over {laps_left} laps a new set wouldn't pay back the "
                   f"{loss:.0f} s stop.")
    else:
        verdict = (f"Stop L{lap + int(best['LapsMore'])} for {best['Compound'].lower()}s. "
                   f"Window L{lap + best['From']}–{lap + best['To']}; stopping next lap costs +{first:.1f} s.")
    evidence = "fitted from this race" if compound in model.deg_measured else "based mainly on typical wear"
    ui.insight(f"{driver}: {'Under typical-tyre assumptions, ' if model.prior_only else ''}{verdict}")
    ui.note(f"{compound.title()} · age {age:.0f} laps · wear {model.deg[compound]:.2f} s/lap ({evidence}) · "
            f"{sum(model.sample_counts.values())} clean laps across the field. "
            "One final stop on fresh tyres; the window is within 1 s of the best plan, not a confidence interval.")

    comparison = []
    for k, label in ((1, "Stop next lap"), (4, "Stop three laps later")):
        options = window[window["LapsMore"] == k]
        if not options.empty:
            plan = options.loc[options["Total"].idxmin()]
            comparison.append({"Plan": label, "Tyres": plan["Compound"].title(), "Total": plan["Total"]})
    if stay is not None:
        comparison.append({"Plan": "Stay out to the flag", "Tyres": compound.title(),
                           "Total": stay_out_time(model, driver, compound, age, laps_left)})
    baseline = min(window["Total"].min(), *(row["Total"] for row in comparison))
    actual = None
    if not st.session_state.get("no_spoilers", False):
        later = race.stops[(race.stops["Driver"] == driver) & (race.stops["Lap"] > lap)]
        show_actual = st.toggle("Show when they really stopped", value=False, key="window_actual",
                               disabled=later.empty, help="Their next stop in this race (from the future, in a replay)")
        actual = int(later["Lap"].iloc[0]) if show_actual and not later.empty else None
    st.plotly_chart(charts.pit_window_chart(window, lap, race.total_laps, best, actual, stay), width="stretch",
                    key="chart_window")
    with st.expander("Compare stop plans"):
        st.dataframe(pd.DataFrame([{"Plan": row["Plan"], "Tyres": row["Tyres"],
                                    "Cost vs quickest plan": f"+{max(0, row['Total'] - baseline):.1f} s"}
                                   for row in comparison]), hide_index=True, width="stretch")

    with st.expander("How the model works"):
        ui.note("With no clean dry laps, typical compound pace and wear provide a baseline. "
                "It updates as observations arrive; wear is marked as measured after five clean laps "
                "in a stint, which may take longer than five race laps. No future race laps are used.")
        ui.note("Each clean lap so far is fitted as driver pace + compound offset + wear x tyre age + a trend for "
                "fuel and track that is the same for everyone. Each plan is one more stop then the new set to the "
                "flag, with the pit loss above. It knows tyres and pit loss only: not traffic, undercut threats, "
                "safety cars or tyre-life limits. Backtested on every 2024 and 2025 race (gridpulse pitwindow), its "
                "best lap is within five laps of the team's choice 59–66% of the time, a little better than "
                "splitting the remaining laps evenly between the stints.")
        st.dataframe(pd.DataFrame({
            "Compound": [c.title() for c in DRY],
            "Fresh pace vs medium": [f"{model.offset[c]:+.2f} s" for c in DRY],
            "Wear": [f"{model.deg[c]:.3f} s/lap" for c in DRY],
            "Pace evidence": ["race fit" if c in model.measured else "typical figures" for c in DRY],
            "Wear evidence": ["race fit" if c in model.deg_measured else "typical figures" for c in DRY],
            "Clean laps": [model.sample_counts.get(c, 0) for c in DRY],
        }), hide_index=True, width="stretch")
        ui.note(f"Fuel and track: {model.trend:+.3f} s a lap, every car.")


def strategy_view(race: RaceData, tower: pd.DataFrame, lap: int, focus: list[str]) -> None:
    stops = race.stops_through(lap)
    battles = race.battles[race.battles["RivalStopLap"] + 1 <= lap]
    last = stops.iloc[-1] if not stops.empty else None
    status = race.lap_status.get(lap, "Green")
    loss, loss_source = pit_loss_now(stops[stops["Lap"] < lap], status, race.pit_loss_ref)
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
        model = fit_tyre_model(race.clean_through(lap), allow_prior=(~tower['Out'] & tower['Compound'].isin(DRY)).any())
        pit_window_view(race, tower, lap, focus, loss, model)
        ui.label("If they pit at the end of this lap")
        ui.note(f"Uses a pit loss of {loss:.1f} s ({loss_source}). Under a safety car or VSC a stop costs less, "
                "which is why teams pit then.")
        everyone = st.toggle("All cars on the lead lap", value=False, key="rejoin_all")
        proj = rejoin_projection(tower, loss)
        if not everyone:
            proj = proj[proj["Driver"].isin(focus)]
        if model is not None and model.prior_only:
            ui.note("Rejoin positions use the current gaps. Catch estimates wait for observed pace from both drivers.")
        st.dataframe(
            pd.DataFrame(
                {
                    "Driver": proj["Driver"],
                    "Now": "P" + proj["Now"].astype(str),
                    "Rejoins": "P" + proj["Rejoin"].astype(str),
                    "Behind": [f"{c} by {g:.1f} s" if c else "–" for c, g in zip(proj["CarAhead"], proj["GapAhead"])],
                    "Catches them": [catch_text(race, tower, model, lap, loss, r) for r in proj.itertuples()],
                    "Ahead of": [f"{c} by {g:.1f} s" if c else "–" for c, g in zip(proj["CarBehind"], proj["GapBehind"])],
                }
            ),
            hide_index=True,
            width="stretch",
            column_config={"Catches them": st.column_config.TextColumn(
                help="Laps on new tyres until the gap to the car ahead is closed, from the tyre model below")},
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
        st.plotly_chart(battle_chart(gap, battle, race.total_laps, through_lap=lap),
                        width="stretch", key="chart_battle")
