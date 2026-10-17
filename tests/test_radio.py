import pandas as pd

from gridpulse.radio.clips import assign_laps, parse_stream

STREAM = (
    "﻿00:08:11.285{\"Captures\":[{\"Utc\":\"2025-08-03T12:13:31.908Z\",\"RacingNumber\":\"10\","
    "\"Path\":\"TeamRadio/PIEGAS01_10_20250803_141320.mp3\"}]}\n"
    "01:03:23.464{\"Captures\":{\"1\":{\"Utc\":\"2025-08-03T13:08:41.557Z\",\"RacingNumber\":\"1\","
    "\"Path\":\"TeamRadio/MAXVER01_1_20250803_150810.mp3\"}}}\n"
)


def test_parse_stream_handles_list_and_keyed_messages():
    clips = parse_stream(STREAM)
    assert clips["DriverNumber"].tolist() == ["10", "1"]
    assert clips.loc[1, "SessionTime"] == pd.to_timedelta(3803.464, unit="s")
    assert clips.loc[1, "Path"].endswith("MAXVER01_1_20250803_150810.mp3")
    assert clips.loc[0, "Utc"].year == 2025


def test_assign_laps_uses_the_drivers_own_lap_window():
    laps = pd.DataFrame(
        {
            "DriverNumber": ["1", "1", "10"],
            "LapNumber": [4, 5, 4],
            "LapStartTime": pd.to_timedelta(["01:02:08", "01:03:32", "01:02:20"]),
            "Time": pd.to_timedelta(["01:03:32", "01:04:56", "01:03:40"]),
        }
    )
    clips = parse_stream(STREAM)
    laps_of = assign_laps(clips, laps)
    assert pd.isna(laps_of[0])  # GAS clip before the race started
    assert laps_of[1] == 4  # VER on lap 4 at 1:03:23
