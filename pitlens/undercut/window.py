"""A tyre model for the pit window: when to stop, and how fast fresher tyres close a gap.

On representative laps (no pit laps, safety cars or traffic outliers) a lap time is modelled as

    driver's pace + compound offset + compound wear x tyre age + trend x lap number

where the trend is the car getting lighter and the track rubbering in, which is the same for
everyone. All of it is one least-squares fit over every clean lap so far. Fresh tyres after a
stop are what tell wear and trend apart: the lap time jumps back by the wear, not the trend.
Typical figures act as weak priors, so a compound nobody has run yet, or a race with few laps,
still gives sensible numbers. The replay only fits on laps up to the one being shown, so it
knows what the pit wall knew then.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DRY = ("SOFT", "MEDIUM", "HARD")
TYPICAL_OFFSET = {"SOFT": -0.5, "MEDIUM": 0.0, "HARD": 0.4}  # s a lap on fresh tyres, against the medium
TYPICAL_DEG = {"SOFT": 0.09, "MEDIUM": 0.06, "HARD": 0.04}  # s lost per lap of tyre age
TYPICAL_TREND = -0.06  # s a lap quicker every lap from fuel burn and track evolution
# How far each figure is expected to stray from the typical one, against the noise of one lap.
PRIOR_SD = {"offset": 0.4, "deg": 0.01, "trend": 0.03}  # wear: tight, see backtest()
LAP_NOISE_SD = 0.3
MIN_STINT_LAPS = 5  # clean laps in one stint before a compound's wear counts as measured
MIN_COMPOUND_LAPS = 8  # clean laps before a compound's pace counts as measured
WINDOW_SECONDS = 1.0  # stopping laps within this of the best count as the window


@dataclass
class TyreModel:
    base: dict[str, float]  # driver -> lap time on fresh mediums with the trend taken out, s
    offset: dict[str, float]  # compound -> s a lap against the medium on fresh tyres
    deg: dict[str, float]  # compound -> s lost per lap of tyre age
    trend: float = TYPICAL_TREND  # s a lap gained every lap (fuel and track), the same for every car
    measured: set[str] = field(default_factory=set)  # compounds whose pace was measured in this race
    deg_measured: set[str] = field(default_factory=set)  # compounds whose wear was measured

    @property
    def field_base(self) -> float:
        return float(np.median(list(self.base.values()))) if self.base else 0.0

    def lap_time(self, driver: str, compound: str, age) -> np.ndarray | float:
        """Lap time for `driver` on `compound` at tyre age `age` (a number or an array), without the trend.

        Plans are compared over the same laps, so the trend adds the same to each and drops out.
        """
        return self.base.get(driver, self.field_base) + self.offset[compound] + self.deg[compound] * np.asarray(age)


def fit_tyre_model(clean: pd.DataFrame) -> TyreModel | None:
    """Fit the model to clean laps (Driver, Stint, Compound, TyreLife, LapNumber, LapTime in s).

    None without dry laps.
    """
    dry = clean[clean["Compound"].isin(DRY)].dropna(subset=["LapTime", "TyreLife", "LapNumber"])
    if dry.empty:
        return None
    theta, drivers = _solve(dry)
    residual = dry["LapTime"].to_numpy(float) - _design(dry, drivers) @ theta
    spread = max(1.4826 * float(np.median(np.abs(residual - np.median(residual)))), 0.15)
    keep = np.abs(residual) <= 3 * spread  # traffic and mistakes that got past the clean-lap filter
    if keep.sum() >= len(drivers) + 2 and not keep.all():
        dry = dry[keep]
        theta, drivers = _solve(dry)

    n = len(drivers)
    offset = {"SOFT": float(theta[n]), "MEDIUM": 0.0, "HARD": float(theta[n + 1])}
    deg = {c: float(np.clip(theta[n + 2 + j], 0.0, 0.4)) for j, c in enumerate(DRY)}
    counts = dry["Compound"].value_counts()
    stint_laps = dry.groupby(["Driver", "Stint"])["Compound"].agg(["first", "size"])
    return TyreModel(
        base={d: float(theta[i]) for i, d in enumerate(drivers)},
        offset=offset,
        deg=deg,
        trend=float(theta[n + 5]),
        measured={c for c in DRY if counts.get(c, 0) >= MIN_COMPOUND_LAPS},
        deg_measured=set(stint_laps.loc[stint_laps["size"] >= MIN_STINT_LAPS, "first"]),
    )


def _design(laps: pd.DataFrame, drivers: list[str]) -> np.ndarray:
    """Columns: one per driver, soft and hard offsets, wear per compound, trend per lap."""
    n = len(drivers)
    x = np.zeros((len(laps), n + 6))
    index = laps["Driver"].map({d: i for i, d in enumerate(drivers)}).to_numpy()
    x[np.arange(len(laps)), index] = 1.0
    compound = laps["Compound"].to_numpy()
    age = laps["TyreLife"].to_numpy(float)
    x[:, n] = compound == "SOFT"
    x[:, n + 1] = compound == "HARD"
    for j, c in enumerate(DRY):
        x[:, n + 2 + j] = age * (compound == c)
    x[:, n + 5] = laps["LapNumber"].to_numpy(float)
    return x


def _solve(laps: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Least squares with the typical figures as weak priors (extra rows pulling each towards them)."""
    drivers = sorted(laps["Driver"].unique())
    n = len(drivers)
    x = _design(laps, drivers)
    y = laps["LapTime"].to_numpy(float)
    priors = [(n, TYPICAL_OFFSET["SOFT"], PRIOR_SD["offset"]), (n + 1, TYPICAL_OFFSET["HARD"], PRIOR_SD["offset"])]
    priors += [(n + 2 + j, TYPICAL_DEG[c], PRIOR_SD["deg"]) for j, c in enumerate(DRY)]
    priors += [(n + 5, TYPICAL_TREND, PRIOR_SD["trend"])]
    rows = np.zeros((len(priors), n + 6))
    targets = np.zeros(len(priors))
    for i, (column, value, sd) in enumerate(priors):
        weight = LAP_NOISE_SD / sd
        rows[i, column] = weight
        targets[i] = value * weight
    theta, *_ = np.linalg.lstsq(np.vstack([x, rows]), np.concatenate([y, targets]), rcond=None)
    return theta, drivers


def compounds_allowed(used: set[str]) -> list[str]:
    """Dry compounds a car may fit for its last stop: in a dry race it must have run two different ones."""
    dry_used = used & set(DRY)
    if len(dry_used) == 1:
        return [c for c in DRY if c not in dry_used]
    return list(DRY)


def pit_window(model: TyreModel, driver: str, compound: str, age: float, laps_left: int, loss: float,
               choices: list[str]) -> pd.DataFrame:
    """Time to the flag for every plan "k more laps on these tyres, stop, then the new set to the end".

    k runs from 1 (stop at the end of the next lap) to laps_left - 1. Returns one row per plan:
    Compound, LapsMore (k), Total (s) and Lost (s over the best plan).
    """
    rows = []
    if laps_left < 2:
        return pd.DataFrame(columns=["Compound", "LapsMore", "Total", "Lost"])
    old = np.cumsum(model.lap_time(driver, compound, age + np.arange(1, laps_left + 1)))  # old[k-1]: k laps on
    for new_compound in choices:
        fresh = np.cumsum(model.lap_time(driver, new_compound, np.arange(1, laps_left + 1)))  # fresh[n-1]: n laps
        for k in range(1, laps_left):
            rows.append({"Compound": new_compound, "LapsMore": k,
                         "Total": float(old[k - 1] + loss + fresh[laps_left - k - 1])})
    out = pd.DataFrame(rows)
    out["Lost"] = out["Total"] - out["Total"].min()
    return out


def stay_out_time(model: TyreModel, driver: str, compound: str, age: float, laps_left: int) -> float:
    """Time to the flag without stopping again."""
    return float(np.sum(model.lap_time(driver, compound, age + np.arange(1, laps_left + 1))))


def best_plan(window: pd.DataFrame) -> pd.Series:
    """The quickest plan, and the span of stopping laps within WINDOW_SECONDS of it on that compound."""
    best = window.loc[window["Total"].idxmin()].copy()
    same = window[(window["Compound"] == best["Compound"]) & (window["Lost"] <= WINDOW_SECONDS)]
    best["From"], best["To"] = int(same["LapsMore"].min()), int(same["LapsMore"].max())
    return best


def laps_to_catch(model: TyreModel, chaser: str, chaser_compound: str, chaser_age: float, ahead: str,
                  ahead_compound: str, ahead_age: float, gap: float, laps_left: int) -> int | None:
    """Laps until the chaser has closed `gap` seconds on the car ahead, or None if it won't before the flag."""
    if laps_left < 1 or gap <= 0:
        return 0 if gap <= 0 else None
    n = np.arange(1, laps_left + 1)
    closing = np.cumsum(model.lap_time(ahead, ahead_compound, ahead_age + n)
                        - model.lap_time(chaser, chaser_compound, chaser_age + n))
    reached = np.nonzero(closing >= gap)[0]
    return int(reached[0] + 1) if len(reached) else None


def backtest(race, horizon: int = 10) -> pd.DataFrame:
    """How the model's best stopping lap compares with each driver's actual last green-flag stop.

    For a stop at the end of lap s the model sees only clean laps up to lap s - horizon (what a
    strategist planning that far ahead would have had) and the pit loss known then, and picks the
    best lap for the tyre the driver actually fitted. For comparison, EvenSplit is the rule of
    thumb that needs no model: stop where the old and new stints come out the same length.
    Returns Driver, Lap (actual), Predicted, EvenSplit, Error (predicted - actual),
    EvenSplitError and InWindow (actual lap within a second of the best plan).
    """
    from pitlens.undercut.analysis import pit_loss_now

    rows = []
    stops = race.stops[~race.stops["Neutralised"] & race.stops["To"].isin(DRY) & race.stops["From"].isin(DRY)]
    last = stops.sort_values("Lap").groupby("Driver").tail(1)
    for s in last.itertuples():
        plan_lap = s.Lap - horizon
        if plan_lap < 5:
            continue
        model = fit_tyre_model(race.clean_laps[race.clean_laps["LapNumber"] <= plan_lap])
        on = race.laps[(race.laps["Driver"] == s.Driver) & (race.laps["LapNumber"] == plan_lap)]
        if model is None or on.empty or pd.isna(on["TyreLife"].iloc[0]) or on["Compound"].iloc[0] not in DRY:
            continue
        loss, _ = pit_loss_now(race.stops[race.stops["Lap"] <= plan_lap], "Green", race.pit_loss_ref)
        if loss is None:
            continue
        age, laps_left = float(on["TyreLife"].iloc[0]), race.total_laps - plan_lap
        best = best_plan(pit_window(model, s.Driver, on["Compound"].iloc[0], age, laps_left, loss, [s.To]))
        rows.append({"Driver": s.Driver, "Lap": int(s.Lap), "Predicted": plan_lap + int(best["LapsMore"]),
                     "EvenSplit": plan_lap + max(1, round((laps_left - age) / 2)),
                     "InWindow": plan_lap + best["From"] <= s.Lap <= plan_lap + best["To"]})
    out = pd.DataFrame(rows, columns=["Driver", "Lap", "Predicted", "EvenSplit", "InWindow"])
    out["Error"] = out["Predicted"] - out["Lap"]
    out["EvenSplitError"] = out["EvenSplit"] - out["Lap"]
    return out
