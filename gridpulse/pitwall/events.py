"""What happened on each lap: pit stops, passes, fastest laps, safety cars, retirements.

Built by comparing the timing tower at the end of one lap with the one
before, so it works the same for a replay or a live feed.
"""

import pandas as pd

from gridpulse.pitwall.timing import format_lap_time, timing_tower, track_status
from gridpulse.stints.pace import plausible

NEUTRAL = {"Safety car": "Safety car", "VSC": "Virtual safety car", "Red flag": "Red flag"}
TOP = 10  # only passes for points-paying positions, so the feed stays readable


def fastest_lap_candidates(laps: pd.DataFrame) -> pd.DataFrame:
    """Laps that can count as a fastest lap: timed, not lap 1, not deleted, not out of the pit lane, not
    run into a red flag, and not implausibly quick.

    Officially any lap counts. So does an in-lap (Norris's fastest lap in Australia 2025 was the lap he
    pitted at the end of), and so does a lap on which a VSC or safety car was called after the car had
    gone through most of it (Alonso in China 2024, Norris in Qatar 2024)."""
    timed = laps.dropna(subset=["LapTime"])
    if "Deleted" in timed:
        timed = timed[timed["Deleted"] != True]  # noqa: E712 (column holds True/False/NaN)
    if "PitOutTime" in timed:
        timed = timed[timed["PitOutTime"].isna()]
    stopped = timed["TrackStatus"].astype(str).str.contains("5")
    # Lap 1 starts from the grid, so it's never representative.
    return plausible(timed[~stopped & (timed["LapNumber"] > 1)])


def fastest_sectors(laps: pd.DataFrame, top: int = 5) -> list[list[tuple[str, float, int]]]:
    """For sectors 1, 2 and 3: the `top` drivers' best times so far as (driver, seconds, lap), fastest first."""
    candidates = fastest_lap_candidates(laps)
    out = []
    for col in ("Sector1Time", "Sector2Time", "Sector3Time"):
        if col not in candidates:
            out.append([])
            continue
        ok = candidates.dropna(subset=[col])
        secs = ok[col].dt.total_seconds()
        ok = ok[secs >= 0.85 * secs.median()]  # drop glitches, as for laps
        best = ok.sort_values(col).drop_duplicates("Driver").head(top)
        out.append([(r.Driver, r[col].total_seconds(), int(r.LapNumber)) for _, r in best.iterrows()])
    return out


def lap_status(laps: pd.DataFrame) -> pd.Series:
    """Most severe track status any car saw on each lap."""
    s = laps.dropna(subset=["TrackStatus"]).groupby("LapNumber")["TrackStatus"].apply(
        lambda codes: track_status("".join(map(str, codes)))
    )
    return s.replace({"VSC ending": "VSC"})


def drive_throughs(laps: pd.DataFrame) -> set[tuple[str, int]]:
    """(driver, lap) for trips through the pit lane that didn't change tyres: same stint before and after."""
    if "Stint" not in laps:
        return set()
    stint = laps.set_index(["Driver", "LapNumber"])["Stint"]
    out = set()
    for r in laps[laps["PitInTime"].notna()].itertuples():
        before, after = stint.get((r.Driver, r.LapNumber)), stint.get((r.Driver, r.LapNumber + 1))
        if pd.notna(before) and pd.notna(after) and before == after:
            out.add((r.Driver, int(r.LapNumber)))
    return out


def race_events(laps: pd.DataFrame, retired: set[str], total_laps: int, entrants: pd.DataFrame | None = None,
                stops: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    status = lap_status(laps)
    # A trip down the pit lane is a stop if it's in the stop list (or, without one, if the tyres changed).
    listed = set(zip(stops["Driver"], stops["Lap"].astype(int))) if stops is not None else None
    passes_through = drive_throughs(laps)
    timed = fastest_lap_candidates(laps)
    best = None

    prev = None
    for lap in range(1, total_laps + 1):
        if lap not in laps["LapNumber"].values:
            continue
        tower = timing_tower(laps, lap, retired, entrants, official=False, stops=stops)  # passes happen on the road
        pos = tower.set_index("Driver")

        # Track status changes
        now, before = status.get(lap, "Unknown"), status.get(lap - 1, "Green")
        if now != before and now in NEUTRAL:
            rows.append((lap, "SC", "", f"{NEUTRAL[now]}"))
        elif now == "Green" and before in NEUTRAL:
            rows.append((lap, "GREEN", "", "Green flag, racing resumes"))

        # Fastest lap of the race so far
        on_lap = timed[timed["LapNumber"] == lap]
        if not on_lap.empty:
            fl = on_lap.loc[on_lap["LapTime"].idxmin()]
            if best is None or fl["LapTime"] < best:
                if best is not None:
                    rows.append((lap, "FL", fl["Driver"], f"{fl['Driver']} fastest lap, {format_lap_time(fl['LapTime'])}"))
                best = fl["LapTime"]

        for r in tower.itertuples():
            if r.Pit and ((r.Driver, lap) in listed if listed is not None else (r.Driver, lap) not in passes_through):
                rows.append((lap, "PIT", r.Driver, f"{r.Driver} pits from P{r.Pos}"))
        if prev is None:  # out before completing a single lap
            for r in tower[tower["Out"]].itertuples():
                rows.append((lap, "OUT", r.Driver, f"{r.Driver} retires on the opening lap"))
        else:
            for r in tower.itertuples():
                was_running = r.Driver in prev.index and not prev.loc[r.Driver, "Out"]
                if r.Out and was_running:
                    rows.append((lap, "OUT", r.Driver, f"{r.Driver} retires"))
            # Passes on track: gained places on cars that didn't pit this lap or last.
            pitted = set(tower.loc[tower["Pit"], "Driver"]) | set(prev.index[prev["Pit"]])
            stops_now, stops_before = pos["Stops"].fillna(-1), prev["Stops"].fillna(-1)
            changed_stint = {d for d in pos.index if d in prev.index and stops_now[d] != stops_before[d]}
            for r in tower[tower["Pos"] <= TOP].itertuples():
                d = r.Driver
                if d not in prev.index or r.Out or prev.loc[d, "Pos"] <= r.Pos or d in pitted | changed_stint:
                    continue
                passed = [
                    o for o in prev.index[prev["Pos"] < prev.loc[d, "Pos"]]
                    if o in pos.index and pos.loc[o, "Pos"] > r.Pos and o not in pitted | changed_stint and not pos.loc[o, "Out"]
                ]
                if passed:
                    rows.append((lap, "PASS", d, f"{d} passes {', '.join(passed)} for P{r.Pos}"))
        prev = pos

    if total_laps in laps["LapNumber"].values:
        final = timing_tower(laps, total_laps, retired)
        winner = final.loc[0, "Driver"]
        if len(final) > 1 and pd.notna(final.loc[1, "GapSeconds"]):
            rows.append((total_laps, "FLAG", winner,
                         f"{winner} wins by {final.loc[1, 'GapSeconds']:.3f} s from {final.loc[1, 'Driver']}"))
        else:  # nobody else on the lead lap
            rows.append((total_laps, "FLAG", winner, f"{winner} wins"))
        # Where the result differs from the order they crossed the line (penalties after the flag).
        road = timing_tower(laps, total_laps, retired, official=False)
        crossed = dict(zip(road.loc[~road["Out"], "Driver"], road.loc[~road["Out"], "Pos"]))
        for r in final[~final["Out"]].itertuples():
            if r.Driver in crossed and r.Pos > crossed[r.Driver]:
                rows.append((total_laps, "FLAG", r.Driver,
                             f"{r.Driver} classified P{r.Pos}, crossed the line P{crossed[r.Driver]}"))
        for r in final[final["Gap"] == "DSQ"].itertuples():
            where = f", crossed the line P{crossed[r.Driver]}" if r.Driver in crossed else ""
            rows.append((total_laps, "FLAG", r.Driver, f"{r.Driver} disqualified{where}"))
    return pd.DataFrame(rows, columns=["Lap", "Kind", "Driver", "Text"])


def situation(tower: pd.DataFrame, lap: int, total_laps: int) -> str:
    """One line on the state of the race at the end of `lap`."""
    lead = tower.loc[0, "Driver"]
    second = tower.iloc[1] if len(tower) > 1 else None
    if lap >= total_laps and (second is None or pd.isna(second["GapSeconds"])):
        return f"Chequered flag: {lead} wins."
    if second is None or pd.isna(second["GapSeconds"]):
        return f"Lap {lap} of {total_laps}: {lead} leads."
    if lap >= total_laps:
        return f"Chequered flag: {lead} wins by {second['GapSeconds']:.3f} s from {second['Driver']}."
    return f"Lap {lap} of {total_laps}: {lead} leads {second['Driver']} by {second['GapSeconds']:.1f} s."


BANNERS = {"Safety car": ("sc", "Safety car"), "VSC": ("vsc", "Virtual safety car"), "Red flag": ("red", "Red flag")}


def neutralised_banner(status: pd.Series, lap: int) -> dict | None:
    """Banner for the timing tower while the race is neutralised, with how many laps it has run."""
    now = status.get(lap)
    if now not in BANNERS:
        return None
    laps_under = 0
    while status.get(lap - laps_under) == now:
        laps_under += 1
    kind, text = BANNERS[now]
    return {"kind": kind, "text": text, "laps": laps_under}
