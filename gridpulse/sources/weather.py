"""Rainfall in millimetres, which F1's own feed doesn't give (it only says rain yes/no).

Hourly precipitation for the circuit's location from Open-Meteo's free
historical forecast API (no key). It's a weather-model estimate for the area
around the track (a few km grid), not a gauge at the circuit, so it reads
"how hard was it raining around here this hour".
"""

import json
from pathlib import Path

import pandas as pd
import requests

from gridpulse.session import CACHE_DIR

CACHE = CACHE_DIR / "weather"
HEADERS = {"User-Agent": "GridPulse/0.1 (+https://github.com/KaiQ7an/gridpulse)"}

# Circuit locations (FastF1 "Location" names) -> latitude, longitude.
CIRCUITS = {
    "melbourne": (-37.8497, 144.968), "shanghai": (31.3389, 121.2197), "suzuka": (34.8431, 136.5407),
    "sakhir": (26.0325, 50.5106), "jeddah": (21.6319, 39.1044), "miami": (25.9581, -80.2389), "miami gardens": (25.9581, -80.2389),
    "montréal": (45.5000, -73.5228), "montreal": (45.5000, -73.5228), "monaco": (43.7347, 7.4206),
    "monte carlo": (43.7347, 7.4206), "barcelona": (41.5700, 2.2611), "spielberg": (47.2197, 14.7647),
    "silverstone": (52.0786, -1.0169), "spa-francorchamps": (50.4372, 5.9714), "budapest": (47.5789, 19.2486),
    "zandvoort": (52.3888, 4.5409), "monza": (45.6156, 9.2811), "madrid": (40.4650, -3.6150),
    "baku": (40.3725, 49.8533), "marina bay": (1.2914, 103.8640), "singapore": (1.2914, 103.8640),
    "austin": (30.1328, -97.6411), "mexico city": (19.4042, -99.0907), "são paulo": (-23.7036, -46.6997),
    "sao paulo": (-23.7036, -46.6997), "las vegas": (36.1147, -115.1730), "lusail": (25.4900, 51.4542),
    "yas island": (24.4672, 54.6031), "yas marina": (24.4672, 54.6031), "abu dhabi": (24.4672, 54.6031),
    "imola": (44.3439, 11.7167), "portimão": (37.2270, -8.6267), "istanbul": (40.9517, 29.4050),
    "sochi": (43.4057, 39.9578), "le castellet": (43.2506, 5.7917), "hockenheim": (49.3278, 8.5656),
    "mugello": (43.9975, 11.3719), "nürburgring": (50.3356, 6.9475), "nurburgring": (50.3356, 6.9475),
    "kuala lumpur": (2.7608, 101.7382), "sepang": (2.7608, 101.7382), "losail": (25.4900, 51.4542),
}


def coordinates(location: str) -> tuple[float, float] | None:
    return CIRCUITS.get((location or "").strip().lower())


def hourly_rain(location: str, start_utc: pd.Timestamp, hours: int = 5) -> pd.Series | None:
    """Precipitation (mm in each UTC hour) at the circuit from the race start for `hours` hours."""
    where = coordinates(location)
    if where is None or start_utc is None or pd.isna(start_utc):
        return None
    start = pd.Timestamp(start_utc).tz_localize(None) if pd.Timestamp(start_utc).tzinfo else pd.Timestamp(start_utc)
    day_from, day_to = start.normalize(), (start + pd.Timedelta(hours=hours)).normalize()
    path = Path(CACHE) / f"{location.lower().replace(' ', '_')}_{day_from:%Y%m%d}_{day_to:%Y%m%d}.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        params = {"latitude": where[0], "longitude": where[1], "hourly": "precipitation", "timezone": "UTC",
                  "start_date": f"{day_from:%Y-%m-%d}", "end_date": f"{day_to:%Y-%m-%d}"}
        try:
            resp = requests.get("https://historical-forecast-api.open-meteo.com/v1/forecast", params=params,
                                headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    hourly = data.get("hourly") or {}
    if not hourly.get("time"):
        return None
    series = pd.Series(hourly["precipitation"], index=pd.to_datetime(hourly["time"]), dtype=float)
    return series[(series.index >= start.floor("h")) & (series.index <= start + pd.Timedelta(hours=hours))]


def rain_at(series: pd.Series | None, when_utc: pd.Timestamp) -> float | None:
    """mm of rain in the hour that contains `when_utc`."""
    if series is None or series.empty or when_utc is None or pd.isna(when_utc):
        return None
    hour = pd.Timestamp(when_utc).floor("h")
    return float(series.get(hour)) if hour in series.index and pd.notna(series.get(hour)) else None
