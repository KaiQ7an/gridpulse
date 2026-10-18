"""Responsive identity cards with official artwork and useful profile navigation."""

from base64 import b64encode
from html import escape
from urllib.parse import urlencode

import streamlit as st

from gridpulse.dtm.badges import marks
from gridpulse.pitwall.styles import ASSETS


def artwork(badge: dict) -> str:
    """Frame transparent padding without changing or recolouring the source artwork."""
    name = escape(badge["name"], quote=True)
    src = ("data:image/jpeg;base64," + b64encode((ASSETS / badge["asset"]).read_bytes()).decode("ascii")) \
        if badge.get("asset") else escape(badge["url"], quote=True)
    frame = badge.get("artwork")
    if frame:
        x, y, width, height = frame["bounds"]
        display_width = min(96, 48 * width / height)
        return (f'<span class="identity-artwork" style="width:min(100%,{display_width:.2f}px);'
                f'aspect-ratio:{width}/{height}">'
                f'<img src="{src}" alt="{name} logo" loading="lazy" style="position:absolute;'
                f'width:{frame["width"] / width * 100:.4f}%;height:{frame["height"] / height * 100:.4f}%;'
                f'left:{-x / width * 100:.4f}%;top:{-y / height * 100:.4f}%;max-width:none;object-fit:fill"></span>')
    return f'<img src="{src}" alt="{name} logo" loading="lazy">'


def render(year: int, team_id: str, manufacturers: list[str], *, link_team: bool = False) -> None:
    badges = marks(year, team_id, manufacturers)
    if not badges:
        return
    items = []
    for badge in badges:
        name, label = escape(badge["name"]), escape(badge["label"])
        source = escape(badge["source"], quote=True)
        background = "#20242b" if badge.get("dark") else "#fff"
        is_team = badge["label"] == "Team identity"
        profile_link = link_team and is_team
        href = escape('/dtm?' + urlencode({"year": year, "view": "teams", "team": team_id}), quote=True) if profile_link else source
        title = escape(f"Open {year} team profile" if profile_link else f"{badge['name']} · {badge['scope']} Open official source", quote=True)
        target = '' if profile_link else ' target="_blank" rel="noopener noreferrer"'
        plate = "identity-badge-plate identity-badge-plate-wide" if badge.get("wide") else "identity-badge-plate"
        items.append(f'<div class="identity-badge-card"><a class="identity-badge" href="{href}"{target} title="{title}">'
                     f'<span class="{plate}" style="background:{background}">{artwork(badge)}</span>'
                     f'<span class="identity-badge-text"><small>{label}</small><strong>{name}</strong>'
                     f'<span class="identity-badge-action">{"Explore team →" if profile_link else "Official source ↗"}</span>'
                     '</span></a>' +
                     (f'<a class="identity-badge-source" href="{source}" target="_blank" rel="noopener noreferrer" '
                      f'aria-label="Official {name} logo source" title="Official logo source">↗</a>' if profile_link else '') + '</div>')
    st.html('''<style>
.identity-badges{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));
 gap:12px;margin:4px 0 12px;max-width:860px;container-type:inline-size}
.identity-badge-card{position:relative;border:1px solid rgba(128,128,128,.24);border-radius:12px;
 overflow:hidden;transition:border-color .16s,box-shadow .16s;background:rgba(128,128,128,.025)}
.identity-badge-card:hover{border-color:#ff352b;box-shadow:0 4px 16px rgba(0,0,0,.06)}
.identity-badge{display:flex;align-items:center;gap:16px;padding:14px;min-height:110px;height:100%;
 box-sizing:border-box;color:inherit!important;text-decoration:none!important}
.identity-badge:focus-visible,.identity-badge-source:focus-visible{outline:2px solid #ff352b;outline-offset:-3px}
.identity-badge-plate{display:flex;align-items:center;justify-content:center;width:120px;height:72px;
 border-radius:8px;padding:12px;box-sizing:border-box;flex-shrink:0;border:1px solid rgba(128,128,128,.08)}
.identity-badge-plate-wide{width:170px}
.identity-artwork{display:block;position:relative;overflow:hidden;flex-shrink:1}
.identity-badge img,.identity-badge svg{display:block;width:100%;height:100%;object-fit:contain}
.identity-badge-text{display:flex;flex-direction:column;gap:4px;min-width:0;padding-right:10px}
.identity-badge small{font-size:11px;opacity:.65;line-height:1.4}
.identity-badge strong{font-size:15px;line-height:1.35;overflow-wrap:anywhere}
.identity-badge-action{font-size:11px;opacity:.6;transition:color .16s,opacity .16s}
.identity-badge:hover .identity-badge-action{color:#ff352b;opacity:1}
.identity-badge-source{position:absolute;right:8px;top:6px;padding:2px 5px;color:inherit!important;
 text-decoration:none!important;font-size:15px;opacity:.65}
@container(max-width:350px){.identity-badge{gap:12px;padding:12px}.identity-badge-plate{width:96px;height:64px}
 .identity-badge-plate-wide{width:145px}}
@media(prefers-reduced-motion:reduce){.identity-badge-card,.identity-badge-action{transition:none}}
</style><div class="identity-badges">''' + "".join(items) + '</div>')
