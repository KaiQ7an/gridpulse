"""Car counts distinguish season entries from replacement drivers and race starts."""

import pandas as pd
from streamlit.testing.v1 import AppTest

from gridpulse.dtm import data, teams


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
    monkeypatch.setenv("GRIDPULSE_OFFLINE", "1")
    season = data.saved(2026)
    assert len(teams.car_entries(season)) == 22
    at = AppTest.from_string("from gridpulse.pitwall.dtm_page import render\nrender()", default_timeout=60)
    at.query_params.update(year="2026", view="championship")
    at.run().segmented_control[0].set_value("manufacturers").run()
    assert not at.exception
    table = at.dataframe[0]
    assert table.value.set_index("Name").loc["Porsche", "Cars"] == 3
    assert table.value.set_index("Name").loc["Mercedes-AMG", "Cars"] == 4
    markup = ''.join(h.proto.body for h in at.get('html'))
    assert '<th scope="col">Manufacturer</th><th scope="col">Points</th><th scope="col">Cars</th>' in markup
    assert 'Porsche</th><td class="points">356</td><td>3</td>' in markup
    assert any("two best-placed cars from each manufacturer" in note.value
               and "Qualifying bonus points do not count" in note.value for note in at.info)
