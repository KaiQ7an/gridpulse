"""Plotly charts for pit stops and undercut battles."""

import pandas as pd
import plotly.graph_objects as go

from pitlens import plotstyle

INK_GREY = "rgba(140,140,140,1)"
RULE = "rgba(150,150,150,0.35)"
GREEN_STOP = "#2F6FDE"
NEUTRAL_STOP = "#9A9A9A"


def battle_chart(gap: pd.DataFrame, battle, total_laps: int) -> go.Figure:
    """Gap between the two cars around their stops, drawn so 'up' means the first stopper is ahead."""
    a, b = battle.FirstStop, battle.Rival
    lo, hi = max(1, battle.Lap - 5), min(total_laps, battle.RivalStopLap + 6)
    g = gap[(gap["LapNumber"] >= lo) & (gap["LapNumber"] <= hi)]
    ahead = -g["Gap"]  # > 0: a ahead of b

    fig = go.Figure()
    fig.add_vrect(x0=battle.Lap - 0.5, x1=battle.RivalStopLap + 1.5, fillcolor="rgba(150,150,150,0.10)", line_width=0)
    fig.add_hline(y=0, line=dict(color=RULE, width=1))
    fig.add_trace(
        go.Scatter(
            x=g["LapNumber"], y=ahead, mode="lines+markers", line=dict(color=GREEN_STOP, width=2.5), marker=dict(size=7),
            name=f"{a} vs {b}", showlegend=False,
            hovertemplate=f"Lap %{{x}}<br>{a} %{{customdata}}<extra></extra>",
            customdata=[f"ahead by {v:.2f} s" if v > 0 else f"behind by {-v:.2f} s" for v in ahead],
        )
    )
    # First stopper's label to the left of its line, the rival's to the right, so a stop a lap
    # later doesn't print on top of the first.
    for lap, who, side in ((battle.Lap, a, "right"), (battle.RivalStopLap, b, "left")):
        fig.add_vline(x=lap, line=dict(color=INK_GREY, width=1, dash="dot"))
        fig.add_annotation(x=lap, y=1, yref="paper", text=f"{who} pits", showarrow=False, yanchor="bottom",
                           xanchor=side, xshift=-3 if side == "right" else 3, font=dict(size=11, color=INK_GREY))
    span = max(3.0, float(ahead.abs().max()) * 1.2) if len(ahead) else 3.0
    fig.update_yaxes(title=f"{a} ahead of {b} (s)", range=[-span, span], zeroline=False)
    fig.update_xaxes(title="Lap", dtick=1)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=36, b=10), hovermode="x")
    return plotstyle.apply(fig)


def pit_loss_chart(stops: pd.DataFrame, loss: float | None, total_laps: int) -> go.Figure:
    """Time each stop cost against the lap it was made on; grey stops were under SC/VSC."""
    # A "negative cost" under a safety car is the field queueing behind it, not a measurement.
    stops = stops[~(stops["Neutralised"] & (stops["Loss"] < 0))]
    fig = go.Figure()
    for neutral, name, color in ((False, "Green flag", GREEN_STOP), (True, "Safety car / VSC", NEUTRAL_STOP)):
        s = stops[stops["Neutralised"] == neutral]
        if s.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=s["Lap"], y=s["Loss"], mode="markers+text", name=name, text=s["Driver"], textposition="top center",
                textfont=dict(size=9, color=INK_GREY), marker=dict(size=9, color=color, line=dict(width=1, color="white")),
                customdata=s[["Driver", "From", "To", "LaneTime"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> lap %{x}<br>%{customdata[1]} → %{customdata[2]}"
                    "<br>cost %{y:.1f} s · pit lane %{customdata[3]:.1f} s<extra></extra>"
                ),
            )
        )
    if loss is not None:
        fig.add_hline(y=loss, line=dict(color=INK_GREY, width=1, dash="dash"),
                      annotation_text=f"typical {loss:.1f} s", annotation_position="top left")
    fig.update_xaxes(title="Lap", range=[0.5, total_laps + 0.5])
    fig.update_yaxes(title="Time lost to the stop (s)")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))
    return plotstyle.apply(fig)
