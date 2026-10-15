"""Load two drivers' fastest laps (with telemetry) from one session."""

from dataclasses import dataclass

import fastf1
import pandas as pd
from fastf1.exceptions import DataNotLoadedError

from pitlens.onboard.compare import corner_distances
from pitlens.session import TimingUnavailable, enable_cache, load_session, refused_recently, remember_refusal
from pitlens.sources import openf1

SESSION_NAMES = {
    "Q": "Qualifying",
    "R": "Race",
    "SQ": "Sprint Qualifying",
    "S": "Sprint",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
}

# Fixed comparison colours (first driver blue, second orange). They pass the
# colour-blind and contrast checks on light and dark backgrounds, and unlike
# team colours they still differ when the two drivers are teammates.
REF_COLOR = "#2F6FDE"
OTHER_COLOR = "#E8590C"


@dataclass
class DriverLap:
    driver: str
    team: str
    lap_time: pd.Timedelta
    sectors: tuple[pd.Timedelta, pd.Timedelta, pd.Timedelta]
    compound: str
    tyre_life: float
    lap_number: int
    telemetry: pd.DataFrame


@dataclass
class OnboardData:
    name: str
    session_name: str
    ref: DriverLap
    other: DriverLap
    corners: pd.DataFrame
    rotation: float
    source: str = "F1 live timing"


def session_drivers(session) -> pd.DataFrame:
    """Drivers in classification order with their team, for pickers."""
    res = session.results.sort_values("Position")
    return pd.DataFrame({"Driver": res["Abbreviation"], "Team": res["TeamName"]}).reset_index(drop=True)


def teammate_of(drivers: pd.DataFrame, driver: str) -> str | None:
    team = drivers.loc[drivers["Driver"] == driver, "Team"]
    if team.empty:
        return None
    mates = drivers[(drivers["Team"] == team.iloc[0]) & (drivers["Driver"] != driver)]
    return mates["Driver"].iloc[0] if not mates.empty else None


def fastest_lap(session, driver: str) -> DriverLap:
    lap = session.laps.pick_drivers(driver).pick_fastest()
    if lap is None or pd.isna(lap["LapTime"]):
        raise ValueError(f"{driver} has no timed lap in this session")
    tel = lap.get_telemetry()
    return DriverLap(
        driver=driver,
        team=lap["Team"],
        lap_time=lap["LapTime"],
        sectors=(lap["Sector1Time"], lap["Sector2Time"], lap["Sector3Time"]),
        compound=lap["Compound"] if isinstance(lap["Compound"], str) else "UNKNOWN",
        tyre_life=lap["TyreLife"],
        lap_number=int(lap["LapNumber"]),
        telemetry=pd.DataFrame(tel[["Time", "Distance", "Speed", "Throttle", "Brake", "nGear", "DRS", "X", "Y"]]),
    )


def load_session_with_telemetry(year: int, event, kind: str):
    return load_session(year, event, kind, telemetry=True)


def compare(session, ref_driver: str, other_driver: str) -> OnboardData:
    info = session.get_circuit_info()
    return OnboardData(
        name=f"{session.event.year} {session.event['EventName']}",
        session_name=session.name,
        ref=fastest_lap(session, ref_driver),
        other=fastest_lap(session, other_driver),
        corners=pd.DataFrame(info.corners),
        rotation=float(info.rotation),
    )


class FastF1Weekend:
    """A FastF1 session behind the small interface the onboard page and report use."""

    def __init__(self, session, year: int, round_number: int, kind: str):
        self.session = session
        self.name = f"{session.event.year} {session.event['EventName']}"
        self.session_name = session.name
        self.source = "F1 live timing"
        self._where = (year, round_number, kind)
        self._openf1 = None

    def drivers(self) -> pd.DataFrame:
        """Drivers with a timed lap, fastest first (in a race that isn't the classification order)."""
        team = session_drivers(self.session).set_index("Driver")["Team"]
        laps = self.session.laps.dropna(subset=["LapTime"])
        if "IsPersonalBest" in laps and laps["IsPersonalBest"].eq(True).any():
            laps = laps[laps["IsPersonalBest"].eq(True)]  # the laps pick_fastest chooses from: no deleted laps
        best = laps.groupby("Driver")["LapTime"].min().sort_values()
        return pd.DataFrame({"Driver": best.index, "Team": best.index.map(team)}).reset_index(drop=True)

    def compare(self, ref: str, other: str) -> OnboardData:
        try:
            return compare(self.session, ref, other)
        except (KeyError, DataNotLoadedError):
            # The archive sometimes has a session's laps but not every car's telemetry.
            year = self._where[0]
            if year < openf1.FIRST_SEASON:
                raise ValueError(f"F1's archive has no car telemetry for {ref} or {other} in this session") from None
            if self._openf1 is None:
                self._openf1 = OpenF1Weekend(*self._where)
            return self._openf1.compare(ref, other)


class OpenF1Weekend:
    """The same interface, fed from OpenF1 when F1's archive won't serve the session."""

    def __init__(self, year: int, round_number: int, kind: str):
        enable_cache()
        event = fastf1.get_event_schedule(year, include_testing=False).get_event_by_round(round_number)
        self.year = year
        self.session = openf1.weekend_session(year, event["Session5DateUtc"], kind)
        self.laps = openf1.session_laps(self.session["session_key"])
        self.stints = pd.DataFrame(openf1.get("stints", session_key=self.session["session_key"]))
        self.name = f"{year} {event['EventName']}"
        self.session_name = openf1.ONBOARD_SESSION_NAMES[kind]
        self.source = "OpenF1"

    def drivers(self) -> pd.DataFrame:
        best = self.laps.sort_values("lap_duration").drop_duplicates("driver_number")
        return pd.DataFrame({"Driver": best["name_acronym"], "Team": best["team_name"]}).reset_index(drop=True)

    def fastest_lap(self, driver: str) -> DriverLap:
        mine = self.laps[self.laps["name_acronym"] == driver]
        if mine.empty:
            raise ValueError(f"{driver} has no timed lap in this session")
        lap = mine.loc[mine["lap_duration"].idxmin()]
        compound, age = "UNKNOWN", float("nan")
        st = self.stints[(self.stints.get("driver_number") == lap["driver_number"])] if not self.stints.empty else self.stints
        for s in st.itertuples():
            if s.lap_start <= lap["lap_number"] <= s.lap_end:
                compound, age = s.compound, (s.tyre_age_at_start or 0) + lap["lap_number"] - s.lap_start + 1
        sec = lambda k: pd.to_timedelta(lap[k], unit="s") if pd.notna(lap[k]) else pd.NaT  # noqa: E731
        return DriverLap(
            driver=driver,
            team=lap["team_name"],
            lap_time=pd.to_timedelta(lap["lap_duration"], unit="s"),
            sectors=(sec("duration_sector_1"), sec("duration_sector_2"), sec("duration_sector_3")),
            compound=compound,
            tyre_life=age,
            lap_number=int(lap["lap_number"]),
            telemetry=openf1.lap_telemetry(
                self.session["session_key"], int(lap["driver_number"]), lap["date_start"], float(lap["lap_duration"])
            ),
        )

    def compare(self, ref: str, other: str) -> OnboardData:
        ref_lap, other_lap = self.fastest_lap(ref), self.fastest_lap(other)
        corners, rotation = openf1.circuit_info(self.session["circuit_key"], self.year)
        corners["Distance"] = corner_distances(corners, ref_lap.telemetry)
        return OnboardData(name=self.name, session_name=self.session_name, ref=ref_lap, other=other_lap,
                           corners=corners.sort_values("Distance").reset_index(drop=True), rotation=rotation,
                           source=self.source)


def load_weekend(year: int, round_number: int, kind: str):
    """F1's archive (with car telemetry) if it answers, otherwise OpenF1."""
    key = f"{year}-{round_number}-{kind}"
    archive_error = TimingUnavailable(f"F1's live-timing archive refused {year} round {round_number} recently.")
    if not refused_recently(key):
        try:
            return FastF1Weekend(load_session_with_telemetry(year, round_number, kind), year, round_number, kind)
        except TimingUnavailable as exc:
            archive_error = exc
            remember_refusal(key)
    try:
        return OpenF1Weekend(year, round_number, kind)
    except openf1.OpenF1Error as exc:
        raise TimingUnavailable(f"{archive_error} OpenF1 couldn't provide it either: {exc}") from None
