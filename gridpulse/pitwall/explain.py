"""Plain-language race explanations, computed only from the replay's known laps.

The guide and the workbench share the same tyre fit and one-final-stop scenarios.
No lesson uses a later result to decide what a visitor should do now.
"""

from dataclasses import dataclass

import pandas as pd

from gridpulse.pitwall.data import RaceData
from gridpulse.undercut.analysis import pit_loss_now
from gridpulse.undercut.window import DRY, TyreModel, best_plan, compounds_allowed, fit_tyre_model, pit_window


def name(race: RaceData, driver: str) -> str:
    value = race.full_names.get(driver)
    return str(value) if pd.notna(value) and value else driver


def names(race: RaceData) -> dict[str, str]:
    return {d: name(race, d) for d in race.entrants.Driver}


@dataclass
class StrategyContext:
    loss: float | None
    source: str
    model: TyreModel | None


def prepare(race: RaceData, tower: pd.DataFrame, lap: int) -> StrategyContext:
    stops = race.stops_through(lap)
    loss, source = pit_loss_now(stops[stops.Lap < lap], race.lap_status.get(lap, 'Green'), race.pit_loss_ref)
    model = fit_tyre_model(race.clean_through(lap), allow_prior=(~tower.Out & tower.Compound.isin(DRY)).any())
    return StrategyContext(loss, source, model)


def plan(race: RaceData, tower: pd.DataFrame, lap: int, driver: str, context: StrategyContext):
    rows = tower[tower.Driver == driver]
    if rows.empty or context.model is None or not context.loss or race.total_laps - lap < 2:
        return None, None
    row = rows.iloc[0]
    if row.Out or row.LapsDown or row.Compound not in DRY or pd.isna(row.TyreAge):
        return None, None
    used = set(race.laps[(race.laps.Driver == driver) & (race.laps.LapNumber <= lap)].Compound.dropna())
    window = pit_window(context.model, driver, row.Compound, float(row.TyreAge), race.total_laps - lap,
                        context.loss, compounds_allowed(used))
    return best_plan(window), window


def comparison(window: pd.DataFrame, compound: str, wait: int) -> dict | None:
    """Compare two legal scenarios on the *same* fresh compound; negative means less time.

    wait=3 is two laps later than the earliest modelled stop (wait=1).
    """
    fresh = window[window.Compound == compound]
    first, chosen = fresh[fresh.LapsMore == 1], fresh[fresh.LapsMore == wait]
    if first.empty or chosen.empty:
        return None
    return {'delta': float(chosen.iloc[0].Total - first.iloc[0].Total),
            'cost': float(chosen.iloc[0].Lost), 'next_cost': float(first.iloc[0].Lost)}


def situation(race: RaceData, tower: pd.DataFrame, lap: int) -> str:
    if tower.empty:
        return f'Lap {lap} of {race.total_laps}. Timing is unavailable.'
    lead = tower.iloc[0]
    text = f'Lap {lap} of {race.total_laps}: {name(race, lead.Driver)} leads'
    if len(tower) > 1:
        second = tower.iloc[1]
        if not second.Out and second.LapsDown == 0 and pd.notna(second.GapSeconds):
            text += f' {name(race, second.Driver)} by {second.GapSeconds:.1f} seconds'
    recent = race.stops_through(lap)
    now = recent[recent.Lap == lap]
    if not now.empty:
        text += '. Pitting this lap: ' + ', '.join(name(race, d) for d in now.Driver)
    return text + '.'


def takeaway(race: RaceData, tower: pd.DataFrame, lap: int, driver: str, context: StrategyContext) -> str:
    best, window = plan(race, tower, lap, driver, context)
    if best is None:
        return 'No dry-tyre stop estimate is available for this driver at this lap.'
    stop = lap + int(best.LapsMore)
    first = window[(window.Compound == best.Compound) & (window.LapsMore == 1)].iloc[0]
    timing = ('stopping on the next lap' if int(best.LapsMore) == 1 else f'waiting until lap {stop}')
    return (f'For {name(race, driver)}, this one-more-stop model favours {timing} and fitting '
            f'{best.Compound.lower()} tyres. Stopping next lap on the same tyre is '
            f'{first.Lost:.1f} seconds slower than that model plan. '
            + ('Typical tyre wear is used until measured dry laps are available. ' if context.model.prior_only else '')
            + 'This is a simplified scenario, not a prediction of who wins.')
