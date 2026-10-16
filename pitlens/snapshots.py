"""Races and qualifying sessions saved ahead of time, so they open instantly and without the network.

A snapshot holds what the data sources gave (laps, results, race control, weather, radio,
stationary times) plus the extras normally fetched while loading (circuit map, pit loss
reference, rainfall) and any radio transcripts made so far. Loading one runs the same build
as a live load, so every fix in the build applies to snapshots too. Make them with
`pitlens snapshot`; they live in snapshots/ in the repository.

Set PITLENS_OFFLINE=1 to use snapshots only (the tests do).
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from pitlens.session import PROJECT_ROOT

SNAPSHOT_DIR = PROJECT_ROOT / "snapshots"
FORMAT = 1  # bump when what's saved changes shape; older snapshots are then ignored
RACE_FRAMES = ("laps", "results", "messages", "weather", "radio", "stationary")
RACE_SCALARS = ("total_laps", "event_name", "location", "source", "circuit_key", "session_name", "pit_loss_ref")
DATES = ("date", "race_utc")


def offline() -> bool:
    return os.environ.get("PITLENS_OFFLINE", "").lower() in ("1", "true", "yes")


def _dir(year: int, round_number: int, kind: str) -> Path:
    return SNAPSHOT_DIR / str(year) / f"{round_number:02d}-{kind}"


def _timestamp(value) -> str | None:
    return None if value is None or pd.isna(value) else pd.Timestamp(value).isoformat()


# ---------------------------------------------------------------- races


def save_race(year: int, round_number: int, kind: str, parts: dict, event_format: str = "") -> Path:
    """Write a race's parts (as `pitwall.data` builds them, with track, pit_loss_ref and rain_mm filled in)."""
    from pitlens.radio import transcribe

    d = _dir(year, round_number, kind)
    d.mkdir(parents=True, exist_ok=True)
    for name in RACE_FRAMES:
        frame = parts.get(name)
        if frame is not None:
            pd.DataFrame(frame).reset_index(drop=True).to_parquet(d / f"{name}.parquet", index=False)
    track = parts.get("track")
    rain = parts.get("rain_mm")
    urls = parts["radio"]["Url"].dropna().tolist() if parts.get("radio") is not None else []
    meta = {
        "format": FORMAT,
        "year": year,
        "round": round_number,
        "kind": kind,
        "event_format": event_format,
        **{k: _jsonable(parts.get(k)) for k in RACE_SCALARS},
        **{k: _timestamp(parts.get(k)) for k in DATES},
        "track": None if track is None else {
            "x": np.asarray(track["x"], float).round(1).tolist(), "y": np.asarray(track["y"], float).round(1).tolist(),
            "splits": [int(i) for i in track["splits"]], "rotation": float(track["rotation"]),
            "source": track.get("source", ""),
        },
        "rain_mm": None if rain is None else [[t.isoformat(), None if pd.isna(v) else float(v)] for t, v in rain.items()],
        "transcripts": {u: r for u in urls if (r := transcribe.cached(u))},
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    return d


def load_race(year: int, round_number: int, kind: str) -> dict | None:
    """A saved race's parts, or None if there's no (current) snapshot."""
    d = _dir(year, round_number, kind)
    meta = _meta(d)
    if meta is None:
        return None
    parts = {k: meta.get(k) for k in RACE_SCALARS}
    for k in DATES:
        parts[k] = pd.Timestamp(meta[k]) if meta.get(k) else None
    for name in RACE_FRAMES:
        path = d / f"{name}.parquet"
        parts[name] = pd.read_parquet(path) if path.exists() else None
    if parts["radio"] is None:
        parts["radio"] = pd.DataFrame(columns=["Driver", "Lap", "SessionTime", "Utc", "Url"])
    track = meta.get("track")
    if track:
        track = {**track, "x": np.asarray(track["x"]), "y": np.asarray(track["y"])}
    parts["track"] = track
    rain = meta.get("rain_mm")
    parts["rain_mm"] = None if rain is None else pd.Series(
        [v for _, v in rain], index=pd.to_datetime([t for t, _ in rain]), dtype=float)
    _seed_transcripts(meta.get("transcripts") or {})
    return parts


# ---------------------------------------------------------------- qualifying


def save_quali(q, kind: str, event_format: str = "") -> Path:
    d = _dir(q.year, q.round_number, kind)
    d.mkdir(parents=True, exist_ok=True)
    q.results.to_parquet(d / "results.parquet", index=False)
    q.laps.to_parquet(d / "laps.parquet", index=False)
    meta = {"format": FORMAT, "year": q.year, "round": q.round_number, "kind": kind, "event_format": event_format,
            "name": q.name, "event_name": q.event_name, "session_name": q.session_name, "location": q.location,
            "date": _timestamp(q.date), "source": q.source, "team_colors": q.team_colors}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    return d


def load_quali(year: int, round_number: int, kind: str):
    from pitlens.quali.data import QualiData

    d = _dir(year, round_number, kind)
    meta = _meta(d)
    if meta is None:
        return None
    return QualiData(name=meta["name"], event_name=meta["event_name"], session_name=meta["session_name"],
                     year=year, round_number=round_number, location=meta["location"],
                     date=pd.Timestamp(meta["date"]), source=meta["source"],
                     results=pd.read_parquet(d / "results.parquet"), laps=pd.read_parquet(d / "laps.parquet"),
                     team_colors=meta["team_colors"])


# ---------------------------------------------------------------- index


def races(year: int) -> pd.DataFrame:
    """Grands Prix with a snapshot in `year`, shaped like `pitwall.data.completed_races`."""
    rows = []
    for meta_path in sorted((SNAPSHOT_DIR / str(year)).glob("*-R/meta.json")):
        meta = json.loads(meta_path.read_text())
        if meta.get("format") == FORMAT:
            rows.append({"RoundNumber": meta["round"], "EventName": meta["event_name"], "Location": meta["location"],
                         "EventDate": pd.Timestamp(meta["date"]), "EventFormat": meta.get("event_format", "")})
    return pd.DataFrame(rows, columns=["RoundNumber", "EventName", "Location", "EventDate", "EventFormat"])


def _meta(d: Path) -> dict | None:
    path = d / "meta.json"
    if not path.exists():
        return None
    meta = json.loads(path.read_text())
    return meta if meta.get("format") == FORMAT else None


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _seed_transcripts(transcripts: dict) -> None:
    """Put a snapshot's radio transcripts (and translations) where the radio view looks for them."""
    from pitlens.radio import transcribe

    for url, record in transcripts.items():
        if not transcribe.cached(url):
            transcribe.save(url, record)


# ---------------------------------------------------------------- `pitlens snapshot`


def add_arguments(parser) -> None:
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--round", type=int, help="Only this round (default: every finished race of the season)")
    parser.add_argument("--only", choices=["races", "quali"], help="Only the races (and sprints), or only qualifying")


def run(args) -> None:
    from pitlens.checks import check_race
    from pitlens.pitwall.data import build_race, completed_races, fetch_race_parts, with_extras
    from pitlens.quali.data import fetch_quali
    from pitlens.session import TimingUnavailable

    races = completed_races(args.year)
    if args.round:
        races = races[races["RoundNumber"] == args.round]
    for r in races.itertuples():
        sprint_weekend = "sprint" in str(r.EventFormat)
        jobs = []
        if args.only != "quali":
            jobs += [("R", "race")] + ([("S", "sprint")] if sprint_weekend else [])
        if args.only != "races":
            jobs += [("Q", "qualifying")] + ([("SQ", "sprint qualifying")] if sprint_weekend else [])
        for kind, label in jobs:
            name = f"{args.year} R{r.RoundNumber:>2} {r.EventName} {label}"
            try:
                if kind in ("R", "S"):
                    path = save_race(args.year, int(r.RoundNumber), kind,
                                     with_extras(args.year, fetch_race_parts(args.year, int(r.RoundNumber), kind)),
                                     str(r.EventFormat))
                    problems = check_race(build_race(args.year, int(r.RoundNumber),
                                                     load_race(args.year, int(r.RoundNumber), kind)))
                    note = "matches the result" if not problems else "; ".join(problems)
                else:
                    path = save_quali(fetch_quali(args.year, int(r.RoundNumber), kind), kind, str(r.EventFormat))
                    note = "saved"
            except TimingUnavailable as exc:
                print(f"{name}: skipped ({exc})", flush=True)
                continue
            except Exception as exc:  # one bad session shouldn't stop the rest of the season
                print(f"{name}: failed ({exc.__class__.__name__}: {exc})", flush=True)
                continue
            size = sum(f.stat().st_size for f in path.iterdir()) / 1024
            print(f"{name:52} {size:6.0f} KB  {note}", flush=True)
