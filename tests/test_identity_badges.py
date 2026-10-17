"""Identity marks must follow selected-season entries rather than current team cars."""

from streamlit.testing.v1 import AppTest

from pitlens.dtm import data, teams
from pitlens.dtm.badges import catalog, marks


def test_every_published_manufacturer_is_covered_without_inventing_unknown_logos():
    for year in data.YEARS:
        brands = set(data.race_rows(data.saved(year)).manufacturer)
        assert brands <= catalog()["manufacturers"].keys()
    assert marks(2026, "unknown", ["Unknown"]) == []
    assert not any(b["label"] == "Team identity" for b in marks(2026, "hrt", ["Ford"]))
    assert any(b["label"] == "Team identity" for b in marks(2024, "hrt", ["Mercedes-AMG"]))


def test_driver_and_team_marks_follow_selected_season(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    for year, brand in [(2024, "Audi"), (2026, "Lamborghini")]:
        season = data.saved(year)
        active = teams.participants(season)["abt"]
        rows = data.race_rows(season)
        brands = list(rows[rows.team.isin(active["entries"])].manufacturer.unique())
        assert brands == [brand]
        at = AppTest.from_string("from pitlens.pitwall.dtm_page import render\nrender()", default_timeout=60)
        entry = next(e for e in data.entrants(season).values() if e["manufacturer"] == brand)
        at.query_params.update(year=str(year), view="drivers", driver=entry["driver"])
        at.run()
        assert not at.exception
        badges = [h.proto.body for h in at.get("html") if 'class="identity-badges"' in h.proto.body]
        assert len(badges) == 1
        assert f'{year} car manufacturer' in badges[0] and f'{brand} logo' in badges[0]
