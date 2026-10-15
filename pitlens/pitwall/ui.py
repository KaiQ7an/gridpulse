"""Shared look for the pit wall pages: global CSS, header, status strip, sidebar brand.

Colours here are theme-neutral (inherit the text colour, translucent greys)
so the same markup reads well in Streamlit's light and dark themes.
"""

import html

import streamlit as st

ACCENT = "#E10600"

STATUS_STYLE = {  # track status -> (background, text)
    "Green": ("rgba(34,197,94,0.16)", "#16A34A"),
    "Yellow": ("rgba(245,183,0,0.20)", "#B88A00"),
    "VSC": ("rgba(245,183,0,0.20)", "#B88A00"),
    "VSC ending": ("rgba(245,183,0,0.14)", "#B88A00"),
    "Safety car": ("#F5B700", "#111111"),
    "Red flag": ("#E10600", "#FFFFFF"),
}

CSS = """
<style>
/* Streamlit dims elements while a rerun is in flight; during a replay that is
   every tick, which reads as stutter. Keep them at full opacity. */
[data-stale="true"], .stale-element { opacity: 1 !important; transition: none !important; }

/* Leave room for the top navigation bar, which sits over the page. */
[data-testid="stMainBlockContainer"] { padding-top: 5rem; padding-bottom: 4rem; padding-left: 3rem; padding-right: 3rem;
  max-width: 1760px; }
[data-testid="stSidebarUserContent"] { padding-top: 1.2rem; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* Page header */
.pl-eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
  color: #E10600; margin-bottom: 0.15rem; }
.pl-title { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 2.5rem; line-height: 1.08;
  margin: 0.1rem 0 0; }
.pl-sub { opacity: 0.62; font-size: 0.95rem; margin-top: 0.45rem; margin-bottom: 0.6rem; }

/* Status strip: small labelled values in a row */
.pl-strip { display: flex; flex-wrap: wrap; gap: 12px; margin: 6px 0 10px; }
.pl-stat { border: 1px solid rgba(128,128,128,0.22); border-radius: 10px; padding: 11px 16px 12px; min-width: 104px;
  background: rgba(128,128,128,0.04); }
.pl-stat .k { font-size: 0.66rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55; }
.pl-stat .v { font-size: 1.2rem; font-weight: 600; font-variant-numeric: tabular-nums; margin-top: 4px;
  white-space: nowrap; }
.pl-stat .v small { font-size: 0.78rem; font-weight: 500; opacity: 0.6; margin-left: 4px; }
/* Fastest sectors: three small stats (a size down from the main ones), P2 and P3 on hover */
.pl-stat.sec { position: relative; min-width: 0; padding: 11px 14px 12px; cursor: default; }
.pl-stat.sec .v { font-size: 0.98rem; margin-top: 6px; }
.pl-stat.sec:hover .pl-pop { display: block; }

.pl-pop { display: none; position: absolute; top: calc(100% + 6px); left: 0; z-index: 50; min-width: 190px;
  padding: 8px 10px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.28);
  background: var(--pl-pop-bg, rgba(250,250,250,0.98)); box-shadow: 0 8px 24px rgba(0,0,0,0.18);
  font-size: 0.82rem; font-weight: 500; font-variant-numeric: tabular-nums; }
@media (prefers-color-scheme: dark) { .pl-pop { --pl-pop-bg: rgba(23,27,34,0.98); } }
.pl-pop .r { display: grid; grid-template-columns: 22px 1fr auto auto; gap: 8px; align-items: center; padding: 2px 0; }
.pl-pop .r .n { opacity: 0.5; }
.pl-pop .r .d { opacity: 0.55; font-size: 0.76rem; }
.pl-pill { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 0.82rem; font-weight: 700;
  letter-spacing: 0.04em; text-transform: uppercase; }
.pl-dot { display: inline-block; width: 4px; height: 14px; border-radius: 2px; margin-right: 7px; vertical-align: -2px; }

/* Section labels inside cards */
.pl-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.55;
  margin: 2px 0 6px; }
.pl-note { font-size: 0.87rem; opacity: 0.62; margin: 0 0 10px; line-height: 1.5; }

/* One-line takeaway under a page header */
.pl-insight { border-left: 3px solid #E10600; border-radius: 4px 10px 10px 4px; padding: 14px 18px; margin: 8px 0 8px;
  background: rgba(128,128,128,0.06); font-size: 0.98rem; line-height: 1.6; }

/* Race feed */
.pl-situation { font-weight: 600; font-size: 1.02rem; margin: 2px 0 12px; }
.pl-ev { display: grid; grid-template-columns: 44px 62px 1fr; align-items: center; gap: 10px; padding: 9px 0;
  border-bottom: 1px solid rgba(128,128,128,0.14); font-size: 0.92rem; line-height: 1.45; }
.pl-ev:last-child { border-bottom: none; }
.pl-ev .lap { opacity: 0.55; font-variant-numeric: tabular-nums; font-size: 0.78rem; }
.pl-ev .tag { justify-self: start; font-size: 0.64rem; font-weight: 800; letter-spacing: 0.08em; padding: 2px 6px;
  border-radius: 4px; }
.pl-ev.now .txt { font-weight: 600; }

/* Team radio transcript */
.pl-quote { margin: 2px 0 6px 11px; padding: 2px 0 2px 10px; border-left: 2px solid rgba(128,128,128,0.35);
  font-size: 0.88rem; line-height: 1.45; opacity: 0.9; font-style: italic; }

.pl-zh { font-style: normal; margin-top: 3px; opacity: 0.95; }

/* Race notifications, styled like the F1 broadcast graphics: a solid label tab, then a dark
   slab with the team colour bar, the surname in capitals and the time on the right. */
.st-key-pl-notes { position: fixed; top: 68px; right: 22px; width: 360px; z-index: 999990; gap: 10px;
  pointer-events: none; }
.pl-bc { animation: pl-in 300ms ease-out, pl-out 450ms ease-in 4.3s forwards; filter: drop-shadow(0 10px 22px rgba(0,0,0,0.35)); }
.pl-bc .tab { display: inline-block; padding: 3px 10px 2px; font-family: "Titillium Web", sans-serif; font-weight: 700;
  font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: #fff; border-radius: 4px 4px 0 0; }
.pl-bc .slab { display: grid; grid-template-columns: 7px 1fr auto; align-items: center; background: #15151E; color: #fff;
  border-radius: 0 6px 6px 6px; overflow: hidden; min-height: 52px; }
.pl-bc .bar { align-self: stretch; background: var(--team); }
.pl-bc .who { padding: 7px 14px 8px; }
.pl-bc .surname { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 1.32rem; letter-spacing: 0.04em;
  text-transform: uppercase; line-height: 1.05; }
.pl-bc .team { font-size: 0.74rem; color: rgba(255,255,255,0.6); margin-top: 2px; }
.pl-bc .right { padding: 0 16px; font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 1.25rem;
  font-variant-numeric: tabular-nums; }
@keyframes pl-in { from { opacity: 0; transform: translateX(28px); } }
@keyframes pl-out { to { opacity: 0; transform: translateX(28px); visibility: hidden; } }

/* Sidebar brand */
.pl-brand { display: flex; align-items: center; gap: 10px; margin: 0 0 6px; }
.pl-brand .mark { width: 8px; height: 30px; border-radius: 2px; background: #E10600; transform: skewX(-14deg); }
.pl-brand .name { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 1.45rem; letter-spacing: 0.01em;
  line-height: 1; }
.pl-brand .tag { font-size: 0.72rem; opacity: 0.55; margin-top: 3px; }
.pl-foot { font-size: 0.72rem; opacity: 0.5; line-height: 1.45; }

/* Cards (keyed containers) get a little more air */
[class*="st-key-card-"] { padding: 10px 12px; }

/* Views bar: scroll sideways rather than wrapping onto a second row */
.st-key-view [data-testid="stButtonGroup"] { overflow-x: auto; scrollbar-width: none; }

/* Replay control bar */
.st-key-controls { align-items: center; }
.st-key-controls [data-testid="stSlider"] { padding-top: 0.2rem; }
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def sidebar_brand(tagline: str) -> None:
    st.sidebar.html(
        f'<div class="pl-brand"><div class="mark"></div><div><div class="name">PitLens</div>'
        f'<div class="tag">{html.escape(tagline)}</div></div></div>'
    )


def sidebar_footer() -> None:
    st.sidebar.html(
        '<div class="pl-foot">Unofficial project. Timing data from the public F1 live-timing archive via FastF1, '
        "or from OpenF1 when the archive is unavailable. "
        "Not associated with Formula 1 or any team.<br>"
        '<a href="https://github.com/KaiQ7an/pitlens" target="_blank" style="color:inherit">Source on GitHub</a></div>'
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


def _ink_for(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return "#111111" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#ffffff"


def team_colored_picker(label: str, options: list[str], colors: dict[str, str], teams: dict[str, str]) -> None:
    """Colour a multiselect's chips and options by team (Streamlit can't, so CSS keyed on the DOM).

    Chips carry aria-label=<driver>; options carry data-key=<index in options> inside
    a listbox labelled with the widget's label.
    """
    rules = []
    for i, d in enumerate(options):
        c = colors.get(d, "#999999")
        team = html.escape(teams.get(d, "") or "").replace('"', "")
        rules.append(
            f'[data-testid="stMultiSelectTagsContainer"] [data-tag][aria-label="{d}"] '
            f"{{ background: {c} !important; color: {_ink_for(c)} !important; }}"
            f'[data-testid="stMultiSelectTagsContainer"] [data-tag][aria-label="{d}"] button '
            f"{{ color: {_ink_for(c)} !important; }}"
            f'[role="listbox"][aria-label="{label}"] [role="option"][data-key="{i}"] [data-item-hl]::before '
            f'{{ content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 9px; '
            f"background: {c}; vertical-align: -1px; }}"
            f'[role="listbox"][aria-label="{label}"] [role="option"][data-key="{i}"] [data-item-hl]::after '
            f'{{ content: "{team}"; opacity: .5; font-size: .8em; margin-left: 8px; }}'
        )
    st.html("<style>" + "".join(rules) + "</style>")


def sector_stats(rankings: list[list[tuple[str, float, int]]], colors: dict[str, str]) -> list[str]:
    """Fastest S1/S2/S3 so far as three small stats (a size down from the main ones); hover shows P2 and P3."""
    out = []
    for n, ranking in enumerate(rankings, start=1):
        if not ranking:
            continue
        driver, secs, lap = ranking[0]
        rows = "".join(
            f'<div class="r"><span class="n">P{i}</span><span>{driver_dot(colors.get(d, "#999"))}{html.escape(d)}</span>'
            f'<span>{t:.3f}</span><span class="d">+{t - secs:.3f}</span></div>'
            for i, (d, t, _) in enumerate(ranking[1:], start=2)
        )
        pop = f'<div class="pl-pop"><div class="pl-label">Sector {n}</div>{rows}</div>' if rows else ""
        out.append(
            f'<div class="pl-stat sec"><div class="k">Best S{n}</div><div class="v">'
            f'{driver_dot(colors.get(driver, "#999"))}{html.escape(driver)} <span style="color:#A855F7">{secs:.3f}</span>'
            f"<small>L{lap}</small></div>{pop}</div>"
        )
    return out


NOTE_STYLE = {"FL": ("Fastest lap", "#A855F7"), "OUT": ("Retired", "#E10600")}


def notifications(notes: list[dict]) -> None:
    """Render race notifications (newest first) in a fixed stack at the top right, broadcast style."""
    cards = []
    for n in notes:
        title, color = NOTE_STYLE.get(n["kind"], (n["kind"], "#888888"))
        right = f'<div class="right" style="color:{color}">{n["right"]}</div>' if n.get("right") else "<div></div>"
        cards.append(
            f'<div class="pl-bc" style="--team:{n["color"]}"><div class="tab" style="background:{color}">'
            f'{html.escape(title)}</div><div class="slab"><div class="bar"></div><div class="who">'
            f'<div class="surname">{html.escape(n["name"])}</div><div class="team">{html.escape(n["team"])}</div>'
            f"</div>{right}</div></div>"
        )
    with st.container(key="pl-notes"):
        for card in cards:
            st.html(card)
