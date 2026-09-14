"""Additive fast transport for the certified NFL Rushing Yards context payload."""
from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, HTTPException, Query, Response

from sports_api.api.nfl_rushing_yards_context_v1 import CONTRACT as FROZEN_V1_CONTRACT
from sports_api.collectors.nfl_rushing_yards_context_v2 import (
    FAST_COLLECTOR_VERSION,
    MODEL_VERSION,
    NFLRushingYardsContextError,
    collect_nfl_rushing_yards_context_fast,
)

router = APIRouter(
    prefix="/api/v1/nfl/rushing-yards/fast",
    tags=["nfl-rushing-yards-fast"],
)

CONTRACT = {
    **FROZEN_V1_CONTRACT,
    "schema_version": MODEL_VERSION,
    "performance_only": True,
    "collector_version": FAST_COLLECTOR_VERSION,
    "frozen_payload_contract": "nfl_rushing_yards_context_v1",
}


def _validate_payload(payload: dict, event_id: str) -> None:
    identity = payload.get("identity") or {}
    semantics = payload.get("semantics") or {}
    if str(payload.get("official_event_id") or "") != event_id:
        raise HTTPException(
            status_code=503,
            detail="NFL Rushing Yards fast context official event identity mismatch",
        )
    if payload.get("schema_version") != MODEL_VERSION:
        raise HTTPException(
            status_code=503,
            detail="NFL Rushing Yards fast context schema contract mismatch",
        )
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
        raise HTTPException(
            status_code=503,
            detail="NFL Rushing Yards fast context safety contract failed closed",
        )

    seen_athletes: set[str] = set()
    team_ids: set[str] = set()
    teams = payload.get("teams") or []
    if not isinstance(teams, list) or len(teams) != 2:
        raise HTTPException(
            status_code=503,
            detail="NFL Rushing Yards fast context two-team contract failed closed",
        )
    for team in teams:
        team_id = str(team.get("official_team_id") or "").strip()
        opponent_id = str(team.get("opponent_official_team_id") or "").strip()
        if (
            not team_id.isdigit()
            or not opponent_id.isdigit()
            or team_id == opponent_id
            or team_id in team_ids
        ):
            raise HTTPException(
                status_code=503,
                detail="NFL Rushing Yards fast context team identity contract failed closed",
            )
        team_ids.add(team_id)
        for player in team.get("players") or []:
            athlete_id = str(player.get("official_athlete_id") or "").strip()
            player_team_id = str(player.get("official_team_id") or "").strip()
            if (
                not athlete_id.isdigit()
                or player_team_id != team_id
                or athlete_id in seen_athletes
            ):
                raise HTTPException(
                    status_code=503,
                    detail="NFL Rushing Yards fast context athlete identity contract failed closed",
                )
            seen_athletes.add(athlete_id)
    if {str(team.get("opponent_official_team_id") or "") for team in teams} != team_ids:
        raise HTTPException(
            status_code=503,
            detail="NFL Rushing Yards fast context reciprocal opponent contract failed closed",
        )


@router.get("/status")
def rushing_yards_fast_context_status():
    return {"status": "ready", "service": "kyre-sports-api", **CONTRACT}


@router.get("")
def rushing_yards_fast_context(
    response: Response,
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official ESPN NFL event ID from the verified Streamlit slate.",
    ),
):
    event_id = str(event_id or "").strip()
    if not event_id.isdigit():
        raise HTTPException(
            status_code=422,
            detail="event_id must be an official numeric ESPN NFL event ID",
        )

    started = perf_counter()
    try:
        payload = collect_nfl_rushing_yards_context_fast(event_id)
    except NFLRushingYardsContextError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Rushing Yards fast context unavailable: {str(exc)[:240]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Rushing Yards fast context unavailable: {type(exc).__name__}",
        ) from exc

    _validate_payload(payload, event_id)
    elapsed_ms = (perf_counter() - started) * 1000.0
    response.headers["Server-Timing"] = f"rushing-context-v2;dur={elapsed_ms:.1f}"
    response.headers["X-Kyre-Rushing-Context"] = "v2-fast"
    return payload


__all__ = ["CONTRACT", "router"]
