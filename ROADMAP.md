# Roadmap

The goal is a race-day companion: something you can have open during a Grand Prix that shows
pace, tyres and strategy as the race unfolds. It is built in layers, each useful on its own.

## 1. `stints`: race pace and tyre degradation (done)

- [x] Clean-lap filter (pit laps, SC/VSC/yellow, inaccurate laps, 107% outliers)
- [x] Fuel correction and per-stint degradation fit
- [x] Pace and degradation charts, CSV export, unit tests, CI
- [ ] Separate track evolution from tyre wear (compare drivers on different tyre ages in the same laps)
- [ ] Run across a whole season and compare circuits

## 2. `onboard`: teammate telemetry comparison

- [ ] Speed, throttle, brake and gear against distance on each driver's fastest lap
- [ ] Delta-time trace and a track map coloured by who was faster in each mini-sector
- [ ] Corner-by-corner table: entry speed, minimum speed, braking point

## 3. `undercut`: pit-stop strategy explorer

- [ ] Stint timeline per driver (compound and length)
- [ ] Pit-loss estimate per circuit from the data
- [ ] Gap before and after each stop to judge whether an undercut or overcut worked

## 4. `pitwall`: race-day dashboard with replay (done)

- [x] Pick a season, event and focus drivers in the browser
- [x] Replay mode: step through a past race lap by lap as if it were live, with every chart
      updating, so the whole live pipeline can be built and tested on any weekend
- [x] Timing tower, race trace, positions, tyre stints, degradation so far and clean-lap pace
- [x] Race-control messages, track status and weather alongside the charts
- [ ] Mark safety car and VSC periods on the race trace
- [ ] Optional public deployment on Streamlit Community Cloud

## 5. `pitwall` live mode and `radio`

- [ ] Live mode on top of the same data layer as replay. F1's live-timing feed now needs an
      F1 TV subscription login (FastF1's `SignalRClient`); OpenF1 offers real-time data on a paid plan
- [ ] Team radio clips (OpenF1 `team_radio`) linked to the lap they were sent on
- [ ] Live tyre-degradation estimate and pit-window projection
