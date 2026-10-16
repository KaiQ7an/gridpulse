"""Circuit atlas: the world, its racing regions, circuit facts and saved race analysis."""

import base64
import html

import numpy as np
import pandas as pd
import streamlit as st

from pitlens import snapshots
from pitlens.onboard.compare import rotate
from pitlens.pitwall import charts, ui
from pitlens.pitwall.atlas_map import atlas_map
from pitlens.season.atlas import REGIONS, catalog, circuit_fact, in_region, record_holders
from pitlens.season.circuits import circuit_years, circuits, saved_races

NEW_RULES = 2026  # the year the cars changed: lap times before it aren't comparable


def cached_races() -> pd.DataFrame:
    return _cached_races(snapshots.revision())


@st.cache_data(show_spinner=False, max_entries=2)
def _cached_races(revision: tuple) -> pd.DataFrame:
    return saved_races()


def cached_years(circuit: int) -> pd.DataFrame:
    return _cached_years(circuit, snapshots.revision())


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_years(circuit: int, revision: tuple) -> pd.DataFrame:
    return circuit_years(cached_races(), circuit)


def cached_track(year: int, round_number: int) -> dict | None:
    return _cached_track(year, round_number, snapshots.revision(year))


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_track(year: int, round_number: int, revision: tuple) -> dict | None:
    parts = snapshots.load_race(year, round_number, "R")
    return parts["track"] if parts else None


def render() -> None:
    ui.sidebar_brand("The world of Formula 1 circuits")
    inject_atlas_css()
    requested = st.query_params.get("circuit")
    fact = circuit_fact(requested)
    region = fact["region"] if fact else st.query_params.get("region", "world")
    if region not in REGIONS:
        region = "world"
    if requested and not fact:
        st.warning("That circuit isn't in the atlas. Choose a circuit below.")
    canonical = {"region": region} if region != "world" else {}
    if fact:
        canonical["circuit"] = fact["slug"]
    if dict(st.query_params) != canonical:
        st.query_params.from_dict(canonical)

    ss = st.session_state
    ss.atlas_jump = fact["slug"] if fact else "world"
    choices = ["world"] + [c["slug"] for c in sorted(catalog(), key=lambda c: (c["country"], c["city"]))]
    st.sidebar.selectbox("Jump to a circuit", choices, key="atlas_jump", on_change=jump_to_circuit,
                         format_func=lambda s: f"{circuit_fact(s)['country']} · {circuit_fact(s)['city']}"
                         if s != "world" else "World atlas")
    ui.sidebar_footer()
    ss.atlas_region = region
    st.pills("Explore regions", list(REGIONS), key="atlas_region", on_change=change_region,
             format_func=lambda r: REGIONS[r]["name"], label_visibility="collapsed")
    if fact:
        render_fact(fact)
    else:
        render_atlas(region)


def navigate(region: str = "world", circuit: str | None = None) -> None:
    params = {"region": region} if region != "world" else {}
    if circuit:
        params["circuit"] = circuit
    st.query_params.from_dict(params)


def jump_to_circuit() -> None:
    fact = circuit_fact(st.session_state.atlas_jump)
    navigate(fact["region"], fact["slug"]) if fact else navigate()


def change_region() -> None:
    navigate(st.session_state.atlas_region or "world")


def map_view(region: str, selected: str | None = None) -> None:
    key = f"atlas-map-{region}-{selected or 'overview'}"
    event = atlas_map(region, selected, key=key)
    if not isinstance(event, dict) or not event.get("id"):
        return
    consumed = dict(st.session_state.get("atlas_clicks", {}))
    if consumed.get(key) == event["id"]:
        return
    consumed[key] = event["id"]
    st.session_state.atlas_clicks = consumed
    if event.get("kind") == "region" and event.get("value") in REGIONS:
        navigate(event["value"])
        st.rerun()
    elif event.get("kind") == "circuit" and (fact := circuit_fact(event.get("value"))):
        navigate(fact["region"], fact["slug"])
        st.rerun()


def render_atlas(region: str) -> None:
    facts = in_region(region)
    ui.header(f"Circuit atlas · {REGIONS[region]['name']} · {len(facts)} venues", REGIONS[region]["title"],
              "Explore the map. Open a circuit for its story, records and every saved Grand Prix.")
    map_view(region)
    if region == "world":
        columns = st.columns(4, gap="small")
        for col, (key, info) in zip(columns, [(k, v) for k, v in REGIONS.items() if k != "world"]):
            with col, st.container(border=True, key=f"card-atlas-region-{key}"):
                st.html(f'<div class="atlas-region-name">{html.escape(info["name"])}</div>'
                        f'<div class="atlas-card-meta">{len(in_region(key))} circuits</div>')
                st.button(f"Explore {info['name']}", key=f"atlas-region-{key}", on_click=navigate, args=(key,),
                          icon=":material/arrow_outward:", width="stretch")
    ui.label("Find your next circuit")
    search = st.text_input("Find a circuit", placeholder="Search by circuit, city or country", icon=":material/search:",
                           label_visibility="collapsed", key="atlas_search").strip().casefold()
    facts = [c for c in facts if search in f"{c['name']} {c['city']} {c['country']}".casefold()]
    if not facts:
        st.info("No matching circuits in this region. Try another name or choose World.")
        return
    table = circuits(cached_races())
    for start in range(0, len(facts), 3):
        columns = st.columns(3, gap="medium")
        for col, c in zip(columns, facts[start:start + 3]):
            with col, st.container(border=True, key=f"card-atlas-circuit-{c['slug']}"):
                outline = outline_for(c["key"], table)
                st.html(f'<div class="atlas-card-country">{html.escape(c["country"])}</div>'
                        f'<div class="atlas-card-city">{html.escape(c["city"])}</div>'
                        f'<div class="atlas-card-name">{html.escape(c["name"])}</div>'
                        f'{outline_svg(outline)}'
                        f'<div class="atlas-card-meta">{c["length_km"]:.3f} km <span>·</span> {c["kind"]}'
                        f' <span>·</span> Since {c["first_gp"]}</div>')
                st.button(f"Explore {c['city']}", key=f"atlas-open-{c['slug']}", on_click=navigate,
                          args=(c["region"], c["slug"]), icon=":material/arrow_forward:", width="stretch")


def outline_for(key: int, table: pd.DataFrame) -> dict | None:
    rows = table[table["Circuit"] == key]
    if rows.empty:
        return None
    here = rows.iloc[0]
    parts = snapshots.race_metadata(int(here["Year"]), int(here["Round"]))
    return parts.get("track") if parts else None


def outline_svg(track: dict | None) -> str:
    if not track or len(track.get("x", [])) < 2:
        return '<div class="atlas-outline-empty">CIRCUIT FILE</div>'
    x, y = rotate(track["x"], track["y"], track["rotation"])
    scale = min(190 / max(np.ptp(x), 1), 100 / max(np.ptp(y), 1))
    x, y = (x - np.mean([x.min(), x.max()])) * scale + 110, -(y - np.mean([y.min(), y.max()])) * scale + 60
    step = max(1, len(x) // 240)
    points = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(x[::step], y[::step]))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 120">'
           f'<polyline points="{points}" fill="none" stroke="#a3b0c1" stroke-width="2.3" '
           f'stroke-linecap="round" stroke-linejoin="round"/>'
           f'<circle cx="{x[0]:.1f}" cy="{y[0]:.1f}" r="3" fill="#ff302b"/></svg>')
    encoded = base64.b64encode(svg.encode()).decode()
    return f'<img class="atlas-outline" src="data:image/svg+xml;base64,{encoded}" alt="Circuit outline">'


def render_fact(fact: dict) -> None:
    region = fact["region"]
    with st.container(horizontal=True, gap="small"):
        st.button("World atlas", on_click=navigate, icon=":material/public:")
        st.button(REGIONS[region]["name"], on_click=navigate, args=(region,), icon=":material/arrow_back:")
    ui.header(f"Circuit file · {fact['country']}", fact["city"], fact["name"])
    ui.strip([ui.stat("Circuit length", f"{fact['length_km']:.3f} km"),
              ui.stat("Grand Prix laps", str(fact["laps"])),
              ui.stat("First Grand Prix", str(fact["first_gp"]), small=f"{fact['history']['races']} races at this venue"),
              ui.stat("Circuit type", fact["kind"])])
    table = circuits(cached_races())
    left, right = st.columns([6, 5], gap="large")
    with left, st.container(border=True, key="card-atlas-profile"):
        ui.label("The circuit")
        st.html('<div class="atlas-profile-outline">' + outline_svg(outline_for(fact["key"], table)) + '</div>')
        st.write(fact["description"])
    with right:
        map_view(region, fact["slug"])
    history = fact["history"]
    ui.label("Circuit history")
    cutoff = pd.Timestamp(history["as_of"]).strftime("%-d %B %Y")
    ui.note(f"World Championship Grands Prix at this venue, through {cutoff}. Wins and pole starts cover all "
            "recorded layouts at the venue; the published race lap record belongs to the referenced layout.")
    record = fact["record"]
    columns = st.columns(3, gap="medium")
    with columns[0], st.container(border=True, key="card-atlas-record"):
        ui.label("Race lap record")
        st.html(f'<div class="atlas-record-time">{html.escape(record.get("time") or "Not published")}</div>')
        st.write(record.get("driver") or "No record holder published")
        if record.get("year"):
            st.caption(str(record["year"]))
        st.markdown(f"[F1 circuit reference]({fact['facts_source']})")
    for col, field, label in zip(columns[1:], ("wins", "poles"), ("Most wins", "Most pole starts")):
        with col, st.container(border=True, key=f"card-atlas-{field}"):
            ui.label(label)
            leaders = history[field]
            st.html(f'<div class="atlas-record-count">{leaders[0]["count"] if leaders else "–"}</div>')
            st.write(record_holders(leaders))
            for leader in leaders:
                years = ", ".join(map(str, leader["years"]))
                st.caption((leader["driver"] + ": " if len(leaders) > 1 else "") + years)
    with st.expander("Sources and record definitions"):
        st.markdown(f"Layout facts and race lap record: [Formula 1]({fact['facts_source']}). "
                    f"Historical wins and starting grids: [Jolpica results]({history['wins_source']}) · "
                    f"[pole starts]({history['poles_source']}). Reference updated {cutoff}.")
        st.write("Pole starts count the driver recorded in grid position one for the Grand Prix, including "
                 "grid penalties. Sprints are excluded. Tied record holders are all shown. Venue history can "
                 "include earlier layouts; race lap records are separate from qualifying and outright fastest laps.")
        st.write("Geography: Natural Earth (public domain). The globe's connecting lines are a visual guide, "
                 "not a season calendar. Europe & Caucasus groups Baku with the European venues for browsing.")
    rows = table[table["Circuit"] == fact["key"]]
    if rows.empty:
        ui.note("No saved race data here yet. Circuit facts and historical records are available above.")
        return
    here = rows.iloc[0]
    render_saved_history(fact["key"], here)


def render_saved_history(circuit: int, here) -> None:
    years = cached_years(circuit)
    if years.empty:
        st.info("No saved Grand Prix here yet.")
        st.stop()
    saved = years["Year"].astype(str).tolist()
    ui.label("From your saved races")
    ui.note(f"Grands Prix saved here: {', '.join(saved)}. The analysis below uses those races only.")
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
    known_grid = years["WinnerGrid"].notna() & (years["WinnerGrid"] > 0)
    stats = [ui.stat("Laps", str(latest["Scheduled"]))]
    if pd.notna(latest["PitLoss"]):
        vsc = f"{latest['PitLossVsc']:.0f} s under VSC" if pd.notna(latest["PitLossVsc"]) else ""
        stats.append(ui.stat("Pit stop costs", f"{latest['PitLoss']:.0f} s", small=vsc,
                             tip="Time lost to a stop against staying out, from MultiViewer"))
    stats += [
        ui.stat("Won from pole", f"{int((years['WinnerGrid'] == 1).sum())} of {int(known_grid.sum())}",
                small=f"grid unknown in {int((~known_grid).sum())}" if not known_grid.all() else "",
                tip="Only races with a known winner's starting grid count in this comparison"),
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


def inject_atlas_css() -> None:
    st.html('''<style>
      .atlas-card-country { color:#ff3a32;font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700 }
      .atlas-card-city { font-size:26px;font-weight:850;letter-spacing:-.7px;margin:7px 0 4px }
      .atlas-card-name { opacity:.55;font-size:12px;min-height:32px }
      .atlas-card-meta { opacity:.6;font:11px ui-monospace,monospace;margin:12px 0 }
      .atlas-card-meta span { margin:0 4px;opacity:.5 }
      .atlas-outline { display:block;width:100%;height:108px;color:#a3b0c1;margin:6px auto }
      .atlas-outline-empty { height:120px;display:grid;place-content:center;opacity:.2;font:11px ui-monospace,monospace;letter-spacing:4px }
      .atlas-profile-outline .atlas-outline { height:200px;margin:0 }
      .atlas-record-time { color:#bd8aff;font-size:36px;font-weight:800;letter-spacing:-1.5px;margin:12px 0 }
      .atlas-record-count { font-size:42px;font-weight:850;letter-spacing:-2px;margin:6px 0 }
      .atlas-region-name { font-size:16px;font-weight:750;min-height:42px }
      [class*="st-key-card-atlas-circuit-"] { transition:border-color .18s,background .18s }
      [class*="st-key-card-atlas-circuit-"]:hover { border-color:#a73b37;background:rgba(255,40,32,.025) }
      @media(max-width:750px) { .atlas-record-time { font-size:28px } }
    </style>''')
