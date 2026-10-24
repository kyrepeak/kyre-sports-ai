"""Kyre Sports API CFB Game Total Page 1 selected-game decision snapshot.

Read-only adapter over the permanently frozen CFB Game Total distribution and
final synthesis. This route does not alter model math, ranking, selection, or
market ownership. Sportsbook context is used only as the comparison threshold
for the frozen distribution and has zero projection weight.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

from fastapi import APIRouter, HTTPException, Query

import cfb_game_total_slate_v1 as slate
import sports_api.api.cfb_game_total_page1_v1 as page1

router = APIRouter(prefix="/api/v1/cfb/game-total", tags=["cfb"])
MODEL_VERSION = "CFB GAME TOTAL PAGE1 DECISION V1 • FROZEN MODEL SNAPSHOT"
SCHEMA_VERSION = "cfb_game_total_page1_decision_v1"
PROBABILITY_OWNER = "frozen_cfb_game_total_distribution"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _game_id(game: Mapping[str, Any]) -> str:
    return _clean(game.get("game_id") or game.get("identity_key"))


def _market_total(game: Mapping[str, Any]) -> float | None:
    for quote in game.get("market_quotes") or []:
        if not isinstance(quote, Mapping):
            continue
        line = _num(quote.get("total_line"))
        if line is not None:
            return line
    return None


def _projected(raw: Mapping[str, Any], final: Mapping[str, Any]) -> float | None:
    if final.get("ready") is True:
        value = _num(final.get("projected_combined_total") or final.get("projected_total"))
        if value is not None:
            return value
    if raw.get("ready") is True:
        return _num(raw.get("projected_combined_total") or raw.get("projected_total"))
    return None


def _distribution_probabilities(raw: Mapping[str, Any], line: float | None) -> tuple[float | None, float | None, float | None]:
    values = raw.get("distribution")
    if line is None or raw.get("distribution_ready") is not True or not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return None, None, None
    over = under = push = 0.0
    valid = False
    for row in values:
        if not isinstance(row, Mapping):
            continue
        total = _num(row.get("total"))
        probability = _num(row.get("probability"))
        if total is None or probability is None or probability < 0:
            continue
        valid = True
        if total > line:
            over += probability
        elif total < line:
            under += probability
        else:
            push += probability
    if not valid:
        return None, None, None
    return round(over, 6), round(under, 6), round(push, 6)


def _pending_payload(game: Mapping[str, Any], selected_day: str, market_total: float | None) -> dict[str, Any]:
    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "game_id": _game_id(game),
        "selected_date": selected_day,
        "status": "MODEL_PENDING",
        "market_total": market_total,
        "projected_total": None,
        "over_probability": None,
        "under_probability": None,
        "push_probability": None,
        "model_edge": None,
        "model_tilt": "MODEL_PENDING",
        "forecast_grade": None,
        "confidence": None,
        "probability_owner": PROBABILITY_OWNER,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_INFLUENCE,
        "model_mutated": False,
        "probability_mutated": False,
        "selection_mutated": False,
    }


def build_decision_payload(*, game_date: str | None = None, game_id: str) -> dict[str, Any]:
    requested_id = _clean(game_id)
    if not requested_id:
        raise ValueError("game_id is required")

    page_payload = page1.build_page1_payload(game_date=game_date)
    selected_day = _clean(page_payload.get("selected_date"))
    games = [row for row in page_payload.get("games") or [] if isinstance(row, Mapping)]
    game = next((row for row in games if _game_id(row) == requested_id), None)
    if game is None:
        raise ValueError("game_id is not in the verified upcoming slate")

    market_total = _market_total(game)
    try:
        analysis = slate.analyze_game(game, selected_day)
    except Exception:
        return _pending_payload(game, selected_day, market_total)

    raw = analysis.get("raw") if isinstance(analysis.get("raw"), Mapping) else {}
    final = analysis.get("final") if isinstance(analysis.get("final"), Mapping) else {}
    projected = _projected(raw, final)
    over, under, push = _distribution_probabilities(raw, market_total)
    if projected is None or over is None or under is None:
        return _pending_payload(game, selected_day, market_total)

    edge = round(projected - market_total, 1) if market_total is not None else None
    if edge is None:
        tilt = "NEUTRAL"
    elif edge > 0 and over > under:
        tilt = "OVER"
    elif edge < 0 and under > over:
        tilt = "UNDER"
    else:
        tilt = "NEUTRAL"

    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "game_id": requested_id,
        "selected_date": selected_day,
        "status": "READY",
        "market_total": market_total,
        "projected_total": round(projected, 1),
        "over_probability": over,
        "under_probability": under,
        "push_probability": push,
        "model_edge": edge,
        "model_tilt": tilt,
        "forecast_grade": _clean(final.get("grade")) or None,
        "confidence": _clean(final.get("confidence") or raw.get("confidence")) or None,
        "probability_owner": PROBABILITY_OWNER,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_INFLUENCE,
        "sportsbook_input_used": bool(raw.get("sportsbook_input_used")),
        "market_probability_used": bool(raw.get("market_probability_used")),
        "model_mutated": False,
        "probability_mutated": False,
        "selection_mutated": False,
    }


@router.get("/decision")
def decision(
    game_id: str = Query(..., min_length=1, max_length=128),
    game_date: str | None = Query(None, min_length=10, max_length=10),
) -> dict[str, Any]:
    try:
        return build_decision_payload(game_date=game_date, game_id=game_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "PROBABILITY_OWNER",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_distribution_probabilities",
    "build_decision_payload",
    "decision",
    "router",
]
