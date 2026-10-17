"""About page: what GridPulse is, how to use it, and some races worth opening first."""

import streamlit as st

from gridpulse.branding import NAME, TAGLINE
from gridpulse.pitwall import ui

REPO = "https://github.com/KaiQ7an/gridpulse"

# year, round, session ("" or "sprint"), title, why it's worth a look
FEATURED = [
    (2026, 15, "", "2026 Azerbaijan Grand Prix", "Russell beats Verstappen to the line by 0.196 s."),
    (2021, 22, "", "2021 Abu Dhabi Grand Prix", "A late safety car and a last-lap pass decide the title."),
    (2022, 7, "", "2022 Monaco Grand Prix", "Rain, a red flag, and the time limit after 64 of 78 laps."),
    (2025, 2, "", "2025 Chinese Grand Prix", "Three cars disqualified after the flag."),
    (2026, 5, "", "2026 Canadian Grand Prix", "A wet start: the leader pits for slicks on lap 1."),
]

# What each page does, as (page title, what it shows): a race weekend, then a season.
WEEKEND = [
    ("Race replay", "Timing tower with places gained and lost, the race trace, tyre stints, every pit stop with how "
                    "long it took and what it cost, a pit window from a tyre model fitted on the race so far, "
                    "undercuts, and team radio with transcripts. Sprints too."),
    ("Qualifying", "The knockout from Q1 to Q3, each driver's ideal lap from their best sectors, and where the time "
                   "went sector by sector."),
    ("Onboard", "Two selected laps or drivers' fastest laps side by side: speed, throttle, brake and gear along the lap, the gap "
                "building corner by corner, and a track map of who was faster where."),
]
SEASON = [
    ("Season", "The championship round by round: the standings, the points race, who led when, every result in "
               "one grid, and each round's pole, winner and fastest lap."),
    ("Teams", "A season team by team: points, wins and poles, each driver's numbers, the teammate battle in "
              "qualifying and races, and how quick the pit crew is against the rest."),
    ("Drivers", "One driver's season: grid to flag at every Grand Prix, points against the teammate and the "
                "leader, and the standout numbers, from the best comeback to the longest run in the points."),
    ("Circuits", "Explore a world globe and regional maps, then open each circuit's facts and historical records: "
                 "race lap record, most wins and pole starts. Filter venues, compare tracks, explore each corner "
                 "with a lap tour and share a pinned corner. Saved races add year-by-year results and strategy."),
]
DTM_GUIDE = [("DTM", "2023–2026 official driver, team and manufacturer standings, interactive points charts, "
                     "race calendar, practice and qualifying classifications, both weekend races, "
                     "driver comparisons and CSV exports. Team profiles include headquarters, history, dated honours, "
                     "season cars and sourced photographs; driver profiles add biography and official portraits.")]

# Set by the app: its pages by title, so the cards and featured races can link to them.
pages: dict = {}


def render() -> None:
    ui.sidebar_brand("Motorsport data & analysis")
    ui.sidebar_footer(st.session_state.get("racing_series", "Formula 1"))
    ui.header("Motorsport data & analysis", NAME, TAGLINE)
    st.caption("Current coverage: Formula 1 from 2018; DTM classifications and championships from 2023 to 2026.")
    ui.insight("Choose your championship in Racing series at the top left. Formula 1 offers lap-by-lap replay, "
               "telemetry and strategy; DTM brings official championship tables, both weekend races and driver comparisons.")

    ui.label("Formula 1 · a race weekend")
    cards(WEEKEND)
    ui.label("Formula 1 · across a season")
    cards(SEASON)
    ui.label("DTM · championship & race weekends")
    cards(DTM_GUIDE)

    ui.label("Races worth a look")
    cols = st.columns(len(FEATURED), gap="small")
    for col, (year, round_number, session, title, why) in zip(cols, FEATURED):
        with col, st.container(border=True, key=f"card-featured-{year}-{round_number}"):
            st.html(f'<div style="font-weight:700;margin-bottom:4px">{title}</div>'
                    f'<div class="pl-note" style="margin-bottom:6px">{why}</div>')
            if "Race replay" in pages:
                params = {"year": str(year), "round": str(round_number), **({"session": session} if session else {})}
                st.page_link(pages["Race replay"], label="Open the replay", icon=":material/play_arrow:",
                             query_params=params)

    ui.label("How far to trust it")
    ui.note("The data is F1's public live-timing archive (through FastF1), or OpenF1 when the archive won't "
            "serve a session. Every Grand Prix from 2021 on, and every sprint since 2023, has been checked "
            "against the official result: the same winner, the same top ten and every finisher the same "
            "number of laps down, and the 2023 to 2025 championships add up to the official final standings "
            "point for point. The checks, and the data problems they caught, are written up on GitHub.")
    st.markdown(f"[Source code and the data checks on GitHub]({REPO}) · "
                f"[How the data was checked]({REPO}/blob/main/docs/data-validation.md)")
    ui.note("Unofficial: not associated with Formula 1 or any team. Circuit maps and pit loss figures from "
            "MultiViewer, rainfall from Open-Meteo.")


def cards(items: list[tuple[str, str]]) -> None:
    for col, (title, what) in zip(st.columns(len(items), gap="medium"), items):
        with col, st.container(border=True, key=f"card-about-{title.lower().replace(' ', '-')}"):
            ui.label(title)
            ui.note(what)
            if title in pages:
                st.page_link(pages[title], label="Open", icon=":material/arrow_forward:")
