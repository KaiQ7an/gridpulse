"""The atlas is complete offline and keeps venue history separate from saved race coverage."""

import re

from streamlit.testing.v1 import AppTest

from pitlens.season.atlas import REGIONS, browse_circuits, catalog, circuit_fact, in_region
from pitlens.season.circuits import circuits, saved_races


def test_every_saved_venue_has_geography_facts_and_sourced_records():
    facts = catalog()
    assert set(circuits(saved_races()).Circuit) <= {c["key"] for c in facts}
    assert len({c["key"] for c in facts}) == len({c["slug"] for c in facts}) == len(facts)
    for c in facts:
        assert c["region"] in REGIONS and c["region"] != "world"
        assert -90 <= c["lat"] <= 90 and -180 <= c["lon"] <= 180
        assert c["length_km"] > 3 and c["laps"] > 30 and c["first_gp"] >= 1950
        assert c["facts_source"].startswith("https://www.formula1.com/")
        assert re.fullmatch(r"\d+:\d{2}\.\d{3}", c["record"]["time"])
        for metric in ("wins", "poles"):
            leaders = c["history"][metric]
            assert leaders and len({r["count"] for r in leaders}) == 1
            assert all(len(r["years"]) == r["count"] for r in leaders)
    assert sum(len(in_region(r)) for r in REGIONS if r != "world") == len(facts)
    assert circuit_fact("monaco")["slug"] == "monte-carlo"
    assert circuit_fact("unrecognised") is None


def test_venue_records_include_history_and_ties_not_just_saved_years():
    suzuka = circuit_fact("suzuka")
    assert suzuka["history"]["wins"] == [{"driver": "Michael Schumacher", "count": 6,
                                            "years": [1995, 1997, 2000, 2001, 2002, 2004]}]
    monza = circuit_fact("monza")
    assert {r["driver"] for r in monza["history"]["wins"]} == {"Michael Schumacher", "Lewis Hamilton"}
    assert all(r["count"] == 5 for r in monza["history"]["wins"])


def atlas(**params):
    at = AppTest.from_string("from pitlens.pitwall import circuits_page\ncircuits_page.render()", default_timeout=60)
    at.query_params.update(params)
    return at.run()


def text(at):
    return "".join(item.proto.body for item in at.get("html")) + "".join(item.value for item in at.markdown)


def test_atlas_navigation_search_and_shared_links(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    at = atlas()
    assert not at.exception and "A world built for racing" in text(at)
    at.button(key="atlas-region-asia-pacific").click().run()
    assert not at.exception and at.query_params["region"] == "asia-pacific"
    at.text_input(key="atlas_search").set_value("Japan").run()
    assert [b.label for b in at.button if b.key.startswith("atlas-open-")] == ["Explore Suzuka"]
    at.button(key="atlas-open-suzuka").click().run()
    assert not at.exception and at.query_params["circuit"] == "suzuka"
    assert "Michael Schumacher" in text(at) and "Race lap record" in text(at)
    at.selectbox(key="atlas_jump").set_value("monza").run()
    assert not at.exception and at.query_params["region"] == "europe"
    assert "Most pole starts" in text(at)


def test_circuit_filters_compose_and_can_be_cleared(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    at = atlas(region="asia-pacific")
    at.selectbox(key="atlas_sort").set_value("Longest first").run()
    at.button_group(key="atlas_kind").set_value("Permanent").run()
    assert not at.exception
    actual = [b.label for b in at.button if b.key.startswith("atlas-open-")]
    expected = [f"Explore {c['city']}" for c in browse_circuits("asia-pacific", kind="Permanent", sort="Longest first")]
    assert actual == expected
    at.button(key="atlas-open-suzuka").click().run()
    at.run()  # hidden widget state is cleaned up while the circuit file is open
    next(b for b in at.button if b.label == "Asia-Pacific").click().run()
    assert at.selectbox(key="atlas_sort").value == "Longest first"
    assert at.button_group(key="atlas_kind").value == "Permanent"
    at.text_input(key="atlas_search").set_value("no such venue").run()
    assert any("No matching circuits" in i.value for i in at.info)
    at.button(key="atlas_reset").click().run()
    assert not at.exception and at.text_input(key="atlas_search").value == ""
    assert at.selectbox(key="atlas_sort").value == "Atlas order"
    assert len([b for b in at.button if b.key.startswith("atlas-open-")]) == len(in_region("asia-pacific"))


def test_circuit_sort_never_mutates_the_catalog():
    before = [c["slug"] for c in catalog()]
    longest = browse_circuits("world", sort="Longest first")
    assert [c["length_km"] for c in longest] == sorted((c["length_km"] for c in catalog()), reverse=True)
    assert [c["slug"] for c in catalog()] == before
    assert [c["slug"] for c in browse_circuits("asia-pacific", " JAPAN ", "Permanent")] == ["suzuka"]


def test_corner_links_restore_only_valid_markers_and_clicks_are_consumed_once(monkeypatch):
    from pitlens.pitwall import circuits_page

    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    calls = []
    event = {}

    def guide(*args, **kwargs):
        calls.append(kwargs)
        return event

    monkeypatch.setattr(circuits_page, "corner_guide", guide)
    at = atlas(circuit="suzuka", corner="t15")
    assert not at.exception and at.query_params["corner"] == "T15"
    assert calls[-1]["selected"] == "T15" and "circuit=suzuka" in calls[-1]["share_path"]
    event.update(id="pin-1", corner="T8")
    at.run()
    assert not at.exception and at.query_params["corner"] == "T8"
    at.query_params["corner"] = "T2"
    at.run()
    assert at.query_params["corner"] == "T2"  # the old component event must not overwrite a new link
    at.query_params["corner"] = "T999"
    at.run()
    assert not at.exception and "corner" not in at.query_params
    assert calls[-1]["selected"] is None


def test_comparison_metric_links_survive_changes_and_offer_export(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    at = atlas(compare="suzuka,monza", metric="stops")
    assert not at.exception and at.segmented_control(key="atlas_compare_metric").value == "Stops per finisher"
    assert at.get("download_button")[0].proto.label == "Download comparison CSV"
    at.segmented_control(key="atlas_compare_metric").set_value("SC races (%)").run()
    assert not at.exception and at.query_params["metric"] == "safety-cars"
    at.run()
    assert at.segmented_control(key="atlas_compare_metric").value == "SC races (%)"
    at.multiselect(key="atlas_compared").set_value(["suzuka", "monza", "imola"]).run()
    assert at.query_params["metric"] == "safety-cars" and at.query_params["compare"] == "suzuka,monza,imola"
    at.segmented_control(key="atlas_compare_metric").set_value("Length (km)").run()
    assert "metric" not in at.query_params
    at.button(key="compare-open-suzuka").click().run()
    at.run()
    at.query_params.update(compare="suzuka,monza", metric="stops")
    at.run()
    assert not at.exception and at.segmented_control(key="atlas_compare_metric").value == "Stops per finisher"


def test_facts_remain_available_when_no_races_are_saved(monkeypatch):
    from pitlens.pitwall import circuits_page

    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    monkeypatch.setattr(circuits_page, "cached_races", lambda: saved_races().iloc[:0])
    at = atlas(circuit="suzuka")
    assert not at.exception and "Suzuka" in text(at) and "Michael Schumacher" in text(at)
    assert "No saved race data here yet" in text(at)


def test_history_aggregation_keeps_ties_and_ignores_future_races():
    from tools.update_circuit_atlas import leaders

    def result(year, name):
        return {"date": f"{year}-09-01", "season": str(year),
                "Results": [{"Driver": {"driverId": name, "givenName": name, "familyName": "Driver"}}]}

    races = [result(2022, "A"), result(2023, "B"), result(2024, "A"), result(2025, "B"), result(2027, "A")]
    assert leaders(races, "2026-10-16") == [
        {"driver": "A Driver", "count": 2, "years": [2022, 2024]},
        {"driver": "B Driver", "count": 2, "years": [2023, 2025]},
    ]
