"""Allow `python -m pitlens.stints ...` as a shortcut for `pitlens stints ...`."""

import sys

from pitlens.cli import main

main(["stints", *sys.argv[1:]])
