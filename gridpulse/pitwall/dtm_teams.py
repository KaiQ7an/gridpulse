"""A compact directory of the season's operating teams, linking to full profiles."""

from html import escape
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from gridpulse.drivers.profiles import profile as driver_profile
from gridpulse.dtm import data, teams
from gridpulse.dtm.badges import marks
from gridpulse.pitwall import identity_badges, styles


def link(year: int, view: str, **params) -> str:
    return escape("/dtm?" + urlencode({"year": year, "view": view, **params}), quote=True)


def mark(badge: dict | None, fallback: str, *, manufacturer: bool = False) -> str:
    kind = "dtm-team-manufacturer-mark" if manufacturer else "dtm-team-mark"
    if badge and badge.get("wide"):
        kind += " dtm-team-mark-wide"
    if badge is None:
        return f'<span class="{kind} dtm-team-monogram" aria-hidden="true">{escape(fallback)}</span>'
    background = "#20242b" if badge.get("dark") else "#fff"
    source = escape(badge["source"], quote=True)
    name = escape(badge["name"], quote=True)
    return (f'<a class="{kind}" style="background:{background}" href="{source}" '
            f'target="_blank" rel="noopener noreferrer" title="{name} · official logo source">'
            f'{identity_badges.artwork(badge)}</a>')


def card(year: int, team_id: str, info: dict, rows: pd.DataFrame) -> str:
    brands = sorted(rows.manufacturer.unique())
    badges = marks(year, team_id, brands)
    team_badge = next((b for b in badges if b["label"] == "Team identity"), None)
    brand_badges = {b["name"]: b for b in badges if b["label"] != "Team identity"}
    team_mark = mark(team_badge, "") if team_badge else ""
    href, name = link(year, "teams", team=team_id), escape(info["name"])
    accent = data.COLORS.get(brands[0], "#A0A8B6") if brands else "#A0A8B6"
    machinery = []
    for brand in brands:
        models = " · ".join(rows.loc[rows.manufacturer == brand, "model"].unique())
        machinery.append('<div class="dtm-team-machinery">' + mark(brand_badges.get(brand), brand[:2], manufacturer=True) +
                         f'<div><strong>{escape(brand)}</strong><span>{escape(models)}</span></div></div>')
    classified = rows[rows.status == ""]
    stats = (("Wins", int(classified.position.eq(1).sum())),
             ("Podiums", int(classified.position.le(3).sum())),
             ("Cars", len(rows.drop_duplicates(["number", "manufacturer"]))))
    metrics = "".join(f'<div><strong>{value}</strong><span>{label}</span></div>' for label, value in stats)
    # Community Cloud embeds the app in a sandbox: open profile URLs outside that iframe.
    drivers = []
    for driver, entries in rows.groupby("driver", sort=False):
        full_name = driver_profile("dtm", driver).get("name") or entries.iloc[0]["name"]
        car_numbers = entries.number.map(data.number).dropna().unique()
        numbers = " / ".join(f"#{number:g}" for number in sorted(car_numbers))
        drivers.append(f'<a href="{link(year, "drivers", driver=driver)}" target="_blank" rel="noopener noreferrer"><span>{escape(full_name)}</span>'
                       f'<span class="dtm-team-number">{escape(numbers)}</span></a>')
    return (f'<article class="dtm-team-card" style="--team-accent:{accent}" aria-label="{escape(info["name"], quote=True)}">'
            '<header class="dtm-team-card-heading">' + team_mark +
            f'<div><span class="dtm-team-kicker">DTM · {year}</span><h3><a href="{href}" target="_blank" rel="noopener noreferrer">{name}</a></h3></div></header>'
            '<div class="dtm-team-card-body">' + "".join(machinery) +
            f'<div class="dtm-team-card-stats" aria-label="{year} season race results">{metrics}</div>'
            '<div class="dtm-team-lineup"><span class="dtm-team-kicker">Season line-up</span>' + "".join(drivers) + '</div>'
            '</div><footer class="dtm-team-card-footer">'
            f'<span>{escape(info.get("base") or "Base not verified")}</span>'
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" aria-label="Explore {escape(info["name"], quote=True)} team profile in a new tab">Team profile <span aria-hidden="true">↗</span></a>'
            '</footer></article>')


def directory(season: dict, active: dict) -> None:
    styles.inject("teams.css")
    races, year = data.race_rows(season), season["year"]
    cards = [card(year, key, info, races[races.team.isin(info["entries"])]) for key, info in active.items()]
    st.html('<section class="dtm-team-directory" aria-label="Participating DTM teams">'
            f'<div class="dtm-team-directory-heading"><h2>{year} grid</h2>'
            f'<span>{len(active)} teams · {len(teams.car_entries(season))} car entries · '
            f'{races.manufacturer.nunique()} manufacturers</span></div>'
            '<div class="dtm-team-grid">' + "".join(cards) + '</div></section>')
    st.caption("Published race entrants, including guests. Sponsor entries are grouped by operating team. "
               "Statistics cover the selected season’s races; full history and sources are inside each profile.")
