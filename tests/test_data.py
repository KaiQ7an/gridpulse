from types import SimpleNamespace

import pandas as pd
import pytest

from pitlens.pitwall import data
from pitlens.session import ResultsUnavailable


def session_with_empty_classification():
    results = pd.DataFrame({"Abbreviation": ["PIA", "NOR"], "DriverNumber": ["81", "4"],
                            "Position": [float("nan")] * 2, "Status": [None, None]})
    return SimpleNamespace(results=results, date=pd.Timestamp("2025-07-27 13:00"),
                           event={"EventName": "Belgian Grand Prix"})


def test_empty_classification_is_filled_from_openf1(monkeypatch):
    official = pd.DataFrame({"DriverNumber": ["4", "81"], "Position": [2.0, 1.0], "Status": ["Finished"] * 2,
                             "Laps": [44, 44], "GapToLeader": [3.415, 0.0]})
    monkeypatch.setattr(data.openf1, "classification", lambda *a, **k: official)
    results = data._fastf1_results(2025, session_with_empty_classification()).set_index("Abbreviation")
    assert results.loc["PIA", "Position"] == 1 and results.loc["NOR", "GapToLeader"] == pytest.approx(3.415)
    assert (results["Status"] == "Finished").all()


def test_empty_classification_before_openf1_fails_so_the_next_load_retries():
    with pytest.raises(ResultsUnavailable):
        data._fastf1_results(2021, session_with_empty_classification())
