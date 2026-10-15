"""Team radio clips from the F1 live-timing archive, matched to laps.

Each session in the archive has a TeamRadio stream: one message per clip with
the car number and the path of an mp3 next to it. The stream's timestamps use
the same session clock as FastF1's lap times, so every clip can be placed on
the lap its driver was on when it was sent.
"""

import json
import re
from pathlib import Path

import pandas as pd
import requests

from pitlens.session import CACHE_DIR

ARCHIVE = "https://livetiming.formula1.com"
_LINE = re.compile(r"^(\d+):(\d\d):(\d\d\.\d+)(.*)$")


def parse_stream(text: str) -> pd.DataFrame:
    """Parse TeamRadio.jsonStream into SessionTime, Utc, DriverNumber and Path."""
    rows = []
    for line in text.lstrip("﻿").splitlines():
        m = _LINE.match(line.strip())
        if not m:
            continue
        h, mnt, sec, payload = m.groups()
        t = pd.to_timedelta(int(h) * 3600 + int(mnt) * 60 + float(sec), unit="s")
        captures = json.loads(payload).get("Captures", [])
        if isinstance(captures, dict):  # later messages are keyed by index
            captures = captures.values()
        for c in captures:
            rows.append({"SessionTime": t, "Utc": c.get("Utc"), "DriverNumber": str(c.get("RacingNumber")), "Path": c.get("Path")})
    df = pd.DataFrame(rows, columns=["SessionTime", "Utc", "DriverNumber", "Path"])
    df["Utc"] = pd.to_datetime(df["Utc"], utc=True, errors="coerce", format="ISO8601")
    return df


def assign_laps(clips: pd.DataFrame, laps: pd.DataFrame) -> pd.Series:
    """The lap each clip's driver was on when it was sent (NaN before lap 1 or after the flag)."""
    out = pd.Series(pd.NA, index=clips.index, dtype="Int64")
    for i, clip in clips.iterrows():
        d = laps[(laps["DriverNumber"].astype(str) == clip["DriverNumber"])]
        on = d[(d["LapStartTime"] <= clip["SessionTime"]) & (d["Time"] > clip["SessionTime"])]
        if not on.empty:
            out[i] = int(on["LapNumber"].iloc[0])
    return out


def _cached_stream(api_path: str) -> str:
    """Download the session's radio stream once and keep it in the gitignored cache."""
    cache_file = CACHE_DIR / "radio" / (api_path.strip("/").replace("/", "_") + ".jsonStream")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    resp = requests.get(f"{ARCHIVE}{api_path}TeamRadio.jsonStream", timeout=20)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(text, encoding="utf-8")
    return text


def team_radio(session) -> pd.DataFrame:
    """Every radio clip in a loaded FastF1 session: Driver, Lap, SessionTime, Utc and the audio Url."""
    clips = parse_stream(_cached_stream(session.api_path))
    numbers = dict(zip(session.results["DriverNumber"].astype(str), session.results["Abbreviation"]))
    clips["Driver"] = clips["DriverNumber"].map(numbers).fillna("#" + clips["DriverNumber"])
    clips["Lap"] = assign_laps(clips, pd.DataFrame(session.laps))
    clips["Url"] = ARCHIVE + session.api_path + clips["Path"]
    return clips[["Driver", "Lap", "SessionTime", "Utc", "Url"]].sort_values("SessionTime").reset_index(drop=True)


def download(clips: pd.DataFrame, folder: Path) -> list[Path]:
    """Save the clips' mp3s into `folder` (skips files already there)."""
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for c in clips.itertuples():
        lap = f"lap{int(c.Lap):02d}" if pd.notna(c.Lap) else "nolap"
        path = folder / f"{lap}_{c.Driver}_{c.Url.rsplit('/', 1)[-1]}"
        if not path.exists():
            resp = requests.get(c.Url, timeout=30)
            resp.raise_for_status()
            path.write_bytes(resp.content)
        saved.append(path)
    return saved
