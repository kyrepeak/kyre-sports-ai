"""First-class NBA domain manifest for the Kyre Sports API application gateway."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from . import nba_pra_player_context_history_v1 as player_context_history


router = APIRouter(prefix="/api/v1/nba", tags=["nba-gateway"])
router.include_router(player_context_history.router)

LIVE_CAPABILITIES = (
    "pra.market",
    "pra.schedule",
    "pra.player-context",
    "pra.player-context-history",
    "pra.injuries",
    "pra.matchup",
)

FUTURE_MARKET_ROUTER_CONTRACT = (
    "points",
    "rebounds",
    "assists",
    "threes",
    "moneyline",
    "spread",
    "totals",
    "player-combos",
)

PROHIBITED_SOURCES = ("SGO", "ESPN", "ESPN BET")


@router.get("/status")
def status() -> dict[str, Any]:
    """Declare NBA application ownership without claiming unbuilt market endpoints."""
    return {
        "service": "Kyre Sports API",
        "schema_version": "nba_universal_gateway_v1",
        "sport": "nba",
        "application_gateway": "KYRE_SPORTS_API",
        "runless_product_transport": False,
        "provider_direct_frontend": False,
        "field_first_routing": True,
        "semantic_empty_states": True,
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
        "consensus_averaging": False,
        "live_capabilities": list(LIVE_CAPABILITIES),
        "future_market_router_contract": list(FUTURE_MARKET_ROUTER_CONTRACT),
        "prohibited_sources": list(PROHIBITED_SOURCES),
    }
