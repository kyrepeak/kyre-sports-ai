"""CFB Player Props Page 3 V1 — exact player/market context and Page-2 return contract."""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import cfb_player_props_page2_context_v1 as page2_context
import cfb_player_props_page2_roster_v1 as page2_roster
from cfb_player_props_market_v1 import canonical_market_key
from cfb_player_props_page2_handoff_v1 import SESSION_HANDOFF_KEY

PAGE3_LOCAL_KEYS = (
    "cfbpp3_line",
    "cfbpp3_line_identity",
    "cfbpp3_market",
    "cfbpp3_market_tab",
)
SLIDER_KEY_PREFIX = "cfbpp3_slider_"


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


def _handoff(session: Mapping[str, Any]) -> dict[str, Any]:
    raw = session.get(SESSION_HANDOFF_KEY)
    return dict(raw) if isinstance(raw, Mapping) else {}


def resolve_page3_context(session: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
    game = page2_context.resolve_page2_context(session, query)
    if _text(game.get("state")) != "ready":
        return {**dict(game), "player": None, "market_key": None, "official_player_id": ""}

    handoff = _handoff(session)
    player_id = _pick(query, "player_id") or _pick(session, "player_id") or _text(handoff.get("official_player_id"))
    raw_market = _pick(query, "prop") or _pick(session, "prop") or _text(handoff.get("market_key"))
    market_key = canonical_market_key(raw_market)
    if not player_id or not raw_market:
        return {**dict(game), "state": "invalid", "reason": "Canonical player and prop are required.", "player": None, "market_key": None, "official_player_id": player_id}
    if market_key is None:
        return {**dict(game), "state": "invalid", "reason": "Selected prop market is unsupported.", "player": None, "market_key": None, "official_player_id": player_id}

    handoff_game = _text(handoff.get("official_game_id"))
    if handoff_game and handoff_game != _text(game.get("official_game_id")):
        return {**dict(game), "state": "invalid", "reason": "Selected game conflicts with the Page-2 handoff.", "player": None, "market_key": None, "official_player_id": player_id}
    handoff_player = _text(handoff.get("official_player_id"))
    if handoff_player and handoff_player != player_id:
        return {**dict(game), "state": "invalid", "reason": "Selected player conflicts with the Page-2 handoff.", "player": None, "market_key": None, "official_player_id": player_id}

    rosters = page2_roster.load_offensive_roster(game)
    players = list(rosters.get("away") or []) + list(rosters.get("home") or [])
    matches = [player for player in players if _text(getattr(player, "official_player_id", "")) == player_id]
    if len(matches) != 1:
        return {**dict(game), "state": "player_unavailable", "reason": "Selected player is unavailable for this game.", "player": None, "market_key": market_key, "official_player_id": player_id}

    player = matches[0]
    handoff_market = canonical_market_key(handoff.get("market_key"))
    handoff_line = handoff.get("consensus_line") if handoff_market == market_key else None
    try:
        handoff_line = float(handoff_line) if handoff_line is not None else None
    except (TypeError, ValueError):
        handoff_line = None
    return {
        **dict(game),
        "state": "ready",
        "official_player_id": player_id,
        "player": player,
        "market_key": market_key,
        "handoff_line": handoff_line,
        "page2_handoff": handoff,
    }


def _clear_mapping_local(mapping: MutableMapping[str, Any]) -> None:
    keys=list(PAGE3_LOCAL_KEYS)
    try:
        keys.extend(str(key) for key in list(mapping.keys()) if str(key).startswith(SLIDER_KEY_PREFIX))
    except Exception:
        pass
    for key in dict.fromkeys(keys):
        _remove(mapping,key)


def _clear_local(session: MutableMapping[str, Any], query: MutableMapping[str, Any]) -> None:
    _clear_mapping_local(session)
    _clear_mapping_local(query)


def clear_page3_selection(session: MutableMapping[str, Any], query: MutableMapping[str, Any]) -> None:
    for key in ("player_id", "prop", "market_key"):
        _remove(session, key)
        _remove(query, key)
    _clear_local(session, query)
    try:
        session["sport"] = "cfb"; session["market"] = "player-props"
    except Exception:
        pass
    try:
        query["sport"] = "cfb"; query["market"] = "player-props"
    except Exception:
        pass


def switch_page3_market(session: MutableMapping[str, Any], query: MutableMapping[str, Any], market_key: str) -> bool:
    canonical = canonical_market_key(market_key)
    if canonical is None or not (_pick(query, "game_id") or _pick(session, "game_id")) or not (_pick(query, "player_id") or _pick(session, "player_id")):
        return False
    session["prop"] = canonical
    query["prop"] = canonical
    _remove(session, "market_key"); _remove(query, "market_key")
    _clear_local(session, query)
    raw = session.get(SESSION_HANDOFF_KEY)
    if isinstance(raw, Mapping):
        handoff = dict(raw)
        if _text(handoff.get("official_player_id")) in {"", _pick(session, "player_id")} and _text(handoff.get("official_game_id")) in {"", _pick(session, "game_id")}:
            handoff["market_key"] = canonical
            handoff["consensus_line"] = None
            session[SESSION_HANDOFF_KEY] = handoff
    return True


__all__ = ["PAGE3_LOCAL_KEYS", "SLIDER_KEY_PREFIX", "clear_page3_selection", "resolve_page3_context", "switch_page3_market"]