"""Smoke tests of the pit wall pages, offline on the saved snapshots: every page and view renders
without an exception. These are the crashes unit tests don't see (an empty table reaching a view,
a missing column on one race)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pitlens.pitwall.about_page import FEATURED
from pitlens.pitwall.app import VIEWS

APP = str(Path(__file__).resolve().parent.parent / "pitlens" / "pitwall" / "app.py")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")


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
        from pitlens.pitwall import quali_page, ui

        ui.inject_css()
        quali_page.render()

    at = AppTest.from_function(qualifying, default_timeout=180)
    at.session_state["q_year"] = 2026
    at.run()
    assert not at.exception
    assert "Classification" in page_text(at)


def test_onboard_page_offline_says_why():
    def onboard():
        from pitlens.pitwall import onboard_page, ui

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

        from pitlens.pitwall import about_page, ui

        ui.inject_css()
        titles = [title for title, _ in about_page.WEEKEND + about_page.SEASON]
        about_page.pages = {t: st.Page(lambda: None, title=t, url_path=t.lower().replace(" ", "-")) for t in titles}
        about_page.render()

    at = AppTest.from_function(about, default_timeout=60).run()
    assert not at.exception
    from pitlens.pitwall.about_page import SEASON, WEEKEND

    assert len(at.get("page_link")) == len(WEEKEND) + len(SEASON) + len(FEATURED)


def test_teams_page():
    def teams():
        import streamlit as st

        from pitlens.pitwall import teams_page, ui

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
    at = AppTest.from_string(f"from pitlens.pitwall import ui, {module}\nui.inject_css()\n{module}.render()\n",
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
