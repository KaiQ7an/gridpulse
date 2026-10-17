"""Circuits across seasons: every saved Grand Prix at a track, year by year.

Circuits are matched by OpenF1's circuit key, not the location name, which the feeds spell
differently from one year to the next (Monaco and Monte Carlo are the same track).
"""

import unicodedata
from collections import Counter

import numpy as np
import pandas as pd

from gridpulse import snapshots
from gridpulse.pitwall.data import race_distance
from gridpulse.pitwall.events import fastest_lap_candidates
from gridpulse.pitwall.timing import neutralised_periods
from gridpulse.season.data import _colors, _results
from gridpulse.undercut.analysis import pit_stops

COMPOUND_LETTER = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}

YEAR_COLUMNS = ["Year", "Round", "Event", "Location", "Scheduled", "Laps", "Winner", "WinnerColor", "WinnerGrid",
                "Pole", "PoleColor", "PoleTime", "Fastest", "FastestColor", "FastestTime", "SafetyCars", "VSCs",
                "RedFlags", "Wet", "Finishers", "Retirements", "Stops", "WinnerTyres", "CommonTyres", "CommonShare",
                "PitLoss", "PitLossVsc"]


def slug(location: str) -> str:
    """A location as it goes in a link: São Paulo -> sao-paulo."""
    ascii_name = unicodedata.normalize("NFKD", location).encode("ascii", "ignore").decode()
    return "-".join(ascii_name.lower().replace("-", " ").split())


def saved_races() -> pd.DataFrame:
    """Every saved Grand Prix: Year, Round, Event, Location, Circuit (key), Date."""
    rows = []
    years = sorted(int(p.name) for p in snapshots.SNAPSHOT_DIR.glob("*") if p.name.isdigit())
    for year in years:
        for r in snapshots.races(year).itertuples():
            parts = snapshots.race_metadata(year, int(r.RoundNumber))
            if parts is None or parts.get("circuit_key") is None:
                continue
            rows.append({"Year": year, "Round": int(r.RoundNumber), "Event": r.EventName, "Location": r.Location,
                         "Circuit": int(parts["circuit_key"]), "Date": r.EventDate})
    return pd.DataFrame(rows, columns=["Year", "Round", "Event", "Location", "Circuit", "Date"])


def circuits(races: pd.DataFrame) -> pd.DataFrame:
    """One row per circuit, in the order of the latest season's calendar: Circuit, Location and Event (as
    last raced), Slug, Years (raced here, oldest first), Year and Round (latest)."""
    if races.empty:
        return pd.DataFrame(columns=["Circuit", "Location", "Event", "Slug", "Years", "Year", "Round"])
    latest = races.sort_values(["Year", "Round"]).groupby("Circuit").tail(1).set_index("Circuit")
    years = races.groupby("Circuit")["Year"].apply(lambda y: sorted(set(y)))
    out = latest.assign(Years=years, Slug=latest["Location"].map(slug)).reset_index()
    return out.sort_values(["Year", "Round"], ascending=[False, True]).reset_index(drop=True)[
        ["Circuit", "Location", "Event", "Slug", "Years", "Year", "Round"]]


def circuit_years(races: pd.DataFrame, circuit: int) -> pd.DataFrame:
    """Each saved Grand Prix at `circuit`, oldest first: the result, pole, fastest lap, neutralisations,
    weather, pit stops and tyres (see YEAR_COLUMNS)."""
    rows = []
    for r in races[races["Circuit"] == circuit].sort_values("Year").itertuples():
        parts = snapshots.load_race(r.Year, r.Round, "R")
        if parts is not None:
            rows.append(_year(parts, r))
    return pd.DataFrame(rows, columns=YEAR_COLUMNS)


def _year(parts: dict, r) -> dict:
    res, laps = parts["results"], parts["laps"]
    table = _results(res, r.Round, "R")
    color = {d: _colors(res).get(t, "#888888") for d, t in zip(table["Driver"], table["Team"])}
    winner = table[table["Position"] == 1].iloc[0]

    # Pole: the car that starts first, as F1 credits it (see season.data.pole_sitters), with its
    # qualifying time; the fastest qualifier where the grid isn't known.
    quali = snapshots.load_quali(r.Year, r.Round, "Q")
    q = quali.results.set_index("Driver") if quali is not None else pd.DataFrame(columns=["Position"])
    pole = table.loc[table["Grid"] == 1, "Driver"].iloc[0] if (table["Grid"] == 1).any() else None
    if pole is None and (q["Position"] == 1).any():
        pole = q.index[q["Position"] == 1][0]
    pole_time = np.nan
    if pole in q.index:
        times = [q.loc[pole, part] for part in ("Q3", "Q2", "Q1") if pd.notna(q.loc[pole, part])]
        pole_time = float(times[0]) if times else np.nan

    struck = table.loc[table["Dsq"], "Driver"]
    candidates = fastest_lap_candidates(laps[~laps["Driver"].isin(struck)])
    fastest, fastest_time = None, np.nan
    if not candidates.empty:
        best = candidates.loc[candidates["LapTime"].idxmin()]
        fastest, fastest_time = best["Driver"], best["LapTime"].total_seconds()

    periods = [status for status, _, _ in neutralised_periods(laps)]
    weather = parts.get("weather")
    wet = bool(laps["Compound"].isin(["INTERMEDIATE", "WET"]).any()) or (
        weather is not None and "Rainfall" in weather and bool(weather["Rainfall"].eq(True).any()))

    finishers = table.loc[table["Classified"], "Driver"]
    stops = pit_stops(laps, parts.get("stationary"))
    per_driver = stops.groupby("Driver").size().reindex(finishers, fill_value=0)
    tyres = {d: tyre_sequence(laps[laps["Driver"] == d]) for d in finishers}
    common, share = (Counter(tyres.values()).most_common(1)[0] if tyres else ("", 0))
    loss = parts.get("pit_loss_ref") or {}
    return {
        "Year": r.Year, "Round": r.Round, "Event": r.Event, "Location": r.Location,
        "Scheduled": int(parts["total_laps"]), "Laps": race_distance(int(parts["total_laps"]), res, laps),
        "Winner": winner["Driver"], "WinnerColor": color.get(winner["Driver"]),
        "WinnerGrid": int(winner["Grid"]) if pd.notna(winner["Grid"]) else None,
        "Pole": pole, "PoleColor": color.get(pole), "PoleTime": pole_time,
        "Fastest": fastest, "FastestColor": color.get(fastest), "FastestTime": fastest_time,
        "SafetyCars": periods.count("Safety car"), "VSCs": periods.count("VSC"), "RedFlags": periods.count("Red flag"),
        "Wet": wet, "Finishers": len(finishers), "Retirements": int((~table["Classified"] & ~table["Dsq"]).sum()),
        "Stops": per_driver.value_counts().sort_index().to_dict(),
        "WinnerTyres": tyres.get(winner["Driver"], ""), "CommonTyres": common, "CommonShare": share,
        "PitLoss": loss.get("normal"), "PitLossVsc": loss.get("vsc"),
    }


def tyre_sequence(laps: pd.DataFrame) -> str:
    """A car's tyres through the race as compound letters, stint by stint: M-H-H."""
    stints = laps.dropna(subset=["Stint"]).sort_values("LapNumber").groupby("Stint", sort=True)["Compound"].first()
    return "-".join(COMPOUND_LETTER.get(str(c).upper(), "?") for c in stints)
