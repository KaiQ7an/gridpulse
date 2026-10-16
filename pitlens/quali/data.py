"""One qualifying session as plain tables: the Q1/Q2/Q3 classification and every timed lap.

From F1's archive via FastF1, or from OpenF1 when the archive won't serve it (where deleted
laps come from race control's "TIME ... DELETED" messages).
"""

import re
from dataclasses import dataclass

import fastf1
import numpy as np
import pandas as pd

from pitlens import snapshots
from pitlens.session import TimingUnavailable, enable_cache, load_session, refused_recently, remember_refusal
from pitlens.sources import openf1
from pitlens.style import FALLBACK_TEAM_COLOR

SESSIONS = {"Q": "Qualifying", "SQ": "Sprint Qualifying"}
SHOOTOUT_YEARS = (2023,)  # sprint qualifying ran as the Sprint Shootout, FastF1 session "SS"
PARTS = ("Q1", "Q2", "Q3")
_DELETED = re.compile(r"CAR (\d+) \((\w+)\).*DELETED.*?\bLAP (\d+)")


def session_name(year: int, kind: str) -> str:
    return "Sprint Shootout" if kind == "SQ" and year in SHOOTOUT_YEARS else SESSIONS[kind]


@dataclass
class QualiData:
    name: str  # "2026 Singapore Grand Prix"
    event_name: str
    session_name: str  # "Qualifying" or "Sprint Qualifying"
    year: int
    round_number: int
    location: str
    date: pd.Timestamp
    source: str
    results: pd.DataFrame  # Position, Driver, Team, Q1, Q2, Q3 (s), Out ("Q1", "Q2" or "")
    laps: pd.DataFrame  # Driver, LapNumber, LapTime, S1, S2, S3 (s), Minute (session time), Deleted, Compound
    team_colors: dict[str, str]


def load_quali(year: int, round_number: int, kind: str = "Q") -> QualiData:
    """A qualifying (kind "Q") or sprint qualifying ("SQ") session, from a snapshot if there is one."""
    saved = snapshots.load_quali(year, round_number, kind)
    if saved is not None:
        return saved
    if snapshots.offline():
        raise TimingUnavailable(f"No saved copy of {year} round {round_number} {SESSIONS[kind]}, and PitLens is "
                                "running offline.")
    return fetch_quali(year, round_number, kind)


def fetch_quali(year: int, round_number: int, kind: str = "Q") -> QualiData:
    """A qualifying session from the data sources (not a snapshot)."""
    key = f"{year}-{round_number}-{kind}"
    archive_error = TimingUnavailable(f"F1's live-timing archive refused {year} round {round_number} recently.")
    if not refused_recently(key):
        try:
            return _from_fastf1(year, round_number, kind)
        except TimingUnavailable as exc:
            archive_error = exc
            remember_refusal(key)
    try:
        return _from_openf1(year, round_number, kind)
    except openf1.OpenF1Error as exc:
        raise TimingUnavailable(f"{archive_error} OpenF1 couldn't provide it either: {exc}") from None


def eliminated_in(results: pd.DataFrame) -> pd.Series:
    """Which part each driver went out in: "Q1", "Q2", or "" for those who made Q3.

    Ten go through to Q3, and Q1 and Q2 knock out the rest in equal numbers (five each from 20
    cars, six each from 22). A car that made a part without setting a time in it is still
    classified in that part's group, so the cut-offs come from the number of cars as well as from
    who has times. A car with no time at all went out in Q1.
    """
    if results["Q2"].isna().all():  # a session that never got past one part
        return pd.Series("", index=results.index)
    position = results["Position"]
    cars = int(position.notna().sum())
    q2_cut = max(10 + int(np.ceil((cars - 10) / 2)), position[results["Q2"].notna()].max())
    q3_cut = max(10, position[results["Q3"].notna()].max()) if results["Q3"].notna().any() else 0
    out = pd.Series("Q1", index=results.index)
    out[position <= q2_cut] = "Q2"
    out[position <= q3_cut] = ""
    return out


def ideal_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Per driver: best lap, best S1/S2/S3 and the ideal lap (their best sectors added up), from valid laps."""
    valid = laps[~laps["Deleted"]].dropna(subset=["LapTime"])
    valid = valid[valid["LapTime"] < 1.07 * valid["LapTime"].min()] if not valid.empty else valid  # push laps
    rows = []
    for driver, d in valid.groupby("Driver"):
        sectors = {}
        for s in ("S1", "S2", "S3"):
            times = d[s].dropna()
            sectors[s] = float(times.min()) if not times.empty else np.nan
        ideal = sum(sectors.values())
        rows.append({"Driver": driver, "Best": float(d["LapTime"].min()), **sectors, "Ideal": ideal})
    out = pd.DataFrame(rows, columns=["Driver", "Best", "S1", "S2", "S3", "Ideal"])
    out["LeftOnTable"] = out["Best"] - out["Ideal"]
    return out


def _seconds(values) -> pd.Series:
    return pd.to_timedelta(values).dt.total_seconds()


def _from_fastf1(year: int, round_number: int, kind: str) -> QualiData:
    session = load_session(year, round_number, "SS" if kind == "SQ" and year in SHOOTOUT_YEARS else kind)
    res = session.results.sort_values("Position")
    results = pd.DataFrame({
        "Position": res["Position"].to_numpy(),
        "Driver": res["Abbreviation"].to_numpy(),
        "Team": res["TeamName"].to_numpy(),
        **{q: _seconds(res[q]).to_numpy() for q in PARTS},
    })
    results["Out"] = eliminated_in(results)
    laps = pd.DataFrame(session.laps)
    laps = pd.DataFrame({
        "Driver": laps["Driver"],
        "LapNumber": laps["LapNumber"],
        "LapTime": _seconds(laps["LapTime"]),
        "S1": _seconds(laps["Sector1Time"]),
        "S2": _seconds(laps["Sector2Time"]),
        "S3": _seconds(laps["Sector3Time"]),
        "Minute": _seconds(laps["Time"]) / 60,
        "Deleted": laps["Deleted"].eq(True),
        "Compound": laps["Compound"],
    }).reset_index(drop=True)
    colors = {r.Abbreviation: f"#{r.TeamColor}" if isinstance(r.TeamColor, str) and len(r.TeamColor) == 6
              else FALLBACK_TEAM_COLOR for r in res.itertuples()}
    event = session.event
    return QualiData(name=f"{year} {event['EventName']}", event_name=event["EventName"],
                     session_name=session_name(year, kind), year=year, round_number=round_number,
                     location=event["Location"], date=session.date,
                     source="F1 live timing", results=results, laps=laps, team_colors=colors)


def _from_openf1(year: int, round_number: int, kind: str) -> QualiData:
    enable_cache()
    event = fastf1.get_event_schedule(year, include_testing=False).get_event_by_round(round_number)
    session = openf1.weekend_session(year, event["Session5DateUtc"], kind)
    sk = session["session_key"]
    drivers = pd.DataFrame(openf1.get("drivers", session_key=sk)).drop_duplicates("driver_number")
    code = dict(zip(drivers["driver_number"], drivers["name_acronym"]))
    team = dict(zip(drivers["driver_number"], drivers["team_name"]))
    colors = {code[n]: f"#{c}" if isinstance(c, str) and len(c) == 6 else FALLBACK_TEAM_COLOR
              for n, c in zip(drivers["driver_number"], drivers["team_colour"])}

    result = pd.DataFrame(openf1.get("session_result", session_key=sk))
    if result.empty:
        raise openf1.OpenF1Error("OpenF1 has no result for this session")

    def part(durations, i):
        return durations[i] if isinstance(durations, list) and len(durations) > i else np.nan

    results = pd.DataFrame({
        "Position": pd.to_numeric(result["position"], errors="coerce"),
        "Driver": result["driver_number"].map(code),
        "Team": result["driver_number"].map(team),
        **{q: pd.to_numeric(result["duration"].map(lambda d, i=i: part(d, i)), errors="coerce")
           for i, q in enumerate(PARTS)},
    }).sort_values("Position", na_position="last").reset_index(drop=True)
    results["Out"] = eliminated_in(results)

    raw = pd.DataFrame(openf1.get("laps", session_key=sk))
    if raw.empty or "lap_duration" not in raw:
        raise openf1.OpenF1Error("OpenF1 has no laps for this session")
    raw = raw[raw["lap_duration"].notna()]
    t0 = pd.Timestamp(session["date_start"])
    rc = pd.DataFrame(openf1.get("race_control", session_key=sk))
    deleted = set()
    for message in rc.get("message", pd.Series(dtype=str)).dropna():
        m = _DELETED.search(message)
        if m:
            deleted.add((int(m.group(1)), int(m.group(3))))
    laps = pd.DataFrame({
        "Driver": raw["driver_number"].map(code),
        "LapNumber": raw["lap_number"],
        "LapTime": raw["lap_duration"].astype(float),
        "S1": pd.to_numeric(raw["duration_sector_1"], errors="coerce"),
        "S2": pd.to_numeric(raw["duration_sector_2"], errors="coerce"),
        "S3": pd.to_numeric(raw["duration_sector_3"], errors="coerce"),
        "Minute": (pd.to_datetime(raw["date_start"], utc=True, format="ISO8601") - t0).dt.total_seconds() / 60
                  + raw["lap_duration"].astype(float) / 60,
        "Deleted": [(n, lap) in deleted for n, lap in zip(raw["driver_number"], raw["lap_number"])],
        "Compound": None,
    }).reset_index(drop=True)
    return QualiData(name=f"{year} {event['EventName']}", event_name=event["EventName"],
                     session_name=session_name(year, kind), year=year, round_number=round_number,
                     location=event["Location"], date=pd.Timestamp(session["date_start"]), source="OpenF1",
                     results=results, laps=laps,
                     team_colors=colors)
