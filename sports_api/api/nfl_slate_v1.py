"""Kyre Sports API — canonical NFL Slate V1.

This route owns the application-facing NFL schedule/slate contract. Schedule
rows are reused from the already-certified NFLverse-backed schedule layer; the
frontend never talks to an underlying provider directly. Missing schedule data
remains explicit and is never converted to fabricated games or zero values.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from sports_api.api import nfl_passing_yards_slate_v1 as schedule_source


SCHEMA_VERSION = "nfl_slate_v1"
router = APIRouter(prefix="/api/v1/nfl/slate", tags=["nfl-slate"])


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_nfl_slate(target_date: str | None = None) -> dict[str, Any]:
    resolved_date, games = schedule_source._schedule_games(target_date)
    games = [dict(game) for game in games]
    season = next((game.get("season") for game in games if game.get("season") is not None), None)
    week = next((game.get("week") for game in games if game.get("week") is not None), None)
    ready = bool(resolved_date and games)
    return {
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "ready": ready,
        "reason": None if ready else "NFL slate schedule is not currently available",
        "resolved_date": resolved_date,
        "season": season,
        "week": week,
        "game_count": len(games),
        "games": games,
        "routing": {
            "canonical_ids": True,
            "missing_to_zero": False,
            "semantic_empty_states": True,
            "data_truth_gate": "api2_step2d_data_truth_gate_v1",
        },
        "provenance": {
            "schedule": "NFLverse",
            "application_gateway": "Kyre Sports API",
        },
    }


@router.get("")
def get_nfl_slate(date: str | None = Query(default=None)) -> dict[str, Any]:
    target = _text(date)[:10] or None
    return build_nfl_slate(target)


@router.get("/status")
def get_nfl_slate_status(date: str | None = Query(default=None)) -> dict[str, Any]:
    payload = build_nfl_slate(_text(date)[:10] or None)
    return {
        "service": payload["service"],
        "gateway": payload["gateway"],
        "schema_version": payload["schema_version"],
        "ready": payload["ready"],
        "reason": payload["reason"],
        "resolved_date": payload["resolved_date"],
        "season": payload["season"],
        "week": payload["week"],
        "game_count": payload["game_count"],
        "routing": payload["routing"],
        "provenance": payload["provenance"],
    }


__all__ = ["SCHEMA_VERSION", "build_nfl_slate", "router"]
