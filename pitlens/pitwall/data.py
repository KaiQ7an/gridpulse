"""Load everything the dashboard needs for one race, as plain DataFrames."""

from dataclasses import dataclass

import fastf1
import pandas as pd

from pitlens import snapshots
from pitlens.pitwall.events import lap_status, race_events
from pitlens.pitwall.timing import (
    classify_finish,
    complete_final_laps,
    gap_to_leader,
    lap_coverage,
    leader_times,
    non_starters,
    retired_drivers,
    trim_to_classified_laps,
)
from pitlens.radio.clips import assign_laps, team_radio
from pitlens.session import (
    ResultsUnavailable,
    TimingUnavailable,
    enable_cache,
    load_session,
    refused_recently,
    remember_refusal,
)
from pitlens.sources import openf1, weather
from pitlens.stints.pace import add_fuel_corrected_time, clean_race_laps
from pitlens.style import FALLBACK_TEAM_COLOR
from pitlens.undercut.analysis import pit_battles, pit_loss, pit_stops

FIRST_SEASON = 2018  # first season with full timing data in FastF1
SESSIONS = {"R": "Race", "S": "Sprint"}  # the sessions the pit wall replays


@dataclass
class RaceData:
    name: str
    event_name: str
    session_name: str  # "Race" or "Sprint"
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
    coverage: float | None  # share of the race's laps the timing data has
    start_utc: pd.Timestamp | None  # scheduled race start, for turning laps into clock time

    def clean_through(self, lap: int) -> pd.DataFrame:
        """Clean only the known laps: later fastest laps must not change today's outlier cut."""
        known = self.laps[self.laps["LapNumber"] <= lap]
        return add_fuel_corrected_time(clean_race_laps(known), self.total_laps)

    def stops_through(self, lap: int) -> pd.DataFrame:
        """Known stops, with measurements withheld until the out-lap is complete."""
        known = self.stops[self.stops["Lap"] <= lap].copy()
        pending = known["Lap"] == lap
        for column in ("LaneTime", "Stationary", "Loss", "PosAfter"):
            known.loc[pending, column] = float("nan")
        return known


def completed_races(year: int) -> pd.DataFrame:
    """Rounds of `year` whose race has already finished, latest last (the saved ones when offline or
    when the schedule can't be fetched)."""
    if snapshots.offline():
        return snapshots.races(year)
    enable_cache()
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
    except Exception:  # no network, or the schedule API is down: offer what's saved
        return snapshots.races(year)
    race_start = pd.to_datetime(schedule["Session5DateUtc"], utc=True)
    done = schedule[race_start + pd.Timedelta(hours=3) < pd.Timestamp.now(tz="UTC")]
    return done[["RoundNumber", "EventName", "Location", "EventDate", "EventFormat"]].reset_index(drop=True)


def _fastf1_parts(year: int, round_number: int, kind: str = "R") -> dict:
    session = load_session(year, round_number, kind)
    try:
        radio = team_radio(session)
    except Exception:  # radio is a nice-to-have; the archive may not have it for every session
        radio = _openf1_radio(year, session, SESSIONS[kind])
    return {
        "laps": pd.DataFrame(session.laps),
        "stationary": _stationary(year, session, SESSIONS[kind]),
        "results": _fastf1_results(year, session, SESSIONS[kind]),
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


def _fastf1_results(year: int, session, session_name: str = "Race") -> pd.DataFrame:
    """The session's results. FastF1 takes the classification (positions, statuses, laps) from the
    Ergast/Jolpica API; when that times out the columns come back empty and the race would be built
    wrong (every lapped car looking retired). Fill them from OpenF1, or fail so the next load retries."""
    results = pd.DataFrame(session.results)
    statuses = results["Status"].fillna("").astype(str).str.strip()
    if results["Position"].eq(1).any() and statuses.ne("").mean() > 0.5:  # missing ones can be empty strings
        return results
    if year >= openf1.FIRST_SEASON:
        try:
            official = openf1.classification(year, session.date, session_name).set_index("DriverNumber")
        except openf1.OpenF1Error:
            official = None
        if official is not None:
            numbers = results["DriverNumber"].astype(str)
            for col in ("Position", "Status", "Laps"):
                results[col] = numbers.map(official[col]).values
            results["GapToLeader"] = numbers.map(official["GapToLeader"]).values
            return results
    raise ResultsUnavailable(f"The classification for {session.event['EventName']} didn't load (the results API "
                             "didn't answer). Try again in a minute.")


def _openf1_radio(year: int, session, session_name: str = "Race") -> pd.DataFrame:
    """Radio clips from OpenF1, placed on laps by F1's session clock, when the archive won't serve them."""
    empty = pd.DataFrame(columns=["Driver", "Lap", "SessionTime", "Utc", "Url"])
    if year < openf1.FIRST_SEASON:
        return empty
    numbers = dict(zip(pd.to_numeric(session.results["DriverNumber"], errors="coerce"), session.results["Abbreviation"]))
    try:
        clips = openf1.team_radio(year, session.date, numbers, session_name)
        laps = pd.DataFrame(session.laps)
        # Session clock zero in UTC: OpenF1's lap start (UTC) minus the archive's (session clock), lap by lap.
        starts = openf1.lap_starts(year, session.date, session_name)
        matched = laps.merge(starts, on=["DriverNumber", "LapNumber"])
        zero = (matched["Utc"] - matched["LapStartTime"]).median()
        clips["SessionTime"] = clips["Utc"].dt.tz_convert(None) - zero
        clips["Lap"] = assign_laps(clips, laps)
    except Exception:  # optional extra, like the archive's own radio
        return empty
    return clips[["Driver", "Lap", "SessionTime", "Utc", "Url"]].sort_values("SessionTime").reset_index(drop=True)


def _stationary(year: int, session, session_name: str = "Race") -> pd.DataFrame | None:
    """Stationary pit stop times from OpenF1 (F1's archive doesn't carry them; OpenF1 starts in 2023)."""
    if year < openf1.FIRST_SEASON:
        return None
    numbers = dict(zip(pd.to_numeric(session.results["DriverNumber"], errors="coerce"), session.results["Abbreviation"]))
    try:
        return openf1.stationary_times(year, session.date, numbers, session_name)
    except Exception:  # optional extra: offline, rate-limited, or OpenF1 doesn't have the race
        return None


def _openf1_parts(year: int, round_number: int, kind: str = "R") -> dict:
    enable_cache()
    event = fastf1.get_event_schedule(year, include_testing=False).get_event_by_round(round_number)
    start = event.get_session_date(SESSIONS[kind], utc=True)
    parts = openf1.race_parts(year, start, SESSIONS[kind])
    parts["event_name"] = event["EventName"]
    parts["location"] = event["Location"]
    parts["date"] = event["EventDate"]
    parts["radio"]["Lap"] = assign_laps(parts["radio"], parts["laps"])
    parts["race_utc"] = start
    return parts


def load_race(year: int, round_number: int, kind: str = "R") -> RaceData:
    """One race (or, with kind="S", the sprint): from a snapshot if there is one, else from F1's
    archive, or from OpenF1 when the archive won't serve it."""
    parts = snapshots.load_race(year, round_number, kind)
    if parts is None and snapshots.offline():
        raise TimingUnavailable(f"No saved copy of {year} round {round_number}, and PitLens is running offline.")
    if parts is None:
        parts = fetch_race_parts(year, round_number, kind)
    return build_race(year, round_number, parts)


def fetch_race_parts(year: int, round_number: int, kind: str = "R") -> dict:
    """A race's parts from the data sources (not a snapshot)."""
    key = f"{year}-{round_number}-{kind}"
    archive_error = TimingUnavailable(f"F1's live-timing archive refused {year} round {round_number} recently.")
    parts = None
    if not refused_recently(key):
        try:
            parts = _fastf1_parts(year, round_number, kind)
        except ResultsUnavailable:
            raise  # the archive answered; only the results API didn't, so just try again later
        except TimingUnavailable as exc:
            archive_error = exc
            remember_refusal(key)
    if parts is None:
        try:
            parts = _openf1_parts(year, round_number, kind)
        except openf1.OpenF1Error as exc:
            raise TimingUnavailable(f"{archive_error} OpenF1 couldn't provide it either: {exc}") from None
    parts["session_name"] = SESSIONS[kind]
    return parts


def with_extras(year: int, parts: dict) -> dict:
    """Fetch what building a race would otherwise fetch (map, pit loss, rainfall), for a snapshot."""
    return {**parts, "track": _track(year, parts), "pit_loss_ref": _pit_loss_ref(year, parts),
            "rain_mm": weather.hourly_rain(parts["location"], parts.get("race_utc"))}


def _pit_loss_ref(year: int, parts: dict) -> dict | None:
    return openf1.circuit_pit_loss(parts["circuit_key"], year) if parts.get("circuit_key") else None


def build_race(year: int, round_number: int, parts: dict) -> RaceData:
    results = parts["results"].sort_values("Position")
    total_laps = race_distance(parts["total_laps"], results, parts["laps"])
    laps = trim_to_classified_laps(parts["laps"], results)
    laps = classify_finish(complete_final_laps(laps, results, total_laps), results, total_laps)
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
        name=f"{year} {parts['event_name']}" + (" Sprint" if parts.get("session_name") == "Sprint" else ""),
        event_name=parts["event_name"],
        session_name=parts.get("session_name", "Race"),
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
        pit_loss_ref=parts["pit_loss_ref"] if "pit_loss_ref" in parts else _pit_loss_ref(year, parts),
        radio=parts["radio"],
        events=race_events(laps, retired, total_laps, entrants, stops),
        lap_status=lap_status(laps),
        team_colors=colors,
        first_names=dict(zip(results["Abbreviation"], results["FirstName"])) if "FirstName" in results else {},
        full_names=dict(zip(results["Abbreviation"], results["FullName"])) if "FullName" in results else {},
        last_names=dict(zip(results["Abbreviation"], results["LastName"])) if "LastName" in results else {},
        finish_order=results["Abbreviation"].tolist(),
        retired=retired,
        entrants=entrants,
        track=parts["track"] if "track" in parts else _track(year, parts),
        rain_mm=parts["rain_mm"] if "rain_mm" in parts else weather.hourly_rain(parts["location"], parts.get("race_utc")),
        coverage=lap_coverage(laps, results),
        start_utc=pd.Timestamp(parts["race_utc"]) if parts.get("race_utc") is not None else None,
    )


def race_distance(scheduled: int, results: pd.DataFrame, laps: pd.DataFrame) -> int:
    """Laps the race actually ran: the winner's, which is fewer than scheduled when the race is cut
    short (2022 Monaco hit the time limit after 64 of 78 laps; FastF1's total is the scheduled one)."""
    run = results["Laps"].max() if "Laps" in results else float("nan")
    if pd.isna(run) or run <= 0:
        run = laps["LapNumber"].max()
    return int(min(scheduled, run)) if pd.notna(run) else int(scheduled)


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
        return openf1.track_outline(year, parts.get("race_utc"), parts.get("circuit_key"),
                                    parts.get("session_name", "Race"))
    except Exception:  # the map is optional; never let it stop a race from loading
        return None
