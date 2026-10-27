"""MONSTER WNBA PRA upcoming-games-only market gate R1.

This successor keeps Kyre Sports API as the only application-facing gateway and
filters the certified WNBA schedule before sportsbook offers are matched. A game
is ineligible once its certified status is live/final or its certified tip time
has passed, even if a provider still exposes stale pregame props.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import wnba_pra_api_market_bridge_v1 as previous

MODEL_VERSION = "MONSTER WNBA PRA UPCOMING ONLY R1"
EASTERN = ZoneInfo("America/New_York")

_BLOCKED_STATUS = frozenset({
    "in_progress", "in progress", "live", "halftime", "final", "completed",
    "complete", "postponed", "cancelled", "canceled", "suspended",
})
_PREGAME_STATUS = frozenset({
    "scheduled", "pregame", "pre_game", "pre-game", "not_started", "not started",
})
_ORIGINAL_BUILD_SNAPSHOT = previous._build_snapshot


def _current_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _status_category(game: Mapping[str, Any]) -> str:
    raw = game.get("status") if isinstance(game.get("status"), Mapping) else {}
    value = raw.get("category") if isinstance(raw, Mapping) else None
    if not value:
        value = game.get("status_category") or game.get("game_status")
    return str(value or "").strip().casefold()


def _game_start_utc(game: Mapping[str, Any]) -> datetime | None:
    for key in (
        "game_datetime_eastern",
        "game_datetime_utc",
        "game_datetime",
        "start_time_utc",
        "commence_time",
    ):
        text = str(game.get(key) or "").strip()
        if not text:
            continue
        try:
            stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=EASTERN if key == "game_datetime_eastern" else timezone.utc)
        return stamp.astimezone(timezone.utc)
    return None


def _is_upcoming_game(game: Mapping[str, Any], *, now: datetime | None = None) -> bool:
    category = _status_category(game)
    if category in _BLOCKED_STATUS:
        return False

    start = _game_start_utc(game)
    if start is not None and start <= _current_utc(now):
        return False

    if category in _PREGAME_STATUS:
        return True

    # Unknown status fails closed unless a certified future tip time proves the
    # game has not started yet.
    return start is not None and start > _current_utc(now)


def _pregame_schedule(schedule_payload: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    out = dict(schedule_payload)
    raw_games = schedule_payload.get("games")
    games = [dict(game) for game in raw_games if isinstance(game, Mapping)] if isinstance(raw_games, list) else []
    eligible = [game for game in games if _is_upcoming_game(game, now=now)]
    out["games"] = eligible
    out["pregame_gate"] = {
        "authority": "MONSTER_ONLY",
        "rule": "UPCOMING_GAMES_ONLY",
        "games_received": len(games),
        "games_eligible": len(eligible),
        "games_removed": len(games) - len(eligible),
    }
    return out


def _build_snapshot(
    day: Any,
    schedule_payload: Mapping[str, Any],
    snapshot_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    filtered_schedule = _pregame_schedule(schedule_payload, now=now)
    result = _ORIGINAL_BUILD_SNAPSHOT(day, filtered_schedule, snapshot_payload, now=now)
    gate = dict(filtered_schedule.get("pregame_gate") or {})
    result["pregame_gate"] = gate
    result["live_games_removed"] = int(gate.get("games_removed") or 0)
    return result


def install() -> dict[str, Any]:
    previous._build_snapshot = _build_snapshot
    previous.clear_cache()
    return {
        "model_version": MODEL_VERSION,
        "authority": "MONSTER_ONLY",
        "rule": "UPCOMING_GAMES_ONLY",
        "kyre_sports_api_only": True,
        "live_games_allowed": False,
        "final_games_allowed": False,
    }


__all__ = [
    "MODEL_VERSION",
    "_status_category",
    "_game_start_utc",
    "_is_upcoming_game",
    "_pregame_schedule",
    "_build_snapshot",
    "install",
]
