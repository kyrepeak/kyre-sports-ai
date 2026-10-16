"""NBA Spread Step 8 — Kyre Sports Preview / Live-Final behavior.

This module owns state-transition history only. It captures descriptive pregame
context while a verified matchup is UPCOMING/DELAYED, freezes that exact
snapshot when the game becomes LIVE, and preserves it through FINAL. It never
reconstructs a pregame snapshot from live/final data and never changes model,
projection, probability, edge, ranking, or sportsbook influence.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

MODEL_VERSION = "NBA_SPREAD_STEP8_LIVE_FINAL_BEHAVIOR_V1"
PREVIEW_STATE_KEY = "nba_spread_step8_preview_history_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
NETWORK_CALLS_ADDED = 0

_PREGAME = {"UPCOMING", "DELAYED"}
_TERMINAL = {"FINAL", "CANCELLED"}
_ORDER = {"UPCOMING": 0, "DELAYED": 0, "LIVE": 1, "FINAL": 2, "CANCELLED": 2}


def _status(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text in _ORDER else "UPCOMING"


def _phase(status: str) -> str:
    if status in _PREGAME:
        return "PREGAME"
    if status == "LIVE":
        return "LIVE"
    return "FINAL" if status in _TERMINAL else "PREGAME"


def _clean_game(game: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(game))
    out.pop("step8_preview", None)
    return out


def _snapshot(game: Mapping[str, Any], context: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "game": _clean_game(game),
        "context": deepcopy(dict(context or {})),
        "captured_status": _status(game.get("status")),
    }


def _missing_record(game: Mapping[str, Any], status: str) -> dict[str, Any]:
    return {
        "game_key": str(game.get("game_key") or "").strip(),
        "verification": "UNAVAILABLE",
        "diagnostic_state": "PREGAME_SNAPSHOT_MISSING",
        "phase": _phase(status),
        "current_status": status,
        "snapshot_frozen": False,
        "pregame_snapshot": None,
        "state_history": [status],
    }


def _new_pregame_record(
    game: Mapping[str, Any],
    status: str,
    context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "game_key": str(game.get("game_key") or "").strip(),
        "verification": "VERIFIED",
        "diagnostic_state": "PREGAME_CAPTURED",
        "phase": "PREGAME",
        "current_status": status,
        "snapshot_frozen": False,
        "pregame_snapshot": _snapshot(game, context),
        "state_history": [status],
    }


def _advance_record(
    previous: Mapping[str, Any],
    game: Mapping[str, Any],
    status: str,
    context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    record = deepcopy(dict(previous))
    prior_status = _status(record.get("current_status"))
    prior_order = _ORDER[prior_status]
    next_order = _ORDER[status]

    if next_order < prior_order:
        record["diagnostic_state"] = "STALE_STATE_IGNORED"
        return record

    history = list(record.get("state_history") or [])
    if not history:
        history = [prior_status]
    if status != prior_status and status not in history:
        history.append(status)
    record["state_history"] = history

    if record.get("pregame_snapshot") is None:
        record["verification"] = "UNAVAILABLE"
        record["diagnostic_state"] = "PREGAME_SNAPSHOT_MISSING"
        record["phase"] = _phase(status)
        record["current_status"] = status
        record["snapshot_frozen"] = False
        return record

    if next_order == 0 and record.get("snapshot_frozen") is not True:
        record["pregame_snapshot"] = _snapshot(game, context)
        record["phase"] = "PREGAME"
        record["current_status"] = status
        record["verification"] = "VERIFIED"
        record["diagnostic_state"] = "PREGAME_REFRESHED"
        return record

    record["current_status"] = status
    record["phase"] = _phase(status)
    record["snapshot_frozen"] = True
    record["verification"] = "VERIFIED"
    record["diagnostic_state"] = (
        "PREGAME_SNAPSHOT_FROZEN_LIVE" if status == "LIVE" else "PREGAME_SNAPSHOT_RETAINED_FINAL"
    )
    return record


def reconcile_preview_history(
    games: list[dict[str, Any]],
    history: Mapping[str, Mapping[str, Any]] | None,
    *,
    context_by_game: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return decorated current games plus durable-in-session preview history.

    History is never dropped merely because a game leaves the rolling window.
    A game first observed after tip-off is recorded as unavailable rather than
    having a pregame snapshot fabricated from live/final values.
    """
    updated: dict[str, dict[str, Any]] = {
        str(key): deepcopy(dict(value))
        for key, value in dict(history or {}).items()
        if str(key).strip() and isinstance(value, Mapping)
    }
    contexts = dict(context_by_game or {})
    decorated: list[dict[str, Any]] = []

    for raw_game in games:
        game = _clean_game(raw_game)
        key = str(game.get("game_key") or "").strip()
        status = _status(game.get("status"))

        if not key:
            preview = {
                "verification": "UNAVAILABLE",
                "diagnostic_state": "GAME_IDENTITY_MISSING",
                "phase": _phase(status),
                "current_status": status,
                "snapshot_frozen": False,
                "pregame_snapshot": None,
                "state_history": [status],
            }
        else:
            context = contexts.get(key)
            previous = updated.get(key)
            if previous is None:
                record = (
                    _new_pregame_record(game, status, context)
                    if status in _PREGAME
                    else _missing_record(game, status)
                )
            else:
                record = _advance_record(previous, game, status, context)
            updated[key] = record
            preview = deepcopy(record)

        game["step8_preview"] = preview
        decorated.append(game)

    return {
        "version": MODEL_VERSION,
        "verification": "VERIFIED",
        "games": decorated,
        "history": updated,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "MODEL_VERSION",
    "PREVIEW_STATE_KEY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "NETWORK_CALLS_ADDED",
    "reconcile_preview_history",
]
