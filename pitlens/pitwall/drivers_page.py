"""Drivers page of the pit wall: one driver's season, weekend by weekend, and against their teammate."""

import html

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, ui
from pitlens.pitwall.teams_page import cached_season
from pitlens.season.data import (
    driver_highlights,
    driver_season,
    driver_standings,
    points_by_round,
    seasons_saved,
    teammate_battles,
)


def render() -> None:
    ui.sidebar_brand("Drivers, a season at a time")
    years = seasons_saved()
    if not years:
        st.info("No saved seasons yet: run `pitlens snapshot --year 2026` first.")
        st.stop()
    ss = st.session_state
    link = (st.query_params.get("year"), st.query_params.get("driver"))
    if link[0] and ss.get("driver_link") != link:  # a shared link: open that season and driver
        ss.driver_link = link
        if link[0].isdigit() and int(link[0]) in years:
            ss.driver_year = int(link[0])
        if link[1]:
            ss.driver_pick = link[1].upper()
    year = st.sidebar.selectbox("Season", years, key="driver_year")
    ui.sidebar_footer()

    with st.spinner("Adding up the season..."):
        season = cached_season(year)
    table = driver_standings(season)
    if table.empty:
        st.info(f"No {year} races saved yet.")
        st.stop()
    drivers = table["Driver"].tolist()
    if ss.get("driver_pick") not in drivers:
        ss.driver_pick = drivers[0]
    label = {r.Driver: f"P{i} · {r.FullName} · {r.Team}" for i, r in enumerate(table.itertuples(), start=1)}
    driver = st.selectbox("Driver", drivers, key="driver_pick", format_func=label.get, label_visibility="collapsed")
    if dict(st.query_params) != {"year": str(year), "driver": driver}:  # keep the address shareable
        st.query_params.from_dict({"year": str(year), "driver": driver})
        ss.driver_link = (str(year), driver)

    me = table.set_index("Driver").loc[driver]
    rows = driver_season(season, driver)
    team = me["Team"]
    color = season.colors.get(team, "#888888")
    teams = list(dict.fromkeys(rows["Team"]))
    ui.header(f"{year} season · drivers' P{drivers.index(driver) + 1}", str(me["FullName"]),
              " then ".join(teams),
              title_html=f'<span style="display:inline-block;width:10px;height:0.9em;background:{color};'
                         f'border-radius:2px;margin-right:12px;vertical-align:-2px"></span>'
                         f'{html.escape(str(me["FullName"]))}')
    strips(rows, me, season, driver)

    left, right = st.columns(2, gap="large")
    with left, st.container(border=True, key="card-driver-races"):
        ui.label("Grid to flag")
        ui.note("Where they started (hollow) and finished (filled) every Grand Prix: green for places gained, "
                "red for places lost.")
        st.plotly_chart(charts.driver_results_chart(rows, color), width="stretch", key="chart_driver_races")
    with right, st.container(border=True, key="card-driver-points"):
        ui.label("Points through the season")
        progress = points_by_round(season)
        leader = drivers[0]
        mates = teammates(season, driver)[:1]
        lines = [(driver, driver, color)]
        lines += [(m, f"{m} (leader)" if m == leader else m, color) for m in mates]
        if leader != driver and leader not in mates:
            lines.append((leader, f"{leader} (leader)", season.colors.get(table.iloc[0]["Team"], "#888888")))
        ui.note("Points after each round, races and sprints, against "
                + ("the teammate." if leader == driver or leader in mates else "the teammate and the leader."))
        st.plotly_chart(charts.points_progress_chart(progress, lines, season.rounds), width="stretch",
                        key="chart_driver_points")

    left, right = st.columns([7, 4], gap="large")
    with left, st.container(border=True, key="card-driver-table"):
        ui.label("Weekend by weekend")
        ui.note("Finishing positions: gold, silver and bronze for the podium, green in the points, red for a "
                "retirement; a purple ring for pole and a purple underline for the race's fastest lap. Points "
                "include the sprint. Each Grand Prix opens its replay.")
        ui.driver_results_table(rows, year)
    with right, st.container(border=True, key="card-driver-highlights"):
        ui.label("Highlights")
        items = driver_highlights(rows)
        if items:
            ui.highlights(items)
        else:
            ui.note("Nothing stands out yet: no points finishes this season.")
    if season.missing:
        ui.note(f"Rounds not saved yet: {', '.join(map(str, season.missing))}.")


def teammates(season, driver: str) -> list[str]:
    """Everyone who shared a team with `driver` in a race this season, most races together first."""
    gp = season.results[season.results["Kind"] == "R"]
    mine = gp[gp["Driver"] == driver][["Round", "Team"]]
    shared = gp.merge(mine, on=["Round", "Team"])
    shared = shared[shared["Driver"] != driver]
    return shared["Driver"].value_counts().index.tolist()


def strips(rows: pd.DataFrame, me, season, driver: str) -> None:
    races = len(rows)
    classified = rows[rows["Classified"] & rows["Position"].notna()]
    started = classified[classified["Grid"].notna() & (classified["Grid"] > 0)]
    gained = (started["Grid"] - started["Position"]).mean() if len(started) else float("nan")
    dnfs = int((~rows["Classified"] & ~rows["Dsq"]).sum())
    ui.strip([
        ui.stat("Points", f"{me['Points']:g}"),
        ui.stat("Wins", str(me["Wins"])),
        ui.stat("Podiums", str(me["Podiums"])),
        ui.stat("Poles", str(me["Poles"])),
        ui.stat("Fastest laps", str(me["FastestLaps"])),
        ui.stat("Laps led", str(me["LapsLed"])),
        ui.stat("Retirements", str(dnfs), small=f"of {races}"),
    ])
    battles = [teammate_battles(season, t) for t in rows["Team"].unique()]
    mine = pd.concat(battles).query("Driver == @driver") if battles else pd.DataFrame()
    started_at = rows.loc[rows["Grid"] > 0, "Grid"]
    stats = [
        ui.stat("Average grid", f"{started_at.mean():.1f}" if len(started_at) else "–"),
        ui.stat("Average finish", f"{classified['Position'].mean():.1f}" if len(classified) else "–",
                small="when classified"),
        ui.stat("Places gained", f"{gained:+.1f}" if pd.notna(gained) else "–", small="a race",
                tip="Grid slot minus finishing position, averaged over the races they finished"),
        ui.stat("Points a race", f"{me['Points'] / races:.1f}" if races else "–"),
    ]
    if not mine.empty:
        b = mine.sum(numeric_only=True)
        stats += [ui.stat("Beat teammate", f"{int(b['QualiWon'])}/{int(b['QualiOf'])}", small="qualifying"),
                  ui.stat("Beat teammate", f"{int(b['RaceWon'])}/{int(b['RaceOf'])}", small="races")]
    ui.strip(stats)
