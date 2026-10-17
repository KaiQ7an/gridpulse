"""DTM overview preserves official positions and opens full results with one click."""

from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.dtm import data
from gridpulse.pitwall.weekend_overview import sections, top_three


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")


def page(year, event):
    at = AppTest.from_string("from gridpulse.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.query_params.update(year=str(year), view="weekend", event=str(event), session="race-2")
    return at.run()


def test_all_four_sessions_top_three_are_visible_without_changing_session():
    at = page(2026, 2)
    assert not at.exception
    assert [h.value for h in at.subheader] == ["Race 1", "Race 2", "Qualifying 1", "Qualifying 2"]
    cards = [h.proto.body for h in at.get("html") if 'role="list"' in h.proto.body]
    assert len(cards) == 4 and all(c.count('role="listitem"') == 3 for c in cards)
    sessions = dict(sections(data.saved(2026)["events"][1]))
    for card, key in zip(cards, sessions):
        for result in top_three(sessions[key][0]):
            assert result["name"] in card
    assert "1:32.974" in cards[2] and "1:32.831" in cards[3]
    assert at.selectbox(key="dtm_session").value == "race-2"
    at.button(key="dtm_overview_2026_2_race-1").click().run()
    assert not at.exception
    assert at.selectbox(key="dtm_session").value == at.query_params["session"] == "race-1"
    assert at.selectbox(key="dtm_session").proto.raw_value == "Race 1"
    at.button(key="dtm_overview_2026_2_qualifying-2").click().run()
    assert at.selectbox(key="dtm_session").value == at.query_params["session"] == "qualifying-2"


def test_qualifying_groups_remain_separate_and_can_open_their_own_results():
    event = data.saved(2025)["events"][3]
    groups = dict(sections(event))
    assert [s["name"] for s in groups["Qualifying 2"]] == ["Qualifying 2 Group A", "Qualifying 2 Group B"]
    at = page(2025, 4)
    assert not at.exception
    cards = [h.proto.body for h in at.get("html") if 'role="list"' in h.proto.body]
    assert len(cards) == 6
    assert sum("not the combined starting grid" in c.value for c in at.caption) == 4
    at.button(key="dtm_overview_2025_4_qualifying-2-group-b").click().run()
    assert not at.exception and at.selectbox(key="dtm_session").value == "qualifying-2-group-b"
    assert at.query_params["session"] == "qualifying-2-group-b"


def test_incomplete_or_disqualified_results_are_not_invented_or_promoted():
    session = deepcopy(data.saved(2026)["events"][1]["sessions"][2])
    session["rows"] = [dict(position=4, status="", name="Fourth"),
                       dict(position=2, status="DSQ", name="Disqualified"),
                       dict(position=3, status="", name="Third"),
                       dict(position=1, status="", name="Winner")]
    assert [r["position"] for r in top_three(session)] == [1, 3]
    assert top_three({"rows": []}) == []
    assert sections({"sessions": []}) == [("Race 1", []), ("Race 2", []),
                                          ("Qualifying 1", []), ("Qualifying 2", [])]
