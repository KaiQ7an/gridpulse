"""Interactive plotly charts for the pit wall dashboard.

Focus drivers are drawn in their team colour (the second driver of a team
dashed); everyone else stays a thin grey line for context.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from pitlens.style import COMPOUND_COLORS, COMPOUND_ORDER, COMPOUND_SYMBOLS

CONTEXT_GREY = "rgba(150,150,150,0.35)"
HEIGHT = 420


def _layout(fig: go.Figure, total_laps: int, **kwargs) -> go.Figure:
    fig.update_layout(
        height=HEIGHT,
        margin=dict(l=10, r=45, t=30, b=10),  # right margin leaves room for end-of-line labels
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
        **kwargs,
    )
    fig.update_xaxes(title="Lap", range=[0.5, total_laps + 0.5], showgrid=False)
    return fig


def _line_styles(focus: list[str], colors: dict[str, str]) -> dict[str, dict]:
    styles, seen_colors = {}, set()
    for driver in focus:
        color = colors.get(driver)
        styles[driver] = {"color": color, "width": 2.5, "dash": "dash" if color in seen_colors else "solid"}
        seen_colors.add(color)
    return styles


def _driver_lines(df: pd.DataFrame, y: str, focus, colors, hover: str) -> go.Figure:
    fig = go.Figure()
    styles = _line_styles(focus, colors)
    others = [d for d in df["Driver"].unique() if d not in styles]
    for driver in others + list(styles):  # focus drivers drawn last, on top
        d = df[df["Driver"] == driver].sort_values("LapNumber")
        if d.empty:
            continue
        is_focus = driver in styles
        fig.add_trace(
            go.Scatter(
                x=d["LapNumber"],
                y=d[y],
                mode="lines",
                name=driver,
                line=styles[driver] if is_focus else {"color": CONTEXT_GREY, "width": 1},
                showlegend=is_focus,
                hovertemplate=f"<b>{driver}</b><br>Lap %{{x}}<br>{hover}<extra></extra>",
            )
        )
        if is_focus:  # label the end of each focus line so identity isn't colour-only
            last = d.iloc[-1]
            fig.add_annotation(
                x=last["LapNumber"], y=last[y], text=driver, showarrow=False, xanchor="left", xshift=6,
                font=dict(size=11, color=styles[driver]["color"]),
            )
    return fig


PERIOD_STYLE = {"Safety car": ("SC", "rgba(240,180,0,0.18)"), "VSC": ("VSC", "rgba(240,180,0,0.10)"), "Red flag": ("RED", "rgba(225,6,0,0.15)")}


def shade_periods(fig: go.Figure, periods) -> go.Figure:
    """Shade safety car, VSC and red flag laps behind the lines."""
    for status, first, last in periods:
        label, color = PERIOD_STYLE[status]
        fig.add_vrect(
            x0=first - 0.5, x1=last + 0.5, fillcolor=color, line_width=0, layer="below",
            annotation_text=label, annotation_position="top left", annotation_font_size=10,
        )
    return fig


def gap_chart(gaps: pd.DataFrame, focus, colors, total_laps: int) -> go.Figure:
    """Race trace: seconds behind the leader, lap by lap (leader on top)."""
    fig = _driver_lines(gaps, "Gap", focus, colors, "+%{y:.1f} s to leader")
    focus_gaps = gaps.loc[gaps["Driver"].isin(focus), "Gap"]
    if focus_gaps.empty:
        fig.update_yaxes(autorange="reversed")
    else:
        # Scale to the focus drivers; lapped back-markers would flatten everyone else.
        top = max(focus_gaps.max(), 5) * 1.15
        fig.update_yaxes(range=[top, -0.04 * top])
    fig.update_yaxes(title="Gap to leader (s)", zeroline=False)
    return _layout(fig, total_laps)


def position_chart(laps: pd.DataFrame, focus, colors, total_laps: int) -> go.Figure:
    df = laps.dropna(subset=["Position"])
    fig = _driver_lines(df, "Position", focus, colors, "P%{y:.0f}")
    n = int(df["Position"].max()) if not df.empty else 20
    fig.update_yaxes(title="Position", autorange=False, range=[n + 0.5, 0.5], dtick=1)
    return _layout(fig, total_laps)


def strategy_chart(stints: pd.DataFrame, order: list[str], total_laps: int) -> go.Figure:
    """Tyre stints per driver as horizontal bars, in running order."""
    fig = go.Figure()
    for compound in COMPOUND_ORDER:
        s = stints[stints["Compound"] == compound]
        if s.empty:
            continue
        fig.add_trace(
            go.Bar(
                y=s["Driver"],
                x=s["Laps"],
                base=s["StartLap"] - 0.5,
                orientation="h",
                name=compound.title(),
                marker=dict(color=COMPOUND_COLORS[compound], line=dict(color="rgba(255,255,255,0.9)", width=2)),
                customdata=s[["Stint", "StartLap", "EndLap", "StartAge"]],
                hovertemplate=(
                    "<b>%{y}</b> stint %{customdata[0]}<br>"
                    f"{compound.title()}, laps %{{customdata[1]}}–%{{customdata[2]}}"
                    "<br>%{x} laps, started at age %{customdata[3]}<extra></extra>"
                ),
            )
        )
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)), title=None)
    fig = _layout(fig, total_laps)
    fig.update_layout(height=max(HEIGHT, 24 * len(order) + 80))
    return fig


def pace_chart(clean: pd.DataFrame, focus: list[str], total_laps: int) -> go.Figure:
    """Clean lap times of the focus drivers, one panel each, marked by compound."""
    df = clean[clean["Driver"].isin(focus)].copy()
    df["Compound"] = pd.Categorical(df["Compound"], categories=COMPOUND_ORDER)
    fig = px.scatter(
        df,
        x="LapNumber",
        y="LapTime",
        color="Compound",
        symbol="Compound",
        facet_col="Driver",
        facet_col_wrap=min(3, max(len(focus), 1)),
        category_orders={"Driver": focus, "Compound": COMPOUND_ORDER},
        color_discrete_map=COMPOUND_COLORS,
        symbol_map=COMPOUND_SYMBOLS,
        custom_data=["TyreLife", "LapTimeFuelCorr"],
    )
    fig.update_traces(
        marker=dict(size=7),
        hovertemplate="Lap %{x}<br>%{y:.3f} s (fuel-corrected %{customdata[1]:.3f})<br>tyre age %{customdata[0]:.0f}<extra></extra>",
    )
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.for_each_trace(lambda t: t.update(name=t.name.title()))
    rows = -(-max(len(focus), 1) // 3)
    fig = _layout(fig, total_laps)
    # Legend above the facet titles rather than on top of them.
    fig.update_layout(height=280 * rows + 80, margin=dict(t=60), legend=dict(y=0.99, yanchor="top", yref="container"))
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None)
    if not df.empty:
        # Explicit range: plotly's autorange misfires on facets drawn inside a hidden tab.
        lo, hi = df["LapTime"].min(), df["LapTime"].max()
        pad = max((hi - lo) * 0.08, 0.3)
        fig.update_yaxes(range=[lo - pad, hi + pad])
    return fig


def degradation_chart(deg: pd.DataFrame) -> go.Figure:
    """Fuel-corrected degradation per stint, ranked."""
    deg = deg.sort_values("DegPerLap").copy()
    deg["Label"] = deg["Driver"] + " · stint " + deg["Stint"].astype(str)
    fig = go.Figure(
        go.Bar(
            x=deg["DegPerLap"],
            y=deg["Label"],
            orientation="h",
            marker=dict(color=[COMPOUND_COLORS.get(c, COMPOUND_COLORS["UNKNOWN"]) for c in deg["Compound"]]),
            text=deg["DegPerLap"].map(lambda v: f"{v:+.3f}"),
            textposition="outside",
            customdata=deg[["Compound", "StartLap", "EndLap", "CleanLaps"]],
            hovertemplate=(
                "<b>%{y}</b><br>%{customdata[0]}, laps %{customdata[1]}–%{customdata[2]}"
                "<br>%{x:+.3f} s/lap over %{customdata[3]} clean laps<extra></extra>"
            ),
            showlegend=False,
        )
    )
    # Legend entries for the compounds present, since bar colour alone isn't enough.
    for compound in [c for c in COMPOUND_ORDER if c in set(deg["Compound"])]:
        fig.add_trace(go.Bar(x=[None], y=[None], name=compound.title(), marker_color=COMPOUND_COLORS[compound]))
    fig.update_layout(
        height=max(220, 34 * len(deg) + 110),
        margin=dict(l=10, r=40, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        bargap=0.3,
    )
    fig.update_xaxes(title="Seconds lost per lap of tyre age (fuel-corrected)", zeroline=True)
    return fig
