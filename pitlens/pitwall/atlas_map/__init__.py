"""Local SVG map component: geographic projections and interactive circuit markers."""

from pathlib import Path

import streamlit.components.v1 as components

from pitlens.season.atlas import REGIONS, catalog

_component = components.declare_component("pitlens_circuit_atlas", path=str(Path(__file__).parent))


def atlas_map(region: str = "world", selected: str | None = None, *, key: str = "atlas-map"):
    return _component(circuits=catalog(), regions=REGIONS, region=region, selected=selected,
                      height=330 if selected else 540, key=key, default=None)
