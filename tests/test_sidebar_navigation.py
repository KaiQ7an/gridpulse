"""The shared sidebar remains usable across series and unavailable F1 sessions."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from pitlens.pitwall import app
from pitlens.session import TimingUnavailable

APP = str(Path(__file__).resolve().parent.parent / "pitlens" / "pitwall" / "app.py")
F1_LINKS = ["Championship", "Race replay", "Qualifying", "Onboard", "Teams", "Drivers", "Circuits", "About"]


def test_sidebar_links_are_series_specific_and_keep_the_replay(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    at = AppTest.from_file(APP, default_timeout=90)
    at.query_params.update(year="2025", round="4", lap="23", drivers="HAM,LEC", view="Tyres", mode="replay")
    at.run()
    assert not at.exception
    assert [link.label for link in at.sidebar.get("page_link")] == F1_LINKS
    assert 'series-nav-replay' in ''.join(h.proto.body for h in at.get("html"))
    at.selectbox(key="racing_series").set_value("DTM").run()
    assert not at.exception
    assert [link.label for link in at.sidebar.get("page_link")] == ["About"]
    assert at.radio(key="dtm_view").options == ["Championship", "Race weekends", "Teams", "Drivers", "Circuits", "Driver comparison"]
    at.selectbox(key="racing_series").set_value("Formula 1").run()
    assert not at.exception
    assert [link.label for link in at.sidebar.get("page_link")] == F1_LINKS
    assert at.slider(key="lap").value == 23
    assert at.toggle(key="no_spoilers").value
    assert at.multiselect(key="focus").value == ["HAM", "LEC"]


def test_unavailable_race_keeps_navigation_visible(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")

    def unavailable(*args, **kwargs):
        raise TimingUnavailable("Timing is unavailable for this test race")

    monkeypatch.setattr(app, "cached_race", unavailable)
    at = AppTest.from_string("from pitlens.pitwall.app import main\nmain()", default_timeout=90)
    at.query_params.update(year="2025", round="4")
    at.run()
    assert not at.exception
    assert any("Timing is unavailable" in w.value for w in at.warning)
    assert [link.label for link in at.sidebar.get("page_link")] == F1_LINKS
