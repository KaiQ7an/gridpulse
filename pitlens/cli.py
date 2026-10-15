"""Command-line entry point: `pitlens <module> [options]`."""

import argparse

from pitlens.onboard import report as onboard_report
from pitlens.pitwall import serve as pitwall_serve
from pitlens.radio import report as radio_report
from pitlens.stints import report as stints_report
from pitlens.undercut import report as undercut_report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pitlens", description="Race-engineering analysis of public F1 data.")
    modules = parser.add_subparsers(dest="module", required=True, metavar="module")

    stints = modules.add_parser("stints", help="Race pace and tyre degradation for one race")
    stints_report.add_arguments(stints)
    stints.set_defaults(run=stints_report.run)

    onboard = modules.add_parser("onboard", help="Compare two drivers' fastest laps (telemetry)")
    onboard_report.add_arguments(onboard)
    onboard.set_defaults(run=onboard_report.run)

    undercut = modules.add_parser("undercut", help="Pit stops, pit loss and undercut battles for one race")
    undercut_report.add_arguments(undercut)
    undercut.set_defaults(run=undercut_report.run)

    radio = modules.add_parser("radio", help="Team radio clips for a session, matched to laps")
    radio_report.add_arguments(radio)
    radio.set_defaults(run=radio_report.run)

    pitwall = modules.add_parser("pitwall", help="Race-day dashboard in the browser (replay any race)")
    pitwall_serve.add_arguments(pitwall)
    pitwall.set_defaults(run=pitwall_serve.run)

    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
