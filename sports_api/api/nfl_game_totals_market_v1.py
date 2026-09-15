"""Kyre Sports API — NFL Game Totals market router scaffold.

The router is intentionally not attached to the shared production route table
until the Game Totals transport, identity, safety, and regression contracts are
complete. Sportsbook totals remain market context only.
"""
from __future__ import annotations

from fastapi import APIRouter

from sports_api.collectors.nfl_fanduel_totals_v1 import SCHEMA_VERSION


router = APIRouter(
    prefix="/api/v1/nfl/game-totals/market",
    tags=["nfl-game-totals-market"],
)

MARKET_SNAPSHOT_TTL_SECONDS = 10.0


__all__ = [
    "MARKET_SNAPSHOT_TTL_SECONDS",
    "SCHEMA_VERSION",
    "router",
]
