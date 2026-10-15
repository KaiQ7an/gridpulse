"""Load everything the dashboard needs for one race, as plain DataFrames."""

from dataclasses import dataclass

import fastf1
import pandas as pd

from pitlens.pitwall.timing import gap_to_leader, leader_times, retired_drivers
from pitlens.radio.clips import team_radio
from pitlens.session import enable_cache, load_session
from pitlens.stints.pace import add_fuel_corrected_time, clean_race_laps
from pitlens.style import FALLBACK_TEAM_COLOR
from pitlens.undercut.analysis import pit_battles, pit_loss, pit_stops

FIRST_SEASON = 2018  # first season with full timing data in FastF1


@dataclass
class RaceData:
    name: str
    date: pd.Timestamp
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
    pit_loss: float | None  # typical green-flag pit loss, seconds
    radio: pd.DataFrame  # team radio clips with the lap they were sent on
    team_colors: dict[str, str]  # driver -> "#rrggbb"
    finish_order: list[str]
    retired: set[str]


def completed_races(year: int) -> pd.DataFrame:
    """Rounds of `year` whose race has already finished, latest last."""
    enable_cache()
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    race_start = pd.to_datetime(schedule["Session5DateUtc"], utc=True)
    done = schedule[race_start + pd.Timedelta(hours=3) < pd.Timestamp.now(tz="UTC")]
    return done[["RoundNumber", "EventName", "Location", "EventDate"]].reset_index(drop=True)


def load_race(year: int, round_number: int) -> RaceData:
    session = load_session(year, round_number, "R")
    results = session.results.sort_values("Position")
    total_laps = int(session.total_laps)

    clean = add_fuel_corrected_time(clean_race_laps(session), total_laps)

    colors = {}
    for _, row in results.iterrows():
        color = row.get("TeamColor")
        colors[row["Abbreviation"]] = f"#{color}" if isinstance(color, str) and len(color) == 6 else FALLBACK_TEAM_COLOR

    laps = pd.DataFrame(session.laps)
    stops = pit_stops(laps)
    try:
        radio = team_radio(session)
    except Exception:  # radio is a nice-to-have; the archive may not have it for every session
        radio = pd.DataFrame(columns=["Driver", "Lap", "SessionTime", "Utc", "Url"])
    return RaceData(
        name=f"{session.event.year} {session.event['EventName']}",
        date=session.event["EventDate"],
        total_laps=total_laps,
        laps=laps,
        clean_laps=clean,
        results=pd.DataFrame(results),
        messages=pd.DataFrame(session.race_control_messages),
        weather=pd.DataFrame(session.weather_data),
        gaps=gap_to_leader(laps),
        lead_times=leader_times(laps),
        stops=stops,
        battles=pit_battles(laps, stops),
        pit_loss=pit_loss(stops),
        radio=radio,
        team_colors=colors,
        finish_order=results["Abbreviation"].tolist(),
        retired=retired_drivers(results),
    )
