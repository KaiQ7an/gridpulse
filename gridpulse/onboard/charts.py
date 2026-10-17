"""Plotly charts comparing two drivers' laps."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from gridpulse import plotstyle
from gridpulse.onboard.compare import rotate
from gridpulse.onboard.data import OnboardData
from gridpulse.season.tours import corner_measurements
from gridpulse.style import FALLBACK_TEAM_COLOR

CORNER_LINE = "rgba(150,150,150,0.30)"
SECTOR_LINE = "rgba(150,150,150,0.65)"
MUTED = "rgba(140,140,140,1)"


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def telemetry_figure(data: OnboardData, aligned, sector_marks: list[float] = (), x_range=None) -> go.Figure:
    """Gap, speed, throttle, brake and gear against distance, one panel each.

    The gap panel is filled in the colour of whoever is ahead at that point,
    so the story of the lap reads at a glance.
    """
    ref, other = data.labels
    ref_color, other_color = data.colors
    ref_dash, other_dash = data.dashes
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.22, 0.34, 0.16, 0.1, 0.18])
    d = aligned["Distance"]
    delta = aligned["Delta"]

    # Ahead/behind areas, then the line on top.
    for part, color in ((delta.clip(lower=0), ref_color), (delta.clip(upper=0), other_color)):
        fig.add_trace(
            go.Scatter(x=d, y=part, mode="lines", line=dict(width=0), fill="tozeroy", fillcolor=_rgba(color, 0.28),
                       hoverinfo="skip", showlegend=False),
            row=1, col=1,
        )
    fig.add_trace(
        go.Scatter(
            x=d, y=delta, mode="lines", line=dict(color=MUTED, width=1.5), showlegend=False,
            customdata=list(zip(np.where(delta >= 0, ref, other), delta.abs())),
            hovertemplate="%{x:.0f} m<br>%{customdata[0]} ahead by %{customdata[1]:.3f} s<extra></extra>",
        ),
        row=1, col=1,
    )
    span = max(0.05, float(delta.abs().max()) * 1.15)
    fig.update_yaxes(range=[-span, span], row=1, col=1)
    for text, y, color, anchor in ((f"▲ {ref} ahead", 1, ref_color, "top"),
                                   (f"▼ {other} ahead", 0, other_color, "bottom")):
        fig.add_annotation(x=0, xref="x domain", y=y, yref="y domain", text=text, showarrow=False, xanchor="left",
                           yanchor=anchor, font=dict(size=10, color=color))

    panels = [("Speed", 2, "%{y:.0f} km/h"), ("Throttle", 3, "%{y:.0f}%"), ("Brake", 4, "%{y:.0f}"), ("nGear", 5, "gear %{y:.0f}")]
    for col, row, fmt in panels:
        for name, prefix, color, dash in ((ref, "Ref", ref_color, ref_dash),
                                           (other, "Other", other_color, other_dash)):
            fig.add_trace(
                go.Scatter(
                    x=d, y=aligned[f"{prefix}{col}"], mode="lines", name=name, legendgroup=name, showlegend=row == 2,
                    line=dict(color=color, dash=dash, width=1.8, shape="hv" if col in ("Brake", "nGear") else "linear"),
                    hovertemplate=f"<b>{name}</b> %{{x:.0f}} m<br>{fmt}<extra></extra>",
                ),
                row=row, col=1,
            )

    for _, c in data.corners.iterrows():
        fig.add_vline(x=c["Distance"], line=dict(color=CORNER_LINE, width=1, dash="dot"))
        fig.add_annotation(x=c["Distance"], y=1, yref="y2 domain", text=f"{int(c['Number'])}{c.get('Letter') or ''}",
                           showarrow=False, yanchor="bottom", font=dict(size=9, color=MUTED))
    for n, x in enumerate(sector_marks, start=1):
        fig.add_vline(x=x, line=dict(color=SECTOR_LINE, width=1.2))
        fig.add_annotation(x=x, y=1, yref="y domain", text=f"S{n} | S{n + 1}", showarrow=False, yanchor="top",
                           xanchor="center", font=dict(size=9, color=MUTED))

    titles = ["Gap (s)", "Speed (km/h)", "Throttle (%)", "Brake", "Gear"]
    for row, title in enumerate(titles, start=1):
        fig.update_yaxes(title_text=title, row=row, col=1)
    fig.update_yaxes(range=[-0.15, 1.15], tickvals=[0, 1], ticktext=["off", "on"], row=4, col=1)
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_xaxes(title_text="Distance (m)", row=5, col=1)
    fig.update_layout(height=780, margin=dict(l=10, r=10, t=36, b=10), hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.01, x=1, xanchor="right"))
    plotstyle.apply(fig)
    if x_range:
        fig.update_xaxes(range=list(x_range))
    return fig


def track_map(data: OnboardData, sectors) -> go.Figure:
    """The circuit drawn in mini-sectors, each coloured by the faster driver."""
    tel = data.ref.telemetry
    x, y = rotate(tel["X"], tel["Y"], data.rotation)
    dist = tel["Distance"].to_numpy()
    colors = dict(zip(("ref", "other"), data.colors))
    dashes = dict(zip(("ref", "other"), data.dashes))
    names = dict(zip(("ref", "other"), data.labels))

    fig = go.Figure()
    # A wide, faint base line under the coloured segments gives the track some body.
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="rgba(128,128,128,0.18)", width=14),
                             hoverinfo="skip", showlegend=False))
    shown = set()
    for _, s in sectors.iterrows():
        mask = (dist >= s["Start"] - 5) & (dist <= s["End"] + 5)  # small overlap so segments join
        who = s["Faster"]
        fig.add_trace(
            go.Scatter(
                x=x[mask], y=y[mask], mode="lines", line=dict(color=colors[who], dash=dashes[who], width=6),
                name=f"{names[who]} faster", legendgroup=who, showlegend=who not in shown,
                hovertemplate=f"Mini-sector {int(s['Sector'])}<br>{names[who]} faster by {abs(s['Gain']):.3f} s<extra></extra>",
            )
        )
        shown.add(who)

    # Corner numbers sit just off the track, pushed out along each corner's label
    # angle from the circuit info, with a hairline back to the corner.
    span = max(np.ptp(x), np.ptp(y))
    off = span * 0.05
    for _, c in data.corners.iterrows():
        a = np.radians(c["Angle"])
        (cx, lx), (cy, ly) = rotate([c["X"], c["X"] + off * np.cos(a)], [c["Y"], c["Y"] + off * np.sin(a)], data.rotation)
        fig.add_shape(type="line", x0=cx, y0=cy, x1=lx, y1=ly, line=dict(color="rgba(128,128,128,0.45)", width=1))
        label = f"T{int(c['Number'])}{c.get('Letter') or ''}"
        details = []
        for lap, name in zip((data.ref, data.other), data.labels):
            distance = c["Distance"] * lap.telemetry["Distance"].max() / dist.max()
            values = corner_measurements(lap.telemetry, distance)
            speed, gear, brake = (values[k] if values[k] is not None else "—" for k in ("speed", "gear", "brake_m"))
            details.append(f"{name}: {speed} km/h · gear {gear} · brake-on ~{brake} m")
        fig.add_trace(go.Scatter(
            x=[lx], y=[ly], mode="markers+text", text=[f"{int(c['Number'])}{c.get('Letter') or ''}"],
            textfont=dict(size=9, color="#ffffff"), marker=dict(size=18, color="rgba(88,92,102,0.95)"),
            hovertemplate=f"<b>{label}</b><br>" + "<br>".join(details)
            + "<br>Local minima / sampled approach braking<extra></extra>", showlegend=False,
        ))

    # Start/finish: a short bar across the track at the first sample.
    sx, sy = x[0], y[0]
    dx, dy = x[min(5, len(x) - 1)] - sx, y[min(5, len(y) - 1)] - sy
    norm = np.hypot(dx, dy) or 1
    px_, py_ = -dy / norm * span * 0.025, dx / norm * span * 0.025
    fig.add_shape(type="line", x0=sx - px_, y0=sy - py_, x1=sx + px_, y1=sy + py_, line=dict(color=MUTED, width=4))
    fig.add_annotation(x=sx + px_ * 2.2, y=sy + py_ * 2.2, text="START", showarrow=False, font=dict(size=9, color=MUTED))

    fig.update_layout(height=520, margin=dict(l=4, r=4, t=36, b=4), legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    plotstyle.apply(fig)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    return fig


def corner_gains(corners: pd.DataFrame, ref: str, other: str, *,
                 ref_color: str = FALLBACK_TEAM_COLOR, other_color: str = FALLBACK_TEAM_COLOR,
                 distinguish: bool = False) -> go.Figure:
    """Time gained through each corner: bars right for `ref`, left for `other`."""
    c = corners.iloc[::-1]  # first corner at the top
    labels = "T" + c["Corner"].astype(str)
    colors = [ref_color if g >= 0 else other_color for g in c["Gain"]]
    patterns = ["/" if distinguish and g < 0 else "" for g in c["Gain"]]
    fig = go.Figure(
        go.Bar(
            x=c["Gain"], y=labels, orientation="h", marker=dict(color=colors, pattern_shape=patterns), width=0.62,
            customdata=c[["RefMinSpeed", "OtherMinSpeed"]],
            hovertemplate=(f"<b>%{{y}}</b><br>{ref} %{{customdata[0]}} km/h · {other} %{{customdata[1]}} km/h"
                           "<br>%{x:+.3f} s<extra></extra>"),
            showlegend=False,
        )
    )
    lim = max(0.05, float(c["Gain"].abs().max()) * 1.2) if len(c) else 0.1
    fig.add_vline(x=0, line=dict(color="rgba(128,128,128,0.5)", width=1))
    for text, x, color, anchor in ((f"{ref} gains →", lim, ref_color, "right"),
                                   (f"← {other} gains", -lim, other_color, "left")):
        fig.add_annotation(x=x, y=1, yref="paper", text=text, showarrow=False, xanchor=anchor, yanchor="bottom",
                           font=dict(size=10, color=color))
    fig.update_layout(height=max(320, 22 * len(c) + 90), margin=dict(l=10, r=10, t=30, b=10), bargap=0.25)
    plotstyle.apply(fig)
    fig.update_xaxes(range=[-lim, lim], title="Time gained through the corner (s)")
    fig.update_yaxes(showgrid=False)
    return fig
