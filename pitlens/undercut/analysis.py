"""Pit stops, pit loss and undercut/overcut battles from lap timing.

All functions take the race's laps as a plain DataFrame (FastF1 columns:
Driver, LapNumber, Time, LapTime, PitInTime, PitOutTime, Compound, TyreLife,
TrackStatus), so they work on a finished race, a replay or live data alike.
"""

import numpy as np
import pandas as pd

from pitlens.pitwall.timing import track_status

NEUTRALISED = {"Safety car", "VSC", "VSC ending", "Red flag"}


def _lap_times(laps: pd.DataFrame) -> pd.DataFrame:
    """Session time (s) at which each driver completed each lap: drivers x laps."""
    timed = laps.dropna(subset=["Time"])
    return timed.pivot_table(index="LapNumber", columns="Driver", values="Time", aggfunc="first").apply(
        lambda col: col.dt.total_seconds()
    )


STOP_COLUMNS = [
    "Driver", "Lap", "LaneTime", "Stationary", "From", "To", "TyreAge", "Status", "Neutralised", "Loss",
    "PosBefore", "PosAfter",
]


def pit_stops(laps: pd.DataFrame, stationary: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per pit stop: in-lap, how long it took, tyres, the time it cost and places lost.

    A stop is an in-lap (PitInTime set) followed by an out-lap (PitOutTime set)
    on a new stint; driving through the pit lane on the same tyres isn't one.
    `LaneTime` is pit entry to pit exit; `Stationary` is how long the car stood
    in its box, where the timing feed has it (`stationary`: Driver, Lap,
    Stationary). `Loss` compares the in-lap plus out-lap with the same two
    laps for the cars that stayed out, corrected for how much quicker or
    slower this car was than them just before. Comparing with the field on
    the same laps makes it fair under a safety car or VSC, when everyone is
    slow. `PosBefore` and `PosAfter` are the running positions at the end of
    the lap before the in-lap and at the end of the out-lap.
    """
    times = _lap_times(laps)
    lap_time = times.diff()  # crossing-to-crossing lap times, s
    pitted = laps.pivot_table(
        index="LapNumber", columns="Driver", values=["PitInTime", "PitOutTime"], aggfunc="first"
    ).notna()
    pit_lap = (pitted["PitInTime"] | pitted["PitOutTime"]).reindex(
        index=times.index, columns=times.columns, fill_value=False
    ).astype(bool)

    still = {} if stationary is None or stationary.empty else \
        stationary.set_index(["Driver", "Lap"])["Stationary"].to_dict()

    rows = []
    for driver, d in laps.sort_values("LapNumber").groupby("Driver"):
        d = d.set_index("LapNumber")
        position = d["Position"] if "Position" in d else pd.Series(dtype=float)
        for lap in d.index[d["PitInTime"].notna()]:
            if lap + 1 not in d.index or pd.isna(d.loc[lap + 1, "PitOutTime"]):
                continue  # retired in the pits, or no out-lap recorded
            inlap, outlap = d.loc[lap], d.loc[lap + 1]
            if inlap.get("Stint") == outlap.get("Stint") and pd.notna(inlap.get("Stint")) \
                    and pd.isna(still.get((driver, int(lap)))):
                continue  # drove through the pit lane on the same tyres: a penalty, or sent through under SC
            status = track_status(str(inlap["TrackStatus"]) + str(outlap["TrackStatus"]))
            rows.append(
                {
                    "Driver": driver,
                    "Lap": int(lap),
                    "LaneTime": round((outlap["PitOutTime"] - inlap["PitInTime"]).total_seconds(), 1),
                    "Stationary": still.get((driver, int(lap)), np.nan),
                    "From": inlap["Compound"],
                    "To": outlap["Compound"],
                    "TyreAge": inlap["TyreLife"],
                    "Status": status,
                    "Neutralised": status in NEUTRALISED,
                    "Loss": _stop_loss(times, lap_time, pit_lap, driver, int(lap)),
                    "PosBefore": position.get(lap - 1, np.nan),
                    "PosAfter": position.get(lap + 1, np.nan),
                }
            )
    if not rows:
        return pd.DataFrame(columns=STOP_COLUMNS)
    out = pd.DataFrame(rows, columns=STOP_COLUMNS).sort_values(["Lap", "Driver"]).reset_index(drop=True)
    out[["PosBefore", "PosAfter"]] = out[["PosBefore", "PosAfter"]].astype("Int64")
    return out


def plausible_lane_times(stops: pd.DataFrame) -> pd.Series:
    """False for pit lane times too short for a normal trip down the pit lane (well under the race's
    median), as when the field is sent through the pit lane behind the safety car and the timing
    loops measure something else."""
    return stops["LaneTime"] >= 0.85 * stops["LaneTime"].median()


def _stop_loss(times, lap_time, pit_lap, driver: str, lap: int) -> float:
    """Seconds a stop on `lap` cost `driver` against the cars that stayed out."""
    if lap - 1 not in times.index or lap + 1 not in times.index:
        return np.nan
    two_laps = times.loc[lap + 1] - times.loc[lap - 1]  # in-lap + out-lap, every car
    stayed_out = ~(pit_lap.loc[lap] | pit_lap.loc[lap + 1])
    field = two_laps[stayed_out].drop(driver, errors="ignore").dropna()
    if pd.isna(two_laps.get(driver)) or len(field) == 0:
        return np.nan

    # How much slower (+) or quicker (-) than the field this car was on normal laps just before.
    offsets = []
    for k in range(max(2, lap - 4), lap):
        if k not in lap_time.index or pit_lap.at[k, driver]:
            continue
        others = lap_time.loc[k][~pit_lap.loc[k]].drop(driver, errors="ignore").dropna()
        own = lap_time.at[k, driver]
        if len(others) and pd.notna(own):
            offsets.append(own - others.median())
    offset = float(np.median(offsets)) if offsets else 0.0
    return round(float(two_laps[driver] - field.median() - 2 * offset), 1)


def pit_loss(stops: pd.DataFrame) -> float | None:
    """Typical cost of a green-flag stop at this race (median), in seconds."""
    green = stops.loc[~stops["Neutralised"], "Loss"].dropna()
    # Ignore obvious outliers: slow stops, drive-throughs, damage.
    green = green[(green > 5) & (green < 60)]
    return round(float(green.median()), 1) if len(green) else None


MIN_STOPS_FOR_RACE_ESTIMATE = 3


def pit_loss_now(
    stops_so_far: pd.DataFrame, status: str, reference: dict[str, float] | None
) -> tuple[float | None, str]:
    """The pit loss a strategist would use at this moment, and where it comes from.

    Before enough green-flag stops have happened, the circuit's reference
    figure; after that, the median of this race's stops. Under a safety car
    or VSC a stop is cheaper, so the figure is the circuit's SC/VSC value (or
    this race's figure scaled by the same ratio).
    """
    key = {"Safety car": "sc", "VSC": "vsc", "VSC ending": "vsc"}.get(status, "normal")
    green = stops_so_far[~stops_so_far["Neutralised"]] if len(stops_so_far) else stops_so_far
    measured = pit_loss(stops_so_far) if len(green) >= MIN_STOPS_FOR_RACE_ESTIMATE else None
    label = {"sc": "safety car", "vsc": "VSC"}.get(key)

    if measured is not None:
        if key != "normal" and reference and key in reference:
            return round(measured * reference[key] / reference["normal"], 1), f"this race, scaled for the {label}"
        return measured, f"median of {len(green)} green-flag stops"
    if reference:
        value = reference.get(key, reference["normal"])
        return round(value, 1), "circuit reference" + (f" under {label}" if label else "")
    return None, "no estimate yet"


def pit_battles(laps: pd.DataFrame, stops: pd.DataFrame, max_gap: float = 3.5, window: int = 6) -> pd.DataFrame:
    """Undercut and overcut attempts between cars running close together.

    For each green-flag stop, the rivals within `max_gap` seconds just ahead
    of and just behind the stopping car are checked. If that rival stops
    within `window` laps afterwards, the gap is compared before the first
    stop and after both have pitted.
    """
    times = _lap_times(laps)
    stop_laps = stops.groupby("Driver")["Lap"].apply(list).to_dict()
    rows = []
    for s in stops[~stops["Neutralised"]].itertuples():
        a, lap = s.Driver, s.Lap
        if lap - 1 not in times.index or pd.isna(times.at[lap - 1, a]):
            continue
        before = times.loc[lap - 1].dropna()
        gaps = before - before[a]  # > 0: that car is behind a
        ahead = gaps[(gaps < 0) & (gaps >= -max_gap)]
        behind = gaps[(gaps > 0) & (gaps <= max_gap)]
        rivals = ([ahead.idxmax()] if len(ahead) else []) + ([behind.idxmin()] if len(behind) else [])

        for b in rivals:
            later = [m for m in stop_laps.get(b, []) if lap < m <= lap + window]
            if not later:
                continue
            m = later[0]
            after_lap = m + 1  # both cars have now been through the pits
            if after_lap not in times.index or pd.isna(times.at[after_lap, a]) or pd.isna(times.at[after_lap, b]):
                continue
            gap_before = times.at[lap - 1, a] - times.at[lap - 1, b]  # > 0: a behind b
            gap_after = times.at[after_lap, a] - times.at[after_lap, b]
            if gap_before > 0:
                verdict = "Undercut worked" if gap_after < 0 else "Undercut failed"
            else:
                verdict = "Overcut worked" if gap_after > 0 else "Held position"
            rows.append(
                {
                    "Lap": lap,
                    "FirstStop": a,
                    "Rival": b,
                    "RivalStopLap": m,
                    "GapBefore": round(gap_before, 2),
                    "GapAfter": round(gap_after, 2),
                    "Gained": round(gap_before - gap_after, 2),  # time the first stopper gained
                    "Verdict": verdict,
                }
            )
    cols = ["Lap", "FirstStop", "Rival", "RivalStopLap", "GapBefore", "GapAfter", "Gained", "Verdict"]
    return pd.DataFrame(rows, columns=cols)


def rejoin_projection(tower: pd.DataFrame, loss: float) -> pd.DataFrame:
    """Where each car on the lead lap would rejoin if it pitted at the end of this lap.

    `tower` is `timing_tower(...)` for the current lap. The projection adds
    the pit loss to the car's gap to the leader and slots it back in among
    the cars that stay out.
    """
    lead_lap = tower[tower["GapSeconds"].notna() & ~tower["Out"]].copy()
    gaps = lead_lap.set_index("Driver")["GapSeconds"]
    rows = []
    for driver, gap in gaps.items():
        others = gaps.drop(driver)
        projected = gap + loss
        ahead = others[others <= projected]
        behind = others[others > projected]
        rows.append(
            {
                "Driver": driver,
                "Now": int(tower.loc[tower["Driver"] == driver, "Pos"].iloc[0]),
                "Rejoin": len(ahead) + 1,
                "CarAhead": ahead.idxmax() if len(ahead) else "",
                "GapAhead": round(projected - ahead.max(), 1) if len(ahead) else np.nan,
                "CarBehind": behind.idxmin() if len(behind) else "",
                "GapBehind": round(behind.min() - projected, 1) if len(behind) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def pair_gap(laps: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    """Gap between two cars at the end of every lap (> 0: `a` behind `b`)."""
    times = _lap_times(laps)
    if a not in times or b not in times:
        return pd.DataFrame(columns=["LapNumber", "Gap"])
    gap = (times[a] - times[b]).dropna()
    return pd.DataFrame({"LapNumber": gap.index.astype(int), "Gap": gap.to_numpy()})
