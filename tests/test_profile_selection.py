"""Profile selections must agree with a newly mounted browser picker, not just Python state."""

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")


def page(**params):
    at = AppTest.from_string("from gridpulse.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.query_params.update(params)
    return at.run()


def mounted_label(widget):
    # When a picker mounts after being hidden, the browser uses the explicit
    # server update or its default. AppTest.value alone misses this divergence.
    return widget.proto.raw_value if widget.proto.set_value else widget.proto.options[widget.proto.default]


def team_card_count(at):
    return sum(h.proto.body.count('class="dtm-team-card"') for h in at.get("html"))


def test_team_and_driver_picker_remounts_match_profile_and_url():
    at = page(year="2026", view="teams", team="manthey")
    at.selectbox(key="dtm_team").set_value("comtoyou").run()
    at.radio(key="dtm_view").set_value("drivers").run()
    at.selectbox(key="dtm_profile").set_value("bortolotti-mirko").run()
    at.radio(key="dtm_view").set_value("teams").run()
    assert not at.exception
    assert at.selectbox(key="dtm_team").value == at.query_params["team"] == "comtoyou"
    assert mounted_label(at.selectbox(key="dtm_team")) == "Comtoyou Racing"
    assert [h.value for h in at.subheader] == ["Comtoyou Racing"]
    at.radio(key="dtm_view").set_value("drivers").run()
    assert at.selectbox(key="dtm_profile").value == at.query_params["driver"] == "bortolotti-mirko"
    assert mounted_label(at.selectbox(key="dtm_profile")) == "Mirko Bortolotti"


def test_all_teams_and_selection_from_a_link_do_not_reapply_an_old_link():
    at = page(year="2026", view="teams", team="manthey")
    at.button(key="dtm_team_back").click().run()
    assert "team" not in at.query_params and team_card_count(at) == 12
    at.radio(key="dtm_view").set_value("drivers").run()
    at.radio(key="dtm_view").set_value("teams").run()
    assert mounted_label(at.selectbox(key="dtm_team")) == "All participating teams"
    assert team_card_count(at) == 12
    at.query_params.update(year="2025", view="drivers", driver="guven-ayhancan")
    at.run()
    assert mounted_label(at.selectbox(key="dtm_profile")) == "Ayhancan Güven"
    at.selectbox(key="dtm_profile").set_value("preining-thomas").run()
    assert at.query_params["driver"] == "preining-thomas"
    at.run()
    assert at.selectbox(key="dtm_profile").value == "preining-thomas"


def test_weekend_and_season_picker_remounts_also_match_the_retained_selection():
    at = page(year="2024", view="weekend", event="4", session="race-1")
    at.radio(key="dtm_view").set_value("teams").run()
    at.radio(key="dtm_view").set_value("weekend").run()
    assert mounted_label(at.selectbox(key="dtm_event")).startswith("R4 ·")
    assert mounted_label(at.selectbox(key="dtm_session")) == "Race 1"
    assert at.query_params["year"] == "2024"


def test_team_and_driver_invalid_in_a_new_season_reset_both_picker_and_profile():
    at = page(year="2024", view="teams", team="ssr")
    at.selectbox(key="dtm_year").set_value(2026).run()
    assert at.selectbox(key="dtm_team").value == "all" and "team" not in at.query_params
    at.query_params.update(year="2023", view="drivers", driver="holzem-sandro")
    at.run()
    at.selectbox(key="dtm_year").set_value(2026).run()
    assert at.selectbox(key="dtm_profile").value == at.query_params["driver"] != "holzem-sandro"
    assert mounted_label(at.selectbox(key="dtm_profile")) == "Thomas Preining"


def test_departing_profile_is_not_recreated_while_another_view_is_open():
    at = page(year="2026", view="teams", team="comtoyou")
    at.radio(key="dtm_view").set_value("drivers").run()
    at.run()
    # Canonical memory survives, but an absent widget is not repeatedly seeded.
    assert at.session_state["dtm_saved"]["dtm_team"] == "comtoyou"
    assert "dtm_team" not in at.session_state
