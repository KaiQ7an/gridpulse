# Replay and pit-window validation

GridPulse rebuilds every race from lap timing: who crossed the line when, on which lap, on which
tyres. The timing comes from F1's live-timing archive (through FastF1) or, when the archive
refuses a session, from OpenF1. Neither source is the official result. So the obvious test of
the whole pipeline is whether the replay's final lap agrees with the classification.

## Reproduced snapshot check: 17 October 2026

The current checkout was checked **offline**, rebuilding all bundled race and sprint snapshots.
All **89 Grands Prix and 24 sprints** pass the winner, top-ten order and classified-finishers’
laps-down checks. The saved classification is the reference for this check; no fresh result was
scraped and this is not a test of every mid-race gap or the visual pixels.

| Bundled season | Grands Prix | Sprints |
|---|---:|---:|
| 2021 | 1 | 0 |
| 2022 | 1 | 0 |
| 2023 | 22 | 6 |
| 2024 | 24 | 6 |
| 2025 | 24 | 6 |
| 2026, through Singapore | 17 | 6 |

The 2024/2025 pit-window backtest was also rerun with its ten-lap horizon: **303 + 322 = 625 stops**.
The rounded results match the table below. [Machine-readable run summary](validation-2026-10-17.json).

To reproduce without network requests, set `GRIDPULSE_OFFLINE=1` before the commands below;
they then check only the snapshots included for that season. The earlier 131-race result below
covers a wider historical run, not the smaller 2021/2022 sample bundled in this checkout.

## The check

For every race, `gridpulse check` builds the timing tower at the flag and compares it with the
official classification:

- the same winner;
- the same top ten, in the same order;
- every classified finisher the same number of laps down.

```bash
.venv/bin/python -m gridpulse check --year 2025            # every Grand Prix of a season
.venv/bin/python -m gridpulse check --year 2025 --sprint   # the sprints
.venv/bin/python -m gridpulse check --year 2026 --round 15 # one race
```

Earlier recorded archive-wide checks:

| Season | Grands Prix | Sprints | Data |
|---|---|---|---|
| 2021 | 22 of 22 | not checked | F1's archive |
| 2022 | 22 of 22 | not checked | F1's archive |
| 2023 | 22 of 22 | 6 of 6 | OpenF1 |
| 2024 | 24 of 24 | 6 of 6 | OpenF1 |
| 2025 | 24 of 24 | 6 of 6 | OpenF1 (two races from the archive) |
| 2026, to Singapore | 17 of 17 | 6 of 6 | OpenF1 (Singapore from the archive) |

It didn't start that way. A user spotted the first problem by eye ("Russell won Baku, not
Verstappen"), and running the check over every season turned up the rest. Each one below is now
fixed and covered by a unit test.

## What it caught

**A photo finish the wrong way round.** In the 2026 Azerbaijan Grand Prix OpenF1's lap times put
Verstappen 0.003 s ahead of Russell at the flag; Russell won by 0.196 s. OpenF1 rebuilds each
lap's end from the next lap's start stamp, and those stamps are only good to a few tenths. The
tower now shows the official classification and gaps on the last lap. In mid-race, cars that
cross the line within half a second of each other are ordered by the timing feed's running
position instead of by the clock. Without that, the 2026 Baku race showed Leclerc gaining three
seconds on Piastri on one lap and losing it all on the next, with two invented passes.

**Penalties after the flag.** Colapinto crossed the line 8th in the 2026 Barcelona Grand Prix
and was classified 10th; Ocon dropped from 9th to 12th at Monaco in 2022. The replay keeps the
order they crossed the line in for working out passes. At the flag it shows the result, and the
race feed says "COL classified P10, crossed the line P8" rather than inventing a last-lap pass.

**Disqualifications.** Leclerc, Hamilton and Gasly took the flag in the 2025 Chinese Grand Prix
and were disqualified afterwards. They drop to the bottom of the tower, marked DSQ.

**A missing last lap.** For the 2026 Australian Grand Prix OpenF1 has no time for anyone's last
lap, and no last lap at all for most cars, so every car looked a lap down at the flag. The finish
is rebuilt from the result. The winner's flag time is estimated from the start of their last lap
and their recent pace. Lead-lap finishers come in their official gap behind (with a last lap
added where one is missing). Other finishers get their own last lap estimated from their pace.

**A lap too many.** The 2026 British Grand Prix finished behind the safety car, and OpenF1 gives
Sainz a 52nd lap although he was classified a lap down with 51, which put him on the lead lap.
Each driver's laps are now capped at the number the classification says they completed.

**A race cut short.** The 2022 Monaco Grand Prix hit the time limit after 64 of its 78 laps.
FastF1's lap total is the scheduled distance, so the replay waited for 14 laps that never
happened, and every car showed as 13 laps down. The race distance is now the winner's laps.

**Lapped cars with a "gap".** FastF1's results give lapped cars a time too, but it isn't their
gap to the winner. Using it as one added a final lap they never ran, and six lapped cars appeared
on the lead lap in Singapore 2026. Official gaps now only cover cars that ran the full distance.
This one was only caught when the check started comparing laps down, not just the order.

**Pit stops on the wrong lap.** OpenF1 records a stop on the lap it was made. That's the in-lap
where the pit boxes come before the timing line (Baku, Singapore), but the out-lap where the pit
lane crosses it (Montreal, Melbourne). GridPulse had assumed the in-lap everywhere, so the 2026
Canadian Grand Prix showed no stops at all. The tyre stints tell the two cases apart: where the
pit lane crosses the line, the new stint starts on the recorded lap.

**Stops that weren't stops.** Behind the safety car in Baku the whole field was sent through the
pit lane, and OpenF1 starts a new tyre stint at every pass through it. That made drive-throughs
look like tyre changes in the timing tower, the race feed and the pit stop list. A stint on the
same compound whose tyre age carries straight on (to within a lap, because of the timing-line
quirk above) is folded into the one before; stop-and-go penalties go the same way.

**A stop on lap 1 read as a pit-lane start.** When a car pits at the end of the first lap (often
under a lap-1 safety car, as in Jeddah 2025, or for a cheap first stop in Monaco 2025, where two
were compulsory), OpenF1 can end its first tyre stint at lap 0 and start the next on lap 1, which
is what a pit-lane start looks like. Twenty-two saved races lost one or more stops this way. OpenF1's
pit-out flag tells the two apart: a pit-lane start leaves the pits on lap 1, these cars only on
lap 2. Tyres changed in the pit lane while the race is stopped under a red flag aren't counted as
stops either, as in F1's own pit stop summaries.

**Fastest laps.** Officially any lap counts, and GridPulse had been stricter. Norris's fastest lap
in Australia 2025 was the lap he pitted at the end of, and leaving in-laps out had given it to
Lawson. Alonso's in China 2024 and Norris's in Qatar 2024 were laps on which a VSC came out near
the end, and leaving out every lap with a neutralisation on it had given both to Verstappen. Only
laps run into a red flag (and glitch times) are left out now. A disqualified driver's laps are
struck from the season tables with the rest of their result (Hamilton's quickest lap in China
2025). The championship check below is what found these.

**No pit data at all.** OpenF1 has tyre stints but no pit records for the first six races of
2023, and loading them crashed. Stops are now worked out from the stint changes, with the pit
lane time left unknown and the Pit stops view saying so.

**A results API that sometimes doesn't answer.** For archive races FastF1 takes positions and
statuses from the Ergast/Jolpica API. When that times out, the classification comes back empty
or with blank statuses, and every lapped car looked retired. GridPulse now fills the
classification from OpenF1 where it has the race. Otherwise it fails with "try again in a
minute"; failed loads aren't cached, so the next attempt retries.

**Data that isn't there.** OpenF1 has only 55% of the laps of the 2025 Miami Grand Prix. The
final order still checks out, but the replay can't be right on the missing laps, so any race
with less than 95% of its laps carries a warning above the replay.

## The championship tables

The Season, Teams and Drivers pages add up points from the saved races. F1's archive gives the
points; OpenF1 doesn't, so they're worked out from the results, including the sprints and, from
2019 to 2024, the point for the fastest lap. The final drivers' and constructors' standings for
2023, 2024 and 2025 come out exactly as the official ones, which also checks every scoring
fastest lap. That's a test in `tests/test_standings.py`, run on the saved races in CI.

## What the check doesn't cover

- The order mid-race is only checked through what it does at the flag. Gaps mid-race come from
  lap end times. On the 2026 Singapore Grand Prix, which both sources have, OpenF1 and F1's
  archive agree to within about 0.2 s.
- There's no official list of pit stops to check against. The timing tower, the race feed and
  the Pit stops view now count stops from the same list, so at least they agree with each other.
- Stationary times only exist where F1 published them, which is patchy from 2024 on.
- OpenF1 doesn't always mark a pit-lane start: Verstappen started the 2025 São Paulo Grand Prix
  from the pit lane, and the saved race still has him on the grid slot he qualified in (16th).
  Races from F1's archive show a pit-lane start as such.
- Pole goes to the car that starts first, as F1 credits it: after a grid penalty that isn't the
  fastest qualifier (Verstappen was fastest in Belgium in 2023 and 2024 and in Qatar 2024).
  Qualifying stands in where the starting grid isn't known.

## The same idea for the pit window

The pit window model is tested the same way, against what teams did. `gridpulse pitwindow` takes
every driver's last green-flag stop in a season. It fits the tyre model only on the laps up to
ten laps before the stop, asks for the best lap to stop, and compares that with the lap the team
chose. A rule of thumb that needs no model serves as the baseline: split the remaining laps
evenly between the two stints.

| Season | Stops | Model within 5 laps | Rule of thumb within 5 laps | Real stop inside the model's window |
|---|---|---|---|---|
| 2024 | 303 | 66% | 62% | 54% |
| 2025 | 322 | 59% | 57% | 51% |

These figures use the replay boundary throughout: the clean-lap filter is rebuilt on the known
laps at each prediction, and a pit loss is only available after its out-lap. A future fastest
lap cannot change which early laps the model treats as representative. Replay attack/defence
charts are also clipped at the selected lap. The one-second pit window measures the cost of
alternative plans, not a statistical confidence interval.

The first version of the model lost to the rule of thumb (median error 9 laps). It took the fuel
correction as a fixed 0.06 s a lap, and wherever that was wrong the error leaked into the tyre
wear estimate, which the best stopping lap is very sensitive to. Fitting fuel and track evolution
as one trend alongside the wear, and holding the wear estimates close to typical values unless a
race gives strong evidence otherwise, brought it to a median of 4 laps, a little better than the
rule of thumb in both seasons. A model that only knows tyres and pit loss can't do much better,
because teams also stop on traffic, undercut threats, safety cars and rules: Qatar 2025 had a
25-lap limit per set, and Monaco 2025 required two stops.
