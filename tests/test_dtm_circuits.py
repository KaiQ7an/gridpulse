"""DTM circuits retain their own layouts, archive scope and season selection."""

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from pitlens.dtm import circuits, data


def test_all_season_venues_have_sourced_dtm_layouts():
    assert len(circuits.catalog()) == 8
    for year in data.YEARS:
        season = data.saved(year)
        venues = circuits.venues(season)
        assert len(venues) == len(season["events"]) == 8
        assert {v["event_key"] for v in venues} == {circuits.event_key(e) for e in season["events"]}
        for fact in venues:
            assert -90 <= fact["lat"] <= 90 and -180 <= fact["lon"] <= 180
            assert fact["plan"].startswith("https://") and fact["history_source"].startswith("https://")
        assert next(c for c in venues if c["slug"] == "nurburgring")["length_km"] == 3.629


def test_records_exclude_future_seasons_disqualifications_and_qualifying_groups():
    season = deepcopy(data.saved(2023))
    fact = circuits.venues(season)[0]
    event = fact["event"]
    race = next(s for s in event["sessions"] if s["kind"] == "race")
    race["rows"][0].update(name="Disqualified", status="DSQ", fastest_lap="0:01.000")
    group = deepcopy(next(s for s in event["sessions"] if s["kind"] == "qualifying"))
    group["name"] += " Group A"
    group["rows"][0].update(name="Group winner", status="", position=1)
    event["sessions"].append(group)
    history = circuits.history(fact, 2023, season)
    assert {w["Year"] for w in history["weekends"]} == {2023}
    assert "Disqualified" not in history["wins"]
    assert history["fastest"]["name"] != "Disqualified"
    assert "Group winner" not in history["poles"]


def test_atlas_search_details_and_direct_links_preserve_selected_season(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    at = AppTest.from_string("from pitlens.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.query_params.update(year="2024", view="circuits")
    at.run()
    assert not at.exception
    assert len([b for b in at.button if b.key.startswith("dtm-circuit-open-")]) == 8
    at.text_input(key="dtm_circuit_search").set_value("Nürburg").run()
    assert [b.label for b in at.button if b.key.startswith("dtm-circuit-open-")] == ["Explore Nürburg"]
    at.button(key="dtm-circuit-open-nurburgring").click().run()
    assert not at.exception
    assert at.query_params["year"] == "2024" and at.query_params["circuit"] == "nurburgring"
    text = ''.join(h.proto.body for h in at.get('html'))
    assert '3.629 km' in text and 'DTM circuit file' in text
    assert any("2023–2024" in c.value and "not all-time DTM records" in c.value for c in at.caption)
    assert set(at.dataframe[0].value.Year) <= {2023, 2024}
    at.radio(key="dtm_view").set_value("drivers").run()
    at.radio(key="dtm_view").set_value("circuits").run()
    assert not at.exception and at.selectbox(key="dtm_circuit").value == "nurburgring"
    at.selectbox(key="dtm_year").set_value(2023).run()
    assert at.query_params["year"] == "2023"
    assert set(at.dataframe[0].value.Year) == {2023}
