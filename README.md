<div align="center">

# PitLens

**A race engineer's view of public Formula 1 data.**

Replay any race from the pit wall, lap by lap, and measure what the tyres were really doing:<br>
the same questions a strategy desk asks on a Sunday afternoon.

[![Tests](https://github.com/KaiQ7an/pitlens/actions/workflows/test.yml/badge.svg)](https://github.com/KaiQ7an/pitlens/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastF1](https://img.shields.io/badge/data-FastF1-E10600)
![Streamlit](https://img.shields.io/badge/dashboard-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[Quick start](#quick-start) · [Pit wall](#pit-wall) · [Tyre analysis](#tyre-analysis) · [How it works](#how-it-works) · [Roadmap](ROADMAP.md)

</div>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/pitwall_dark.png">
    <img src="docs/images/pitwall_light.png" alt="The PitLens pit wall replaying the 2026 Singapore Grand Prix" width="900">
  </picture>
  <br><sub><b>Pit wall</b> · timing tower and race trace at the end of the 2026 Singapore Grand Prix</sub>
</p>

## Why

Lap times on a broadcast tower are noisy: in-laps, safety cars, traffic and a car that gets
lighter every lap all hide what the tyres are actually doing. PitLens turns the public F1 timing
feed (via [FastF1](https://github.com/theOehrly/Fast-F1)) into what a race engineer would want on
their screens: who is where and on what tyre, how gaps are moving, and how fast each stint is
falling away, with the cleaning rules written down and tested.

## Features

**`pitwall`: race-day dashboard** (available now)

- Any race from 2018 to the latest Grand Prix, picked from the sidebar.
- **Replay**: press Play and the whole dashboard advances a lap at a time (three speeds), or drag
  the lap slider to any moment of the race.
- **Timing tower**: running order, gap to the leader, interval, last lap, tyre compound and age,
  stops, lapped cars and retirements, with a pit flag on the lap a car boxes.
- **Race trace**: seconds behind the leader for every car, focus drivers in team colours.
- **Positions**, **tyre stints** in running order, **degradation so far** for the focus drivers,
  **clean-lap pace** by compound, and **race control messages** up to the current lap.
- Track status, track temperature and rain at the current lap.

**`stints`: race pace and tyre degradation report** (available now)

- Filters each driver's race to representative laps: no lap 1, no pit in/out laps, green flag
  only, FastF1's accuracy check, and a 107% outlier cut.
- Fuel correction (default 0.06 s per lap of fuel burned, adjustable or switchable off).
- A straight-line fit of lap time against tyre age for every stint gives the degradation rate in
  seconds per lap. Charts and CSVs are saved for further work.

**Planned** (see the [roadmap](ROADMAP.md))

- `onboard`: teammate telemetry comparison, with speed, throttle, brake and gear traces on the
  fastest lap and a delta-time trace.
- `undercut`: pit-loss estimates and whether each undercut or overcut worked.
- `radio`: team radio clips linked to the lap they were sent on.
- A live mode for the pit wall on race day.

## Quick start

You need Python 3.12 or newer.

```bash
git clone https://github.com/KaiQ7an/pitlens
cd pitlens
python3 -m venv .venv
.venv/bin/pip install -e .
```

Then, from the project folder:

```bash
.venv/bin/python -m pitlens pitwall
```

The pit wall opens in your browser at <http://localhost:8501>. Press **Ctrl+C** in the terminal to
stop it. The first load of each race downloads its timing data into `cache/` (gitignored), which
takes up to a minute; after that it opens instantly.

With the virtual environment activated (`source .venv/bin/activate`) the shorter `pitlens pitwall`
works too.

## Pit wall

| Option | Default | Meaning |
|---|---|---|
| `--port` | `8501` | Port for the local web server |
| `--no-browser` | off | Start the server without opening a browser tab |

The server only listens on this computer (`localhost`).

## Tyre analysis

```bash
.venv/bin/python -m pitlens stints --year 2025 --event Hungary --open
```

| Option | Default | Meaning |
|---|---|---|
| `--year` | `2025` | Season |
| `--event` | `Hungary` | Event name, location or round number |
| `--top` | `10` | Analyse the top N finishers |
| `--fuel-effect` | `0.06` | Seconds gained per lap from fuel burn (`0` to disable) |
| `--open` | off | Open the charts when the report is done (macOS) |

Charts and CSVs land in `outputs/<year>_<event>/`.

<table align="center">
<tr>
<td align="center"><img src="docs/images/pace_by_driver.png" alt="Race pace of the top 10" width="560"><br><sub><b>Race pace</b> · every clean lap of the top 10, by compound</sub></td>
<td align="center"><img src="docs/images/stint_degradation.png" alt="Tyre degradation per stint" width="300"><br><sub><b>Degradation</b> · fuel-corrected s/lap per stint</sub></td>
</tr>
</table>

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
├── style.py           compound colours and symbols shared by every chart
├── stints/
│   ├── pace.py        clean laps, fuel correction, per-stint degradation fit
│   ├── plots.py       static matplotlib charts
│   └── report.py      the `stints` command
├── pitwall/
│   ├── data.py        one race as plain DataFrames (laps, results, weather, messages)
│   ├── timing.py      timing tower, gaps, track status and stints at any lap
│   ├── charts.py      interactive plotly charts
│   ├── app.py         the Streamlit dashboard
│   └── serve.py       the `pitwall` command
└── cli.py             `pitlens <module>`
tests/                 unit tests on synthetic races, run in CI
```

- **Tyre degradation.** `clean_race_laps` keeps representative laps,
  `add_fuel_corrected_time` subtracts `laps remaining × fuel effect` so every lap is compared as if
  it carried end-of-race fuel, and `stint_degradation` fits lap time against tyre age for each
  stint with at least five clean laps; the slope is the degradation rate.
- **Timing tower.** FastF1 records the session time at which every car completed every lap.
  `timing_tower` orders cars by when they crossed the line on a given lap, takes gaps from those
  times, and counts laps down by how many laps the leader had finished when a car crossed.
  Cars that never complete the lap are lapped or, if their result says so, out.
- **Replay.** The dashboard body is a Streamlit fragment that reruns every 0.4 to 2 seconds while
  playing, moving the lap forward and recomputing everything from laps up to that point. The
  functions don't care whether the laps came from a finished race or a live feed, which is the
  plan for live mode.

Run the tests with `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest`.

## Troubleshooting

**`No module named 'pitlens'` when running `pitlens ...`.** On macOS, if the project sits in an
iCloud-synced folder (Desktop or Documents with iCloud Drive), iCloud marks files inside `.venv`
as hidden, and Python 3.13+ then skips the file that makes the editable install importable. Run
`.venv/bin/python -m pitlens ...` from the project folder instead, which always works, or keep the
project outside iCloud Drive (for example `~/Developer`).

## Data

Timing data comes from the public F1 live-timing archive via FastF1. This project is unofficial
and not associated with Formula 1 or any team.

## License

[MIT](LICENSE)
