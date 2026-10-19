# Usability review: 19 October 2026

This pass prioritizes reading a result and finding an analysis, without adding another tool.

- Home explains three tasks: replay an F1 decision, compare laps, or catch up on DTM results.
  Featured links show the decision question; race/year/lap remain secondary context.
- DTM standings put position, name and total score first and pin those columns. Team is the
  only additional default driver column; vehicle metadata and point breakdowns are expandable.
  The full CSV remains available. Season counts use one line instead of five separate cards.
- F1 navigation stays above filters. Home, Championship and Replay are primary; supporting
  pages are grouped under More Formula 1 pages; low-frequency season/archive controls are collapsed,
  leaving event and driver selectors visible. In replay, Gaps, Strategy, Tyres and Order
  occupy one row, with Pit stops, Pace, Radio and Messages in a native More selector.
  Old `view=Positions` and supporting-view deep links retain their meaning.
- The event timeline starts collapsed. Fastest sectors and weather remain available in the
  compact status strip. Supporting text uses explicit theme-aware colours instead of low opacity.
- DTM opens saved classifications before any network request. Refresh data checks the official
  feed, preserving the displayed fetched time and provisional status. Replay and DTM show a
  named loading state while reading data; this does not eliminate Community Cloud's cold boot.
- DTM circuits start with Europe, retaining an optional world map. The map responds to the
  app's light/dark theme; no globe rotation is needed to reach the season's eight venues.
  Marker navigation is deferred until the next render before selectors are instantiated,
  fixing the state exception that previously affected map clicks but not the list buttons.
- Strategy conclusions are labelled model estimates and display their exclusions. Agreement
  with a team's actual stop is not evidence that the stop was optimal.

## Venue naming: an important distinction

The reported “Bahrain / Kuala Lumpur” mismatch is an incomplete display name, not a wrong host
location in the saved 2026 race. F1's [26 July 2026 announcement](https://corp.formula1.com/formula-1-and-fia-confirm-that-malaysia-will-join-the-2026-calendar-as-host-venue-for-the-bahrain-grand-prix/)
identifies Sepang as the host of the **Bahrain Grand Prix in Malaysia**, held on 2–4 October.
The [official race classification](https://www.formula1.com/en/results/2026/races/1308/bahrain/race-result)
uses that event name too.

The UI adds the Malaysia suffix only for the matching 2026 event and Kuala Lumpur venue. Home
displays Sepang International Circuit / Malaysia and links the announcement. Replay and session
menus use the contextual display name. Raw snapshots, timing and historical Bahrain names are
unchanged. Venue labels use the saved circuit identity, rather than guessing from an event name.

## Verification

`tests/test_product_basics.py` covers venue context without source mutation, saved-first DTM loading,
pinned name/score columns, primary/More replay state and deep links, and the Europe default with
an explicit world-link override. Existing application tests exercise every replay view, cross-page
state, unavailable sessions and DTM circuit navigation. Visual checks use the normal 1280 × 720
browser viewport, including both themes and a standings table with no horizontal scroll required
to read the driver and score.
