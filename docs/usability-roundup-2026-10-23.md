# Usability roundup · 23 October 2026

Six follow-ups to the first-visit guide, delivered as one release:

- The guide compares two tyre-use timelines, shows tyre ages at each stop and marks the
  selected plan. Relative time comes from the same lap-18 model as the workbench. The bars
  are labelled as lap allocation, never invented on-track positions or race-result predictions.
- Strategy keeps its current decision visible. Rival radar, past battles and optional chart
  overlays are in native expandable sections. The model's limits remain beside the result.
- At phone widths, the selected replay analysis precedes the tall timing tower. Standings
  retain name and points, with other columns still in the full table. Expandable timing help
  provides full tyre names and gap explanations without hover.
- DTM weekends show points earned, points-only rank movement and the same two leaders' gap
  before/after the weekend. Race totals already include qualifying: they are counted once.
  Ties share rank; missing races/allocations suppress cumulative totals. This is a published
  allocation reconstruction, not an assertion of official intermediate countback or deductions.
- Browser-local memory preserves pins, replay and DTM selections, followed DTM entries and
  radar controls. It waits for hydration, validates a bounded allowlist, respects explicit links
  and restores spoiler protection. Forget clears selections and persists an opt-out marker.
- Replay charts, feed, radar, sector/status labels, Onboard and qualifying display names where
  metadata is available. Driver codes remain internal IDs. Chart callbacks keep their original
  customdata fields; extra hover identity is appended only when needed.

## Validation

Automated coverage exercises future-data invariance, qualifying double counting, ties,
new entrants, missing/non-finite allocations, malformed browser memory, preservation of
active selections, and stable chart callback IDs. Existing replay and selected-lap tests remain.

Browser checks use the MAMP proxy at `https://gridpulse.localhost:8890/`: guide interaction,
refresh-retained pins, persistent forget/disable and re-enable controls, a new-session DTM resume, explicit Hungary lap-18 deep link,
390px analysis ordering, and 320px standings identity/points visibility. These are responsive
browser checks, not comprehensive real-device or assistive-technology certification.

No strategy fit, backtest benchmark or race-outcome claim changes in this release. Browser memory
is origin-local and last-writer-wins across tabs; it is not cross-device sync. DTM cumulative
reconstruction cannot apply unpublished separate administrative adjustments or countback.

A restored zero radar cost is explicitly converted to float: browser JSON serializes `0.0`
as `0`, and native numeric controls require a consistent floating-point type.
