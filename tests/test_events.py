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
