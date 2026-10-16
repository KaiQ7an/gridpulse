import pandas as pd

from pitlens.pitwall.events import race_events, situation
from pitlens.pitwall.timing import timing_tower


def car(driver, lap_times, offset=0.0, pit_in=None, status=None):
    rows, t = [], offset
    for n, lt in enumerate(lap_times, start=1):
        t += lt
        stint = 1 if pit_in is None or n <= pit_in else 2
        rows.append({
            "Driver": driver, "Team": "T", "LapNumber": n,
            "Time": pd.to_timedelta(t, unit="s"), "LapTime": pd.to_timedelta(lt, unit="s"),
            "Stint": stint, "Compound": "MEDIUM", "TyreLife": n,
            "PitInTime": pd.to_timedelta(t - 5, unit="s") if n == pit_in else pd.NaT,
            "TrackStatus": (status or {}).get(n, "1"),
        })
    return rows


def make_race():
    # A leads; B passes A on lap 4 (A has a slow lap); C pits on lap 3; D retires after lap 2;
    # VSC on lap 5; B sets the fastest lap on lap 4.
    vsc = {5: "6"}
    a = car("A", [80, 80, 80, 83, 90, 80], status=vsc)
    b = car("B", [80.5, 80, 80, 79, 90, 80], offset=0.5, status=vsc)
    c = car("C", [81, 81, 101, 81, 90, 81], offset=1, pit_in=3, status=vsc)
    d = car("D", [82, 82], offset=2)
    return pd.DataFrame(a + b + c + d)


def test_race_events():
    events = race_events(make_race(), retired={"D"}, total_laps=6)
    texts = events["Text"].tolist()
    assert "C pits from P3" in texts
    assert "B passes A for P1" in texts
    assert "D retires" in texts
    assert "Virtual safety car" in texts
    assert "Green flag, racing resumes" in texts
    assert any(t.startswith("B fastest lap, 1:19.000") for t in texts)
    assert texts[-1].startswith("B wins by")
    assert events.loc[events["Text"] == "B passes A for P1", "Lap"].item() == 4


def test_situation():
    laps = make_race()
    assert situation(timing_tower(laps, 2, {"D"}), 2, 6) == "Lap 2 of 6: A leads B by 1.0 s."
    assert situation(timing_tower(laps, 6, {"D"}), 6, 6).startswith("Chequered flag: B wins by")


def test_neutralised_banner_counts_laps_under_the_same_status():
    from pitlens.pitwall.events import neutralised_banner

    status = pd.Series({1: "Green", 2: "Safety car", 3: "Safety car", 4: "Safety car", 5: "Green", 6: "VSC"})
    assert neutralised_banner(status, 1) is None
    assert neutralised_banner(status, 3) == {"kind": "sc", "text": "Safety car", "laps": 2}
    assert neutralised_banner(status, 4)["laps"] == 3
    assert neutralised_banner(status, 5) is None
    assert neutralised_banner(status, 6) == {"kind": "vsc", "text": "Virtual safety car", "laps": 1}


def test_laps_under_safety_car_or_in_the_pits_cannot_be_fastest():
    from pitlens.pitwall.events import fastest_lap_candidates

    laps = pd.DataFrame(car("A", [80, 70, 79, 81, 40, 75], pit_in=6, status={2: "4"}))
    laps["PitOutTime"] = pd.NaT
    fast = fastest_lap_candidates(laps)
    # lap 1 from the grid, lap 2 under SC, lap 5 a 40 s data glitch, lap 6 an in-lap
    assert fast["LapNumber"].tolist() == [3, 4]


def test_tower_lists_a_first_lap_retirement():
    laps = make_race()
    entrants = pd.DataFrame({"Driver": ["A", "B", "C", "D", "E"], "Team": ["T"] * 5})
    tower = timing_tower(laps, 6, {"D"}, entrants)
    assert tower["Driver"].tolist()[-1] == "E"
    assert tower.set_index("Driver").loc["E", "Gap"] == "OUT"


def test_fastest_sectors():
    from pitlens.pitwall.events import fastest_sectors

    laps = pd.DataFrame(car("A", [80, 80, 80]) + car("B", [80, 80, 80]))
    sectors = {("A", 2): (25.0, 30.0, 25.0), ("A", 3): (26.0, 29.0, 25.0), ("B", 2): (24.5, 30.5, 25.2),
               ("B", 3): (5.0, 31.0, 24.9), ("A", 1): (20.0, 20.0, 20.0)}  # B lap 3 S1 is a glitch, lap 1 ignored
    for i, name in enumerate(("Sector1Time", "Sector2Time", "Sector3Time")):
        laps[name] = [pd.to_timedelta(sectors.get((d, n), (30, 30, 30))[i], unit="s")
                      for d, n in zip(laps["Driver"], laps["LapNumber"])]
    ranked = fastest_sectors(laps)
    assert [r[0] for r in ranked] == [("B", 24.5, 2), ("A", 29.0, 3), ("B", 24.9, 3)]
    assert ranked[0][1] == ("A", 25.0, 2)  # second fastest S1, one entry per driver
    assert len(ranked[0]) == 2


def test_drive_through_is_not_reported_as_a_pit_stop():
    laps = make_race()
    c = laps["Driver"] == "C"
    laps.loc[c, "Stint"] = 1  # C passes through the pit lane on lap 3 without changing tyres
    texts = race_events(laps, retired={"D"}, total_laps=6)["Text"].tolist()
    assert "C pits from P3" not in texts


def test_penalty_after_the_flag_is_a_classification_note_not_a_pass():
    from pitlens.pitwall.timing import classify_finish

    laps = make_race()
    # C crosses the line third, behind B and A... but A is classified behind C after a penalty.
    results = pd.DataFrame({"Abbreviation": ["B", "C", "A", "D"], "Position": [1.0, 2.0, 3.0, None],
                            "GapToLeader": [0.0, None, None, None]})
    laps = classify_finish(laps, results, total_laps=6)
    events = race_events(laps, retired={"D"}, total_laps=6)
    texts = events["Text"].tolist()
    assert any(t.startswith("A classified P3, crossed the line P") for t in texts)
    assert not any("passes A" in t for t in events.loc[events["Lap"] == 6, "Text"])
    final = timing_tower(laps, 6, {"D"})
    assert final["Driver"].tolist()[:3] == ["B", "C", "A"]


def test_disqualified_drivers_drop_to_the_bottom_marked_dsq():
    from pitlens.pitwall.timing import classify_finish

    results = pd.DataFrame({"Abbreviation": ["A", "C", "B", "D"], "Position": [1.0, 2.0, None, None],
                            "GapToLeader": [0.0, None, None, None],
                            "Status": ["Finished", "Finished", "Disqualified", "Retired"]})
    laps = classify_finish(make_race(), results, total_laps=6)
    final = timing_tower(laps, 6, {"D", "B"})
    assert final["Driver"].tolist() == ["A", "C", "D", "B"]
    assert final.set_index("Driver").loc["B", "Gap"] == "DSQ"
    texts = race_events(laps, retired={"D", "B"}, total_laps=6)["Text"].tolist()
    assert "B disqualified, crossed the line P1" in texts
    assert texts[-2].startswith("A wins by")


def test_pit_events_follow_the_stop_list_when_given():
    laps = make_race()
    stops = pd.DataFrame({"Driver": [], "Lap": []})  # e.g. C's trip down the pit lane wasn't a stop
    texts = race_events(laps, retired={"D"}, total_laps=6, stops=stops)["Text"].tolist()
    assert "C pits from P3" not in texts
    stops = pd.DataFrame({"Driver": ["C"], "Lap": [3]})
    texts = race_events(laps, retired={"D"}, total_laps=6, stops=stops)["Text"].tolist()
    assert "C pits from P3" in texts


def test_winner_alone_on_the_lead_lap():
    laps = make_race()
    laps = laps[~((laps["Driver"] != "B") & (laps["LapNumber"] == 6))]  # only B completes lap 6
    events = race_events(laps, retired={"D"}, total_laps=6)
    assert events.loc[events["Kind"] == "FLAG", "Text"].tolist() == ["B wins"]
    assert situation(timing_tower(laps, 6, {"D"}), 6, 6) == "Chequered flag: B wins."


def test_places_gained_on_the_lap_and_against_the_grid():
    from types import SimpleNamespace

    from pitlens.pitwall.app import places_gained

    laps = make_race()
    race = SimpleNamespace(laps=laps, retired={"D"}, entrants=None, stops=None,
                           results=pd.DataFrame({"Abbreviation": ["A", "B", "C", "D"], "GridPosition": [2, 1, 3, 0]}))
    # B passes A on lap 4.
    assert places_gained(race, timing_tower(laps, 4, {"D"}), 4) == {"B": 1, "A": -1, "C": 0}
    # Lap 1 against the grid; D started from the pit lane (0) and has no arrow.
    assert places_gained(race, timing_tower(laps, 1, {"D"}), 1) == {"A": 1, "B": -1, "C": 0}
