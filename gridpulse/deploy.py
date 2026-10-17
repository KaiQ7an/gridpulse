"""Detect shared hosting, where Onboard prefers the smaller OpenF1 telemetry fetch.

Radio reads prepared transcripts in every web environment; models run only in the CLI.
"""

import os

from gridpulse.session import PROJECT_ROOT


def hosted() -> bool:
    """True on Streamlit Community Cloud (apps run from /mount/src) or with GRIDPULSE_HOSTED=1."""
    flag = os.environ.get("GRIDPULSE_HOSTED", "").lower()
    if flag in ("0", "false", "no"):
        return False
    return flag in ("1", "true", "yes") or str(PROJECT_ROOT).startswith("/mount/src/")
