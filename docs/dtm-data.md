# DTM data coverage

GridPulse's `/dtm` section covers the 2023–2026 DTM seasons. It uses the public JSON
feeds requested by the official [results](https://www.dtm.com/en/results) and
[standings](https://www.dtm.com/en/standings) pages, served at `https://api.dtm.com/data`:

| Query | Use |
| --- | --- |
| `wigeResults` | Practice, qualifying and race classifications |
| `wigeStandings` | Published driver, team and manufacturer order and points |
| `eventsRacetrack` | Calendar, country, circuit length and official event links |
| `driversShort` | Driver name spelling |

The adapter in `gridpulse/dtm/data.py` is separate from the Formula 1 loaders and scoring.
No account, credential or private API is used. Feed availability and schema are not guaranteed.

## Interpretation

- Official championship positions are retained, including tie breaks and penalties.
  Points are read directly, with race and qualifying contributions displayed separately.
  Manufacturer and team points are not inferred by summing driver points.
- The per-race `points` fields in standings are allocations. The chart sums those allocations;
  it does not sum the already cumulative official totals. Tests reconcile every chart endpoint
  against every published standings row in all four saved seasons.
- Race 1 and Race 2 remain distinct. Norisring qualifying groups remain distinct too;
  group P1 does not imply overall pole, and qualifying results do not imply a starting grid.
- Multiple revisions of the same session are replaced in feed order, matching the official
  website's handling. In particular, the later 2025 Zandvoort Race 2 classification contains
  the Dörr/Glock disqualifications and Wittmann's revised time gap. The 2024 Zandvoort Race 1
  duplicate is counted once. Manufacturer spelling variants (BMW M/BMW-Motorsport, Mercedes,
  Audi-Sport, McLaren capitalisation) are grouped under a consistent manufacturer name.
- DNF, DNS and DSQ remain visible. Classified-finish statistics and charts exclude them.
  Empty positions, times and gaps stay missing. The best lap comes from the classification,
  excludes DSQ/DNS, and is not an average pace estimate or a circuit record.
- Calendar dates come from the event catalogue. Some result documents contain contradictory
  end dates (for example the 2026 Hockenheim result metadata), so they are not used as the calendar.
- A snapshot records when it was fetched, not when a steward last revised the result.
  Provisional status is retained case-insensitively. No championship winner is inferred.
- Manufacturer chart colours are GridPulse's display palette, not official livery specifications.

## Availability and updates

The current season checks the official feeds with a 30-minute shared cache. Historical seasons
use the bundled snapshots by default. **Refresh official data** retries any supported season.
All four feed requests have bounded timeouts; invalid or failed responses fall back to the saved
snapshot with a visible message and timestamp. Failed fetches are cached too, preventing every
widget interaction from repeatedly waiting for an unavailable service. `GRIDPULSE_OFFLINE=1`
always uses bundled data and is used by the regression suite.

Refresh a bundled snapshot from the project environment:

```sh
python -m gridpulse.dtm.refresh --year 2026
pytest -q tests/test_dtm.py
```

The refresh writes atomically after validating all feeds; it does not overwrite a saved season
with an empty response. Snapshot JSON is included in the Python package distribution.

## Limits

This adapter has classifications, not a lap-by-lap telemetry feed. It does not provide race replay,
tyre strategy simulation, throttle/brake traces, qualifying-grid reconstruction or inferred poles.
Driver summary identities use the latest saved race; individual result tables retain the team
and manufacturer at that event. Historical identity changes are not a claim that a driver drove
the same car throughout the season.

## Team profiles, photographs and driver introductions

`gridpulse/dtm/cars.json` identifies GT3 models by season and manufacturer, using the official
entry lists and driver catalogue, with links retained for each season. It distinguishes the
2025 BMW M4 GT3 Evo and the 2026 Ferrari, Ford, Porsche and Lamborghini upgrades. Unknown
models remain unconfirmed rather than borrowing a model from another year. Model names
are added at presentation time, so refreshing classification snapshots cannot erase them.

Reference photographs link directly to their publisher. Team sources (Manthey, Emil Frey,
Schubert, HRT, Comtoyou, Dörr and ABT) take priority; DTM and manufacturer imagery fills gaps.
The caption identifies these as model references: a picture does not identify every driver's
exact livery. Image copyrights remain with their respective owners. External images are
loaded lazily and are not required to load the local result data or introductions.

Driver facts are saved separately in `gridpulse/drivers/`. DTM birthday, nationality, debut and
season portraits come from the official driver-detail feed; missing birthdays and portraits
are displayed as unpublished. F1 facts use official F1 profiles and the Jolpica historical
driver/result records. F1 debut refers to a first race result, not a first practice appearance
(Antonelli raced from 2025; Lindblad from 2026). Career introductions are concise original
summaries with sources. Biographies describe the driver as known when researched, while
team and car associations are taken from the selected season's results. Current F1 portraits
are labelled explicitly, as clothing may belong to a different season.

`gridpulse/dtm/teams.json` stores sourced operating-team profiles. `teams.identity()` resolves
sponsor names per season: MANN-FILTER is Landgraf in 2023, Winward from 2024 onward.
The Teams directory is built from that season’s race entrants, including guests absent from
the official team standings. It never rewrites official championship positions or points.
Historical honours are dated and filtered through the selected season. Founding dates describe
the stated operation, not necessarily a parent company. Missing verified facts stay blank.
Team-published photos are preferred, with source links. Other images are explicitly model
references, not a claim about the selected team’s exact livery.

## Local preview

Start the existing Python app with `gridpulse pitwall`, then open
`http://localhost:8501/dtm`. MAMP Pro's Apache/PHP document root does not execute Streamlit;
if using a MAMP virtual host as the front end, proxy HTTP **and WebSocket upgrades** to
the Streamlit service. A document-root change alone is insufficient.

## First points and first wins

`gridpulse/milestones.json` keeps sourced milestones independently of the saved season snapshots.
F1 uses Grand Prix results: sprint wins are not presented as GP wins, disqualifications cannot
supply a points milestone, and constructor name changes are explicitly scoped. Historical
McLaren engine-suffixed identities are combined; modern Williams starts in 1977, modern
Mercedes in 2010, and the present Aston Martin team in 2021.

DTM first points includes qualifying awards. Published zero-point guest results do not count
as points finishes (for example Bortolotti’s 2021 Assen podium). The official result archive
is available from 2020; older career firsts require a separate primary reference. Records carry
`verified_first` per milestone, so an earliest available 2020 result is never called a career
first for a driver who debuted earlier. Unverified older milestones display as unverified,
not as zero wins or points. Selecting a historical season hides later milestones.


## Circuit atlas

`gridpulse/dtm/circuits.json` holds sourced venue background and official DTM layout diagrams for
the eight venues on the supported 2023–2026 calendars. The atlas reuses the F1 map component
with DTM-specific labels and markers. Circuit length follows the selected DTM event feed;
Spielberg uses the sourced 4.326 km reference when the feed has no length. Nürburgring is the
3.629 km sprint layout, not the F1 Grand Prix layout or Nordschleife.

Records cover bundled 2023 data through the selected season, using live results for the selected
season when available. They are labelled archive bests, not all-time DTM records. DSQ/DNS results
cannot supply a fastest race lap; DNF fastest laps can. Wins use classified P1 finishers.
Qualifying P1 counts use combined classifications only; group winners are excluded, and the
page explicitly notes this incomplete pole coverage. Layout changes across years also limit
comparisons. Venue opening dates describe the venue's heritage, not necessarily the present layout.

Manufacturer standings show car-entry counts alongside official points. Counts use distinct
operating-team, car-number and manufacturer combinations across published race classifications,
including guest entries; replacement drivers do not add a car. They describe season participation,
not the number of starters in any single race. Manufacturer points take the best two cars per
brand per race and exclude qualifying bonuses; the UI links to the official explanation.
