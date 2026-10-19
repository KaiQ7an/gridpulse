"""A short, conditional undercut scenario using only the current timing tower and fitted pace.

The chaser stops next lap; the car ahead responds `delay` laps later. Compare their clocks
after both out-laps are complete. Both fit the selected fresh compound. Equal total stop
costs (including equal warm-up effects) cancel; `disadvantage` is an extra cost to the chaser.
This is a free-air scenario, not a prediction of the teams' stops, tyre stocks or traffic.
"""

import numpy as np
import pandas as pd

from gridpulse.undercut.window import DRY, MIN_STINT_LAPS, MODEL_Z, TyreModel, lap_coefficients

COLUMNS = ['Ahead', 'Chaser', 'Gap', 'Gain', 'Margin', 'Low', 'High', 'Status', 'PriorLed',
           'AheadSamples', 'ChaserSamples', 'AheadAge', 'ChaserAge']


def _eligible(row) -> bool:
    return (pd.notna(row.Out) and not row.Out and pd.notna(row.LapsDown) and row.LapsDown == 0
            and pd.notna(row.Pit) and not row.Pit
            and pd.notna(row.get('PitOut', False)) and not row.get('PitOut', False)
            and pd.notna(row.Compound) and row.Compound in DRY
            and pd.notna(row.TyreAge) and np.isfinite(float(row.TyreAge)) and row.TyreAge >= 0
            and pd.notna(row.GapSeconds) and np.isfinite(float(row.GapSeconds)))


def undercut_radar(model: TyreModel | None, tower: pd.DataFrame, *, status: str, laps_left: int,
                   compound: str = 'HARD', delay: int = 1, disadvantage: float = 0.0,
                   max_gap: float = 3.5) -> pd.DataFrame:
    """Adjacent lead-lap pairs; positive Margin means the first stopper would finish ahead.

    Low/High are approximate central 90% model ranges, including independent future lap noise.
    No strong edge is labelled until both drivers have five retained clean laps and the
    relevant compound offsets/wear have race evidence. Missing driver pace is never replaced
    with the field's average. Yellow/SC/VSC/red flags suspend this green-flag scenario.
    """
    if compound not in DRY or delay not in (1, 2, 3) or not np.isfinite(disadvantage) or disadvantage < 0:
        raise ValueError('Use a dry compound, a 1–3 lap response and a non-negative extra cost.')
    if not np.isfinite(max_gap) or max_gap <= 0:
        raise ValueError('The scan gap must be positive and finite.')
    if model is None or model.prior_only or status != 'Green' or laps_left < delay + 2:
        return pd.DataFrame(columns=COLUMNS)
    rows = []
    ordered = tower.sort_values('Pos').reset_index(drop=True)
    n = delay + 2
    for i in range(1, len(ordered)):
        ahead, chaser = ordered.iloc[i - 1], ordered.iloc[i]
        # Check neighbours before filtering; a missing/wet/pitting car must not be jumped over.
        if not _eligible(ahead) or not _eligible(chaser):
            continue
        gap = float(chaser.GapSeconds - ahead.GapSeconds)
        if not 0 <= gap <= max_gap or any(d not in model.base for d in (ahead.Driver, chaser.Driver)):
            continue
        a_ages = float(ahead.TyreAge) + np.arange(1, n)
        b_ages = np.arange(1, n)
        gain = float(np.sum(model.lap_time(ahead.Driver, ahead.Compound, a_ages))
                     + model.lap_time(ahead.Driver, compound, 1)
                     - model.lap_time(chaser.Driver, chaser.Compound, float(chaser.TyreAge) + 1)
                     - np.sum(model.lap_time(chaser.Driver, compound, b_ages)) - disadvantage)
        margin = gain - gap
        sd = None
        if all(d in model.parameter_drivers for d in (ahead.Driver, chaser.Driver)):
            weights = (lap_coefficients(model, ahead.Driver, ahead.Compound, a_ages)
                       + lap_coefficients(model, ahead.Driver, compound, 1)
                       - lap_coefficients(model, chaser.Driver, chaser.Compound, float(chaser.TyreAge) + 1)
                       - lap_coefficients(model, chaser.Driver, compound, b_ages))
            sd = model.contrast_sd(weights, future_laps=2 * n)
        low, high = (margin - MODEL_Z * sd, margin + MODEL_Z * sd) if sd is not None else (np.nan, np.nan)
        a_count, b_count = (model.driver_samples.get(d, 0) for d in (ahead.Driver, chaser.Driver))
        relevant = {ahead.Compound, chaser.Compound, compound}
        prior_led = not relevant <= (model.measured & model.deg_measured)
        if min(a_count, b_count) < MIN_STINT_LAPS:
            label = 'Learning'
        elif sd is None:
            label = 'Range unavailable'
        elif prior_led:
            label = 'Prior-led'
        else:
            label = 'Model edge' if low > 0 else ('No edge' if high < 0 else 'Uncertain')
        rows.append(dict(zip(COLUMNS, [ahead.Driver, chaser.Driver, gap, gain, margin, low, high, label,
                                       prior_led, a_count, b_count, float(ahead.TyreAge), float(chaser.TyreAge)])))
    return pd.DataFrame(rows, columns=COLUMNS).sort_values('Margin', ascending=False).reset_index(drop=True)
