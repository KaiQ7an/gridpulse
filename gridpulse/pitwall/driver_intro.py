"""Compact profile card shared by F1 and DTM; facts are separate from season results."""

import html

import streamlit as st

from gridpulse.drivers.profiles import birth_date, profile, public_url
from gridpulse.pitwall import identity_badges, milestone_cards, ui


def render(series: str, driver: str, year: int, name: str, *, team: str = "", car: str = "",
           team_id: str = "", manufacturer: str = "") -> None:
    info = profile(series, driver)
    name = info.get("name") or name
    label = "Formula 1" if series == "f1" else "DTM"
    photo = (info.get("portraits", {}).get(str(year)) if series == "dtm" else info.get("portrait"))
    photo = public_url(photo)
    with st.container(border=True, key=f"driver-intro-{series}"):
        left, right = st.columns([1, 3], gap="large")
        with left:
            if photo:
                src, alt = html.escape(photo, quote=True), html.escape(name, quote=True)
                st.html(f'<img src="{src}" alt="Portrait of {alt}" loading="lazy" '
                        'style="width:100%;height:220px;object-fit:contain;border-radius:10px;'
                        'background:rgba(128,128,128,.06)">')
                st.caption(f"{year} DTM profile portrait" if series == "dtm" else
                           "Current official F1 portrait; team clothing may differ from the selected season.")
            else:
                ui.label(name)
                st.caption("Profile portrait not published for this season.")
        with right:
            ui.label("Driver introduction")
            nationality = info.get("nationality") or "Not published"
            ui.strip([ui.stat("Nationality", nationality), ui.stat("Born", birth_date(info.get("birth", ""))),
                      ui.stat(f"{label} debut", str(info.get("debut") or "Not published"))])
            if info.get("place"):
                st.caption(f"Place of birth: {info['place']}")
            if info.get("intro"):
                st.write(info["intro"])
            elif info.get("debut"):
                st.write(f"{name} first competed in {label} in {info['debut']}.")
            if team:
                st.write(f"{year} entry: {team}" + (f" · {car}" if car else ""))
            if series == "dtm":
                identity_badges.render(year, team_id, [manufacturer] if manufacturer else [], link_team=True)
            with st.container(horizontal=True, gap="small"):
                source = public_url(info.get("profile_url") or info.get("source"))
                if source:
                    st.link_button("Official driver profile" if info.get("profile_url") or series == "dtm" else "Driver reference", source,
                                   icon=":material/open_in_new:")
                site = public_url(info.get("website"))
                if site:
                    st.link_button("Driver website", site, icon=":material/person:")
            with st.expander("Biography sources"):
                for i, source in enumerate(info.get("sources", [info.get("source")]), 1):
                    if public_url(source):
                        st.markdown(f"[Profile reference {i}]({source})")

    milestone_cards.render(series, "drivers", driver, year)
