"""Local SVG map component: geographic projections and interactive circuit markers."""

from pathlib import Path

import streamlit.components.v1 as components

from gridpulse.season.atlas import REGIONS, catalog

_component = components.declare_component("gridpulse_circuit_atlas", path=str(Path(__file__).parent))


def atlas_map(region: str = "world", selected: str | None = None, *, key: str = "atlas-map",
              circuit_data: list[dict] | None = None, regions: dict | None = None, series: str = "Formula 1",
              height: int | None = None):

    return _component(circuits=catalog() if circuit_data is None else circuit_data, regions=REGIONS if regions is None else regions,
                      series=series, region=region, selected=selected,
                      height=height if height is not None else 330 if selected else 540, key=key, default=None)
