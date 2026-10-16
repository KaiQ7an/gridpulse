"""A season, team by team: results, points, qualifying, teammate battles and pit stops.

Built from the saved races (snapshots) so a whole season loads in seconds. Drivers are tied to
a team race by race, so a mid-season swap (Lawson and Tsunoda in 2025) lands in the right place.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pitlens import snapshots
from pitlens.undercut.analysis import ordinary_stationary_times, pit_stops

RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]
FINISHED = ("Finished", "Lapped")


@dataclass
class Season:
    year: int
    rounds: pd.DataFrame  # Round, Event, Location, Sprint (bool), in calendar order
    results: pd.DataFrame  # Round, Kind (R/S), Driver, FullName, Team, Grid, Position, Status, Points, Classified, Dsq
    quali: pd.DataFrame  # Round, Driver, Team, Position, Part (furthest part reached), Q1, Q2, Q3 (s)
    stops: pd.DataFrame  # Round, Driver, Team, LaneTime, Stationary, StillOk
    colors: dict[str, str]  # team -> "#rrggbb"
    missing: list[int]  # finished rounds with no saved race


def seasons_saved() -> list[int]:
    """Seasons with saved races, newest first."""
    years = [int(p.name) for p in snapshots.SNAPSHOT_DIR.glob("*") if p.name.isdigit()]
    return sorted((y for y in years if len(snapshots.races(y)) >= 3), reverse=True)


def points_for(position, kind: str) -> int:
    table = RACE_POINTS if kind == "R" else SPRINT_POINTS
    if pd.isna(position) or not 1 <= int(position) <= len(table):
        return 0
    return table[int(position) - 1]


def load_season(year: int) -> Season:
    rounds = snapshots.races(year).sort_values("RoundNumber")
    result_rows, quali_rows, stop_rows, colors, missing = [], [], [], {}, []
    for r in rounds.itertuples():
        for kind in ("R", "S"):
            parts = snapshots.load_race(year, int(r.RoundNumber), kind)
            if parts is None:
                if kind == "R":
                    missing.append(int(r.RoundNumber))
                continue
            result_rows.append(_results(parts["results"], int(r.RoundNumber), kind))
            colors.update(_colors(parts["results"]))
            stops = pit_stops(parts["laps"], parts.get("stationary"))
            if not stops.empty:
                team = dict(zip(parts["results"]["Abbreviation"], parts["results"]["TeamName"]))
                stop_rows.append(stops.assign(Round=int(r.RoundNumber), Kind=kind, Team=stops["Driver"].map(team)))
        q = snapshots.load_quali(year, int(r.RoundNumber), "Q")
        if q is not None:
            quali_rows.append(q.results.assign(Round=int(r.RoundNumber)))
    results = pd.concat(result_rows, ignore_index=True) if result_rows else pd.DataFrame()
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


def _colors(res: pd.DataFrame) -> dict[str, str]:
    out = {}
    for team, color in zip(res["TeamName"], res.get("TeamColor", pd.Series([None] * len(res)))):
        if isinstance(color, str) and len(color.lstrip("#")) == 6:
            out[team] = "#" + color.lstrip("#")
    return out


# ---------------------------------------------------------------- per team


def standings(season: Season) -> pd.DataFrame:
    """Constructors' points so far: Team, Points, Wins, Podiums, ordered."""
    gp = season.results[season.results["Kind"] == "R"]
    table = season.results.groupby("Team")["Points"].sum().to_frame()
    table["Wins"] = gp[gp["Position"] == 1].groupby("Team").size()
    table["Podiums"] = gp[gp["Position"] <= 3].groupby("Team").size()
    table = table.fillna(0).astype({"Wins": int, "Podiums": int})
    return table.sort_values(["Points", "Wins"], ascending=False).reset_index()


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
