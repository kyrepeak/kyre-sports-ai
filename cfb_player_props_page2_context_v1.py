"""CFB Player Props Page 2 V1 — exact selected-game context and Back contract."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, MutableMapping
from zoneinfo import ZoneInfo

import cfb_schedule_v4
from cfb_player_props_page1_handoff_v1 import SESSION_HANDOFF_KEY

PHOENIX = ZoneInfo("America/Phoenix")
PAGE2_HANDOFF_KEY = "ks_cfb_player_props_page2_handoff_v1"
PAGE2_FILTER_KEYS = ("cfbpp2_position", "cfbpp2_team", "cfbpp2_market")
_SELECTION_KEYS = ("game_id", "player_id", "prop", "market_key")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _pick(mapping: Mapping[str, Any], key: str) -> str:
    try:
        return _text(mapping.get(key))
    except Exception:
        return ""


def _remove(mapping: MutableMapping[str, Any], key: str) -> None:
    try:
        mapping.pop(key, None)
    except Exception:
        try:
            del mapping[key]
        except Exception:
            pass


def _phoenix_kickoff(game: Mapping[str, Any]) -> str:
    existing = _text(game.get("kickoff_phoenix"))
    if existing:
        return existing
    raw = _text(game.get("kickoff_iso"))
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return ""
        local = parsed.astimezone(PHOENIX)
        return local.strftime("%I:%M %p MST").lstrip("0")
    except Exception:
        return ""


def _canonical_game_id(game: Mapping[str, Any]) -> str:
    # Only the official schedule identity is canonical. Provider event aliases
    # such as espn_event_id are intentionally excluded.
    return _text(game.get("official_game_id") or game.get("game_id"))


def _compatible_team_id(game: Mapping[str, Any], side: str, expected: str) -> bool:
    if not expected:
        return True
    candidates = {
        _text(game.get(f"{side}_team_id")),
        _text(game.get(f"{side}_espn_team_id")),
    }
    candidates.discard("")
    return expected in candidates


def resolve_page2_context(
    session: Mapping[str, Any],
    query: Mapping[str, Any],
    *,
    schedule_reader: Callable[[Any], list[dict[str, Any]]] = cfb_schedule_v4.games_for_date,
) -> dict[str, Any]:
    handoff = session.get(SESSION_HANDOFF_KEY)
    handoff = dict(handoff) if isinstance(handoff, Mapping) else {}

    slate_date = _pick(query, "date") or _pick(session, "date") or _text(handoff.get("slate_date"))
    game_id = _pick(query, "game_id") or _pick(session, "game_id") or _text(handoff.get("official_game_id"))
    if not slate_date or not game_id:
        return {
            "state": "invalid",
            "reason": "Canonical date and official game ID are required.",
            "slate_date": slate_date,
        }

    handoff_game_id = _text(handoff.get("official_game_id"))
    if handoff_game_id and handoff_game_id != game_id:
        return {
            "state": "invalid",
            "reason": "Selected game does not match the Page-1 handoff.",
            "slate_date": slate_date,
        }

    try:
        games = list(schedule_reader(slate_date) or [])
    except Exception:
        games = []
    matches = [dict(game) for game in games if _canonical_game_id(game) == game_id]
    if len(matches) != 1:
        return {
            "state": "unavailable",
            "reason": "Selected game is unavailable. Return to Player Props.",
            "slate_date": slate_date,
        }

    game = matches[0]
    away_expected = _text(handoff.get("away_team_id"))
    home_expected = _text(handoff.get("home_team_id"))
    if not _compatible_team_id(game, "away", away_expected) or not _compatible_team_id(game, "home", home_expected):
        return {
            "state": "invalid",
            "reason": "Selected game team identity conflicts with the Page-1 handoff.",
            "slate_date": slate_date,
        }

    return {
        "state": "ready",
        "slate_date": slate_date,
        "official_game_id": game_id,
        "away_team_id": _text(game.get("away_team_id") or game.get("away_espn_team_id")),
        "away_team": _text(game.get("away_team")),
        "away_team_slug": _text(game.get("away_team_slug")),
        "away_abbr": _text(game.get("away_abbr")),
        "away_record": _text(game.get("away_record_summary") or game.get("away_record")),
        "away_rank": game.get("away_rank"),
        "home_team_id": _text(game.get("home_team_id") or game.get("home_espn_team_id")),
        "home_team": _text(game.get("home_team")),
        "home_team_slug": _text(game.get("home_team_slug")),
        "home_abbr": _text(game.get("home_abbr")),
        "home_record": _text(game.get("home_record_summary") or game.get("home_record")),
        "home_rank": game.get("home_rank"),
        "kickoff_iso": _text(game.get("kickoff_iso")),
        "kickoff_phoenix": _phoenix_kickoff(game),
        "status": _text(game.get("status")),
        "venue": _text(game.get("venue")),
        "broadcast": _text(game.get("broadcast")),
        "neutral_site": game.get("neutral_site") is True,
        "week": int(game.get("espn_week") or game.get("week") or 0),
        "generation": int(handoff.get("generation") or 0),
        "game": game,
    }


def clear_page2_selection(
    session: MutableMapping[str, Any],
    query: MutableMapping[str, Any],
) -> None:
    for key in _SELECTION_KEYS:
        _remove(session, key)
        _remove(query, key)
    for key in PAGE2_FILTER_KEYS:
        _remove(session, key)
        _remove(query, key)
    _remove(session, PAGE2_HANDOFF_KEY)
    _remove(query, PAGE2_HANDOFF_KEY)

    # Keep the user inside CFB → Player Props on the same valid slate date.
    try:
        session["sport"] = "cfb"
        session["market"] = "player-props"
    except Exception:
        pass
    try:
        query["sport"] = "cfb"
        query["market"] = "player-props"
    except Exception:
        pass


__all__ = [
    "PAGE2_FILTER_KEYS",
    "PAGE2_HANDOFF_KEY",
    "clear_page2_selection",
    "resolve_page2_context",
]
