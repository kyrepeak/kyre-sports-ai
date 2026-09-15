"""Kyre Sports API — official NFL Game Totals slate metadata V1.

Sportsbook and projection data are deliberately excluded. This endpoint owns
the verified game shell the future Game Totals page will consume: exact event
identity, kickoff, teams, venue and status for one requested calendar date.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_game_totals_schedule_v1 import (
    NFLGameTotalsScheduleError,
    SCHEMA_VERSION,
    collect_official_nfl_slate,
)

router = APIRouter(
    prefix="/api/v1/nfl/game-totals/games",
    tags=["nfl-game-totals-games"],
)

CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "service": "Kyre Sports API",
    "sport": "nfl",
    "official_authority": "ESPN",
    "exact_event_identity": True,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "sportsbook_data_included": False,
    "projection_data_included": False,
    "missing_venue_drops_game": False,
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _validate_game_date(value: str) -> str:
    text = _text(value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="game_date must be YYYY-MM-DD") from exc


def _validate_slate(payload: dict[str, Any], requested_date: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="NFL Game Totals slate payload is invalid")
    games = payload.get("games")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or _text(payload.get("official_authority")) != "ESPN"
        or _text(payload.get("requested_date")) != requested_date
        or not isinstance(games, list)
        or payload.get("game_count") != len(games)
    ):
        raise HTTPException(status_code=503, detail="NFL Game Totals slate contract failed closed")

    seen: set[str] = set()
    venue_available = 0
    for game in games:
        if not isinstance(game, dict):
            raise HTTPException(status_code=503, detail="NFL Game Totals game row is invalid")
        event_id = _text(game.get("official_event_id"))
        away = game.get("away") or {}
        home = game.get("home") or {}
        status = game.get("status") or {}
        venue = game.get("venue") or {}
        identity = game.get("identity_policy") or {}
        if (
            not event_id.isdigit()
            or event_id in seen
            or not _text(game.get("kickoff_utc"))
            or not isinstance(away, dict)
            or not isinstance(home, dict)
            or not _text(away.get("team_id")).isdigit()
            or not _text(home.get("team_id")).isdigit()
            or not _text(away.get("abbr"))
            or not _text(home.get("abbr"))
            or not isinstance(status, dict)
            or not isinstance(status.get("completed"), bool)
            or not isinstance(status.get("pregame"), bool)
            or not isinstance(venue, dict)
            or not isinstance(venue.get("available"), bool)
            or identity.get("fuzzy_matching") is not False
            or identity.get("synthetic_event_ids") is not False
        ):
            raise HTTPException(status_code=503, detail="NFL Game Totals game metadata failed closed")
        if venue["available"] and not _text(venue.get("name")):
            raise HTTPException(status_code=503, detail="NFL Game Totals venue marked available without a name")
        seen.add(event_id)
        venue_available += int(venue["available"])

    if payload.get("venue_available_count") != venue_available:
        raise HTTPException(status_code=503, detail="NFL Game Totals venue available count mismatch")
    if payload.get("venue_missing_count") != len(games) - venue_available:
        raise HTTPException(status_code=503, detail="NFL Game Totals venue missing count mismatch")

    out = dict(payload)
    out["metadata_contract"] = dict(CONTRACT)
    return out


@router.get("/status")
def game_totals_games_status():
    return {
        "status": "metadata_ready",
        "endpoint": "/api/v1/nfl/game-totals/games",
        "shared_host_attached": True,
        **CONTRACT,
    }


@router.get("")
def game_totals_games(
    game_date: str = Query(
        ...,
        min_length=10,
        max_length=10,
        description="NFL slate calendar date in YYYY-MM-DD format.",
    )
):
    requested = _validate_game_date(game_date)
    try:
        payload = collect_official_nfl_slate(requested)
    except NFLGameTotalsScheduleError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Game Totals official slate unavailable: {str(exc)[:240]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Game Totals official slate unavailable: {type(exc).__name__}",
        ) from exc
    return _validate_slate(payload, requested)


__all__ = [
    "CONTRACT",
    "SCHEMA_VERSION",
    "_validate_slate",
    "game_totals_games_status",
    "router",
]
