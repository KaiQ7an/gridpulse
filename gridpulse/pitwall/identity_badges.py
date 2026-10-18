"""Responsive identity cards with official artwork and useful profile navigation."""

from base64 import b64encode
from html import escape
from urllib.parse import urlencode

import streamlit as st

from gridpulse.dtm.badges import marks
from gridpulse.pitwall.styles import ASSETS


def artwork(badge: dict) -> str:
    """Frame surplus padding without changing or recolouring the source artwork."""
    name = escape(badge["name"], quote=True)
    src = ("data:image/jpeg;base64," + b64encode((ASSETS / badge["asset"]).read_bytes()).decode("ascii")) \
        if badge.get("asset") else escape(badge["url"], quote=True)
    frame = badge.get("artwork")
    if frame:
        x, y, width, height = frame["bounds"]
        display_width = min(146 if badge.get("wide") else 96, 48 * width / height)
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
        target = ' target="_top"' if profile_link else ' target="_blank" rel="noopener noreferrer"'
        plate = "identity-badge-plate identity-badge-plate-wide" if badge.get("wide") else "identity-badge-plate"
        items.append(f'<div class="identity-badge-card"><a class="identity-badge" href="{href}"{target} title="{title}">'
                     f'<span class="{plate}" style="background:{background}">{artwork(badge)}</span>'
                     f'<span class="identity-badge-text"><small>{label}</small><strong>{name}</strong>'
                     f'<span class="identity-badge-action">{"Explore team →" if profile_link else "Official source ↗"}</span>'
                     '</span></a>' +
                     (f'<a class="identity-badge-source" href="{source}" target="_blank" rel="noopener noreferrer" '
                      f'aria-label="Official {name} logo source" title="Official logo source">↗</a>' if profile_link else '') + '</div>')
    st.html('<div class="identity-badges">' + "".join(items) + '</div>')
