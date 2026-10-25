"""Direct-book NFL Receiving Yards observations from canonical game context.

This adapter is display-only. It discovers one exact game from caller-supplied
team identity, parses standard two-way Receiving Yards markets, and returns the
provider player metadata needed for exact team + jersey + position reconciliation
against nflverse roster identity in the Kyre Sports API layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from sports_api.collectors import nfl_fanduel_passing_yards_nflverse_v1 as base

MODEL_VERSION = "NFL RECEIVING YARDS DIRECT BOOK NFLVERSE V2"
PLAYER_NAME_MATCHING = False
FUZZY_MATCHING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
KNOWN_PROP_TABS = (
    "receiving-props",
    "player-receiving-props",
    "player-props",
    "receiving",
    "popular",
)
_ALLOWED_POSITIONS = {"WR", "WIDE RECEIVER", "TE", "TIGHT END", "RB", "RUNNING BACK", "FB", "FULLBACK"}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _market_text(market: Mapping[str, Any]) -> str:
    return " ".join(
        _text(market.get(field))
        for field in ("marketType", "marketTypeCode", "type", "marketName", "name", "displayName")
        if _text(market.get(field))
    )


def is_standard_receiving_yards_market(market: Mapping[str, Any]) -> bool:
    text = re.sub(r"[^a-z0-9]+", " ", _market_text(market).lower()).strip()
    if "receiv" not in text or "yard" not in text:
        return False
    blocked = (
        "alternate", "alternative", "longest", "team receiving", "rushing receiving",
        "rushing and receiving", "1st half", "first half", "quarter",
    )
    return not any(token in text for token in blocked)


def _standard_markets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    return [
        row for row in base._rows(attachments.get("markets"))
        if is_standard_receiving_yards_market(row) and base._market_open(row)
    ]


def _discover_tabs(payload: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = _text(value)
        low = text.lower()
        if not text or len(text) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", text):
            return
        if "receiv" not in low or ("prop" not in low and "yard" not in low):
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


def _provider_player_for_pair(
    over: Mapping[str, Any],
    under: Mapping[str, Any],
    players: Mapping[str, dict[str, Any]],
    by_selection: Mapping[str, list[str]],
) -> tuple[str, dict[str, Any]] | None:
    keys: list[str] = []
    for runner in (over, under):
        mapped = by_selection.get(_text(runner.get("selectionId"))) or []
        if len(mapped) != 1:
            return None
        keys.append(mapped[0])
    if len(keys) != 2 or keys[0] != keys[1]:
        return None
    player = players.get(keys[0])
    return (keys[0], dict(player)) if isinstance(player, Mapping) else None


def parse_event_market_observations(
    event_page: Mapping[str, Any],
    fdx_players: Mapping[str, Any],
    *,
    source_timestamp: str,
) -> list[dict[str, Any]]:
    players, by_selection = base._provider_player_maps(fdx_players)
    if not players or not by_selection:
        return []
    observations: list[dict[str, Any]] = []
    for market in _standard_markets(event_page):
        active = [
            row for row in base._rows(market.get("runners"))
            if _text(row.get("runnerStatus")).upper() in {"", "ACTIVE"}
        ]
        overs = [row for row in active if base._runner_role(row) == "OVER"]
        unders = [row for row in active if base._runner_role(row) == "UNDER"]
        if len(overs) != 1 or len(unders) != 1:
            continue
        over, under = overs[0], unders[0]
        over_line, under_line = base._line(over), base._line(under)
        over_odds, under_odds = base._american_odds(over), base._american_odds(under)
        if over_line is None or under_line is None or over_line != under_line or over_odds is None or under_odds is None:
            continue
        resolved = _provider_player_for_pair(over, under, players, by_selection)
        if resolved is None:
            continue
        provider_player_id, player = resolved
        team_abbr = _text(player.get("team") or player.get("teamAbbreviation")).upper()
        position = _text(player.get("position")).upper()
        jersey_number = _text(player.get("number") or player.get("jersey") or player.get("jerseyNumber"))
        player_name = _text(player.get("name") or player.get("displayName") or player.get("fullName"))
        if not team_abbr or position not in _ALLOWED_POSITIONS or not jersey_number:
            continue
        observations.append({
            "provider_player_id": provider_player_id,
            "player_name": player_name,
            "team_abbr": team_abbr,
            "position": position,
            "jersey_number": jersey_number,
            "sportsbook": "FanDuel",
            "market": "Receiving Yards",
            "line": over_line,
            "over_odds": over_odds,
            "under_odds": under_odds,
            "source_timestamp": _text(source_timestamp),
            "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
            "sportsbook_projection_influence": 0.0,
        })
    return observations


def collect_fanduel_game_markets(game: Mapping[str, Any], *, timeout: int = 10) -> list[dict[str, Any]]:
    if not _text(game.get("away_name")) or not _text(game.get("home_name")):
        return []
    landing = base._get_json(
        f"{base.FANDUEL_BASE_URL}/sbapi/content-managed-page",
        {"_ak": base.FANDUEL_PUBLIC_WEB_KEY, "page": "CUSTOM", "customPageId": "nfl", "timezone": "America/New_York"},
        timeout=timeout,
    )
    event_id = base._match_event(landing, game)
    if not event_id:
        return []
    selected = base._get_json(
        f"{base.FANDUEL_BASE_URL}/sbapi/event-page",
        {"_ak": base.FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id},
        timeout=timeout,
    )
    if not _standard_markets(selected):
        for tab in _discover_tabs(selected):
            try:
                candidate = base._get_json(
                    f"{base.FANDUEL_BASE_URL}/sbapi/event-page",
                    {"_ak": base.FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id, "tab": tab},
                    timeout=timeout,
                )
            except base.FanDuelPassingYardsError:
                continue
            if _standard_markets(candidate):
                selected = candidate
                break
    if not _standard_markets(selected):
        return []
    fdx = base._get_json(f"{base.FANDUEL_FDX_BASE_URL}/v1/live/event/{event_id}/players", timeout=timeout)
    timestamp = datetime.now(timezone.utc).isoformat()
    allowed_teams = {_text(game.get("away")).upper(), _text(game.get("home")).upper()}
    return [
        row for row in parse_event_market_observations(selected, fdx, source_timestamp=timestamp)
        if row.get("team_abbr") in allowed_teams
    ]


def reconcile_observation_to_roster(
    observation: Mapping[str, Any],
    roster_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve one market observation to one roster row without name matching."""
    team_abbr = _text(observation.get("team_abbr")).upper()
    jersey_number = _text(observation.get("jersey_number"))
    position = _text(observation.get("position")).upper()
    matches = [
        dict(row) for row in roster_rows
        if _text(row.get("team_abbr")).upper() == team_abbr
        and _text(row.get("jersey_number")) == jersey_number
        and _text(row.get("position")).upper() == position
        and row.get("active") is True
    ]
    if len(matches) != 1:
        return None
    return matches[0]


__all__ = [
    "FUZZY_MATCHING",
    "MODEL_VERSION",
    "PLAYER_NAME_MATCHING",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "collect_fanduel_game_markets",
    "is_standard_receiving_yards_market",
    "parse_event_market_observations",
    "reconcile_observation_to_roster",
]
