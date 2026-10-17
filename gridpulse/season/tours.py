"""Small offline corner tours derived from one explicitly identified telemetry lap."""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from gridpulse.onboard.compare import rotate

# Names verified against the venues' own course guides. Unnamed turns retain their number.
CORNER_NAMES = {
    "monza": ({"T1": "Variante del Rettifilo", "T2": "Variante del Rettifilo", "T3": "Curva Biassono / Grande",
               "T4": "Variante della Roggia", "T5": "Variante della Roggia", "T6": "Lesmo 1", "T7": "Lesmo 2",
               "T8": "Variante Ascari", "T9": "Variante Ascari", "T10": "Variante Ascari",
               "T11": "Curva Alboreto / Parabolica"}, "https://www.monzanet.it/en/circuit/"),
    "suzuka": ({"T3": "S Curves", "T4": "S Curves", "T5": "S Curves", "T6": "S Curves",
                "T8": "Degner 1", "T9": "Degner 2", "T11": "Hairpin", "T13": "Spoon Curve",
                "T14": "Spoon Curve", "T15": "130R", "T16": "Chicane", "T17": "Chicane", "T18": "Last Curve"},
               "https://www.suzukacircuit.jp/course_s/pdf/suzuka_courseguide.pdf"),
}


def corner_measurements(telemetry: pd.DataFrame, distance: float) -> dict:
    part = telemetry[telemetry["Distance"].between(distance - 60, distance + 60)]
    approach = telemetry[telemetry["Distance"].between(distance - 250, distance + 30)]
    if len(part) < 2 or len(approach) < 2:
        return {"speed": None, "gear": None, "brake_m": None}
    speed = part["Speed"].dropna()
    gears = part["nGear"].dropna()
    gears = gears[gears > 0]
    brake_distance = np.diff(approach["Distance"].to_numpy())
    brake_on = approach["Brake"].fillna(False).astype(bool).to_numpy()[1:]
    return {"speed": round(float(speed.min())) if len(speed) else None,
            "gear": int(gears.min()) if len(gears) else None,
            "brake_m": round(float(brake_distance[brake_on].sum()))}


def build_tour(circuit: dict, telemetry: pd.DataFrame | None, fallback_track: dict, reference: dict,
               slug: str = "") -> dict:
    """Coordinate data is sampled, not a simulation. Missing telemetry stays missing."""
    has_telemetry = telemetry is not None and len(telemetry) > 5
    x = np.asarray(telemetry["X"] if has_telemetry else fallback_track["x"], dtype=float)
    y = np.asarray(telemetry["Y"] if has_telemetry else fallback_track["y"], dtype=float)
    rotation = circuit.get("rotation", fallback_track.get("rotation", 0))
    rx, ry = rotate(x, y, rotation)
    scale = min(700 / max(np.ptp(rx), 1), 440 / max(np.ptp(ry), 1))
    centre_x, centre_y = (rx.max() + rx.min()) / 2, (ry.max() + ry.min()) / 2

    def point(i):
        return [round(float((rx[i] - centre_x) * scale + 400), 2),
                round(float(-(ry[i] - centre_y) * scale + 270), 2)]

    indices = np.unique(np.linspace(0, len(x) - 1, min(600, len(x))).astype(int))
    samples = []
    for i in indices:
        row = telemetry.iloc[i] if has_telemetry else None
        samples.append({"point": point(i), "speed": int(row["Speed"]) if row is not None and pd.notna(row["Speed"]) else None,
                        "gear": int(row["nGear"]) if row is not None and pd.notna(row["nGear"]) else None,
                        "brake": bool(row["Brake"]) if row is not None and pd.notna(row["Brake"]) else None})
    corners = []
    names, name_source = CORNER_NAMES.get(slug, ({}, None))
    span = max(np.ptp(x), np.ptp(y), 1)
    for corner in circuit.get("corners", []):
        cx, cy = corner["trackPosition"]["x"], corner["trackPosition"]["y"]
        distances = np.hypot(x - cx, y - cy)
        index = int(distances.argmin())
        number = str(corner["number"]) + (corner.get("letter") or "")
        measurements = {"speed": None, "gear": None, "brake_m": None}
        if has_telemetry and distances[index] / span < .05:
            measurements = corner_measurements(telemetry, float(telemetry.iloc[index]["Distance"]))
        corners.append({"label": "T" + number, "name": corner.get("name") or names.get("T" + number, f"Turn {number}"),
                        "point": point(index), "sample": int(np.abs(indices - index).argmin()), **measurements})
    return {"points": [s["point"] for s in samples], "samples": samples, "corners": corners,
            "reference": reference, "name_source": name_source, "telemetry": has_telemetry}


@lru_cache(maxsize=1)
def _tours(revision: int) -> dict:
    return json.loads(Path(__file__).with_name("corner_tours.json").read_text())


def corner_tour(slug: str) -> dict | None:
    path = Path(__file__).with_name("corner_tours.json")
    return _tours(path.stat().st_mtime_ns).get(slug) if path.exists() else None


def corner_label(tour: dict | None, value: str | None) -> str | None:
    """Only numbered markers in this venue may be restored from a shared link."""
    label = str(value or "").strip().upper()
    return label if tour and any(c["label"] == label for c in tour["corners"]) else None
