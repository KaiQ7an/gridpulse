"""Qualifying page of the pit wall: the knockout classification, ideal laps and where the time went."""

import pandas as pd
import streamlit as st

from gridpulse import snapshots
from gridpulse.pitwall import charts, ui
from gridpulse.pitwall.data import FIRST_SEASON, completed_races
from gridpulse.pitwall.navigation import select_season
from gridpulse.quali.data import SESSIONS, QualiData, ideal_laps, load_quali
from gridpulse.session import TimingUnavailable


@st.cache_data(ttl=3600, show_spinner=False)
def cached_races(year: int) -> pd.DataFrame:
    return completed_races(year)


def cached_quali(year: int, round_number: int, kind: str) -> QualiData:
    return _cached_quali(year, round_number, kind, snapshots.revision(year))


@st.cache_resource(show_spinner=False, max_entries=6)
def _cached_quali(year: int, round_number: int, kind: str, revision: tuple) -> QualiData:
    return load_quali(year, round_number, kind)


def render() -> None:
    ui.sidebar_brand("Qualifying, part by part")
    this_year = pd.Timestamp.now().year
    year = select_season(range(this_year, FIRST_SEASON - 1, -1), key="q_year")
    races = cached_races(year)
    if races.empty:
        st.info(f"No {year} races have finished yet. Pick an earlier season.")
        st.stop()
    labels = [f"R{r.RoundNumber} · {r.EventName}" for r in races.itertuples()]
    i = st.sidebar.selectbox("Grand Prix", range(len(races)), index=len(races) - 1, format_func=lambda i: labels[i],
                             key="q_event")
    kind = "Q"
    if "sprint" in str(races.loc[i, "EventFormat"]):
        choice = st.sidebar.segmented_control("Session", ["Qualifying", "Sprint Qualifying"], key="q_session",
                                              default="Qualifying", required=True)
        kind = "SQ" if choice == "Sprint Qualifying" else "Q"
    ui.sidebar_footer()

    with st.spinner("Loading the session. The first load takes up to a minute; after that it's cached."):
        try:
            q = cached_quali(year, int(races.loc[i, "RoundNumber"]), kind)
        except TimingUnavailable as exc:
            st.warning(str(exc), icon=":material/cloud_off:")
            st.stop()
        except Exception as exc:  # FastF1 and OpenF1 raise a variety of errors for missing data
            st.error(f"Couldn't load {SESSIONS[kind]} for this event: {exc}")
            st.stop()

    ui.header(f"{q.year} · Round {q.round_number} · {q.location} · {q.session_name}", q.event_name,
              f"{q.date:%-d %B %Y} · data: {q.source}")
    ideal = ideal_laps(q.laps)
    results = q.results
    strip(q, ideal)

    left, right = st.columns([7, 6], gap="large")
    with left, st.container(border=True, key="card-quali"):
        ui.label("Classification")
        ui.note("Fastest time of each part in purple. The ideal lap adds up each driver's best three sectors; "
                "the small figure is the time they left on the table.")
        ui.quali_table(results, ideal, q.team_colors)

    order = results["Driver"].dropna().tolist()
    with right, st.container(border=True, key="card-sectors"):
        with st.container(horizontal=True, vertical_alignment="center"):
            ui.label("Where the time went")
            everyone = st.toggle("All drivers", value=False, key="q_all")
        ui.note("Each driver's best sector against the fastest of the session.")
        shown = order if everyone else order[:10]
        dark = getattr(getattr(st.context, "theme", None), "type", "dark") != "light"
        st.plotly_chart(charts.sector_gaps_chart(ideal, shown, dark), width="stretch", key="chart_sectors",
                        config={"displayModeBar": False})

    with st.container(border=True, key="card-evolution"):
        ui.label("Through the session")
        ui.note("Every valid push lap by when it was set: the track gets quicker as it rubbers in, and the "
                "fastest laps come at the end of each part. The top three in team colours; deleted laps "
                "are left out.")
        st.plotly_chart(charts.quali_evolution_chart(q.laps, q.team_colors, order[:3]), width="stretch",
                        key="chart_evolution")
    ui.note("To compare two drivers' laps corner by corner, open the Onboard page.")


def strip(q: QualiData, ideal: pd.DataFrame) -> None:
    results = q.results
    finals = results[results["Out"] == ""]
    pole = finals.iloc[0] if not finals.empty else results.iloc[0]
    pole_time = pole["Q3"] if pd.notna(pole["Q3"]) else results[["Q1", "Q2", "Q3"]].min().min()
    second = finals.iloc[1] if len(finals) > 1 else None
    stats = [
        ui.stat("Pole", "", value_html=ui.driver_dot(q.team_colors.get(pole["Driver"], "#999")) + str(pole["Driver"])
                + f' <span style="color:#A855F7">{ui._laptime(pole_time)}</span>'),
    ]
    if second is not None and pd.notna(second["Q3"]) and pd.notna(pole_time):
        stats.append(ui.stat("Gap to P2", f"{second['Q3'] - pole_time:.3f} s", small=str(second["Driver"])))
    # The cut: the slowest time in a part that still went through to the next.
    for part, went_through in (("Q1", results["Out"].isin(["Q2", ""])), ("Q2", results["Out"] == "")):
        cut = results.loc[went_through, part].max()
        if pd.notna(cut):
            stats.append(ui.stat(f"{part} cut", ui._laptime(cut), tip=f"Slowest {part} time that went through"))
    if len(ideal):
        best = ideal.sort_values("Ideal").iloc[0]
        stats.append(ui.stat("Best ideal lap", "", small=f"{best['Driver']}",
                             value_html=f'<span style="color:#A855F7">{ui._laptime(best["Ideal"])}</span>',
                             tip="Best three sectors of any driver, added up"))
    ui.strip(stats)
