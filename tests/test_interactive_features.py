"""Regression tests for chosen laps, spoiler-safe jumps and circuit exploration data."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.onboard.data import DriverLap, FastF1Weekend, OnboardData, OpenF1Weekend
from gridpulse.pitwall import onboard_page
from gridpulse.pitwall.timeline import known_events
from gridpulse.season.atlas import catalog, circuit_fact
from gridpulse.season.comparison import comparison_slugs, comparison_table, saved_summary
from gridpulse.season.tours import build_tour, corner_measurements, corner_tour


def test_chosen_openf1_lap_is_not_replaced_by_fastest_and_deleted_laps_are_unselectable(monkeypatch):
    from gridpulse.sources import openf1

    weekend = OpenF1Weekend.__new__(OpenF1Weekend)
    weekend.session = {"session_key": 10}
    weekend.stints = pd.DataFrame([dict(driver_number=1, lap_start=1, lap_end=20,
                                       compound="HARD", tyre_age_at_start=2)])
    weekend.laps = pd.DataFrame({"name_acronym": ["VER"] * 3, "driver_number": [1] * 3,
                                "team_name": ["Red Bull"] * 3, "lap_duration": [95, 96, 94],
                                "lap_number": [10, 12, 13], "Deleted": [False, False, True],
                                "duration_sector_1": [30] * 3, "duration_sector_2": [30] * 3,
                                "duration_sector_3": [35, 36, 34], "date_start": ["2025-01-01T12:00Z"] * 3})
    monkeypatch.setattr(openf1, "lap_telemetry", lambda *args: pd.DataFrame())
    assert weekend.lap_options("VER")["Lap"].tolist() == [10, 12]
    assert weekend.fastest_lap("VER").lap_number == 10
    chosen = weekend.lap("VER", 12)
    assert chosen.lap_number == 12 and chosen.lap_time.total_seconds() == 96 and chosen.tyre_life == 14
    with pytest.raises(ValueError, match="no valid timed lap"):
        weekend.lap("VER", 13)


def test_explicit_archive_lap_never_falls_back_to_different_source_numbering(monkeypatch):
    import gridpulse.onboard.data as data

    def unavailable(*args):
        raise KeyError("telemetry")

    monkeypatch.setattr(data, "compare", unavailable)
    archive = FastF1Weekend.__new__(FastF1Weekend)
    archive.session = SimpleNamespace()
    with pytest.raises(ValueError, match="selected laps"):
        archive.compare("VER", "VER", 10, 12)


class LapWeekend:
    def drivers(self):
        return pd.DataFrame({"Driver": ["VER", "PER"], "Team": ["Red Bull"] * 2})

    def lap_options(self, driver):
        return pd.DataFrame({"Lap": [10, 11, 12], "LapTime": pd.to_timedelta([120, 121, 122], unit="s"),
                             "Compound": ["HARD"] * 3, "TyreLife": [4, 5, 6]})

    def compare(self, a, b, lap_a=None, lap_b=None):
        def lap(driver, number):
            number = number or 10
            d = np.linspace(0, 3000, 301)
            angle = d / 3000 * 2 * np.pi
            tel = pd.DataFrame({"Distance": d, "Time": pd.to_timedelta(d / 3000 * (110 + number), unit="s"),
                                "Speed": 100, "Throttle": 100, "Brake": False, "nGear": 5,
                                "X": 1000 * np.cos(angle), "Y": 1000 * np.sin(angle)})
            return DriverLap(driver, "Red Bull", pd.Timedelta(seconds=110 + number),
                             (pd.Timedelta(seconds=(110 + number) / 3),) * 3, "HARD", number - 6, number, tel)

        corners = pd.DataFrame({"Number": [1, 2], "Letter": ["", ""], "Angle": [0, 180],
                                "X": [0, 0], "Y": [1000, -1000], "Distance": [750, 2250]})
        return OnboardData("Test GP", "Race", lap(a, lap_a), lap(b, lap_b), corners, 0)


def test_same_driver_chosen_laps_survive_picker_changes_and_shareable_link(monkeypatch):
    monkeypatch.setattr(onboard_page, "cached_races", lambda year: pd.DataFrame(
        [{"RoundNumber": 1, "EventName": "Test GP"}]))
    monkeypatch.setattr(onboard_page, "cached_weekend", lambda *args: LapWeekend())
    at = AppTest.from_string("from gridpulse.pitwall.onboard_page import render\nrender()", default_timeout=30)
    at.query_params.update(year="2025", round="1", session="R", drivers="VER,VER", mode="laps", lap_a="10", lap_b="12")
    at.run()
    assert not at.exception and at.selectbox(key="ob_b").value == "VER"
    text = "".join(h.proto.body for h in at.get("html"))
    assert "Max Verstappen · L10" in text and "Max Verstappen · L12" in text
    at.selectbox(key="ob_other_lap").set_value(11).run()
    assert not at.exception and at.query_params["lap_b"] == "11"
    at.run()
    assert at.selectbox(key="ob_other_lap").value == 11  # incoming link must be consumed once
    at.selectbox(key="ob_other_lap").set_value(10).run()
    assert not at.exception and any("two different laps" in i.value for i in at.info)
    assert at.query_params["lap_b"] == "10"


def test_timeline_does_not_send_future_events_or_nan_to_the_browser():
    events = pd.DataFrame({"Lap": [4, 8, 10], "Kind": ["PIT", "SC", "FLAG"],
                           "Driver": ["HAM", np.nan, "VER"], "Text": ["Pit", "SC", "Wins"]})
    assert [e["lap"] for e in known_events(events, 8, True)] == [4, 8]
    assert known_events(events, 8, True)[1]["driver"] == ""
    assert len(known_events(events, 1, False)) == 3


@pytest.mark.parametrize("future", [False, True])
def test_event_click_pauses_and_jumps_but_cannot_bypass_spoiler_mode(monkeypatch, future):
    from gridpulse.pitwall import app, timeline

    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    race = app.cached_race(2025, 4)
    candidates = known_events(race.events, 23, not future)
    event = next(e for e in candidates if (e["lap"] > 23 if future else 1 < e["lap"] < 23))
    monkeypatch.setattr(timeline, "event_timeline", lambda *args, **kwargs: {**event, "id": "test-click"})
    at = AppTest.from_file(str(Path(app.__file__)), default_timeout=90)
    at.query_params.update(year="2025", round="4", lap="23", mode="replay")
    at.run()
    assert not at.exception
    expected = 23 if future else event["lap"]
    assert at.slider(key="lap").value == expected
    assert at.query_params["lap"] == str(expected)
    assert at.toggle(key="no_spoilers").value and not at.session_state["playing"]


def test_circuit_comparison_uses_weighted_stops_and_explicit_coverage():
    years = pd.DataFrame({"Year": [2024, 2025], "SafetyCars": [0, 2], "PitLoss": [20, 24],
                          "Stops": [{1: 2, 2: 2}, {2: 6}]})
    result = saved_summary(years)
    assert result["Saved races"] == 2 and result["Coverage"] == "2024, 2025"
    assert result["Stops per finisher"] == pytest.approx(1.8)
    assert result["SC races (%)"] == 50 and result["Typical pit loss (s)"] == 22
    assert comparison_slugs("monza,bogus,suzuka,monza,spa-francorchamps,imola") == ["monza", "suzuka", "spa-francorchamps"]
    table = comparison_table([circuit_fact("monza"), circuit_fact("suzuka")], {})
    assert table["Length (km)"].notna().all() and table["SC races (%)"].isna().all()


def test_circuit_comparison_link_and_metrics_render_offline(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    at = AppTest.from_string("from gridpulse.pitwall.circuits_page import render\nrender()", default_timeout=60)
    at.query_params["compare"] = "monza,suzuka"
    at.run()
    assert not at.exception and at.multiselect(key="atlas_compared").value == ["monza", "suzuka"]
    at.multiselect(key="atlas_compared").set_value(["monza", "suzuka", "spa-francorchamps"]).run()
    at.segmented_control(key="atlas_compare_metric").set_value("SC races (%)").run()
    assert not at.exception and at.query_params["compare"] == "monza,suzuka,spa-francorchamps"
    assert len(at.dataframe[0].value.columns) == 3


def test_corner_measurements_use_local_minima_and_sampled_brake_distance():
    tel = pd.DataFrame({"Distance": np.arange(0, 601, 10), "Speed": 200, "nGear": 6, "Brake": False})
    tel.loc[tel.Distance == 300, ["Speed", "nGear"]] = [80, 2]
    tel.loc[tel.Distance.between(200, 290), "Brake"] = True
    assert corner_measurements(tel, 300) == {"speed": 80, "gear": 2, "brake_m": 100}
    assert corner_measurements(tel, 1000) == {"speed": None, "gear": None, "brake_m": None}


def test_corner_geometry_fallback_never_invents_telemetry():
    track = {"x": [0, 10, 20], "y": [0, 10, 0], "rotation": 0}
    circuit = {"corners": [{"number": 1, "trackPosition": {"x": 10, "y": 10}}]}
    result = build_tour(circuit, None, track, {"year": 2025})
    assert not result["telemetry"] and len(result["points"]) == 3
    assert result["corners"][0]["speed"] is None and result["samples"][0]["brake"] is None


def test_every_atlas_venue_has_an_offline_tour_with_identified_reference():
    for fact in catalog():
        tour = corner_tour(fact["slug"])
        assert tour and len(tour["points"]) > 50 and tour["reference"]["year"] >= 2018
        if tour["telemetry"]:
            assert tour["reference"]["driver"] and tour["reference"]["time"] > 30
        else:
            assert all(c["speed"] is None for c in tour["corners"])
