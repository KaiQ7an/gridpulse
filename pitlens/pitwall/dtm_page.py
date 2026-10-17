"""DTM championship, weekend classifications and driver comparisons."""

import html
import os
from datetime import UTC, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pitlens import plotstyle
from pitlens.drivers.profiles import profile as driver_profile
from pitlens.dtm import data
from pitlens.dtm import teams as team_data
from pitlens.dtm.cars import model, profile
from pitlens.pitwall import driver_intro, dtm_nav, milestone_cards, ui

VIEWS = {"championship": "Championship", "weekend": "Race weekends", "drivers": "Drivers",
         "compare": "Driver comparison", "teams": "Teams"}
VIEW_STATE = {"championship": ("dtm_category",), "weekend": ("dtm_event", "dtm_session"),
              "compare": ("dtm_drivers",), "teams": ("dtm_team",), "drivers": ("dtm_profile",)}
STATE = ("dtm_year", "dtm_view", "dtm_event", "dtm_session", "dtm_drivers", "dtm_category", "dtm_team", "dtm_profile")


@st.cache_data(ttl=1800, show_spinner=False)
def load(year: int, refresh: bool = False, offline: bool = False) -> tuple[dict, str]:
    if not offline and (refresh or year == datetime.now(UTC).year):
        try:
            return data.fetch(year), "Official feed"
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return data.saved(year), "Saved snapshot · official feed unavailable"
    return data.saved(year), "Saved snapshot"


def apply_link():
    ss = st.session_state
    params = dict(st.query_params)
    signature = tuple(sorted(params.items()))
    if not params or signature == ss.get("dtm_link"):
        return
    ss.dtm_link = signature
    try:
        year = int(params.get("year", "0"))
        event = int(params.get("event", "0"))
    except ValueError:
        return
    if year in data.YEARS:
        ss.dtm_year = year
    if params.get("view") in VIEWS:
        ss.dtm_view = params["view"]
    if event:
        ss.dtm_event = event
    if params.get("session"):
        ss.dtm_session = params["session"]
    if "drivers" in params:
        ss.dtm_drivers = list(dict.fromkeys(params["drivers"].split(",")))[:4]
    if "team" in params:
        ss.dtm_team = params["team"]
    if "driver" in params:
        ss.dtm_profile = params["driver"]


def sync_link():
    ss = st.session_state
    params = {"year": str(ss.dtm_year), "view": ss.dtm_view}
    if ss.dtm_view == "weekend":
        params.update(event=str(ss.dtm_event), session=ss.dtm_session)
    if ss.dtm_view == "compare":
        params["drivers"] = ",".join(ss.dtm_drivers)
    if ss.dtm_view == "teams" and ss.get("dtm_team") != "all":
        params["team"] = ss.dtm_team
    if ss.dtm_view == "drivers":
        params["driver"] = ss.dtm_profile
    if dict(st.query_params) != params:
        st.query_params.from_dict(params)
    ss.dtm_link = tuple(sorted(params.items()))
    ss.dtm_saved = {**ss.get("dtm_saved", {}), **{k: ss[k] for k in STATE if k in ss}}


def render():
    ss = st.session_state
    # Restore only widgets rendered on this run. Recreating hidden widget keys
    # leaves Python holding a value while the remounted browser shows its default.
    for k in ("dtm_year", "dtm_view"):
        if k in ss.get("dtm_saved", {}):
            ss.setdefault(k, ss.dtm_saved[k])
    apply_link()
    if ss.pop("dtm_open_weekend", False):
        ss.dtm_view = "weekend"
    if ss.get("dtm_year") not in data.YEARS:
        ss.dtm_year = data.YEARS[0]
    if ss.get("dtm_view") not in VIEWS:
        ss.dtm_view = "championship"
    ui.sidebar_brand("DTM · GT racing")
    year = st.sidebar.selectbox("DTM season", data.YEARS, key="dtm_year")
    dtm_nav.render(VIEWS)
    for k in VIEW_STATE[ss.dtm_view]:
        if k in ss.get("dtm_saved", {}):
            ss.setdefault(k, ss.dtm_saved[k])
    refresh = st.sidebar.button("Refresh data", icon=":material/refresh:", key="dtm_refresh", width="stretch",
                                help="Check the official DTM feed for updated classifications.")
    if refresh:
        load.clear()
        ss.dtm_refresh_year = year
    with st.spinner("Loading DTM classifications…"):
        season, source = load(year, ss.get("dtm_refresh_year") == year, bool(os.getenv("PITLENS_OFFLINE")))
    ui.sidebar_footer("DTM")
    ui.header(f"DTM · {year} season", "GT racing, closer.",
              "Two races per weekend. Follow the championship, open a classification, compare the drivers.")
    races = data.race_rows(season)
    race_count = sum(s["kind"] == "race" for e in season["events"] for s in e["sessions"])
    ui.strip([ui.stat("Race weekends", str(len(season["events"]))), ui.stat("Published races", str(race_count)),
              ui.stat("Drivers", str(races.driver.nunique())), ui.stat("Manufacturers", str(races.manufacturer.nunique()))])
    stamp = datetime.fromisoformat(season["fetched_at"]).strftime("%d %b %Y, %H:%M UTC")
    st.caption(f"{source} · fetched {stamp}. " +
               ("The official feed marks these standings provisional." if season["provisional"] else "Published standings."))
    if "unavailable" in source:
        st.info("Showing the saved official snapshot. Use Refresh official data to try again.")
    if ss.dtm_view == "championship":
        championship(season)
    elif ss.dtm_view == "weekend":
        weekend(season)
    elif ss.dtm_view == "compare":
        compare(season)
    elif ss.dtm_view == "drivers":
        drivers(season)
    else:
        teams(season)
    sync_link()
    with st.expander("Data sources & coverage"):
        st.markdown(f"[DTM results]({season['source']}?season={year}) · "
                    f"[DTM standings]({season['standings_url']}?season={year}) · "
                    "[Official race calendar](https://www.dtm.com/en/events)")
        st.write("2023–2026: published practice, qualifying and race classifications; official driver, team and "
                 "manufacturer standings. Current-season data refreshes every 30 minutes while in use. "
                 "Historical seasons use saved snapshots; the refresh button checks the official feed.")
        st.write("Points and championship positions come directly from DTM, including qualifying points. "
                 "Qualifying groups stay separate. A qualifying position is not presented as a starting-grid slot. "
                 "The feed does not supply the lap-by-lap telemetry needed for an F1-style replay.")


def color(entry: dict, category: str, meta: dict) -> str:
    manufacturer = (meta.get(entry["key"], {}).get("manufacturer", "") if category == "drivers" else
                    entry["name"] if category == "manufacturers" else
                    next((r["manufacturer"] for r in meta.values() if data.key(r["team"]) == entry["key"]), ""))
    return data.COLORS.get(data.MANUFACTURERS.get(manufacturer, manufacturer), "#A0A8B6")


def points_chart(season: dict, selected: list[str], category="drivers") -> go.Figure:
    progress = data.progress(season, category)
    meta, fig, used = data.entrants(season), go.Figure(), {}
    for entry in season["standings"][category]:
        if entry["key"] not in selected:
            continue
        points = progress[progress.key == entry["key"]]
        shade = color(entry, category, meta)
        dash = ["solid", "dash", "dot", "dashdot"][used.get(shade, 0) % 4]
        used[shade] = used.get(shade, 0) + 1
        fig.add_trace(go.Scatter(x=points.race, y=points.points, name=entry["name"], mode="lines+markers",
                                 line=dict(color=shade, width=2.5, dash=dash),
                                 customdata=points[["event", "earned"]],
                                 hovertemplate="%{customdata[0]}<br>%{y:g} points (+%{customdata[1]:g})<extra>%{fullData.name}</extra>"))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=15, b=10), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.2), uirevision=f"dtm-{season['year']}-{category}")
    fig.update_xaxes(title="Race (two per weekend)", dtick=1)
    fig.update_yaxes(title="Cumulative published points", rangemode="tozero")
    plotstyle.apply(fig)
    return fig


def championship(season: dict):
    ss = st.session_state
    if ss.get("dtm_category") not in ("drivers", "teams", "manufacturers"):
        ss.dtm_category = "drivers"
    category = st.segmented_control("Championship", ["drivers", "teams", "manufacturers"],
                                    format_func=str.title, key="dtm_category", required=True)
    board = season["standings"][category]
    if len(board) > 1:
        gap = board[0]["points"] - board[1]["points"]
        ui.insight(f"Published P1: {board[0]['name']} · {board[0]['points']:g} points · "
                   f"{gap:g} points ahead of {board[1]['name']}.")
    meta = data.entrants(season)
    table = pd.DataFrame([{"Pos": int(r["position"]) if r["position"] else None, "Name": r["name"], "Points": r["points"],
                           **({"Team": meta.get(r["key"], {}).get("team", ""),
                               "Car model": meta.get(r["key"], {}).get("model", "–"),
                               "Manufacturer": meta.get(r["key"], {}).get("manufacturer", "")} if category == "drivers" else {}),
                           "Race pts": r["race_points"], "Quali pts": r["qualifying_points"]}
                          for r in board])
    left, right = st.columns([5, 7], gap="large")
    with left, st.container(border=True):
        ui.label(f"{category} · official order")
        st.dataframe(table, hide_index=True, width="stretch", height=460,
                     column_config={"Quali pts": st.column_config.NumberColumn(help="Published qualifying points, already included in Points.")})
        st.download_button("Download standings", table.to_csv(index=False), f"dtm-{season['year']}-{category}.csv", "text/csv")
    with right, st.container(border=True):
        ui.label("The points race")
        options = [r["key"] for r in board]
        names = {r["key"]: r["name"] for r in board}
        picker = f"dtm_lines_{category}_{season['year']}"
        selected = st.multiselect("Follow up to six", options, default=options[:4], format_func=names.get,
                                  max_selections=6, key=picker)
        if selected:
            st.plotly_chart(points_chart(season, selected, category), width="stretch", key="dtm_points")
        else:
            st.info("Choose an entry to follow its points through the season.")
        ui.note("Hover a race for its points allocation. Click a legend entry to hide it; double-click to isolate it.")
    calendar(season)


def calendar(season: dict):
    ui.label("Race calendar · choose a weekend")
    ui.note("Select a row to open its practice, qualifying and both races.")
    rows = []
    for event in season["events"]:
        wins = [next((r["name"] for r in s["rows"] if r["position"] == 1 and not r["status"]), "–")
                for s in event["sessions"] if s["kind"] == "race"]
        rows.append({"Round": event["round"], "Circuit": event["name"], "Country": event["country"],
                     "From": event["start"], "To": event["end"], "Race 1 winner": wins[0] if wins else "Pending",
                     "Race 2 winner": wins[1] if len(wins) > 1 else "Pending"})
    selected = st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", on_select="rerun",
                             selection_mode="single-row",
                             key=f"dtm_calendar_{season['year']}_{st.session_state.get('dtm_calendar_nonce', 0)}")
    if selected.selection.rows:
        event = season["events"][selected.selection.rows[0]]
        st.session_state.dtm_event = event["round"]
        # The sidebar radio was already instantiated: switch before it is built next run.
        st.session_state.dtm_open_weekend = True
        st.session_state.dtm_calendar_nonce = st.session_state.get("dtm_calendar_nonce", 0) + 1
        st.rerun()


def weekend(season: dict):
    ss = st.session_state
    events = {e["round"]: e for e in season["events"]}
    if ss.get("dtm_event") not in events:
        ss.dtm_event = max(events)
    selected = st.selectbox("Race weekend", list(events), format_func=lambda r: f"R{r} · {events[r]['name']}", key="dtm_event")
    event = events[selected]
    ui.header(f"Round {selected} · {event['country']}", event["name"], f"{event['start']} — {event['end']}")
    if event["length_m"]:
        st.caption(f"Official listed circuit length: {event['length_m'] / 1000:.3f} km")
    st.link_button("Official circuit & event guide", event["url"], icon=":material/open_in_new:")
    sessions = {s["key"]: s for s in event["sessions"]}
    if not sessions:
        st.info("No classifications have been published for this weekend yet.")
        ss.dtm_session = ""
        return
    if ss.get("dtm_session") not in sessions:
        ss.dtm_session = next((s["key"] for s in reversed(event["sessions"]) if s["kind"] == "race"), next(iter(sessions)))
    session_key = st.selectbox("Session", list(sessions), format_func=lambda k: sessions[k]["name"], key="dtm_session")
    session = sessions[session_key]
    st.caption(f"Session start: {session['start'][:16].replace('T', ' ')} UTC" +
               (" · Provisional official classification" if session["provisional"] else ""))
    rows = session["rows"]
    fastest = [r for r in rows if r["status"] not in ("DSQ", "DNS") and data.seconds(r["fastest_lap"]) is not None]
    if fastest:
        best = min(fastest, key=lambda r: data.seconds(r["fastest_lap"]))
        ui.strip([ui.stat("Classified P1", next((r["name"] for r in rows if r["position"] == 1 and not r["status"]), "–")),
                  ui.stat("Best lap in classification", best["fastest_lap"], small=best["name"])])
    table = pd.DataFrame([{"Pos": r["position"], "No": r["number"], "Driver": r["name"], "Team": r["team"],
                           "Manufacturer": r["manufacturer"], "Car model": model(season["year"], r["manufacturer"]),
                           "Time": r["time"], "Gap": r["gap"],
                           "Laps": r["laps"], "Best lap": r["fastest_lap"], "Stops": r["pitstops"],
                           "Status": r["status"] or "Classified",
                           **({"Race pts": r["race_points"], "Quali pts": r["qualifying_points"],
                               "Total pts": r["total_points"]} if session["kind"] == "race" else {})} for r in rows])
    st.dataframe(table, hide_index=True, width="stretch", height=550)
    st.download_button("Download classification", table.to_csv(index=False),
                       f"dtm-{season['year']}-r{selected}-{session_key}.csv", "text/csv")
    if "Group" in session["name"]:
        st.info("This is one qualifying group. Its P1 is the group leader, not a claim of overall pole or grid position.")
    ui.note("Race points and qualifying points are shown separately; Total pts already includes both. "
            "Best lap is a driver's quickest lap in this classification, not their average race pace.")


def compare(season: dict):
    ss = st.session_state
    board = season["standings"]["drivers"]
    options, names = [r["key"] for r in board], {r["key"]: r["name"] for r in board}
    if "dtm_drivers" not in ss:
        ss.dtm_drivers = options[:2]
    ss.dtm_drivers = [d for d in ss.dtm_drivers if d in options][:4]
    selected = st.multiselect("Compare drivers", options, key="dtm_drivers", max_selections=4, format_func=names.get)
    if not selected:
        st.info("Choose up to four drivers to compare their published season results.")
        return
    table = data.comparison(season, selected)
    st.dataframe(table.set_index("Driver").T.astype("string").fillna("–"), width="stretch")
    st.plotly_chart(points_chart(season, selected), width="stretch", key="dtm_comparison_points")
    results, fig = data.race_rows(season), go.Figure()
    meta = data.entrants(season)
    labels = [f"R{e['round']} · {s['name']}" for e in season["events"] for s in e["sessions"] if s["kind"] == "race"]
    for i, driver in enumerate(selected):
        subset = results[results.driver == driver].copy()
        subset["label"] = "R" + subset["round"].astype(str) + " · " + subset.session
        subset["position"] = subset.position.where(subset.status == "")
        subset = subset.set_index("label").reindex(labels)
        fig.add_trace(go.Scatter(x=labels, y=subset.position, name=names[driver], mode="lines+markers", connectgaps=False,
                                 line=dict(color=data.COLORS.get(meta.get(driver, {}).get("manufacturer"), "#A0A8B6"),
                                           dash=["solid", "dash", "dot", "dashdot"][i]),
                                 customdata=subset[["event", "session"]],
                                 hovertemplate="%{customdata[0]} · %{customdata[1]}<br>P%{y:g}<extra>%{fullData.name}</extra>"))
    fig.update_xaxes(categoryorder="array", categoryarray=labels)
    fig.update_yaxes(title="Classified finish", autorange="reversed", dtick=1)
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))
    plotstyle.apply(fig)
    ui.label("Classified finishes")
    st.plotly_chart(fig, width="stretch", key="dtm_comparison_finishes")
    ui.note("DNF, DNS and DSQ are excluded from the finish chart and counted in the table. "
            "Colours identify manufacturers; line patterns distinguish drivers.")
    st.download_button("Download driver comparison", table.to_csv(index=False),
                       f"dtm-{season['year']}-comparison.csv", "text/csv")


def teams(season: dict):
    st.html('<style>.dtm-team-photo:hover{transform:scale(1.025)}'
            'a:focus-visible .dtm-team-photo{outline:2px solid #55bfff;outline-offset:3px}</style>')
    active = team_data.participants(season)
    options = ["all", *active]
    if st.session_state.get("dtm_team") not in options:
        st.session_state.dtm_team = "all"
    selected = st.selectbox("Team", options, format_func=lambda k: "All participating teams" if k == "all" else active[k]["name"],
                            key="dtm_team")
    ui.label(f"{season['year']} · participating teams")
    ui.note("Only teams with published race appearances in this season are listed, including guests. "
            "Sponsor names are grouped under the operating team; the official championship table stays unchanged.")
    races = data.race_rows(season)
    columns = st.columns(2, gap="large") if selected == "all" else [st.container()]
    for i, team_id in enumerate(active if selected == "all" else [selected]):
        info = active[team_id]
        results = races[races.team.isin(info["entries"])]
        classified = results[results.status == ""]
        with columns[i % len(columns)], st.container(border=True):
            st.subheader(info["name"])
            ui.strip([ui.stat("Headquarters", info.get("base") or "Not verified"),
                      ui.stat("Founded", info.get("founded") or "Not verified")])
            ui.label("Team history")
            st.write(info["history"])
            milestone_cards.render("dtm", "teams", team_id, season["year"])
            ui.label(f"Selected historical honours · through {season['year']}")
            honours = [h for h in info.get("honors", []) if h["year"] <= season["year"]]
            if honours:
                for honour in honours:
                    st.markdown(f"- **{honour['year']}** · [{honour['text']}]({honour['source']})")
            else:
                st.caption("Historical honours research pending; season results are shown below.")
            st.caption(f"{season['year']} entrant names: " + " · ".join(sorted(info["entries"])))
            ui.strip([ui.stat("Season race wins", str(int((classified.position == 1).sum()))),
                      ui.stat("Season podiums", str(int(classified.position.le(3).sum()))),
                      ui.stat("Season drivers", str(results.driver.nunique()))])
            for brand in sorted(results.manufacturer.unique()):
                car = profile(season["year"], brand)
                st.markdown(f"**{season['year']} car · {car['name']}**")
                photo = car.get("photo")
                # Only use the team-owned image for its own team and generation.
                # Other teams get an explicitly labelled model reference, never a claimed team photo.
                own_photo = info.get("photo_brand") == brand and (
                    (team_id in ("manthey", "emil-frey", "hrt", "comtoyou", "abt") and season["year"] == 2026)
                    or (team_id == "schubert" and season["year"] >= 2025)
                    or (team_id == "doerr" and season["year"] >= 2024))
                if photo:
                    src, alt = html.escape(photo["url"], quote=True), html.escape(car["name"], quote=True)
                    st.html(f'<a href="{src}" target="_blank" rel="noopener noreferrer" '
                            f'aria-label="Open car photograph: {alt}"><img src="{src}" alt="{alt}" loading="lazy" '
                            'style="width:100%;height:280px;object-fit:contain;background:rgba(128,128,128,.06);'
                            'border-radius:8px;transition:transform .18s" class="dtm-team-photo"></a>')
                    st.caption("Team-published car photograph; shown livery may differ between drivers." if own_photo else
                               "Model reference photograph; not this team’s season livery.")
                    st.markdown(f"Photo source: [{photo['credit']}]({photo['source']})")
            entries = results[["driver", "name", "number", "model"]].drop_duplicates().copy()
            entries["Profile"] = entries.driver.map(lambda d: f"/dtm?year={season['year']}&view=drivers&driver={d}")
            entries["name"] = [driver_profile("dtm", d).get("name") or n
                               for d, n in zip(entries.driver, entries.name)]
            st.dataframe(entries.drop(columns="driver").rename(columns={"name": "Driver", "number": "No", "model": "Car model"}),
                         hide_index=True, width="stretch", column_config={"Profile": st.column_config.LinkColumn(display_text="Driver profile")})
            with st.expander("Profile sources & scope"):
                st.write(info.get("facts_note", "Facts refer to the operating team; unverified founding dates and bases are left blank."))
                st.write("History is a current background profile. The honours list is filtered through the selected year and is not an exhaustive trophy count.")
                for j, source in enumerate(info["sources"], 1):
                    st.markdown(f"[Official team / series reference {j}]({source})")


def drivers(season: dict):
    entries = data.entrants(season)
    order = [r["key"] for r in season["standings"]["drivers"] if r["key"] in entries]
    order += sorted(set(entries) - set(order), key=lambda d: entries[d]["name"])
    if st.session_state.get("dtm_profile") not in order:
        st.session_state.dtm_profile = order[0]
    names = {d: driver_profile("dtm", d).get("name") or entries[d]["name"] for d in order}
    selected = st.selectbox("Driver", order, format_func=names.get, key="dtm_profile")
    entry = entries[selected]
    ui.header(f"{season['year']} · DTM driver", names[selected])
    driver_intro.render("dtm", selected, season["year"], entry["name"], team=entry["team"], car=entry["model"])
    all_rows = data.race_rows(season)
    rows = all_rows[all_rows.driver == selected]
    classified = rows[rows.status == ""]
    ui.strip([ui.stat("Race appearances", str(len(rows))), ui.stat("Wins", str(int((classified.position == 1).sum()))),
              ui.stat("Podiums", str(int(classified.position.le(3).sum())))])
    ui.label("The season · race by race")
    st.dataframe(rows[["round", "event", "session", "team", "model", "position", "status", "total_points"]].rename(
        columns={"round": "Round", "event": "Circuit", "session": "Race", "team": "Team", "model": "Car model",
                 "position": "Position", "status": "Status", "total_points": "Points incl. qualifying"}),
        hide_index=True, width="stretch")
