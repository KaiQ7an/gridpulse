"""The old entry point, kept for the hosted app.

The Streamlit Community Cloud deployment was created when the package was called `pitlens`, and
Community Cloud can't change an app's main file, so it still runs this path. It only starts the
real app, gridpulse/pitwall/app.py. Delete it once the app is redeployed with the new path.
"""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The server's environment may have been installed under the old package name: import gridpulse
# from this checkout whatever is installed.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "gridpulse" / "pitwall" / "app.py"), run_name="__main__")
