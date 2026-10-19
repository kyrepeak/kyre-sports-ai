"""Minimal exact-identity consumer seam for NBA Spread selected-game analysis.

This module does not compute or alter model outputs. It only resolves the exact
Page-1 handoff identity and exposes already-certified Step-9/Step-10 records to
an additive selected-game presentation layer.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

MODEL_VERSION = "NBA_SPREAD_SELECTED_GAME_CONSUMER_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False


def _clean(value: object) -> str:
    return str(value or "").strip()


def resolve_selected_game(
    games: Sequence[Mapping[str, Any]],
    *,
    date: object,
    game_id: object,
) -> dict[str, Any]:
    exact_id = _clean(game_id)
    exact_date = _clean(date)
    if not exact_id:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SELECTED_GAME_ID_MISSING",
            "game": None,
        }
    if not exact_date:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SELECTED_GAME_DATE_MISSING",
            "game": None,
        }

    by_id = [dict(game) for game in games if _clean(game.get("game_key")) == exact_id]
    if not by_id:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SELECTED_GAME_NOT_FOUND",
            "game": None,
        }
    if len(by_id) != 1:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SELECTED_GAME_IDENTITY_AMBIGUOUS",
            "game": None,
        }

    game = by_id[0]
    if _clean(game.get("game_date_phoenix")) != exact_date:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SELECTED_GAME_IDENTITY_MISMATCH",
            "game": None,
        }
    if not _clean(game.get("away_tricode")) or not _clean(game.get("home_tricode")):
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SELECTED_GAME_TEAM_IDENTITY_MISSING",
            "game": None,
        }
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "game": game,
    }


def build_selected_game_state(
    games: Sequence[Mapping[str, Any]],
    *,
    date: object,
    game_id: object,
) -> dict[str, Any]:
    resolved = resolve_selected_game(games, date=date, game_id=game_id)
    base = {
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_model": MAY_MODIFY_MODEL,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_probability": MAY_MODIFY_PROBABILITY,
        "may_modify_ranking": MAY_MODIFY_RANKING,
    }
    if resolved.get("verification") != "VERIFIED":
        return {**resolved, **base}
    game = dict(resolved["game"])
    return {
        **base,
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "game": game,
        "fair_record": dict(game.get("step9_fair_spread") or {}),
        "decision_record": dict(game.get("step10_decision") or {}),
    }


def build_back_query(query: Mapping[str, Any]) -> dict[str, Any]:
    out = {str(key): value for key, value in dict(query).items()}
    out["sport"] = "nba"
    out["market"] = "spread"
    out.pop("game_id", None)
    out.pop("date", None)
    out.pop("player_id", None)
    return out


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_FROZEN_STEPS",
    "resolve_selected_game",
    "build_selected_game_state",
    "build_back_query",
]
