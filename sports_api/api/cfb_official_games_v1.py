"""Read-only canonical CFB game identity feed for Streamlit consumers.

This module reuses the certified CFB identity sources from
``cfb_market_identity_v1`` and exposes only schedule identity metadata.
It never modifies projections, probabilities, qualification, rankings, or
sportsbook/model influence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.cfb_market_identity_v1 import (
    _fetch_espn_verified_games,
    _fetch_github_verified_games,
    load_verified_games,
)

router = APIRouter(prefix="/api/v1/cfb/identity", tags=["cfb"])
MODEL_VERSION = "CFB OFFICIAL GAMES V1 • GAME TOTAL V164 IDENTITY TRANSPORT"


def _validated_date(value: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="game_date must use YYYY-MM-DD",
        ) from exc
    if parsed != text:
        raise HTTPException(status_code=400, detail="game_date must use YYYY-MM-DD")
    return parsed


def _games_for_date(
    games: Iterable[Mapping[str, Any]],
    game_date: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in games:
        if str(raw.get("game_date") or "").strip() != game_date:
            continue
        event_id = str(raw.get("event_id") or "").strip()
        away_team = str(raw.get("away_team") or "").strip()
        home_team = str(raw.get("home_team") or "").strip()
        if not event_id or not away_team or not home_team or event_id in seen:
            continue
        seen.add(event_id)
        rows.append(dict(raw))
    rows.sort(
        key=lambda row: (
            str(row.get("away_team") or ""),
            str(row.get("home_team") or ""),
            str(row.get("event_id") or ""),
        )
    )
    return rows


@router.get("/official-games")
def official_games(
    game_date: str = Query(..., description="Eastern game date in YYYY-MM-DD"),
):
    """Return canonical verified CFB game identities for one exact date.

    Source order is intentionally server-side: local verified snapshot, GitHub
    hourly verified snapshot, then direct ESPN only when both snapshots have no
    verified rows for the requested date. Streamlit therefore never needs ESPN
    network access to obtain official event IDs.
    """
    requested_day = _validated_date(game_date)

    try:
        local_games, local_diag = load_verified_games()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    local_rows = _games_for_date(local_games, requested_day)

    github_games, github_diag = _fetch_github_verified_games()
    github_rows = _games_for_date(github_games, requested_day)

    combined = _games_for_date([*local_rows, *github_rows], requested_day)
    espn_diag: dict[str, Any] = {
        "attempted": False,
        "date": requested_day,
        "games": 0,
    }
    if not combined:
        espn_games, raw_espn_diag = _fetch_espn_verified_games(requested_day)
        espn_diag = {**raw_espn_diag, "attempted": True}
        combined = _games_for_date(espn_games, requested_day)

    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "model_version": MODEL_VERSION,
        "game_date": requested_day,
        "verified": bool(combined),
        "game_count": len(combined),
        "games": combined,
        "synthetic_ids": False,
        "fail_closed": True,
        "sportsbook_projection_influence_pct": 0.0,
        "identity_policy": {
            "streamlit_direct_espn_required": False,
            "source_order": [
                "local verified runtime snapshot",
                "GitHub hourly verified runtime snapshot",
                "server-side ESPN exact-date fallback",
            ],
        },
        "diagnostics": {
            "local": local_diag,
            "local_rows_for_date": len(local_rows),
            "github": github_diag,
            "github_rows_for_date": len(github_rows),
            "espn": espn_diag,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "official_games",
    "router",
]
