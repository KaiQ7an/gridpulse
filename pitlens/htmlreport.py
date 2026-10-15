"""Self-contained HTML reports: a title, some text, tables and plotly charts."""

import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

STYLE = """
:root { color-scheme: light dark; --ink: #1d1d1f; --muted: #6b6b6b; --bg: #ffffff; --rule: #e6e6e6; }
@media (prefers-color-scheme: dark) { :root { --ink: #f2f2f2; --muted: #a0a0a0; --bg: #111214; --rule: #2a2b2e; } }
body { font-family: -apple-system, system-ui, sans-serif; color: var(--ink); background: var(--bg);
  max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 1.6rem; margin-bottom: 4px; } h2 { margin-top: 32px; }
p { color: var(--muted); margin-top: 0; }
.table { overflow-x: auto; }
table { border-collapse: collapse; margin: 12px 0; font-variant-numeric: tabular-nums; }
th, td { padding: 6px 12px; border-bottom: 1px solid var(--rule); text-align: left; white-space: nowrap; }
"""


def table(df: pd.DataFrame) -> str:
    return f'<div class="table">{df.to_html(index=False, border=0, na_rep="")}</div>'


def text(s: str) -> str:
    return f"<p>{html.escape(s)}</p>"


def write_report(path: Path, title: str, subtitle: str, sections: list[tuple[str | None, list]]) -> None:
    """Write `sections` (heading, [html strings or plotly figures]) to one HTML file.

    plotly.js is embedded once so the file works offline.
    """
    parts, first_chart = [], True
    for heading, blocks in sections:
        if heading:
            parts.append(f"<h2>{html.escape(heading)}</h2>")
        for block in blocks:
            if isinstance(block, go.Figure):
                # Mid-grey text reads on the page's light and dark backgrounds alike.
                block = go.Figure(block).update_layout(template="plotly_white", font_color="#80858F")
                parts.append(block.to_html(full_html=False, include_plotlyjs=first_chart))
                first_chart = False
            else:
                parts.append(block)
    body = "\n".join(parts)
    path.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>
<h1>{html.escape(title)}</h1>
<p>{html.escape(subtitle)}</p>
{body}
</body></html>""",
        encoding="utf-8",
    )
