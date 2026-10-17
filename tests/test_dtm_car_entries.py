"""Car counts distinguish season entries from replacement drivers and race starts."""

import pandas as pd
from streamlit.testing.v1 import AppTest

from pitlens.dtm import data, teams


def test_car_count_deduplicates_replacements_and_sponsor_aliases(monkeypatch):
    rows = pd.DataFrame([
        {"team": "Manthey EMA", "number": "91", "manufacturer": "Porsche", "driver": "first"},
        {"team": "Manthey", "number": "91", "manufacturer": "Porsche", "driver": "reserve"},
        {"team": "Manthey", "number": "90", "manufacturer": "Porsche", "driver": "other"},
        {"team": "Land-Motorsport", "number": "91", "manufacturer": "Porsche", "driver": "guest"},
    ])
    monkeypatch.setattr(data, "race_rows", lambda _: rows)
    assert len(teams.car_entries({"year": 2026})) == 3


def test_manufacturer_standings_show_car_counts_instead_of_qualifying_column(monkeypatch):
    monkeypatch.setenv("PITLENS_OFFLINE", "1")
    season = data.saved(2026)
    assert len(teams.car_entries(season)) == 22
    at = AppTest.from_string("from pitlens.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.query_params.update(year="2026", view="championship")
    at.run().segmented_control[0].set_value("manufacturers").run()
    assert not at.exception
    table = at.dataframe[0]
    assert table.value.set_index("Name").loc["Porsche", "Cars"] == 3
    assert table.value.set_index("Name").loc["Mercedes-AMG", "Cars"] == 4
    assert list(table.proto.column_order) == ["Pos", "Name", "Cars", "Points"]
    assert any("qualifying bonuses do not count" in c.value for c in at.caption)
