"""Race state at any lap: timing tower, gaps, track status and tyre stints.

Everything here works on a plain DataFrame of FastF1 laps (one row per driver
per lap, with `Time` = session time when the lap was completed), so the same
functions serve a finished race, a lap-by-lap replay and, later, live data.
"""

import pandas as pd

TRACK_STATUS = {
    "1": "Green",
    "2": "Yellow",
    "4": "Safety car",
    "5": "Red flag",
    "6": "VSC",
    "7": "VSC ending",
}
# Most severe first: a lap that saw yellow then SC is an SC lap.
_SEVERITY = ["5", "4", "6", "7", "2", "1"]

# Result statuses for drivers who took the flag; anything else ran out of race.
FINISHED_STATUSES = ("Finished", "Lapped")


def track_status(code) -> str:
    """Most severe track status seen during a lap, e.g. "124" -> "Safety car"."""
    code = "" if pd.isna(code) else str(code)
    for c in _SEVERITY:
        if c in code:
            return TRACK_STATUS[c]
    return "Unknown"


def neutralised_periods(laps: pd.DataFrame) -> list[tuple[str, int, int]]:
    """Runs of laps run under safety car, VSC or red flag, as (status, first, last).

    Each lap takes the most severe status any car saw on it.
    """
    per_lap = (
        laps.dropna(subset=["TrackStatus"])
        .groupby("LapNumber")["TrackStatus"]
        .apply(lambda codes: track_status("".join(map(str, codes))))
        .sort_index()
    )
    periods: list[tuple[str, int, int]] = []
    for lap, status in per_lap.items():
        if status == "VSC ending":
            status = "VSC"
        if status not in ("Safety car", "VSC", "Red flag"):
            continue
        if periods and periods[-1][0] == status and periods[-1][2] == lap - 1:
            periods[-1] = (status, periods[-1][1], int(lap))
        else:
            periods.append((status, int(lap), int(lap)))
    return periods


def retired_drivers(results: pd.DataFrame) -> set[str]:
    """Drivers whose result shows they did not take the chequered flag."""
    status = results["Status"].fillna("")
    finished = status.isin(FINISHED_STATUSES) | status.str.startswith("+")
    return set(results.loc[~finished, "Abbreviation"])


def leader_times(laps: pd.DataFrame) -> pd.Series:
    """Session time at which the race leader completed each lap."""
    return laps.dropna(subset=["Time"]).groupby("LapNumber")["Time"].min()


def gap_to_leader(laps: pd.DataFrame) -> pd.DataFrame:
    """Seconds behind the leader at the end of every lap (a "race trace")."""
    timed = laps.dropna(subset=["Time"])
    lead = timed["LapNumber"].map(leader_times(timed))
    out = timed[["Driver", "LapNumber"]].copy()
    out["Gap"] = (timed["Time"] - lead).dt.total_seconds()
    return out.reset_index(drop=True)


def timing_tower(
    laps: pd.DataFrame, lap: int, retired: set[str] = frozenset(), entrants: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Running order, gaps and tyres as each driver completes `lap`.

    Drivers who completed `lap` are ordered by when they crossed the line.
    Anyone who never completes it is either out of the race (in `retired`) or
    lapped, and is placed behind by laps completed. `entrants` (Driver, Team)
    adds anyone who never completed a lap at all, such as a first-lap
    retirement, at the bottom.
    """
    timed = laps.dropna(subset=["Time"])
    timed = timed[timed["LapNumber"] <= lap]
    lead = leader_times(laps)
    leader_time = lead.get(lap, pd.NaT)  # NaT if the feed is missing this lap

    latest = timed.sort_values("LapNumber").groupby("Driver").tail(1).copy()
    if entrants is not None:
        absent = entrants[~entrants["Driver"].isin(latest["Driver"])]
        if not absent.empty:
            # Grow the frame with empty rows (each column keeps its own dtype) and fill in who they are.
            n = len(latest)
            latest = latest.reset_index(drop=True).reindex(range(n + len(absent)))
            latest.loc[n:, "Driver"] = absent["Driver"].values
            latest.loc[n:, "Team"] = absent["Team"].values
            latest.loc[n:, "LapNumber"] = 0.0
            retired = set(retired) | set(absent["Driver"])
    latest["Out"] = (latest["LapNumber"] < lap) & latest["Driver"].isin(retired)

    # Laps down: how many more laps the leader had finished when this driver
    # crossed the line (or the plain lap deficit if they never reach `lap`).
    def laps_down(row) -> int:
        if row["LapNumber"] < lap:
            return int(lap - row["LapNumber"])
        return int(((lead.index > lap) & (lead <= row["Time"])).sum())

    latest["LapsDown"] = latest.apply(laps_down, axis=1)
    latest["SortGroup"] = latest["Out"].astype(int)
    latest = latest.sort_values(["SortGroup", "LapNumber", "Time"], ascending=[True, False, True])
    latest = latest.reset_index(drop=True)

    latest["GapSeconds"] = (latest["Time"] - leader_time).dt.total_seconds().where(latest["LapNumber"] == lap)
    latest["IntervalSeconds"] = latest["GapSeconds"].diff()

    def gap_text(row) -> str:
        if row["Out"]:
            return "OUT"
        if row.name == 0:
            return "Leader"
        if row["LapsDown"] > 0:
            return f"+{row['LapsDown']} lap" + ("s" if row["LapsDown"] > 1 else "")
        return "" if pd.isna(row["GapSeconds"]) else f"+{row['GapSeconds']:.3f}"

    def interval_text(row) -> str:
        if row.name == 0 or row["Out"] or row["LapsDown"] > 0 or pd.isna(row["IntervalSeconds"]):
            return ""
        return f"+{row['IntervalSeconds']:.3f}"

    return pd.DataFrame(
        {
            "Pos": range(1, len(latest) + 1),
            "Driver": latest["Driver"],
            "Team": latest["Team"],
            "Gap": latest.apply(gap_text, axis=1),
            "Interval": latest.apply(interval_text, axis=1),
            "LastLap": latest["LapTime"].map(format_lap_time),
            "Compound": latest["Compound"].fillna("UNKNOWN"),
            "TyreAge": latest["TyreLife"].astype("Int64"),
            "Stops": (latest["Stint"] - 1).astype("Int64"),
            "Pit": latest["PitInTime"].notna() & (latest["LapNumber"] == lap),
            "GapSeconds": latest["GapSeconds"],
            "IntervalSeconds": latest["IntervalSeconds"],
            "LapsDown": latest["LapsDown"],
            "Out": latest["Out"],
        }
    )


def stint_timeline(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per tyre stint: driver, compound, first and last lap."""
    g = laps.dropna(subset=["Stint"]).groupby(["Driver", "Stint"])
    out = g.agg(
        Compound=("Compound", lambda c: c.mode().iloc[0] if c.notna().any() else "UNKNOWN"),
        StartLap=("LapNumber", "min"),
        EndLap=("LapNumber", "max"),
        StartAge=("TyreLife", "min"),
    ).reset_index()
    out["Laps"] = out["EndLap"] - out["StartLap"] + 1
    return out


def format_lap_time(value) -> str:
    """Timedelta -> "1:21.345"."""
    if pd.isna(value):
        return ""
    seconds = value.total_seconds()
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}:{rest:06.3f}"
