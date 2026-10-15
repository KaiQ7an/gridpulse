"""Load everything the dashboard needs for one race, as plain DataFrames."""

from dataclasses import dataclass

import fastf1
import pandas as pd

from pitlens.pitwall.events import lap_status, race_events
from pitlens.pitwall.timing import gap_to_leader, leader_times, retired_drivers
from pitlens.radio.clips import assign_laps, team_radio
from pitlens.session import TimingUnavailable, enable_cache, load_session
from pitlens.sources import openf1
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
    finish_order: list[str]
    retired: set[str]
    entrants: pd.DataFrame  # Driver, Team for everyone who started, even without a completed lap


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
        "results": pd.DataFrame(session.results),
        "messages": pd.DataFrame(session.race_control_messages),
        "weather": pd.DataFrame(session.weather_data),
        "radio": radio,
        "total_laps": int(session.total_laps),
        "event_name": session.event["EventName"],
        "location": session.event["Location"],
        "date": session.event["EventDate"],
        "source": "F1 live timing",
        "circuit_key": (session.session_info.get("Meeting", {}).get("Circuit") or {}).get("Key"),
    }


def _openf1_parts(year: int, round_number: int) -> dict:
    enable_cache()
    event = fastf1.get_event_schedule(year, include_testing=False).get_event_by_round(round_number)
    parts = openf1.race_parts(year, event["Session5DateUtc"])
    parts["event_name"] = event["EventName"]
    parts["location"] = event["Location"]
    parts["date"] = event["EventDate"]
    parts["radio"]["Lap"] = assign_laps(parts["radio"], parts["laps"])
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
    laps = parts["laps"]
    results = parts["results"].sort_values("Position")
    total_laps = parts["total_laps"]
    clean = add_fuel_corrected_time(clean_race_laps(laps), total_laps)

    colors = {}
    for _, row in results.iterrows():
        color = row.get("TeamColor")
        colors[row["Abbreviation"]] = f"#{color}" if isinstance(color, str) and len(color) == 6 else FALLBACK_TEAM_COLOR

    stops = pit_stops(laps)
    retired = retired_drivers(results)
    entrants = pd.DataFrame({"Driver": results["Abbreviation"], "Team": results["TeamName"]}).dropna(subset=["Driver"])
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
        gaps=gap_to_leader(laps),
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
        finish_order=results["Abbreviation"].tolist(),
        retired=retired,
        entrants=entrants,
    )
