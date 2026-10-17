"""Compact, keyboard-accessible DTM navigation, styled from native radio inputs."""

from urllib.parse import quote

import streamlit as st

ICONS = {
    'championship': '<path d="M8 3h8v5a4 4 0 0 1-8 0V3Zm0 2H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 1v6m-4 3h8m-7-3h6"/>',
    'weekend': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
    'drivers': '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    'compare': '<path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/>',
    'teams': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-17a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v3"/>',
}


def render(views: dict):
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
  background:rgba(225,6,0,.07);border-color:rgba(225,6,0,.12);color:#E10600;
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
.dtm-menu-caption {font-size:.65rem;font-weight:600;letter-spacing:.14em;opacity:.46;text-transform:uppercase;margin:10px 0 6px}
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
    st.sidebar.html('<div class="dtm-menu-caption">Explore DTM</div>')
    st.sidebar.radio("Explore DTM", list(views), format_func=views.get, key="dtm_view", label_visibility="collapsed", width="stretch")
