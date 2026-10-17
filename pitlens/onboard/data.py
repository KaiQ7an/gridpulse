"""Load two drivers' fastest laps (with telemetry) from one session."""

import re
from dataclasses import dataclass

import fastf1
import pandas as pd
from fastf1.exceptions import DataNotLoadedError

from pitlens import snapshots
from pitlens.deploy import hosted
from pitlens.onboard.compare import corner_distances
from pitlens.session import TimingUnavailable, enable_cache, load_session, refused_recently, remember_refusal
from pitlens.sources import openf1
from pitlens.style import FALLBACK_TEAM_COLOR

SESSION_NAMES = {
    "Q": "Qualifying",
    "R": "Race",
    "SQ": "Sprint Qualifying",
    "S": "Sprint",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
}

def team_color(value) -> str:
    """Use this session's team colour; missing metadata gets a neutral fallback."""
    color = str(value).strip().lstrip("#")
    return f"#{color.upper()}" if re.fullmatch(r"[0-9a-fA-F]{6}", color) else FALLBACK_TEAM_COLOR


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
    team_color: str = FALLBACK_TEAM_COLOR


@dataclass
class OnboardData:
    name: str
    session_name: str
    ref: DriverLap
    other: DriverLap
    corners: pd.DataFrame
    rotation: float
    source: str = "F1 live timing"

    @property
    def colors(self) -> tuple[str, str]:
        return team_color(self.ref.team_color), team_color(self.other.team_color)

    @property
    def dashes(self) -> tuple[str, str]:
        return "solid", "dash" if self.ref.team == self.other.team or self.colors[0] == self.colors[1] else "solid"

    @property
    def labels(self) -> tuple[str, str]:
        return tuple(f"{lap.driver} · L{lap.lap_number}" for lap in (self.ref, self.other))


def session_drivers(session) -> pd.DataFrame:
    """Drivers in classification order with their team, for pickers."""
    res = session.results.sort_values("Position")
    return pd.DataFrame({"Driver": res["Abbreviation"], "Team": res["TeamName"],
                         "FullName": res.get("FullName", res["Abbreviation"])}).reset_index(drop=True)


def teammate_of(drivers: pd.DataFrame, driver: str) -> str | None:
    team = drivers.loc[drivers["Driver"] == driver, "Team"]
    if team.empty:
        return None
    mates = drivers[(drivers["Team"] == team.iloc[0]) & (drivers["Driver"] != driver)]
    return mates["Driver"].iloc[0] if not mates.empty else None


def fastest_lap(session, driver: str, lap_number: int | None = None) -> DriverLap:
    mine = session.laps.pick_drivers(driver)
    if lap_number is None:
        lap = mine.pick_fastest()
    else:
        selected = mine[(mine["LapNumber"] == lap_number) & mine["LapTime"].notna()]
        if "Deleted" in selected:
            selected = selected[~selected["Deleted"].eq(True)]
        if selected.empty:
            raise ValueError(f"{driver} lap {lap_number} has no valid lap time in this session")
        lap = selected.iloc[0]
    if lap is None or pd.isna(lap["LapTime"]):
        raise ValueError(f"{driver} has no timed lap in this session")
    tel = lap.get_telemetry()
    result = session.results[session.results["Abbreviation"] == driver]
    color = result["TeamColor"].iloc[0] if "TeamColor" in result and not result.empty else None
    return DriverLap(
        driver=driver,
        team=lap["Team"],
        lap_time=lap["LapTime"],
        sectors=(lap["Sector1Time"], lap["Sector2Time"], lap["Sector3Time"]),
        compound=lap["Compound"] if isinstance(lap["Compound"], str) else "UNKNOWN",
        tyre_life=lap["TyreLife"],
        lap_number=int(lap["LapNumber"]),
        telemetry=pd.DataFrame(tel[["Time", "Distance", "Speed", "Throttle", "Brake", "nGear", "DRS", "X", "Y"]]),
        team_color=team_color(color),
    )


def load_session_with_telemetry(year: int, event, kind: str):
    return load_session(year, event, kind, telemetry=True)


def compare(session, ref_driver: str, other_driver: str, ref_lap: int | None = None,
            other_lap: int | None = None) -> OnboardData:
    info = session.get_circuit_info()
    return OnboardData(
        name=f"{session.event.year} {session.event['EventName']}",
        session_name=session.name,
        ref=fastest_lap(session, ref_driver, ref_lap),
        other=fastest_lap(session, other_driver, other_lap),
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
        drivers = session_drivers(self.session).set_index("Driver")
        team = drivers["Team"]
        laps = self.session.laps.dropna(subset=["LapTime"])
        if "IsPersonalBest" in laps and laps["IsPersonalBest"].eq(True).any():
            laps = laps[laps["IsPersonalBest"].eq(True)]  # the laps pick_fastest chooses from: no deleted laps
        best = laps.groupby("Driver")["LapTime"].min().sort_values()
        return pd.DataFrame({"Driver": best.index, "Team": best.index.map(team),
                             "FullName": best.index.map(drivers["FullName"])}).reset_index(drop=True)

    def lap_options(self, driver: str) -> pd.DataFrame:
        laps = self.session.laps.pick_drivers(driver).dropna(subset=["LapTime"])
        if "Deleted" in laps:
            laps = laps[~laps["Deleted"].eq(True)]
        if "PitOutTime" in laps:
            laps = laps[laps["PitOutTime"].isna()]
        return pd.DataFrame({"Lap": laps["LapNumber"].astype(int), "LapTime": laps["LapTime"],
                             "Compound": laps["Compound"], "TyreLife": laps["TyreLife"]}).sort_values("Lap")

    def compare(self, ref: str, other: str, ref_lap: int | None = None,
                other_lap: int | None = None) -> OnboardData:
        try:
            return compare(self.session, ref, other, ref_lap, other_lap)
        except (KeyError, DataNotLoadedError):
            if ref_lap is not None or other_lap is not None:
                raise ValueError("The archive has no telemetry for one of the selected laps. Choose another lap.") from None
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
        valid = self.laps[~self.laps["Deleted"]] if "Deleted" in self.laps else self.laps
        best = valid.sort_values("lap_duration").drop_duplicates("driver_number")
        return pd.DataFrame({"Driver": best["name_acronym"], "Team": best["team_name"],
                             "FullName": best.get("full_name", best["name_acronym"])}).reset_index(drop=True)

    def fastest_lap(self, driver: str) -> DriverLap:
        return self.lap(driver)

    def lap_options(self, driver: str) -> pd.DataFrame:
        mine = self.laps[self.laps["name_acronym"] == driver].copy()
        if "Deleted" in mine:
            mine = mine[~mine["Deleted"]]
        compounds, ages = [], []
        for row in mine.itertuples():
            compound, age = self.tyre_info(row.driver_number, row.lap_number)
            compounds.append(compound)
            ages.append(age)
        return pd.DataFrame({"Lap": mine["lap_number"].astype(int),
                             "LapTime": pd.to_timedelta(mine["lap_duration"], unit="s"),
                             "Compound": compounds, "TyreLife": ages}).sort_values("Lap")

    def tyre_info(self, driver_number: int, lap_number: int) -> tuple[str, float]:
        stints = self.stints[self.stints["driver_number"] == driver_number] if not self.stints.empty else self.stints
        for stint in stints.itertuples():
            if stint.lap_start <= lap_number <= stint.lap_end:
                age = stint.tyre_age_at_start
                return stint.compound, age + lap_number - stint.lap_start + 1 if pd.notna(age) else float("nan")
        return "UNKNOWN", float("nan")

    def lap(self, driver: str, lap_number: int | None = None) -> DriverLap:
        mine = self.laps[self.laps["name_acronym"] == driver]
        if "Deleted" in mine:
            mine = mine[~mine["Deleted"]]
        if lap_number is not None:
            mine = mine[mine["lap_number"] == lap_number]
        if mine.empty:
            label = f" lap {lap_number}" if lap_number is not None else ""
            raise ValueError(f"{driver}{label} has no valid timed lap in this session")
        lap = mine.loc[mine["lap_duration"].idxmin()]
        compound, age = self.tyre_info(lap["driver_number"], lap["lap_number"])
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
            team_color=team_color(lap.get("team_colour")),
        )

    def compare(self, ref: str, other: str, ref_lap: int | None = None,
                other_lap: int | None = None) -> OnboardData:
        ref_lap, other_lap = self.lap(ref, ref_lap), self.lap(other, other_lap)
        corners, rotation = openf1.circuit_info(self.session["circuit_key"], self.year)
        corners["Distance"] = corner_distances(corners, ref_lap.telemetry)
        return OnboardData(name=self.name, session_name=self.session_name, ref=ref_lap, other=other_lap,
                           corners=corners.sort_values("Distance").reset_index(drop=True), rotation=rotation,
                           source=self.source)


def load_weekend(year: int, round_number: int, kind: str):
    """F1's archive (with car telemetry) if it answers, otherwise OpenF1."""
    if snapshots.offline():
        raise TimingUnavailable("Onboard laps aren't saved with the snapshots, and GridPulse is running offline.")
    key = f"{year}-{round_number}-{kind}"
    archive_error = TimingUnavailable(f"F1's live-timing archive refused {year} round {round_number} recently.")
    # On a public server the archive's telemetry (about 100 MB a session) is too heavy when OpenF1
    # can serve just the two laps compared.
    light = hosted() and year >= openf1.FIRST_SEASON
    if not light and not refused_recently(key):
        try:
            return FastF1Weekend(load_session_with_telemetry(year, round_number, kind), year, round_number, kind)
        except TimingUnavailable as exc:
            archive_error = exc
            remember_refusal(key)
    try:
        return OpenF1Weekend(year, round_number, kind)
    except openf1.OpenF1Error as exc:
        raise TimingUnavailable(f"{archive_error} OpenF1 couldn't provide it either: {exc}") from None
