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


def test_driver_badge_links_to_same_season_team_and_keeps_official_source(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    at = AppTest.from_string("from pitlens.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.query_params.update(year="2024", view="drivers", driver="wittmann-marco")
    at.run()
    assert not at.exception
    card = next(h.proto.body for h in at.get("html") if 'class="identity-badges"' in h.proto.body)
    assert '/dtm?year=2024&amp;view=teams&amp;team=schubert' in card
    assert 'Official Schubert Motorsport logo source' in card
    assert 'Explore team →' in card


def test_logo_frames_stay_within_source_and_keep_original_colours():
    from pitlens.pitwall.identity_badges import artwork

    for category in catalog().values():
        if not isinstance(category, dict):
            continue
        for badge in category.values():
            frame = badge.get("artwork")
            if not frame:
                continue
            x, y, width, height = frame["bounds"]
            assert 0 <= x < x + width <= frame["width"]
            assert 0 <= y < y + height <= frame["height"]
            markup = artwork(badge)
            assert badge["url"] in markup and 'class="identity-artwork"' in markup
            assert 'filter' not in markup
