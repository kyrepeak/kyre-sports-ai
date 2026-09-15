"""Kyre Sports API — NFL Game Totals market contract V1.

This module owns the public transport contract for pregame NFL Game Totals.
The sportsbook total is context only: it cannot modify football-only
projections, Monte Carlo inputs, probabilities, grades, stake sizing, or wager
actions. The live market endpoint remains intentionally unattached until its
collector and fail-closed validation are certified.
"""
from __future__ import annotations

from fastapi import APIRouter

from sports_api.collectors.nfl_fanduel_totals_v1 import SCHEMA_VERSION


router = APIRouter(
    prefix="/api/v1/nfl/game-totals/market",
    tags=["nfl-game-totals-market"],
)

MARKET_SNAPSHOT_TTL_SECONDS = 10.0

CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "service": "Kyre Sports API",
    "sport": "nfl",
    "market": "game_total",
    "official_authority": "ESPN",
    "official_event_id_required": True,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "projection_weight": 0.0,
    "market_context_only": True,
    "may_modify_projection": False,
    "model_probability_input": False,
    "multi_book_capable": True,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}

RESPONSE_REQUIRED_FIELDS = (
    "schema_version",
    "service",
    "sport",
    "market",
    "official_event_id",
    "captured_at_utc",
    "ready",
    "market_available",
    "identity",
    "books",
    "market_semantics",
)

IDENTITY_REQUIRED_FIELDS = (
    "official_authority",
    "official_event_id",
    "provider_event_id",
    "away_team_id",
    "home_team_id",
    "away_abbr",
    "home_abbr",
    "kickoff_delta_seconds",
    "team_name_matching",
    "fuzzy_matching",
    "synthetic_event_ids",
)

BOOK_REQUIRED_FIELDS = (
    "official_event_id",
    "sportsbook",
    "provider",
    "provider_event_id",
    "market_id",
    "total",
    "over_price",
    "under_price",
    "updated_at_utc",
    "line_status",
)


@router.get("/status")
def game_totals_market_status():
    """Expose the frozen transport/safety contract without touching a provider."""
    return {
        "status": "contract_ready",
        "endpoint": "/api/v1/nfl/game-totals/market",
        "live_market_attached": False,
        **CONTRACT,
    }


__all__ = [
    "BOOK_REQUIRED_FIELDS",
    "CONTRACT",
    "IDENTITY_REQUIRED_FIELDS",
    "MARKET_SNAPSHOT_TTL_SECONDS",
    "RESPONSE_REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "game_totals_market_status",
    "router",
]
