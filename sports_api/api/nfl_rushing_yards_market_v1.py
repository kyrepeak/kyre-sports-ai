"""Kyre Sports API — NFL Rushing Yards verified post-projection market endpoint.

The endpoint exposes only fresh exact-ID sportsbook context. It does not
calculate or modify projections, probabilities, fair odds, EV, grades, stake
sizes, rankings, recommendations, or wager actions.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_fanduel_rushing_yards_v1 import (
    NFLRushingYardsCollectorError,
    SCHEMA_VERSION,
    collect_fanduel_nfl_rushing_yards_hosted,
)

router = APIRouter(prefix="/api/v1/nfl/rushing-yards/market", tags=["nfl-rushing-yards-market"])

CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "provider": "FanDuel",
    "transport": "anonymous_public_get_only",
    "official_authority": "ESPN",
    "official_event_id_required": True,
    "official_athlete_id_required": True,
    "official_team_id_required": True,
    "player_name_display_only": True,
    "player_name_matching": False,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "synthetic_player_ids": False,
    "projection_weight": 0.0,
    "market_context_only": True,
    "may_modify_projection": False,
    "probability_enabled": False,
    "fair_odds_enabled": False,
    "ev_enabled": False,
    "grading_enabled": False,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


@router.get("/status")
def rushing_yards_market_status():
    return {"status": "ready", "service": "kyre-sports-api", **CONTRACT}


@router.get("")
def rushing_yards_market(
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
        payload = collect_fanduel_nfl_rushing_yards_hosted(event_id)
    except NFLRushingYardsCollectorError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Rushing Yards market unavailable: {str(exc)[:240]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Rushing Yards market unavailable: {type(exc).__name__}",
        ) from exc

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(status_code=503, detail="NFL Rushing Yards market schema contract mismatch")
    if str(payload.get("official_event_id") or "") != event_id:
        raise HTTPException(status_code=503, detail="NFL Rushing Yards market official event identity mismatch")
    if (
        identity.get("player_name_matching") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or identity.get("synthetic_player_ids") is not False
        or semantics.get("projection_weight") != 0.0
        or semantics.get("market_context_only") is not True
        or semantics.get("may_modify_projection") is not False
        or semantics.get("probability_enabled") is not False
        or semantics.get("fair_odds_enabled") is not False
        or semantics.get("ev_enabled") is not False
        or semantics.get("grading_enabled") is not False
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Rushing Yards Step 4 market safety contract failed closed")

    seen_athletes: set[str] = set()
    for row in payload.get("props") or []:
        athlete_id = str(row.get("official_athlete_id") or "").strip()
        team_id = str(row.get("official_team_id") or "").strip()
        row_event_id = str(row.get("official_event_id") or "").strip()
        if (
            row_event_id != event_id
            or not athlete_id.isdigit()
            or not team_id.isdigit()
            or athlete_id in seen_athletes
            or str(row.get("market_type") or "").strip().lower() != "rushing_yards"
            or str(row.get("sportsbook") or "").strip().lower() != "fanduel"
            or str(row.get("line_status") or "").strip().lower() != "active"
        ):
            raise HTTPException(status_code=503, detail="NFL Rushing Yards market row identity contract failed closed")
        seen_athletes.add(athlete_id)

    return payload


__all__ = ["CONTRACT", "router"]
