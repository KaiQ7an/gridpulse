"""Sourced display context for event names that do not identify their host venue.

Keep source event names intact in snapshots/analysis; this adds UI context, not a venue
inferred from a Grand Prix's name. In 2026 the Bahrain-named event was hosted in Malaysia.
"""

MALAYSIA_SOURCE = ('https://corp.formula1.com/formula-1-and-fia-confirm-that-malaysia-will-join-'
                   'the-2026-calendar-as-host-venue-for-the-bahrain-grand-prix/')


def in_malaysia(year: int, event: str, location: str) -> bool:
    return year == 2026 and event == 'Bahrain Grand Prix' and location == 'Kuala Lumpur'


def title(year: int, event: str, location: str) -> str:
    return event + ' in Malaysia' if in_malaysia(year, event, location) else event
