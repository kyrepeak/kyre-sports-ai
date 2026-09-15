"""Read-only FanDuel NFL Game Totals collector scaffold.

This module is intentionally isolated from the hosted route table while the
Game Totals API contract is built and certified. Sportsbook information is
market context only and must never modify football-only projection logic.
"""
from __future__ import annotations


SCHEMA_VERSION = "nfl_game_totals_market_v1"
SPORTSBOOK = "FanDuel"


class NFLGameTotalsCollectorError(RuntimeError):
    """The NFL Game Totals market could not be proven safely."""


__all__ = [
    "NFLGameTotalsCollectorError",
    "SCHEMA_VERSION",
    "SPORTSBOOK",
]
