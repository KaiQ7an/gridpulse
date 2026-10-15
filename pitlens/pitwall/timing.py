"""Race state at any lap: timing tower, gaps, track status and tyre stints.

Everything here works on a plain DataFrame of FastF1 laps (one row per driver
per lap, with `Time` = session time when the lap was completed), so the same
functions serve a finished race, a lap-by-lap replay and, later, live data.
"""

import numpy as np
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

# Cars that cross the line closer together than this are ordered by the timing feed's
# running position rather than by their lap end times, which (especially OpenF1's,
# rebuilt from lap start stamps) are only good to a few tenths of a second.
TIE_SECONDS = 0.5


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


def disqualified(results: pd.DataFrame) -> set[str]:
    """Drivers disqualified from the race (they take the flag but aren't classified)."""
    status = results.get("Status", pd.Series("", index=results.index)).fillna("").str.lower()
    dsq = status.str.contains("disqualif|dsq", regex=True)
    if "ClassifiedPosition" in results:
        dsq |= results["ClassifiedPosition"].astype(str).eq("D")
    return set(results.loc[dsq, "Abbreviation"])


def non_starters(results: pd.DataFrame) -> pd.Series:
    """True for drivers who never took the start (did not start, withdrawn)."""
    status = results["Status"].fillna("").str.lower()
    dns = status.str.contains("not start|withdr|dns", regex=True)
    if "ClassifiedPosition" in results:
        dns |= results["ClassifiedPosition"].astype(str).eq("W")
    return dns


def official_gaps(results: pd.DataFrame) -> pd.Series:
    """Seconds behind the winner at the flag for cars on the lead lap, from the official classification.

    OpenF1 results carry `GapToLeader`; FastF1's carry `Time`, which is the
    winner's race time and every other lead-lap finisher's gap to them (and
    for lapped cars something else, so they're left out by laps completed).
    """
    ranked = results.dropna(subset=["Position"]).sort_values("Position")
    # Only cars that ran the full distance: FastF1's Time for a lapped car is some other gap.
    if "Laps" in ranked and ranked["Laps"].notna().any():
        ranked = ranked[ranked["Laps"] == ranked["Laps"].max()]
    elif "Status" in ranked:
        ranked = ranked[ranked["Status"].fillna("").eq("Finished") | (ranked["Position"] == 1)]
    if "GapToLeader" in ranked:
        gaps = pd.to_numeric(ranked["GapToLeader"], errors="coerce")
    elif "Time" in ranked:
        gaps = pd.to_timedelta(ranked["Time"], errors="coerce").dt.total_seconds()
    else:
        return pd.Series(dtype=float)
    gaps = pd.Series(gaps.values, index=ranked["Abbreviation"].values, dtype=float)
    if gaps.empty or ranked["Position"].iloc[0] != 1:
        return pd.Series(dtype=float)
    gaps.iloc[0] = 0.0  # FastF1 gives the winner's total race time here
    return gaps.dropna()


def trim_to_classified_laps(laps: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    """Drop laps beyond the number the result says a driver completed.

    OpenF1 sometimes counts one lap too many for a lapped car (2026 British
    GP: Sainz, classified a lap down with 51 laps, has a 52nd), which would
    put it on the lead lap at the flag.
    """
    if "Laps" not in results:
        return laps
    done = results.dropna(subset=["Laps"]).set_index("Abbreviation")["Laps"]
    done = done[done > 0]  # a disqualified car can show 0
    limit = laps["Driver"].map(done)
    return laps[~(limit.notna() & (laps["LapNumber"] > limit))].reset_index(drop=True)


def lap_coverage(laps: pd.DataFrame, results: pd.DataFrame) -> float | None:
    """Share of the laps the result says were run that the timing data has (OpenF1 is missing
    almost half of them for the 2025 Miami GP)."""
    if "Laps" not in results:
        return None
    expected = results["Laps"].where(results["Laps"] > 0).sum()
    return min(1.0, laps["Time"].notna().sum() / expected) if expected else None


def complete_final_laps(laps: pd.DataFrame, results: pd.DataFrame, total_laps: int) -> pd.DataFrame:
    """Give finishers' last laps a finishing time where the feed left it out.

    OpenF1 sometimes has no duration for the last lap (2026 Australian GP: no
    lap 58 time for anyone, and no lap 58 at all for most cars), which would
    leave every car looking a lap down at the flag. The winner's flag time is
    estimated from their last lap's start and recent pace; cars on the lead
    lap then finish their official gap behind (a missing last lap is added);
    other finishers get their own last lap estimated from their pace. Lap
    times of these laps stay unknown.
    """
    status = results["Status"].fillna("")
    finishers = set(results.loc[status.isin(FINISHED_STATUSES) | status.str.startswith("+"), "Abbreviation"])
    gaps = official_gaps(results)
    timed = laps.dropna(subset=["Time"])
    if not finishers or timed.empty or len(gaps) == 0:
        return laps

    def pace(driver: str):
        recent = timed[timed["Driver"] == driver].sort_values("LapNumber")["LapTime"].dropna().tail(5)
        return recent.median() if len(recent) else pd.NaT

    def last_row(driver: str):
        mine = laps[laps["Driver"] == driver]
        return mine.loc[mine["LapNumber"].idxmax()] if not mine.empty else None

    def estimated_end(row) -> pd.Timedelta:
        start = row.get("LapStartTime")
        if pd.isna(start):  # no start stamp: the lap before ended where this one began
            before = timed[(timed["Driver"] == row["Driver"]) & (timed["LapNumber"] == row["LapNumber"] - 1)]["Time"]
            start = before.iloc[0] if not before.empty else pd.NaT
        return start + pace(row["Driver"])

    laps = laps.copy()
    winner = last_row(gaps.index[0])
    if winner is None:
        return laps
    if winner["LapNumber"] == total_laps:
        flag = winner["Time"] if pd.notna(winner["Time"]) else estimated_end(winner)
    else:
        flag = winner["Time"] + pace(winner["Driver"])
    if pd.isna(flag):
        return laps

    added = []
    for driver in finishers:
        row = last_row(driver)
        if row is None:
            continue
        if driver in gaps.index:
            end = flag + pd.to_timedelta(float(gaps[driver]), unit="s")
            if row["LapNumber"] == total_laps:
                if pd.isna(row["Time"]):
                    laps.loc[row.name, "Time"] = end
            elif row["LapNumber"] == total_laps - 1 and pd.notna(row["Time"]):
                new = row.copy()
                new["LapNumber"], new["LapStartTime"], new["Time"] = float(total_laps), row["Time"], end
                for col in ("LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "PitInTime", "PitOutTime"):
                    if col in new:
                        new[col] = pd.NaT
                if "TyreLife" in new:
                    new["TyreLife"] = row["TyreLife"] + 1
                for col, value in (("Position", np.nan), ("IsAccurate", False), ("IsPitOutLap", False)):
                    if col in new:
                        new[col] = value
                added.append(new)
        elif pd.isna(row["Time"]):
            laps.loc[row.name, "Time"] = estimated_end(row)
    if added:
        # Via object: an all-NaT column would otherwise be read as datetimes, not durations.
        extra = pd.DataFrame(added).astype(object).astype(laps.dtypes.to_dict())
        laps = pd.concat([laps, extra], ignore_index=True).sort_values(["Driver", "LapNumber"]).reset_index(drop=True)
    return laps


def classify_finish(laps: pd.DataFrame, results: pd.DataFrame, total_laps: int) -> pd.DataFrame:
    """Attach the official result to the laps: `Classified` (position) and `OfficialGap` (seconds behind
    the winner, lead-lap finishers only), which `timing_tower` uses for the final lap.

    Lap times say who crossed the line first; the result is what counts. A
    photo finish can come out the wrong way round in lap timing (in the 2026
    Azerbaijan GP OpenF1's lap times put Verstappen 0.003 s ahead of Russell,
    who won by 0.196 s), and penalties applied after the flag change the
    order (Colapinto crossed the line 8th in the 2026 Barcelona GP and was
    classified 10th).
    """
    laps = laps.copy()
    position = results.dropna(subset=["Position"]).set_index("Abbreviation")["Position"]
    laps["Classified"] = laps["Driver"].map(position).astype(float)
    laps["OfficialGap"] = laps["Driver"].map(official_gaps(results)).where(laps["LapNumber"] == total_laps)
    laps["Disqualified"] = laps["Driver"].isin(disqualified(results))
    return laps


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
    laps: pd.DataFrame, lap: int, retired: set[str] = frozenset(), entrants: pd.DataFrame | None = None,
    official: bool = True, stops: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Running order, gaps and tyres as each driver completes `lap`.

    Drivers who completed `lap` are ordered by when they crossed the line
    (near-ties by the feed's running position, see TIE_SECONDS). On the last
    lap, if `classify_finish` has attached the result and `official` is set,
    the finishers are in classified order with the official gaps. `stops`
    (from `pit_stops`) counts each car's stops; without it they come from the
    tyre stint number. Anyone who never completes it is either out of the race (in `retired`) or
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
    latest = _settle_near_ties(latest).reset_index(drop=True)
    final = official and "Classified" in latest and lap >= laps["LapNumber"].max()
    latest["Dsq"] = False
    if final:
        # Cars still running in classified order (unclassified last); those out keep their places;
        # the disqualified go to the bottom.
        if "Disqualified" in latest:
            latest["Dsq"] = latest["Disqualified"].fillna(False).astype(bool)
            latest.loc[latest["Dsq"], "Out"] = True
        running = (latest["SortGroup"] == 0).to_numpy() & ~latest["Dsq"].to_numpy()
        key = np.where(running, latest["Classified"].fillna(1e6), 1e7 + np.arange(len(latest)))
        key = np.where(latest["Dsq"].to_numpy(), 2e7 + np.arange(len(latest)), key)
        latest = latest.iloc[np.argsort(key, kind="stable")].reset_index(drop=True)

    on_lap = (latest["LapNumber"] == lap) & ~latest["Dsq"]
    if on_lap.any():
        leader_time = latest.loc[on_lap, "Time"].iloc[0]
    gaps = (latest["Time"] - leader_time).dt.total_seconds().where(on_lap)
    if final and "OfficialGap" in latest:
        gaps = latest["OfficialGap"].where(latest["OfficialGap"].notna() & on_lap, gaps)
    # A car placed ahead on a near-tie can't be behind on the clock: keep gaps rising.
    latest["GapSeconds"] = gaps.where(~on_lap, gaps[on_lap].cummax())
    latest["IntervalSeconds"] = latest["GapSeconds"].diff()

    def gap_text(row) -> str:
        if row["Dsq"]:
            return "DSQ"
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
            "Stops": stops_made(latest, lap, stops),
            "Pit": latest["PitInTime"].notna() & (latest["LapNumber"] == lap),
            "GapSeconds": latest["GapSeconds"],
            "IntervalSeconds": latest["IntervalSeconds"],
            "LapsDown": latest["LapsDown"],
            "Out": latest["Out"],
        }
    )


def stops_made(latest: pd.DataFrame, lap: int, stops: pd.DataFrame | None) -> pd.Series:
    """Stops each car has made by the end of `lap`: from the stop list where there is one (OpenF1's
    tyre stints miss some stops), else from the stint number."""
    if stops is None:
        return (latest["Stint"] - 1).astype("Int64").reset_index(drop=True)
    done = stops[stops["Lap"] < lap].groupby("Driver").size()
    return latest["Driver"].map(done).fillna(0).astype("Int64").reset_index(drop=True)


def _settle_near_ties(rows: pd.DataFrame) -> pd.DataFrame:
    """Within each run of cars that crossed the line less than TIE_SECONDS apart, order by running position."""
    if "Position" not in rows or rows["Position"].isna().all():
        return rows
    t = rows["Time"].dt.total_seconds()
    same_group = rows["LapNumber"].eq(rows["LapNumber"].shift()) & rows["SortGroup"].eq(rows["SortGroup"].shift())
    close = same_group & (t - t.shift() < TIE_SECONDS)
    run = (~close).cumsum().rename("_run")
    return rows.assign(_run=run).sort_values(["_run", "Position"], na_position="last").drop(columns="_run")


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
