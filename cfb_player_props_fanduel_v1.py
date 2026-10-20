"""Read-only FanDuel CFB player-prop secondary transport; fail-soft by design."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sports_api.collectors.cfb_fanduel_direct import fetch_fanduel_ncaaf_page

_MARKETS = {
    "passing yards": "passing_yards",
    "rushing yards": "rushing_yards",
    "receiving yards": "receiving_yards",
    "receptions": "receiving_receptions",
    "passing touchdowns": "passing_touchdowns",
    "anytime touchdown scorer": "touchdowns",
    "player to score a touchdown": "touchdowns",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(v, _attachment_key=str(k)) for k, v in value.items() if isinstance(v, Mapping)]
    if isinstance(value, list):
        return [dict(v) for v in value if isinstance(v, Mapping)]
    return []


def _fetch_payload() -> dict[str, Any]:
    try:
        payload = fetch_fanduel_ncaaf_page(timeout=12.0)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _market_key(name: Any) -> str | None:
    lower = _text(name).lower()
    for needle, key in _MARKETS.items():
        if needle in lower:
            return key
    return None


def fetch_fanduel_cfb_player_props(slate_games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    payload = _fetch_payload()
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    markets = _rows(attachments.get("markets"))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    out: list[dict[str, Any]] = []
    for market in markets:
        stat = _market_key(market.get("marketName") or market.get("name") or market.get("displayName"))
        if stat is None or market.get("inPlay") is True:
            continue
        status = _text(market.get("marketStatus") or market.get("status")).upper()
        if status not in {"", "OPEN"}:
            continue
        event_id = _text(market.get("eventId") or market.get("eventID") or market.get("event_id"))
        for runner in _rows(market.get("runners")):
            side = _text(((runner.get("result") or {}).get("type") if isinstance(runner.get("result"), Mapping) else "") or runner.get("side")).lower()
            if side not in {"over", "under"}:
                continue
            player_id = _text(runner.get("participantId") or runner.get("playerId") or runner.get("playerID"))
            name = _text(runner.get("runnerName") or runner.get("name"))
            try:
                line = float(runner.get("handicap"))
            except (TypeError, ValueError):
                continue
            price = runner.get("winRunnerOdds") or runner.get("americanOdds") or runner.get("odds")
            if isinstance(price, Mapping):
                price = price.get("americanDisplayOdds") or price.get("americanOdds")
            out.append({
                "provider": "FanDuel", "provider_event_id": event_id,
                "provider_player_id": player_id, "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
                "player_name": name, "stat_id": stat, "sportsbook": "FanDuel",
                "side": side, "line": line, "price": price, "observed_at_utc": now,
            })
    return out


__all__ = ["fetch_fanduel_cfb_player_props"]
