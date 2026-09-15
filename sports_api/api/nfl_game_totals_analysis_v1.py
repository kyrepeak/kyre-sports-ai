"""Kyre Sports API — public NFL Game Totals analysis endpoint V1.

This module is a thin conductor over the already-certified Game Totals layers:
official ESPN slate identity -> ESPN team scoring profiles -> football-only
features -> football-only fair-total projection -> FanDuel market snapshot ->
market line used only as an Over/Under evaluation threshold for the certified
Monte Carlo distribution.

No sportsbook field may modify the football feature vector, projected team
points, projected fair total, simulation means, uncertainty, or distribution.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.nfl_game_totals_market_v1 import _collect_or_reuse_market
from sports_api.collectors.nfl_game_totals_schedule_v1 import (
    NFLGameTotalsScheduleError,
    collect_official_nfl_slate,
)
from sports_api.collectors.nfl_game_totals_team_profiles_v1 import (
    NFLGameTotalsTeamProfileError,
    collect_team_scoring_profile,
)
from sports_api.collectors.nfl_game_totals_features_v1 import (
    NFLGameTotalsFeatureError,
    build_game_totals_feature_vector,
)
from sports_api.nfl_game_totals_projection_v1 import (
    NFLGameTotalsProjectionError,
    project_game_total,
)
from sports_api.nfl_game_totals_probability_v1 import (
    CERTIFIED_BATCHES,
    CERTIFIED_SEED,
    CERTIFIED_SIMULATIONS,
    NFLGameTotalsProbabilityError,
    simulate_over_under,
)

router = APIRouter(
    prefix="/api/v1/nfl/game-totals/analysis",
    tags=["nfl-game-totals-analysis"],
)

CONTRACT = {
    "service": "Kyre Sports API",
    "sport": "nfl",
    "market": "game_total",
    "official_authority": "ESPN",
    "exact_event_identity": True,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "sportsbook_projection_influence": 0.0,
    "sportsbook_distribution_influence": 0.0,
    "market_line_role": "evaluation_threshold_only",
    "certified_simulations": CERTIFIED_SIMULATIONS,
    "certified_batches": CERTIFIED_BATCHES,
    "certified_seed": CERTIFIED_SEED,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _validate_game_date(value: str) -> str:
    text = _text(value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="game_date must be YYYY-MM-DD") from exc


def _validate_event_id(value: str) -> str:
    event_id = _text(value)
    if not event_id.isdigit():
        raise HTTPException(
            status_code=422,
            detail="event_id must be an official numeric ESPN NFL event ID",
        )
    return event_id


def _verified_game_from_slate(
    payload: Mapping[str, Any],
    requested_date: str,
    event_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise HTTPException(status_code=503, detail="NFL Game Totals official slate payload is invalid")
    if _text(payload.get("official_authority")) != "ESPN":
        raise HTTPException(status_code=503, detail="NFL Game Totals official slate authority mismatch")
    if _text(payload.get("requested_date")) != requested_date:
        raise HTTPException(status_code=503, detail="NFL Game Totals official slate date mismatch")
    games = payload.get("games")
    if not isinstance(games, list):
        raise HTTPException(status_code=503, detail="NFL Game Totals official slate games payload is invalid")

    matches = [game for game in games if isinstance(game, Mapping) and _text(game.get("official_event_id")) == event_id]
    if not matches:
        raise HTTPException(status_code=404, detail="official ESPN NFL event was not found on the requested slate")
    if len(matches) != 1:
        raise HTTPException(status_code=503, detail="official ESPN NFL event identity is duplicated")

    game = dict(matches[0])
    away = game.get("away") if isinstance(game.get("away"), Mapping) else {}
    home = game.get("home") if isinstance(game.get("home"), Mapping) else {}
    status = game.get("status") if isinstance(game.get("status"), Mapping) else {}
    identity = game.get("identity_policy") if isinstance(game.get("identity_policy"), Mapping) else {}
    away_id = _text(away.get("team_id"))
    home_id = _text(home.get("team_id"))

    if (
        not away_id.isdigit()
        or not home_id.isdigit()
        or away_id == home_id
        or not _text(away.get("abbr"))
        or not _text(home.get("abbr"))
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Game Totals exact event identity failed closed")
    if status.get("pregame") is not True or status.get("completed") is not False:
        raise HTTPException(status_code=409, detail="NFL Game Totals analysis is available for pregame events only")
    return game


def _fanduel_threshold(payload: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise HTTPException(status_code=503, detail="NFL Game Totals market payload is invalid")
    if _text(payload.get("official_event_id")) != event_id:
        raise HTTPException(status_code=503, detail="NFL Game Totals market event identity mismatch")
    if payload.get("ready") is not True or payload.get("market_available") is not True:
        raise HTTPException(status_code=503, detail="NFL Game Totals market is not ready")

    semantics = payload.get("market_semantics") if isinstance(payload.get("market_semantics"), Mapping) else {}
    if (
        semantics.get("projection_weight") != 0.0
        or semantics.get("market_context_only") is not True
        or semantics.get("may_modify_projection") is not False
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Game Totals market safety contract failed closed")

    books = payload.get("books")
    if not isinstance(books, list):
        raise HTTPException(status_code=503, detail="NFL Game Totals market books payload is invalid")
    fanduel = [
        row
        for row in books
        if isinstance(row, Mapping) and _text(row.get("sportsbook")).casefold() == "fanduel"
    ]
    if len(fanduel) != 1:
        raise HTTPException(status_code=503, detail="exactly one active FanDuel Game Total is required")

    row = fanduel[0]
    try:
        total = float(row.get("total"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="FanDuel Game Total is invalid") from exc
    if total <= 0.0:
        raise HTTPException(status_code=503, detail="FanDuel Game Total is invalid")

    return {
        "sportsbook": "FanDuel",
        "provider": _text(row.get("provider")),
        "provider_event_id": _text(row.get("provider_event_id")),
        "market_id": _text(row.get("market_id")),
        "total": total,
        "over_price": row.get("over_price"),
        "under_price": row.get("under_price"),
        "updated_at_utc": _text(row.get("updated_at_utc")),
        "line_status": _text(row.get("line_status")),
        "role": "evaluation_threshold_only",
        "projection_weight": 0.0,
        "distribution_weight": 0.0,
    }


def _run_analysis(requested_date: str, event_id: str) -> dict[str, Any]:
    try:
        slate = collect_official_nfl_slate(requested_date)
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

    game = _verified_game_from_slate(slate, requested_date, event_id)
    away = game["away"]
    home = game["home"]

    try:
        away_profile = collect_team_scoring_profile(away, requested_date)
        home_profile = collect_team_scoring_profile(home, requested_date)
        features = build_game_totals_feature_vector(game, away_profile, home_profile)
        projection = project_game_total(features)
    except (
        NFLGameTotalsTeamProfileError,
        NFLGameTotalsFeatureError,
        NFLGameTotalsProjectionError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Game Totals football model unavailable: {str(exc)[:240]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Game Totals football model unavailable: {type(exc).__name__}",
        ) from exc

    market_payload = _collect_or_reuse_market(event_id)
    market = _fanduel_threshold(market_payload, event_id)

    try:
        probability = simulate_over_under(
            projection,
            market["total"],
            simulations=CERTIFIED_SIMULATIONS,
            batches=CERTIFIED_BATCHES,
            seed=CERTIFIED_SEED,
        )
    except NFLGameTotalsProbabilityError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Game Totals probability model unavailable: {str(exc)[:240]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFL Game Totals probability model unavailable: {type(exc).__name__}",
        ) from exc

    if (
        _text(projection.get("official_event_id")) != event_id
        or _text(probability.get("official_event_id")) != event_id
        or projection.get("sportsbook_projection_influence") != 0.0
        or probability.get("sportsbook_projection_influence") != 0.0
        or probability.get("sportsbook_distribution_influence") != 0.0
        or probability.get("market_line_role") != "evaluation_threshold_only"
    ):
        raise HTTPException(status_code=503, detail="NFL Game Totals end-to-end safety contract failed closed")

    return {
        "ready": True,
        "service": "Kyre Sports API",
        "sport": "nfl",
        "market_type": "game_total",
        "official_event_id": event_id,
        "game_date": requested_date,
        "game": deepcopy(game),
        "profiles": {
            "away": deepcopy(away_profile),
            "home": deepcopy(home_profile),
        },
        "features": deepcopy(features),
        "projection": deepcopy(projection),
        "market": market,
        "probability": deepcopy(probability),
        "safety": {
            "exact_event_identity": True,
            "football_only_projection": True,
            "sportsbook_projection_influence": 0.0,
            "sportsbook_distribution_influence": 0.0,
            "market_line_role": "evaluation_threshold_only",
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


@router.get("/status")
def game_totals_analysis_status():
    return {
        "status": "analysis_ready",
        "endpoint": "/api/v1/nfl/game-totals/analysis",
        "shared_host_attached": False,
        **CONTRACT,
    }


@router.get("")
def game_totals_analysis(
    game_date: str = Query(
        ...,
        min_length=10,
        max_length=10,
        description="NFL slate calendar date in YYYY-MM-DD format.",
    ),
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official numeric ESPN NFL event ID from the verified Game Totals slate.",
    ),
):
    requested_date = _validate_game_date(game_date)
    official_event_id = _validate_event_id(event_id)
    return _run_analysis(requested_date, official_event_id)


__all__ = [
    "CERTIFIED_BATCHES",
    "CERTIFIED_SEED",
    "CERTIFIED_SIMULATIONS",
    "CONTRACT",
    "game_totals_analysis",
    "game_totals_analysis_status",
    "router",
]
