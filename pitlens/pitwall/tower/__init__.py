"""Animated timing tower: a small Streamlit component (plain HTML + JS, no build step).

The iframe stays mounted between reruns, so when the lap advances rows slide
to their new positions and gaps count smoothly to their new values instead of
the whole table being redrawn.
"""

from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components

from pitlens.style import COMPOUND_COLORS

_component = components.declare_component("pitlens_timing_tower", path=str(Path(__file__).parent))


def timing_tower(
    tower: pd.DataFrame,
    team_colors: dict[str, str],
    lap: int,
    duration_ms: int,
    on_radio: set[str] = frozenset(),
    focus: list[str] = (),
    banner: dict | None = None,
    key: str = "tower",
):
    rows = []
    for r in tower.itertuples():
        age = "" if pd.isna(r.TyreAge) else int(r.TyreAge)
        rows.append(
            {
                "pos": int(r.Pos),
                "driver": r.Driver,
                "team_color": team_colors.get(r.Driver, "#999999"),
                "gap": r.Gap,
                "gap_seconds": None if pd.isna(r.GapSeconds) or r.LapsDown > 0 or r.Out else float(r.GapSeconds),
                "interval": r.Interval,
                "interval_seconds": float(r.IntervalSeconds) if r.Interval else None,
                "last_lap": r.LastLap,
                "compound_letter": r.Compound[0],
                "tyre_age": age,
                "compound_color": COMPOUND_COLORS.get(r.Compound, COMPOUND_COLORS["UNKNOWN"]),
                "stops": None if pd.isna(r.Stops) else int(r.Stops),
                "pit": bool(r.Pit),
                "out": bool(r.Out),
                "radio": r.Driver in on_radio,
            }
        )
    return _component(
        rows=rows, lap=lap, duration_ms=duration_ms, focus=list(focus), banner=banner, key=key, default=None
    )
