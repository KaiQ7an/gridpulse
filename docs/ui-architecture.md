# UI module boundaries

Page modules choose data and controls. They compose small presentation modules rather than
adding domain renderers or static style blocks to `ui.py`.

| Module | Owns | Depends on |
| --- | --- | --- |
| `ui.py` | Headers, status strips, sidebar navigation, notes, driver dots and tyre marks | Branding, styles, navigation decoration |
| `tables.py` | Pit stops, qualifying, teammate cards, driver results, standings, result matrices and circuit history | `ui.py` primitives and prepared DataFrames |
| `styles.py` | Loading application-owned CSS files through `st.html(Path(...))` | Streamlit and packaged `assets/` files |
| `assets/pitwall.css` | Shared page layout and presentation of UI primitives and tables | Application classes and scoped widget decoration |
| `assets/atlas.css` | Circuit cards, record typography and atlas hover/focus feedback | Shared by Formula 1 and DTM |
| `assets/home.css` | Landing-page layout, series covers and local photo fallbacks | Home's own classes |
| `driver_picker.py` | Optional team metadata and colour decoration on native selectors | Streamlit selectors rendered by their page |

The dependency direction is **page → table → primitive**. `ui.py` does not import page or table
renderers. DTM loads atlas CSS directly; it does not import the Formula 1 circuits page to get styles.

All three CSS files are setuptools package data. The wheel must include them alongside the Python
modules; running an editable checkout alone does not verify that delivery path.

Table renderers receive already prepared rows. They do not fetch data, change replay state or
calculate championship rules. Replay visibility and statistical decisions stay in the data/view layers.
Shared number formatting is public (`ui.lap_time`) rather than an imported private table helper.

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
