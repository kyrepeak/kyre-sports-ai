"""Consumer-ready College Football odds endpoint — odds integration Step 3.

Step 1 owns the market transport.
Step 2 owns verified game identity.
Step 3 exposes one stable, Streamlit-friendly read contract.

Only identity-verified rows are allowed through this endpoint. Sportsbook data
remains context-only and carries 0% projection weight.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.cfb_market_identity_v1 import (
    _fetch_espn_verified_games,
    _fetch_github_verified_games,
    load_verified_games,
    reconcile_market_feed,
    resolve_verified_games,
)
from sports_api.api.cfb_markets import _load_feed

router = APIRouter(prefix="/api/v1/cfb", tags=["cfb"])

MODEL_VERSION = "CFB ODDS API V1 • ODDS INTEGRATION STEP 3"
SCHEMA_VERSION = "cfb_odds_v1"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _public_row(line: Mapping[str, Any]) -> dict[str, Any]:
    if line.get("identity_verified") is not True:
        raise ValueError("Step 3 refuses non-verified CFB market identity")
    official_game_id = _clean(line.get("official_game_id"))
    away_team = _clean(line.get("official_away_team"))
    home_team = _clean(line.get("official_home_team"))
    if not official_game_id or not away_team or not home_team:
        raise ValueError("Step 3 requires official game and team identity")
    return {
        "game_id": official_game_id,
        "provider_game_id": _clean(line.get("provider_game_id")),
        "game_date": _clean(line.get("game_date")),
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": _clean(line.get("away_team_id")),
        "home_team_id": _clean(line.get("home_team_id")),
        "start_time_utc": _clean(line.get("start_time_utc")),
        "sportsbook": _clean(line.get("sportsbook")),
        "market_type": "game_total",
        "total": line.get("total"),
        "line_status": _clean(line.get("line_status")),
        "line_updated_at_utc": _clean(line.get("updated_at_utc")),
        "venue": _clean(line.get("venue")),
        "broadcast": _clean(line.get("broadcast")),
        "official_status": _clean(line.get("official_status")),
        "identity_verified": True,
        "identity_method": _clean(line.get("match_method")),
        "identity_confidence": line.get("match_confidence"),
    }


def _selector_public_row(game: Mapping[str, Any]) -> dict[str, Any] | None:
    event_id = _clean(game.get("event_id"))
    game_date = _clean(game.get("game_date"))
    away_team = _clean(game.get("away_team"))
    home_team = _clean(game.get("home_team"))
    if not event_id or not game_date or not away_team or not home_team:
        return None
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": _clean(game.get("away_team_id")),
        "home_team_id": _clean(game.get("home_team_id")),
        "venue": _clean(game.get("venue")),
        "broadcast": _clean(game.get("broadcast")),
        "status": _clean(game.get("status")),
        "identity_verified": True,
    }


def build_odds_payload(
    feed: Mapping[str, Any],
    verified_games: list[dict[str, Any]],
) -> dict[str, Any]:
    reconciled = reconcile_market_feed(feed, verified_games)
    diagnostics = dict(reconciled.get("diagnostics") or {})
    lines = list(reconciled.get("lines") or [])
    unmatched = list(reconciled.get("unmatched") or [])

    # Step 3 is intentionally strict. A partial identity slate should never look
    # like a complete public odds board.
    if unmatched or diagnostics.get("all_lines_identity_verified") is not True:
        raise ValueError(
            "CFB odds endpoint is not ready: market identity coverage is incomplete"
        )

    rows = [_public_row(line) for line in lines]
    rows.sort(
        key=lambda row: (
            row["start_time_utc"],
            row["game_id"],
            row["sportsbook"],
        )
    )

    semantics = dict(reconciled.get("market_semantics") or {})
    semantics.update(
        {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        }
    )

    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 3,
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "captured_at_utc": reconciled.get("captured_at_utc"),
        "source": reconciled.get("source"),
        "game_count": len(rows),
        "games": rows,
        "diagnostics": {
            "input_market_rows": diagnostics.get("input_market_rows", 0),
            "identity_verified_rows": len(rows),
            "unmatched_market_rows": 0,
            "complete_identity_coverage": True,
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
            "fail_closed": True,
        },
        "market_semantics": semantics,
    }


def _filtered_payload(
    payload: dict[str, Any],
    *,
    game_date: str | None,
    game_id: str | None,
    sportsbook: str | None,
) -> dict[str, Any]:
    rows = list(payload["games"])

    if game_date is not None:
        target = game_date.strip()
        rows = [row for row in rows if row["game_date"] == target]
    if game_id is not None:
        target = game_id.strip()
        rows = [row for row in rows if row["game_id"] == target]
    if sportsbook is not None:
        target = sportsbook.strip().casefold()
        rows = [row for row in rows if row["sportsbook"].casefold() == target]

    if (game_date is not None or game_id is not None or sportsbook is not None) and not rows:
        raise HTTPException(
            status_code=404,
            detail="No identity-verified CFB odds matched those filters.",
        )

    result = dict(payload)
    result["games"] = rows
    result["game_count"] = len(rows)
    result["diagnostics"] = dict(payload["diagnostics"])
    result["diagnostics"]["returned_rows"] = len(rows)
    return result


@router.get("/odds/status")
def odds_status():
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 3,
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "endpoint_ready": True,
        "endpoint": "/api/v1/cfb/odds",
        "consumer": "Streamlit / Kyre Sports AI",
        "market_scope": ["game_total"],
        "identity_required": True,
        "identity_policy": {
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


@router.get("/odds")
def odds(
    game_date: str | None = Query(default=None),
    game_id: str | None = Query(default=None),
    sportsbook: str | None = Query(default=None),
):
    feed = _load_feed()
    try:
        verified_games, identity_resolution = resolve_verified_games(feed)
        payload = build_odds_payload(feed, verified_games)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payload["identity_resolution"] = identity_resolution
    return _filtered_payload(
        payload,
        game_date=game_date,
        game_id=game_id,
        sportsbook=sportsbook,
    )


@router.get("/selector/verified-games")
def selector_verified_games(
    game_date: str = Query(..., min_length=10, max_length=10),
):
    """Return official selector identities for one CFB slate date.

    This endpoint is presentation-only. It deliberately combines every existing
    verified identity source for the requested date so future games remain
    selectable even when no sportsbook market exists. No synthetic IDs are
    created and the response can never modify projections.
    """
    try:
        requested_day = date.fromisoformat(game_date).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="game_date must be YYYY-MM-DD") from exc

    local_games, local_diag = load_verified_games()
    github_games, github_diag = _fetch_github_verified_games()
    espn_games, espn_diag = _fetch_espn_verified_games(requested_day)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_counts = {"runtime_snapshot": 0, "github_snapshot": 0, "server_espn": 0}
    for source_name, candidates in (
        ("runtime_snapshot", local_games),
        ("github_snapshot", github_games),
        ("server_espn", espn_games),
    ):
        for game in candidates:
            if _clean(game.get("game_date")) != requested_day:
                continue
            row = _selector_public_row(game)
            if row is None:
                continue
            event_id = row["event_id"]
            if event_id in seen:
                continue
            seen.add(event_id)
            row["identity_source"] = source_name
            rows.append(row)
            source_counts[source_name] += 1

    rows.sort(key=lambda row: (row["away_team"].casefold(), row["home_team"].casefold(), row["event_id"]))
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "consumer": "CFB Game Total V163 selector",
        "requested_date": requested_day,
        "game_count": len(rows),
        "games": rows,
        "synthetic_ids": False,
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "diagnostics": {
            "fail_closed": True,
            "runtime_snapshot": local_diag,
            "github_snapshot": github_diag,
            "server_espn": espn_diag,
            "source_counts": source_counts,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "build_odds_payload",
    "router",
    "selector_verified_games",
]
