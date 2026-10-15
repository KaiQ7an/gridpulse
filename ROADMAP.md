# Roadmap

The goal is a race-day companion: something you can have open during a Grand Prix that shows
pace, tyres and strategy as the race unfolds. It is built in layers, each useful on its own.

## 1. `stints`: race pace and tyre degradation (done)

- [x] Clean-lap filter (pit laps, SC/VSC/yellow, inaccurate laps, 107% outliers)
- [x] Fuel correction and per-stint degradation fit
- [x] Pace and degradation charts, CSV export, unit tests, CI
- [ ] Separate track evolution from tyre wear (compare drivers on different tyre ages in the same laps)
- [ ] Run across a whole season and compare circuits

## 2. `onboard`: teammate telemetry comparison (done)

- [x] Speed, throttle, brake and gear against distance on each driver's fastest lap
- [x] Delta-time trace (laps aligned by GPS position, not integrated distance) and a track map
      coloured by who was faster in each mini-sector
- [x] Corner-by-corner table: minimum speed and time gained
- [ ] Braking points and throttle application per corner
- [ ] Compare a driver's laps across a stint, not only the fastest

## 3. `undercut`: pit-stop strategy explorer (done)

- [x] Every stop with pit lane time, tyres and its cost against the cars that stayed out
- [x] Typical green-flag pit loss per race
- [x] Undercut and overcut battles with before/after gaps and a verdict
- [x] Rejoin projection: where a car comes out if it pits now
- [x] Circuit reference pit loss (green, VSC, SC) until this race has three green-flag stops of its own
- [x] Stationary time per stop (from OpenF1, where F1 publishes it), places lost, quickest stops and crews
- [x] Leave out drives through the pit lane on the same tyres (penalties, field sent through under SC)
- [ ] Tyre-offset model: when does a fresher tyre catch the car ahead

## 4. `pitwall`: race-day dashboard with replay (done)

- [x] Pick a season, event and focus drivers in the browser
- [x] Replay mode: step through a past race lap by lap as if it were live, with every chart
      updating, so the whole live pipeline can be built and tested on any weekend
- [x] Timing tower, race trace, positions, tyre stints, degradation so far and clean-lap pace
- [x] Race-control messages, track status and weather alongside the charts
- [x] Mark safety car and VSC periods on the race trace
- [x] Replay sprints as well as Grands Prix

## 5. `radio` (done)

- [x] Team radio clips from the F1 archive, placed on the lap they were sent
- [x] Radio view in the pit wall and a microphone in the timing tower
- [x] Transcribe clips locally with Whisper, shown under each clip and in the race feed
- [x] Translate transcripts into Chinese (offline with an F1 glossary, or Claude)

## 6. Data sources

- [x] OpenF1 fallback for races and onboard laps when F1's archive refuses requests
- [x] Use MultiViewer's per-circuit pit loss (normal, SC, VSC) for the rejoin projection
- [x] Final lap follows the official classification (penalties, disqualifications, missing last laps);
      near-ties mid-race follow the running position
- [x] OpenF1 quirks handled: stops placed on their in-lap where the pit lane crosses the timing line,
      drive-throughs folded into the stint, extra laps capped at the classified count
- [x] Every 2025 and 2026 race checked against the official winner, top ten and laps down
- [x] Warn when a race's source is missing laps (2025 Miami); radio and stationary times from OpenF1
      when F1's archive won't serve them

## 7. `pitwall` live mode

- [ ] Live mode on top of the same data layer as replay. F1's live-timing feed now needs an
      F1 TV subscription login (FastF1's `SignalRClient`); OpenF1 offers real-time data on a paid plan
- [ ] Live tyre-degradation estimate and pit-window projection
- [ ] Optional public deployment on Streamlit Community Cloud
