"""One look for every plotly chart: transparent, quiet grid, Inter, small ticks.

Colours are translucent greys so the same figure reads on light and dark
backgrounds; Streamlit's theme supplies the text colour.
"""

import plotly.graph_objects as go

FONT = "Inter, -apple-system, system-ui, sans-serif"
GRID = "rgba(128,128,128,0.14)"
AXIS = "rgba(128,128,128,0.35)"


def apply(fig: go.Figure, height: int | None = None) -> go.Figure:
    fig.update_layout(
        font=dict(family=FONT, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(font=dict(family=FONT, size=12)),
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color=AXIS, activecolor="#E10600"),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticks="", tickfont=dict(size=11),
                     title_font=dict(size=11), title_standoff=8)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticks="", tickfont=dict(size=11),
                     title_font=dict(size=11), title_standoff=8)
    if height:
        fig.update_layout(height=height)
    return fig
