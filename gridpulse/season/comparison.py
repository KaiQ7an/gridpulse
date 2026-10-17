"""Comparable circuit metrics, with saved-race coverage kept explicit."""

import numpy as np
import pandas as pd

from gridpulse.season.atlas import circuit_fact


def comparison_slugs(value: str) -> list[str]:
    return list(dict.fromkeys(c["slug"] for s in value.split(",") if (c := circuit_fact(s.strip()))))[:3]


def saved_summary(years: pd.DataFrame) -> dict:
    empty = {"Saved races": 0, "Coverage": "No saved races", "SC races (%)": np.nan,
             "Typical pit loss (s)": np.nan, "Stops per finisher": np.nan}
    if years.empty:
        return empty
    finishers = sum(sum(counts.values()) for counts in years["Stops"])
    stops = sum(sum(int(n) * count for n, count in counts.items()) for counts in years["Stops"])
    pit_loss = years["PitLoss"].dropna()
    return {"Saved races": len(years), "Coverage": ", ".join(years["Year"].astype(str)),
            "SC races (%)": float((years["SafetyCars"] > 0).mean() * 100),
            "Typical pit loss (s)": float(pit_loss.median()) if len(pit_loss) else np.nan,
            "Stops per finisher": stops / finishers if finishers else np.nan}


def comparison_table(facts: list[dict], histories: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for fact in facts:
        rows.append({"Circuit": fact["city"], "Country": fact["country"], "Type": fact["kind"],
                     "Length (km)": fact["length_km"], "Race laps": fact["laps"], "First GP": fact["first_gp"],
                     "Historical GPs": fact["history"]["races"], "Race lap record": fact["record"]["time"],
                     **saved_summary(histories.get(fact["key"], pd.DataFrame()))})
    return pd.DataFrame(rows)
