"""Direct FanDuel CFB player props with exact verified-game binding.

This adapter repairs the V1 transport gap where FanDuel player rows could be
fetched but were discarded by Page 2 because provider event identity was not
bound back to the selected official game.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from sports_api.collectors.cfb_fanduel_direct import fetch_fanduel_ncaaf_page

_MARKETS = {
    "passing yards": "passing_yards",
    "pass yds": "passing_yards",
    "rushing yards": "rushing_yards",
    "rush yds": "rushing_yards",
    "receiving yards": "receiving_yards",
    "receiving yds": "receiving_yards",
    "receptions": "receiving_receptions",
    "passing touchdowns": "passing_touchdowns",
    "pass tds": "passing_touchdowns",
    "anytime touchdown scorer": "touchdowns",
    "player to score a touchdown": "touchdowns",
    "anytime td": "touchdowns",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _text(value).casefold()))


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


def _market_key(value: Any) -> str | None:
    text = _norm(value)
    for needle, key in _MARKETS.items():
        if _norm(needle) in text:
            return key
    return None


def _parse_matchup(value: Any) -> tuple[str, str] | None:
    text = _text(value)
    parts = re.split(r"\s+@\s+|\s+at\s+|\s+vs\.?\s+", text, maxsplit=1, flags=re.I)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        return None
    return parts[0].strip(), parts[1].strip()


def _aware(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _same_team(left: Any, right: Any) -> bool:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return False
    return a == b or (len(a) >= 4 and len(b) >= 4 and (a in b or b in a))


def _match_verified_game(event: Mapping[str, Any], games: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    matchup = _parse_matchup(event.get("name") or event.get("eventName") or event.get("displayName"))
    if matchup is None:
        return None
    event_away, event_home = matchup
    event_start = _aware(event.get("openDate") or event.get("startTime") or event.get("date"))
    matches: list[Mapping[str, Any]] = []
    for game in games:
        away = game.get("away_team") or game.get("awayTeam")
        home = game.get("home_team") or game.get("homeTeam")
        if not (_same_team(event_away, away) and _same_team(event_home, home)):
            continue
        verified_start = _aware(game.get("kickoff_iso") or game.get("start_time_utc") or game.get("date"))
        if event_start is not None and verified_start is not None:
            if abs((event_start - verified_start).total_seconds()) > 45 * 60:
                continue
        matches.append(game)
    return matches[0] if len(matches) == 1 else None


def _price(value: Any) -> int | None:
    if isinstance(value, Mapping):
        value = value.get("americanDisplayOdds") or value.get("americanOdds") or value.get("price")
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def fetch_fanduel_cfb_player_props(slate_games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    payload = _fetch_payload()
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    events = _rows(attachments.get("events"))
    event_map = {
        _text(event.get("eventId") or event.get("id") or event.get("_attachment_key")): event
        for event in events
        if _text(event.get("eventId") or event.get("id") or event.get("_attachment_key"))
    }
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    out: list[dict[str, Any]] = []
    for market in _rows(attachments.get("markets")):
        stat = _market_key(market.get("marketName") or market.get("name") or market.get("displayName"))
        if stat is None or market.get("inPlay") is True:
            continue
        status = _text(market.get("marketStatus") or market.get("status")).upper()
        if status not in {"", "OPEN"}:
            continue
        event_id = _text(market.get("eventId") or market.get("eventID") or market.get("event_id"))
        event = event_map.get(event_id)
        if event is None:
            continue
        game = _match_verified_game(event, slate_games)
        if game is None:
            continue
        official_game_id = _text(game.get("official_game_id") or game.get("event_id") or game.get("game_id"))
        if not official_game_id:
            continue
        matchup = _parse_matchup(event.get("name") or event.get("eventName") or event.get("displayName"))
        event_start = _text(event.get("openDate") or event.get("startTime") or event.get("date") or game.get("kickoff_iso"))
        for runner in _rows(market.get("runners")):
            if _text(runner.get("runnerStatus")).upper() not in {"", "ACTIVE"}:
                continue
            result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
            side = _text(result.get("type") or runner.get("side")).lower()
            if side not in {"over", "under"}:
                continue
            try:
                line = float(runner.get("handicap"))
            except (TypeError, ValueError):
                continue
            name = _text(runner.get("runnerName") or runner.get("name") or runner.get("participantName"))
            if not name:
                continue
            price = _price(runner.get("winRunnerOdds") or runner.get("americanOdds") or runner.get("odds"))
            out.append({
                "provider": "FanDuel",
                "provider_event_id": event_id,
                "provider_player_id": _text(runner.get("participantId") or runner.get("playerId") or runner.get("playerID")),
                "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
                "official_game_id": official_game_id,
                "player_name": name,
                "stat_id": stat,
                "sportsbook": "FanDuel",
                "side": side,
                "line": line,
                "price": price,
                "observed_at_utc": now,
                "away_team": _text(game.get("away_team") or (matchup[0] if matchup else "")),
                "home_team": _text(game.get("home_team") or (matchup[1] if matchup else "")),
                "event_start": event_start,
            })
    return out


__all__ = ["fetch_fanduel_cfb_player_props"]
