"""OpenF1 (api.openf1.org) as a second source for a race.

Used when F1's live-timing archive won't serve a session. Everything is
reshaped into the columns FastF1 uses (laps with Time, LapTime, PitInTime,
Stint, Compound, TyreLife, TrackStatus, ...), so the analysis code doesn't
know which source the data came from. Responses are cached on disk; a
finished race doesn't change.
"""

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from pitlens.session import CACHE_DIR

API = "https://api.openf1.org/v1/"
# Identify ourselves honestly; some APIs refuse the anonymous python-requests default.
HEADERS = {"User-Agent": "PitLens/0.1 (+https://github.com/KaiQ7an/pitlens)"}
CACHE = CACHE_DIR / "openf1"
_last_call = 0.0


class OpenF1Error(RuntimeError):
    pass


def get(endpoint: str, cache: bool = True, **params) -> list[dict]:
    """GET an OpenF1 endpoint, politely rate-limited, cached on disk."""
    global _last_call
    key = hashlib.sha1(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()[:16]
    path = CACHE / endpoint / f"{key}.json"
    if cache and path.exists():
        return json.loads(path.read_text())

    for attempt in range(6):
        wait = 0.35 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        resp = requests.get(API + endpoint, params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 429:  # rate limited: back off and retry
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 404:
            return []
        if not resp.ok:
            raise OpenF1Error(f"OpenF1 {endpoint} returned HTTP {resp.status_code}")
        data = resp.json()
        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        return data
    raise OpenF1Error(f"OpenF1 {endpoint} kept rate-limiting us; try again in a minute")


def find_session(year: int, race_date_utc: pd.Timestamp, session_name: str = "Race") -> dict:
    """The OpenF1 session that starts on the same UTC day as the race in FastF1's schedule."""
    sessions = get("sessions", cache=False, year=year, session_name=session_name)
    day = pd.Timestamp(race_date_utc).tz_localize(None).normalize() if pd.Timestamp(race_date_utc).tzinfo \
        else pd.Timestamp(race_date_utc).normalize()
    for s in sessions:
        start = pd.Timestamp(s["date_start"]).tz_convert(None).normalize()
        if start == day and not s.get("is_cancelled"):
            return s
    raise OpenF1Error(f"OpenF1 has no {session_name} on {day:%Y-%m-%d}")


def _utc(series) -> pd.Series:
    return pd.to_datetime(series, utc=True, format="ISO8601").dt.tz_convert(None)


def track_status_by_lap(race_control: pd.DataFrame, total_laps: int) -> dict[int, str]:
    """Rebuild FastF1-style track status codes per lap from race control messages.

    1 green, 2 yellow (any sector), 4 safety car, 5 red flag, 6 VSC, 7 VSC ending.
    A lap gets every code that was in force at some point during it.
    """
    msgs = race_control.sort_values("date")
    by_lap = {lap: g for lap, g in msgs.groupby("lap_number")}
    sc = vsc = red = False
    yellow: set = set()
    out = {}
    for lap in range(1, total_laps + 1):
        codes = set()

        def snapshot():
            codes.add("5" if red else "4" if sc else "6" if vsc else "1")
            if yellow and not (sc or vsc or red):
                codes.add("2")

        snapshot()
        for m in (by_lap[lap].itertuples() if lap in by_lap else []):
            text = (m.message or "").upper()
            if m.category == "SafetyCar":
                if "VSC DEPLOYED" in text or "VIRTUAL SAFETY CAR DEPLOYED" in text:
                    vsc = True
                elif "VSC ENDING" in text or "VIRTUAL SAFETY CAR ENDING" in text:
                    vsc = False
                    codes.add("7")
                elif "SAFETY CAR DEPLOYED" in text:
                    sc = True
                elif "IN THIS LAP" in text:
                    codes.add("4")
                    sc = False
            elif m.category == "Other" and "BEHIND THE SAFETY CAR" in text:
                sc, red = True, False  # rolling (re)start: ends with "SAFETY CAR IN THIS LAP"
            elif m.flag == "RED" or text.startswith("RED FLAG"):
                red, sc, vsc = True, False, False  # a red flag supersedes any safety car
            elif text.startswith(("STANDING START", "ROLLING START")):
                red = False
            elif m.flag in ("YELLOW", "DOUBLE YELLOW") and m.scope == "Sector":
                yellow.add(m.sector)
            elif m.flag == "CLEAR" and m.scope == "Sector":
                yellow.discard(m.sector)
            elif m.flag in ("CLEAR", "GREEN") and m.scope == "Track":
                yellow.clear()
                red = False
            snapshot()
        out[lap] = "".join(sorted(codes)) if codes != {"1"} else "1"
    return out


def race_parts(year: int, race_date_utc) -> dict:
    """Everything `pitwall.data` needs for one race, from OpenF1."""
    session = find_session(year, race_date_utc)
    sk = session["session_key"]
    t0 = pd.Timestamp(session["date_start"]).tz_convert(None)

    meeting = (get("meetings", meeting_key=session["meeting_key"]) or [{}])[0]
    drivers = pd.DataFrame(get("drivers", session_key=sk)).drop_duplicates("driver_number")
    laps = pd.DataFrame(get("laps", session_key=sk))
    if laps.empty:
        raise OpenF1Error("OpenF1 has no lap data for this race yet")
    stints = pd.DataFrame(get("stints", session_key=sk))
    pits = pd.DataFrame(get("pit", session_key=sk))
    result = pd.DataFrame(get("session_result", session_key=sk))
    rc = pd.DataFrame(get("race_control", session_key=sk))
    weather = pd.DataFrame(get("weather", session_key=sk))
    radio = pd.DataFrame(get("team_radio", session_key=sk))
    position = pd.DataFrame(get("position", session_key=sk))

    abbr = dict(zip(drivers["driver_number"], drivers["name_acronym"]))
    team = dict(zip(drivers["driver_number"], drivers["team_name"]))
    colour = dict(zip(drivers["driver_number"], drivers["team_colour"]))

    # ---- laps -> FastF1 columns
    laps = laps.sort_values(["driver_number", "lap_number"]).copy()
    laps["start"] = _utc(laps["date_start"])
    laps["next_start"] = laps.groupby("driver_number")["start"].shift(-1)
    dur = pd.to_timedelta(laps["lap_duration"], unit="s")
    end = laps["next_start"].where(laps["next_start"].notna(), laps["start"] + dur)
    out = pd.DataFrame(
        {
            "Driver": laps["driver_number"].map(abbr),
            "DriverNumber": laps["driver_number"].astype(str),
            "Team": laps["driver_number"].map(team),
            "LapNumber": laps["lap_number"].astype(float),
            "LapStartTime": laps["start"] - t0,
            "Time": end - t0,
            "LapTime": dur.where(dur.notna(), end - laps["start"]),
            "Sector1Time": pd.to_timedelta(laps["duration_sector_1"], unit="s"),
            "Sector2Time": pd.to_timedelta(laps["duration_sector_2"], unit="s"),
            "Sector3Time": pd.to_timedelta(laps["duration_sector_3"], unit="s"),
            "IsPitOutLap": laps["is_pit_out_lap"].fillna(False).astype(bool),
        }
    ).reset_index(drop=True)

    # Pit stops: OpenF1's lap_number is the in-lap; the out-lap is the next one.
    out["PitInTime"] = pd.Series(pd.NaT, index=out.index, dtype="timedelta64[ns]")
    out["PitOutTime"] = pd.Series(pd.NaT, index=out.index, dtype="timedelta64[ns]")
    for p in pits.itertuples() if not pits.empty else []:
        d = abbr.get(p.driver_number)
        lane = p.lane_duration if "lane_duration" in pits and pd.notna(getattr(p, "lane_duration", np.nan)) else p.pit_duration
        pin = pd.Timestamp(p.date).tz_convert(None) - t0
        inl = (out["Driver"] == d) & (out["LapNumber"] == p.lap_number)
        outl = (out["Driver"] == d) & (out["LapNumber"] == p.lap_number + 1)
        out.loc[inl, "PitInTime"] = pin
        out.loc[outl, "PitOutTime"] = pin + pd.to_timedelta(lane if pd.notna(lane) else 0, unit="s")
    pit_lane_start = out["IsPitOutLap"] & out["PitOutTime"].isna()
    out.loc[pit_lane_start, "PitOutTime"] = out.loc[pit_lane_start, "LapStartTime"]

    # Tyres
    out["Stint"] = np.nan
    out["Compound"] = None
    out["TyreLife"] = np.nan
    for s in stints.itertuples() if not stints.empty else []:
        d = abbr.get(s.driver_number)
        m = (out["Driver"] == d) & out["LapNumber"].between(s.lap_start, s.lap_end)
        out.loc[m, "Stint"] = float(s.stint_number)
        out.loc[m, "Compound"] = s.compound
        out.loc[m, "TyreLife"] = (s.tyre_age_at_start or 0) + out.loc[m, "LapNumber"] - s.lap_start + 1

    total_laps = int(result["number_of_laps"].max()) if not result.empty else int(out["LapNumber"].max())
    status = track_status_by_lap(rc, total_laps) if not rc.empty else {}
    out["TrackStatus"] = out["LapNumber"].astype(int).map(status).fillna("1")
    out["IsAccurate"] = out["LapTime"].notna() & out["PitInTime"].isna() & out["PitOutTime"].isna() & (out["LapNumber"] > 1)
    out["Deleted"] = False

    # Running position at the end of each lap, from the position stream.
    out["Position"] = np.nan
    if not position.empty:
        position["t"] = _utc(position["date"]) - t0
        position["Driver"] = position["driver_number"].map(abbr)
        pos = position.sort_values("t")
        merged = pd.merge_asof(
            out.dropna(subset=["Time"]).sort_values("Time").reset_index(),
            pos[["t", "Driver", "position"]].rename(columns={"t": "Time"}),
            on="Time", by="Driver", direction="backward",
        ).set_index("index")
        out.loc[merged.index, "Position"] = merged["position"].astype(float)

    # ---- results
    winner_laps = result["number_of_laps"].max() if not result.empty else total_laps

    def status_of(r):
        if r.get("dsq"):
            return "Disqualified"
        if r.get("dns"):
            return "Did not start"
        if r.get("dnf"):
            return "Retired"
        return "Finished" if r.get("number_of_laps", 0) >= winner_laps else "Lapped"

    results = pd.DataFrame(
        {
            "Abbreviation": result["driver_number"].map(abbr),
            "DriverNumber": result["driver_number"].astype(str),
            "TeamName": result["driver_number"].map(team),
            "TeamColor": result["driver_number"].map(colour),
            "Position": pd.to_numeric(result["position"], errors="coerce").astype(float),
            "Status": [status_of(r) for r in result.to_dict("records")],
        }
    ).sort_values("Position", na_position="last").reset_index(drop=True)

    messages = pd.DataFrame(
        {
            "Time": _utc(rc["date"]) if not rc.empty else [],
            "Category": rc.get("category"),
            "Message": rc.get("message"),
            "Flag": rc.get("flag"),
            "Scope": rc.get("scope"),
            "Sector": rc.get("sector"),
            "Lap": rc.get("lap_number"),
        }
    )
    wx = pd.DataFrame(
        {
            "Time": _utc(weather["date"]) - t0,
            "AirTemp": weather["air_temperature"],
            "TrackTemp": weather["track_temperature"],
            "Rainfall": weather["rainfall"].astype(bool),
            "Humidity": weather["humidity"],
            "Pressure": weather["pressure"],
            "WindSpeed": weather["wind_speed"],
            "WindDirection": weather["wind_direction"],
        }
    ) if not weather.empty else pd.DataFrame(columns=["Time", "AirTemp", "TrackTemp", "Rainfall"])

    clips = pd.DataFrame(columns=["Driver", "DriverNumber", "SessionTime", "Utc", "Url"])
    if not radio.empty:
        clips = pd.DataFrame(
            {
                "Driver": radio["driver_number"].map(abbr),
                "DriverNumber": radio["driver_number"].astype(str),
                "SessionTime": _utc(radio["date"]) - t0,
                "Utc": pd.to_datetime(radio["date"], utc=True, format="ISO8601"),
                "Url": radio["recording_url"],
            }
        )

    return {
        "laps": out,
        "results": results,
        "messages": messages,
        "weather": wx,
        "radio": clips,
        "total_laps": total_laps,
        "event_name": meeting.get("meeting_name", session.get("location", "")),
        "location": session.get("location", ""),
        "date": t0,
        "source": "OpenF1",
    }


# ---------------------------------------------------------------- onboard (single laps)

ONBOARD_SESSION_NAMES = {
    "Q": "Qualifying",
    "R": "Race",
    "SQ": "Sprint Qualifying",
    "S": "Sprint",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
}


def weekend_session(year: int, race_date_utc, kind: str) -> dict:
    """Any session of the race weekend (qualifying, sprint, practice...) by FastF1-style code."""
    race = find_session(year, race_date_utc)
    name = ONBOARD_SESSION_NAMES[kind]
    names = [name, "Sprint Shootout"] if kind == "SQ" else [name]
    for n in names:
        found = get("sessions", meeting_key=race["meeting_key"], session_name=n)
        if found:
            return found[0]
    raise OpenF1Error(f"OpenF1 has no {name} at this event")


def session_laps(session_key: int) -> pd.DataFrame:
    """Timed laps of a session with driver code and team."""
    drivers = pd.DataFrame(get("drivers", session_key=session_key)).drop_duplicates("driver_number")
    laps = pd.DataFrame(get("laps", session_key=session_key))
    if laps.empty:
        raise OpenF1Error("OpenF1 has no laps for this session")
    laps = laps.merge(drivers[["driver_number", "name_acronym", "team_name"]], on="driver_number", how="left")
    return laps[laps["lap_duration"].notna() & ~laps["is_pit_out_lap"].fillna(False).astype(bool)]


def lap_telemetry(session_key: int, driver_number: int, start, duration_s: float) -> pd.DataFrame:
    """Car data and position for one lap, merged on time, with distance integrated from speed."""
    t0 = pd.Timestamp(start).tz_convert(None) if pd.Timestamp(start).tzinfo else pd.Timestamp(start)
    window = {
        "session_key": session_key,
        "driver_number": driver_number,
        "date>": (t0 - pd.Timedelta(seconds=1)).isoformat(),
        "date<": (t0 + pd.Timedelta(seconds=duration_s + 1)).isoformat(),
    }
    car = pd.DataFrame(get("car_data", **window))
    loc = pd.DataFrame(get("location", **window))
    if car.empty or loc.empty:
        raise OpenF1Error("OpenF1 has no car telemetry for this lap")
    car["t"] = _utc(car["date"])
    loc["t"] = _utc(loc["date"])
    tel = pd.merge_asof(car.sort_values("t"), loc[["t", "x", "y"]].sort_values("t"), on="t", direction="nearest")
    tel = tel[(tel["t"] >= t0) & (tel["t"] <= t0 + pd.Timedelta(seconds=duration_s))]
    secs = (tel["t"] - t0).dt.total_seconds().to_numpy()
    speed_ms = tel["speed"].to_numpy(dtype=float) / 3.6
    dist = np.concatenate([[0.0], np.cumsum(np.diff(secs) * (speed_ms[1:] + speed_ms[:-1]) / 2)])
    return pd.DataFrame(
        {
            "Time": pd.to_timedelta(secs, unit="s"),
            "Distance": dist,
            "Speed": tel["speed"].astype(float).to_numpy(),
            "Throttle": tel["throttle"].astype(float).to_numpy(),
            "Brake": (tel["brake"].fillna(0) > 0).to_numpy(),
            "nGear": tel["n_gear"].astype(float).to_numpy(),
            "DRS": tel["drs"].to_numpy(),
            "X": tel["x"].astype(float).to_numpy(),
            "Y": tel["y"].astype(float).to_numpy(),
        }
    )


def circuit_info(circuit_key: int, year: int) -> tuple[pd.DataFrame, float]:
    """Corners (X, Y, Number, Letter, Angle) and map rotation from the MultiViewer circuit API."""
    path = CACHE / "circuits" / f"{circuit_key}_{year}.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        resp = requests.get(f"https://api.multiviewer.app/api/v1/circuits/{circuit_key}/{year}", headers=HEADERS,
                            timeout=20)
        resp.raise_for_status()
        data = resp.json()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    corners = pd.DataFrame(
        {
            "X": [c["trackPosition"]["x"] for c in data["corners"]],
            "Y": [c["trackPosition"]["y"] for c in data["corners"]],
            "Number": [c["number"] for c in data["corners"]],
            "Letter": [c.get("letter") or "" for c in data["corners"]],
            "Angle": [c["angle"] for c in data["corners"]],
        }
    )
    return corners, float(data.get("rotation", 0))
