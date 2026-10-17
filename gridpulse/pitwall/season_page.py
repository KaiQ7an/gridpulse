"""Season page of the pit wall: the championship so far, round by round."""

from datetime import date

import pandas as pd
import streamlit as st

from gridpulse.pitwall import charts, ui
from gridpulse.pitwall.navigation import select_season
from gridpulse.pitwall.teams_page import cached_season
from gridpulse.season.data import (
    driver_standings,
    leaders_by_round,
    points_by_round,
    pole_sitters,
    round_winners,
    seasons_saved,
    standings,
)

TOP_LINES = 6  # drivers drawn on the points chart


def render() -> None:
    ui.sidebar_brand("The championship, round by round")
    years = seasons_saved()
    if not years:
        st.info("No saved seasons yet: run `gridpulse snapshot --year 2026` first.")
        st.stop()
    ss = st.session_state
    link = st.query_params.get("year")
    if link and ss.get("season_link") != link:  # a shared link: open that season
        ss.season_link = link
        if link.isdigit() and int(link) in years:
            ss.season_year = int(link)
    year = select_season(years, key="season_year")
    ui.sidebar_footer()
    if dict(st.query_params) != {"year": str(year)}:  # keep the address shareable
        st.query_params.from_dict({"year": str(year)})
        ss.season_link = str(year)

    with st.spinner("Adding up the season..."):
        season = cached_season(year)
    drivers, teams = driver_standings(season), standings(season)
    if len(drivers) < 2:
        st.info(f"No {year} races saved yet.")
        st.stop()
    winners = round_winners(season)
    progress = points_by_round(season)
    ui.header(*headline(year, drivers, teams, winners, complete=season.complete))
    strip(season, drivers, winners, progress)

    left, right = st.columns([5, 7], gap="large")
    with left, st.container(border=True, key="card-season-drivers"):
        ui.label("Drivers' championship")
        ui.note("Points from every Grand Prix and sprint. Each driver opens their season.")
        ui.standings_table(drivers, season.colors, year)
    with right, st.container(border=True, key="card-season-progress"):
        ui.label("Points through the season")
        ui.note(f"The current top {TOP_LINES}, followed through every round; teammates share a colour, the second dashed.")
        lines = [(d.Driver, d.Driver, season.colors.get(d.Team, "#888888"))
                 for d in drivers.head(TOP_LINES).itertuples()]
        st.plotly_chart(charts.points_progress_chart(progress, lines, season.rounds), width="stretch",
                        key="chart_season_progress")
        ui.label("Who led the championship")
        ui.highlights(lead_spells(leaders_by_round(progress, season), drivers, season.rounds))

    left, right = st.columns([5, 7], gap="large")
    with left, st.container(border=True, key="card-season-teams"):
        ui.label("Constructors' championship")
        st.plotly_chart(charts.constructors_chart(teams, season.colors), width="stretch", key="chart_season_teams",
                        config={"displayModeBar": False})
    with right, st.container(border=True, key="card-season-teams-progress"):
        ui.label("Constructors through the season")
        lines = [(t, short_team(t), season.colors.get(t, "#888888")) for t in teams["Team"].head(5)]
        st.plotly_chart(charts.points_progress_chart(points_by_round(season, by="Team"), lines, season.rounds,
                                                     legend=False),
                        width="stretch", key="chart_season_teams_progress")

    with st.container(border=True, key="card-season-matrix"):
        ui.label("Every result")
        ui.note("Each driver's Grand Prix finishes, round by round: gold, silver and bronze for the podium, green "
                "in the points, red for a retirement; a purple ring for pole and a purple underline for the "
                "fastest lap. Each round number opens its replay.")
        fastest = season.fastest.set_index("Round")["Driver"].to_dict()
        ui.results_matrix(season.results, drivers, season.rounds, pole_sitters(season).to_dict(), fastest,
                          season.colors, year)

    with st.container(border=True, key="card-season-winners"):
        ui.label("Round by round")
        ui.round_winners_table(winners, season.results, season.colors, year)
    if season.missing:
        ui.note(f"Rounds not saved yet: {', '.join(map(str, season.missing))}.")
    if season.missing_sprints:
        ui.note(f"Sprint results not saved yet: rounds {', '.join(map(str, season.missing_sprints))}.")


def headline(year: int, drivers: pd.DataFrame, teams: pd.DataFrame, winners: pd.DataFrame, *,
             complete: bool = False) -> tuple[str, str, str]:
    first, second = drivers.iloc[0], drivers.iloc[1]
    margin = first["Points"] - second["Points"]
    gap = "level on points with" if margin == 0 else f"by {margin:g} point{'' if margin == 1 else 's'} from"
    rounds = len(winners)
    if year < date.today().year and complete:
        return (f"{year} season · final standings after {rounds} rounds", f"{year} championship",
                f"{first['FullName']} champion {gap} {second['FullName']}; "
                f"{teams.iloc[0]['Team']} take the constructors' title.")
    coverage = "saved standings" if year < date.today().year else "standings"
    return (f"{year} season · {coverage} through round {int(winners['Round'].max())}", f"{year} championship",
            f"{first['FullName']} leads {gap} {second['FullName']} after {rounds} rounds; "
            f"{teams.iloc[0]['Team']} lead the constructors.")


def strip(season, drivers: pd.DataFrame, winners: pd.DataFrame, progress: pd.DataFrame) -> None:
    leaders = leaders_by_round(progress, season)
    most_wins = drivers.sort_values("Wins", ascending=False, kind="stable").iloc[0]
    most_poles = drivers.sort_values("Poles", ascending=False, kind="stable").iloc[0]
    sprints = int(season.results.loc[season.results["Kind"] == "S", "Round"].nunique())
    ui.strip([
        ui.stat("Grands Prix", str(len(winners)), small=f"+ {sprints} sprints" if sprints else ""),
        ui.stat("Different winners", str(winners["Winner"].nunique())),
        ui.stat("Different pole sitters", str(winners["Pole"].nunique())),
        ui.stat("Most wins", most_wins["Driver"], small=str(most_wins["Wins"])),
        ui.stat("Most poles", most_poles["Driver"], small=str(most_poles["Poles"])),
        ui.stat("Lead changes", str(int((leaders != leaders.shift()).sum() - 1)),
                tip="Times the championship lead changed hands after a round"),
    ])


def lead_spells(leaders: pd.Series, drivers: pd.DataFrame, rounds: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Each run of rounds one driver led the championship after, as highlights: name, rounds, how many."""
    names = drivers.set_index("Driver")["FullName"]
    spells, out = (leaders != leaders.shift()).cumsum(), []
    for _, run in leaders.groupby(spells):
        first, last, n = run.index[0], run.index[-1], len(run)
        span = f"Round {first}" if n == 1 else f"Rounds {first} to {last}"
        out.append((names.get(run.iloc[0], run.iloc[0]), span, f"{n} round{'' if n == 1 else 's'}"))
    return out


def short_team(team: str) -> str:
    """A team name short enough to sit at the end of a line: Red Bull Racing -> Red Bull, Haas F1 Team -> Haas."""
    for suffix in (" F1 Team", " Racing", " F1"):
        team = team.removesuffix(suffix)
    return team
