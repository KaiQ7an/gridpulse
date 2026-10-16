"""Interactive plotly charts for the pit wall dashboard.

Focus drivers are drawn in their team colour (the second driver of a team
dashed); everyone else stays a thin grey line for context.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from pitlens import plotstyle
from pitlens.style import COMPOUND_COLORS, COMPOUND_ORDER, COMPOUND_SYMBOLS

CONTEXT_GREY = "rgba(150,150,150,0.35)"
HEIGHT = 460


def _layout(fig: go.Figure, total_laps: int, **kwargs) -> go.Figure:
    fig.update_layout(
        height=HEIGHT,
        margin=dict(l=10, r=45, t=30, b=10),  # right margin leaves room for end-of-line labels
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
        uirevision="keep",  # keep the user's zoom while the replay updates the data
        **kwargs,
    )
    plotstyle.apply(fig)
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


def _spread_end_labels(fig: go.Figure, y_span: float, min_px: float = 15, height: int = HEIGHT) -> None:
    """Nudge apart end-of-line labels that would overlap (cars finishing a few tenths apart)."""
    step = y_span * min_px / (height - 80)  # data units per label, from the plot's height in pixels
    labels = sorted((a for a in fig.layout.annotations if a.xanchor == "left"), key=lambda a: (a.x, a.y))
    prev = None
    for a in labels:
        if prev is not None and a.x == prev.x and a.y - prev.y < step:
            a.y = prev.y + step
        prev = a


PERIOD_STYLE = {"Safety car": ("SC", "rgba(240,180,0,0.18)"), "VSC": ("VSC", "rgba(240,180,0,0.10)"), "Red flag": ("RED", "rgba(225,6,0,0.15)")}


def shade_periods(fig: go.Figure, periods, lap: int | None = None) -> go.Figure:
    """Shade safety car, VSC and red flag laps behind the lines.

    A period still running at `lap` (the right-hand end of the lines) gets no label: it would sit on
    the drivers' end-of-line labels, and the status strip and tower banner already say it.
    """
    for status, first, last in periods:
        label, color = PERIOD_STYLE[status]
        fig.add_vrect(
            x0=first - 0.5, x1=last + 0.5, fillcolor=color, line_width=0, layer="below",
            annotation_text="" if lap is not None and last >= lap - 1 else label,
            annotation_position="top left", annotation_font_size=10,
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
        _spread_end_labels(fig, 1.04 * top)
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
                marker=dict(color=COMPOUND_COLORS[compound], line=dict(color="rgba(128,128,128,0.55)", width=1.5)),
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
    df["Shown"] = df["LapTime"].map(_minutes)
    df["ShownCorr"] = df["LapTimeFuelCorr"].map(_minutes)
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
        custom_data=["TyreLife", "Shown", "ShownCorr"],
    )
    fig.update_traces(
        marker=dict(size=7),
        hovertemplate="Lap %{x}<br>%{customdata[1]} (fuel-corrected %{customdata[2]})<br>tyre age %{customdata[0]:.0f}"
                      "<extra></extra>",
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
        # Lap times read as 1:38.5, not 98.5 s.
        step = 0.5 if hi - lo < 3 else 1.0
        ticks = np.arange(np.ceil((lo - pad) / step) * step, hi + pad, step)
        fig.update_yaxes(tickvals=ticks, ticktext=[_minutes(t, 1) for t in ticks])
    return fig


def _minutes(seconds: float, decimals: int = 3) -> str:
    """98.5 -> "1:38.500" (or "1:38.5" with one decimal)."""
    if pd.isna(seconds):
        return ""
    minutes, rest = divmod(round(float(seconds), decimals), 60)  # round first: 59.95 is 1:00.0, not 0:60.0
    return f"{int(minutes)}:{rest:0{3 + decimals}.{decimals}f}"


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
            cliponaxis=False,
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
    plotstyle.apply(fig)
    # Room either side for the value labels, which sit outside the bars.
    lo, hi = min(float(deg["DegPerLap"].min()), 0.0), max(float(deg["DegPerLap"].max()), 0.0)
    pad = max(hi - lo, 0.02) * 0.22
    fig.update_xaxes(title="Seconds lost per lap of tyre age (fuel-corrected)", zeroline=True,
                     zerolinecolor=plotstyle.AXIS, range=[lo - (pad if lo < 0 else 0), hi + pad])
    return fig


def circuit_map(track: dict) -> go.Figure:
    """The circuit outline (from the race's fastest lap where available), with the start/finish line."""
    from pitlens.onboard.compare import rotate

    x, y = rotate(track["x"], track["y"], track["rotation"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="rgba(128,128,128,0.16)", width=12, shape="spline",
                             smoothing=0.6), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="rgba(150,150,150,0.95)", width=3.5,
                             shape="spline", smoothing=0.6), hoverinfo="skip", showlegend=False))
    # Start/finish: a short bar across the track where the lap begins.
    span = max(float(np.ptp(x)), float(np.ptp(y)))
    dx, dy = x[min(4, len(x) - 1)] - x[0], y[min(4, len(y) - 1)] - y[0]
    norm = float(np.hypot(dx, dy)) or 1.0
    px, py = -dy / norm * span * 0.03, dx / norm * span * 0.03
    fig.add_shape(type="line", x0=x[0] - px, y0=y[0] - py, x1=x[0] + px, y1=y[0] + py,
                  line=dict(color="#E10600", width=4))
    fig.update_layout(height=300, margin=dict(l=8, r=8, t=8, b=8))
    plotstyle.apply(fig)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    return fig


def quickest_stops(stops: pd.DataFrame, colors: dict[str, str], column: str, top: int = 10) -> go.Figure:
    """The quickest stops so far as team-coloured bars, quickest on top. `column` is Stationary or LaneTime."""
    best = stops.dropna(subset=[column]).sort_values([column, "Lap"]).head(top).iloc[::-1]
    labels = best["Driver"] + " · L" + best["Lap"].astype(str)
    fig = go.Figure(
        go.Bar(
            x=best[column],
            y=labels,
            orientation="h",
            marker=dict(color=[colors.get(d, "#999999") for d in best["Driver"]]),
            text=best[column].map(lambda v: f"{v:.1f} s"),
            textposition="outside",
            cliponaxis=False,
            customdata=best[["From", "To"]].fillna("?").apply(lambda c: c.str.title()),
            hovertemplate="<b>%{y}</b><br>%{x:.1f} s<br>%{customdata[0]} → %{customdata[1]}<extra></extra>",
            showlegend=False,
        )
    )
    return _bar_layout(fig, len(best), "Stationary (s)" if column == "Stationary" else "Pit entry to exit (s)",
                       best[column])


def team_stop_times(stops: pd.DataFrame, colors: dict[str, str], teams: dict[str, str], column: str) -> go.Figure:
    """Each team's median stop so far (green-flag and neutralised alike), quickest on top."""
    s = stops.dropna(subset=[column]).assign(Team=lambda d: d["Driver"].map(teams))
    by_team = s.groupby("Team").agg(Median=(column, "median"), Stops=(column, "size"), Driver=("Driver", "first"))
    by_team = by_team.sort_values("Median", ascending=False)
    fig = go.Figure(
        go.Bar(
            x=by_team["Median"],
            y=by_team.index,
            orientation="h",
            marker=dict(color=[colors.get(d, "#999999") for d in by_team["Driver"]]),
            text=by_team["Median"].map(lambda v: f"{v:.1f} s"),
            textposition="outside",
            cliponaxis=False,
            customdata=by_team[["Stops"]],
            hovertemplate="<b>%{y}</b><br>median %{x:.1f} s over %{customdata[0]} stops<extra></extra>",
            showlegend=False,
        )
    )
    return _bar_layout(fig, len(by_team), "Median stationary (s)" if column == "Stationary" else
                       "Median pit entry to exit (s)", by_team["Median"])


def _bar_layout(fig: go.Figure, n: int, title: str, values: pd.Series) -> go.Figure:
    fig.update_layout(height=max(200, 30 * n + 70), margin=dict(l=10, r=50, t=10, b=10), bargap=0.32)
    plotstyle.apply(fig)
    if len(values):
        fig.update_xaxes(range=[0, float(values.max()) * 1.18])  # bars from zero; room for the labels
    fig.update_xaxes(title=title)
    fig.update_yaxes(title=None)
    return fig


def pit_window_chart(window: pd.DataFrame, lap: int, total_laps: int, best, actual: int | None = None,
                     stay_lost: float | None = None) -> go.Figure:
    """Time lost against the best plan by the lap a car stops on, one line per compound it could fit."""
    fig = go.Figure()
    for compound in [c for c in COMPOUND_ORDER if c in set(window["Compound"])]:
        w = window[window["Compound"] == compound]
        fig.add_trace(go.Scatter(
            x=lap + w["LapsMore"], y=w["Lost"], mode="lines", name=compound.title(),
            line=dict(color=COMPOUND_COLORS[compound], width=2.5),
            hovertemplate="Stop at the end of lap %{x}<br>%{y:.1f} s slower than the best plan"
                          f"<extra>{compound.title()}</extra>",
        ))
    fig.add_vrect(x0=lap + best["From"] - 0.5, x1=lap + best["To"] + 0.5, line_width=0, layer="below",
                  fillcolor=COMPOUND_COLORS.get(best["Compound"], "#888888"), opacity=0.12,
                  annotation_text="window", annotation_position="top left", annotation_font_size=10)
    if stay_lost is not None and stay_lost < 20:
        fig.add_hline(y=stay_lost, line=dict(color=CONTEXT_GREY, width=1.5, dash="dash"),
                      annotation_text="no more stops", annotation_position="top right", annotation_font_size=10)
    if actual is not None:
        fig.add_vline(x=actual, line=dict(color="#E10600", width=1.5, dash="dot"),
                      annotation_text=f"actual stop, lap {actual}", annotation_position="bottom right",
                      annotation_font=dict(size=10, color="#E10600"))
    top = min(15.0, float(window["Lost"].max())) if len(window) else 10.0
    fig.update_layout(height=320, margin=dict(l=10, r=20, t=30, b=10), hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    fig.update_xaxes(title="Stop at the end of lap", range=[lap + 0.5, total_laps + 0.5])
    fig.update_yaxes(title="Slower than the best plan (s)", range=[-0.3, max(top, 3.0)], zeroline=True,
                     zerolinecolor=plotstyle.AXIS)
    return fig


def sector_gaps_chart(ideal: pd.DataFrame, order: list[str], dark: bool = True) -> go.Figure:
    """Each driver's best S1, S2 and S3 against the fastest of the session, as a heat map (redder: slower).

    Opaque colours for the page's theme, so plotly can pick readable text for each cell.
    """
    rows = ideal.set_index("Driver").reindex([d for d in order if d in set(ideal["Driver"])])
    gaps = rows[["S1", "S2", "S3"]] - rows[["S1", "S2", "S3"]].min()
    text = gaps.map(lambda g: "fastest" if g == 0 else ("" if pd.isna(g) else f"+{g:.3f}"))
    fig = go.Figure(go.Heatmap(
        z=gaps.to_numpy(), x=["Sector 1", "Sector 2", "Sector 3"], y=gaps.index, text=text.to_numpy(),
        texttemplate="%{text}", textfont=dict(size=11),
        colorscale=[[0, "#7C3AED" if dark else "#A855F7"], [0.0001, "#1E222A" if dark else "#F1F2F5"],
                    [1, "#C81E14" if dark else "#E5483F"]],
        zmin=0, zmax=max(float(np.nanmax(gaps.to_numpy())) if gaps.size else 0.5, 0.3), showscale=False,
        hovertemplate="<b>%{y}</b> %{x}<br>%{text}<extra></extra>", xgap=3, ygap=3,
    ))
    fig.update_layout(height=max(260, 26 * len(gaps) + 60), margin=dict(l=10, r=10, t=10, b=10))
    plotstyle.apply(fig)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False)
    return fig


def quali_evolution_chart(laps: pd.DataFrame, colors: dict[str, str], highlight: list[str]) -> go.Figure:
    """Every valid push lap through the session; the highlighted drivers in team colours."""
    valid = laps[~laps["Deleted"]].dropna(subset=["LapTime", "Minute"])
    valid = valid[valid["LapTime"] < 1.07 * valid["LapTime"].min()] if not valid.empty else valid
    fig = go.Figure()
    others = valid[~valid["Driver"].isin(highlight)]
    fig.add_trace(go.Scatter(x=others["Minute"], y=others["LapTime"], mode="markers", name="Others",
                             marker=dict(size=6, color=CONTEXT_GREY), customdata=others[["Driver"]],
                             hovertemplate="%{customdata[0]} %{y:.3f} s<extra></extra>"))
    seen = set()
    for driver in highlight:
        d = valid[valid["Driver"] == driver]
        if d.empty:
            continue
        color = colors.get(driver, "#999")
        symbol = "diamond" if color in seen else "circle"  # teammates share a colour
        seen.add(color)
        fig.add_trace(go.Scatter(x=d["Minute"], y=d["LapTime"], mode="markers+lines", name=driver,
                                 line=dict(color=color, width=1, dash="dot"),
                                 marker=dict(size=9, color=color, symbol=symbol),
                                 hovertemplate=f"{driver} %{{y:.3f}} s<extra></extra>"))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    fig.update_xaxes(title="Minutes into the session")
    if not valid.empty:
        lo, hi = valid["LapTime"].min(), valid["LapTime"].max()
        ticks = np.arange(np.floor(lo * 2) / 2, hi + 0.5, 0.5 if hi - lo < 4 else 1.0)
        fig.update_yaxes(title=None, autorange="reversed", tickvals=ticks, ticktext=[_minutes(t, 1) for t in ticks])
    return fig


def team_results_chart(results: pd.DataFrame, rounds: pd.DataFrame, drivers: list[str], color: str) -> go.Figure:
    """Each driver's Grand Prix finishing position round by round; a cross at the foot for a DNF."""
    names = dict(zip(rounds["Round"], rounds["Location"]))
    gp = results[(results["Kind"] == "R") & results["Driver"].isin(drivers)]
    floor = int(results["Position"].max()) + 1 if results["Position"].notna().any() else 21
    fig = go.Figure()
    for i, driver in enumerate(drivers):
        d = gp[gp["Driver"] == driver].sort_values("Round")
        if d.empty:
            continue
        done = d[d["Classified"]]
        out = d[~d["Classified"]]
        dash = "solid" if i == 0 else "dash"
        fig.add_trace(go.Scatter(
            x=done["Round"], y=done["Position"], mode="lines+markers", name=driver,
            line=dict(color=color, width=2, dash=dash), marker=dict(size=8, color=color,
                                                                    symbol="circle" if i == 0 else "diamond"),
            customdata=[names.get(r, "") for r in done["Round"]],
            hovertemplate=f"<b>{driver}</b> %{{customdata}}<br>P%{{y:.0f}}<extra></extra>",
        ))
        if not out.empty:
            fig.add_trace(go.Scatter(
                x=out["Round"], y=[floor] * len(out), mode="markers", showlegend=False,
                marker=dict(size=10, color=color, symbol="x"),
                customdata=[[names.get(r, ""), s] for r, s in zip(out["Round"], out["Status"])],
                hovertemplate=f"<b>{driver}</b> %{{customdata[0]}}<br>%{{customdata[1]}}<extra></extra>",
            ))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), hovermode="closest",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    ticks = [t for t in (1, 3, 5, 10, 15, 20) if t <= floor - 2]  # keep P20 clear of the DNF row
    fig.update_yaxes(title="Finished", autorange=False, range=[floor + 0.7, 0.3], tickvals=ticks + [floor],
                     ticktext=[f"P{t}" for t in ticks] + ["DNF"])
    fig.update_xaxes(title=None, tickvals=rounds["Round"], ticktext=[f"R{r}" for r in rounds["Round"]],
                     range=[0.5, rounds["Round"].max() + 0.5] if len(rounds) else None)
    return fig


def _team_bars(table: pd.DataFrame, value: str, colors: dict[str, str], team: str, fmt: str, title: str) -> go.Figure:
    """Horizontal bars, first row of `table` on top, `team` in full colour and the rest faded (all in
    full colour when `team` is None)."""
    t = table.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=t[value], y=t["Team"], orientation="h",
        marker=dict(color=[colors.get(x, "#888888") for x in t["Team"]],
                    opacity=[1.0 if team is None or x == team else 0.35 for x in t["Team"]]),
        text=[fmt.format(v) for v in t[value]], textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>" + fmt.replace("{:", "%{x:").replace("}", "}") + "<extra></extra>",
        showlegend=False,
    ))
    return _bar_layout(fig, len(t), title, t[value])


def constructors_chart(table: pd.DataFrame, colors: dict[str, str], team: str | None = None) -> go.Figure:
    """Constructors' points so far, this team in full colour."""
    return _team_bars(table, "Points", colors, team, "{:.0f}", "Points")


def pit_crews_chart(table: pd.DataFrame, colors: dict[str, str], team: str) -> go.Figure:
    """Every team's median stationary time this season, quickest on top, this team in full colour."""
    return _team_bars(table.sort_values("Median"), "Median", colors, team, "{:.2f} s", "Median time stood still (s)")


def driver_results_chart(rows: pd.DataFrame, color: str) -> go.Figure:
    """Grid slot to finishing position for every Grand Prix: a line up in green for places gained,
    down in red for places lost; a cross at the foot for a retirement."""
    floor = 23
    fig = go.Figure()
    for r in rows.itertuples():
        if pd.isna(r.Grid) or r.Grid <= 0 or not r.Classified or pd.isna(r.Position):
            continue
        gained = r.Grid - r.Position
        fig.add_trace(go.Scatter(x=[r.Round, r.Round], y=[r.Grid, r.Position], mode="lines", showlegend=False,
                                 hoverinfo="skip",
                                 line=dict(width=3, color="#16A34A" if gained > 0 else "#E10600" if gained < 0
                                           else CONTEXT_GREY)))
    grid = rows[rows["Grid"].notna() & (rows["Grid"] > 0)]
    fig.add_trace(go.Scatter(x=grid["Round"], y=grid["Grid"], mode="markers", name="Grid",
                             marker=dict(size=8, color="rgba(0,0,0,0)", line=dict(width=1.5, color=CONTEXT_GREY)),
                             customdata=grid[["Event"]], hovertemplate="%{customdata[0]}<br>started P%{y:.0f}<extra></extra>"))
    done = rows[rows["Classified"] & rows["Position"].notna()]
    fig.add_trace(go.Scatter(x=done["Round"], y=done["Position"], mode="markers", name="Finish",
                             marker=dict(size=10, color=color), customdata=done[["Event"]],
                             hovertemplate="%{customdata[0]}<br>finished P%{y:.0f}<extra></extra>"))
    out = rows[~rows["Classified"] | rows["Position"].isna()]
    fig.add_trace(go.Scatter(x=out["Round"], y=[floor] * len(out), mode="markers", name="Retired",
                             marker=dict(size=11, color=color, symbol="x"), customdata=out[["Event", "Status"]],
                             hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), hovermode="closest",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    ticks = [1, 3, 5, 10, 15, 20]
    fig.update_yaxes(autorange=False, range=[floor + 0.8, 0.2], tickvals=ticks + [floor],
                     ticktext=[f"P{t}" for t in ticks] + ["DNF"], title=None)
    fig.update_xaxes(title=None, tickvals=rows["Round"], ticktext=[f"R{r}" for r in rows["Round"]])
    return fig


def points_progress_chart(progress: pd.DataFrame, lines: list[tuple[str, str, str]], rounds: pd.DataFrame,
                          legend: bool = True) -> go.Figure:
    """Cumulative points after each round. `lines`: (column, label, colour), drawn in order; a colour
    repeated (teammates) is dashed. Each line is named at its end, by its column with the legend or by
    its label without one."""
    names = dict(zip(rounds["Round"], rounds["Location"]))
    fig = go.Figure()
    seen = set()
    for column, label, color in lines:
        if column not in progress:
            continue
        dash = "dash" if color in seen else "solid"
        seen.add(color)
        y = progress[column]
        fig.add_trace(go.Scatter(x=progress.index, y=y, mode="lines", name=label,
                                 line=dict(color=color, width=2.5, dash=dash),
                                 customdata=[names.get(r, "") for r in progress.index],
                                 hovertemplate=f"<b>{label}</b> after %{{customdata}}<br>%{{y:.0f}} points<extra></extra>"))
        fig.add_annotation(x=progress.index[-1], y=y.iloc[-1], text=column if legend else label, showarrow=False,
                           xanchor="left", xshift=6, font=dict(size=11, color=color))
    top = max((progress[c].max() for c, _, _ in lines if c in progress), default=0)
    _spread_end_labels(fig, max(top, 1), height=340)
    longest = max((len(c if legend else label) for c, label, _ in lines), default=3)
    fig.update_layout(height=340, margin=dict(l=10, r=max(48, 7 * longest + 14), t=30 if legend else 10, b=10),
                      hovermode="x unified", showlegend=legend, legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    fig.update_xaxes(title=None, tickvals=list(progress.index), ticktext=[f"R{r}" for r in progress.index])
    fig.update_yaxes(title="Points", rangemode="tozero")
    return fig


def _minute_ticks(values: pd.Series) -> dict:
    """Y-axis ticks in m:ss for lap times in seconds: whole seconds, about five of them."""
    lo, hi = float(values.min()), float(values.max())
    step = max(1, int(np.ceil((hi - lo) / 5)))
    ticks = np.arange(np.floor(lo) - step, np.ceil(hi) + 2 * step, step)
    return dict(tickvals=ticks, ticktext=[f"{int(t // 60)}:{int(t % 60):02d}" for t in ticks])


def circuit_laps_chart(years: pd.DataFrame) -> go.Figure:
    """Pole and the race's fastest lap at one circuit, year by year."""
    fig = go.Figure()
    shown = []
    for column, driver, name, color in (("PoleTime", "Pole", "Pole", "#A855F7"),
                                        ("FastestTime", "Fastest", "Fastest race lap", "#F5B700")):
        y = years[column]
        if y.isna().all():
            continue
        shown.append(y.dropna())
        fig.add_trace(go.Scatter(
            x=years["Year"].astype(str), y=y, mode="lines+markers+text", name=name,
            line=dict(color=color, width=2.5), marker=dict(size=9, color=color),
            text=[f"{_minutes(v)} {d}" if pd.notna(v) else "" for v, d in zip(y, years[driver])],
            textposition="top center", textfont=dict(size=10), cliponaxis=False,
            hovertemplate="%{x}: %{text}<extra>" + name + "</extra>",
        ))
    fig.update_layout(height=320, margin=dict(l=10, r=40, t=30, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    fig.update_xaxes(title=None, type="category", range=[-0.6, len(years) - 0.4])  # room for the end labels
    if shown:
        fig.update_yaxes(title="Lap time", **_minute_ticks(pd.concat(shown)))
    return fig


STOP_BANDS = [(0, "No stop", "#9CA3AF"), (1, "1 stop", "#22C55E"), (2, "2 stops", "#F5B700"), (3, "3 or more", "#E10600")]


def circuit_stops_chart(years: pd.DataFrame) -> go.Figure:
    """How many times the finishers stopped at one circuit, a bar per year."""
    fig = go.Figure()
    for stops, name, color in STOP_BANDS:
        counts = [sum(n for s, n in by.items() if (s >= stops if stops == 3 else s == stops)) for by in years["Stops"]]
        if not any(counts):
            continue
        fig.add_trace(go.Bar(
            y=years["Year"].astype(str), x=counts, orientation="h", name=name, marker_color=color,
            text=[c or "" for c in counts], textposition="inside", insidetextanchor="middle",
            hovertemplate="%{y}: %{x} finishers<extra>" + name + "</extra>",
        ))
    fig.update_layout(barmode="stack", height=max(170, 52 * len(years) + 90), margin=dict(l=10, r=10, t=30, b=10),
                      bargap=0.35, legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, traceorder="normal"))
    plotstyle.apply(fig)
    fig.update_xaxes(title="Finishers")
    fig.update_yaxes(title=None, type="category", autorange="reversed")
    return fig
