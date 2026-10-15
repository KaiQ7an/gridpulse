"""Load two drivers' fastest laps (with telemetry) from one session."""

from dataclasses import dataclass

import pandas as pd

from pitlens.session import load_session

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
