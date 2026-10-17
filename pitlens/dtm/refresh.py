"""Refresh a bundled DTM snapshot: python -m pitlens.dtm.refresh --year 2026."""

import argparse
import json

from pitlens.dtm.data import ROOT, YEARS, fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, type=int, choices=YEARS)
    args = parser.parse_args()
    payload = fetch(args.year)
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / f"{args.year}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)
    print(f"Saved {args.year}: {len(payload['events'])} weekends to {target}")


if __name__ == "__main__":
    main()
