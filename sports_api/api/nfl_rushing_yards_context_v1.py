"""Kyre Sports API — NFL Rushing Yards Step 2 player + matchup context."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_rushing_yards_context_v1 import (
    MODEL_VERSION,
    NFLRushingYardsContextError,
    collect_nfl_rushing_yards_context,
)

router = APIRouter(prefix="/api/v1/nfl/rushing-yards", tags=["nfl-rushing-yards"])

CONTRACT = {
    "schema_version": MODEL_VERSION,
    "provider": "ESPN",
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
    "model_enabled": False,
    "projection_enabled": False,
    "market_enabled": False,
    "sportsbook_influence": 0.0,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


@router.get("/status")
def rushing_yards_context_status():
    return {"status": "ready", "service": "kyre-sports-api", **CONTRACT}


@router.get("")
def rushing_yards_context(
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
        payload = collect_nfl_rushing_yards_context(event_id)
    except NFLRushingYardsContextError as exc:
        raise HTTPException(status_code=503, detail=f"NFL Rushing Yards context unavailable: {str(exc)[:240]}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"NFL Rushing Yards context unavailable: {type(exc).__name__}") from exc

    identity = payload.get("identity") or {}
    semantics = payload.get("semantics") or {}
    if str(payload.get("official_event_id") or "") != event_id:
        raise HTTPException(status_code=503, detail="NFL Rushing Yards official event identity mismatch")
    if payload.get("schema_version") != MODEL_VERSION:
        raise HTTPException(status_code=503, detail="NFL Rushing Yards schema contract mismatch")
    if (
        identity.get("official_event_id_required") is not True
        or identity.get("official_athlete_id_required") is not True
        or identity.get("official_team_id_required") is not True
        or identity.get("player_name_display_only") is not True
        or identity.get("player_name_matching") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or identity.get("synthetic_player_ids") is not False
        or semantics.get("model_enabled") is not False
        or semantics.get("projection_enabled") is not False
        or semantics.get("market_enabled") is not False
        or semantics.get("sportsbook_influence") != 0.0
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Rushing Yards Step 2 safety contract failed closed")

    seen_athletes: set[str] = set()
    for team in payload.get("teams") or []:
        team_id = str(team.get("official_team_id") or "").strip()
        opponent_id = str(team.get("opponent_official_team_id") or "").strip()
        if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
            raise HTTPException(status_code=503, detail="NFL Rushing Yards team identity contract failed closed")
        for player in team.get("players") or []:
            athlete_id = str(player.get("official_athlete_id") or "").strip()
            player_team_id = str(player.get("official_team_id") or "").strip()
            if not athlete_id.isdigit() or player_team_id != team_id or athlete_id in seen_athletes:
                raise HTTPException(status_code=503, detail="NFL Rushing Yards athlete identity contract failed closed")
            seen_athletes.add(athlete_id)

    return payload


__all__ = ["CONTRACT", "router"]
