"""Small, validated links shared by the replay and analysis pages."""

from urllib.parse import urlencode

import streamlit as st


def integer(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def driver_codes(value: str) -> list[str]:
    return list(dict.fromkeys(c.strip().upper() for c in value.split(",") if c.strip()))[:6]


def select_season(years, *, key: str, target=None) -> int:
    """Keep the selected season when navigation removes another page's widget state."""
    years = list(years)
    ss = st.session_state
    if key not in ss and ss.get("selected_year") in years:
        ss[key] = ss.selected_year
    year = (st.sidebar if target is None else target).selectbox("Season", years, key=key)
    ss.selected_year = year
    return year


def replay_params(year: int, round_number: int, kind: str = "R", *, lap: int | None = None,
                  focus: list[str] | None = None, view: str = "Gaps", no_spoilers: bool = False) -> dict[str, str]:
    params = {"year": str(year), "round": str(round_number)}
    if kind == "S":
        params["session"] = "sprint"
    if lap is not None:
        params["lap"] = str(lap)
    if focus is not None:
        params["drivers"] = ",".join(focus)
    if view != "Gaps":
        params["view"] = view
    if no_spoilers:
        params["mode"] = "replay"
    return params


def url(page: str, **params) -> str:
    return f"./{page}?{urlencode({k: v for k, v in params.items() if v is not None})}"
