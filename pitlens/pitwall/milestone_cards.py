"""Two compact career milestone cards for drivers and teams."""

import html

import streamlit as st

from pitlens import milestones
from pitlens.pitwall import ui

CSS = '''<style>
.gp-milestones{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0}
.gp-milestone{padding:16px 18px;border:1px solid rgba(128,128,128,.2);border-radius:10px;position:relative;
 background:rgba(128,128,128,.025);transition:border-color .16s,transform .16s}
.gp-milestone:hover{border-color:rgba(225,6,0,.4);transform:translateY(-2px)}
.gp-milestone .label{font-size:.65rem;letter-spacing:.12em;text-transform:uppercase;opacity:.52}
.gp-milestone .year{font-size:1.45rem;font-weight:700;line-height:1.2;margin:6px 0 3px}
.gp-milestone .event{font-size:.88rem;font-weight:600;line-height:1.4}
.gp-milestone .detail{font-size:.72rem;opacity:.6;margin-top:5px}
.gp-milestone a{color:inherit;text-decoration:none}
.gp-milestone a:hover{text-decoration:underline}
.gp-milestone a:focus-visible{outline:2px solid #55bfff;outline-offset:3px}
@media(max-width:450px){.gp-milestones{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.gp-milestone{transition:none}.gp-milestone:hover{transform:none}}
</style>'''


def render(series: str, kind: str, identity: str, year: int):
    entry = milestones.profile(series, kind, identity)
    ui.label("Career milestones" if kind == "drivers" else "Team milestones")
    cards = []
    for key, label in (("first_points", "First GP points" if series == "f1" else "First points"),
                       ("first_win", "First GP win" if series == "f1" else "First win")):
        status, record = milestones.milestone(series, kind, identity, key, year)
        if record:
            event = html.escape(record["event"])
            source = html.escape(record["source"], quote=True)
            position = int(record["position"]) if record.get("position") else None
            details = [record["session"], f"P{position}" if position else ""]
            if record.get("points") is not None:
                details.append(f"{record['points']:g} pts")
            if kind == "teams" and record.get("driver"):
                details.append(record.get("name") or record["driver"])
            elif record.get("team"):
                details.append(record["team"])
            body = (f'<div class="year">{record["year"]}</div><div class="event">'
                    f'<a href="{source}" target="_blank" rel="noopener noreferrer">{event} ↗</a></div>'
                    f'<div class="detail">{html.escape(" · ".join(d for d in details if d))}</div>')
        else:
            message = f"Not achieved by {year}" if status == "not_yet" else "Earlier history not verified"
            body = f'<div class="event" style="margin-top:9px">{message}</div>'
        cards.append(f'<div class="gp-milestone"><div class="label">{label}</div>{body}</div>')
    st.html(CSS + '<div class="gp-milestones">' + "".join(cards) + '</div>')
    st.caption(f"{entry.get('scope', 'Historical records')} · through {year}. "
               f"References checked {milestones.catalog()['checked_at']}.")
