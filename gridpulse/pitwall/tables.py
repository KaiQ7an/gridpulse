"""Domain table renderers for race, qualifying and season pages.

The table markup lives here; shared design primitives stay in ui.py and all styles in assets/.
"""

import html

import pandas as pd
import streamlit as st

from gridpulse.pitwall.ui import TYRE_LETTERS, driver_dot, lap_time, tyre

FLAG_TAGS = {"Safety car": ("SC", ""), "VSC": ("VSC", ""), "VSC ending": ("VSC", ""), "Red flag": ("RED", " red")}


def _places(before, after) -> str:
    if pd.isna(before) or pd.isna(after):
        return '<span class="muted">–</span>'
    delta = int(before) - int(after)
    change = (f' <span class="up">+{delta}</span>' if delta > 0 else
              f' <span class="down">−{-delta}</span>' if delta < 0 else "")
    return f"P{int(before)} → P{int(after)}{change}"


def pit_table(stops, colors: dict[str, str], lap: int) -> None:
    """Every stop so far, newest first: lap, driver, tyres, pit lane and stationary time, cost, places.

    The quickest pit lane and stationary times are purple, like a fastest lap. Pit lane times
    flagged false in `LaneOk` (implausibly short) are greyed out. Cost under a safety car or VSC
    is greyed too: the field's lap times swing too much then for it to be more than a rough
    guide. Cost and places need the out-lap, so a stop made on the current lap shows them once
    the next lap is done.
    """
    still = stops["Stationary"].notna().any()
    lane_ok = stops["LaneOk"] if "LaneOk" in stops else pd.Series(True, index=stops.index)
    still_ok = stops["StillOk"] if "StillOk" in stops else pd.Series(True, index=stops.index)
    best_lane = stops.loc[lane_ok, "LaneTime"].min()
    best_still = stops.loc[still_ok, "Stationary"].min() if still else None
    cls = "pl-pit" + ("" if still else " nostill")

    def secs(value, best, ok=True) -> str:
        if pd.isna(value):
            return '<span class="muted">–</span>'
        if value >= 100:  # cars held in the pit lane under a red flag, or repairs in the garage
            minutes, rest = divmod(round(value, 1), 60)
            return (f'<span class="muted" title="Held in the pit lane (red flag) or in the garage">'
                    f"{int(minutes)}:{rest:04.1f}</span>")
        if not ok:
            why = ("Too short for a normal trip down the pit lane, as when cars are sent through it behind the "
                   "safety car" if pd.isna(best) or value < best else "Far longer than a normal stop: repairs, or held")
            return f'<span class="muted" title="{why}">{value:.1f}</span>'
        return f'<span class="best">{value:.1f}</span>' if value == best else f"{value:.1f}"

    def stationary(value, best, ok) -> str:
        if pd.notna(value) and not ok:
            return f'<span class="muted" title="A long stop: a penalty served, or repairs">{value:.1f}</span>'
        return secs(value, best)

    head = (f'<div class="{cls} head"><span>Lap</span><span>Driver</span><span>Tyres</span>'
            f'<span class="num">Pit lane</span>' + ('<span class="num">Stopped</span>' if still else "")
            + '<span class="num">Cost</span><span>Places</span></div>')
    rows = []
    for s in stops.sort_values(["Lap", "Driver"], ascending=[False, True]).itertuples():
        pending = s.Lap + 1 > lap  # out-lap not finished yet
        flag, flag_cls = FLAG_TAGS.get(s.Status, ("", ""))
        flag_html = f'<span class="flag{flag_cls}">{flag}</span>' if flag else ""
        age = (f'<span class="age">{int(s.TyreAge)} lap{"" if int(s.TyreAge) == 1 else "s"}</span>'
               if pd.notna(s.TyreAge) else "")
        if pending:
            cost = '<span class="muted">…</span>'
        elif pd.isna(s.Loss):
            cost = '<span class="muted">–</span>'
        elif s.Neutralised and s.Loss < 0:  # the field queueing behind the safety car, not a real gain
            cost = ('<span class="muted" title="Under a safety car or VSC the field\'s lap times swing too much '
                    'to measure this stop">–</span>')
        elif s.Neutralised:
            cost = f'<span class="muted" title="Rough: under a safety car or VSC">{s.Loss:.1f}</span>'
        else:
            cost = f"{s.Loss:.1f}"
        places = '<span class="muted">…</span>' if pending else _places(s.PosBefore, s.PosAfter)
        rows.append(
            f'<div class="{cls}{" now" if s.Lap == lap else ""}"><span>L{s.Lap}{flag_html}</span>'
            f'<span>{driver_dot(colors.get(s.Driver, "#999"))}<b>{html.escape(s.Driver)}</b></span>'
            f'<span>{tyre(s.From)}<span class="arrow">→</span>{tyre(s.To)}{age}</span>'
            f'<span class="num">{secs(s.LaneTime, best_lane, lane_ok[s.Index])}</span>'
            + (f'<span class="num">{stationary(s.Stationary, best_still, still_ok[s.Index])}</span>' if still else "")
            + f'<span class="num">{cost}</span><span>{places}</span></div>'
        )
    st.html(f'<div class="pl-pits-wrap">{head}<div class="pl-pits">{"".join(rows)}</div></div>')


def quali_table(results, ideal, colors: dict[str, str]) -> None:
    """Qualifying classification: Q1/Q2/Q3 times (fastest of each part in purple), gap to pole, and the
    ideal lap from each driver's best sectors with what was left on the table; dashed lines mark the
    knockouts."""
    best = {q: results[q].min() for q in ("Q1", "Q2", "Q3")}
    pole = results["Q3"].min() if results["Q3"].notna().any() else results[["Q1", "Q2", "Q3"]].min().min()
    ideal = ideal.set_index("Driver") if len(ideal) else ideal
    head = ('<div class="pl-q head"><span class="num">Pos</span><span>Driver</span><span class="num">Q1</span>'
            '<span class="num">Q2</span><span class="num">Q3</span><span class="num">Gap</span>'
            '<span class="num ideal">Ideal lap</span></div>')
    rows, group = [], ""
    for r in results.itertuples():
        if r.Out != group:
            rows.append(f'<div class="pl-qcut">Out in {r.Out}</div>')
            group = r.Out
        cells = []
        for q in ("Q1", "Q2", "Q3"):
            t = getattr(r, q)
            cls = "num best" if pd.notna(t) and t == best[q] else "num"
            cells.append(f'<span class="{cls}">{lap_time(t) or "<span class=muted>–</span>"}</span>')
        own = min((getattr(r, q) for q in ("Q1", "Q2", "Q3") if pd.notna(getattr(r, q))), default=float("nan"))
        if r.Out == "":
            final = r.Q3 if pd.notna(r.Q3) else own
        else:
            final = getattr(r, r.Out)
        gap = "" if pd.isna(final) or pd.isna(pole) else ("Pole" if final == pole else f"+{final - pole:.3f}")
        lap = ideal.loc[r.Driver] if r.Driver in getattr(ideal, "index", []) else None
        ideal_html = ""
        if lap is not None and pd.notna(lap["Ideal"]):
            left = f'<span class="left">−{lap["LeftOnTable"]:.3f}</span>' if lap["LeftOnTable"] > 0.0005 else ""
            ideal_html = f"{lap_time(lap['Ideal'])}{left}"
        pos = "" if pd.isna(r.Position) else int(r.Position)
        rows.append(
            f'<div class="pl-q{" out" if r.Out else ""}"><span class="pos">{pos}</span>'
            f'<span>{driver_dot(colors.get(r.Driver, "#999"))}<b>{html.escape(str(r.Driver))}</b></span>'
            + "".join(cells) + f'<span class="num">{gap}</span><span class="num ideal">{ideal_html}</span></div>'
        )
    st.html(f'<div class="pl-qwrap">{head}{"".join(rows)}</div>')


def team_drivers(drivers, battles, color: str, *, year: int | None = None) -> None:
    """A card per driver of a team: season numbers and how they fared against their teammate."""
    battle = battles.set_index("Driver") if len(battles) else battles
    cards = []
    for d in drivers.itertuples():
        nums = [("Races", d.Races), ("Points", f"{d.Points:.0f}"), ("Wins", d.Wins), ("Podiums", d.Podiums),
                ("Best", f"P{d.Best}" if d.Best else "–"),
                ("Avg finish", f"{d.AverageFinish:.1f}" if pd.notna(d.AverageFinish) else "–"), ("DNFs", d.Dnf)]
        h2h = ""
        if d.Driver in getattr(battle, "index", []):
            b = battle.loc[d.Driver]
            parts = []
            if b["QualiOf"]:
                parts.append(f"qualifying <b>{int(b['QualiWon'])}–{int(b['QualiOf'] - b['QualiWon'])}</b>")
            if b["RaceOf"]:
                parts.append(f"races <b>{int(b['RaceWon'])}–{int(b['RaceOf'] - b['RaceWon'])}</b>")
            if pd.notna(b["QualiGap"]):
                parts.append(f"qualifying gap <b>{b['QualiGap']:+.3f} s</b>")
            if parts:
                h2h = f'<div class="h2h">Against their teammate: {" · ".join(parts)}</div>'
        cells = "".join(f"<div>{html.escape(k)}<b>{v}</b></div>" for k, v in nums)
        name = html.escape(d.FullName)
        if year is not None:
            name = f'<a href="./drivers?year={year}&driver={d.Driver}" target="_self">{name}</a>'
        cards.append(f'<div class="pl-drv"><div class="name">{driver_dot(color)}{name}'
                     f'<span class="code">{html.escape(d.Driver)}</span></div><div class="nums">{cells}</div>{h2h}</div>')
    st.html("".join(cards))


def position_cell(position, classified: bool = True, dsq: bool = False, pole: bool = False,
                  fastest: bool = False, points_from: int = 10) -> str:
    """A finishing position as a small coloured cell: gold, silver and bronze for the podium, green in the
    points, red for a retirement; a purple ring for pole, a purple underline for the fastest lap."""
    extra = (" pole" if pole else "") + (" fl" if fastest else "")
    if dsq:
        return f'<span class="pl-pos out{extra}" title="Disqualified">DSQ</span>'
    if not classified or pd.isna(position):
        return f'<span class="pl-pos out{extra}" title="Did not finish">DNF</span>'
    p = int(position)
    cls = {1: "p1", 2: "p2", 3: "p3"}.get(p, "pts" if p <= points_from else "")
    return f'<span class="pl-pos {cls}{extra}">{p}</span>'


def driver_results_table(rows, year: int, *, driver: str | None = None) -> None:
    """A driver's season: one row per Grand Prix with grid, finish, points and qualifying; each race
    links to its replay."""
    sprints = "Sprint" in rows and rows["Sprint"].notna().any()
    cls = "pl-res sprints" if sprints else "pl-res"
    head = (f'<div class="{cls} head"><span>Rd</span><span>Grand Prix</span><span class="num">Quali</span>'
            '<span class="num">Grid</span><span class="num">Finish</span>'
            + ('<span class="num">Sprint</span>' if sprints else "") + '<span class="num">Points</span></div>')
    out = []
    for r in rows.itertuples():
        grid = "" if pd.isna(r.Grid) else ('<span class="muted">pit</span>' if r.Grid <= 0 else int(r.Grid))
        quali = "" if pd.isna(r.Quali) else int(r.Quali)
        points = f"{r.Points:g}" if r.Points else '<span class="muted">0</span>'
        sprint = "" if not sprints or pd.isna(r.Sprint) else int(r.Sprint)
        out.append(
            f'<div class="{cls}"><span class="muted">{r.Round}</span>'
            f'<span><a href="./?year={year}&round={r.Round}{"&drivers=" + driver if driver else ""}" '
            f'target="_self">{html.escape(r.Event)}</a></span>'
            f'<span class="num">{quali}</span><span class="num">{grid}</span>'
            f'<span class="num">{position_cell(r.Position, r.Classified, r.Dsq, r.Pole, r.Fastest)}</span>'
            + (f'<span class="num">{sprint}</span>' if sprints else "") + f'<span class="num">{points}</span></div>'
        )
    st.html(f"{head}{''.join(out)}")


def standings_table(table, colors: dict[str, str], year: int) -> None:
    """The drivers' championship: position, driver (opening their Drivers page), team, wins, points and
    the gap to the leader."""
    lead = table["Points"].iloc[0] if len(table) else 0
    head = ('<div class="pl-std head"><span>Pos</span><span>Driver</span><span class="num">Wins</span>'
            '<span class="num">Points</span><span class="num">Gap</span></div>')
    rows = []
    for i, r in enumerate(table.itertuples(), start=1):
        gap = "" if i == 1 else f"-{lead - r.Points:g}"
        rows.append(
            f'<div class="pl-std"><span class="muted">{i}</span>'
            f'<span>{driver_dot(colors.get(r.Team, "#888888"))}'
            f'<a href="./drivers?year={year}&driver={r.Driver}" target="_self">{html.escape(r.FullName)}</a>'
            f'<span class="team">{html.escape(r.Team)}</span></span>'
            f'<span class="num">{r.Wins or ""}</span><span class="num"><b>{r.Points:g}</b></span>'
            f'<span class="num muted">{gap}</span></div>'
        )
    st.html(head + "".join(rows))


def results_matrix(results, table, rounds, poles, fastest, colors: dict[str, str], year: int) -> None:
    """Every Grand Prix finish in one grid: drivers down the side in championship order, rounds across
    (each opening its replay), points at the end."""
    gp = results[results["Kind"] == "R"].set_index(["Driver", "Round"])
    events = dict(zip(rounds["Round"], rounds["Event"]))
    head = '<th class="who"></th>' + "".join(
        f'<th><a href="./?year={year}&round={r}" target="_self" title="{html.escape(events[r])}">{r}</a></th>'
        for r in rounds["Round"]) + '<th class="pts">Pts</th>'
    body = []
    for d in table.itertuples():
        cells = []
        for r in rounds["Round"]:
            if (d.Driver, r) not in gp.index:
                cells.append("<td></td>")
                continue
            x = gp.loc[(d.Driver, r)]
            if isinstance(x, pd.DataFrame):
                x = x.iloc[0]
            cell = position_cell(x["Position"], x["Classified"], x["Dsq"], poles.get(r) == d.Driver,
                                 fastest.get(r) == d.Driver)
            cells.append(f'<td title="{html.escape(events[r])}">{cell}</td>')
        who = (f'<td class="who">{driver_dot(colors.get(d.Team, "#888888"))}'
               f'<a href="./drivers?year={year}&driver={d.Driver}" target="_self" title="{html.escape(d.FullName)}">'
               f'{html.escape(d.Driver)}</a></td>')
        body.append(f"<tr>{who}{''.join(cells)}<td class=\"pts\">{d.Points:g}</td></tr>")
    st.html(f'<div class="pl-mx"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def round_winners_table(winners, results, colors: dict[str, str], year: int) -> None:
    """Round by round: pole, winner, fastest lap and the sprint winner, each Grand Prix opening its replay."""
    team = results.drop_duplicates(["Round", "Driver"]).set_index(["Round", "Driver"])["Team"]

    def who(rnd, driver) -> str:
        if not isinstance(driver, str):
            return '<span class="muted">–</span>'
        return driver_dot(colors.get(team.get((rnd, driver)), "#888888")) + html.escape(driver)

    sprints = winners["SprintWinner"].notna().any()
    head = ('<div class="pl-rw head"><span>Rd</span><span>Grand Prix</span><span>Pole</span><span>Winner</span>'
            '<span>Fastest lap</span><span>' + ("Sprint" if sprints else "") + "</span></div>")
    rows = []
    for w in winners.itertuples():
        event = html.escape(w.Event.replace(" Grand Prix", ""))
        rows.append(
            f'<div class="pl-rw"><span class="muted">{w.Round}</span>'
            f'<span><a href="./?year={year}&round={w.Round}" target="_self">{event}</a></span>'
            f"<span>{who(w.Round, w.Pole)}</span><span><b>{who(w.Round, w.Winner)}</b></span>"
            f"<span>{who(w.Round, w.Fastest)}</span>"
            f"<span>{who(w.Round, w.SprintWinner) if w.Sprint else ''}</span></div>"
        )
    st.html(head + "".join(rows))


def circuit_years_table(years) -> None:
    """A circuit's Grands Prix, one row per year: winner (and where they started), pole, fastest lap,
    safety cars and red flags, and the winner's tyres. Each year opens its replay."""
    letters = {v: k for k, v in TYRE_LETTERS.items()}

    def who(driver, color, extra="") -> str:
        if not isinstance(driver, str):
            return '<span class="muted">–</span>'
        return f"{driver_dot(color or '#888888')}{html.escape(driver)}{extra}"

    head = ('<div class="pl-cy head"><span>Year</span><span>Winner</span><span>Pole</span><span>Fastest lap</span>'
            "<span>Neutralised</span><span>Winner's tyres</span></div>")
    rows = []
    for y in years.itertuples():
        grid = f"<small>from P{y.WinnerGrid}</small>" if y.WinnerGrid else ""
        pole = f"<small>{lap_time(y.PoleTime)}</small>" if pd.notna(y.PoleTime) else ""
        fastest = f"<small>{lap_time(y.FastestTime)}</small>" if pd.notna(y.FastestTime) else ""
        flags = [f"{n} {name}{'s' if n > 1 and name != 'VSC' else ''}" for n, name in
                 ((y.SafetyCars, "safety car"), (y.VSCs, "VSC"), (y.RedFlags, "red flag")) if n]
        if y.Wet:
            flags.append("wet")
        if y.Laps < y.Scheduled:
            flags.append(f"{y.Laps} of {y.Scheduled} laps")
        tyres = "".join(tyre(letters.get(c, "UNKNOWN")) for c in y.WinnerTyres.split("-") if c)
        rows.append(
            f'<div class="pl-cy"><span><a href="./?year={y.Year}&round={y.Round}" target="_self">{y.Year}</a></span>'
            f"<span><b>{who(y.Winner, y.WinnerColor, grid)}</b></span><span>{who(y.Pole, y.PoleColor, pole)}</span>"
            f"<span>{who(y.Fastest, y.FastestColor, fastest)}</span>"
            f'<span>{html.escape(", ".join(flags)) if flags else "<span class=muted>none</span>"}</span>'
            f"<span>{tyres}</span></div>"
        )
    st.html(head + "".join(rows))
