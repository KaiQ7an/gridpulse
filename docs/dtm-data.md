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

The adapter in `pitlens/dtm/data.py` is separate from the Formula 1 loaders and scoring.
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
widget interaction from repeatedly waiting for an unavailable service. `PITLENS_OFFLINE=1`
always uses bundled data and is used by the regression suite.

Refresh a bundled snapshot from the project environment:

```sh
python -m pitlens.dtm.refresh --year 2026
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

## Local preview

Start the existing Python app with `pitlens pitwall`, then open
`http://localhost:8501/dtm`. MAMP Pro's Apache/PHP document root does not execute Streamlit;
if using a MAMP virtual host as the front end, proxy HTTP **and WebSocket upgrades** to
the Streamlit service. A document-root change alone is insufficient.
