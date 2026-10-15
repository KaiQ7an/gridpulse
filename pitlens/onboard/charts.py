"""Plotly charts comparing two drivers' laps."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pitlens import plotstyle
from pitlens.onboard.compare import rotate
from pitlens.onboard.data import OTHER_COLOR, REF_COLOR, OnboardData

CORNER_LINE = "rgba(150,150,150,0.35)"
DELTA_COLOR = "rgba(140,140,140,1)"


def telemetry_figure(data: OnboardData, aligned) -> go.Figure:
    """Gap, speed, throttle, brake and gear against distance, one panel each."""
    ref, other = data.ref.driver, data.other.driver
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.2, 0.36, 0.16, 0.1, 0.18],
    )
    d = aligned["Distance"]

    fig.add_trace(
        go.Scatter(
            x=d, y=aligned["Delta"], mode="lines", line=dict(color=DELTA_COLOR, width=2), showlegend=False,
            hovertemplate=f"%{{x:.0f}} m<br>{other} %{{y:+.3f}} s vs {ref}<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_hline(y=0, line=dict(color=CORNER_LINE, width=1), row=1, col=1)

    panels = [("Speed", 2, "%{y:.0f} km/h"), ("Throttle", 3, "%{y:.0f}%"), ("Brake", 4, "%{y:.0f}"), ("nGear", 5, "gear %{y:.0f}")]
    for col, row, fmt in panels:
        for name, prefix, color in ((ref, "Ref", REF_COLOR), (other, "Other", OTHER_COLOR)):
            fig.add_trace(
                go.Scatter(
                    x=d, y=aligned[f"{prefix}{col}"], mode="lines", name=name, legendgroup=name,
                    showlegend=row == 2, line=dict(color=color, width=2, shape="hv" if col in ("Brake", "nGear") else "linear"),
                    hovertemplate=f"<b>{name}</b> %{{x:.0f}} m<br>{fmt}<extra></extra>",
                ),
                row=row, col=1,
            )

    for _, c in data.corners.iterrows():
        fig.add_vline(x=c["Distance"], line=dict(color=CORNER_LINE, width=1, dash="dot"))
        fig.add_annotation(
            x=c["Distance"], y=1, yref="y2 domain", text=f"{int(c['Number'])}{c.get('Letter') or ''}",
            showarrow=False, yanchor="bottom", font=dict(size=9, color="rgba(140,140,140,1)"),
        )

    titles = [f"Gap (s)<br><sup>+ = {other} behind</sup>", "Speed (km/h)", "Throttle (%)", "Brake", "Gear"]
    for row, title in enumerate(titles, start=1):
        fig.update_yaxes(title_text=title, title_font=dict(size=11), row=row, col=1)
    fig.update_yaxes(range=[-0.1, 1.1], tickvals=[0, 1], ticktext=["off", "on"], row=4, col=1)
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_xaxes(title_text="Distance (m)", row=5, col=1)
    fig.update_layout(
        height=820,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return plotstyle.apply(fig)


def track_map(data: OnboardData, sectors) -> go.Figure:
    """The circuit drawn in mini-sectors, each coloured by the faster driver."""
    tel = data.ref.telemetry
    x, y = rotate(tel["X"], tel["Y"], data.rotation)
    dist = tel["Distance"].to_numpy()
    colors = {"ref": REF_COLOR, "other": OTHER_COLOR}
    names = {"ref": data.ref.driver, "other": data.other.driver}

    fig = go.Figure()
    shown = set()
    for _, s in sectors.iterrows():
        mask = (dist >= s["Start"] - 5) & (dist <= s["End"] + 5)  # small overlap so segments join
        who = s["Faster"]
        fig.add_trace(
            go.Scatter(
                x=x[mask], y=y[mask], mode="lines", line=dict(color=colors[who], width=7),
                name=names[who], legendgroup=who, showlegend=who not in shown,
                hovertemplate=(
                    f"Mini-sector {int(s['Sector'])}<br>{names[who]} faster by {abs(s['Gain']):.3f} s<extra></extra>"
                ),
            )
        )
        shown.add(who)

    cx, cy = rotate(data.corners["X"], data.corners["Y"], data.rotation)
    fig.add_trace(
        go.Scatter(
            x=cx, y=cy, mode="text", showlegend=False, hoverinfo="skip",
            text=[f"{int(n)}{l or ''}" for n, l in zip(data.corners["Number"], data.corners["Letter"])],
            textfont=dict(size=10, color="rgba(140,140,140,1)"), textposition="top center",
        )
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(
        height=480,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text="Faster in mini-sector: "),
    )
    return plotstyle.apply(fig)
