"""Direct-book Rushing Yards adapter using canonical game context from Kyre Sports API."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from sports_api.collectors import nfl_fanduel_passing_yards_nflverse_v1 as base

MODEL_VERSION = "NFL RUSHING YARDS DIRECT BOOK ADAPTER V2"
MARKET_READ_TIMEOUT_SECONDS = 8
MAX_MARKET_READ_ATTEMPTS = 2
PLAYER_NAME_MATCHING = False
FUZZY_MATCHING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_STANDARD_TYPE_RE = re.compile(r"^PLAYER_X_RUSHING_YARDS(?:_(?:LOW|MEDIUM|HIGH))?$")
KNOWN_PROP_TABS = ("rushing-props", "player-rushing-props", "player-props", "rushing", "popular")
_TEAM_ALIASES = {
    "ARZ": "ARI",
    "JAC": "JAX",
    "LA": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
    "WSH": "WAS",
}
_POSITION_ALIASES = {
    "RUNNING BACK": "RB",
    "HALFBACK": "RB",
    "HALF BACK": "RB",
    "TAILBACK": "RB",
    "FULLBACK": "FB",
    "FULL BACK": "FB",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _normalize_team(value: Any) -> str:
    team = _text(value).upper()
    return _TEAM_ALIASES.get(team, team)


def _normalize_jersey(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        number = float(text)
    except (TypeError, ValueError):
        return text.upper()
    if not number.is_integer():
        return text
    return str(int(number))


def _normalize_position(value: Any) -> str:
    position = re.sub(r"\s+", " ", _text(value).upper()).strip()
    return _POSITION_ALIASES.get(position, position)


def _is_transient_read_failure(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(token in text for token in ("timeouterror", "readtimeout", "read timed out", "timed out", "timeout")) and "http " not in text


def _get_json_reliable(url: str, params: Mapping[str, Any] | None = None, *, timeout: int = MARKET_READ_TIMEOUT_SECONDS) -> Any:
    """Use a production-safe read floor and retry one transient timeout only."""
    effective_timeout = max(MARKET_READ_TIMEOUT_SECONDS, int(timeout or 0))
    last_error: Exception | None = None
    for attempt in range(MAX_MARKET_READ_ATTEMPTS):
        try:
            return base._get_json(url, params, timeout=effective_timeout)
        except base.FanDuelPassingYardsError as exc:
            last_error = exc
            if attempt + 1 >= MAX_MARKET_READ_ATTEMPTS or not _is_transient_read_failure(exc):
                raise
    if last_error is not None:
        raise last_error
    raise base.FanDuelPassingYardsError("FanDuel read failed without a provider result")


def reconcile_observation_to_roster(observation: Mapping[str, Any], roster_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Return one active exact team + jersey + position match; ambiguity fails closed."""
    team = _normalize_team(observation.get("team_abbr") or observation.get("team"))
    jersey = _normalize_jersey(observation.get("jersey_number") or observation.get("jersey") or observation.get("number"))
    position = _normalize_position(observation.get("position"))
    if not team or not jersey or position not in {"RB", "FB"}:
        return None
    matched: list[dict[str, Any]] = []
    for raw in roster_rows or []:
        if not isinstance(raw, Mapping):
            continue
        active = raw.get("active")
        if active is False or _text(raw.get("status")).upper() in {"CUT", "INACTIVE", "RES", "RET"}:
            continue
        if _normalize_team(raw.get("team_abbr") or raw.get("team")) != team:
            continue
        if _normalize_jersey(raw.get("jersey_number") or raw.get("jersey") or raw.get("number")) != jersey:
            continue
        if _normalize_position(raw.get("position")) != position:
            continue
        matched.append(dict(raw))
    return matched[0] if len(matched) == 1 else None


def _market_type(market: Mapping[str, Any]) -> str:
    return _text(market.get("marketType") or market.get("marketTypeCode") or market.get("type")).upper()


def is_standard_rushing_yards_market(market: Mapping[str, Any]) -> bool:
    market_type = _market_type(market)
    if not _STANDARD_TYPE_RE.fullmatch(market_type):
        return False
    name = _text(market.get("marketName") or market.get("name") or market.get("displayName")).lower()
    blocked = ("alt rushing", "alternate rushing", "rushing + receiving", "rushing & receiving", "most rushing", "longest rushing", "team rushing", "1st half", "first half", "quarter")
    if name and any(token in name for token in blocked):
        return False
    return not name or ("rushing" in name and ("yard" in name or "yd" in name))


def _standard_markets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    return [row for row in base._rows(attachments.get("markets")) if is_standard_rushing_yards_market(row) and base._market_open(row)]


def _discover_tabs(payload: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = _text(value)
        low = text.lower()
        if not text or len(text) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", text):
            return
        if "rush" not in low or ("prop" not in low and "yard" not in low):
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


def _identity_catalog(fdx_players: Mapping[str, Any], *, allowed_teams: set[str]) -> list[dict[str, Any]]:
    """Provider identity evidence only; player names are intentionally excluded."""
    players, _ = base._provider_player_maps(fdx_players)
    rows: list[dict[str, Any]] = []
    for provider_player_id, player in players.items():
        team_abbr = _normalize_team(player.get("team") or player.get("teamAbbreviation"))
        position = _normalize_position(player.get("position"))
        jersey_number = _normalize_jersey(player.get("jerseyNumber") or player.get("jersey") or player.get("number"))
        if team_abbr not in allowed_teams or position not in {"RB", "FB"} or not jersey_number:
            continue
        rows.append({
            "provider_player_id": _text(provider_player_id),
            "team_abbr": team_abbr,
            "position": position,
            "jersey_number": jersey_number,
            "active": True,
        })
    rows.sort(key=lambda row: (row["team_abbr"], row["position"], row["jersey_number"], row["provider_player_id"]))
    return rows


def _offered_provider_player_ids(event_page: Mapping[str, Any], fdx_players: Mapping[str, Any]) -> list[str]:
    """Return player IDs attached to open standard rushing markets before quote parsing."""
    _players, by_selection = base._provider_player_maps(fdx_players)
    found: set[str] = set()
    for market in _standard_markets(event_page):
        for runner in base._rows(market.get("runners")):
            if _text(runner.get("runnerStatus")).upper() not in {"", "ACTIVE"}:
                continue
            mapped = by_selection.get(_text(runner.get("selectionId"))) or []
            if len(mapped) == 1:
                found.add(_text(mapped[0]))
    return sorted(player_id for player_id in found if player_id)


def parse_event_market_observations(event_page: Mapping[str, Any], fdx_players: Mapping[str, Any], *, source_timestamp: str) -> list[dict[str, Any]]:
    attachments = event_page.get("attachments") if isinstance(event_page, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    players, by_selection = base._provider_player_maps(fdx_players)
    if not players or not by_selection:
        return []
    observations: list[dict[str, Any]] = []
    for market in _standard_markets(event_page):
        active = [runner for runner in base._rows(market.get("runners")) if _text(runner.get("runnerStatus")).upper() in {"", "ACTIVE"}]
        overs = [runner for runner in active if base._runner_role(runner) == "OVER"]
        unders = [runner for runner in active if base._runner_role(runner) == "UNDER"]
        if len(overs) != 1 or len(unders) != 1:
            continue
        over, under = overs[0], unders[0]
        over_line, under_line = base._line(over), base._line(under)
        over_odds, under_odds = base._american_odds(over), base._american_odds(under)
        if over_line is None or under_line is None or over_line != under_line or over_odds is None or under_odds is None:
            continue
        keys: list[str] = []
        for runner in (over, under):
            mapped = by_selection.get(_text(runner.get("selectionId"))) or []
            if len(mapped) != 1:
                keys = []
                break
            keys.append(mapped[0])
        if len(keys) != 2 or keys[0] != keys[1]:
            continue
        provider_player_id = keys[0]
        player = players.get(provider_player_id) or {}
        position = _normalize_position(player.get("position"))
        player_name = _text(player.get("name") or player.get("displayName") or player.get("fullName"))
        team_abbr = _normalize_team(player.get("team") or player.get("teamAbbreviation"))
        jersey_number = _normalize_jersey(player.get("jerseyNumber") or player.get("jersey") or player.get("number"))
        if position not in {"RB", "FB"} or not player_name or not team_abbr or not jersey_number:
            continue
        observations.append({
            "provider_player_id": provider_player_id,
            "player_name": player_name,
            "position": position,
            "team_abbr": team_abbr,
            "jersey_number": jersey_number,
            "sportsbook": "FanDuel",
            "market": "Rushing Yards",
            "line": over_line,
            "over_odds": over_odds,
            "under_odds": under_odds,
            "source_timestamp": _text(source_timestamp),
            "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
            "source_provider": "FanDuel direct",
            "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        })
    return observations


def collect_fanduel_game_market_bundle(game: Mapping[str, Any], *, timeout: int = MARKET_READ_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Collect observations plus exact identity/market-membership evidence for one game."""
    if not _text(game.get("away_name")) or not _text(game.get("home_name")):
        return {"state": "EVENT_MAPPING_FAILURE", "observations": [], "reason": "canonical game names unavailable", "evidence": {}}

    landing = _get_json_reliable(
        f"{base.FANDUEL_BASE_URL}/sbapi/content-managed-page",
        {"_ak": base.FANDUEL_PUBLIC_WEB_KEY, "page": "CUSTOM", "customPageId": "nfl", "timezone": "America/New_York"},
        timeout=timeout,
    )
    event_id = base._match_event(landing, game)
    if not event_id:
        return {"state": "EVENT_MAPPING_FAILURE", "observations": [], "reason": "exact FanDuel event match unavailable", "evidence": {"event_match": "failed"}}

    selected = _get_json_reliable(
        f"{base.FANDUEL_BASE_URL}/sbapi/event-page",
        {"_ak": base.FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id},
        timeout=timeout,
    )
    if not _standard_markets(selected):
        for tab in _discover_tabs(selected):
            try:
                candidate = _get_json_reliable(
                    f"{base.FANDUEL_BASE_URL}/sbapi/event-page",
                    {"_ak": base.FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id, "tab": tab},
                    timeout=timeout,
                )
            except base.FanDuelPassingYardsError:
                continue
            if _standard_markets(candidate):
                selected = candidate
                break

    fdx = _get_json_reliable(f"{base.FANDUEL_FDX_BASE_URL}/v1/live/event/{event_id}/players", timeout=timeout)
    allowed_teams = {_normalize_team(game.get("away")), _normalize_team(game.get("home"))}
    identity_catalog = _identity_catalog(fdx, allowed_teams=allowed_teams)
    offered_provider_player_ids = _offered_provider_player_ids(selected, fdx)
    standard_markets = _standard_markets(selected)
    timestamp = datetime.now(timezone.utc).isoformat()
    observations = [
        row
        for row in parse_event_market_observations(selected, fdx, source_timestamp=timestamp)
        if _normalize_team(row.get("team_abbr")) in allowed_teams
    ]
    evidence = {
        "provider_event_id": event_id,
        "event_match": "exact_home_away",
        "identity_catalog": identity_catalog,
        "offered_provider_player_ids": offered_provider_player_ids,
        "standard_market_count": len(standard_markets),
        "player_name_matching": False,
        "fuzzy_matching": False,
    }
    if observations:
        return {"state": "AVAILABLE", "observations": observations, "reason": "", "evidence": evidence}
    if standard_markets and offered_provider_player_ids:
        return {
            "state": "MARKET_MAPPING_FAILURE",
            "observations": [],
            "reason": "standard rushing markets were offered but no complete quote survived normalization",
            "evidence": evidence,
        }
    return {
        "state": "VERIFIED_NOT_POSTED",
        "observations": [],
        "reason": "exact FanDuel event parsed successfully with no open standard rushing-yards market",
        "evidence": evidence,
    }


def collect_fanduel_game_markets(game: Mapping[str, Any], *, timeout: int = MARKET_READ_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    """Compatibility wrapper for callers that only need complete quote rows."""
    bundle = collect_fanduel_game_market_bundle(game, timeout=timeout)
    return [dict(row) for row in bundle.get("observations") or [] if isinstance(row, Mapping)]


__all__ = [
    "FUZZY_MATCHING",
    "MARKET_READ_TIMEOUT_SECONDS",
    "MAX_MARKET_READ_ATTEMPTS",
    "MODEL_VERSION",
    "PLAYER_NAME_MATCHING",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "collect_fanduel_game_market_bundle",
    "collect_fanduel_game_markets",
    "is_standard_rushing_yards_market",
    "parse_event_market_observations",
    "reconcile_observation_to_roster",
]
