"""Load the new code after Streamlit Community Cloud updates a running app.

When a commit lands, Community Cloud pulls it into the running server without restarting it. The
page script (app.py) is read again on every run, but the modules it imported stay in memory as they
were, so the new script can call a function those modules don't have yet: an AttributeError for
every visitor until someone reboots the app. `forget_stale_modules` runs first thing in app.py. When
the checked-out commit has changed since the modules were loaded, it forgets every gridpulse module
and Streamlit's caches (which can hold objects built by the old code), so the imports that follow
load the new code.

Standard library and Streamlit only: anything else from gridpulse could itself be stale.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOADED = "GRIDPULSE_LOADED_COMMIT"  # the commit this process loaded its modules at (process-wide)
PACKAGE = "gridpulse"


def commit(root: Path = ROOT) -> str | None:
    """The checked-out commit, read straight from .git; None outside a git checkout."""
    git = root / ".git"
    if git.is_file():  # a worktree: ".git" names the real directory
        line = git.read_text().strip()
        git = Path(line.removeprefix("gitdir:").strip()) if line.startswith("gitdir:") else None
    if git is None or not (git / "HEAD").exists():
        return None
    head = (git / "HEAD").read_text().strip()
    if not head.startswith("ref:"):
        return head or None  # detached HEAD: the commit itself
    ref = head.removeprefix("ref:").strip()
    common = Path((git / "commondir").read_text().strip()) if (git / "commondir").exists() else git
    common = common if common.is_absolute() else (git / common).resolve()
    for base in (git, common):
        if (base / ref).exists():
            return (base / ref).read_text().strip() or None
    packed = common / "packed-refs"
    if packed.exists():
        for line in packed.read_text().splitlines():
            sha, _, name = line.partition(" ")
            if name == ref:
                return sha
    return None


def _ours(name: str) -> bool:
    return name == PACKAGE or name.startswith(PACKAGE + ".")


def forget_stale_modules(root: Path = ROOT, *, hosted: bool | None = None, modules: dict | None = None,
                         clear=None) -> bool:
    """Forget the gridpulse modules and Streamlit's caches if they were loaded at another commit; True
    if it did.

    The first run of a process records the commit and keeps what's loaded, with one exception on a
    server: modules other than this one already in memory were loaded by a version of the app from
    before this check existed, so there's no telling which commit they came from.
    """
    modules = sys.modules if modules is None else modules
    now = commit(root)
    if now is None:
        return False
    loaded = os.environ.get(LOADED)
    os.environ[LOADED] = now
    if loaded == now:
        return False
    if loaded is None:
        if hosted is None:
            hosted = str(root).startswith("/mount/src/") or os.environ.get("GRIDPULSE_HOSTED", "").lower() in (
                "1", "true", "yes")
        earlier = [n for n in modules if _ours(n) and n not in (PACKAGE, f"{PACKAGE}.pitwall", __name__)]
        if not (hosted and earlier):
            return False
    for name in [n for n in modules if _ours(n)]:
        del modules[name]
    if clear is None:
        import streamlit as st

        st.cache_data.clear()
        st.cache_resource.clear()
    else:
        clear()
    return True
