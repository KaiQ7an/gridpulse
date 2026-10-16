"""Teams page of the pit wall: one team's season, its drivers, the teammate battle and its pit crew."""

import html

import pandas as pd
import streamlit as st

from pitlens.pitwall import charts, ui
from pitlens.teams.facts import facts
from pitlens.teams.season import Season, drivers_of, load_season, pit_crews, seasons_saved, standings, teammate_battles


@st.cache_resource(show_spinner=False, max_entries=3)
def cached_season(year: int) -> Season:
    return load_season(year)


def render() -> None:
    ui.sidebar_brand("Teams, a season at a time")
    years = seasons_saved()
    if not years:
        st.info("No saved seasons yet: run `pitlens snapshot --year 2026` first.")
        st.stop()
    link = (st.query_params.get("year"), st.query_params.get("team"))
    if link[0] and st.session_state.get("team_link") != link:  # a shared link: open that season and team
        st.session_state.team_link = link
        if link[0].isdigit() and int(link[0]) in years:
            st.session_state.team_year = int(link[0])
        if link[1]:
            st.session_state.team_pick = link[1]
    year = st.sidebar.selectbox("Season", years, key="team_year")
    ui.sidebar_footer()

    with st.spinner("Adding up the season..."):
        season = cached_season(year)
    table = standings(season)
    if table.empty:
        st.info(f"No {year} races saved yet.")
        st.stop()
    teams = table["Team"].tolist()
    if st.session_state.get("team_pick") not in teams:
        st.session_state.team_pick = teams[0]
    team = st.pills("Team", teams, key="team_pick", label_visibility="collapsed", width="stretch")
    team = team or teams[0]
    color_pills(teams, season.colors)
    if dict(st.query_params) != {"year": str(year), "team": team}:  # keep the address shareable
        st.query_params.from_dict({"year": str(year), "team": team})
        st.session_state.team_link = (str(year), team)
    color = season.colors.get(team, "#888888")
    rank = teams.index(team) + 1
    row = table.set_index("Team").loc[team]
    drivers = drivers_of(season, team)
    info = facts(team, year)

    names = " · ".join(drivers["FullName"].head(3))
    ui.header(f"{year} season · constructors' P{rank}", team, f"{names}" + (f" · {info['power']} power" if info
                                                                         and info.get("power") else ""),
              title_html=f'<span style="display:inline-block;width:10px;height:0.9em;background:{color};'
                         f'border-radius:2px;margin-right:12px;vertical-align:-2px"></span>{html.escape(team)}')
    strip(season, team, row, drivers)
    if info:
        titles = f"{info['titles']}" + (f" ({info['note']})" if info.get("note") else "")
        ui.strip([ui.stat("Base", info["base"]), ui.stat("Power unit", info.get("power") or "–"),
                  ui.stat("In F1 since", info["since"]), ui.stat("Constructors' titles", titles)])

    left, right = st.columns([5, 7], gap="large")
    with left, st.container(border=True, key="card-team-drivers"):
        ui.label("Drivers")
        ui.team_drivers(drivers, teammate_battles(season, team), color)
    with right, st.container(border=True, key="card-team-results"):
        ui.label("Race by race")
        ui.note("Where each driver finished every Grand Prix; a cross for a retirement.")
        main = drivers.sort_values("Races", ascending=False)["Driver"].head(2).tolist()
        st.plotly_chart(charts.team_results_chart(season.results, season.rounds, main, color), width="stretch",
                        key="chart_team_results")

    left, right = st.columns(2, gap="large")
    with left, st.container(border=True, key="card-team-standings"):
        ui.label("Constructors' championship")
        ui.note("Points from every Grand Prix and sprint so far.")
        st.plotly_chart(charts.constructors_chart(table, season.colors, team), width="stretch",
                        key="chart_constructors", config={"displayModeBar": False})
    with right, st.container(border=True, key="card-team-crew"):
        ui.label("Pit crew")
        crews = pit_crews(season)
        if team in set(crews["Team"]):
            crew = crews.set_index("Team").loc[team]
            fastest = season.stops[(season.stops["Team"] == team) & season.stops["Stationary"].notna()]
            fastest = fastest.loc[fastest["Stationary"].idxmin()]
            event = season.rounds.set_index("Round")["Location"].get(int(fastest["Round"]), "")
            ui.note(f"Median {crew['Median']:.2f} s stood still over {int(crew['Stops'])} stops, "
                    f"{_ordinal(list(crews['Team']).index(team) + 1)} of {len(crews)} teams. Quickest: "
                    f"{fastest['Stationary']:.1f} s for {fastest['Driver']} in {event}. Penalty stops and repairs "
                    "are left out.")
            st.plotly_chart(charts.pit_crews_chart(crews, season.colors, team), width="stretch", key="chart_crews",
                            config={"displayModeBar": False})
        else:
            ui.note("Not enough stationary times for this team this season (F1 doesn't publish them for "
                    "every race).")
    if season.missing:
        ui.note(f"Rounds not saved yet: {', '.join(map(str, season.missing))}.")


def strip(season: Season, team: str, row, drivers: pd.DataFrame) -> None:
    gp = season.results[(season.results["Team"] == team) & (season.results["Kind"] == "R")]
    poles = int((season.quali[season.quali["Team"] == team]["Position"] == 1).sum())
    best = int(gp["Position"].min()) if gp["Position"].notna().any() else None
    dnfs = int((~gp["Classified"] & ~gp["Dsq"]).sum())
    both = gp.groupby("Round").filter(lambda w: (w["Position"] <= 10).sum() == 2)["Round"].nunique()
    ui.strip([
        ui.stat("Points", f"{row['Points']:.0f}"),
        ui.stat("Wins", str(int(row["Wins"]))),
        ui.stat("Podiums", str(int(row["Podiums"]))),
        ui.stat("Poles", str(poles)),
        ui.stat("Best finish", f"P{best}" if best else "–"),
        ui.stat("Both in the points", str(both), small=f"of {gp['Round'].nunique()}"),
        ui.stat("Retirements", str(dnfs)),
    ])


def color_pills(teams: list[str], colors: dict[str, str]) -> None:
    """Team colours on the team pills: a bar before each name, and the chosen one outlined in its colour.

    Streamlit can't colour pills, so CSS picks them out by position (they're in the order of `teams`).
    """
    rules = []
    for i, team in enumerate(teams, start=1):
        c = colors.get(team, "#888888")
        pill = f'.st-key-team_pick [data-testid="stButtonGroup"] > div > button:nth-child({i})'
        rules.append(f'{pill}::before {{ content: ""; width: 4px; height: 14px; border-radius: 2px; '
                     f"background: {c}; margin-right: 8px; flex: none; }}")
        rules.append(f'{pill}[aria-checked="true"] {{ border-color: {c} !important; color: inherit !important; '
                     f"background: color-mix(in srgb, {c} 16%, transparent) !important; }}")
    st.html("<style>" + "".join(rules) + "</style>")


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
