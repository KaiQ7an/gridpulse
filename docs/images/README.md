# UI previews

Home and replay previews were refreshed on **19 October 2026**; the remaining previews were captured
on 18 October. Captures use the browser's default 1280 × 720 viewport and the app's Light/Dark theme controls.
They are actual browser captures; the files are stored as PNG without retouching the interface.

| Files (light/dark) | Page and selections |
| --- | --- |
| `home_*.png` | `/`, clean browser session; results hidden |
| `pitwall_*.png` | `/replay?year=2025&round=4&lap=23&drivers=HAM,LEC&view=Gaps&mode=replay`, top of page |
| `strategy_*.png` | Same race, lap and drivers; `view=Strategy`, scrolled to the window and curve |
| `pitstops_*.png` | Same race, lap and drivers; `view=Pit%20stops`, scrolled to the stop table |
| `onboard_*.png` | `/onboard?year=2026&round=17&session=Q&drivers=VER,LEC`, fastest valid laps; scrolled to telemetry |

When refreshing a preview, wait for data and charts to finish rendering, close the theme menu,
keep the replay paused and preserve the same selections in the paired images. Verify that the
timeline matches the selected theme and that the header and sidebar show GridPulse.

`pace_by_driver.png` and `stint_degradation.png` are static analysis exports rather than interface
screenshots. Their source is the CLI report workflow described in the main README.
