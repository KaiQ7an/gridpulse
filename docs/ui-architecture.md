# UI module boundaries

Page modules choose data and controls. They compose small presentation modules rather than
adding domain renderers or static style blocks to `ui.py`.

| Module | Owns | Depends on |
| --- | --- | --- |
| `ui.py` | Headers, status strips, sidebar navigation, notes, driver dots and tyre marks | Branding, styles, navigation decoration |
| `tables.py` | Pit stops, qualifying, teammate cards, driver results, standings, result matrices and circuit history | `ui.py` primitives and prepared DataFrames |
| `styles.py` | Loading application-owned CSS files through `st.html(Path(...))` | Streamlit and packaged `assets/` files |
| `assets/pitwall.css` | Shared page layout, identity badges and presentation of UI primitives and tables | Application classes and scoped widget decoration |
| `assets/atlas.css` | Circuit cards, record typography and atlas hover/focus feedback | Shared by Formula 1 and DTM |
| `assets/home.css` | Landing-page layout, series covers and local photo fallbacks | Home's own classes |
| `learn_page.py` / `assets/learn.css` | Three-step newcomer lesson and replay explanation presentation | Saved race, shared explanations and native controls |
| `explain.py` | Current-lap situation, shared tyre-model context and same-compound timing comparisons | Race data and strategy functions; no UI state |
| `assets/teams.css` | DTM team directory cards, brand accents and responsive rows | Application-owned directory markup |
| `dtm_teams.py` | Compact selected-season team cards and profile/driver links | DTM rows, sourced marks and styles |
| `driver_picker.py` | Optional team metadata and colour decoration on native selectors | Streamlit selectors rendered by their page |

The dependency direction is **page → table → primitive**. `ui.py` does not import page or table
renderers. DTM loads atlas CSS directly; it does not import the Formula 1 circuits page to get styles.

CSS files and the original Dörr and Seyffarth logo images are setuptools package data. The wheel
must include them alongside the Python modules; running an editable checkout alone does not
verify that delivery path.

Table renderers receive already prepared rows. They do not fetch data, change replay state or
calculate championship rules. Replay visibility and statistical decisions stay in the data/view layers.
Shared number formatting is public (`ui.lap_time`) rather than an imported private table helper.

DTM's primary standings use a semantic HTML table so the live theme applies equally to names and scores.
The native detailed DataFrame and CSV retain every published field and sorting/export tools. All names
and team text are escaped before HTML rendering. Guide calculations share the replay's model and stop
planner; an experiment changes stop timing while holding the driver, fresh compound and pit loss fixed.

## Native selectors and decoration

The actual controls remain Streamlit selectors: their option labels, selected values, search and
keyboard behaviour do not depend on the CSS. Team metadata and coloured chips still use
Streamlit-specific DOM selectors. They are isolated in `driver_picker.py`; they have not been
replaced by a custom JavaScript picker or claimed to be free of DOM assumptions.

When updating Streamlit, verify full-name labels, right-aligned teams and selected-chip colours
in both themes. A decoration mismatch should lose presentation only, while the native control
continues to select and search the original driver options.

## Verification of the extraction

The eight moved table renderers were compared with the previous implementation using saved 2025
race, qualifying, driver, team and circuit-history data. Their emitted HTML matched exactly,
including replay links. Position cells also retained podium, points, retirement, disqualification,
pole and fastest-lap markers. Existing application tests cover the pages that compose them.

## Browser memory and small screens

`browser_memory.py` uses Streamlit's public v2 component API to read and write one versioned,
origin-local `localStorage` record. Hydration restores non-widget copies only; native widget state and
explicit URL selections take priority. The write waits for the read acknowledgement, so an empty
initial Python session cannot wipe a previous visit. The replay fragment writes after its current lap
and focus have been saved. The other pages write after rendering.

Only replay selections, DTM selections/followed entries, four weekend pins and radar controls are
allowlisted. Payload size, field types, ranges and list lengths are bounded. Future-result switches
are excluded and restored replays enable spoiler protection. Missing/blocked storage falls back to
the current session. Forget removes the selections and retains only a disabled-memory marker; it
stays off across reloads until enabled again. Storage is per origin/device; concurrent tabs use the
last writer, with no cross-device sync or server-side profile.

Responsive CSS keeps the primary standings' name and points columns visible while detailed metadata
remains in the native full table. At phone width the replay's selected analysis precedes the timing
tower. That ordering has one scoped Streamlit column selector in `pitwall.css`; verify it on framework
upgrades. Native expandable timing help makes compound names, tyre ages and gaps available without
hover. Layout checks cover 390px and desktop widths; they are not a claim of a complete device lab.

`dtm/impact.py` reconstructs points through a selected round from race-row totals, which already
include qualifying. It never reads later results or the final standings. Missing allocations withhold
cumulative totals/rank movement; equal points share a rank. The UI explicitly distinguishes this
reconstruction from official countback and administrative adjustments.
