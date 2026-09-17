"""Feed-independent, date-scoped College Football identity endpoint.

This endpoint exposes only verified official ESPN event identities for a requested
slate date. It deliberately does not read sportsbook inventory and therefore can
serve schedule selectors even when market reconciliation is incomplete.

Identity authority and transport are reused from the certified CFB Step-2
resolver: local verified snapshot -> GitHub verified snapshot -> live ESPN
FBS/FCS exact-date scoreboards. No synthetic IDs or fuzzy identity are allowed.
Sportsbook information remains context-only with 0.0% projection influence.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.cfb_market_identity_v1 import (
    MODEL_VERSION as IDENTITY_MODEL_VERSION,
    _fetch_espn_verified_games,
    _fetch_github_verified_games,
    load_verified_games,
)

router = APIRouter(prefix="/api/v1/cfb/markets", tags=["cfb"])

MODEL_VERSION = "CFB VERIFIED GAMES V1 • FEED-INDEPENDENT ESPN IDENTITY"
SCHEMA_VERSION = "cfb_verified_games_v1"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _public_game(row: Mapping[str, Any]) -> dict[str, Any] | None:
    event_id = _clean(row.get("event_id"))
    game_date = _clean(row.get("game_date"))
    away_team = _clean(row.get("away_team"))
    home_team = _clean(row.get("home_team"))
    if not event_id or not game_date or not away_team or not home_team:
        return None
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": _clean(row.get("away_team_id")),
        "home_team_id": _clean(row.get("home_team_id")),
        "venue": _clean(row.get("venue")),
        "broadcast": _clean(row.get("broadcast")),
        "status": _clean(row.get("status")),
        "sources": [str(value) for value in (row.get("sources") or []) if _clean(value)],
        "identity_verified": True,
    }


def _validate_day(value: str) -> str:
    raw = _clean(value)
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="game_date must be a valid YYYY-MM-DD date") from exc
    return parsed.isoformat()


@router.get("/verified-games")
def verified_games(
    game_date: str = Query(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Eastern slate date in YYYY-MM-DD format.",
    ),
) -> dict[str, Any]:
    """Return official ESPN event identities for one exact CFB slate date."""
    target = _validate_day(game_date)

    try:
        local_games, local_diag = load_verified_games()
    except ValueError as exc:
        local_games = []
        local_diag = {
            "snapshot_present": False,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:240],
        }

    github_games, github_diag = _fetch_github_verified_games()
    espn_games, espn_diag = _fetch_espn_verified_games(target)

    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_counts = {"local": 0, "github": 0, "espn": 0}
    for source_name, rows in (
        ("local", local_games),
        ("github", github_games),
        ("espn", espn_games),
    ):
        for row in rows:
            if not isinstance(row, Mapping) or _clean(row.get("game_date")) != target:
                continue
            public = _public_game(row)
            if public is None:
                continue
            event_id = public["event_id"]
            if event_id in seen:
                continue
            seen.add(event_id)
            combined.append(public)
            source_counts[source_name] += 1

    github_ok = bool(github_diag.get("ok")) if isinstance(github_diag, Mapping) else False
    espn_ok = bool(espn_diag.get("ok")) if isinstance(espn_diag, Mapping) else False
    if not combined and not github_ok and not espn_ok:
        raise HTTPException(
            status_code=503,
            detail="verified CFB identity unavailable for requested date",
        )

    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 2,
        "model_version": MODEL_VERSION,
        "identity_parent_model_version": IDENTITY_MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "game_date": target,
        "game_count": len(combined),
        "games": combined,
        "diagnostics": {
            "local_snapshot": local_diag,
            "github_snapshot": github_diag,
            "espn_exact_date": espn_diag,
            "returned_by_source": source_counts,
            "duplicate_event_ids_removed": (
                sum(
                    1
                    for rows in (local_games, github_games, espn_games)
                    for row in rows
                    if isinstance(row, Mapping) and _clean(row.get("game_date")) == target
                )
                - len(combined)
            ),
            "sportsbook_feed_read": False,
        },
        "identity_policy": {
            "official_id_source": "ESPN event_id",
            "synthetic_ids": False,
            "fuzzy_matching": False,
            "fail_closed": True,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "router",
    "verified_games",
]
