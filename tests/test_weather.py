import pandas as pd

from gridpulse.sources.weather import coordinates, rain_at


def test_coordinates_ignore_case_and_cover_aliases():
    assert coordinates("Marina Bay") == coordinates("singapore")
    assert coordinates("Spa-Francorchamps") is not None
    assert coordinates("Nowhere") is None


def test_rain_at_picks_the_hour_containing_the_time():
    series = pd.Series([0.0, 0.9, 0.1], index=pd.to_datetime(["2026-10-04 07:00", "2026-10-04 08:00", "2026-10-04 09:00"]))
    assert rain_at(series, pd.Timestamp("2026-10-04 08:38")) == 0.9
    assert rain_at(series, pd.Timestamp("2026-10-04 11:00")) is None
    assert rain_at(None, pd.Timestamp("2026-10-04 08:00")) is None
