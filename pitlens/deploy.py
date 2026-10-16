"""Where PitLens is running. On a public server a few things are switched off: the local speech and
translation models (too heavy for a small shared machine) and anything that would spend an API key.
"""

import os

from pitlens.session import PROJECT_ROOT


def hosted() -> bool:
    """True on Streamlit Community Cloud (apps run from /mount/src) or with PITLENS_HOSTED=1."""
    flag = os.environ.get("PITLENS_HOSTED", "").lower()
    if flag in ("0", "false", "no"):
        return False
    return flag in ("1", "true", "yes") or str(PROJECT_ROOT).startswith("/mount/src/")
