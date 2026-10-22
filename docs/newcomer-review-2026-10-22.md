# Newcomer experience pass · 22 October 2026

The first visit now offers a short, optional guided example before asking the visitor to choose
an unfamiliar series or interpret a strategy plot. Existing expert tools remain accessible.

## Delivered path

1. Home explains what Formula 1 and DTM offer and links to `/learn`.
2. The guide identifies Charles Leclerc/Ferrari and Oscar Piastri/McLaren at Hungary 2025 lap 18,
   using the current timing tower for positions and their gap. It explains the pit-stop trade-off.
3. The visitor switches between a lap-19 stop and a lap-21 stop on the same fresh compound.
   The immediate estimate explains what changed, why tyre ages matter, and the model's limits.
4. A recap retains the tried choice and links into the same lap, focus drivers and spoiler-free replay.
   Reading the guide does not overwrite an existing replay's saved selections.

The full replay now puts a current-lap explanation before detailed status cards. A native HTML
disclosure there explains timing, tyre and neutralisation terms. Full names appear in focus
selectors, the strategy driver selector and the animated tower; driver codes remain stable in URLs.
Narrow tower cards prioritise names and gaps over secondary columns. Hover retains identity and tyre details.

DTM's primary standings are a semantic table with equally readable names and points in both themes.
Detailed native tables and CSV exports retain all fields. Rules and the distinction between drivers,
teams and manufacturers live in a help popover next to the category selector. A driver-points gap
is compared with the 2026 race-win score without presenting it as a title prediction. Provisional
classification and source timestamps remain available. 2026-specific scoring is not applied to older seasons.

## Review and boundaries

- Both interfaces use the same model preparation and stop planner. Fitting reads only completed
  laps; current-lap stop measurements are withheld until the out-lap is known.
- The experiment compares relative model time for the same driver/compound. It does not predict
  a rival's response, traffic, future safety cars or tyre-stock availability, nor claim the optimal real strategy.
- A future-lap mutation test checks that changing unseen pace leaves the lesson estimate and
  current-lap explanation unchanged. Wet, finished and unknown-driver cases do not invent stop plans.
- Review consolidated duplicate stop-planning logic and moved DTM introductory copy into a popover
  after visual inspection showed that default-expanded explanations pushed scores too low.
- Full suite: 297 passing tests. Focused checks were rerun after the final presentation and planner
  consolidation. Ruff and whitespace checks passed.

MAMP PRO's local Apache site was configured and its HTTP-to-HTTPS forwarding tested through
the real home → guide → changed stop decision flow. The local hostname is not a public deployment.
See [local setup](local-mamp.md). Home and replay documentation captures were refreshed from the app.
