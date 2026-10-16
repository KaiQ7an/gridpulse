"""A season, team by team: results, points, qualifying, teammate battles and pit stops.

Built from the saved races (snapshots) so a whole season loads in seconds. Drivers are tied to
a team race by race, so a mid-season swap (Lawson and Tsunoda in 2025) lands in the right place.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pitlens import snapshots
from pitlens.pitwall.events import fastest_lap_candidates
from pitlens.undercut.analysis import ordinary_stationary_times, pit_stops

RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]
FINISHED = ("Finished", "Lapped")

# Completed calendars, verified against F1's results and FastF1's event schedules.
# https://www.formula1.com/en/results/2025/races (and the equivalent archived seasons).
# Unknown years remain provisional until their completed calendar is recorded here.
COMPLETED_CALENDARS = {
    2018: (21, ()), 2019: (21, ()), 2020: (17, ()),
    2021: (22, (10, 14, 19)), 2022: (22, (4, 11, 21)),
    2023: (22, (4, 9, 12, 17, 18, 20)),
    2024: (24, (5, 6, 11, 19, 21, 23)), 2025: (24, (2, 6, 13, 19, 21, 23)),
}


@dataclass
class Season:
    year: int
    rounds: pd.DataFrame  # Round, Event, Location, Sprint (bool), in calendar order
    results: pd.DataFrame  # Round, Kind (R/S), Driver, FullName, Team, Grid, Position, Status, Points, Classified, Dsq
    quali: pd.DataFrame  # Round, Driver, Team, Position, Part (furthest part reached), Q1, Q2, Q3 (s)
    stops: pd.DataFrame  # Round, Driver, Team, LaneTime, Stationary, StillOk
    led: pd.DataFrame  # Round, Kind, Driver, Laps (laps completed in the lead)
    fastest: pd.DataFrame  # Round, Driver, LapTime (s): each Grand Prix's fastest lap
    colors: dict[str, str]  # team -> "#rrggbb"
    missing: list[int]  # finished rounds with no saved race

    @property
    def missing_sprints(self) -> list[int]:
        _, expected = COMPLETED_CALENDARS.get(self.year, (0, ()))
        saved = set(self.results.loc[self.results["Kind"] == "S", "Round"])
        return sorted(set(expected) - saved)

    @property
    def complete(self) -> bool:
        calendar = COMPLETED_CALENDARS.get(self.year)
        if calendar is None or self.missing or self.missing_sprints:
            return False
        return set(self.results.loc[self.results["Kind"] == "R", "Round"]) == set(range(1, calendar[0] + 1))


def seasons_saved() -> list[int]:
    """Seasons with saved races, newest first."""
    years = [int(p.name) for p in snapshots.SNAPSHOT_DIR.glob("*") if p.name.isdigit()]
    return sorted((y for y in years if len(snapshots.races(y)) >= 3), reverse=True)


FASTEST_LAP_POINT = range(2019, 2025)  # a point for the fastest lap, to a driver who finished in the top ten


def points_for(position, kind: str) -> int:
    table = RACE_POINTS if kind == "R" else SPRINT_POINTS
    if pd.isna(position) or not 1 <= int(position) <= len(table):
        return 0
    return table[int(position) - 1]


def load_season(year: int) -> Season:
    rounds = snapshots.races(year).sort_values("RoundNumber")
    result_rows, quali_rows, stop_rows, led_rows, fastest_rows, colors, missing = [], [], [], [], [], {}, []
    for r in rounds.itertuples():
        for kind in ("R", "S"):
            parts = snapshots.load_race(year, int(r.RoundNumber), kind)
            if parts is None:
                if kind == "R":
                    missing.append(int(r.RoundNumber))
                continue
            rows = _results(parts["results"], int(r.RoundNumber), kind)
            result_rows.append(rows)
            colors.update(_colors(parts["results"]))
            laps = parts["laps"]
            if "Position" in laps:
                led = laps[laps["Position"] == 1].groupby("Driver").size()
                led_rows += [{"Round": int(r.RoundNumber), "Kind": kind, "Driver": d, "Laps": int(n)}
                             for d, n in led.items()]
            if kind == "R":
                # A disqualified driver's laps are struck from the result, fastest lap included.
                dsq = rows.loc[rows["Dsq"], "Driver"]
                candidates = fastest_lap_candidates(laps[~laps["Driver"].isin(dsq)])
                if not candidates.empty:
                    best = candidates.loc[candidates["LapTime"].idxmin()]
                    fastest_rows.append({"Round": int(r.RoundNumber), "Driver": best["Driver"],
                                         "LapTime": best["LapTime"].total_seconds()})
                    if year in FASTEST_LAP_POINT and not _has_points(parts["results"]):
                        rows.loc[(rows["Driver"] == best["Driver"]) & (rows["Position"] <= 10), "Points"] += 1
            stops = pit_stops(parts["laps"], parts.get("stationary"))
            if not stops.empty:
                team = dict(zip(parts["results"]["Abbreviation"], parts["results"]["TeamName"]))
                stop_rows.append(stops.assign(Round=int(r.RoundNumber), Kind=kind, Team=stops["Driver"].map(team)))
        q = snapshots.load_quali(year, int(r.RoundNumber), "Q")
        if q is not None:
            quali_rows.append(q.results.assign(Round=int(r.RoundNumber)))
    results = pd.concat(result_rows, ignore_index=True) if result_rows else pd.DataFrame()
    if year in COMPLETED_CALENDARS:
        expected = set(range(1, COMPLETED_CALENDARS[year][0] + 1))
        saved = set(results.loc[results["Kind"] == "R", "Round"]) if not results.empty else set()
        missing = sorted(expected - saved)
    quali = pd.concat(quali_rows, ignore_index=True) if quali_rows else pd.DataFrame(
        columns=["Round", "Driver", "Team", "Position", "Q1", "Q2", "Q3", "Out"])
    stops = pd.concat(stop_rows, ignore_index=True) if stop_rows else pd.DataFrame(
        columns=["Round", "Driver", "Team", "LaneTime", "Stationary"])
    if not stops.empty:
        stops["StillOk"] = ordinary_stationary_times(stops)
    rounds = pd.DataFrame({"Round": rounds["RoundNumber"].astype(int), "Event": rounds["EventName"],
                           "Location": rounds["Location"],
                           "Sprint": rounds["EventFormat"].astype(str).str.contains("sprint")})
    return Season(year=year, rounds=rounds.reset_index(drop=True), results=results, quali=quali, stops=stops,
                  led=pd.DataFrame(led_rows, columns=["Round", "Kind", "Driver", "Laps"]),
                  fastest=pd.DataFrame(fastest_rows, columns=["Round", "Driver", "LapTime"]),
                  colors=colors, missing=missing)


def _results(res: pd.DataFrame, round_number: int, kind: str) -> pd.DataFrame:
    status = res["Status"].fillna("").astype(str)
    dsq = status.str.contains("Disqualif", case=False)
    official = pd.to_numeric(res["Points"], errors="coerce") if "Points" in res else pd.Series(np.nan, index=res.index)
    computed = [0 if d else points_for(p, kind) for p, d in zip(res["Position"], dsq)]
    return pd.DataFrame({
        "Round": round_number,
        "Kind": kind,
        "Driver": res["Abbreviation"],
        "FullName": res["FullName"] if "FullName" in res else res["Abbreviation"],
        "Team": res["TeamName"],
        "Grid": pd.to_numeric(res["GridPosition"], errors="coerce") if "GridPosition" in res else np.nan,
        "Position": pd.to_numeric(res["Position"], errors="coerce"),
        "Status": status,
        "Points": official.where(official.notna(), pd.Series(computed, index=res.index)),
        "Classified": status.isin(FINISHED) | status.str.startswith("+"),
        "Dsq": dsq,
    })


def _has_points(res: pd.DataFrame) -> bool:
    """Whether the results carry the official points (F1's archive does, OpenF1 doesn't)."""
    return "Points" in res and pd.to_numeric(res["Points"], errors="coerce").notna().any()


def _colors(res: pd.DataFrame) -> dict[str, str]:
    out = {}
    for team, color in zip(res["TeamName"], res.get("TeamColor", pd.Series([None] * len(res)))):
        if isinstance(color, str) and len(color.lstrip("#")) == 6:
            out[team] = "#" + color.lstrip("#")
    return out


# ---------------------------------------------------------------- championship


def driver_standings(season: Season) -> pd.DataFrame:
    """Drivers' points so far with wins, podiums, poles, fastest laps and laps led, leader first."""
    results = season.results
    gp = results[results["Kind"] == "R"]
    latest = results.sort_values("Round").groupby("Driver").tail(1).set_index("Driver")
    table = results.groupby("Driver")["Points"].sum().to_frame()
    table["FullName"] = latest["FullName"]
    table["Team"] = latest["Team"]
    counts = {
        "Wins": gp[gp["Position"] == 1].groupby("Driver").size(),
        "Podiums": gp[gp["Position"] <= 3].groupby("Driver").size(),
        "Poles": pole_sitters(season).value_counts(),
        "FastestLaps": season.fastest.groupby("Driver").size(),
        "LapsLed": season.led[season.led["Kind"] == "R"].groupby("Driver")["Laps"].sum(),
    }
    for name, count in counts.items():
        table[name] = count.reindex(table.index, fill_value=0).astype(int)
    return countback(table, results, "Driver").reset_index()


def countback(table: pd.DataFrame, results: pd.DataFrame, by: str) -> pd.DataFrame:
    """FIA championship order: points, then the count of P1, P2, P3, ... in Grands Prix."""
    gp = results[(results["Kind"] == "R") & ~results["Dsq"] & results["Position"].notna()]
    finishes = pd.crosstab(gp[by], gp["Position"]).reindex(table.index, fill_value=0)
    finishes = finishes.reindex(sorted(finishes.columns), axis=1).fillna(0)
    finishes.columns = [f"_finish_{p:g}" for p in finishes.columns]
    ranked = table.join(finishes)
    return ranked.sort_values(["Points", *finishes.columns], ascending=False, kind="stable")[table.columns]


def pole_sitters(season: Season) -> pd.Series:
    """Round -> driver on pole. F1 credits pole to the car that starts first, so after a grid penalty
    it isn't the fastest qualifier (Leclerc in Belgium 2023, Verstappen fastest); qualifying stands
    in where the grid isn't known."""
    gp = season.results[(season.results["Kind"] == "R") & (season.results["Grid"] == 1)]
    grid = gp.drop_duplicates("Round").set_index("Round")["Driver"]
    quali = season.quali[season.quali["Position"] == 1].set_index("Round")["Driver"]
    quali = quali[~quali.index.isin(grid.index)]
    return pd.concat([x for x in (grid, quali) if len(x)] or [grid]).sort_index()


def points_by_round(season: Season, by: str = "Driver") -> pd.DataFrame:
    """Cumulative points after each round (sprint included), one column per driver (or team)."""
    per_round = season.results.pivot_table(index="Round", columns=by, values="Points", aggfunc="sum")
    return per_round.reindex(season.rounds["Round"]).fillna(0).cumsum()


def round_winners(season: Season) -> pd.DataFrame:
    """Every round: Round, Event, Location, Sprint (bool), Pole, Winner, Fastest, SprintWinner (drivers)."""
    results = season.results
    won = results[results["Position"] == 1]
    winner = won[won["Kind"] == "R"].set_index("Round")["Driver"]
    sprint = won[won["Kind"] == "S"].set_index("Round")["Driver"]
    rounds = season.rounds.copy()
    rounds["Pole"] = rounds["Round"].map(pole_sitters(season))
    rounds["Winner"] = rounds["Round"].map(winner)
    rounds["Fastest"] = rounds["Round"].map(season.fastest.set_index("Round")["Driver"])
    rounds["SprintWinner"] = rounds["Round"].map(sprint)
    return rounds[rounds["Winner"].notna()].reset_index(drop=True)


def leaders_by_round(progress: pd.DataFrame, season: Season) -> pd.Series:
    """Championship leader after each round, using only countback results known by then."""
    return pd.Series({r: countback(points.to_frame("Points"), season.results[season.results["Round"] <= r],
                                   "Driver").index[0] for r, points in progress.iterrows()})


# ---------------------------------------------------------------- per team


def standings(season: Season) -> pd.DataFrame:
    """Constructors' points so far: Team, Points, Wins, Podiums, ordered."""
    gp = season.results[season.results["Kind"] == "R"]
    table = season.results.groupby("Team")["Points"].sum().to_frame()
    table["Wins"] = gp[gp["Position"] == 1].groupby("Team").size()
    table["Podiums"] = gp[gp["Position"] <= 3].groupby("Team").size()
    table = table.fillna(0).astype({"Wins": int, "Podiums": int})
    return countback(table, season.results, "Team").reset_index()


def drivers_of(season: Season, team: str) -> pd.DataFrame:
    """Each driver who raced for `team`: races, points, wins, podiums, best and average finish, DNFs."""
    gp = season.results[(season.results["Team"] == team)]
    rows = []
    for driver, d in gp.groupby("Driver"):
        races = d[d["Kind"] == "R"]
        finishes = races.loc[races["Classified"], "Position"]
        rows.append({
            "Driver": driver,
            "FullName": d["FullName"].iloc[-1],
            "Races": len(races),
            "Points": float(d["Points"].sum()),
            "Wins": int((races["Position"] == 1).sum()),
            "Podiums": int((races["Position"] <= 3).sum()),
            "Best": int(races["Position"].min()) if races["Position"].notna().any() else None,
            "AverageFinish": float(finishes.mean()) if len(finishes) else np.nan,
            "Dnf": int((~races["Classified"] & ~races["Dsq"]).sum()),
        })
    return pd.DataFrame(rows).sort_values(["Races", "Points"], ascending=False).reset_index(drop=True)


def teammate_battles(season: Season, team: str) -> pd.DataFrame:
    """Per driver: races and qualifying sessions where they beat the teammate they had that weekend.

    Race: finished ahead (a car that didn't finish counts as behind; both out is no result).
    Qualifying: the better position. QualiGap is the median gap to the teammate in the last part
    both set a time in (s; negative is quicker).
    """
    race = season.results[(season.results["Team"] == team) & (season.results["Kind"] == "R")].copy()
    race["Rank"] = race["Position"].where(race["Classified"])
    quali = season.quali[season.quali["Team"] == team]
    tally: dict[str, dict] = {}

    def count(driver, key, won):
        t = tally.setdefault(driver, {"RaceWon": 0, "RaceOf": 0, "QualiWon": 0, "QualiOf": 0, "Gaps": []})
        t[key + "Of"] += 1
        t[key + "Won"] += int(won)

    for _, weekend in race.groupby("Round"):
        if len(weekend) != 2:
            continue
        a, b = weekend.iloc[0], weekend.iloc[1]
        if pd.isna(a["Rank"]) and pd.isna(b["Rank"]):
            continue
        a_ahead = pd.notna(a["Rank"]) and (pd.isna(b["Rank"]) or a["Rank"] < b["Rank"])
        count(a["Driver"], "Race", a_ahead)
        count(b["Driver"], "Race", not a_ahead)
    for _, weekend in quali.groupby("Round"):
        if len(weekend) != 2 or weekend["Position"].isna().any():
            continue
        a, b = weekend.iloc[0], weekend.iloc[1]
        count(a["Driver"], "Quali", a["Position"] < b["Position"])
        count(b["Driver"], "Quali", b["Position"] < a["Position"])
        for part in ("Q3", "Q2", "Q1"):
            if pd.notna(a[part]) and pd.notna(b[part]):
                tally[a["Driver"]]["Gaps"].append(a[part] - b[part])
                tally[b["Driver"]]["Gaps"].append(b[part] - a[part])
                break
    rows = [{"Driver": d, **{k: v for k, v in t.items() if k != "Gaps"},
             "QualiGap": float(np.median(t["Gaps"])) if t["Gaps"] else np.nan} for d, t in tally.items()]
    return pd.DataFrame(rows, columns=["Driver", "RaceWon", "RaceOf", "QualiWon", "QualiOf", "QualiGap"])


def pit_crews(season: Season, min_stops: int = 5) -> pd.DataFrame:
    """Every team's stationary times: Team, Stops, Median, Best (s), quickest median first."""
    s = season.stops.dropna(subset=["Stationary"])
    s = s[s["StillOk"]] if "StillOk" in s else s
    table = s.groupby("Team")["Stationary"].agg(Stops="size", Median="median", Best="min")
    return table[table["Stops"] >= min_stops].sort_values("Median").reset_index()


# ---------------------------------------------------------------- per driver


def driver_season(season: Season, driver: str) -> pd.DataFrame:
    """A driver's weekends: Round, Event, Team, Grid, Position, Status, Classified, Dsq, Points (race and
    sprint), Quali (position), Pole, Fastest (fastest lap of the Grand Prix), Sprint (sprint finish)."""
    gp = season.results[(season.results["Driver"] == driver) & (season.results["Kind"] == "R")]
    sprint = season.results[(season.results["Driver"] == driver) & (season.results["Kind"] == "S")]
    sprint = sprint.set_index("Round")["Position"].where(sprint.set_index("Round")["Classified"])
    weekend_points = season.results[season.results["Driver"] == driver].groupby("Round")["Points"].sum()
    quali = season.quali[season.quali["Driver"] == driver].set_index("Round")["Position"]
    fastest = set(season.fastest.loc[season.fastest["Driver"] == driver, "Round"])
    events = season.rounds.set_index("Round")["Event"]
    rows = gp.assign(
        Event=gp["Round"].map(events).str.replace(" Grand Prix", ""),
        Points=gp["Round"].map(weekend_points).fillna(0),
        Quali=gp["Round"].map(quali),
        Pole=gp["Round"].map(pole_sitters(season)).eq(driver),
        Fastest=gp["Round"].isin(fastest),
        Sprint=gp["Round"].map(sprint),
    )
    return rows[["Round", "Event", "Team", "Grid", "Position", "Status", "Classified", "Dsq", "Points", "Quali",
                 "Pole", "Fastest", "Sprint"]].sort_values("Round").reset_index(drop=True)


def driver_highlights(rows: pd.DataFrame) -> list[tuple[str, str, str]]:
    """The standout numbers of a driver's season from `driver_season` rows, as (label, value, detail);
    a highlight that doesn't apply (no wins, no comeback) is left out."""
    out = []
    finished = rows[rows["Classified"] & rows["Position"].notna()]
    started = finished[finished["Grid"] > 0]
    if len(started):
        gains = started["Grid"] - started["Position"]
        best = started.loc[gains.idxmax()]
        if gains.max() > 0:
            out.append(("Best comeback", f"+{gains.max():.0f} places",
                        f"{best['Event']}: P{best['Grid']:.0f} to P{best['Position']:.0f}"))
    wins = finished[finished["Position"] == 1]
    if len(wins):
        back = wins.loc[wins["Grid"].where(wins["Grid"] > 0).idxmax()] if (wins["Grid"] > 0).any() else None
        if back is not None and back["Grid"] > 1:
            out.append(("Win from furthest back", f"P{back['Grid']:.0f}", back["Event"]))
    poles = rows[rows["Pole"]]
    if len(poles):
        out.append(("Poles turned into wins", f"{int((poles['Position'] == 1).sum())} of {len(poles)}", ""))
    hat_tricks = rows[rows["Pole"] & (rows["Position"] == 1) & rows["Fastest"]]
    if len(hat_tricks):
        out.append(("Hat-tricks", str(len(hat_tricks)), "pole, win and fastest lap: " + ", ".join(hat_tricks["Event"])))
    scored = (rows["Classified"] & (rows["Position"] <= 10)).tolist()
    run, best_run, end = 0, 0, None
    for i, s in enumerate(scored):
        run = run + 1 if s else 0
        if run > best_run:
            best_run, end = run, i
    if best_run > 1:
        first, last = rows.iloc[end - best_run + 1], rows.iloc[end]
        out.append(("Longest run in the points", f"{best_run} races", f"{first['Event']} to {last['Event']}"))
    if len(finished):
        worst = finished.loc[finished["Position"].idxmax()]
        out.append(("Lowest finish", f"P{worst['Position']:.0f}", worst["Event"]))
    return out
