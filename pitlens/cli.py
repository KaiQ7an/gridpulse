"""Command-line entry point: `pitlens <module> [options]`."""

import argparse

from pitlens.onboard import report as onboard_report
from pitlens.pitwall import serve as pitwall_serve
from pitlens.stints import report as stints_report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pitlens", description="Race-engineering analysis of public F1 data.")
    modules = parser.add_subparsers(dest="module", required=True, metavar="module")

    stints = modules.add_parser("stints", help="Race pace and tyre degradation for one race")
    stints_report.add_arguments(stints)
    stints.set_defaults(run=stints_report.run)

    onboard = modules.add_parser("onboard", help="Compare two drivers' fastest laps (telemetry)")
    onboard_report.add_arguments(onboard)
    onboard.set_defaults(run=onboard_report.run)

    pitwall = modules.add_parser("pitwall", help="Race-day dashboard in the browser (replay any race)")
    pitwall_serve.add_arguments(pitwall)
    pitwall.set_defaults(run=pitwall_serve.run)

    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
