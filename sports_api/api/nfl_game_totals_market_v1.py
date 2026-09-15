"""Identity-verified, read-only NFL Game Totals API v1.

Sportsbook information is market context only. It has exactly 0.0% influence on
projection/model math and this endpoint exposes no wager or staking action.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from sports_api.collectors.nfl_fanduel_game_totals_v1 import collect_nfl_game_totals

router = APIRouter(tags=["nfl-game-totals-v1"])


@router.get("/api/v1/nfl/totals/market")
def get_nfl_game_totals_market(
    event_id: str = Query(
        ...,
        min_length=1,
        pattern=r"^\d+$",
        description="Official ESPN NFL event ID",
    ),
) -> dict[str, Any]:
    """Return one exact-identity FanDuel full-game total for an ESPN NFL event."""
    payload = collect_nfl_game_totals(event_id)
    return {
        **payload,
        "contract": "nfl-game-totals-market-v1",
        "identity_mode": "exact_espn_event_id",
        "sportsbook_projection_weight": 0.0,
        "projection_use": "context_only",
        "wager_actions_enabled": False,
    }
