"""Shared look for the pit wall pages: global CSS, header, status strip, sidebar brand.

Colours here are theme-neutral (inherit the text colour, translucent greys)
so the same markup reads well in Streamlit's light and dark themes.
"""

import html

import pandas as pd
import streamlit as st

from pitlens.branding import NAME, TAGLINE
from pitlens.style import COMPOUND_COLORS

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
/* Fastest sectors: three small stats (a size down from the main ones), P2 and P3 on hover.
   light-dark() follows Streamlit's theme (it sets color-scheme on the app), not the OS. */
.pl-stat.sec { position: relative; min-width: 0; padding: 11px 14px 12px; cursor: default; }
.pl-stat.sec .v { font-size: 0.98rem; margin-top: 6px; }
.pl-stat.sec:is(:hover,:focus-within) .pl-pop { display: block; }
.pl-stat.sec:focus-visible { outline: 2px solid #55bfff; outline-offset: 3px; }

.pl-pop { display: none; position: absolute; top: calc(100% + 6px); left: 0; z-index: 50; min-width: 190px;
  padding: 8px 10px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.28);
  background: light-dark(rgba(250,250,250,0.98), rgba(23,27,34,0.98)); box-shadow: 0 8px 24px rgba(0,0,0,0.18);
  font-size: 0.82rem; font-weight: 500; font-variant-numeric: tabular-nums; }
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

/* Fastest-sector list beside the circuit map */
.pl-seclist { display: flex; flex-direction: column; gap: 16px; padding-top: 22px; }
.pl-secrow { display: grid; grid-template-columns: 26px 1fr; gap: 10px; align-items: center; }
.pl-secrow .num { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; color: #fff;
  font-size: 0.75rem; font-weight: 700; }
.pl-secrow .who { font-weight: 700; font-size: 0.98rem; line-height: 1.2; }
.pl-secrow .t { color: #A855F7; font-weight: 600; font-variant-numeric: tabular-nums; margin-left: 6px; }
.pl-secrow .meta { font-size: 0.76rem; opacity: 0.55; font-variant-numeric: tabular-nums; }

/* Race notifications, styled like the F1 broadcast graphics: a solid label tab, then a dark
   slab with the team colour bar, the surname in capitals and the time on the right. */
.st-key-pl-notes { position: fixed; top: 64px; right: 20px; width: 264px; z-index: 999990; gap: 6px;
  pointer-events: none; }
.pl-bc { animation: pl-in 260ms ease-out, pl-out 400ms ease-in 3.4s forwards; filter: drop-shadow(0 6px 14px rgba(0,0,0,0.25)); }
.pl-bc .tab { display: inline-block; padding: 2px 8px 1px; font-family: "Titillium Web", sans-serif; font-weight: 700;
  font-size: 0.6rem; letter-spacing: 0.14em; text-transform: uppercase; color: #fff; border-radius: 4px 4px 0 0; }
.pl-bc .slab { display: grid; grid-template-columns: 5px 1fr auto; align-items: center; background: #15151E; color: #fff;
  border-radius: 0 5px 5px 5px; overflow: hidden; min-height: 38px; }
.pl-bc .bar { align-self: stretch; background: var(--team); }
.pl-bc .who { padding: 5px 10px 6px; }
.pl-bc .surname { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 0.98rem; letter-spacing: 0.04em;
  text-transform: uppercase; line-height: 1.05; }
.pl-bc .team { font-size: 0.66rem; color: rgba(255,255,255,0.55); margin-top: 1px; }
.pl-bc .right { padding: 0 11px; font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 0.92rem;
  font-variant-numeric: tabular-nums; }
@keyframes pl-in { from { opacity: 0; transform: translateX(28px); } }
@keyframes pl-out { to { opacity: 0; transform: translateX(28px); visibility: hidden; } }

/* Pit stop list: one row per stop, newest first. It sizes to its card (container queries), not the window. */
.pl-pits-wrap { container-type: inline-size; }
.pl-pits { max-height: 430px; overflow-y: auto; }
.pl-pit { display: grid; grid-template-columns: 62px 64px minmax(118px, 1fr) 70px 70px 62px 118px; align-items: center;
  gap: 8px; padding: 8px 6px; border-bottom: 1px solid rgba(128,128,128,0.14); font-size: 0.9rem;
  font-variant-numeric: tabular-nums; }
.pl-pit.nostill { grid-template-columns: 62px 64px minmax(118px, 1fr) 70px 62px 118px; }
.pl-pit.head { border-bottom: 1px solid rgba(128,128,128,0.3); padding-top: 0; font-size: 0.64rem; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55; }
.pl-pit .num { text-align: right; }
.pl-pit.now { background: rgba(225,6,0,0.07); border-radius: 6px; }
.pl-pit .best { color: #A855F7; font-weight: 700; }
.pl-pit .muted { opacity: 0.45; }
.pl-pit .age { opacity: 0.55; font-size: 0.76rem; margin-left: 6px; }
.pl-pit .flag { font-size: 0.56rem; font-weight: 800; letter-spacing: 0.06em; padding: 1px 4px; border-radius: 3px;
  margin-left: 5px; background: #F5B700; color: #111; vertical-align: 1px; }
.pl-pit .flag.red { background: #E10600; color: #fff; }
.pl-pit .up { color: #16A34A; font-weight: 600; }
.pl-pit .down { color: #E10600; font-weight: 600; }
.pl-tyre { display: inline-grid; place-items: center; width: 21px; height: 21px; border-radius: 50%;
  border: 2.5px solid var(--c); font-size: 0.6rem; font-weight: 800; box-sizing: border-box; vertical-align: middle; }
.pl-pit .arrow { opacity: 0.4; margin: 0 5px; }
@container (max-width: 640px) {  /* narrower card: no tyre age, flag tag under the lap */
  .pl-pit { grid-template-columns: 46px 54px 62px 54px 56px 46px minmax(0, 1fr); gap: 6px; font-size: 0.84rem; }
  .pl-pit.nostill { grid-template-columns: 46px 54px 62px 54px 46px minmax(0, 1fr); }
  .pl-pit.head { font-size: 0.58rem; letter-spacing: 0.08em; }
  .pl-pit .age { display: none; }
  .pl-pit .flag { display: block; width: fit-content; margin: 2px 0 0; }
  .pl-pit .arrow { margin: 0 2px; }
}
@container (max-width: 420px) {  /* phones */
  .pl-pit { grid-template-columns: 40px 46px 50px 40px 36px 36px minmax(0, 1fr); gap: 4px; padding: 7px 2px;
    font-size: 0.78rem; }
  .pl-pit.nostill { grid-template-columns: 40px 46px 50px 40px 36px minmax(0, 1fr); }
  .pl-pit.head { font-size: 0.56rem; letter-spacing: 0.06em; }
  .pl-pit .arrow { margin: 0 1px; }
  .pl-tyre { width: 18px; height: 18px; border-width: 2px; font-size: 0.52rem; }
}
.st-key-card-views .pl-stat { padding: 10px 14px 11px; min-width: 0; }

/* Qualifying classification: Q1/Q2/Q3 times with the knockout lines between the groups */
.pl-qwrap { container-type: inline-size; }
.pl-q { display: grid; grid-template-columns: 32px 60px repeat(3, minmax(62px, 1fr)) 64px 126px; gap: 8px;
  align-items: center; padding: 7px 6px; border-bottom: 1px solid rgba(128,128,128,0.14); font-size: 0.9rem;
  font-variant-numeric: tabular-nums; }
.pl-q.head { font-size: 0.64rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55;
  border-bottom: 1px solid rgba(128,128,128,0.3); padding-top: 0; }
.pl-q .num { text-align: right; }
.pl-q .pos { opacity: 0.6; text-align: right; }
.pl-q .best { color: #A855F7; font-weight: 700; }
.pl-q .muted { opacity: 0.4; }
.pl-q.out { opacity: 0.72; }
.pl-q .left { font-size: 0.76rem; opacity: 0.6; margin-left: 4px; }
.pl-qcut { display: flex; align-items: center; gap: 8px; margin: 2px 0; font-size: 0.62rem; font-weight: 800;
  letter-spacing: 0.12em; text-transform: uppercase; color: #E10600; }
.pl-qcut::after { content: ""; flex: 1; border-top: 1.5px dashed rgba(225,6,0,0.6); }
@container (max-width: 560px) {
  .pl-q { grid-template-columns: 26px 52px repeat(3, minmax(54px, 1fr)) 60px; gap: 5px; font-size: 0.8rem; }
  .pl-q .ideal { display: none; }
}

/* Team page: one card per driver */
.pl-drv { padding: 12px 2px 14px; border-bottom: 1px solid rgba(128,128,128,0.14); }
.pl-drv:last-child { border-bottom: none; }
.pl-drv .name { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 1.25rem; line-height: 1.1; }
.pl-drv .code { font-size: 0.78rem; font-weight: 700; opacity: 0.5; margin-left: 6px; letter-spacing: 0.06em; }
.pl-drv .nums { display: grid; grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); gap: 6px 10px; margin-top: 10px; }
.pl-drv .nums div { font-size: 0.66rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.55; }
.pl-drv .nums b { display: block; font-size: 1.05rem; letter-spacing: 0; text-transform: none; opacity: 1;
  font-variant-numeric: tabular-nums; margin-top: 2px; }
.pl-drv .h2h { margin-top: 10px; font-size: 0.86rem; opacity: 0.85; }
.pl-drv .h2h b { font-variant-numeric: tabular-nums; }

/* Finishing positions as coloured cells (driver results, the season matrix) */
.pl-pos { display: inline-grid; place-items: center; min-width: 34px; height: 24px; padding: 0 5px; border-radius: 5px;
  font-size: 0.8rem; font-weight: 700; font-variant-numeric: tabular-nums; background: rgba(128,128,128,0.10); }
.pl-pos.p1 { background: #E8B931; color: #111; }
.pl-pos.p2 { background: #C4CAD3; color: #111; }
.pl-pos.p3 { background: #C9824A; color: #111; }
.pl-pos.pts { background: rgba(34,197,94,0.22); }
.pl-pos.out { background: rgba(225,6,0,0.18); color: #E10600; }
.pl-pos.none { background: transparent; opacity: 0.35; }
.pl-pos.pole { box-shadow: inset 0 0 0 2px #A855F7; }
.pl-pos.fl { text-decoration: underline 2px #A855F7; text-underline-offset: 3px; }

/* A driver's season, race by race */
.pl-res { display: grid; grid-template-columns: 30px minmax(0, 1fr) 44px 40px 52px 48px; gap: 8px; align-items: center;
  padding: 6px 4px; border-bottom: 1px solid rgba(128,128,128,0.12); font-size: 0.88rem; font-variant-numeric: tabular-nums; }
.pl-res.sprints { grid-template-columns: 30px minmax(0, 1fr) 44px 40px 52px 48px 48px; }
.pl-res > span:nth-child(2) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 520px) {
  .pl-res, .pl-res.sprints { grid-template-columns: 20px minmax(0, 1fr) 34px 30px 40px 40px; gap: 5px; font-size: 0.8rem; }
  .pl-res.sprints { grid-template-columns: 20px minmax(0, 1fr) 34px 30px 40px 40px 38px; }
  .pl-res.head { font-size: 0.52rem; letter-spacing: 0.06em; }
}
/* The championship: standings, the results grid and the round-by-round winners */
.pl-std { display: grid; grid-template-columns: 26px minmax(0, 1fr) 40px 52px 52px; gap: 8px; align-items: center;
  padding: 6px 4px; border-bottom: 1px solid rgba(128,128,128,0.12); font-size: 0.88rem; font-variant-numeric: tabular-nums; }
.pl-std.head, .pl-rw.head { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  opacity: 0.55; border-bottom: 1px solid rgba(128,128,128,0.3); }
.pl-std .num, .pl-rw .num { text-align: right; }
.pl-std > span:nth-child(2) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pl-std .team { font-size: 0.78rem; opacity: 0.5; margin-left: 6px; }
.pl-std a, .pl-rw a, .pl-mx a { color: inherit; text-decoration: none; }
.pl-std a:hover, .pl-rw a:hover, .pl-mx a:hover { text-decoration: underline; }
.pl-std .muted, .pl-rw .muted { opacity: 0.45; }
.pl-mx { overflow-x: auto; }
.pl-mx table { border-collapse: collapse; font-size: 0.78rem; font-variant-numeric: tabular-nums; }
.pl-mx th { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.06em; opacity: 0.6; padding: 0 1px 6px; text-align: center; }
.pl-mx td { padding: 1px; text-align: center; }
.pl-mx td.who, .pl-mx th.who { text-align: left; padding-right: 8px; white-space: nowrap; font-weight: 700;
  position: sticky; left: 0; background: light-dark(#F5F6F8, #0B0D11); z-index: 1; }
.pl-mx td.pts { padding-left: 8px; text-align: right; font-weight: 700; }
.pl-mx .pl-pos { min-width: 27px; height: 21px; font-size: 0.72rem; padding: 0 3px; border-radius: 4px; }
.pl-rw { display: grid; grid-template-columns: 26px minmax(0, 1.6fr) repeat(4, minmax(0, 1fr)); gap: 8px; align-items: center;
  padding: 6px 4px; border-bottom: 1px solid rgba(128,128,128,0.12); font-size: 0.86rem; }
.pl-rw > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 520px) {
  .pl-std .team { display: none; }
  .pl-rw { grid-template-columns: 20px minmax(0, 1.3fr) repeat(4, minmax(0, 1fr)); gap: 4px; font-size: 0.76rem; }
  .pl-rw.head { font-size: 0.5rem; letter-spacing: 0.04em; }
}
/* A circuit, year by year */
.pl-cy { display: grid; grid-template-columns: 46px repeat(3, minmax(0, 1fr)) minmax(0, 1.2fr) 96px; gap: 10px;
  align-items: center; padding: 8px 4px; border-bottom: 1px solid rgba(128,128,128,0.12); font-size: 0.86rem;
  font-variant-numeric: tabular-nums; }
.pl-cy.head { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55;
  border-bottom: 1px solid rgba(128,128,128,0.3); }
.pl-cy > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pl-cy > span:nth-child(5), .pl-cy > span:nth-child(6) { white-space: normal; }
.pl-cy small { opacity: 0.55; margin-left: 4px; }
.pl-cy a { color: inherit; font-weight: 700; }
.pl-cy .muted { opacity: 0.45; }
.pl-cy .pl-tyre { margin-right: 2px; }
@media (max-width: 620px) {
  .pl-cy { grid-template-columns: 38px repeat(3, minmax(0, 1fr)) 70px; gap: 6px; font-size: 0.78rem; }
  .pl-cy > span:nth-child(5) { display: none; }
  .pl-cy small { display: block; margin-left: 0; }
}
.pl-hl { padding: 10px 0; border-bottom: 1px solid rgba(128,128,128,0.12); }
.pl-hl:last-child { border-bottom: none; }
.pl-hl .k { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.6; }
.pl-hl .v { font-size: 1.25rem; font-weight: 700; margin-top: 2px; font-variant-numeric: tabular-nums; }
.pl-hl .d { font-size: 0.84rem; opacity: 0.7; margin-top: 1px; }
.pl-res.head { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55;
  border-bottom: 1px solid rgba(128,128,128,0.3); }
.pl-res .num { text-align: right; }
.pl-res a { color: inherit; text-decoration: none; }
.pl-res a:hover { text-decoration: underline; }
.pl-res .muted { opacity: 0.45; }

/* Sidebar brand */
.pl-brand { display: flex; align-items: center; gap: 10px; margin: 0 0 6px; }
.pl-brand .mark { width: 8px; height: 30px; border-radius: 2px; background: #E10600; transform: skewX(-14deg); }
.pl-brand .name { font-family: "Titillium Web", sans-serif; font-weight: 700; font-size: 1.45rem; letter-spacing: 0.01em;
  line-height: 1; }
.pl-brand .tag { font-size: 0.72rem; opacity: 0.55; margin-top: 3px; }
.pl-brand .context { font-size: 0.66rem; opacity: 0.45; margin-top: 5px; }
.pl-foot { font-size: 0.72rem; opacity: 0.5; line-height: 1.45; }

/* Cards (keyed containers) get a little more air */
[class*="st-key-card-"] { padding: 10px 12px; }

/* Views bar: scroll sideways rather than wrapping onto a second row */
.st-key-view [data-testid="stButtonGroup"] { overflow-x: auto; scrollbar-width: none; }
.st-key-view button { padding-left: 0.6rem; padding-right: 0.6rem; }

/* Replay control bar */
.st-key-controls { align-items: center; }
.st-key-controls [data-testid="stSlider"] { padding-top: 0.2rem; }

/* Phones: less side padding, stats two to a row */
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; padding-top: 4rem; }
  .pl-title { font-size: 2rem; }
  .pl-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .pl-stat { min-width: 0; padding: 9px 12px 10px; }
  .pl-stat .v { font-size: 1.02rem; overflow: hidden; text-overflow: ellipsis; }
  .pl-stat.sec .v { font-size: 0.9rem; }
  .pl-stat.sec:last-child .pl-pop { left: auto; right: 0; }
  [class*="st-key-card-"] { padding: 6px 4px; }
  .st-key-pl-notes { right: 10px; top: 56px; width: 236px; }
}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def sidebar_brand(tagline: str) -> None:
    st.sidebar.html(
        f'<div class="pl-brand"><div class="mark"></div><div><div class="name">{NAME}</div>'
        f'<div class="tag">{TAGLINE}</div><div class="context">{html.escape(tagline)}</div></div></div>'
    )


def sidebar_footer() -> None:
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
FLAG_TAGS = {"Safety car": ("SC", ""), "VSC": ("VSC", ""), "VSC ending": ("VSC", ""), "Red flag": ("RED", " red")}


def tyre(compound) -> str:
    """A small tyre: the compound's letter in a ring of its colour, as on the broadcast."""
    c = compound if isinstance(compound, str) and compound in COMPOUND_COLORS else "UNKNOWN"
    return (f'<span class="pl-tyre" style="--c:{COMPOUND_COLORS[c]}" title="{c.title()}">'
            f'{TYRE_LETTERS.get(c, "?")}</span>')


def _places(before, after) -> str:
    if pd.isna(before) or pd.isna(after):
        return '<span class="muted">–</span>'
    delta = int(before) - int(after)
    change = (f' <span class="up">+{delta}</span>' if delta > 0 else
              f' <span class="down">−{-delta}</span>' if delta < 0 else "")
    return f"P{int(before)} → P{int(after)}{change}"


def pit_table(stops, colors: dict[str, str], lap: int) -> None:
    """Every stop so far, newest first: lap, driver, tyres, pit lane and stationary time, cost, places.

    The quickest pit lane and stationary times are purple, like a fastest lap. Pit lane times
    flagged false in `LaneOk` (implausibly short) are greyed out. Cost under a safety car or VSC
    is greyed too: the field's lap times swing too much then for it to be more than a rough
    guide. Cost and places need the out-lap, so a stop made on the current lap shows them once
    the next lap is done.
    """
    still = stops["Stationary"].notna().any()
    lane_ok = stops["LaneOk"] if "LaneOk" in stops else pd.Series(True, index=stops.index)
    still_ok = stops["StillOk"] if "StillOk" in stops else pd.Series(True, index=stops.index)
    best_lane = stops.loc[lane_ok, "LaneTime"].min()
    best_still = stops.loc[still_ok, "Stationary"].min() if still else None
    cls = "pl-pit" + ("" if still else " nostill")

    def secs(value, best, ok=True) -> str:
        if pd.isna(value):
            return '<span class="muted">–</span>'
        if value >= 100:  # cars held in the pit lane under a red flag, or repairs in the garage
            minutes, rest = divmod(round(value, 1), 60)
            return (f'<span class="muted" title="Held in the pit lane (red flag) or in the garage">'
                    f"{int(minutes)}:{rest:04.1f}</span>")
        if not ok:
            why = ("Too short for a normal trip down the pit lane, as when cars are sent through it behind the "
                   "safety car" if pd.isna(best) or value < best else "Far longer than a normal stop: repairs, or held")
            return f'<span class="muted" title="{why}">{value:.1f}</span>'
        return f'<span class="best">{value:.1f}</span>' if value == best else f"{value:.1f}"

    def stationary(value, best, ok) -> str:
        if pd.notna(value) and not ok:
            return f'<span class="muted" title="A long stop: a penalty served, or repairs">{value:.1f}</span>'
        return secs(value, best)

    head = (f'<div class="{cls} head"><span>Lap</span><span>Driver</span><span>Tyres</span>'
            f'<span class="num">Pit lane</span>' + ('<span class="num">Stopped</span>' if still else "")
            + '<span class="num">Cost</span><span>Places</span></div>')
    rows = []
    for s in stops.sort_values(["Lap", "Driver"], ascending=[False, True]).itertuples():
        pending = s.Lap + 1 > lap  # out-lap not finished yet
        flag, flag_cls = FLAG_TAGS.get(s.Status, ("", ""))
        flag_html = f'<span class="flag{flag_cls}">{flag}</span>' if flag else ""
        age = (f'<span class="age">{int(s.TyreAge)} lap{"" if int(s.TyreAge) == 1 else "s"}</span>'
               if pd.notna(s.TyreAge) else "")
        if pending:
            cost = '<span class="muted">…</span>'
        elif pd.isna(s.Loss):
            cost = '<span class="muted">–</span>'
        elif s.Neutralised and s.Loss < 0:  # the field queueing behind the safety car, not a real gain
            cost = ('<span class="muted" title="Under a safety car or VSC the field\'s lap times swing too much '
                    'to measure this stop">–</span>')
        elif s.Neutralised:
            cost = f'<span class="muted" title="Rough: under a safety car or VSC">{s.Loss:.1f}</span>'
        else:
            cost = f"{s.Loss:.1f}"
        places = '<span class="muted">…</span>' if pending else _places(s.PosBefore, s.PosAfter)
        rows.append(
            f'<div class="{cls}{" now" if s.Lap == lap else ""}"><span>L{s.Lap}{flag_html}</span>'
            f'<span>{driver_dot(colors.get(s.Driver, "#999"))}<b>{html.escape(s.Driver)}</b></span>'
            f'<span>{tyre(s.From)}<span class="arrow">→</span>{tyre(s.To)}{age}</span>'
            f'<span class="num">{secs(s.LaneTime, best_lane, lane_ok[s.Index])}</span>'
            + (f'<span class="num">{stationary(s.Stationary, best_still, still_ok[s.Index])}</span>' if still else "")
            + f'<span class="num">{cost}</span><span>{places}</span></div>'
        )
    st.html(f'<div class="pl-pits-wrap">{head}<div class="pl-pits">{"".join(rows)}</div></div>')


def _laptime(seconds) -> str:
    if pd.isna(seconds):
        return ""
    minutes, rest = divmod(round(float(seconds), 3), 60)
    return f"{int(minutes)}:{rest:06.3f}"


def quali_table(results, ideal, colors: dict[str, str]) -> None:
    """Qualifying classification: Q1/Q2/Q3 times (fastest of each part in purple), gap to pole, and the
    ideal lap from each driver's best sectors with what was left on the table; dashed lines mark the
    knockouts."""
    best = {q: results[q].min() for q in ("Q1", "Q2", "Q3")}
    pole = results["Q3"].min() if results["Q3"].notna().any() else results[["Q1", "Q2", "Q3"]].min().min()
    ideal = ideal.set_index("Driver") if len(ideal) else ideal
    head = ('<div class="pl-q head"><span class="num">Pos</span><span>Driver</span><span class="num">Q1</span>'
            '<span class="num">Q2</span><span class="num">Q3</span><span class="num">Gap</span>'
            '<span class="num ideal">Ideal lap</span></div>')
    rows, group = [], ""
    for r in results.itertuples():
        if r.Out != group:
            rows.append(f'<div class="pl-qcut">Out in {r.Out}</div>')
            group = r.Out
        cells = []
        for q in ("Q1", "Q2", "Q3"):
            t = getattr(r, q)
            cls = "num best" if pd.notna(t) and t == best[q] else "num"
            cells.append(f'<span class="{cls}">{_laptime(t) or "<span class=muted>–</span>"}</span>')
        own = min((getattr(r, q) for q in ("Q1", "Q2", "Q3") if pd.notna(getattr(r, q))), default=float("nan"))
        if r.Out == "":
            final = r.Q3 if pd.notna(r.Q3) else own
        else:
            final = getattr(r, r.Out)
        gap = "" if pd.isna(final) or pd.isna(pole) else ("Pole" if final == pole else f"+{final - pole:.3f}")
        lap = ideal.loc[r.Driver] if r.Driver in getattr(ideal, "index", []) else None
        ideal_html = ""
        if lap is not None and pd.notna(lap["Ideal"]):
            left = f'<span class="left">−{lap["LeftOnTable"]:.3f}</span>' if lap["LeftOnTable"] > 0.0005 else ""
            ideal_html = f"{_laptime(lap['Ideal'])}{left}"
        pos = "" if pd.isna(r.Position) else int(r.Position)
        rows.append(
            f'<div class="pl-q{" out" if r.Out else ""}"><span class="pos">{pos}</span>'
            f'<span>{driver_dot(colors.get(r.Driver, "#999"))}<b>{html.escape(str(r.Driver))}</b></span>'
            + "".join(cells) + f'<span class="num">{gap}</span><span class="num ideal">{ideal_html}</span></div>'
        )
    st.html(f'<div class="pl-qwrap">{head}{"".join(rows)}</div>')


def team_drivers(drivers, battles, color: str, *, year: int | None = None) -> None:
    """A card per driver of a team: season numbers and how they fared against their teammate."""
    battle = battles.set_index("Driver") if len(battles) else battles
    cards = []
    for d in drivers.itertuples():
        nums = [("Races", d.Races), ("Points", f"{d.Points:.0f}"), ("Wins", d.Wins), ("Podiums", d.Podiums),
                ("Best", f"P{d.Best}" if d.Best else "–"),
                ("Avg finish", f"{d.AverageFinish:.1f}" if pd.notna(d.AverageFinish) else "–"), ("DNFs", d.Dnf)]
        h2h = ""
        if d.Driver in getattr(battle, "index", []):
            b = battle.loc[d.Driver]
            parts = []
            if b["QualiOf"]:
                parts.append(f"qualifying <b>{int(b['QualiWon'])}–{int(b['QualiOf'] - b['QualiWon'])}</b>")
            if b["RaceOf"]:
                parts.append(f"races <b>{int(b['RaceWon'])}–{int(b['RaceOf'] - b['RaceWon'])}</b>")
            if pd.notna(b["QualiGap"]):
                parts.append(f"qualifying gap <b>{b['QualiGap']:+.3f} s</b>")
            if parts:
                h2h = f'<div class="h2h">Against their teammate: {" · ".join(parts)}</div>'
        cells = "".join(f"<div>{html.escape(k)}<b>{v}</b></div>" for k, v in nums)
        name = html.escape(d.FullName)
        if year is not None:
            name = f'<a href="./drivers?year={year}&driver={d.Driver}" target="_self">{name}</a>'
        cards.append(f'<div class="pl-drv"><div class="name">{driver_dot(color)}{name}'
                     f'<span class="code">{html.escape(d.Driver)}</span></div><div class="nums">{cells}</div>{h2h}</div>')
    st.html("".join(cards))


def position_cell(position, classified: bool = True, dsq: bool = False, pole: bool = False,
                  fastest: bool = False, points_from: int = 10) -> str:
    """A finishing position as a small coloured cell: gold, silver and bronze for the podium, green in the
    points, red for a retirement; a purple ring for pole, a purple underline for the fastest lap."""
    extra = (" pole" if pole else "") + (" fl" if fastest else "")
    if dsq:
        return f'<span class="pl-pos out{extra}" title="Disqualified">DSQ</span>'
    if not classified or pd.isna(position):
        return f'<span class="pl-pos out{extra}" title="Did not finish">DNF</span>'
    p = int(position)
    cls = {1: "p1", 2: "p2", 3: "p3"}.get(p, "pts" if p <= points_from else "")
    return f'<span class="pl-pos {cls}{extra}">{p}</span>'


def driver_results_table(rows, year: int, *, driver: str | None = None) -> None:
    """A driver's season: one row per Grand Prix with grid, finish, points and qualifying; each race
    links to its replay."""
    sprints = "Sprint" in rows and rows["Sprint"].notna().any()
    cls = "pl-res sprints" if sprints else "pl-res"
    head = (f'<div class="{cls} head"><span>Rd</span><span>Grand Prix</span><span class="num">Quali</span>'
            '<span class="num">Grid</span><span class="num">Finish</span>'
            + ('<span class="num">Sprint</span>' if sprints else "") + '<span class="num">Points</span></div>')
    out = []
    for r in rows.itertuples():
        grid = "" if pd.isna(r.Grid) else ('<span class="muted">pit</span>' if r.Grid <= 0 else int(r.Grid))
        quali = "" if pd.isna(r.Quali) else int(r.Quali)
        points = f"{r.Points:g}" if r.Points else '<span class="muted">0</span>'
        sprint = "" if not sprints or pd.isna(r.Sprint) else int(r.Sprint)
        out.append(
            f'<div class="{cls}"><span class="muted">{r.Round}</span>'
            f'<span><a href="./?year={year}&round={r.Round}{"&drivers=" + driver if driver else ""}" '
            f'target="_self">{html.escape(r.Event)}</a></span>'
            f'<span class="num">{quali}</span><span class="num">{grid}</span>'
            f'<span class="num">{position_cell(r.Position, r.Classified, r.Dsq, r.Pole, r.Fastest)}</span>'
            + (f'<span class="num">{sprint}</span>' if sprints else "") + f'<span class="num">{points}</span></div>'
        )
    st.html(f"{head}{''.join(out)}")


def highlights(items: list[tuple[str, str, str]]) -> None:
    """A short list of standout numbers: label, value and a line of detail."""
    rows = "".join(f'<div class="pl-hl"><div class="k">{html.escape(k)}</div><div class="v">{html.escape(v)}</div>'
                   + (f'<div class="d">{html.escape(d)}</div>' if d else "") + "</div>" for k, v, d in items)
    st.html(rows)


def standings_table(table, colors: dict[str, str], year: int) -> None:
    """The drivers' championship: position, driver (opening their Drivers page), team, wins, points and
    the gap to the leader."""
    lead = table["Points"].iloc[0] if len(table) else 0
    head = ('<div class="pl-std head"><span>Pos</span><span>Driver</span><span class="num">Wins</span>'
            '<span class="num">Points</span><span class="num">Gap</span></div>')
    rows = []
    for i, r in enumerate(table.itertuples(), start=1):
        gap = "" if i == 1 else f"-{lead - r.Points:g}"
        rows.append(
            f'<div class="pl-std"><span class="muted">{i}</span>'
            f'<span>{driver_dot(colors.get(r.Team, "#888888"))}'
            f'<a href="./drivers?year={year}&driver={r.Driver}" target="_self">{html.escape(r.FullName)}</a>'
            f'<span class="team">{html.escape(r.Team)}</span></span>'
            f'<span class="num">{r.Wins or ""}</span><span class="num"><b>{r.Points:g}</b></span>'
            f'<span class="num muted">{gap}</span></div>'
        )
    st.html(head + "".join(rows))


def results_matrix(results, table, rounds, poles, fastest, colors: dict[str, str], year: int) -> None:
    """Every Grand Prix finish in one grid: drivers down the side in championship order, rounds across
    (each opening its replay), points at the end."""
    gp = results[results["Kind"] == "R"].set_index(["Driver", "Round"])
    events = dict(zip(rounds["Round"], rounds["Event"]))
    head = '<th class="who"></th>' + "".join(
        f'<th><a href="./?year={year}&round={r}" target="_self" title="{html.escape(events[r])}">{r}</a></th>'
        for r in rounds["Round"]) + '<th class="pts">Pts</th>'
    body = []
    for d in table.itertuples():
        cells = []
        for r in rounds["Round"]:
            if (d.Driver, r) not in gp.index:
                cells.append("<td></td>")
                continue
            x = gp.loc[(d.Driver, r)]
            if isinstance(x, pd.DataFrame):
                x = x.iloc[0]
            cell = position_cell(x["Position"], x["Classified"], x["Dsq"], poles.get(r) == d.Driver,
                                 fastest.get(r) == d.Driver)
            cells.append(f'<td title="{html.escape(events[r])}">{cell}</td>')
        who = (f'<td class="who">{driver_dot(colors.get(d.Team, "#888888"))}'
               f'<a href="./drivers?year={year}&driver={d.Driver}" target="_self" title="{html.escape(d.FullName)}">'
               f'{html.escape(d.Driver)}</a></td>')
        body.append(f"<tr>{who}{''.join(cells)}<td class=\"pts\">{d.Points:g}</td></tr>")
    st.html(f'<div class="pl-mx"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def round_winners_table(winners, results, colors: dict[str, str], year: int) -> None:
    """Round by round: pole, winner, fastest lap and the sprint winner, each Grand Prix opening its replay."""
    team = results.drop_duplicates(["Round", "Driver"]).set_index(["Round", "Driver"])["Team"]

    def who(rnd, driver) -> str:
        if not isinstance(driver, str):
            return '<span class="muted">–</span>'
        return driver_dot(colors.get(team.get((rnd, driver)), "#888888")) + html.escape(driver)

    sprints = winners["SprintWinner"].notna().any()
    head = ('<div class="pl-rw head"><span>Rd</span><span>Grand Prix</span><span>Pole</span><span>Winner</span>'
            '<span>Fastest lap</span><span>' + ("Sprint" if sprints else "") + "</span></div>")
    rows = []
    for w in winners.itertuples():
        event = html.escape(w.Event.replace(" Grand Prix", ""))
        rows.append(
            f'<div class="pl-rw"><span class="muted">{w.Round}</span>'
            f'<span><a href="./?year={year}&round={w.Round}" target="_self">{event}</a></span>'
            f"<span>{who(w.Round, w.Pole)}</span><span><b>{who(w.Round, w.Winner)}</b></span>"
            f"<span>{who(w.Round, w.Fastest)}</span>"
            f"<span>{who(w.Round, w.SprintWinner) if w.Sprint else ''}</span></div>"
        )
    st.html(head + "".join(rows))


def circuit_years_table(years) -> None:
    """A circuit's Grands Prix, one row per year: winner (and where they started), pole, fastest lap,
    safety cars and red flags, and the winner's tyres. Each year opens its replay."""
    letters = {v: k for k, v in TYRE_LETTERS.items()}

    def who(driver, color, extra="") -> str:
        if not isinstance(driver, str):
            return '<span class="muted">–</span>'
        return f"{driver_dot(color or '#888888')}{html.escape(driver)}{extra}"

    head = ('<div class="pl-cy head"><span>Year</span><span>Winner</span><span>Pole</span><span>Fastest lap</span>'
            "<span>Neutralised</span><span>Winner's tyres</span></div>")
    rows = []
    for y in years.itertuples():
        grid = f"<small>from P{y.WinnerGrid}</small>" if y.WinnerGrid else ""
        pole = f"<small>{_laptime(y.PoleTime)}</small>" if pd.notna(y.PoleTime) else ""
        fastest = f"<small>{_laptime(y.FastestTime)}</small>" if pd.notna(y.FastestTime) else ""
        flags = [f"{n} {name}{'s' if n > 1 and name != 'VSC' else ''}" for n, name in
                 ((y.SafetyCars, "safety car"), (y.VSCs, "VSC"), (y.RedFlags, "red flag")) if n]
        if y.Wet:
            flags.append("wet")
        if y.Laps < y.Scheduled:
            flags.append(f"{y.Laps} of {y.Scheduled} laps")
        tyres = "".join(tyre(letters.get(c, "UNKNOWN")) for c in y.WinnerTyres.split("-") if c)
        rows.append(
            f'<div class="pl-cy"><span><a href="./?year={y.Year}&round={y.Round}" target="_self">{y.Year}</a></span>'
            f"<span><b>{who(y.Winner, y.WinnerColor, grid)}</b></span><span>{who(y.Pole, y.PoleColor, pole)}</span>"
            f"<span>{who(y.Fastest, y.FastestColor, fastest)}</span>"
            f'<span>{html.escape(", ".join(flags)) if flags else "<span class=muted>none</span>"}</span>'
            f"<span>{tyres}</span></div>"
        )
    st.html(head + "".join(rows))
