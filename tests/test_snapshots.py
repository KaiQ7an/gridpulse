import numpy as np
import pandas as pd
import pytest

from pitlens import snapshots
from pitlens.radio import transcribe

URL = "https://livetiming.formula1.com/static/2026/clip.mp3"


@pytest.fixture
def parts():
    laps = pd.DataFrame({"Driver": ["RUS", "VER"], "LapNumber": [1.0, 1.0],
                         "Time": pd.to_timedelta([95.1, 95.4], unit="s"), "Compound": ["SOFT", None]})
    results = pd.DataFrame({"Abbreviation": ["RUS", "VER"], "Position": [1.0, 2.0], "Status": ["Finished"] * 2})
    radio = pd.DataFrame({"Driver": ["RUS"], "Lap": pd.array([1], dtype="Int64"),
                          "SessionTime": pd.to_timedelta([90.0], unit="s"),
                          "Utc": pd.to_datetime(["2026-09-26T11:02:00Z"]), "Url": [URL]})
    return {
        "laps": laps, "results": results, "messages": pd.DataFrame({"Lap": [1], "Message": ["GREEN LIGHT"]}),
        "weather": None, "radio": radio, "stationary": None, "total_laps": 51, "event_name": "Azerbaijan Grand Prix",
        "location": "Baku", "source": "OpenF1", "circuit_key": 144, "session_name": "Race",
        "pit_loss_ref": {"normal": 21.8, "vsc": 15.8, "sc": 13.8},
        "date": pd.Timestamp("2026-09-27"), "race_utc": pd.Timestamp("2026-09-27 11:00"),
        "track": {"x": np.array([0.0, 10.0, 20.0]), "y": np.array([0.0, 5.0, 0.0]), "splits": [1, 2],
                  "rotation": 90.0, "source": "fastest lap"},
        "rain_mm": pd.Series([0.0, 0.4], index=pd.to_datetime(["2026-09-27 11:00", "2026-09-27 12:00"])),
    }


def test_a_saved_race_comes_back_the_same_on_a_fresh_machine(tmp_path, monkeypatch, parts):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(transcribe, "TEXT_DIR", tmp_path / "here")
    transcribe.save(URL, {"text": "Box, box.", "zh": {"offline": "进站，进站。"}})
    snapshots.save_race(2026, 15, "R", parts, "conventional")

    monkeypatch.setattr(transcribe, "TEXT_DIR", tmp_path / "fresh")  # another machine: no transcripts yet
    back = snapshots.load_race(2026, 15, "R")
    pd.testing.assert_frame_equal(back["laps"], parts["laps"])
    pd.testing.assert_frame_equal(back["radio"], parts["radio"])
    assert back["weather"] is None and back["total_laps"] == 51 and back["pit_loss_ref"]["sc"] == 13.8
    assert back["race_utc"] == parts["race_utc"]
    assert back["track"]["x"].tolist() == [0.0, 10.0, 20.0] and back["track"]["splits"] == [1, 2]
    assert back["rain_mm"].tolist() == [0.0, 0.4]
    assert transcribe.cached(URL)["zh"]["offline"] == "进站，进站。"  # the radio view finds it

    listed = snapshots.races(2026)
    assert listed.to_dict("records")[0]["EventName"] == "Azerbaijan Grand Prix"


def test_an_older_snapshot_format_is_ignored(tmp_path, monkeypatch, parts):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    snapshots.save_race(2026, 15, "R", parts)
    monkeypatch.setattr(snapshots, "FORMAT", snapshots.FORMAT + 1)
    assert snapshots.load_race(2026, 15, "R") is None
    assert snapshots.races(2026).empty
