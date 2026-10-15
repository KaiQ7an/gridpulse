"""Load everything the dashboard needs for one race, as plain DataFrames."""

from dataclasses import dataclass

import fastf1
import pandas as pd

from pitlens.pitwall.events import lap_status, race_events
from pitlens.pitwall.timing import (
    classify_finish,
    complete_final_laps,
    gap_to_leader,
    leader_times,
    non_starters,
    retired_drivers,
)
from pitlens.radio.clips import assign_laps, team_radio
from pitlens.session import TimingUnavailable, enable_cache, load_session
from pitlens.sources import openf1, weather
from pitlens.stints.pace import add_fuel_corrected_time, clean_race_laps
from pitlens.style import FALLBACK_TEAM_COLOR
from pitlens.undercut.analysis import pit_battles, pit_loss, pit_stops

FIRST_SEASON = 2018  # first season with full timing data in FastF1


@dataclass
class RaceData:
    name: str
    event_name: str
    year: int
    round_number: int
    location: str
    date: pd.Timestamp
    source: str  # "F1 live timing" or "OpenF1"
    total_laps: int
    laps: pd.DataFrame  # every lap, all drivers
    clean_laps: pd.DataFrame  # representative laps with fuel-corrected time
    results: pd.DataFrame
    messages: pd.DataFrame
    weather: pd.DataFrame
    gaps: pd.DataFrame  # seconds behind the leader, every driver, every lap
    lead_times: pd.Series  # session time the leader completed each lap
    stops: pd.DataFrame  # every pit stop with its cost
    battles: pd.DataFrame  # undercut / overcut attempts
    pit_loss: float | None  # typical green-flag pit loss over the whole race, seconds
    pit_loss_ref: dict | None  # circuit reference pit loss: normal / vsc / sc
    radio: pd.DataFrame  # team radio clips with the lap they were sent on
    events: pd.DataFrame  # race feed: pits, passes, fastest laps, safety cars
    lap_status: pd.Series  # track status per lap: Green, Yellow, Safety car, VSC, Red flag
    team_colors: dict[str, str]  # driver -> "#rrggbb"
    first_names: dict[str, str]  # driver -> first name, e.g. "VER" -> "Max"
    full_names: dict[str, str]  # driver -> full name, e.g. "VER" -> "Max Verstappen"
    last_names: dict[str, str]  # driver -> surname, e.g. "VER" -> "Verstappen"
    finish_order: list[str]
    retired: set[str]
    entrants: pd.DataFrame  # Driver, Team for everyone who started, even without a completed lap
    track: dict | None  # circuit outline split into the three timing sectors
    rain_mm: pd.Series | None  # hourly rainfall at the circuit (Open-Meteo estimate), indexed by UTC hour
    start_utc: pd.Timestamp | None  # scheduled race start, for turning laps into clock time


def completed_races(year: int) -> pd.DataFrame:
    """Rounds of `year` whose race has already finished, latest last."""
    enable_cache()
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    race_start = pd.to_datetime(schedule["Session5DateUtc"], utc=True)
    done = schedule[race_start + pd.Timedelta(hours=3) < pd.Timestamp.now(tz="UTC")]
    return done[["RoundNumber", "EventName", "Location", "EventDate"]].reset_index(drop=True)


def _fastf1_parts(year: int, round_number: int) -> dict:
    session = load_session(year, round_number, "R")
    try:
        radio = team_radio(session)
    except Exception:  # radio is a nice-to-have; the archive may not have it for every session
        radio = pd.DataFrame(columns=["Driver", "Lap", "SessionTime", "Utc", "Url"])
    return {
        "laps": pd.DataFrame(session.laps),
        "stationary": _stationary(year, session),
        "results": pd.DataFrame(session.results),
        "messages": pd.DataFrame(session.race_control_messages),
        "weather": pd.DataFrame(session.weather_data),
        "radio": radio,
        "total_laps": int(session.total_laps),
        "event_name": session.event["EventName"],
        "location": session.event["Location"],
        "date": session.event["EventDate"],
        "source": "F1 live timing",
        "race_utc": session.date,
        "circuit_key": (session.session_info.get("Meeting", {}).get("Circuit") or {}).get("Key"),
    }


def _stationary(year: int, session) -> pd.DataFrame | None:
    """Stationary pit stop times from OpenF1 (F1's archive doesn't carry them; OpenF1 starts in 2023)."""
    if year < openf1.FIRST_SEASON:
        return None
    numbers = dict(zip(pd.to_numeric(session.results["DriverNumber"], errors="coerce"), session.results["Abbreviation"]))
    try:
        return openf1.stationary_times(year, session.date, numbers)
    except Exception:  # optional extra: offline, rate-limited, or OpenF1 doesn't have the race
        return None


def _openf1_parts(year: int, round_number: int) -> dict:
    enable_cache()
    event = fastf1.get_event_schedule(year, include_testing=False).get_event_by_round(round_number)
    parts = openf1.race_parts(year, event["Session5DateUtc"])
    parts["event_name"] = event["EventName"]
    parts["location"] = event["Location"]
    parts["date"] = event["EventDate"]
    parts["radio"]["Lap"] = assign_laps(parts["radio"], parts["laps"])
    parts["race_utc"] = event["Session5DateUtc"]
    return parts


def load_race(year: int, round_number: int) -> RaceData:
    """One race from F1's archive, or from OpenF1 when the archive won't serve it."""
    try:
        parts = _fastf1_parts(year, round_number)
    except TimingUnavailable as archive_error:
        try:
            parts = _openf1_parts(year, round_number)
        except openf1.OpenF1Error as exc:
            raise TimingUnavailable(f"{archive_error} OpenF1 couldn't provide it either: {exc}") from None
    return build_race(year, round_number, parts)


def build_race(year: int, round_number: int, parts: dict) -> RaceData:
    results = parts["results"].sort_values("Position")
    total_laps = parts["total_laps"]
    laps = classify_finish(complete_final_laps(parts["laps"], results, total_laps), results, total_laps)
    clean = add_fuel_corrected_time(clean_race_laps(laps), total_laps)

    colors = {}
    for _, row in results.iterrows():
        color = row.get("TeamColor")
        colors[row["Abbreviation"]] = f"#{color}" if isinstance(color, str) and len(color) == 6 else FALLBACK_TEAM_COLOR

    stops = pit_stops(laps, parts.get("stationary"))
    retired = retired_drivers(results)
    started = results[~non_starters(results)]  # a car that never took the start isn't in the running order
    entrants = pd.DataFrame({"Driver": started["Abbreviation"], "Team": started["TeamName"]}).dropna(subset=["Driver"])
    return RaceData(
        name=f"{year} {parts['event_name']}",
        event_name=parts["event_name"],
        year=year,
        round_number=round_number,
        location=parts["location"],
        date=parts["date"],
        source=parts["source"],
        total_laps=total_laps,
        laps=laps,
        clean_laps=clean,
        results=results,
        messages=parts["messages"],
        weather=parts["weather"],
        gaps=official_finish_gaps(gap_to_leader(laps), laps, total_laps),
        lead_times=leader_times(laps),
        stops=stops,
        battles=pit_battles(laps, stops),
        pit_loss=pit_loss(stops),
        pit_loss_ref=openf1.circuit_pit_loss(parts["circuit_key"], year) if parts.get("circuit_key") else None,
        radio=parts["radio"],
        events=race_events(laps, retired, total_laps, entrants),
        lap_status=lap_status(laps),
        team_colors=colors,
        first_names=dict(zip(results["Abbreviation"], results["FirstName"])) if "FirstName" in results else {},
        full_names=dict(zip(results["Abbreviation"], results["FullName"])) if "FullName" in results else {},
        last_names=dict(zip(results["Abbreviation"], results["LastName"])) if "LastName" in results else {},
        finish_order=results["Abbreviation"].tolist(),
        retired=retired,
        entrants=entrants,
        track=_track(year, parts),
        rain_mm=weather.hourly_rain(parts["location"], parts.get("race_utc")),
        start_utc=pd.Timestamp(parts["race_utc"]) if parts.get("race_utc") is not None else None,
    )


def official_finish_gaps(gaps: pd.DataFrame, laps: pd.DataFrame, total_laps: int) -> pd.DataFrame:
    """The race trace with the official gaps at the flag (see `classify_finish`)."""
    if "OfficialGap" not in laps:
        return gaps
    official = laps[laps["LapNumber"] == total_laps].set_index("Driver")["OfficialGap"].dropna()
    final = (gaps["LapNumber"] == total_laps) & gaps["Driver"].isin(official.index)
    gaps = gaps.copy()
    gaps.loc[final, "Gap"] = gaps.loc[final, "Driver"].map(official)
    return gaps


def lap_clock(race: "RaceData", lap: int) -> pd.Timestamp | None:
    """Approximate UTC time the leader finished `lap`: race start plus the elapsed race time."""
    if race.start_utc is None or lap not in race.lead_times.index:
        return None
    first = race.lead_times.index.min()
    lap1 = race.laps[(race.laps["LapNumber"] == first)]["LapTime"].dropna()
    race_start = race.lead_times[first] - (lap1.min() if not lap1.empty else pd.Timedelta(0))
    return race.start_utc + (race.lead_times[lap] - race_start)


def _track(year: int, parts: dict) -> dict | None:
    try:
        return openf1.track_outline(year, parts.get("race_utc"), parts.get("circuit_key"))
    except Exception:  # the map is optional; never let it stop a race from loading
        return None
