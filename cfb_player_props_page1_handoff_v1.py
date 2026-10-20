"""CFB Player Props Page 1 V1 — exact selected-game handoff."""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, MutableMapping

ROUTE_VERSION = "cfb-player-props-v1"
SESSION_HANDOFF_KEY = "ks_cfb_player_props_page1_handoff_v1"
MARKET_ID = "player-props"


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_selected_game_handoff(
    game: Mapping[str, Any], *, slate_date: date, generation: int
) -> dict[str, Any]:
    game_id = _text(game.get("official_game_id") or game.get("game_id"))
    if not game_id:
        raise ValueError("official game id is required")
    return {
        "route_version": ROUTE_VERSION,
        "slate_date": slate_date.isoformat(),
        "official_game_id": game_id,
        "away_team_id": _text(game.get("away_team_id")),
        "away_team": _text(game.get("away_team")),
        "home_team_id": _text(game.get("home_team_id")),
        "home_team": _text(game.get("home_team")),
        "kickoff_iso": _text(game.get("kickoff_iso")),
        "market_id": MARKET_ID,
        "generation": int(generation),
    }


def _pop(mapping: MutableMapping[str, Any], key: str) -> None:
    try:
        mapping.pop(key, None)
    except TypeError:
        try:
            del mapping[key]
        except Exception:
            pass


def commit_selected_game_handoff(
    session: MutableMapping[str, Any],
    query: MutableMapping[str, Any],
    handoff: Mapping[str, Any],
) -> None:
    candidate = dict(handoff)
    current = session.get(SESSION_HANDOFF_KEY)
    if isinstance(current, Mapping):
        if int(current.get("generation") or 0) > int(candidate.get("generation") or 0):
            return
    session[SESSION_HANDOFF_KEY] = candidate
    session["date"] = _text(candidate.get("slate_date"))
    session["game_id"] = _text(candidate.get("official_game_id"))
    _pop(session, "player_id")
    query["sport"] = "cfb"
    query["market"] = MARKET_ID
    query["date"] = _text(candidate.get("slate_date"))
    query["game_id"] = _text(candidate.get("official_game_id"))
    _pop(query, "player_id")


__all__ = [
    "MARKET_ID",
    "ROUTE_VERSION",
    "SESSION_HANDOFF_KEY",
    "build_selected_game_handoff",
    "commit_selected_game_handoff",
]
