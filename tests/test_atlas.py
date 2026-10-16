"""The atlas is complete offline and keeps venue history separate from saved race coverage."""

import re

from streamlit.testing.v1 import AppTest

from pitlens.season.atlas import REGIONS, catalog, circuit_fact, in_region
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
