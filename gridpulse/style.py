"""Colours and symbols shared by the static charts and the dashboard."""

# F1's own compound colours, adjusted to read on both light and dark
# backgrounds (hard is grey rather than white). Charts pair each colour with
# a marker shape so they still work for colour-blind readers.
COMPOUND_COLORS = {
    "SOFT": "#D7261E",
    "MEDIUM": "#D99A00",
    "HARD": "#8C8C8C",
    "INTERMEDIATE": "#2E9B3E",
    "WET": "#1F6FD1",
    "UNKNOWN": "#B0B0B0",
}
COMPOUND_ORDER = list(COMPOUND_COLORS)

# matplotlib marker codes and their plotly equivalents
COMPOUND_MARKERS = {"SOFT": "o", "MEDIUM": "s", "HARD": "^", "INTERMEDIATE": "D", "WET": "v", "UNKNOWN": "x"}
COMPOUND_SYMBOLS = {
    "SOFT": "circle",
    "MEDIUM": "square",
    "HARD": "triangle-up",
    "INTERMEDIATE": "diamond",
    "WET": "triangle-down",
    "UNKNOWN": "x",
}

FALLBACK_TEAM_COLOR = "#9A9A9A"
