"""Onboard page of the pit wall: two drivers' fastest laps side by side."""

import pandas as pd
import streamlit as st

from pitlens.onboard.charts import telemetry_figure, track_map
from pitlens.onboard.compare import align, corner_speeds, minisectors
from pitlens.onboard.data import SESSION_NAMES, OnboardData, compare, load_session_with_telemetry, teammate_of
from pitlens.pitwall.data import FIRST_SEASON, completed_races
from pitlens.pitwall.timing import format_lap_time


@st.cache_data(ttl=3600, show_spinner=False)
def cached_races(year: int) -> pd.DataFrame:
    return completed_races(year)


@st.cache_resource(show_spinner=False, max_entries=4)
def cached_session(year: int, round_number: int, kind: str):
    return load_session_with_telemetry(year, round_number, kind)


@st.cache_data(show_spinner=False, max_entries=16)
def cached_compare(_session, key: tuple, ref: str, other: str) -> OnboardData:
    return compare(_session, ref, other)


def drivers_with_laps(session) -> pd.DataFrame:
    res = session.results.sort_values("Position")
    timed = set(session.laps.dropna(subset=["LapTime"])["Driver"])
    drivers = pd.DataFrame({"Driver": res["Abbreviation"], "Team": res["TeamName"]})
    return drivers[drivers["Driver"].isin(timed)].reset_index(drop=True)


def pick_drivers(drivers: pd.DataFrame) -> tuple[str, str]:
    """First driver defaults to the fastest; the second follows them to their teammate."""
    ss = st.session_state
    names = drivers["Driver"].tolist()
    if ss.get("ob_a") not in names:
        ss.ob_a = names[0]
    a = st.sidebar.selectbox("Driver", names, key="ob_a")
    if ss.get("ob_prev_a") != a or ss.get("ob_b") not in names or ss.get("ob_b") == a:
        mate = teammate_of(drivers, a)
        ss.ob_b = mate if mate in names else next(n for n in names if n != a)
        ss.ob_prev_a = a
    b = st.sidebar.selectbox("Compared with", [n for n in names if n != a], key="ob_b")
    return a, b


def render() -> None:
    st.sidebar.title("PitLens")
    st.sidebar.caption("Onboard · fastest-lap comparison")
    this_year = pd.Timestamp.now().year
    year = st.sidebar.selectbox("Season", range(this_year, FIRST_SEASON - 1, -1), key="ob_year")
    races = cached_races(year)
    if races.empty:
        st.info(f"No {year} races have finished yet. Pick an earlier season.")
        st.stop()
    labels = [f"R{r.RoundNumber} · {r.EventName}" for r in races.itertuples()]
    i = st.sidebar.selectbox("Event", range(len(races)), index=len(races) - 1, format_func=lambda i: labels[i], key="ob_event")
    round_number = int(races.loc[i, "RoundNumber"])
    kind = st.sidebar.selectbox("Session", list(SESSION_NAMES), format_func=SESSION_NAMES.get, key="ob_session")

    with st.spinner("Loading the session with car telemetry (the first time takes up to a minute)..."):
        try:
            session = cached_session(year, round_number, kind)
        except Exception as exc:  # e.g. no sprint at this event
            st.error(f"Couldn't load {SESSION_NAMES[kind]} for this event: {exc}")
            st.stop()

    drivers = drivers_with_laps(session)
    if len(drivers) < 2:
        st.warning("Fewer than two drivers set a lap time in this session.")
        st.stop()
    a, b = pick_drivers(drivers)
    st.sidebar.divider()
    st.sidebar.caption("Unofficial. Timing data from the public F1 archive via FastF1.")

    try:
        data = cached_compare(session, (year, round_number, kind), a, b)
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()

    aligned = align(data.ref.telemetry, data.other.telemetry)
    sectors = minisectors(aligned)
    corners = corner_speeds(data.ref.telemetry, data.other.telemetry, data.corners)
    gap = (data.other.lap_time - data.ref.lap_time).total_seconds()

    st.title(f"{a} vs {b}")
    st.caption(f"{data.name} · {data.session_name} · fastest laps")

    m = st.columns(4)
    m[0].metric(f"{a} lap", format_lap_time(data.ref.lap_time), help=f"{data.ref.compound.title()}, {data.ref.tyre_life:.0f} laps old")
    m[1].metric(
        f"{b} lap", format_lap_time(data.other.lap_time), f"{gap:+.3f} s", delta_color="inverse",
        help=f"{data.other.compound.title()}, {data.other.tyre_life:.0f} laps old",
    )
    won = int((sectors["Faster"] == "ref").sum())
    m[2].metric("Mini-sectors won", f"{a} {won} · {b} {len(sectors) - won}")
    m[3].metric("Top speed", f"{data.ref.telemetry['Speed'].max():.0f} · {data.other.telemetry['Speed'].max():.0f} km/h")

    sector_rows = pd.DataFrame(
        {
            "Driver": [a, b],
            **{
                f"S{n + 1}": [format_lap_time(data.ref.sectors[n]), format_lap_time(data.other.sectors[n])]
                for n in range(3)
            },
            "Lap": [format_lap_time(data.ref.lap_time), format_lap_time(data.other.lap_time)],
        }
    )
    st.dataframe(sector_rows, hide_index=True)

    st.subheader("Telemetry")
    st.caption("Gap at the top: above zero, the second driver is behind at that point of the lap. Dotted lines mark corners.")
    st.plotly_chart(telemetry_figure(data, aligned), width="stretch")

    left, right = st.columns([6, 5], gap="medium")
    with left:
        st.subheader("Who was faster where")
        st.plotly_chart(track_map(data, sectors), width="stretch")
    with right:
        st.subheader("Corner by corner")
        st.caption(f"Minimum speed in each corner and time {a} gained (+) or lost (−) through it.")
        table = corners.rename(
            columns={"RefMinSpeed": f"{a} km/h", "OtherMinSpeed": f"{b} km/h", "SpeedDiff": "Diff", "Gain": f"{a} gain (s)"}
        )[["Corner", f"{a} km/h", f"{b} km/h", "Diff", f"{a} gain (s)"]]
        st.dataframe(table, hide_index=True, width="stretch", height=480)
