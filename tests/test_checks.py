import pandas as pd
from test_events import make_race

from pitlens.checks import check_race
from pitlens.pitwall.data import RaceData


def race_with(results: pd.DataFrame) -> RaceData:
    laps = make_race()
    fields = {name: None for name in RaceData.__dataclass_fields__}
    fields.update(laps=laps, results=results, total_laps=6, retired={"D"}, entrants=None,
                  stops=pd.DataFrame(columns=["Driver", "Lap"]))
    return RaceData(**fields)


def test_matching_finish_has_no_problems():
    results = pd.DataFrame({"Abbreviation": ["B", "A", "C", "D"], "Position": [1.0, 2.0, 3.0, None],
                            "Laps": [6, 6, 6, 2]})
    assert check_race(race_with(results)) == []


def test_wrong_winner_and_laps_down_are_reported():
    results = pd.DataFrame({"Abbreviation": ["A", "B", "C", "D"], "Position": [1.0, 2.0, 3.0, None],
                            "Laps": [6, 6, 5, 2]})
    problems = check_race(race_with(results))
    assert any(p.startswith("winner ['B']") for p in problems)
    assert "C 0 laps down, the result has 1" in problems
