import numpy as np
import pandas as pd
import pytest

from pitlens.undercut.window import (
    TYPICAL_OFFSET,
    TyreModel,
    best_plan,
    compounds_allowed,
    fit_tyre_model,
    laps_to_catch,
    pit_window,
    stay_out_time,
)

# Known truth: A is 0.5 s a lap quicker than B; the soft is 0.6 s quicker than the medium when new
# but wears 0.10 s a lap against the medium's 0.05; fuel and track take 0.08 s a lap off everyone.
BASE = {"A": 80.0, "B": 80.5}
OFFSET = {"SOFT": -0.6, "MEDIUM": 0.0}
DEG = {"SOFT": 0.10, "MEDIUM": 0.05}
TREND = -0.08


def stint(driver, compound, number, laps, first_lap=1, noise=0.0, rng=None):
    rows = []
    for age in range(1, laps + 1):
        lap = first_lap + age - 1
        t = BASE[driver] + OFFSET[compound] + DEG[compound] * age + TREND * lap
        if rng is not None:
            t += rng.normal(0, noise)
        rows.append({"Driver": driver, "Stint": number, "Compound": compound, "TyreLife": float(age),
                     "LapNumber": lap, "LapTime": t})
    return rows


@pytest.fixture
def clean():
    # A race's worth of laps (ten cars each of A's and B's pace), so the data outweighs the priors.
    rows = []
    for i in range(10):
        a, b = f"A{i}", f"B{i}"
        BASE[a], BASE[b] = BASE["A"], BASE["B"]
        rows += stint(a, "SOFT", 1, 12 + i % 3) + stint(a, "MEDIUM", 2, 25, first_lap=13 + i % 3)
        rows += stint(b, "MEDIUM", 1, 15 + i % 4) + stint(b, "SOFT", 2, 14, first_lap=16 + i % 4)
    return pd.DataFrame(rows)


def test_fit_recovers_pace_offsets_wear_and_trend(clean):
    model = fit_tyre_model(clean)
    assert model.base["A0"] == pytest.approx(80.0, abs=0.05)
    assert model.base["B3"] == pytest.approx(80.5, abs=0.05)
    assert model.offset["SOFT"] == pytest.approx(-0.6, abs=0.05)
    assert model.offset["MEDIUM"] == 0
    assert model.deg["SOFT"] == pytest.approx(0.10, abs=0.01)
    assert model.deg["MEDIUM"] == pytest.approx(0.05, abs=0.01)
    # The stops (tyre age back to one, lap number carrying on) separate wear from the trend.
    assert model.trend == pytest.approx(-0.08, abs=0.01)
    assert model.measured == {"SOFT", "MEDIUM"}
    # Nobody ran the hard: typical gap to the medium, flagged as not measured.
    assert model.offset["HARD"] == pytest.approx(TYPICAL_OFFSET["HARD"] - TYPICAL_OFFSET["MEDIUM"], abs=0.1)
    assert "HARD" not in model.measured


def test_fit_copes_with_noise():
    rng = np.random.default_rng(1)
    rows = []
    for driver in BASE:
        rows += stint(driver, "SOFT", 1, 14, noise=0.15, rng=rng)
        rows += stint(driver, "MEDIUM", 2, 25, first_lap=15, noise=0.15, rng=rng)
    model = fit_tyre_model(pd.DataFrame(rows))
    assert model.deg["MEDIUM"] == pytest.approx(0.05, abs=0.03)
    assert model.base["B"] - model.base["A"] == pytest.approx(0.5, abs=0.15)


def test_traffic_laps_dont_drag_the_fit():
    rows = stint("A", "SOFT", 1, 12) + stint("A", "MEDIUM", 2, 20, first_lap=13)
    rows += stint("B", "MEDIUM", 1, 15) + stint("B", "SOFT", 2, 12, first_lap=16)
    laps = pd.DataFrame(rows)
    laps.loc[[3, 20, 40], "LapTime"] += 2.5  # stuck behind slower cars
    model = fit_tyre_model(laps)
    assert model.deg["MEDIUM"] == pytest.approx(0.05, abs=0.01)


def test_no_dry_laps_no_model():
    wet = pd.DataFrame({"Driver": ["A"], "Stint": [1], "Compound": ["INTERMEDIATE"], "TyreLife": [3.0],
                        "LapNumber": [5], "LapTime": [95.0]})
    assert fit_tyre_model(wet) is None


def test_pit_window_matches_a_hand_calculation():
    model = TyreModel(base={"A": 80.0}, offset={"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4},
                      deg={"SOFT": 0.10, "MEDIUM": 0.05, "HARD": 0.03})
    window = pit_window(model, "A", "MEDIUM", age=20, laps_left=10, loss=20.0, choices=["HARD"])
    # One more lap on the medium (age 21), stop, nine laps on new hards.
    hand = (80 + 0.05 * 21) + 20 + sum(80.4 + 0.03 * j for j in range(1, 10))
    assert window.loc[window["LapsMore"] == 1, "Total"].item() == pytest.approx(hand)
    assert window["Lost"].min() == 0 and len(window) == 9


def test_worn_tyres_and_a_long_way_to_go_say_stop_soon():
    model = TyreModel(base={"A": 80.0}, offset={"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4},
                      deg={"SOFT": 0.10, "MEDIUM": 0.15, "HARD": 0.03})
    best = best_plan(pit_window(model, "A", "MEDIUM", age=25, laps_left=40, loss=20.0, choices=["HARD"]))
    assert best["LapsMore"] == 1  # wearing 0.15 s a lap already: every lap waiting costs more
    best = best_plan(pit_window(model, "A", "MEDIUM", age=2, laps_left=40, loss=20.0, choices=["HARD"]))
    assert 5 < best["LapsMore"] < 35 and best["From"] <= best["LapsMore"] <= best["To"]


def test_staying_out_compares_with_stopping():
    model = TyreModel(base={"A": 80.0}, offset={"MEDIUM": 0.0, "HARD": 0.4, "SOFT": -0.6},
                      deg={"MEDIUM": 0.05, "HARD": 0.03, "SOFT": 0.1})
    # Five laps to go: a 20 s stop can't pay back.
    window = pit_window(model, "A", "MEDIUM", age=30, laps_left=5, loss=20.0, choices=["SOFT"])
    assert stay_out_time(model, "A", "MEDIUM", 30, 5) < window["Total"].min()


def test_compound_rule():
    assert compounds_allowed({"MEDIUM"}) == ["SOFT", "HARD"]
    assert compounds_allowed({"MEDIUM", "HARD"}) == ["SOFT", "MEDIUM", "HARD"]
    assert compounds_allowed({"INTERMEDIATE"}) == ["SOFT", "MEDIUM", "HARD"]


def test_laps_to_catch():
    model = TyreModel(base={"A": 80.0, "B": 80.0}, offset={"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4},
                      deg={"SOFT": 0.10, "MEDIUM": 0.05, "HARD": 0.03})
    # A on new softs, B on 20-lap-old mediums: A gains 0.6 + 0.05*(20+n) - 0.10*n = 1.6 - 0.05n a lap.
    assert laps_to_catch(model, "A", "SOFT", 0, "B", "MEDIUM", 20, gap=3.0, laps_left=20) == 2
    assert laps_to_catch(model, "A", "SOFT", 0, "B", "MEDIUM", 20, gap=100.0, laps_left=20) is None
    assert laps_to_catch(model, "A", "SOFT", 0, "B", "MEDIUM", 20, gap=-1.0, laps_left=20) == 0
