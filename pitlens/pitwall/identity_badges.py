"""Consistent linked logo plates with visible text fallbacks and source attribution."""

from html import escape

import streamlit as st

from pitlens.dtm.badges import marks


def render(year: int, team_id: str, manufacturers: list[str]) -> None:
    badges = marks(year, team_id, manufacturers)
    if not badges:
        return
    items = []
    for badge in badges:
        name, label = escape(badge["name"]), escape(badge["label"])
        src, source = escape(badge["url"], quote=True), escape(badge["source"], quote=True)
        background = "#20242b" if badge.get("dark") else "#fff"
        title = escape(f"{badge['name']} · {badge['scope']} Open official source", quote=True)
        items.append(f'<a class="identity-badge" href="{source}" target="_blank" rel="noopener noreferrer" title="{title}">'
                     f'<span class="identity-badge-plate" style="background:{background}">'
                     f'<img src="{src}" alt="{name} logo" loading="lazy"></span>'
                     f'<span class="identity-badge-text"><small>{label}</small><strong>{name}</strong></span></a>')
    st.html('''<style>
.identity-badges{display:flex;flex-wrap:wrap;gap:12px;margin:4px 0 20px}
.identity-badge{display:flex;align-items:center;gap:12px;border:1px solid rgba(128,128,128,.24);
 border-radius:10px;padding:10px 14px;color:inherit!important;text-decoration:none!important;
 transition:transform .16s,border-color .16s;min-height:82px}
.identity-badge:hover{transform:translateY(-2px);border-color:#ff352b}
.identity-badge:focus-visible{outline:2px solid #ff352b;outline-offset:3px}
.identity-badge-plate{display:flex;align-items:center;justify-content:center;width:104px;height:58px;
 border-radius:6px;padding:6px;flex-shrink:0}
.identity-badge img{width:100%;height:100%;object-fit:contain}
.identity-badge-text{display:flex;flex-direction:column;gap:3px}
.identity-badge small{font-size:11px;opacity:.65}.identity-badge strong{font-size:14px}
@media(prefers-reduced-motion:reduce){.identity-badge{transition:none}.identity-badge:hover{transform:none}}
</style><div class="identity-badges">''' + "".join(items) + '</div>')
