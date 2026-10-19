"""Compact, keyboard-accessible DTM navigation, styled from native radio inputs."""

from urllib.parse import quote

import streamlit as st

ICONS = {
    'championship': '<path d="M8 3h8v5a4 4 0 0 1-8 0V3Zm0 2H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 1v6m-4 3h8m-7-3h6"/>',
    'weekend': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
    'drivers': '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    'circuits': '<path d="M7 3H5a2 2 0 0 0-2 2v3a3 3 0 0 0 3 3h1a2 2 0 0 1 2 2v6a2 2 0 0 0 2 2h6a4 4 0 0 0 4-4v-4a2 2 0 0 0-2-2h-3a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>',
    'compare': '<path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/>',
    'teams': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-17a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v3"/>',
}


def render(views: dict, target=None):
    rules = '''
.st-key-dtm_view [role="radiogroup"] {gap:4px;width:100%}
.st-key-dtm_view [role="radiogroup"] > div {width:100%}
.st-key-dtm_view label[data-testid="stRadioOption"] {
  display:flex!important;width:100%;box-sizing:border-box;margin:0!important;padding:10px 12px!important;border-radius:8px;
  border:1px solid transparent;cursor:pointer;position:relative;align-items:center;gap:12px;
  transition:background .15s,border-color .15s,color .15s;
}
.st-key-dtm_view label[data-testid="stRadioOption"] > div > div:first-child {display:none}
.st-key-dtm_view label[data-testid="stRadioOption"] > div:last-child {padding:0}
.st-key-dtm_view label[data-testid="stRadioOption"] p {font-size:.9rem;font-weight:500;line-height:1.5}
.st-key-dtm_view label[data-testid="stRadioOption"]:hover {background:rgba(128,128,128,.09)}
.st-key-dtm_view label[data-testid="stRadioOption"][data-selected] {
  background:rgba(225,6,0,.07);border-color:rgba(225,6,0,.12);color:var(--gp-accent);
}
.st-key-dtm_view label[data-testid="stRadioOption"][data-selected]::after {
  content:"";position:absolute;left:-1px;top:12px;bottom:12px;width:3px;background:#E10600;border-radius:2px;
}
.st-key-dtm_view label[data-testid="stRadioOption"][data-focus-visible] {outline:2px solid #55bfff;outline-offset:2px}
.st-key-dtm_view label[data-testid="stRadioOption"]::before {
  content:"";width:18px;height:18px;flex:0 0 18px;background:currentColor;opacity:.7;
  mask-size:contain;mask-position:center;mask-repeat:no-repeat;
}
.st-key-dtm_refresh button {font-size:.8rem;min-height:32px;padding:5px 10px;opacity:.72}
.st-key-dtm_refresh button p {font-size:.8rem}
.st-key-dtm_refresh button:hover {opacity:1}
.dtm-menu-caption {font-size:.75rem;font-weight:600;letter-spacing:.1em;color:var(--gp-muted);text-transform:uppercase;margin:10px 0 6px}
.dtm-foot {border-top:1px solid rgba(128,128,128,.16);padding-top:12px;margin-top:8px;font-size:.68rem;line-height:1.6;opacity:.5}
.dtm-foot a {color:inherit;text-decoration:none}
.dtm-foot a:hover {text-decoration:underline;opacity:1}
@media(prefers-reduced-motion:reduce){.st-key-dtm_view label[data-testid="stRadioOption"]{transition:none}}
'''
    for i, view in enumerate(views, 1):
        path = ICONS[view]
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
        rules += f'.st-key-dtm_view [role="radiogroup"] > div:nth-child({i}) label::before {{mask-image:url("data:image/svg+xml,{quote(svg)}")}}'
    st.html(f"<style>{rules}</style>")
    target = st.sidebar if target is None else target
    with target.container():
        st.html('<div class="dtm-menu-caption">Explore DTM</div>')
        st.radio("Explore DTM", list(views), format_func=views.get, key="dtm_view", label_visibility="collapsed", width="stretch")


PAGE_ICONS = {
    "": '<path d="m3 11 9-8 9 8M5 10v11h5v-7h4v7h5V10"/>',
    "replay": '<path d="M5 21V3m0 1h14l-2 4 2 4H5m0-8 4 4 4-4 4 4M5 12l4-4 4 4 4-4"/>',
    "qualifying": '<circle cx="12" cy="14" r="7"/><path d="M9 2h6m-3 0v5m5 1 2-2m-7 8 3-3"/>',
    "onboard": '<path d="M4 19a9 9 0 1 1 16 0H4Zm8-7 4-4M6 14h1m5-8v1m5 7h1"/>',
    "season": ICONS["championship"], "teams": ICONS["teams"], "drivers": ICONS["drivers"],
    "circuits": '<path d="M7 3H5a2 2 0 0 0-2 2v3a3 3 0 0 0 3 3h1a2 2 0 0 1 2 2v6a2 2 0 0 0 2 2h6a4 4 0 0 0 4-4v-4a2 2 0 0 0-2-2h-3a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>',
    "dtm": '<path d="m4 10 2-6h12l2 6M3 10h18v8H3v-8Zm2 8v3m14-3v3M6 14h2m8 0h2"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
}


def render_pages(pages: list, current: str, series: str, *, caption: bool = True, target=None,
                 suffix: str = "", secondary: bool = False) -> None:
    """Use native page links so URLs, browser history and Streamlit state keep working."""
    rules = '''
.st-key-series-navigation [data-testid="stPageLink-NavLink"] {
 display:flex!important;align-items:center;gap:12px;position:relative;box-sizing:border-box;
 width:100%;padding:10px 12px;border-radius:8px;border:1px solid transparent;
 color:inherit;text-decoration:none;transition:background .15s,border-color .15s,color .15s;
}
.st-key-series-navigation [data-testid="stPageLink-NavLink"] p {font-size:.9rem;font-weight:500;line-height:1.5}
.st-key-series-navigation [data-testid="stPageLink-NavLink"]:hover {background:rgba(128,128,128,.09)}
.st-key-series-navigation [data-testid="stPageLink-NavLink"]:focus-visible {outline:2px solid #55bfff;outline-offset:2px}
.st-key-series-navigation [data-testid="stPageLink-NavLink"]::before {
 content:"";width:18px;height:18px;flex:0 0 18px;background:currentColor;opacity:.7;
 mask-size:contain;mask-position:center;mask-repeat:no-repeat;
}
.st-key-series-navigation [data-testid="stVerticalBlock"] {gap:4px}
.series-menu-caption {font-size:.75rem;font-weight:600;letter-spacing:.1em;color:var(--gp-muted);
 text-transform:uppercase;margin:10px 0 6px}
@media(prefers-reduced-motion:reduce){.st-key-series-navigation [data-testid="stPageLink-NavLink"]{transition:none}}
'''
    rules = rules.replace(".st-key-series-navigation", f".st-key-series-navigation{suffix}")
    for page in pages:
        route = page.url_path
        path = PAGE_ICONS[route]
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
        selector = f'.st-key-series-nav-{route or "home"}{suffix} [data-testid="stPageLink-NavLink"]'
        rules += f'{selector}::before {{mask-image:url("data:image/svg+xml,{quote(svg)}")}}'
        if route == current:
            rules += (f'{selector}{{background:rgba(225,6,0,.07);border-color:rgba(225,6,0,.12);color:var(--gp-accent)}}'
                      f'{selector}::after{{content:"";position:absolute;left:-1px;top:12px;bottom:12px;'
                      'width:3px;background:#E10600;border-radius:2px}')
    st.html(f"<style>{rules}</style>")
    target = st.sidebar if target is None else target
    with target.container(key=f"series-navigation{suffix}"):
        if caption:
            st.html(f'<div class="series-menu-caption">Explore {series}</div>')
        def link(page):
            with st.container(key=f"series-nav-{page.url_path or 'home'}{suffix}"):
                st.page_link(page, label="Championship" if page.url_path == "season" else page.title, icon="", width="stretch")
        for page in pages[:3] if secondary else pages:
            link(page)
        if secondary:
            with st.expander("More Formula 1 pages", expanded=current not in ("", "season", "replay")):
                for page in pages[3:]:
                    link(page)
