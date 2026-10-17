import pandas as pd

from gridpulse.season.circuits import circuit_years, circuits, saved_races, slug, tyre_sequence


def test_slug():
    assert slug("São Paulo") == "sao-paulo" and slug("Spa-Francorchamps") == "spa-francorchamps"


def test_circuits_follow_the_track_not_the_name():
    races = pd.DataFrame({"Year": [2022, 2025, 2026, 2026], "Round": [7, 8, 6, 1],
                          "Event": ["Monaco Grand Prix"] * 3 + ["Australian Grand Prix"],
                          "Location": ["Monaco", "Monaco", "Monte Carlo", "Melbourne"],
                          "Circuit": [22, 22, 22, 10], "Date": pd.to_datetime(["2022-05-29"] * 4)})
    table = circuits(races).set_index("Circuit")
    assert list(table.index) == [10, 22]  # in the latest season's calendar order
    assert table.loc[22, "Location"] == "Monte Carlo" and table.loc[22, "Years"] == [2022, 2025, 2026]
    assert table.loc[22, "Slug"] == "monte-carlo"


def test_tyre_sequence():
    laps = pd.DataFrame({"LapNumber": [1, 2, 3, 4, 5], "Stint": [1, 1, 2, 2, 3],
                         "Compound": ["MEDIUM", "MEDIUM", "HARD", "HARD", "SOFT"]})
    assert tyre_sequence(laps) == "M-H-S"


def test_a_circuit_year_by_year_from_the_saved_races(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    years = circuit_years(saved_races(), 39).set_index("Year")  # Monza
    assert years.loc[2025, "Winner"] == "VER" and years.loc[2025, "WinnerGrid"] == 1
    assert years.loc[2025, "Pole"] == "VER" and round(years.loc[2025, "PoleTime"], 3) == 78.792
    assert years.loc[2025, "Stops"] == {1: 18}  # every finisher stopped once
