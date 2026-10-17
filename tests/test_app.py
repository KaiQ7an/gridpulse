"""Smoke tests of the pit wall pages, offline on the saved snapshots: every page and view renders
without an exception. These are the crashes unit tests don't see (an empty table reaching a view,
a missing column on one race)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from gridpulse.pitwall.about_page import FEATURED
from gridpulse.pitwall.app import VIEWS

APP = str(Path(__file__).resolve().parent.parent / "gridpulse" / "pitwall" / "app.py")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")


def page_text(at: AppTest) -> str:
    return "".join(h.proto.body for h in at.get("html"))


def replay(**link) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    for key, value in link.items():
        at.query_params[key] = value
    return at.run()


def test_a_link_opens_that_race():
    at = replay(year="2026", round="15")
    assert not at.exception
    assert "Azerbaijan Grand Prix" in page_text(at)
    assert at.slider(key="lap").value == 51  # opens on the final lap


@pytest.mark.parametrize("lap", [1, 12, 30])
def test_every_view_renders(lap):
    at = replay(year="2026", round="15")
    at.slider(key="lap").set_value(lap).run()
    for view in VIEWS:
        at.segmented_control(key="view").set_value(view).run()
        assert not at.exception, f"{view} on lap {lap}: {at.exception[0].value}"


def test_sprint_replay():
    at = replay(year="2026", round="2", session="sprint")
    assert not at.exception
    assert "Chinese Grand Prix Sprint" in page_text(at)


def test_qualifying_page():
    def qualifying():
        from gridpulse.pitwall import quali_page, ui

        ui.inject_css()
        quali_page.render()

    at = AppTest.from_function(qualifying, default_timeout=180)
    at.session_state["q_year"] = 2026
    at.run()
    assert not at.exception
    assert "Classification" in page_text(at)


def test_onboard_page_offline_says_why():
    def onboard():
        from gridpulse.pitwall import onboard_page, ui

        ui.inject_css()
        onboard_page.render()

    at = AppTest.from_function(onboard, default_timeout=180)
    at.session_state["ob_year"] = 2026
    at.run()
    assert not at.exception
    assert any("offline" in w.value for w in at.warning)


def test_about_page_links_to_featured_races():
    def about():
        import streamlit as st

        from gridpulse.pitwall import about_page, ui

        ui.inject_css()
        titles = [title for title, _ in about_page.WEEKEND + about_page.SEASON + about_page.DTM_GUIDE]
        about_page.pages = {t: st.Page(lambda: None, title=t, url_path=t.lower().replace(" ", "-")) for t in titles}
        about_page.render()

    at = AppTest.from_function(about, default_timeout=60).run()
    assert not at.exception
    from gridpulse.pitwall.about_page import DTM_GUIDE, SEASON, WEEKEND

    assert len(at.get("page_link")) == len(WEEKEND) + len(SEASON) + len(DTM_GUIDE) + len(FEATURED)


def test_teams_page():
    def teams():
        import streamlit as st

        from gridpulse.pitwall import teams_page, ui

        ui.inject_css()
        st.query_params["year"] = "2025"
        st.query_params["team"] = "McLaren"
        teams_page.render()

    at = AppTest.from_function(teams, default_timeout=180).run()
    assert not at.exception
    text = page_text(at)
    assert "McLaren" in text and "Lando Norris" in text and "Against their teammate" in text


def render_page(module: str, **link) -> AppTest:
    """Run one page on its own, opened from a link with `link` as its query parameters."""
    at = AppTest.from_string(f"from gridpulse.pitwall import ui, {module}\nui.inject_css()\n{module}.render()\n",
                             default_timeout=180)
    for key, value in link.items():
        at.query_params[key] = value
    return at.run()


def test_season_page():
    at = render_page("season_page", year="2025")
    assert not at.exception
    text = page_text(at)
    assert "Lando Norris champion by 2 points from Max Verstappen" in text and "Round by round" in text


def test_drivers_page():
    at = render_page("drivers_page", year="2025", driver="VER")
    assert not at.exception
    text = page_text(at)
    assert "Max Verstappen" in text and "Best comeback" in text and "Abu Dhabi" in text


def test_circuits_page():
    at = render_page("circuits_page", circuit="monte-carlo")
    assert not at.exception
    text = page_text(at)
    assert "Monte Carlo" in text and "Year by year" in text


def test_replay_link_restores_lap_drivers_and_view_and_tracks_changes():
    at = replay(year="2026", round="17", lap="24", drivers="HAM,ANT", view="Strategy")
    assert not at.exception
    assert at.slider(key="lap").value == 24
    assert at.multiselect(key="focus").value == ["HAM", "ANT"]
    assert at.segmented_control(key="view").value == "Strategy"
    at.slider(key="lap").set_value(26).run()
    assert not at.exception
    assert at.query_params["lap"] == "26"
    assert at.query_params["drivers"] == "HAM,ANT"
    assert at.query_params["view"] == "Strategy"


def test_replay_link_clamps_lap_and_filters_unknown_and_duplicate_drivers():
    at = replay(year="2026", round="17", lap="99999", drivers="ham,INVALID,HAM,ant", view="invalid")
    assert not at.exception
    assert at.slider(key="lap").value == 62
    assert at.multiselect(key="focus").value == ["HAM", "ANT"]
    assert at.segmented_control(key="view").value == "Gaps"


def test_spoiler_free_mode_starts_at_lap_one_and_uses_starting_order():
    from gridpulse.pitwall.app import starting_order
    from gridpulse.pitwall.data import load_race

    at = replay(year="2026", round="17", mode="replay")
    assert not at.exception
    assert at.slider(key="lap").value == 1
    assert at.multiselect(key="focus").value == starting_order(load_race(2026, 17))[:3]
    at.slider(key="lap").set_value(24).run()
    at.segmented_control(key="view").set_value("Strategy").run()
    assert not at.exception
    assert all(t.key != "window_actual" for t in at.toggle)


def test_spoiler_mode_switch_restarts_an_analysis():
    at = replay(year="2026", round="17")
    at.toggle(key="no_spoilers").set_value(True).run()
    assert not at.exception
    assert at.slider(key="lap").value == 1
    assert at.query_params["mode"] == "replay"


def test_driver_race_links_keep_the_selected_driver():
    at = render_page("drivers_page", year="2025", driver="VER")
    assert not at.exception
    assert 'round=24&drivers=VER' in page_text(at)


def test_new_page_inherits_the_selected_season():
    at = AppTest.from_string(
        "from gridpulse.pitwall import drivers_page\ndrivers_page.render()", default_timeout=180)
    at.session_state["selected_year"] = 2024
    at.run()
    assert not at.exception
    assert at.selectbox(key="driver_year").value == 2024


def test_replay_survives_widget_cleanup_when_visiting_drivers():
    at = AppTest.from_string('''
import streamlit as st
from gridpulse.pitwall import app, drivers_page
st.radio("Page", ["Race", "Drivers"], key="test_page", on_change=st.query_params.clear)
if st.session_state.test_page == "Race":
    app.race_page()
else:
    drivers_page.render()
''', default_timeout=180)
    at.query_params.update(year="2025", round="4", lap="23", drivers="HAM,LEC", view="Tyres", mode="replay")
    at.run()
    assert not at.exception
    at.radio(key="test_page").set_value("Drivers").run()
    assert not at.exception
    at.radio(key="test_page").set_value("Race").run()
    assert not at.exception
    assert at.selectbox(key="race_pick").value == 4
    assert at.slider(key="lap").value == 23
    assert at.multiselect(key="focus").value == ["HAM", "LEC"]
    assert at.toggle(key="no_spoilers").value
    assert at.segmented_control(key="view").value == "Tyres"
    assert not at.session_state["playing"]


def test_onboard_link_failure_does_not_override_recovery_selection(monkeypatch):
    import pandas as pd

    from gridpulse.pitwall import onboard_page
    from gridpulse.session import TimingUnavailable

    calls = []
    monkeypatch.setattr(onboard_page, "cached_races", lambda year: pd.DataFrame(
        [{"RoundNumber": 1, "EventName": "Test GP"}, {"RoundNumber": 2, "EventName": "Other GP"}]))

    def fail(year, round_number, kind):
        calls.append((year, round_number, kind))
        raise TimingUnavailable("Session unavailable")

    monkeypatch.setattr(onboard_page, "cached_weekend", fail)
    at = render_page("onboard_page", year="2025", round="1", session="Q")
    at.selectbox(key="ob_session").set_value("R").run()
    at.selectbox(key="ob_event").set_value(1).run()
    at.selectbox(key="ob_year").set_value(2024).run()
    assert not at.exception
    assert calls == [(2025, 1, "Q"), (2025, 1, "R"), (2025, 2, "R"), (2024, 2, "R")]


def test_the_old_entry_point_still_starts_the_app():
    """The hosted app was set up with pitlens/pitwall/app.py as its main file (see that file)."""
    old = Path(__file__).resolve().parent.parent / "pitlens" / "pitwall" / "app.py"
    at = AppTest.from_file(str(old), default_timeout=180)
    at.query_params["year"] = "2026"
    at.query_params["round"] = "15"
    at.run()
    assert not at.exception
    assert "Azerbaijan Grand Prix" in page_text(at)
