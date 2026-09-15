"""Kyre Sports API — NFL Receiving Yards player + matchup context.

A short-lived exact-event in-process cache reduces repeated ESPN collection
work while preserving the original capture timestamp and re-running the full
exact-ID/safety validator on every response.
"""
from __future__ import annotations

from copy import deepcopy
import threading
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_receiving_yards_context_v1 import (
    ELIGIBLE_RECEIVER_POSITIONS,
    MODEL_VERSION,
    NFLReceivingYardsContextError,
    collect_nfl_receiving_yards_context,
)

router = APIRouter(
    prefix="/api/v1/nfl/receiving-yards",
    tags=["nfl-receiving-yards"],
)

CONTEXT_SNAPSHOT_TTL_SECONDS = 60.0
_CACHE_LOCK = threading.RLock()
_CONTEXT_SNAPSHOT_CACHE: dict[str, tuple[float, int, dict[str, Any]]] = {}
_EVENT_LOCKS: dict[str, threading.Lock] = {}

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
    "eligible_positions": sorted(ELIGIBLE_RECEIVER_POSITIONS),
    "targets_explicit_only": True,
    "targets_inferred": False,
    "model_enabled": False,
    "projection_enabled": False,
    "market_enabled": False,
    "sportsbook_influence": 0.0,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


def _validate_context_payload(payload: dict[str, Any], event_id: str) -> dict[str, Any]:
    """Re-run exact-ID, target-integrity and safety contracts every response."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="NFL Receiving Yards context payload is invalid")

    identity = payload.get("identity") or {}
    semantics = payload.get("semantics") or {}
    if str(payload.get("official_event_id") or "") != event_id:
        raise HTTPException(status_code=503, detail="NFL Receiving Yards official event identity mismatch")
    if payload.get("schema_version") != MODEL_VERSION:
        raise HTTPException(status_code=503, detail="NFL Receiving Yards schema contract mismatch")
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
        or semantics.get("targets_inferred") is not False
    ):
        raise HTTPException(
            status_code=503,
            detail="NFL Receiving Yards safety contract failed closed",
        )

    seen_athletes: set[str] = set()
    teams = payload.get("teams") or []
    if not isinstance(teams, list):
        raise HTTPException(status_code=503, detail="NFL Receiving Yards team payload contract failed closed")

    for team in teams:
        if not isinstance(team, dict):
            raise HTTPException(status_code=503, detail="NFL Receiving Yards team payload contract failed closed")
        team_id = str(team.get("official_team_id") or "").strip()
        opponent_id = str(team.get("opponent_official_team_id") or "").strip()
        if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
            raise HTTPException(status_code=503, detail="NFL Receiving Yards team identity contract failed closed")

        defense = team.get("opponent_pass_defense") or {}
        if (
            not isinstance(defense, dict)
            or str(defense.get("official_team_id") or "").strip() != opponent_id
        ):
            raise HTTPException(status_code=503, detail="NFL Receiving Yards pass-defense identity failed closed")
        if defense.get("targets_data_available") is False and defense.get("targets_allowed_per_game") is not None:
            raise HTTPException(status_code=503, detail="NFL Receiving Yards defensive target contract failed closed")

        players = team.get("players") or []
        if not isinstance(players, list):
            raise HTTPException(status_code=503, detail="NFL Receiving Yards athlete payload contract failed closed")
        for player in players:
            if not isinstance(player, dict):
                raise HTTPException(status_code=503, detail="NFL Receiving Yards athlete payload contract failed closed")
            athlete_id = str(player.get("official_athlete_id") or "").strip()
            player_team_id = str(player.get("official_team_id") or "").strip()
            position = str(player.get("position") or "").strip().upper()
            if (
                not athlete_id.isdigit()
                or player_team_id != team_id
                or athlete_id in seen_athletes
                or position not in ELIGIBLE_RECEIVER_POSITIONS
            ):
                raise HTTPException(status_code=503, detail="NFL Receiving Yards athlete identity contract failed closed")
            seen_athletes.add(athlete_id)

            targets_available = player.get("targets_data_available") is True
            targets = player.get("targets")
            targets_per_game = player.get("targets_per_game")
            target_sample_games = player.get("target_sample_games")
            if targets_available:
                if targets is None or targets_per_game is None or not isinstance(target_sample_games, int) or target_sample_games <= 0:
                    raise HTTPException(status_code=503, detail="NFL Receiving Yards explicit-target contract failed closed")
            elif targets is not None or targets_per_game is not None:
                raise HTTPException(status_code=503, detail="NFL Receiving Yards inferred-target contract failed closed")

    return payload


def _collector_identity() -> int:
    """Keep test/runtime collector swaps from reusing an older cached payload."""
    return id(collect_nfl_receiving_yards_context)


def _cache_get(event_id: str, now: float | None = None) -> dict[str, Any] | None:
    stamp = monotonic() if now is None else float(now)
    collector_id = _collector_identity()
    with _CACHE_LOCK:
        entry = _CONTEXT_SNAPSHOT_CACHE.get(event_id)
        if entry is None:
            return None
        expires_at, stored_collector_id, payload = entry
        if expires_at <= stamp or stored_collector_id != collector_id:
            _CONTEXT_SNAPSHOT_CACHE.pop(event_id, None)
            return None
        return deepcopy(payload)


def _cache_put(event_id: str, payload: dict[str, Any], now: float | None = None) -> None:
    if payload.get("ready") is not True:
        return
    stamp = monotonic() if now is None else float(now)
    with _CACHE_LOCK:
        _CONTEXT_SNAPSHOT_CACHE[event_id] = (
            stamp + CONTEXT_SNAPSHOT_TTL_SECONDS,
            _collector_identity(),
            deepcopy(payload),
        )


def _event_lock(event_id: str) -> threading.Lock:
    with _CACHE_LOCK:
        lock = _EVENT_LOCKS.get(event_id)
        if lock is None:
            lock = threading.Lock()
            _EVENT_LOCKS[event_id] = lock
        return lock


def _clear_context_snapshot_cache() -> None:
    """Test/operations helper; never weakens response validation."""
    with _CACHE_LOCK:
        _CONTEXT_SNAPSHOT_CACHE.clear()
        _EVENT_LOCKS.clear()


def _collect_or_reuse_context(event_id: str) -> dict[str, Any]:
    cached = _cache_get(event_id)
    if cached is not None:
        return _validate_context_payload(cached, event_id)

    with _event_lock(event_id):
        cached = _cache_get(event_id)
        if cached is not None:
            return _validate_context_payload(cached, event_id)

        try:
            payload = collect_nfl_receiving_yards_context(event_id)
        except NFLReceivingYardsContextError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Receiving Yards context unavailable: {str(exc)[:240]}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Receiving Yards context unavailable: {type(exc).__name__}",
            ) from exc

        validated = _validate_context_payload(payload, event_id)
        _cache_put(event_id, validated)
        return deepcopy(validated)


@router.get("/status")
def receiving_yards_context_status():
    return {"status": "ready", "service": "kyre-sports-api", **CONTRACT}


@router.get("")
def receiving_yards_context(
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official ESPN NFL event ID from the verified Streamlit slate.",
    )
):
    event_id = str(event_id or "").strip()
    if not event_id.isdigit():
        raise HTTPException(
            status_code=422,
            detail="event_id must be an official numeric ESPN NFL event ID",
        )
    return _collect_or_reuse_context(event_id)


__all__ = [
    "CONTEXT_SNAPSHOT_TTL_SECONDS",
    "CONTRACT",
    "_clear_context_snapshot_cache",
    "router",
]
