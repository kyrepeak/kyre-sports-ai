"""Kyre Sports API — NFL Passing Yards verified market endpoint.

The endpoint exposes only post-model market context. It does not calculate or
modify projections, probabilities, rankings, stake sizes, or recommendations.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_fanduel_passing_yards import NFLPassingYardsCollectorError
from sports_api.collectors.nfl_passing_yards_render_espn_v2 import (
    collect_fanduel_nfl_passing_yards_hosted as collect_fanduel_nfl_passing_yards,
)

router = APIRouter(prefix="/api/v1/nfl/passing-yards", tags=["nfl-passing-yards"])

CONTRACT = {
    "schema_version": "nfl_passing_yards_market_v1",
    "provider": "FanDuel",
    "transport": "anonymous_public_get_only",
    "official_authority": "ESPN",
    "official_event_id_required": True,
    "official_athlete_id_required": True,
    "player_name_matching": False,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "synthetic_player_ids": False,
    "projection_weight": 0.0,
    "market_context_only": True,
    "may_modify_projection": False,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


@router.get("/status")
def passing_yards_market_status():
    """Return the immutable safety/identity contract without making provider calls."""
    return {
        "status": "ready",
        "service": "kyre-sports-api",
        **CONTRACT,
    }


@router.get("")
def passing_yards_market(
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official ESPN NFL event ID from the verified Streamlit slate.",
    )
):
    event_id = str(event_id or "").strip()
    if not event_id.isdigit():
        raise HTTPException(status_code=422, detail="event_id must be an official numeric ESPN NFL event ID")
    try:
        payload = collect_fanduel_nfl_passing_yards(event_id)
    except NFLPassingYardsCollectorError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Passing Yards market unavailable: {str(exc)[:240]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Passing Yards market unavailable: {type(exc).__name__}",
        ) from exc

    # Defense in depth: the route refuses to publish a payload that weakens any
    # permanent market/identity guardrail even if the collector regresses later.
    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if (
        semantics.get("projection_weight") != 0.0
        or semantics.get("may_modify_projection") is not False
        or semantics.get("market_context_only") is not True
        or semantics.get("stake_sizing_enabled") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("player_name_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or identity.get("synthetic_player_ids") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Passing Yards market safety contract failed closed")
    if str(payload.get("official_event_id") or "") != event_id:
        raise HTTPException(status_code=503, detail="NFL Passing Yards official event identity mismatch")

    return payload


__all__ = ["CONTRACT", "router"]
