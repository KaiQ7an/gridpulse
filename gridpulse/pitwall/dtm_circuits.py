"""DTM circuit atlas using the same map, cards and record presentation as Formula 1."""

import html
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gridpulse import plotstyle
from gridpulse.dtm import circuits as reference
from gridpulse.dtm import data
from gridpulse.pitwall import styles, ui
from gridpulse.pitwall.atlas_map import atlas_map

REGIONS = {
    "world": {"name": "World", "title": "A world built for racing.", "center": [12, 50]},
    "europe": {"name": "Europe", "title": "DTM across Germany, Austria and the Netherlands.",
               "center": [10, 50], "bounds": [-2, 43, 21, 56]},
}


def navigate(slug="all", region="world"):
    st.session_state.dtm_circuit = slug
    st.session_state.dtm_region = region


def change_region():
    st.session_state.dtm_circuit = "all"


@st.cache_data(show_spinner=False, max_entries=8)
def facts_for(year: int, stamp: str, _season: dict) -> list[dict]:
    archive = {y: _season if y == year else data.saved(y) for y in data.YEARS if y <= year}
    result = []
    for fact in reference.venues(_season):
        history = reference.history(fact, year, _season, archive=archive)
        fastest = history["fastest"]
        result.append({**fact, "history": history, "preview": {"races": history["races"], "coverage": f"2023–{year}"},
                       "record": {"time": fastest["fastest_lap"], "driver": fastest["name"], "year": fastest["year"]} if fastest else {}})
    return result


def map_view(facts: list[dict], region: str, selected: str | None = None):
    key = f"dtm-atlas-{region}-{selected or 'all'}"
    # Send only the map's public display fields, not entire classifications.
    pins = [{k: c[k] for k in ("slug", "name", "city", "country", "region", "lat", "lon", "length_km", "opened", "preview", "record")}
            for c in facts]
    event = atlas_map(region, selected, key=key, circuit_data=pins, regions=REGIONS, series="DTM")
    if not isinstance(event, dict) or not event.get("id"):
        return
    consumed = st.session_state.get("dtm_atlas_clicks", {})
    if consumed.get(key) == event["id"]:
        return
    st.session_state.dtm_atlas_clicks = {**consumed, key: event["id"]}
    if event.get("kind") == "region" and event.get("value") in REGIONS:
        navigate(region=event["value"])
        st.rerun()
    if event.get("kind") == "circuit" and event.get("value") in {c["slug"] for c in facts}:
        navigate(event["value"], "europe")
        st.rerun()


def plan(fact: dict, height=150):
    src, alt = html.escape(fact["plan"], quote=True), html.escape(fact["name"], quote=True)
    st.html(f'<a href="{src}" target="_blank" rel="noopener noreferrer" aria-label="Open {alt} circuit plan">'
            f'<img src="{src}" alt="DTM layout: {alt}" loading="lazy" '
            f'style="width:100%;height:{height}px;object-fit:contain;border-radius:8px;background:#fff;padding:12px;box-sizing:border-box"></a>')


def leaders(counter):
    if not counter:
        return "—", "No eligible classification in the covered archive."
    best = max(counter.values())
    return str(best), " / ".join(sorted(name for name, count in counter.items() if count == best))


def render(season: dict):
    styles.inject("atlas.css")
    st.html(Path(__file__).with_name("atlas_map") / "bridge.html", unsafe_allow_javascript=True)
    facts = facts_for(season["year"], season["fetched_at"], season)
    by_slug = {c["slug"]: c for c in facts}
    ss = st.session_state
    if ss.get("dtm_circuit") not in ["all", *by_slug]:
        ss.dtm_circuit = "all"
    if ss.get("dtm_region") not in REGIONS:
        ss.dtm_region = "world"
    if ss.dtm_circuit != "all":
        ss.dtm_region = "europe"
    st.selectbox("Jump to a circuit", ["all", *by_slug], key="dtm_circuit",
                 format_func=lambda slug: "World atlas" if slug == "all" else f"{by_slug[slug]['name']} · {by_slug[slug]['country']}")
    st.pills("Explore regions", list(REGIONS), key="dtm_region", format_func=lambda r: REGIONS[r]["name"],
             on_change=change_region, label_visibility="collapsed")
    if ss.dtm_circuit != "all":
        render_fact(by_slug[ss.dtm_circuit], facts, season)
        return
    ui.header(f"DTM circuit atlas · {season['year']} · {len(facts)} venues", "A world built for racing.",
              "Explore the map, hover a circuit and open its story, DTM layout and covered race history.")
    map_view(facts, ss.dtm_region or "world")
    query = st.text_input("Find a circuit", key="dtm_circuit_search", placeholder="Search circuit, city or country",
                          icon=":material/search:").strip().casefold()
    visible = [c for c in facts if query in f"{c['name']} {c['city']} {c['country']}".casefold()]
    st.caption(f"{len(visible)} of {len(facts)} circuits on the selected season’s calendar.")
    if not visible:
        st.info("No matching circuits. Change or clear your search.")
    for i, fact in enumerate(visible):
        if i % 3 == 0:
            columns = st.columns(3, gap="medium")
        with columns[i % 3], st.container(border=True, height="stretch", key=f"card-atlas-circuit-{fact['slug']}"):
            st.html(f'<div class="atlas-card-country">{html.escape(fact["country"])}</div>'
                    f'<div class="atlas-card-city">{html.escape(fact["city"])}</div>'
                    f'<div class="atlas-card-name">{html.escape(fact["name"])}</div>')
            plan(fact)
            st.caption(f"{fact['length_km']:.3f} km · {fact['kind']} · opened {fact['opened']}")
            st.button(f"Explore {fact['city']}", key=f"dtm-circuit-open-{fact['slug']}", on_click=navigate,
                      args=(fact["slug"], "europe"), width="stretch")
    ui.label("Compare circuits")
    selected = st.multiselect("Circuits to compare", list(by_slug), max_selections=3, key="dtm_circuit_compare",
                              format_func=lambda slug: by_slug[slug]["name"])
    if selected:
        table = pd.DataFrame([{"Circuit": by_slug[s]["name"], "DTM listed length (km)": by_slug[s]["length_km"],
                               "Opened": by_slug[s]["opened"], "Covered races": by_slug[s]["history"]["races"]} for s in selected])
        fig = go.Figure(go.Bar(x=table["Circuit"], y=table["DTM listed length (km)"], marker_color="#ff453e",
                               hovertemplate="%{x}<br>%{y:.3f} km<extra></extra>"))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=15, b=10), yaxis_title="DTM listed length (km)")
        st.plotly_chart(plotstyle.apply(fig), width="stretch", key="dtm_circuit_lengths")
        st.dataframe(table, hide_index=True, width="stretch")


def render_fact(fact: dict, facts: list[dict], season: dict):
    with st.container(horizontal=True):
        st.button("World atlas", on_click=navigate, icon=":material/public:")
        st.button("Europe", on_click=navigate, kwargs={"region": "europe"}, icon=":material/arrow_back:")
    ui.header(f"DTM circuit file · {fact['country']}", fact["city"], fact["name"])
    history = fact["history"]
    ui.strip([ui.stat("DTM listed length", f"{fact['length_km']:.3f} km"), ui.stat("Circuit type", fact["kind"]),
              ui.stat("Venue opened", str(fact["opened"])), ui.stat("Covered DTM races", str(history["races"]))])
    left, right = st.columns([6, 5], gap="large")
    with left, st.container(border=True, key="card-atlas-profile"):
        ui.label("The circuit & its history")
        plan(fact, 270)
        st.write(fact["description"])
        st.caption("Length and diagram use the DTM reference layout; other championships may use a different configuration.")
        st.markdown(f"[Venue history]({fact['history_source']}) · [Official DTM event guide]({fact['event']['url']})")
    with right:
        map_view(facts, "europe", fact["slug"])
    ui.label("DTM circuit history")
    st.caption(f"Covered archive: 2023–{season['year']}, through the selected season. These are archive bests, not all-time DTM records. "
               "Qualifying groups are excluded from combined-session P1 counts; layouts can differ between years.")
    columns = st.columns(3, gap="medium")
    with columns[0], st.container(border=True, height="stretch", key="card-atlas-record"):
        ui.label("Fastest covered race lap")
        record = history["fastest"]
        st.html(f'<div class="atlas-record-time">{html.escape(record["fastest_lap"]) if record else "—"}</div>')
        if record:
            st.write(record["name"])
            st.caption(f"{record['year']} · {record['session']}")
    for col, field, title in zip(columns[1:], ("wins", "poles"), ("Most covered wins", "Most qualifying P1s")):
        with col, st.container(border=True, height="stretch", key=f"card-atlas-{field}"):
            count, names = leaders(history[field])
            ui.label(title)
            st.html(f'<div class="atlas-record-count">{count}</div>')
            st.write(names)
    ui.label("Year by year · DTM weekends")
    st.dataframe(pd.DataFrame(history["weekends"]), hide_index=True, width="stretch")
    event = fact["event"]
    params = urlencode({"year": season["year"], "view": "weekend", "event": event["round"], "session": "race-1"})
    st.link_button(f"Open {season['year']} race weekend", f"/dtm?{params}", icon=":material/calendar_month:")
    st.caption("Race and qualifying classifications: official DTM feed. Disqualified laps are excluded from covered bests.")
