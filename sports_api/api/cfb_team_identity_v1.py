"""CFB V164 exact ESPN team identity endpoint.

Additive read-only identity surface for presentation assets such as team logos.
It resolves exact ESPN team IDs by official event_id for one slate date. It
cannot modify projections, rankings, qualification, odds, or model behavior.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.cfb_market_identity_v1 import _fetch_espn_verified_games

router = APIRouter(prefix="/api/v1/cfb/identity", tags=["cfb"])

MODEL_VERSION = "CFB TEAM IDENTITY V1 • V164 EXACT ESPN TEAM IDS"
SCHEMA_VERSION = "cfb_team_identity_v1"
ESPN_LOGO_CDN_TEMPLATE = "https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _public_row(game: Mapping[str, Any]) -> dict[str, Any] | None:
    event_id = _clean(game.get("event_id"))
    game_date = _clean(game.get("game_date"))
    away_team = _clean(game.get("away_team"))
    home_team = _clean(game.get("home_team"))
    away_id = _clean(game.get("away_team_id"))
    home_id = _clean(game.get("home_team_id"))
    if (
        not event_id
        or not game_date
        or not away_team
        or not home_team
        or not away_id.isdigit()
        or not home_id.isdigit()
    ):
        return None
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "away_logo": ESPN_LOGO_CDN_TEMPLATE.format(team_id=away_id),
        "home_logo": ESPN_LOGO_CDN_TEMPLATE.format(team_id=home_id),
        "identity_verified": True,
        "identity_method": "official ESPN event_id -> exact ESPN team IDs",
    }


def build_team_identity_payload(
    requested_day: str,
    games: list[dict[str, Any]],
    diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game in games:
        row = _public_row(game)
        if row is None or row["game_date"] != requested_day:
            continue
        if row["event_id"] in seen:
            continue
        seen.add(row["event_id"])
        rows.append(row)

    rows.sort(
        key=lambda row: (
            row["away_team"].casefold(),
            row["home_team"].casefold(),
            row["event_id"],
        )
    )
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "consumer": "CFB Game Total V164 exact team logos",
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "requested_date": requested_day,
        "game_count": len(rows),
        "games": rows,
        "synthetic_ids": False,
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "diagnostics": {
            "fail_closed": True,
            "source": "ESPN college-football FBS/FCS scoreboards",
            "upstream": dict(diagnostics or {}),
        },
    }


@router.get("/team-logos")
def team_logos(
    game_date: str = Query(..., min_length=10, max_length=10),
):
    try:
        requested_day = date.fromisoformat(game_date).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="game_date must be YYYY-MM-DD") from exc

    games, diagnostics = _fetch_espn_verified_games(requested_day)
    payload = build_team_identity_payload(requested_day, games, diagnostics)
    if payload["game_count"] == 0 and not bool((diagnostics or {}).get("ok")):
        raise HTTPException(
            status_code=503,
            detail="Exact ESPN team identity is temporarily unavailable.",
        )
    return payload


__all__ = [
    "ESPN_LOGO_CDN_TEMPLATE",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "build_team_identity_payload",
    "router",
    "team_logos",
]
