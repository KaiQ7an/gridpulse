"""Load packaged CSS resources through Streamlit's public HTML API."""

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).with_name('assets')


def inject(filename: str) -> None:
    """Load an application-owned CSS filename; Streamlit wraps .css files in a style tag."""
    st.html(ASSETS / filename)
