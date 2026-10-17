"""Model generations, biography coverage and the new driver/car page interactions."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pitlens.drivers.profiles import birth_date, catalog, profile, public_url
from pitlens.dtm import data, teams
from pitlens.dtm.cars import model
from pitlens.dtm.cars import profile as car_profile
from pitlens.season.data import load_season, seasons_saved
from pitlens.season.facts import facts


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")


def page(module, **params):
    at = AppTest.from_string(f"from pitlens.pitwall.{module} import render\nrender()", default_timeout=60)
    at.query_params.update(params)
    return at.run()


def text(at):
    return " ".join([*(h.proto.body for h in at.get("html")), *(m.value for m in at.markdown)])


def test_car_generations_follow_the_selected_season_including_live_classifications():
    assert model(2024, "BMW") == "BMW M4 GT3"
    assert model(2025, "BMW") == "BMW M4 GT3 Evo"
    assert model(2025, "Lamborghini") == "Lamborghini Huracán GT3 Evo II"
    assert model(2026, "Lamborghini") == "Lamborghini Temerario GT3"
    assert model(2025, "Ferrari") == "Ferrari 296 GT3"
    assert model(2026, "Ferrari") == "Ferrari 296 GT3 Evo"
    assert model(2026, "Ford") == "Ford Mustang GT3 Evo"
    assert car_profile(2023, "Ford")["photo"] is None  # no guessing a future model
    for year in data.YEARS:
        rows = data.race_rows(data.saved(year))
        assert not rows.model.eq("Model not confirmed").any()
        assert all(car_profile(year, brand)["photo"]["source"].startswith("https://")
                   for brand in rows.manufacturer.unique())
    summary = data.comparison(data.saved(2026), ["preining-thomas"])
    assert summary.iloc[0]["Car model"] == "Porsche 911 GT3 R Evo"


def test_all_saved_drivers_have_sourced_introductions_and_known_births_parse():
    f1 = catalog("f1")
    for year in seasons_saved():
        drivers = set(load_season(year).results.Driver)
        assert drivers <= set(f1)
    dtm = catalog("dtm")
    for year in data.YEARS:
        assert set(data.race_rows(data.saved(year)).driver) <= set(dtm)
    for entry in [*f1.values(), *dtm.values()]:
        assert entry["name"] and entry["intro"] and entry["sources"]
        assert all(public_url(source) for source in entry["sources"])
        if entry.get("birth") not in (None, "", "-"):
            assert birth_date(entry["birth"]) != "Not published", entry["name"]
    assert birth_date(None) == birth_date("-") == "Not published"
    assert birth_date("2026-02-30") == "Not published"
    assert public_url("javascript:alert(1)") is None
    assert profile("f1", "UNKNOWN") == {}


def test_practice_appearances_are_not_reported_as_f1_race_debuts():
    assert profile("f1", "ANT")["debut"] == "2025"
    assert profile("f1", "LIN")["debut"] == "2026"
    assert profile("f1", "BEA")["debut"] == "2024"
    assert profile("f1", "DEV")["debut"] == "2022"


def test_team_profile_link_facts_and_car_follow_season_changes():
    at = page("dtm_page", year="2025", view="teams", team="emil-frey")
    assert not at.exception
    assert at.selectbox(key="dtm_team").value == "emil-frey"
    assert "Safenwil" in text(at) and "Team history" in text(at)
    assert "Ferrari 296 GT3" in text(at) and "Ferrari 296 GT3 Evo" not in text(at)
    at.selectbox(key="dtm_year").set_value(2026).run()
    assert not at.exception and "Ferrari 296 GT3 Evo" in text(at)
    assert "dtm-team-photo" in text(at) and at.query_params["team"] == "emil-frey"
    at.selectbox(key="dtm_year").set_value(2023).run()
    assert not at.exception and "Ferrari 296 GT3 Evo" not in text(at)
    at.selectbox(key="dtm_team").set_value("all").run()
    assert "team" not in at.query_params


def test_only_season_participants_include_guests_and_sponsor_aliases_are_year_sensitive():
    assert teams.identity(2023, "Mercedes-AMG Team MANN-FILTER") == "landgraf"
    assert teams.identity(2024, "Mercedes-AMG Team MANN-FILTER") == "winward"
    for year in data.YEARS:
        active = teams.participants(data.saved(year))
        assert all(t["history"] and t["sources"] for t in active.values())
        assert all(k in teams.catalog() for k in active)
    current = teams.participants(data.saved(2026))
    assert "ssr" not in current and "seyffarth" in current and len(current) == 12
    assert "comtoyou" not in teams.participants(data.saved(2023))
    at = page("dtm_page", year="2024", view="teams", team="ssr")
    assert at.selectbox(key="dtm_team").value == "ssr"
    at.selectbox(key="dtm_year").set_value(2026).run()
    assert not at.exception and at.selectbox(key="dtm_team").value == "all"
    assert "ssr" not in at.selectbox(key="dtm_team").options


def test_f1_team_history_has_era_specific_honours_and_no_future_teams():
    assert facts("McLaren", 2023)["titles"] == 8
    assert facts("McLaren", 2024)["titles"] == 9
    assert facts("McLaren", 2026)["titles"] == 10
    assert facts("Mercedes", 2026)["titles"] == 8
    assert facts("Alpine", 2025)["titles"] == 0
    for year in seasons_saved():
        assert all(facts(t, year)["history"] for t in load_season(year).results.Team.unique())
    at = page("teams_page", year="2025", team="Audi")
    assert not at.exception
    assert "Audi" not in at.pills(key="team_pick").options
    assert "Cadillac" not in at.pills(key="team_pick").options
    assert "Team history &amp; headquarters" in text(at)
    at.selectbox(key="team_year").set_value(2023).run()
    assert not at.exception and "Alfa Romeo" in at.pills(key="team_pick").options


def test_empty_optional_dtm_widget_state_recovers():
    at = AppTest.from_string("from pitlens.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.session_state["dtm_category"] = None
    at.session_state["dtm_view"] = None
    at.session_state["dtm_year"] = None
    at.run()
    assert not at.exception and at.segmented_control(key="dtm_category").value == "drivers"


def test_dtm_driver_introduction_link_and_model_changes():
    at = page("dtm_page", year="2025", view="drivers", driver="preining-thomas")
    assert not at.exception
    assert "21 July 1998" in text(at) and "Driver introduction" in text(at)
    at.selectbox(key="dtm_profile").set_value("bortolotti-mirko").run()
    assert not at.exception and at.query_params["driver"] == "bortolotti-mirko"
    assert "Lamborghini Huracán GT3 Evo II" in text(at)
    at.selectbox(key="dtm_year").set_value(2026).run()
    assert not at.exception and "Lamborghini Temerario GT3" in text(at)
    at.radio(key="dtm_view").set_value("teams").run()
    at.radio(key="dtm_view").set_value("drivers").run()
    assert not at.exception and at.selectbox(key="dtm_profile").value == "bortolotti-mirko"


def test_f1_introduction_retains_selected_historical_team_and_labels_current_portrait():
    at = page("drivers_page", year="2023", driver="HAM")
    assert not at.exception
    assert "07 January 1985" in text(at) and "Mercedes" in text(at)
    assert any("Current official F1 portrait" in c.value for c in at.caption)
    at.selectbox(key="driver_pick").set_value("PIA").run()
    assert not at.exception and "06 April 2001" in text(at)
    assert "Oscar Piastri" in text(at) and at.query_params["driver"] == "PIA"


def test_new_reference_data_is_declared_as_package_data():
    root = Path(__file__).resolve().parent.parent
    for file in ("pitlens/milestones.json", "pitlens/dtm/cars.json", "pitlens/dtm/teams.json", "pitlens/drivers/f1.json", "pitlens/drivers/dtm.json"):
        assert json.loads((root / file).read_text())
    config = (root / "pyproject.toml").read_text()
    assert '"pitlens.drivers" = ["f1.json", "dtm.json"]' in config


def test_career_milestones_are_not_limited_to_saved_seasons_or_inherited_identities():
    from pitlens import milestones

    def record(series, kind, key, field, year=2026):
        status, result = milestones.milestone(series, kind, key, field, year)
        assert status == "achieved"
        return result

    assert record("f1", "drivers", "HAM", "first_points")["year"] == 2007
    # Perez's debut Australian result was disqualified; his first points came in Spain.
    assert record("f1", "drivers", "PER", "first_points")["event"] == "Spanish Grand Prix"
    assert record("f1", "teams", "McLaren", "first_points")["date"] == "1966-07-16"
    assert record("f1", "teams", "McLaren", "first_win")["year"] == 1968
    assert record("f1", "teams", "Williams", "first_points")["year"] == 1978
    assert record("f1", "teams", "Mercedes", "first_win")["year"] == 2012
    assert milestones.milestone("f1", "teams", "Alfa Romeo", "first_win", 2023) == ("not_yet", None)
    assert milestones.milestone("f1", "drivers", "NOR", "first_win", 2023) == ("not_yet", None)
    assert record("f1", "drivers", "NOR", "first_win", 2024)["event"] == "Miami Grand Prix"
    assert record("f1", "drivers", "PIA", "first_win")["year"] == 2024  # 2023 sprint is separate


def test_dtm_milestones_count_real_awards_and_do_not_claim_partial_archive_firsts():
    from pitlens import milestones

    status, points = milestones.milestone("dtm", "drivers", "bortolotti-mirko", "first_points", 2026)
    assert status == "achieved" and points["year"] == 2022  # 2021 guest podium scored zero
    status, points = milestones.milestone("dtm", "teams", "winward", "first_points", 2026)
    assert status == "achieved" and points["session"] == "Qualifying 1" and points["points"] == 2
    assert milestones.milestone("dtm", "drivers", "auer-lucas", "first_points", 2026) == ("unverified", None)
    assert milestones.milestone("dtm", "drivers", "glock-timo", "first_win", 2026)[1]["year"] == 2013
    assert milestones.milestone("dtm", "drivers", "rast-rene", "first_points", 2026)[1]["year"] == 2016
    assert milestones.milestone("dtm", "teams", "abt", "first_win", 2026)[1]["year"] == 2001
    for series in ("f1", "dtm"):
        assert set(catalog(series)) <= set(milestones.catalog()[series]["drivers"])
    assert set(teams.catalog()) <= set(milestones.catalog()["dtm"]["teams"])


def test_milestone_cards_follow_the_selected_season():
    at = page("drivers_page", year="2023", driver="NOR")
    assert not at.exception and "First GP points" in text(at) and "Not achieved by 2023" in text(at)
    at.selectbox(key="driver_year").set_value(2024).run()
    assert not at.exception and "Miami Grand Prix" in text(at)
