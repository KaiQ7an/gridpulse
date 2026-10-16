"""About page: what PitLens is, how to use it, and some races worth opening first."""

import streamlit as st

from pitlens.pitwall import ui

REPO = "https://github.com/KaiQ7an/pitlens"

# year, round, session ("" or "sprint"), title, why it's worth a look
FEATURED = [
    (2026, 15, "", "2026 Azerbaijan Grand Prix", "Russell beats Verstappen to the line by 0.196 s."),
    (2021, 22, "", "2021 Abu Dhabi Grand Prix", "A late safety car and a last-lap pass decide the title."),
    (2022, 7, "", "2022 Monaco Grand Prix", "Rain, a red flag, and the time limit after 64 of 78 laps."),
    (2025, 2, "", "2025 Chinese Grand Prix", "Three cars disqualified after the flag."),
    (2026, 5, "", "2026 Canadian Grand Prix", "A wet start: the leader pits for slicks on lap 1."),
]

# Set by the app to its race replay page, so the links can open a race there.
replay_page = None


def render() -> None:
    ui.sidebar_brand("A race engineer's view of F1 data")
    ui.sidebar_footer()
    ui.header("Unofficial F1 data project", "PitLens",
              "Replay any race from 2018 on the way a strategy desk sees it, lap by lap.")
    ui.insight("Pick a race, press Play, and the whole pit wall moves on a lap at a time: the timing tower, "
               "the gaps, tyres, pit stops, strategy and team radio, with what was known at that lap and "
               "nothing after it.")

    left, middle, right = st.columns(3, gap="large")
    with left, st.container(border=True, key="card-about-replay"):
        ui.label("Race replay")
        ui.note("Timing tower with places gained and lost, the race trace, tyre stints, every pit stop with "
                "how long it took and what it cost, a pit window from a tyre model fitted on the race so far, "
                "undercuts, and team radio with transcripts. Sprints too.")
    with middle, st.container(border=True, key="card-about-quali"):
        ui.label("Qualifying")
        ui.note("The knockout from Q1 to Q3, each driver's ideal lap from their best sectors, and where the "
                "time went sector by sector.")
    with right, st.container(border=True, key="card-about-onboard"):
        ui.label("Onboard")
        ui.note("Two drivers' fastest laps side by side: speed, throttle, brake and gear along the lap, the gap "
                "building corner by corner, and a track map of who was faster where.")

    ui.label("Races worth a look")
    cols = st.columns(len(FEATURED), gap="small")
    for col, (year, round_number, session, title, why) in zip(cols, FEATURED):
        with col, st.container(border=True, key=f"card-featured-{year}-{round_number}"):
            st.html(f'<div style="font-weight:700;margin-bottom:4px">{title}</div>'
                    f'<div class="pl-note" style="margin-bottom:6px">{why}</div>')
            if replay_page is not None:
                params = {"year": str(year), "round": str(round_number), **({"session": session} if session else {})}
                st.page_link(replay_page, label="Open the replay", icon=":material/play_arrow:", query_params=params)

    ui.label("How far to trust it")
    ui.note("The data is F1's public live-timing archive (through FastF1), or OpenF1 when the archive won't "
            "serve a session. Every Grand Prix from 2021 on, and every sprint since 2023, has been checked "
            "against the official result: the same winner, the same top ten and every finisher the same "
            "number of laps down. The checks, and the data problems they caught, are written up on GitHub.")
    st.markdown(f"[Source code and the data checks on GitHub]({REPO}) · "
                f"[How the data was checked]({REPO}/blob/main/docs/data-validation.md)")
    ui.note("Unofficial: not associated with Formula 1 or any team. Circuit maps and pit loss figures from "
            "MultiViewer, rainfall from Open-Meteo.")
