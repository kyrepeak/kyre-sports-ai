"""FanDuel NFL Passing Yards market adapter for Kyre Sports API.

Identity comes from the caller's canonical NFLverse game context. The adapter is
read-only, never averages sportsbook lines, and never invents missing market data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import re
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FANDUEL_BASE_URL = "https://api.sportsbook.fanduel.com"
FANDUEL_FDX_BASE_URL = "https://fdx-api.sportsbook.fanduel.com/api"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
MAX_RESPONSE_BYTES = 20_000_000
DEFAULT_TIMEOUT_SECONDS = 15
KNOWN_PROP_TABS = (
    "passing-props",
    "player-passing-props",
    "player-props",
    "passing",
    "popular",
)
FANDUEL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NFL/3.0; read-only)",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": FANDUEL_REGION,
}


class FanDuelPassingYardsError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        out: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("_attachment_key", _text(key))
                out.append(row)
        return out
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _get_json(url: str, params: Mapping[str, Any] | None = None, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    request = Request(target, headers=FANDUEL_HEADERS, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            if status != 200:
                raise FanDuelPassingYardsError(f"FanDuel GET returned HTTP {status}")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except FanDuelPassingYardsError:
        raise
    except Exception as exc:
        raise FanDuelPassingYardsError(f"FanDuel read failed: {type(exc).__name__}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FanDuelPassingYardsError("FanDuel response exceeded safe size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FanDuelPassingYardsError("FanDuel response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise FanDuelPassingYardsError("FanDuel response was not an object")
    return payload


def _market_text(market: Mapping[str, Any]) -> str:
    return " ".join(
        _text(market.get(field))
        for field in ("marketType", "marketTypeCode", "type", "marketName", "name", "displayName")
        if _text(market.get(field))
    )


def _is_passing_yards_market(market: Mapping[str, Any]) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", _market_text(market).lower())
    if "alternate" in normalized or "alternative" in normalized:
        return False
    return "passing" in normalized and "yard" in normalized


def _market_open(market: Mapping[str, Any]) -> bool:
    status = _text(market.get("marketStatus") or market.get("status")).upper()
    if status and status != "OPEN":
        return False
    return market.get("inPlay") is not True


def _runner_role(runner: Mapping[str, Any]) -> str:
    result = runner.get("result") or {}
    if isinstance(result, Mapping):
        role = _text(result.get("type")).upper()
        if role in {"OVER", "UNDER"}:
            return role
    text = _text(runner.get("runnerName") or runner.get("name") or runner.get("selectionName")).upper()
    if text.startswith("OVER") or " OVER " in f" {text} ":
        return "OVER"
    if text.startswith("UNDER") or " UNDER " in f" {text} ":
        return "UNDER"
    return ""


def _line(runner: Mapping[str, Any]) -> float | None:
    try:
        value = float(runner.get("handicap"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and 0 < value <= 700 else None


def _american_odds(runner: Mapping[str, Any]) -> int | None:
    win = runner.get("winRunnerOdds") or {}
    display = win.get("americanDisplayOdds") or {} if isinstance(win, Mapping) else {}
    raw = display.get("americanOddsInt") if isinstance(display, Mapping) else None
    if raw is None and isinstance(display, Mapping):
        raw = display.get("americanOdds")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value == 0 or not value.is_integer() or abs(value) < 100:
        return None
    return int(value)


def _provider_player_maps(payload: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    raw = payload.get("playerMap") if isinstance(payload, Mapping) else None
    if not isinstance(raw, Mapping):
        return {}, {}
    players: dict[str, dict[str, Any]] = {}
    by_selection: dict[str, list[str]] = {}
    for provider_key, value in raw.items():
        if not isinstance(value, Mapping):
            continue
        key = _text(provider_key)
        if not key:
            continue
        players[key] = dict(value)
        for selection in value.get("selectionIds") or []:
            selection_id = _text(selection)
            if selection_id:
                by_selection.setdefault(selection_id, []).append(key)
    return players, by_selection


def _player_for_pair(over: Mapping[str, Any], under: Mapping[str, Any], players: Mapping[str, dict[str, Any]], by_selection: Mapping[str, list[str]]) -> dict[str, Any] | None:
    keys: list[str] = []
    for runner in (over, under):
        mapped = by_selection.get(_text(runner.get("selectionId"))) or []
        if len(mapped) != 1:
            return None
        keys.append(mapped[0])
    if len(keys) != 2 or keys[0] != keys[1]:
        return None
    player = players.get(keys[0])
    return dict(player) if isinstance(player, Mapping) else None


def parse_event_market_observations(event_page: Mapping[str, Any], fdx_players: Mapping[str, Any], *, source_timestamp: str) -> list[dict[str, Any]]:
    attachments = event_page.get("attachments") if isinstance(event_page, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    players, by_selection = _provider_player_maps(fdx_players)
    if not players or not by_selection:
        return []
    observations: list[dict[str, Any]] = []
    for market in _rows(attachments.get("markets")):
        if not _is_passing_yards_market(market) or not _market_open(market):
            continue
        active = [runner for runner in _rows(market.get("runners")) if _text(runner.get("runnerStatus")).upper() in {"", "ACTIVE"}]
        overs = [runner for runner in active if _runner_role(runner) == "OVER"]
        unders = [runner for runner in active if _runner_role(runner) == "UNDER"]
        if len(overs) != 1 or len(unders) != 1:
            continue
        over, under = overs[0], unders[0]
        over_line, under_line = _line(over), _line(under)
        over_odds, under_odds = _american_odds(over), _american_odds(under)
        if over_line is None or under_line is None or over_line != under_line or over_odds is None or under_odds is None:
            continue
        player = _player_for_pair(over, under, players, by_selection)
        if not player:
            continue
        position = _text(player.get("position")).upper()
        player_name = _text(player.get("name") or player.get("displayName") or player.get("fullName"))
        team_abbr = _text(player.get("team") or player.get("teamAbbreviation")).upper()
        if position not in {"QB", "QUARTERBACK"} or not player_name or not team_abbr:
            continue
        observations.append({
            "player_name": player_name,
            "team_abbr": team_abbr,
            "sportsbook": "FanDuel",
            "market": "Passing Yards",
            "line": over_line,
            "over_odds": over_odds,
            "under_odds": under_odds,
            "source_timestamp": _text(source_timestamp),
            "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
            "source_provider": "FanDuel direct",
        })
    return observations


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _match_event(landing: Mapping[str, Any], game: Mapping[str, Any]) -> str:
    attachments = landing.get("attachments") if isinstance(landing, Mapping) else None
    if not isinstance(attachments, Mapping):
        return ""
    expected = f"{_norm(game.get('away_name'))} @ {_norm(game.get('home_name'))}"
    matches: list[str] = []
    for event in _rows(attachments.get("events")):
        name = _text(event.get("name") or event.get("eventName") or event.get("displayName"))
        parts = [part.strip() for part in name.split(" @ ")]
        if len(parts) != 2:
            continue
        candidate = f"{_norm(parts[0])} @ {_norm(parts[1])}"
        if candidate != expected:
            continue
        event_id = _text(event.get("eventId") or event.get("id") or event.get("_attachment_key"))
        if event_id:
            matches.append(event_id)
    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else ""


def _passing_markets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    return [market for market in _rows(attachments.get("markets")) if _is_passing_yards_market(market) and _market_open(market)]


def discover_passing_tab_candidates(payload: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    def add(value: Any) -> None:
        text = _text(value)
        low = text.lower()
        if not text or len(text) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", text):
            return
        if "pass" not in low or ("prop" not in low and "yard" not in low):
            return
        if low not in seen:
            seen.add(low)
            found.append(text)
    def walk(value: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if _text(key).lower() in {"tab", "tabid", "slug", "key", "id"}:
                    add(child)
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:200]:
                walk(child, depth + 1)
    walk(payload)
    for tab in KNOWN_PROP_TABS:
        if tab.lower() not in seen:
            seen.add(tab.lower())
            found.append(tab)
    return found[:8]


def collect_fanduel_game_markets(game: Mapping[str, Any], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    if not _text(game.get("away_name")) or not _text(game.get("home_name")):
        return []
    landing = _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/content-managed-page",
        {"_ak": FANDUEL_PUBLIC_WEB_KEY, "page": "CUSTOM", "customPageId": "nfl", "timezone": "America/New_York"},
        timeout=timeout,
    )
    event_id = _match_event(landing, game)
    if not event_id:
        return []
    base_page = _get_json(f"{FANDUEL_BASE_URL}/sbapi/event-page", {"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id}, timeout=timeout)
    selected = base_page
    if not _passing_markets(selected):
        for tab in discover_passing_tab_candidates(base_page):
            try:
                candidate = _get_json(
                    f"{FANDUEL_BASE_URL}/sbapi/event-page",
                    {"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id, "tab": tab},
                    timeout=timeout,
                )
            except FanDuelPassingYardsError:
                continue
            if _passing_markets(candidate):
                selected = candidate
                break
    if not _passing_markets(selected):
        return []
    fdx = _get_json(f"{FANDUEL_FDX_BASE_URL}/v1/live/event/{event_id}/players", timeout=timeout)
    timestamp = datetime.now(timezone.utc).isoformat()
    allowed_teams = {_text(game.get("away")).upper(), _text(game.get("home")).upper()}
    return [row for row in parse_event_market_observations(selected, fdx, source_timestamp=timestamp) if row.get("team_abbr") in allowed_teams]
