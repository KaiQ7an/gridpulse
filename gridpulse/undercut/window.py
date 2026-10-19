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
MODEL_Z = 1.6448536269514722  # central 90% Gaussian model range, not calibrated race odds


@dataclass
class TyreModel:
    base: dict[str, float]  # driver -> lap time on fresh mediums with the trend taken out, s
    offset: dict[str, float]  # compound -> s a lap against the medium on fresh tyres
    deg: dict[str, float]  # compound -> s lost per lap of tyre age
    trend: float = TYPICAL_TREND  # s a lap gained every lap (fuel and track), the same for every car
    measured: set[str] = field(default_factory=set)  # compounds whose pace was measured in this race
    deg_measured: set[str] = field(default_factory=set)  # compounds whose wear was measured
    sample_counts: dict[str, int] = field(default_factory=dict)  # retained clean laps per compound
    prior_only: bool = False  # no observed dry pace; compare plans for one car, not relative driver pace
    driver_samples: dict[str, int] = field(default_factory=dict)
    parameter_drivers: tuple[str, ...] = ()
    covariance: tuple[tuple[float, ...], ...] | None = None
    noise_sd: float = LAP_NOISE_SD
    bounded_wear: bool = False

    @property
    def field_base(self) -> float:
        return float(np.median(list(self.base.values()))) if self.base else 0.0

    def lap_time(self, driver: str, compound: str, age) -> np.ndarray | float:
        """Lap time for `driver` on `compound` at tyre age `age` (a number or an array), without the trend.

        Plans are compared over the same laps, so the trend adds the same to each and drops out.
        """
        return self.base.get(driver, self.field_base) + self.offset[compound] + self.deg[compound] * np.asarray(age)

    def contrast_sd(self, weights: np.ndarray, *, future_laps: int = 0) -> float | None:
        """Uncertainty of a linear contrast, retaining correlations between fitted parameters.

        `future_laps` adds independent lap noise for a race projection. Relative stop-plan
        curves use parameter uncertainty only. No Gaussian range is claimed after clipping wear.
        """
        if self.covariance is None or self.bounded_wear:
            return None
        variance = float(weights @ np.asarray(self.covariance) @ weights)
        return float(np.sqrt(max(0.0, variance) + future_laps * self.noise_sd ** 2))


def fit_tyre_model(clean: pd.DataFrame, *, allow_prior: bool = False) -> TyreModel | None:
    """Fit the model to clean laps (Driver, Stint, Compound, TyreLife, LapNumber, LapTime in s).

    With no dry observations, an explicit opt-in returns typical tyre parameters. The common
    driver pace cancels between that driver's stop plans, so no qualifying time, opening-lap
    time or future race pace is needed. It cannot support a catch prediction between drivers.
    Callers opt in only when the current tyres are known to be slicks; wet running stays unsupported.
    """
    dry = clean[clean["Compound"].isin(DRY)].dropna(subset=["LapTime", "TyreLife", "LapNumber"])
    if dry.empty:
        return TyreModel(base={}, offset=TYPICAL_OFFSET.copy(), deg=TYPICAL_DEG.copy(),
                         sample_counts=dict.fromkeys(DRY, 0), prior_only=True,
                         covariance=tuple(map(tuple, np.diag([
                             PRIOR_SD['offset'] ** 2, PRIOR_SD['offset'] ** 2,
                             *[PRIOR_SD['deg'] ** 2] * 3, PRIOR_SD['trend'] ** 2])))) if allow_prior else None
    theta, drivers, information_inverse = _solve(dry)
    residual = dry["LapTime"].to_numpy(float) - _design(dry, drivers) @ theta
    spread = max(1.4826 * float(np.median(np.abs(residual - np.median(residual)))), 0.15)
    keep = np.abs(residual) <= 3 * spread  # traffic and mistakes that got past the clean-lap filter
    if keep.sum() >= len(drivers) + 2 and not keep.all():
        dry = dry[keep]
        theta, drivers, information_inverse = _solve(dry)

    residual = dry['LapTime'].to_numpy(float) - _design(dry, drivers) @ theta
    noise_sd = max(LAP_NOISE_SD, 1.4826 * float(np.median(np.abs(residual - np.median(residual)))))

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
        sample_counts={c: int(counts.get(c, 0)) for c in DRY},
        driver_samples={d: int(count) for d, count in dry['Driver'].value_counts().items()},
        parameter_drivers=tuple(drivers),
        covariance=tuple(map(tuple, information_inverse * noise_sd ** 2)),
        noise_sd=noise_sd,
        bounded_wear=any(not 0 <= theta[n + 2 + j] <= 0.4 for j in range(3)),
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


def _solve(laps: pd.DataFrame) -> tuple[np.ndarray, list[str], np.ndarray]:
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
    augmented = np.vstack([x, rows])
    theta, *_ = np.linalg.lstsq(augmented, np.concatenate([y, targets]), rcond=None)
    # SVD avoids squaring the condition number when inverting the penalized information.
    _, singular, right = np.linalg.svd(augmented, full_matrices=False)
    inverse = (right.T / singular ** 2) @ right
    return theta, drivers, inverse


def lap_coefficients(model: TyreModel, driver: str | None, compound: str, ages) -> np.ndarray:
    """Coefficients for a sum of laps, in the fit's parameter order, without the shared trend.

    `driver=None` removes common driver pace when comparing that driver's alternative plans.
    The trend also cancels because both plans span exactly the same race laps.
    """
    n = len(model.parameter_drivers)
    weights = np.zeros(n + 6)
    ages = np.atleast_1d(ages)
    if driver is not None:
        weights[model.parameter_drivers.index(driver)] = len(ages)
    if compound in ('SOFT', 'HARD'):
        weights[n + (compound == 'HARD')] = len(ages)
    weights[n + 2 + DRY.index(compound)] = np.sum(ages)
    return weights


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
    if model.covariance is not None and not model.bounded_wear:
        vectors = [lap_coefficients(model, None, compound, age + np.arange(1, r.LapsMore + 1))
                   + lap_coefficients(model, None, r.Compound, np.arange(1, laps_left - r.LapsMore + 1))
                   for r in out.itertuples()]
        reference = vectors[int(out['Total'].idxmin())]
        half = np.array([MODEL_Z * model.contrast_sd(vector - reference) for vector in vectors])
        out['LostLow'], out['LostHigh'] = out['Lost'] - half, out['Lost'] + half
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
    from gridpulse.undercut.analysis import pit_loss_now

    rows = []
    stops = race.stops[~race.stops["Neutralised"] & race.stops["To"].isin(DRY) & race.stops["From"].isin(DRY)]
    last = stops.sort_values("Lap").groupby("Driver").tail(1)
    for s in last.itertuples():
        plan_lap = s.Lap - horizon
        if plan_lap < 5:
            continue
        model = fit_tyre_model(race.clean_through(plan_lap))
        on = race.laps[(race.laps["Driver"] == s.Driver) & (race.laps["LapNumber"] == plan_lap)]
        if model is None or on.empty or pd.isna(on["TyreLife"].iloc[0]) or on["Compound"].iloc[0] not in DRY:
            continue
        loss, _ = pit_loss_now(race.stops_through(plan_lap).query("Lap < @plan_lap"), "Green", race.pit_loss_ref)
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
