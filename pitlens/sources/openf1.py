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

import numpy as np
import pandas as pd
import requests

from pitlens.session import CACHE_DIR

API = "https://api.openf1.org/v1/"
FIRST_SEASON = 2023  # OpenF1 has data from the 2023 season on
# Identify ourselves honestly; some APIs refuse the anonymous python-requests default.
HEADERS = {"User-Agent": "PitLens/0.1 (+https://github.com/KaiQ7an/pitlens)"}
CACHE = CACHE_DIR / "openf1"
_last_call = 0.0


class OpenF1Error(RuntimeError):
    pass


def get(endpoint: str, cache: bool = True, refresh: bool = False, **params) -> list[dict]:
    """GET an OpenF1 endpoint, politely rate-limited, cached on disk (`refresh` skips the cached copy)."""
    global _last_call
    key = hashlib.sha1(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()[:16]
    path = CACHE / endpoint / f"{key}.json"
    if cache and not refresh and path.exists():
        return json.loads(path.read_text())

    for attempt in range(6):
        wait = 0.35 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            resp = requests.get(API + endpoint, params=params, headers=HEADERS, timeout=30)
        except requests.RequestException as exc:
            raise OpenF1Error(f"couldn't reach OpenF1 ({exc.__class__.__name__})") from None
        if resp.status_code == 429:  # rate limited: back off and retry
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 404:
            return []
        if not resp.ok:
            raise OpenF1Error(f"OpenF1 {endpoint} returned HTTP {resp.status_code}")
        data = resp.json()
        if cache and data:  # an empty answer may just mean "not published yet": ask again next time
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        return data
    raise OpenF1Error(f"OpenF1 {endpoint} kept rate-limiting us; try again in a minute")


def find_session(year: int, race_date_utc: pd.Timestamp, session_name: str = "Race") -> dict:
    """The OpenF1 session that starts on the same UTC day as the race in FastF1's schedule."""
    if year < FIRST_SEASON:
        raise OpenF1Error(f"OpenF1 starts in {FIRST_SEASON}")
    day = pd.Timestamp(race_date_utc).tz_localize(None).normalize() if pd.Timestamp(race_date_utc).tzinfo \
        else pd.Timestamp(race_date_utc).normalize()
    # The season's session list only grows, so the cached copy does until it lacks this day.
    for refresh in (False, True):
        for s in get("sessions", refresh=refresh, year=year, session_name=session_name):
            start = pd.Timestamp(s["date_start"]).tz_convert(None).normalize()
            if start == day and not s.get("is_cancelled"):
                return s
    raise OpenF1Error(f"OpenF1 has no {session_name} on {day:%Y-%m-%d}")


def _utc(series) -> pd.Series:
    return pd.to_datetime(series, utc=True, format="ISO8601").dt.tz_convert(None)


def _in_force(sc: bool, vsc: bool, red: bool, yellow: set) -> set[str]:
    """Track status codes in force right now (yellows only count while the race isn't neutralised)."""
    codes = {"5" if red else "4" if sc else "6" if vsc else "1"}
    if yellow and not (sc or vsc or red):
        codes.add("2")
    return codes


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
        codes = _in_force(sc, vsc, red, yellow)
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
            codes |= _in_force(sc, vsc, red, yellow)
        out[lap] = "".join(sorted(codes)) if codes != {"1"} else "1"
    return out


def in_laps(pits: pd.DataFrame, stints: pd.DataFrame) -> pd.Series:
    """The in-lap of each pit stop.

    OpenF1's `lap_number` is the lap the stop was made on. Where the pit boxes
    come before the timing line (Baku, Singapore) that's the in-lap; where
    the pit lane crosses the line (Montreal, Melbourne) the stop falls on the
    next lap, the out-lap, and the new tyre stint starts on that same lap.
    `stints` should already have drive-throughs merged away
    (`merge_continuing_stints`). 0 means the car started from the pit lane.
    """
    starts = stints.groupby("driver_number")["lap_start"].apply(set).to_dict() if not stints.empty else {}
    return pd.Series(
        [int(n) - 1 if n in starts.get(d, set()) else int(n) for d, n in zip(pits["driver_number"], pits["lap_number"])],
        index=pits.index,
    )


def merge_continuing_stints(stints: pd.DataFrame) -> pd.DataFrame:
    """Fold a "stint" that carries on with the same set of tyres into the one before it.

    OpenF1 starts a new stint at every pass through the pit lane, so a
    drive-through penalty, or the whole field being sent through the pit lane
    behind the safety car, looks like a tyre change. Same compound with the
    tyre age carrying straight on means the same tyres. Stints are then
    renumbered 1, 2, 3... A stop-and-go penalty (no tyre change allowed) goes
    the same way.
    """
    if stints.empty or "tyre_age_at_start" not in stints:
        return stints
    rows = []
    for _, d in stints.sort_values(["driver_number", "stint_number"]).groupby("driver_number"):
        kept: list[dict] = []
        for s in d.to_dict("records"):
            prev = kept[-1] if kept else None
            # Within a lap: where the pit lane crosses the timing line the age can read one higher.
            if prev is not None and s["compound"] == prev["compound"] and pd.notna(s["tyre_age_at_start"]) \
                    and pd.notna(prev["tyre_age_at_start"]) and pd.notna(prev["lap_end"]) \
                    and abs(s["tyre_age_at_start"] - (prev["tyre_age_at_start"] + prev["lap_end"] - prev["lap_start"] + 1)) <= 1:
                prev["lap_end"] = s["lap_end"]
                continue
            kept.append(dict(s))
        for n, s in enumerate(kept, start=1):
            s["stint_number"] = n
        rows += kept
    return pd.DataFrame(rows)


def race_parts(year: int, race_date_utc, session_name: str = "Race") -> dict:
    """Everything `pitwall.data` needs for one race (or sprint), from OpenF1."""
    session = find_session(year, race_date_utc, session_name)
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
    first = dict(zip(drivers["driver_number"], drivers.get("first_name", pd.Series(dtype=str))))
    last = dict(zip(drivers["driver_number"], drivers.get("last_name", pd.Series(dtype=str))))

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

    # Pit stops: the in-lap carries PitInTime, the out-lap after it PitOutTime.
    stints = merge_continuing_stints(stints)
    out["PitInTime"] = pd.Series(pd.NaT, index=out.index, dtype="timedelta64[ns]")
    out["PitOutTime"] = pd.Series(pd.NaT, index=out.index, dtype="timedelta64[ns]")
    if not pits.empty:
        pits["in_lap"] = in_laps(pits, stints)
    for p in pits.itertuples() if not pits.empty else []:
        if p.in_lap < 1:
            continue  # started from the pit lane: handled with the pit-out laps below
        d = abbr.get(p.driver_number)
        lane = p.lane_duration if "lane_duration" in pits and pd.notna(getattr(p, "lane_duration", np.nan)) else p.pit_duration
        pin = pd.Timestamp(p.date).tz_convert(None) - t0
        inl = (out["Driver"] == d) & (out["LapNumber"] == p.in_lap)
        outl = (out["Driver"] == d) & (out["LapNumber"] == p.in_lap + 1)
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
            "FirstName": result["driver_number"].map(first),
            "FullName": [f"{first.get(n, '')} {str(last.get(n, '')).title()}".strip() for n in result["driver_number"]],
            "LastName": [str(last.get(n, "")).title() for n in result["driver_number"]],
            "Position": pd.to_numeric(result["position"], errors="coerce").astype(float),
            # Seconds behind the winner for lead-lap finishers ("+1 LAP" and the like become NaN).
            "GapToLeader": pd.to_numeric(result["gap_to_leader"], errors="coerce") if "gap_to_leader" in result else np.nan,
            "Laps": pd.to_numeric(result["number_of_laps"], errors="coerce") if "number_of_laps" in result else np.nan,
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
        "stationary": stationary_from(pits, abbr, stints),
        "results": results,
        "messages": messages,
        "weather": wx,
        "radio": clips,
        "total_laps": total_laps,
        "event_name": meeting.get("meeting_name", session.get("location", "")),
        "location": session.get("location", ""),
        "date": t0,
        "source": "OpenF1",
        "circuit_key": session.get("circuit_key"),
    }


def stationary_from(pits: pd.DataFrame, abbr: dict, stints: pd.DataFrame | None = None) -> pd.DataFrame:
    """How long each car stood still in its pit box (s), by driver and in-lap, where the feed has it.

    F1's timing only started publishing this in 2024 and it's patchy since:
    some races have every stop, some none. `stints` (merged) places each stop
    on its in-lap; see `in_laps`.
    """
    if pits.empty or "stop_duration" not in pits:
        return pd.DataFrame(columns=["Driver", "Lap", "Stationary"])
    laps = in_laps(pits, merge_continuing_stints(stints)) if stints is not None else pits["lap_number"]
    out = pd.DataFrame(
        {
            "Driver": pits["driver_number"].map(abbr),
            "Lap": pd.to_numeric(laps, errors="coerce"),
            "Stationary": pd.to_numeric(pits["stop_duration"], errors="coerce"),
        }
    ).dropna()
    out["Lap"] = out["Lap"].astype(int)
    return out.drop_duplicates(["Driver", "Lap"]).reset_index(drop=True)


def team_radio(year: int, race_date_utc, numbers: dict[int, str], session_name: str = "Race") -> pd.DataFrame:
    """A race's team radio clips (Driver, DriverNumber, Utc, Url), for races whose laps came from F1's
    archive when the archive won't serve the radio stream. `numbers` maps car number to driver code."""
    session = find_session(year, race_date_utc, session_name)
    radio = pd.DataFrame(get("team_radio", session_key=session["session_key"]))
    if radio.empty:
        return pd.DataFrame(columns=["Driver", "DriverNumber", "Utc", "Url"])
    return pd.DataFrame(
        {
            "Driver": radio["driver_number"].map(numbers),
            "DriverNumber": radio["driver_number"].astype(str),
            "Utc": pd.to_datetime(radio["date"], utc=True, format="ISO8601"),
            "Url": radio["recording_url"],
        }
    ).dropna(subset=["Driver", "Url"])


def lap_starts(year: int, race_date_utc, session_name: str = "Race") -> pd.DataFrame:
    """When each lap of the race started, in UTC: DriverNumber (str), LapNumber (float), Utc (naive)."""
    session = find_session(year, race_date_utc, session_name)
    laps = pd.DataFrame(get("laps", session_key=session["session_key"]))
    if laps.empty:
        return pd.DataFrame(columns=["DriverNumber", "LapNumber", "Utc"])
    return pd.DataFrame(
        {
            "DriverNumber": laps["driver_number"].astype(str),
            "LapNumber": laps["lap_number"].astype(float),
            "Utc": _utc(laps["date_start"]),
        }
    ).dropna()


def stationary_times(year: int, race_date_utc, numbers: dict[int, str], session_name: str = "Race") -> pd.DataFrame:
    """Stationary times for a race whose laps came from F1's archive (which doesn't carry them).

    `numbers` maps car number to driver code.
    """
    session = find_session(year, race_date_utc, session_name)
    pits = pd.DataFrame(get("pit", session_key=session["session_key"]))
    stints = pd.DataFrame(get("stints", session_key=session["session_key"]))
    return stationary_from(pits, numbers, stints)


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


def _circuit(circuit_key: int, year: int) -> dict:
    path = CACHE / "circuits" / f"{circuit_key}_{year}.json"
    if path.exists():
        return json.loads(path.read_text())
    resp = requests.get(f"https://api.multiviewer.app/api/v1/circuits/{circuit_key}/{year}", headers=HEADERS,
                        timeout=20)
    resp.raise_for_status()
    data = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def circuit_pit_loss(circuit_key: int, year: int) -> dict[str, float] | None:
    """Reference time lost to a pit stop at this circuit: green flag, under VSC and under SC (seconds)."""
    try:
        loss = _circuit(circuit_key, year).get("pitLoss") or {}
        out = {k: float(loss[k]) for k in ("normal", "vsc", "sc") if loss.get(k) not in (None, "")}
        return out if "normal" in out else None
    except (requests.RequestException, ValueError):
        return None


def circuit_info(circuit_key: int, year: int) -> tuple[pd.DataFrame, float]:
    """Corners (X, Y, Number, Letter, Angle) and map rotation from the MultiViewer circuit API."""
    data = _circuit(circuit_key, year)
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


def track_outline(year: int, race_date_utc, circuit_key: int | None, session_name: str = "Race") -> dict | None:
    """The circuit as a line split into the three timing sectors.

    From 2023 (OpenF1's coverage) it's the race's fastest lap as actually
    driven, cut where that lap's official sector times end. Before that it
    falls back to the MultiViewer outline, split by the same time shares
    (approximate). Returns x, y, the sector boundary indices and rotation.
    """
    rotation = 0.0
    try:
        circuit = _circuit(circuit_key, year) if circuit_key else {}
        rotation = float(circuit.get("rotation", 0))
    except (requests.RequestException, ValueError):
        circuit = {}

    try:
        session = find_session(year, race_date_utc, session_name)
        laps = session_laps(session["session_key"])
        laps = laps.dropna(subset=["duration_sector_1", "duration_sector_2", "duration_sector_3"])
        median = laps["lap_duration"].median()
        laps = laps[(laps["lap_duration"] > 0.85 * median) & (laps["lap_number"] > 1)]
        lap = laps.loc[laps["lap_duration"].idxmin()]
        tel = lap_telemetry(session["session_key"], int(lap["driver_number"]), lap["date_start"],
                            float(lap["lap_duration"]))
        secs = tel["Time"].dt.total_seconds().to_numpy()
        s1 = float(lap["duration_sector_1"])
        s2 = s1 + float(lap["duration_sector_2"])
        return {"x": tel["X"].to_numpy(), "y": tel["Y"].to_numpy(),
                "splits": [int(np.searchsorted(secs, s1)), int(np.searchsorted(secs, s2))],
                "rotation": rotation, "source": "fastest lap"}
    except (OpenF1Error, requests.RequestException, KeyError, ValueError):
        pass

    if circuit.get("x"):
        x, y = np.asarray(circuit["x"], float), np.asarray(circuit["y"], float)
        t = np.asarray(circuit.get("trackPositionTime") or np.linspace(0, 1, len(x)), float)
        frac = t / t[-1]
        return {"x": x, "y": y, "splits": [int(np.searchsorted(frac, 1 / 3)), int(np.searchsorted(frac, 2 / 3))],
                "rotation": rotation, "source": "circuit outline (approximate sectors)"}
    return None
