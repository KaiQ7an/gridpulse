"""DTM scoring, classification boundaries, source failures and cross-series navigation."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from gridpulse.dtm import data
from gridpulse.pitwall import dtm_page


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")


def page(**params):
    at = AppTest.from_string("from gridpulse.pitwall.dtm_page import render\nrender()", default_timeout=30)
    at.query_params.update(params)
    return at.run()


@pytest.mark.parametrize("year,leader,points", [(2023, "Thomas Preining", 246), (2024, "Mirko Bortolotti", 238),
                                                (2025, "Ayhancan Güven", 192), (2026, "Thomas Preining", 225)])
def test_official_tables_and_every_points_chart_reconcile(year, leader, points):
    season = data.saved(year)
    assert season["standings"]["drivers"][0]["name"] == leader
    assert season["standings"]["drivers"][0]["points"] == points
    for category in ("drivers", "teams", "manufacturers"):
        published = {r["key"]: r["points"] for r in season["standings"][category]}
        endpoints = data.progress(season, category).groupby("key", sort=False).tail(1).set_index("key").points.to_dict()
        assert endpoints == published
    assert len(season["events"]) == 8
    assert data.race_rows(season)[["round", "session"]].drop_duplicates().shape[0] == 16
    assert all(len([s for s in e["sessions"] if s["kind"] == "race"]) == 2 for e in season["events"])


def test_dsq_and_dnf_are_not_classified_finishes_and_points_do_not_double_count_quali():
    season = data.saved(2026)
    races = data.race_rows(season)
    driver = races[(races.status == "DSQ") & (races.position.isna())].iloc[0].driver
    summary = data.comparison(season, [driver]).iloc[0]
    own = races[races.driver == driver]
    assert summary["DNF / DNS / DSQ"] == own.status.ne("").sum()
    assert summary["Best finish"] == own.loc[own.status == "", "position"].min()
    winner = next(s for s in season["events"][0]["sessions"] if s["key"] == "race-1")["rows"][0]
    assert winner["race_points"] == 25 and winner["qualifying_points"] == 1
    assert winner["total_points"] == 26  # already includes the qualifying point
    assert data.seconds("37L") is None and data.seconds(None) is None and data.number("nan") is None
    assert data.seconds("1:28.899") == pytest.approx(88.899)


def test_revised_classification_replaces_earlier_result_instead_of_counting_twice():
    season = data.saved(2025)
    session = next(s for s in season["events"][2]["sessions"] if s["key"] == "race-2")
    rows = {r["driver"]: r for r in session["rows"]}
    assert rows["dorr-ben"]["status"] == "DSQ" and rows["glock-timo"]["position"] is None
    assert rows["wittmann-marco"]["gap"] == "6.155"
    assert len([s for s in season["events"][2]["sessions"] if s["kind"] == "race"]) == 2
    assert data.race_rows(data.saved(2024)).manufacturer.nunique() == 7


def test_refresh_failure_falls_back_and_offline_never_touches_the_network(monkeypatch):
    calls = []

    def fail(year):
        calls.append(year)
        raise requests.Timeout("unavailable")

    monkeypatch.setattr(data, "fetch", fail)
    dtm_page.load.clear()
    year = data.YEARS[0]
    season, label = dtm_page.load(year, True, False)
    assert season["year"] == year and "unavailable" in label and calls == [year]
    dtm_page.load(year, True, False)
    assert calls == [year]  # a rerun must not repeatedly stall on a broken service
    season, label = dtm_page.load(year, True, True)
    assert calls == [year] and label == "Saved snapshot"
    dtm_page.load.clear()


def test_normalize_preserves_official_order_and_groups_without_inventing_points():
    rows = [{"name": "EXAMPLE Driver", "position": 1, "totalpoints": "8", "racepoints": "6", "qualifyingpoints": "2", "races": []},
            {"name": "SECOND Driver", "position": 2, "totalpoints": "8", "racepoints": "7", "qualifyingpoints": "1", "races": []}]
    standings = {"wigeStandingses": [{"jsonText": json.dumps({"drivers": rows, "teams": rows,
                                                             "manufacturers": rows, "provision": "Provisional"})}]}
    descriptors = [{"sessionid": "a", "name": "Qualifying 1 Group A", "timeStart": "2026-07-04T08:00:00Z"},
                   {"sessionid": "b", "name": "Race 1", "timeStart": "2026-07-04T11:30:00Z"}]
    results = {"wigeResultses": [{"wigeEventId": 202604, "raceSeries": "DTM", "jsonText": json.dumps({
        "sessionid": s["sessionid"], "sessions": descriptors, "provision": "provisional",
        "result": [{"name": "EXAMPLE Driver", "position": 1, "status": "", "number": "12"}]})} for s in descriptors]}
    calendar = {"events": [{"name": "Norisring", "eventNumber": 4, "startTime": "2026-07-02", "endTime": "2026-07-05",
                             "raceSeries": ["DTM"], "slug": "norisring-2026"}]}
    season = data.normalize(2026, results, standings, calendar, {})
    assert season["provisional"]
    assert [r["name"] for r in season["standings"]["drivers"]] == [r["name"] for r in rows]
    assert season["events"][0]["sessions"][0]["name"] == "Qualifying 1 Group A"
    assert season["events"][0]["sessions"][1]["rows"][0]["total_points"] is None
    broken = deepcopy(results)
    broken["wigeResultses"] = broken["wigeResultses"][:1]
    with pytest.raises(ValueError, match="no race classifications"):
        data.normalize(2026, broken, standings, calendar, {})
    with pytest.raises(ValueError, match="incomplete"):
        data.normalize(2026, {}, standings, calendar, {})


def test_link_session_recovery_and_all_dtm_views_render():
    at = page(year="2025", view="weekend", event="4", session="qualifying-1-group-a")
    assert not at.exception
    assert at.selectbox(key="dtm_event").value == 4
    assert "Group A" in at.selectbox(key="dtm_session").options[2]
    at.selectbox(key="dtm_session").set_value("race-1").run()
    assert not at.exception and at.query_params["session"] == "race-1"
    at.radio(key="dtm_view").set_value("championship").run()
    for category in ["teams", "manufacturers", "drivers"]:
        at.segmented_control(key="dtm_category").set_value(category).run()
        assert not at.exception
    at.radio(key="dtm_view").set_value("compare").run()
    assert not at.exception and len(at.multiselect(key="dtm_drivers").value) == 2
    at.multiselect(key="dtm_drivers").set_value([]).run()
    assert not at.exception and any("Choose up to four" in i.value for i in at.info)
    at.radio(key="dtm_view").set_value("weekend").run()
    assert at.selectbox(key="dtm_event").value == 4 and at.selectbox(key="dtm_session").value == "race-1"


def test_bad_links_and_season_changes_do_not_trap_the_pickers():
    at = page(year="2025", view="compare", drivers="bogus,guven-ayhancan,guven-ayhancan")
    assert not at.exception and at.multiselect(key="dtm_drivers").value == ["guven-ayhancan"]
    at.selectbox(key="dtm_year").set_value(2024).run()
    assert not at.exception and at.query_params["year"] == "2024"
    assert at.multiselect(key="dtm_drivers").value == ["guven-ayhancan"]
    at = page(year="bogus", view="weekend", event="bogus", session="missing")
    assert not at.exception


def test_f1_spoiler_free_replay_survives_dtm_and_dtm_selection_survives_f1():
    app = Path(__file__).resolve().parent.parent / "gridpulse" / "pitwall" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=90)
    at.query_params.update(year="2025", round="4", lap="23", drivers="HAM,LEC", view="Tyres", mode="replay")
    at.run()
    assert at.selectbox(key="racing_series").value == "Formula 1"
    at.selectbox(key="racing_series").set_value("DTM").run()
    at.selectbox(key="dtm_year").set_value(2024).run()
    at.radio(key="dtm_view").set_value("weekend").run()
    at.selectbox(key="dtm_event").set_value(4).run()
    at.selectbox(key="dtm_session").set_value("race-1").run()
    at.selectbox(key="racing_series").set_value("Formula 1").run()
    assert not at.exception
    assert at.selectbox(key="race_pick").value == 4 and at.slider(key="lap").value == 23
    assert at.toggle(key="no_spoilers").value and at.multiselect(key="focus").value == ["HAM", "LEC"]
    at.selectbox(key="racing_series").set_value("DTM").run()
    assert not at.exception
    assert at.selectbox(key="dtm_year").value == 2024 and at.selectbox(key="dtm_event").value == 4
    assert at.selectbox(key="dtm_session").value == "race-1"
