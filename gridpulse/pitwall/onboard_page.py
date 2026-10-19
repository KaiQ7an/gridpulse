"""Onboard page of the pit wall: fastest or explicitly chosen telemetry laps."""

import pandas as pd
import streamlit as st

from gridpulse.drivers.profiles import profile as driver_profile
from gridpulse.onboard.charts import corner_gains, telemetry_figure, track_map
from gridpulse.onboard.compare import align, corner_speeds, minisectors, sector_distances, summarise
from gridpulse.onboard.data import (
    SESSION_NAMES,
    OnboardData,
    load_weekend,
    teammate_of,
)
from gridpulse.pitwall import driver_picker, event_names, ui
from gridpulse.pitwall.data import FIRST_SEASON, completed_races
from gridpulse.pitwall.navigation import integer, select_season
from gridpulse.pitwall.timing import format_lap_time
from gridpulse.session import TimingUnavailable


@st.cache_data(ttl=3600, show_spinner=False)
def cached_races(year: int) -> pd.DataFrame:
    return completed_races(year)


@st.cache_resource(show_spinner=False, max_entries=4)
def cached_weekend(year: int, round_number: int, kind: str, validity_version: int = 3):
    return load_weekend(year, round_number, kind)


@st.cache_data(show_spinner=False, max_entries=16)
def cached_compare(_weekend, key: tuple, ref: str, other: str, ref_lap: int | None = None,
                   other_lap: int | None = None, validity_version: int = 3) -> OnboardData:
    return _weekend.compare(ref, other, ref_lap, other_lap)


def pick_drivers(drivers: pd.DataFrame, allow_same: bool = False) -> tuple[str, str]:
    """First driver defaults to the fastest; the second follows them to their teammate."""
    ss = st.session_state
    names = drivers["Driver"].tolist()
    full_names = {}
    for row in drivers.to_dict("records"):
        code, full = row["Driver"], row.get("FullName")
        full_names[code] = full if pd.notna(full) and full and full != code else driver_profile("f1", code).get("name") or code
    teams = dict(zip(drivers.Driver, drivers.Team))
    if ss.get("ob_a") not in names:
        ss.ob_a = names[0]
    a = st.sidebar.selectbox("Driver", names, key="ob_a", format_func=full_names.get)
    driver_picker.decorate("Driver", names, teams, key="ob_a", selected=a)
    if ss.get("ob_prev_a") != a or ss.get("ob_b") not in names or (not allow_same and ss.get("ob_b") == a):
        mate = teammate_of(drivers, a)
        ss.ob_b = mate if mate in names else next(n for n in names if n != a)
        ss.ob_prev_a = a
    others = [n for n in names if allow_same or n != a]
    b = st.sidebar.selectbox("Compared with", others, key="ob_b", format_func=full_names.get)
    driver_picker.decorate("Compared with", others, teams, key="ob_b", selected=b)
    return a, b


def pick_laps(weekend, a: str, b: str, scope: tuple, requested: dict) -> tuple[int | None, int | None]:
    ss = st.session_state
    if ss.get("ob_lap_scope") != (*scope, a, b):
        ss.ob_lap_scope = (*scope, a, b)
        ss.ob_ref_lap = ss.ob_other_lap = None
    chosen = []
    for driver, key, param, label in ((a, "ob_ref_lap", "lap_a", "Reference lap"),
                                      (b, "ob_other_lap", "lap_b", "Comparison lap")):
        options = weekend.lap_options(driver).set_index("Lap")
        numbers = [None, *options.index.astype(int).tolist()]
        if integer(requested.get(param)) in options.index:
            ss[key] = integer(requested[param])
        elif requested.get(param):
            st.sidebar.warning(f"{driver} L{requested[param]} isn't a valid available lap. Choose another below.")
        if ss.get(key) not in numbers:
            ss[key] = None

        def name(number, options=options, driver=driver):
            if number is None:
                return f"{driver} · fastest valid lap"
            row = options.loc[number]
            tyre = str(row["Compound"]).title()
            age = f" · {row['TyreLife']:.0f} laps old" if pd.notna(row["TyreLife"]) else ""
            return f"L{number} · {format_lap_time(row['LapTime'])} · {tyre}{age}"

        chosen.append(st.sidebar.selectbox(label, numbers, key=key, format_func=name))
    return tuple(chosen)


def render() -> None:
    ui.sidebar_brand("Onboard, compare two laps")
    ss = st.session_state
    params = dict(st.query_params)
    link = tuple(sorted(params.items()))
    incoming = bool(params.get("year")) and ss.get("ob_link") != link
    if incoming:
        ss.ob_link = link  # consume before loading: a failed request must not trap the pickers
        ss.ob_mode = "Choose laps" if params.get("mode") == "laps" or params.get("lap_a") or params.get("lap_b") \
            else "Fastest laps"
    this_year = pd.Timestamp.now().year
    if incoming and FIRST_SEASON <= integer(params.get("year"), 0) <= this_year:
        ss.ob_year = int(params["year"])
    elif "ob_year" not in ss and ss.get("selected_race"):
        ss.ob_year = ss.selected_race[0]
    year = select_season(range(this_year, FIRST_SEASON - 1, -1), key="ob_year")
    races = cached_races(year)
    if races.empty:
        st.info(f"No {year} races have finished yet. Pick an earlier season.")
        st.stop()
    labels = [f"R{r.RoundNumber} · {event_names.title(year, r.EventName, getattr(r, 'Location', ''))}" for r in races.itertuples()]
    requested_round = integer(params.get("round")) if incoming else None
    if requested_round is None and "ob_event" not in ss and ss.get("selected_race", (None,))[0] == year:
        requested_round = ss.selected_race[1]
    rounds = races["RoundNumber"].astype(int).tolist()
    if requested_round in rounds:
        ss.ob_event = rounds.index(requested_round)
    if ss.get("ob_event", 0) >= len(races):
        ss.ob_event = len(races) - 1
    i = st.sidebar.selectbox("Event", range(len(races)), index=len(races) - 1, format_func=lambda i: labels[i], key="ob_event")
    round_number = int(races.loc[i, "RoundNumber"])
    if incoming and params.get("session") in SESSION_NAMES:
        ss.ob_session = params["session"]
    elif "ob_session" not in ss and ss.get("selected_race", (None, None))[:2] == (year, round_number):
        ss.ob_session = ss.selected_race[2]
    kind = st.sidebar.selectbox("Session", list(SESSION_NAMES), format_func=SESSION_NAMES.get, key="ob_session")
    if incoming:
        requested = [d.strip().upper() for d in params.get("drivers", "").split(",") if d.strip()][:2]
        ss.ob_requested_drivers = ((year, round_number, kind), requested)
        ss.ob_requested_laps = ((year, round_number, kind), params)

    with st.spinner("Loading the session with car telemetry (the first time takes up to a minute)..."):
        try:
            weekend = cached_weekend(year, round_number, kind)
        except TimingUnavailable as exc:
            st.warning(str(exc), icon=":material/cloud_off:")
            st.stop()
        except Exception as exc:  # e.g. no sprint at this event
            st.error(f"Couldn't load {SESSION_NAMES[kind]} for this event: {exc}")
            st.stop()

    drivers = weekend.drivers()
    if len(drivers) < 2:
        st.warning("Fewer than two drivers set a lap time in this session.")
        st.stop()
    requested_key, requested_drivers = ss.pop("ob_requested_drivers", (None, []))
    if requested_key == (year, round_number, kind):
        requested = [d for d in requested_drivers if d in set(drivers["Driver"])]
        if requested:
            ss.ob_a = requested[0]
            ss.ob_prev_a = requested[0]
            if len(requested) > 1:
                ss.ob_b = requested[1]
    mode = st.sidebar.segmented_control("Comparison", ["Fastest laps", "Choose laps"], default="Fastest laps",
                                        key="ob_mode", required=True)
    a, b = pick_drivers(drivers, allow_same=mode == "Choose laps")
    request_key, lap_request = ss.pop("ob_requested_laps", (None, {}))
    lap_a = lap_b = None
    if mode == "Choose laps":
        lap_a, lap_b = pick_laps(weekend, a, b, (year, round_number, kind),
                                lap_request if request_key == (year, round_number, kind) else {})
    current = {"year": str(year), "round": str(round_number), "session": kind, "drivers": f"{a},{b}"}
    if mode == "Choose laps":
        current["mode"] = "laps"
        current.update({key: str(value) for key, value in (("lap_a", lap_a), ("lap_b", lap_b)) if value is not None})
    if dict(st.query_params) != current:
        st.query_params.from_dict(current)
    ss.ob_link = tuple(sorted(current.items()))
    ui.sidebar_footer()

    if a == b and lap_a == lap_b:
        st.info("Choose two different laps to compare this driver's tyre age or race phases.")
        st.stop()

    try:
        with st.spinner("Loading both laps' telemetry..."):
            data = cached_compare(weekend, (year, round_number, kind), a, b, lap_a, lap_b, validity_version=3)
    except (ValueError, TimingUnavailable) as exc:
        st.warning(str(exc))
        st.stop()
    except Exception as exc:
        st.warning(f"Couldn't load telemetry for the selected laps: {exc}. Choose another lap or session.")
        st.stop()

    if a == b and data.ref.lap_number == data.other.lap_number:
        st.info("Both selections resolve to the same lap. Choose a different comparison lap.")
        st.stop()
    a, b = data.labels

    aligned = align(data.ref.telemetry, data.other.telemetry)
    sectors = minisectors(aligned)
    corners = corner_speeds(data.ref.telemetry, data.other.telemetry, data.corners)
    gap = (data.other.lap_time - data.ref.lap_time).total_seconds()
    ref_color, other_color = data.colors

    ui.header(
        f"{year} · Round {round_number} · {data.session_name}",
        f"{a} vs {b}",
        f"{data.name} · {'selected laps' if mode == 'Choose laps' else 'fastest laps'} · data: {data.source}",
        title_html=f'<span style="color:{ref_color}">{a}</span> <span style="opacity:.45">vs</span> '
        f'<span style="color:{other_color}">{b}</span>',
    )
    won = int((sectors["Faster"] == "ref").sum())
    sector_stats = [
        ui.stat(f"Sector {n + 1}",
                f"{a if data.ref.sectors[n] <= data.other.sectors[n] else b}",
                small=f"by {abs((data.other.sectors[n] - data.ref.sectors[n]).total_seconds()):.3f}")
        for n in range(3)
        if pd.notna(data.ref.sectors[n]) and pd.notna(data.other.sectors[n])
    ]
    ui.strip([
        ui.stat(a, format_lap_time(data.ref.lap_time), small=f"{data.ref.compound.title()} · {data.ref.tyre_life:.0f} laps"),
        ui.stat(b, format_lap_time(data.other.lap_time), small=f"{gap:+.3f} s"),
        *sector_stats,
        ui.stat("Mini-sectors", f"{a} {won} · {b} {len(sectors) - won}"),
        ui.stat("Top speed", f"{data.ref.telemetry['Speed'].max():.0f} · {data.other.telemetry['Speed'].max():.0f}",
                small="km/h"),
    ])

    sector_gaps = [
        (o - r).total_seconds() if pd.notna(o) and pd.notna(r) else float("nan")
        for r, o in zip(data.ref.sectors, data.other.sectors)
    ]
    ui.insight(summarise(a, b, gap, sector_gaps, corners))

    marks = sector_distances(data.ref.telemetry, data.ref.sectors)
    lap_len = float(aligned["Distance"].max())
    bounds = [0.0, *marks, lap_len]
    ranges = {"Full lap": None}
    if len(marks) == 2:
        ranges.update({f"Sector {n}": (bounds[n - 1] - 30, bounds[n] + 30) for n in (1, 2, 3)})

    with st.container(border=True, key="card-telemetry"):
        with st.container(horizontal=True, vertical_alignment="center"):
            ui.label("Telemetry")
            zoom = st.segmented_control("Zoom", list(ranges), key="ob_zoom", required=True, default="Full lap",
                                        label_visibility="collapsed")
        ui.note("Top panel: the gap along the lap, shaded in the colour of whoever is ahead. "
                "Dotted lines mark corners, solid lines the sector boundaries.")
        if data.dashes[1] == "dash":
            ui.note(f"Shared team colour: {a} is the solid line; {b} is dashed. "
                    f"The gap is above zero for {a}, below for {b}.")
        st.plotly_chart(telemetry_figure(data, aligned, marks, ranges.get(zoom)), width="stretch", key="ob_tel")

    left, right = st.columns([6, 5], gap="large")
    with left, st.container(border=True, key="card-map"):
        ui.label("Who was faster where")
        ui.note("The lap split into 25 equal mini-sectors, each in the colour of the quicker driver.")
        st.plotly_chart(track_map(data, sectors), width="stretch", key="ob_map")
    with right, st.container(border=True, key="card-corners"):
        ui.label("Corner by corner")
        ui.note("Time gained through each corner; hover for minimum speeds.")
        st.plotly_chart(corner_gains(corners, a, b, ref_color=ref_color, other_color=other_color,
                                    distinguish=data.dashes[1] == "dash"), width="stretch", key="ob_corners")
        with st.expander("Table"):
            table = corners.rename(
                columns={"RefMinSpeed": f"{a} km/h", "OtherMinSpeed": f"{b} km/h", "SpeedDiff": "Diff",
                         "Gain": f"{a} gain (s)"}
            )[["Corner", f"{a} km/h", f"{b} km/h", "Diff", f"{a} gain (s)"]]
            st.dataframe(table, hide_index=True, width="stretch")
