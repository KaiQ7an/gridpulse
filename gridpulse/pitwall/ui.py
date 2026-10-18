"""Shared design primitives: headers, status strips, sidebar navigation and small marks.

Colours here are theme-neutral (inherit the text colour, translucent greys)
so the same markup reads well in Streamlit's light and dark themes.
"""

import html
import json

import pandas as pd
import streamlit as st

from gridpulse.branding import NAME, TAGLINE
from gridpulse.pitwall import dtm_nav, styles
from gridpulse.style import COMPOUND_COLORS

ACCENT = "#E10600"

STATUS_STYLE = {  # track status -> (background, text)
    "Green": ("rgba(34,197,94,0.16)", "#16A34A"),
    "Yellow": ("rgba(245,183,0,0.20)", "#B88A00"),
    "VSC": ("rgba(245,183,0,0.20)", "#B88A00"),
    "VSC ending": ("rgba(245,183,0,0.14)", "#B88A00"),
    "Safety car": ("#F5B700", "#111111"),
    "Red flag": ("#E10600", "#FFFFFF"),
}


def inject_css() -> None:
    styles.inject("pitwall.css")


def sidebar_brand(tagline: str) -> None:
    slot = st.session_state.get("sidebar_brand_slot")
    target = slot if slot is not None else st.sidebar
    home = next((p for p in st.session_state.get("sidebar_pages", []) if p.title == "Home"), None)
    if home is not None:
        with target.container(key="brand-home-link"):
            st.page_link(home, label=NAME, icon="", help="Return to GridPulse home", width="stretch")
            # CSS metadata decorates a native page link, preserving the browser session on navigation.
            caption = json.dumps(TAGLINE + "\n" + tagline, ensure_ascii=False).replace("<", r"\3c ").replace(r"\n", r"\a ")
            st.html('<style>.st-key-brand-home-link a::after{content:' + caption + ';}</style>')
        return
    target.html(
        f'<div class="pl-brand"><div class="mark"></div><div><div class="name">{NAME}</div>'
        f'<div class="tag">{TAGLINE}</div><div class="context">{html.escape(tagline)}</div></div></div>'
    )


def sidebar_navigation(*, fallback: bool = False) -> None:
    pages = st.session_state.get("sidebar_pages", [])
    if not pages or st.session_state.get("sidebar_navigation_rendered"):
        return
    series = st.session_state.get("racing_series", "Formula 1")
    current = st.session_state.get("sidebar_current_page", "")
    if current == "":
        by_path = {p.url_path: p for p in pages}
        pages = [by_path[path] for path in ("", "replay", "dtm", "circuits", "about")]
    elif series == "DTM":
        pages = [p for p in pages if p.url_path in (("", "dtm", "about") if current == "about" else ("", "about"))]
    else:
        by_path = {p.url_path: p for p in pages if p.url_path != "dtm"}
        pages = [by_path[path] for path in ("", "season", "replay", "qualifying", "onboard", "teams", "drivers", "circuits", "about")]
    slot = st.session_state.get("sidebar_navigation_fallback")
    if not fallback and slot is not None:
        slot.empty()
    dtm_nav.render_pages(pages, current, "GridPulse" if current == "" else series,
                         caption=current == "" or series != "DTM" or current == "about",
                         target=slot if fallback else None, suffix="-fallback" if fallback else "")
    if not fallback:
        st.session_state.sidebar_navigation_rendered = True


def sidebar_footer(series: str = "Formula 1") -> None:
    sidebar_navigation()
    if series == "All series":
        st.sidebar.html('<div class="home-nav-foot">Independent motorsport project<br>'
                        '<a href="https://github.com/KaiQ7an/gridpulse" target="_blank" rel="noopener noreferrer">Source on GitHub ↗</a></div>')
        return
    if series == "DTM":
        st.sidebar.html(
            '<div class="dtm-foot">Independent project · Official DTM data<br>'
            '<a href="https://github.com/KaiQ7an/gridpulse" target="_blank" rel="noopener noreferrer">GitHub ↗</a></div>'
        )
        return
    st.sidebar.html(
        '<div class="pl-foot">Unofficial project. Timing data from the public F1 live-timing archive via FastF1, '
        "or from OpenF1 when the archive is unavailable. "
        "Not associated with Formula 1 or any team.<br>"
        '<a href="https://github.com/KaiQ7an/gridpulse" target="_blank" style="color:inherit">Source on GitHub</a></div>'
    )


def label(text: str) -> None:
    st.html(f'<div class="pl-label">{html.escape(text)}</div>')


def note(text: str) -> None:
    st.html(f'<div class="pl-note">{html.escape(text)}</div>')


def header(eyebrow: str, title: str, sub: str = "", title_html: str | None = None) -> None:
    st.html(
        f'<div class="pl-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="pl-title">{title_html or html.escape(title)}</div>'
        + (f'<div class="pl-sub">{html.escape(sub)}</div>' if sub else "")
    )


def stat(key: str, value: str, small: str = "", value_html: str | None = None, tip: str = "") -> str:
    """One labelled value for `strip`. Pass `value_html` for pre-formatted markup, `tip` for a hover note."""
    v = value_html if value_html is not None else html.escape(value)
    s = f"<small>{html.escape(small)}</small>" if small else ""
    t = f' title="{html.escape(tip)}"' if tip else ""
    return f'<div class="pl-stat"{t}><div class="k">{html.escape(key)}</div><div class="v">{v}{s}</div></div>'


def strip(stats: list[str]) -> None:
    st.html('<div class="pl-strip">' + "".join(stats) + "</div>")


def replay_status(primary: list[str], details: list[str]) -> None:
    st.html('<section class="pl-replay-status" aria-label="Race status">'
            '<div class="pl-status-main">' + "".join(primary) + '</div>'
            '<div class="pl-status-details">' + "".join(details) + '</div></section>')


def status_pill(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("rgba(128,128,128,0.18)", "inherit"))
    return f'<span class="pl-pill" style="background:{bg};color:{fg}">{html.escape(status)}</span>'


def driver_dot(color: str) -> str:
    return f'<span class="pl-dot" style="background:{color}"></span>'


def insight(text: str) -> None:
    st.html(f'<div class="pl-insight">{html.escape(text)}</div>')


EVENT_TAGS = {  # kind -> (label, background, text)
    "PIT": ("PIT", "rgba(225,6,0,0.16)", "#E10600"),
    "PASS": ("PASS", "rgba(34,197,94,0.18)", "#16A34A"),
    "FL": ("FASTEST", "rgba(168,85,247,0.18)", "#A855F7"),
    "SC": ("SC/VSC", "#F5B700", "#111111"),
    "GREEN": ("GREEN", "rgba(34,197,94,0.18)", "#16A34A"),
    "OUT": ("OUT", "rgba(128,128,128,0.22)", "inherit"),
    "FLAG": ("FINISH", "rgba(128,128,128,0.22)", "inherit"),
    "RADIO": ("RADIO", "rgba(47,111,222,0.16)", "#2F6FDE"),
}


def race_feed(situation: str, events, lap: int, limit: int = 9) -> None:
    rows = []
    for e in events.itertuples():
        label, bg, fg = EVENT_TAGS.get(e.Kind, (e.Kind, "rgba(128,128,128,0.2)", "inherit"))
        now = " now" if e.Lap == lap else ""
        rows.append(
            f'<div class="pl-ev{now}"><span class="lap">L{e.Lap}</span>'
            f'<span class="tag" style="background:{bg};color:{fg}">{label}</span>'
            f'<span class="txt">{html.escape(e.Text)}</span></div>'
        )
    body = "".join(rows[:limit]) or '<div class="pl-note">Nothing yet.</div>'
    st.html(f'<div class="pl-situation">{html.escape(situation)}</div>{body}')


def quote(text: str, translation: str | None = None) -> None:
    zh = f'<div class="pl-zh">{html.escape(translation)}</div>' if translation else ""
    st.html(f'<div class="pl-quote">“{html.escape(text)}”{zh}</div>')


BIG_FOUR = ("McLaren", "Ferrari", "Red Bull Racing", "Mercedes")


def driver_order(entrants, finish_order: list[str]) -> list[str]:
    """Drivers grouped by team: the big four first, then the rest by their best finisher."""
    team_of = dict(zip(entrants["Driver"], entrants["Team"]))
    rank = {d: i for i, d in enumerate(finish_order)}
    teams = []
    for d in finish_order:
        t = team_of.get(d)
        if t not in teams:
            teams.append(t)
    big = [t for t in BIG_FOUR if t in teams]
    order = big + [t for t in teams if t not in big]
    return sorted(team_of, key=lambda d: (order.index(team_of[d]) if team_of[d] in order else 99, rank.get(d, 99)))


def sector_stats(rankings: list[list[tuple[str, float, int]]], colors: dict[str, str], *, include_empty=False) -> list[str]:
    """Fastest S1/S2/S3 so far as three small stats (a size down from the main ones); hover shows P2 and P3."""
    out = []
    for n, ranking in enumerate(rankings, start=1):
        if not ranking:
            if include_empty:
                out.append(stat(f"Best S{n}", "—"))
            continue
        driver, secs, lap = ranking[0]
        rows = "".join(
            f'<div class="r"><span class="n">P{i}</span><span>{driver_dot(colors.get(d, "#999"))}{html.escape(d)}</span>'
            f'<span>{t:.3f}</span><span class="d">+{t - secs:.3f}</span></div>'
            for i, (d, t, _) in enumerate(ranking[1:], start=2)
        )
        pop = f'<div class="pl-pop"><div class="pl-label">Sector {n}</div>{rows}</div>' if rows else ""
        out.append(
            f'<div class="pl-stat sec" tabindex="0"><div class="k">Best S{n}</div><div class="v">'
            f'{driver_dot(colors.get(driver, "#999"))}{html.escape(driver)} <span style="color:#A855F7">{secs:.3f}</span>'
            f"<small>L{lap}</small></div>{pop}</div>"
        )
    return out


NOTE_STYLE = {  # kind -> (tab label, tab colour, tab text colour)
    "FL": ("Fastest lap", "#A855F7", "#ffffff"),
    "OUT": ("Retired", "#E10600", "#ffffff"),
    "SC": ("Race control", "#F5B700", "#111111"),
    "RED": ("Race control", "#E10600", "#ffffff"),
    "GREEN": ("Race control", "#16A34A", "#ffffff"),
    "WIN": ("Chequered flag", "#F2F2F2", "#111111"),
}


def notifications(notes: list[dict]) -> None:
    """Render race notifications (newest first) in a fixed stack at the top right, broadcast style."""
    cards = []
    for n in notes:
        title, color, ink = NOTE_STYLE.get(n["kind"], (n["kind"], "#888888", "#ffffff"))
        right_color = "#ffffff" if n["kind"] in ("SC", "RED", "GREEN", "WIN") else color
        right = f'<div class="right" style="color:{right_color}">{n["right"]}</div>' if n.get("right") else "<div></div>"
        cards.append(
            f'<div class="pl-bc" style="--team:{n["color"]}"><div class="tab" style="background:{color};color:{ink}">'
            f'{html.escape(title)}</div><div class="slab"><div class="bar"></div><div class="who">'
            f'<div class="surname">{html.escape(n["name"])}</div><div class="team">{html.escape(n["team"])}</div>'
            f"</div>{right}</div></div>"
        )
    with st.container(key="pl-notes"):
        for card in cards:
            st.html(card)


def sector_list(rankings, colors: dict[str, str]) -> None:
    """Fastest S1/S2/S3 so far, with the gap to the next quickest driver."""
    rows = []
    for n, ranking in enumerate(rankings, start=1):
        if not ranking:
            continue
        d, t, lap = ranking[0]
        c = colors.get(d, "#999")
        nxt = f" · +{ranking[1][1] - t:.3f} to {html.escape(ranking[1][0])}" if len(ranking) > 1 else ""
        rows.append(
            f'<div class="pl-secrow"><div class="num" style="background:{c}">{n}</div>'
            f'<div><div class="who">{html.escape(d)}<span class="t">{t:.3f}</span></div>'
            f'<div class="meta">Sector {n} · lap {lap}{nxt}</div></div></div>'
        )
    st.html('<div class="pl-seclist">' + "".join(rows) + "</div>")


TYRE_LETTERS = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}


def tyre(compound) -> str:
    """A small tyre: the compound's letter in a ring of its colour, as on the broadcast."""
    c = compound if isinstance(compound, str) and compound in COMPOUND_COLORS else "UNKNOWN"
    return (f'<span class="pl-tyre" style="--c:{COMPOUND_COLORS[c]}" title="{c.title()}">'
            f'{TYRE_LETTERS.get(c, "?")}</span>')


def lap_time(seconds) -> str:
    """Format a lap time in seconds, or an empty cell for a missing value."""
    if pd.isna(seconds):
        return ""
    minutes, rest = divmod(round(float(seconds), 3), 60)
    return f"{int(minutes)}:{rest:06.3f}"


def highlights(items: list[tuple[str, str, str]]) -> None:
    """A short list of standout numbers: label, value and a line of detail."""
    rows = "".join(f'<div class="pl-hl"><div class="k">{html.escape(k)}</div><div class="v">{html.escape(v)}</div>'
                   + (f'<div class="d">{html.escape(d)}</div>' if d else "") + "</div>" for k, v, d in items)
    st.html(rows)
