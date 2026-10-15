"""Static charts (matplotlib) for the race-pace analysis."""

import matplotlib

matplotlib.use("Agg")  # render to files, no GUI window needed

import matplotlib.pyplot as plt
import pandas as pd

from pitlens.style import COMPOUND_COLORS, COMPOUND_MARKERS

COMPOUND_STYLE = {c: {"color": COMPOUND_COLORS[c], "marker": COMPOUND_MARKERS[c]} for c in COMPOUND_COLORS}

INK = "#222222"
MUTED = "#6B6B6B"
GRID = "#E6E6E6"


def _style_axes(ax) -> None:
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)


def _compound_legend(fig, compounds) -> None:
    handles = [
        plt.Line2D([], [], linestyle="", markersize=7, label=c.title(), **COMPOUND_STYLE[c])
        for c in COMPOUND_STYLE
        if c in set(compounds)
    ]
    fig.legend(handles=handles, loc="upper right", ncol=len(handles), frameon=False, fontsize=9)


def plot_pace_by_driver(laps: pd.DataFrame, driver_order: list[str], title: str, path) -> None:
    """Small multiples: one panel per driver, lap time vs lap, marked by compound."""
    n = len(driver_order)
    cols = 5
    rows = -(-n // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.6 * rows), sharex=True, sharey=True)
    axes = axes.flatten()

    for ax, driver in zip(axes, driver_order):
        d = laps[laps["Driver"] == driver]
        for compound, g in d.groupby("Compound"):
            style = COMPOUND_STYLE.get(compound, COMPOUND_STYLE["UNKNOWN"])
            ax.scatter(g["LapNumber"], g["LapTime"], s=14, linewidths=0, **style)
        ax.set_title(driver, fontsize=10, color=INK, loc="left")
        _style_axes(ax)

    for ax in axes[n:]:
        ax.set_visible(False)

    fig.supxlabel("Lap", color=MUTED, fontsize=9)
    fig.supylabel("Lap time (s)", color=MUTED, fontsize=9)
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, color=INK)
    _compound_legend(fig, laps["Compound"].unique())
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_degradation(deg: pd.DataFrame, title: str, path) -> None:
    """Horizontal bars: degradation rate per stint, sorted, coloured by compound."""
    deg = deg.sort_values("DegPerLap").reset_index(drop=True)
    labels = deg["Driver"] + "  stint " + deg["Stint"].astype(str)

    fig, ax = plt.subplots(figsize=(8, 0.28 * len(deg) + 1.4))
    colors = [COMPOUND_STYLE.get(c, COMPOUND_STYLE["UNKNOWN"])["color"] for c in deg["Compound"]]
    ax.barh(labels, deg["DegPerLap"], color=colors, height=0.7, edgecolor="white", linewidth=1)
    ax.axvline(0, color=MUTED, linewidth=0.8)

    for y, value in enumerate(deg["DegPerLap"]):
        # Labels always sit right of the zero line so negatives don't hit the axis labels.
        ax.text(max(value, 0) + 0.003, y, f"{value:+.3f}", va="center", ha="left", fontsize=7, color=MUTED)

    ax.set_xlabel("Fuel-corrected degradation (s lost per lap of tyre age)", color=MUTED, fontsize=9)
    ax.tick_params(axis="y", labelsize=8, colors=INK)
    _style_axes(ax)
    ax.grid(axis="y", visible=False)
    ax.set_title(title, loc="left", fontsize=12, color=INK)
    _compound_legend(fig, deg["Compound"].unique())
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=150)
    plt.close(fig)
