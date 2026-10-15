"""`pitlens pitwall`: start the Streamlit dashboard and open it in the browser."""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from pitlens.session import PROJECT_ROOT

APP = Path(__file__).with_name("app.py")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab")


def _wait_until_up(url: str, timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def run(args: argparse.Namespace) -> None:
    url = f"http://localhost:{args.port}"
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(APP),
        "--server.port", str(args.port),
        "--server.address", "localhost",  # only this computer, not the whole network
        "--server.headless", "true",  # we open the browser ourselves, no first-run prompt
        "--browser.gatherUsageStats", "false",
    ]
    # Run from the project root so .streamlit/config.toml (theme) is picked up,
    # and put it on the path so the app can import pitlens however it was installed.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(PROJECT_ROOT), os.environ.get("PYTHONPATH")]))}
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, env=env)
    print(f"PitLens pit wall: {url}  (Ctrl+C to stop)")
    if not args.no_browser and _wait_until_up(url):
        webbrowser.open(url)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
