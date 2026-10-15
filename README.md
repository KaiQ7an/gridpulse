<div align="center">

# PitLens

**Race-engineering style analysis of public Formula 1 timing data.**

Clean the laps, correct for fuel, and measure how fast each tyre stint fell away,<br>
the same questions a strategy desk asks on a Sunday afternoon.

[![Tests](https://github.com/KaiQ7an/pitlens/actions/workflows/test.yml/badge.svg)](https://github.com/KaiQ7an/pitlens/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastF1](https://img.shields.io/badge/data-FastF1-E10600)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[Quick start](#quick-start) · [What it shows](#what-it-shows) · [How it works](#how-it-works) · [Roadmap](ROADMAP.md)

</div>

<table align="center">
<tr>
<td align="center"><img src="docs/images/pace_by_driver.png" alt="Race pace of the top 10" width="560"><br><sub><b>Race pace</b> · every clean lap of the top 10, by compound</sub></td>
<td align="center"><img src="docs/images/stint_degradation.png" alt="Tyre degradation per stint" width="300"><br><sub><b>Degradation</b> · fuel-corrected s/lap per stint</sub></td>
</tr>
</table>

## Why

Lap times on a broadcast tower are noisy: in-laps, safety cars, traffic and a car that gets
lighter every lap all hide what the tyres are actually doing. This project turns the public F1
timing feed (via [FastF1](https://github.com/theOehrly/Fast-F1)) into the numbers a race engineer
would want: representative pace per stint and a degradation rate per tyre, with the cleaning
rules written down and tested.

## Features

**`stints`: race pace and tyre degradation** (available now)

- Filters each driver's race to representative laps: no lap 1, no pit in/out laps, green flag
  only, FastF1's accuracy check, and a 107% outlier cut.
- Fuel correction (default 0.06 s per lap of fuel burned, adjustable or switchable off).
- A straight-line fit of lap time against tyre age for every stint gives the degradation rate in
  seconds per lap.
- Small-multiple pace chart and a ranked degradation chart, plus the cleaned laps and stint table
  as CSV for further work.

**Planned** (see the [roadmap](ROADMAP.md))

- `onboard`: teammate telemetry comparison, with speed, throttle, brake and gear traces on the
  fastest lap and a delta-time trace.
- `undercut`: pit-stop strategy explorer, with a stint timeline, a pit-loss estimate, and whether
  the undercut worked.
- `radio`: team radio clips linked to the lap they were sent on.
- `pitwall`: a Streamlit race-day dashboard that brings the modules together, replaying a past race
  lap by lap first and following a live one later.

## Quick start

You need Python 3.12 or newer.

```bash
git clone https://github.com/KaiQ7an/pitlens
cd pitlens
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pitlens.stints --year 2025 --event Hungary
```

The first run downloads the session into `cache/` (gitignored); later runs are instant. Charts
and CSVs land in `outputs/<year>_<event>/`.

| Option | Default | Meaning |
|---|---|---|
| `--year` | `2025` | Season |
| `--event` | `Hungary` | Event name, location or round number |
| `--top` | `10` | Analyse the top N finishers |
| `--fuel-effect` | `0.06` | Seconds gained per lap from fuel burn (`0` to disable) |

Run the tests with `pip install -r requirements-dev.txt && pytest`.

## What it shows

Sample: the 2025 Hungarian Grand Prix (70 laps), top 10 finishers, 661 clean laps, 24 stints.

- **The medium was the race tyre to start on.** Opening medium stints lost about 0.02 s per lap
  on average after fuel correction; several were flat or even got quicker as the track rubbered in.
- **The hard fell away harder than its name suggests.** Hard stints averaged about 0.07 s per lap,
  and the final stints of Verstappen, Leclerc, Piastri and Russell were the worst in the field at
  0.10 to 0.15 s per lap.
- **That is the one-stop versus two-stop story.** Norris went medium to lap 30, then hard to the
  flag; Piastri stopped twice. On fresh hards Piastri was about 0.65 s a lap quicker than Norris
  between laps 48 and 60, but his final stint also degraded fastest of the two, and Norris held on
  to win.

These are first-order numbers: the fit doesn't separate tyre wear from track evolution or
traffic, and the fuel effect is a rule of thumb. The roadmap lists how to tighten them.

## How it works

```
pitlens/
├── session.py         load a FastF1 session with the local cache
├── stints/
│   ├── pace.py        clean laps, fuel correction, per-stint degradation fit
│   ├── plots.py       matplotlib charts (compound colours + marker shapes)
│   └── __main__.py    command-line report for one race
└── pitwall/           race-day dashboard (planned)
tests/                 unit tests on synthetic stints, run in CI
```

1. `load_session` pulls lap timing, results, weather and race-control messages (no car telemetry,
   which this analysis doesn't need and which is the slowest download).
2. `clean_race_laps` applies the filters above and returns one tidy row per lap.
3. `add_fuel_corrected_time` subtracts `laps remaining × fuel effect`, so every lap is compared as
   if it carried end-of-race fuel.
4. `stint_degradation` fits lap time against tyre age for each stint with at least five clean laps;
   the slope is the degradation rate.

## Data

Timing data comes from the public F1 live-timing archive via FastF1. This project is unofficial
and not associated with Formula 1 or any team.

## License

[MIT](LICENSE)
