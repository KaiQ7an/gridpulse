"""What happened on each lap: pit stops, passes, fastest laps, safety cars, retirements.

Built by comparing the timing tower at the end of one lap with the one
before, so it works the same for a replay or a live feed.
"""

import pandas as pd

from pitlens.pitwall.timing import format_lap_time, timing_tower, track_status

NEUTRAL = {"Safety car": "Safety car", "VSC": "Virtual safety car", "Red flag": "Red flag"}
TOP = 10  # only passes for points-paying positions, so the feed stays readable


def lap_status(laps: pd.DataFrame) -> pd.Series:
    """Most severe track status any car saw on each lap."""
    s = laps.dropna(subset=["TrackStatus"]).groupby("LapNumber")["TrackStatus"].apply(
        lambda codes: track_status("".join(map(str, codes)))
    )
    return s.replace({"VSC ending": "VSC"})


def race_events(laps: pd.DataFrame, retired: set[str], total_laps: int) -> pd.DataFrame:
    rows = []
    status = lap_status(laps)
    timed = laps.dropna(subset=["LapTime"])
    if "Deleted" in timed:
        timed = timed[timed["Deleted"] != True]  # noqa: E712 (column holds True/False/NaN)
    best = None

    prev = None
    for lap in range(1, total_laps + 1):
        if lap not in laps["LapNumber"].values:
            continue
        tower = timing_tower(laps, lap, retired)
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
            if r.Pit:
                rows.append((lap, "PIT", r.Driver, f"{r.Driver} pits from P{r.Pos}"))
        if prev is not None:
            for r in tower.itertuples():
                was_running = r.Driver in prev.index and not prev.loc[r.Driver, "Out"]
                if r.Out and was_running:
                    rows.append((lap, "OUT", r.Driver, f"{r.Driver} retires"))
            # Passes on track: gained places on cars that didn't pit this lap or last.
            pitted = set(tower.loc[tower["Pit"], "Driver"]) | set(prev.index[prev["Pit"]])
            changed_stint = {d for d in pos.index if d in prev.index and pos.loc[d, "Stops"] != prev.loc[d, "Stops"]}
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
        if len(final) > 1 and pd.notna(final.loc[1, "GapSeconds"]):
            rows.append((total_laps, "FLAG", final.loc[0, "Driver"],
                         f"{final.loc[0, 'Driver']} wins by {final.loc[1, 'GapSeconds']:.3f} s from {final.loc[1, 'Driver']}"))
    return pd.DataFrame(rows, columns=["Lap", "Kind", "Driver", "Text"])


def situation(tower: pd.DataFrame, lap: int, total_laps: int) -> str:
    """One line on the state of the race at the end of `lap`."""
    lead = tower.loc[0, "Driver"]
    second = tower.iloc[1] if len(tower) > 1 else None
    if second is None or pd.isna(second["GapSeconds"]):
        return f"Lap {lap} of {total_laps}: {lead} leads."
    if lap >= total_laps:
        return f"Chequered flag: {lead} wins by {second['GapSeconds']:.3f} s from {second['Driver']}."
    return f"Lap {lap} of {total_laps}: {lead} leads {second['Driver']} by {second['GapSeconds']:.1f} s."
