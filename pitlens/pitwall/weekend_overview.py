"""DTM weekend podiums and qualifying leaders, visible without changing sessions."""

import html

import streamlit as st

from pitlens.drivers.profiles import profile
from pitlens.dtm import data
from pitlens.pitwall import ui

CSS = '''<style>
.dtm-overview-list{display:flex;flex-direction:column;gap:0;margin:5px 0 10px}
.dtm-overview-row{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:10px;align-items:center;
 padding:10px 0;border-bottom:1px solid rgba(128,128,128,.12);transition:background .15s}
.dtm-overview-row:last-child{border-bottom:0}
.dtm-overview-row:hover{background:rgba(128,128,128,.045)}
.dtm-overview-rank{font-size:1.05rem;font-weight:700;font-variant-numeric:tabular-nums;opacity:.55}
.dtm-overview-row:first-child .dtm-overview-rank{color:#B68A25;opacity:1}
.dtm-overview-driver{font-size:.92rem;font-weight:650;line-height:1.4;border-left:3px solid var(--team-color);padding-left:10px}
.dtm-overview-team{font-size:.7rem;font-weight:400;opacity:.55;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dtm-overview-time{font-size:.82rem;font-variant-numeric:tabular-nums;white-space:nowrap;opacity:.75}
@media(max-width:550px){.dtm-overview-row{grid-template-columns:22px minmax(0,1fr)}
 .dtm-overview-time{grid-column:2;padding-left:13px}}
@media(prefers-reduced-motion:reduce){.dtm-overview-row{transition:none}}
</style>'''


def top_three(session: dict) -> list[dict]:
    """Keep official P1–P3; a missing/disqualified P2 does not promote P4."""
    return sorted([r for r in session.get("rows", []) if r.get("position") in (1, 2, 3)
                   and not r.get("status")], key=lambda r: r["position"])


def sections(event: dict) -> list[tuple[str, list[dict]]]:
    sessions = event.get("sessions", [])
    return [(title, sorted([s for s in sessions if s["kind"] == kind and
                            (s["name"] == title if kind == "race" else s["name"].startswith(title))],
                           key=lambda s: s["name"]))
            for title, kind in (("Race 1", "race"), ("Race 2", "race"),
                                ("Qualifying 1", "qualifying"), ("Qualifying 2", "qualifying"))]


def render(event: dict, year: int) -> str | None:
    """Return a requested session before its detailed-results widget is created."""
    st.html(CSS)
    ui.label("Weekend overview")
    clicked = None
    groups = sections(event)
    for pair in (groups[:2], groups[2:]):
        for column, (title, sessions) in zip(st.columns(2, gap="medium"), pair):
            with column, st.container(border=True):
                st.subheader(title)
                if not sessions:
                    st.caption("Results not published yet.")
                for session in sessions:
                    grouped = "Group" in session["name"]
                    if grouped:
                        ui.label(session["name"])
                        st.caption("Top three in this group; not the combined starting grid.")
                    rows = []
                    for row in top_three(session):
                        name = profile("dtm", row["driver"]).get("name") or row["name"]
                        if session["kind"] == "qualifying":
                            timing = row.get("fastest_lap") or row.get("time") or "–"
                        elif row["position"] == 1:
                            timing = row.get("time") or "–"
                        else:
                            gap = row.get("gap")
                            timing = (gap if str(gap).startswith("+") else f"+{gap}") if gap and gap != "-" else row.get("time") or "–"
                        color = data.COLORS.get(row.get("manufacturer"), "#888888")
                        rows.append(f'<div class="dtm-overview-row" role="listitem">'
                                    f'<span class="dtm-overview-rank">{int(row["position"])}</span>'
                                    f'<div class="dtm-overview-driver" style="--team-color:{color}">{html.escape(name)}'
                                    f'<div class="dtm-overview-team">{html.escape(row.get("team", ""))}</div></div>'
                                    f'<span class="dtm-overview-time">{html.escape(str(timing))}</span></div>')
                    if rows:
                        st.html('<div class="dtm-overview-list" role="list" '
                                f'aria-label="{html.escape(session["name"], quote=True)} top three">' + "".join(rows) + '</div>')
                    else:
                        st.caption("No classified top-three result published yet.")
                    if session.get("provisional"):
                        st.caption("Provisional official classification")
                    if st.button(f"Full {session['name']} results", icon=":material/arrow_downward:",
                                 key=f"dtm_overview_{year}_{event['round']}_{session['key']}", width="stretch"):
                        clicked = session["key"]
    return clicked
