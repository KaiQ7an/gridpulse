"""Allow `python -m gridpulse.stints ...` as a shortcut for `gridpulse stints ...`."""

import sys

from gridpulse.cli import main

main(["stints", *sys.argv[1:]])
