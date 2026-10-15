"""Race pace and tyre degradation from lap-level timing data.

The idea: a lap time is mostly "car + driver pace", plus a penalty that grows
as the tyre wears, minus a bonus as the car gets lighter from burning fuel.
If we keep only representative green-flag laps and correct for fuel, the
slope of lap time against tyre age within a stint is the degradation rate.
"""

import numpy as np
import pandas as pd

# Rule of thumb: ~1.6-1.8 kg of fuel per lap at ~0.03-0.035 s/kg.
# It's an approximation, but without it a light car hides tyre wear.
DEFAULT_FUEL_EFFECT_S_PER_LAP = 0.06

MIN_LAPS_FOR_FIT = 5


def plausible(laps: pd.DataFrame, floor: float = 0.85) -> pd.DataFrame:
    """Drop lap times too quick to be real (data glitches, e.g. a 55 s lap where 1:18 is normal)."""
    times = laps["LapTime"]
    seconds = times.dt.total_seconds() if pd.api.types.is_timedelta64_dtype(times) else times
    return laps[~(seconds < floor * seconds.median())]


def clean_race_laps(laps, drivers: list[str] | None = None) -> pd.DataFrame:
    """Return representative race laps as a tidy DataFrame.

    `laps` is a FastF1 session, its laps, or any DataFrame with the same
    columns (so OpenF1 data works too). Drops lap 1, in/out laps, laps under
    yellow/SC/VSC/red flag, laps flagged as inaccurate, and slow outliers
    (>107% of each driver's best).
    """
    laps = pd.DataFrame(getattr(laps, "laps", laps))
    if drivers:
        laps = laps[laps["Driver"].isin(drivers)]

    laps = laps[
        laps["PitInTime"].isna()
        & laps["PitOutTime"].isna()
        & (laps["TrackStatus"].astype(str) == "1")  # green flag for the whole lap
        & (laps["IsAccurate"] == True)  # noqa: E712 (column may hold NaN)
        & (laps["LapNumber"] > 1)
    ].dropna(subset=["Stint"])
    laps = plausible(laps.dropna(subset=["LapTime"]))

    df = pd.DataFrame(
        {
            "Driver": laps["Driver"],
            "Team": laps["Team"],
            "LapNumber": laps["LapNumber"].astype(int),
            "Stint": laps["Stint"].astype(int),
            "Compound": laps["Compound"].fillna("UNKNOWN"),
            "TyreLife": laps["TyreLife"],
            "LapTime": laps["LapTime"].dt.total_seconds(),
        }
    ).dropna(subset=["LapTime", "TyreLife"])

    best = df.groupby("Driver")["LapTime"].transform("min")
    return df[df["LapTime"] <= best * 1.07].reset_index(drop=True)


def add_fuel_corrected_time(
    laps: pd.DataFrame,
    total_laps: int,
    fuel_effect: float = DEFAULT_FUEL_EFFECT_S_PER_LAP,
) -> pd.DataFrame:
    """Add LapTimeFuelCorr: lap time as if every lap carried end-of-race fuel."""
    laps = laps.copy()
    laps_remaining = total_laps - laps["LapNumber"]
    laps["LapTimeFuelCorr"] = laps["LapTime"] - laps_remaining * fuel_effect
    return laps


def stint_degradation(laps: pd.DataFrame, time_col: str = "LapTimeFuelCorr") -> pd.DataFrame:
    """Fit a straight line of lap time vs tyre age for every stint.

    DegPerLap is the slope (seconds lost per lap of tyre age). Stints with
    fewer than MIN_LAPS_FOR_FIT clean laps are skipped as too noisy.
    """
    rows = []
    for (driver, stint), g in laps.groupby(["Driver", "Stint"]):
        if len(g) < MIN_LAPS_FOR_FIT:
            continue
        slope, intercept = np.polyfit(g["TyreLife"], g[time_col], 1)
        rows.append(
            {
                "Driver": driver,
                "Team": g["Team"].iloc[0],
                "Stint": stint,
                "Compound": g["Compound"].mode().iloc[0],
                "StartLap": int(g["LapNumber"].min()),
                "EndLap": int(g["LapNumber"].max()),
                "CleanLaps": len(g),
                "MedianLapTime": round(g["LapTime"].median(), 3),
                "DegPerLap": round(slope, 3),
            }
        )
    return pd.DataFrame(rows, columns=["Driver", "Team", "Stint", "Compound", "StartLap", "EndLap", "CleanLaps",
                                       "MedianLapTime", "DegPerLap"])
