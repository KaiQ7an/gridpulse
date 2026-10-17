"""Curated, offline replay entry points shared by Home and About.

Questions describe the decision at that lap without revealing the eventual result. These
are one-final-stop model explorations, not a reconstruction of a team's complete strategy.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyMoment:
    year: int
    round: int
    lap: int
    drivers: tuple[str, ...]
    title: str
    question: str
    source: str = ''

    @property
    def params(self) -> dict[str, str]:
        return {'year': str(self.year), 'round': str(self.round), 'lap': str(self.lap),
                'drivers': ','.join(self.drivers), 'view': 'Strategy', 'mode': 'replay'}


FEATURED = (
    StrategyMoment(2025, 14, 18, ('NOR', 'PIA', 'LEC'), 'Hungary 2025 · L18',
                   'Norris or Piastri: stop now or extend the stint?',
                   'https://www.mclaren.com/racing/formula-1/2025/hungarian-grand-prix/race-report/'),
    StrategyMoment(2026, 15, 18, ('RUS', 'VER', 'LEC'), 'Baku 2026 · L18',
                   'Which fresh compound makes the next stop worthwhile?'),
    StrategyMoment(2025, 4, 23, ('HAM', 'LEC', 'PIA'), 'Bahrain 2025 · L23',
                   'Where would Hamilton and Leclerc rejoin after a stop?'),
)
