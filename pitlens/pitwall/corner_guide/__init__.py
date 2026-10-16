"""A local, keyboard-accessible circuit and reference-lap explorer."""

from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component("pitlens_corner_guide", path=str(Path(__file__).parent))


def corner_guide(tour: dict, name: str, key: str, *, selected: str | None = None, share_path: str = ""):
    return _component(tour=tour, name=name, selected=selected, share_path=share_path, key=key, default=None)
