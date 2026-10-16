"""Clickable race events. Only pass events the current spoiler setting permits."""

from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components

_component = components.declare_component("pitlens_event_timeline", path=str(Path(__file__).parent))


def known_events(events: pd.DataFrame, lap: int, no_spoilers: bool) -> list[dict]:
    known = events[events["Lap"] <= lap] if no_spoilers else events
    return [{"event": str(i), "lap": int(r["Lap"]), "kind": r["Kind"],
             "driver": str(r["Driver"]) if pd.notna(r["Driver"]) else "", "text": r["Text"]}
            for i, r in known.iterrows() if pd.notna(r["Lap"])]


def event_timeline(events: list[dict], lap: int, total_laps: int, no_spoilers: bool, key: str):
    return _component(events=events, lap=lap, total_laps=total_laps, no_spoilers=no_spoilers, key=key, default=None)
