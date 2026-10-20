"""CFB Player Props Page 2 V1 — canonical future Page-3 selection handoff."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping

from cfb_player_props_market_v1 import PropObservation
from cfb_player_props_page2_roster_v1 import Page2Player

ROUTE_VERSION = "cfb-player-props-page2-v1"
SESSION_HANDOFF_KEY = "ks_cfb_player_props_page2_handoff_v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _line(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _provenance(market: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = market.get("observations")
    out: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, (list, tuple)) else ():
        if not isinstance(row, PropObservation):
            continue
        out.append({
            "provider": row.provider,
            "sportsbook": row.sportsbook,
            "provider_event_id": row.provider_event_id,
            "provider_player_id": row.provider_player_id,
            "provider_market_id": row.provider_market_id,
            "side": row.side,
            "line": float(row.line),
            "price": row.price,
            "observed_at_utc": row.observed_at_utc,
        })
    out.sort(key=lambda item: (
        _text(item.get("sportsbook")).casefold(),
        _text(item.get("side")),
        _text(item.get("observed_at_utc")),
    ))
    return out


def build_selected_prop_handoff(
    context: Mapping[str, Any],
    player: Page2Player,
    market: Mapping[str, Any],
    *,
    generation: int,
) -> dict[str, Any]:
    return {
        "route_version": ROUTE_VERSION,
        "slate_date": _text(context.get("slate_date") or context.get("game_date")),
        "official_game_id": _text(context.get("official_game_id")),
        "away_team_id": _text(context.get("away_team_id")),
        "home_team_id": _text(context.get("home_team_id")),
        "official_player_id": player.official_player_id,
        "player_name": player.canonical_name,
        "official_team_id": player.official_team_id,
        "market_key": _text(market.get("market_key")),
        "consensus_line": _line(market.get("consensus_line")),
        "generation": int(generation),
        "selected_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selection_state": "selected",
        "provenance": _provenance(market),
    }


def _remove(mapping: MutableMapping[str, Any], key: str) -> None:
    try:
        mapping.pop(key, None)
    except Exception:
        try:
            del mapping[key]
        except Exception:
            pass


def commit_selected_prop_handoff(
    session: MutableMapping[str, Any],
    query: MutableMapping[str, Any],
    payload: Mapping[str, Any],
) -> None:
    candidate = dict(payload)
    if _text(candidate.get("route_version")) != ROUTE_VERSION:
        return
    if not all(_text(candidate.get(key)) for key in (
        "slate_date", "official_game_id", "official_player_id", "official_team_id", "market_key"
    )):
        return
    try:
        generation = int(candidate.get("generation") or 0)
    except (TypeError, ValueError):
        return
    current = session.get(SESSION_HANDOFF_KEY)
    if isinstance(current, Mapping):
        try:
            current_generation = int(current.get("generation") or 0)
        except (TypeError, ValueError):
            current_generation = 0
        if current_generation > generation:
            return

    session[SESSION_HANDOFF_KEY] = candidate
    session["sport"] = "cfb"
    session["market"] = "player-props"
    session["date"] = _text(candidate.get("slate_date"))
    session["game_id"] = _text(candidate.get("official_game_id"))
    session["player_id"] = _text(candidate.get("official_player_id"))
    session["prop"] = _text(candidate.get("market_key"))

    query["sport"] = "cfb"
    query["market"] = "player-props"
    query["date"] = _text(candidate.get("slate_date"))
    query["game_id"] = _text(candidate.get("official_game_id"))
    query["player_id"] = _text(candidate.get("official_player_id"))
    query["prop"] = _text(candidate.get("market_key"))
    _remove(query, "provider_event_id")
    _remove(query, "provider_player_id")
    _remove(query, "provider_market_id")


__all__ = [
    "ROUTE_VERSION", "SESSION_HANDOFF_KEY",
    "build_selected_prop_handoff", "commit_selected_prop_handoff",
]
