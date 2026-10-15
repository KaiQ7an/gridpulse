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
[data-testid="stMainBlockContainer"] { padding-top: 4.6rem; padding-bottom: 3rem; max-width: 1680px; }
[data-testid="stSidebarUserContent"] { padding-top: 1.2rem; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* Page header */
.pl-eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
  color: #E10600; margin-bottom: 0.15rem; }
.pl-title { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 2.15rem; line-height: 1.08;
  margin: 0; }
.pl-sub { opacity: 0.62; font-size: 0.9rem; margin-top: 0.3rem; }

/* Status strip: small labelled values in a row */
.pl-strip { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 4px; }
.pl-stat { border: 1px solid rgba(128,128,128,0.22); border-radius: 8px; padding: 7px 12px 8px; min-width: 96px;
  background: rgba(128,128,128,0.04); }
.pl-stat .k { font-size: 0.64rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55; }
.pl-stat .v { font-size: 1.08rem; font-weight: 600; font-variant-numeric: tabular-nums; margin-top: 2px;
  white-space: nowrap; }
.pl-stat .v small { font-size: 0.78rem; font-weight: 500; opacity: 0.6; margin-left: 4px; }
.pl-pill { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 0.82rem; font-weight: 700;
  letter-spacing: 0.04em; text-transform: uppercase; }
.pl-dot { display: inline-block; width: 4px; height: 14px; border-radius: 2px; margin-right: 7px; vertical-align: -2px; }

/* Section labels inside cards */
.pl-label { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.55;
  margin: 0 0 2px; }
.pl-note { font-size: 0.82rem; opacity: 0.6; margin: 0 0 6px; }

/* Sidebar brand */
.pl-brand { display: flex; align-items: center; gap: 10px; margin: 0 0 6px; }
.pl-brand .mark { width: 8px; height: 30px; border-radius: 2px; background: #E10600; transform: skewX(-14deg); }
.pl-brand .name { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 1.45rem; letter-spacing: 0.01em;
  line-height: 1; }
.pl-brand .tag { font-size: 0.72rem; opacity: 0.55; margin-top: 3px; }
.pl-foot { font-size: 0.72rem; opacity: 0.5; line-height: 1.45; }

/* Cards (keyed containers) get a little more air */
[class*="st-key-card-"] { padding: 2px 4px; }

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
        '<div class="pl-foot">Unofficial project. Timing data from the public F1 live-timing archive via FastF1. '
        "Not associated with Formula 1 or any team.</div>"
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


def stat(key: str, value: str, small: str = "", value_html: str | None = None) -> str:
    """One labelled value for `strip`. Pass `value_html` for pre-formatted markup."""
    v = value_html if value_html is not None else html.escape(value)
    s = f"<small>{html.escape(small)}</small>" if small else ""
    return f'<div class="pl-stat"><div class="k">{html.escape(key)}</div><div class="v">{v}{s}</div></div>'


def strip(stats: list[str]) -> None:
    st.html('<div class="pl-strip">' + "".join(stats) + "</div>")


def status_pill(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("rgba(128,128,128,0.18)", "inherit"))
    return f'<span class="pl-pill" style="background:{bg};color:{fg}">{html.escape(status)}</span>'


def driver_dot(color: str) -> str:
    return f'<span class="pl-dot" style="background:{color}"></span>'
