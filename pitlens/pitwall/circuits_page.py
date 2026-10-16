"""Circuits page of the pit wall: one track, and every saved Grand Prix there year by year."""

import pandas as pd
import streamlit as st

from pitlens import snapshots
from pitlens.pitwall import charts, ui
from pitlens.season.circuits import circuit_years, circuits, saved_races

NEW_RULES = 2026  # the year the cars changed: lap times before it aren't comparable


@st.cache_data(show_spinner=False)
def cached_races() -> pd.DataFrame:
    return saved_races()


@st.cache_data(show_spinner=False, max_entries=8)
def cached_years(circuit: int) -> pd.DataFrame:
    return circuit_years(cached_races(), circuit)


@st.cache_data(show_spinner=False, max_entries=8)
def cached_track(year: int, round_number: int) -> dict | None:
    parts = snapshots.load_race(year, round_number, "R")
    return parts["track"] if parts else None


def render() -> None:
    ui.sidebar_brand("Every circuit, year by year")
    table = circuits(cached_races())
    if table.empty:
        st.info("No saved races yet: run `pitlens snapshot --year 2026` first.")
        st.stop()
    ss = st.session_state
    keys = table["Circuit"].tolist()
    by_slug = dict(zip(table["Slug"], keys))
    link = st.query_params.get("circuit")
    if link and ss.get("circuit_link") != link:  # a shared link: open that circuit
        ss.circuit_link = link
        if link in by_slug:
            ss.circuit_pick = by_slug[link]
    if ss.get("circuit_pick") not in keys:  # the track raced most recently
        ss.circuit_pick = int(table.sort_values(["Year", "Round"]).iloc[-1]["Circuit"])
    ui.sidebar_footer()
    info = table.set_index("Circuit")
    circuit = st.selectbox("Circuit", keys, key="circuit_pick", label_visibility="collapsed",
                           format_func=lambda c: f"{info.loc[c, 'Location']} · {info.loc[c, 'Event']}")
    here = info.loc[circuit]
    if dict(st.query_params) != {"circuit": here["Slug"]}:  # keep the address shareable
        st.query_params.from_dict({"circuit": here["Slug"]})
        ss.circuit_link = here["Slug"]

    years = cached_years(circuit)
    if years.empty:
        st.info("No saved Grand Prix here yet.")
        st.stop()
    saved = years["Year"].astype(str).tolist()
    ui.header(f"{here['Event']} · circuit", here["Location"],
              f"Grands Prix saved here: {', '.join(saved)}. Everything below is from those races.")
    strip(years)

    left, right = st.columns([5, 7], gap="large")
    with left, st.container(border=True, key="card-circuit-map"):
        ui.label("The track")
        track = cached_track(int(here["Year"]), int(here["Round"]))
        if track:
            st.plotly_chart(charts.circuit_map(track), width="stretch", key="chart_circuit_map",
                            config={"displayModeBar": False})
            traced = (f"Traced from the fastest lap of the {here['Year']} race" if track.get("source") == "fastest lap"
                      else "The circuit outline")
            ui.note(f"{traced}; the red bar is the start and finish line.")
        else:
            ui.note("No circuit outline saved for this track.")
    with right, st.container(border=True, key="card-circuit-years"):
        ui.label("Year by year")
        ui.note("Each year opens its replay. Pole is the qualifying time; the fastest lap is the race's.")
        ui.circuit_years_table(years)

    left, right = st.columns(2, gap="large")
    with left, st.container(border=True, key="card-circuit-laps"):
        ui.label("Pole and the fastest race lap")
        note = "How quick it was here each year."
        if years["Year"].min() < NEW_RULES <= years["Year"].max():
            note += f" The cars changed for {NEW_RULES}, so expect a step between the years either side."
        ui.note(note)
        st.plotly_chart(charts.circuit_laps_chart(years), width="stretch", key="chart_circuit_laps")
    with right, st.container(border=True, key="card-circuit-stops"):
        ui.label("Pit stops")
        ui.note(strategy_note(years))
        st.plotly_chart(charts.circuit_stops_chart(years), width="stretch", key="chart_circuit_stops",
                        config={"displayModeBar": False})


def strip(years: pd.DataFrame) -> None:
    latest = years.iloc[-1]
    n = len(years)
    stats = [ui.stat("Laps", str(latest["Scheduled"]))]
    if pd.notna(latest["PitLoss"]):
        vsc = f"{latest['PitLossVsc']:.0f} s under VSC" if pd.notna(latest["PitLossVsc"]) else ""
        stats.append(ui.stat("Pit stop costs", f"{latest['PitLoss']:.0f} s", small=vsc,
                             tip="Time lost to a stop against staying out, from MultiViewer"))
    stats += [
        ui.stat("Won from pole", f"{int((years['WinnerGrid'] == 1).sum())} of {n}"),
        ui.stat("Safety cars", str(int(years["SafetyCars"].sum())), small=f"in {n} race{'s' if n > 1 else ''}"),
        ui.stat("Virtual safety cars", str(int(years["VSCs"].sum()))),
        ui.stat("Red flags", str(int(years["RedFlags"].sum()))),
        ui.stat("Wet races", str(int(years["Wet"].sum()))),
    ]
    ui.strip(stats)


def strategy_note(years: pd.DataFrame) -> str:
    """Finishers by number of stops, and the most used tyre run each year."""
    parts = []
    names = {"S": "soft", "M": "medium", "H": "hard", "I": "intermediate", "W": "wet"}
    for y in years.itertuples():
        if y.CommonTyres and y.CommonShare:
            run = " to ".join(names.get(c, "?") for c in y.CommonTyres.split("-"))
            parts.append(f"{y.Year}: {run} for {y.CommonShare} of {y.Finishers}")
    head = "Finishers by how many times they stopped."
    return head + (" Most used tyre run, " + "; ".join(parts) + "." if parts else "")
