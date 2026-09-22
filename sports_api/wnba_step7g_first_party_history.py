"""Isolated Step 7G WNBA.com first-party game-history bridge.

This module is intentionally NOT wired into the frozen WNBA production providers.
It reads official server-rendered ``__NEXT_DATA__`` from public WNBA.com game and
player pages and normalizes only surfaces that can be proven compatible with the
existing Step 4D/4K contracts:

- traditional game box score
- recent player game-log rows exposed by ``player.latestGames``
- official play-by-play actions

Exact game rotations are deliberately fail-closed. WNBA.com's page payload has
not been proven to expose the source ``IN_TIME_REAL``/``OUT_TIME_REAL`` stint
records (plus per-stint PLAYER_PTS/PT_DIFF/USG_PCT) required by the frozen Step
4R contract, so this adapter never fabricates or reconstructs them.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from threading import Lock
from time import monotonic
from typing import Any

import httpx

from sports_api.wnba_game_history import (
    _normalize_box_team,
    _normalize_game_log_row,
    _normalize_season_type,
)
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_live_game import (
    ALLOWED_EVENT_CATEGORIES,
    _annotate_score_deltas,
    _normalize_action,
    _normalize_choice,
)

WNBA_LEAGUE_ID = "10"
WNBA_FIRST_PARTY_SOURCE = "WNBA.com First-Party Page Data"
WNBA_FIRST_PARTY_BASE_URL = "https://www.wnba.com"
GAME_PAGE_URL = f"{WNBA_FIRST_PARTY_BASE_URL}/game/{{game_id}}"
PLAYER_PAGE_URL = f"{WNBA_FIRST_PARTY_BASE_URL}/player/{{player_id}}"

BOX_SCORE_CACHE_TTL_SECONDS = 30
PLAYER_HISTORY_CACHE_TTL_SECONDS = 120
PLAY_BY_PLAY_CACHE_TTL_SECONDS = 4
CACHE_MAX_ENTRIES = 512
EXACT_ROTATION_SUPPORTED = False

_SEASON_TYPE_PREFIX = {
    "Pre Season": "1",
    "Regular Season": "2",
    "All-Star": "3",
    "All Star": "3",
    "Playoffs": "4",
}

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}

_CACHE: dict[tuple[str, int], dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class WNBAStep7GFirstPartyUpstreamError(RuntimeError):
    """Raised when the official WNBA.com page payload cannot be consumed safely."""


class WNBAStep7GFirstPartyNotFoundError(LookupError):
    """Raised when a requested official WNBA.com surface is not available."""


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        data = {str(key): value for key, value in attrs}
        if data.get("id") == "__NEXT_DATA__":
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._capture:
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self._parts).strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _validate_game_id(game_id: str) -> str:
    result = str(game_id).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _validate_player_id(player_id: int) -> int:
    if not isinstance(player_id, int) or isinstance(player_id, bool) or player_id <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return player_id


def _parse_page_props(html: str, *, url: str) -> dict[str, Any]:
    parser = _NextDataParser()
    try:
        parser.feed(html)
    except Exception as exc:
        raise WNBAStep7GFirstPartyUpstreamError(
            f"WNBA.com page HTML could not be parsed for {url}."
        ) from exc

    raw = parser.text
    if not raw:
        raise WNBAStep7GFirstPartyUpstreamError(
            f"WNBA.com page did not expose __NEXT_DATA__ for {url}."
        )

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise WNBAStep7GFirstPartyUpstreamError(
            f"WNBA.com __NEXT_DATA__ was not valid JSON for {url}."
        ) from exc

    if not isinstance(payload, dict):
        raise WNBAStep7GFirstPartyUpstreamError(
            f"WNBA.com __NEXT_DATA__ was not an object for {url}."
        )
    props = payload.get("props")
    page_props = props.get("pageProps") if isinstance(props, dict) else None
    if not isinstance(page_props, dict):
        raise WNBAStep7GFirstPartyUpstreamError(
            f"WNBA.com __NEXT_DATA__ was missing props.pageProps for {url}."
        )
    return page_props


def _request_page_props(
    url: str,
    *,
    ttl_seconds: int,
) -> tuple[dict[str, Any], str, bool, int]:
    key = (url, ttl_seconds)
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return (
                deepcopy(cached["page_props"]),
                cached["retrieved_at_utc"],
                True,
                ttl_seconds,
            )
        if cached:
            _CACHE.pop(key, None)

    try:
        response = httpx.get(
            url,
            headers=HTTP_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code == 404:
            raise WNBAStep7GFirstPartyNotFoundError(
                f"Official WNBA.com page was not found: {url}"
            )
        response.raise_for_status()
    except WNBAStep7GFirstPartyNotFoundError:
        raise
    except httpx.HTTPError as exc:
        raise WNBAStep7GFirstPartyUpstreamError(
            f"Official WNBA.com page request failed for {url}: {type(exc).__name__}"
        ) from exc

    page_props = _parse_page_props(response.text, url=url)
    retrieved_at_utc = _utc_now_iso()

    with _CACHE_LOCK:
        for cache_key in [
            cache_key for cache_key, item in _CACHE.items()
            if item["expires_at"] <= now
        ]:
            _CACHE.pop(cache_key, None)
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[key] = {
            "page_props": deepcopy(page_props),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + ttl_seconds,
        }

    return deepcopy(page_props), retrieved_at_utc, False, ttl_seconds


def _game_page(
    game_id: str,
    *,
    ttl_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any], str, bool, int, str]:
    url = GAME_PAGE_URL.format(game_id=game_id)
    props, retrieved_at_utc, cache_hit, ttl = _request_page_props(
        url,
        ttl_seconds=ttl_seconds,
    )
    game = props.get("game")
    if not isinstance(game, dict) or not game:
        raise WNBAStep7GFirstPartyNotFoundError(
            f"WNBA.com game payload is not available for game {game_id}."
        )
    returned_game_id = _clean(game.get("gameId"))
    if returned_game_id != game_id:
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com game payload game ID did not match the requested game ID."
        )
    return props, game, retrieved_at_utc, cache_hit, ttl, url


def _player_page(
    player_id: int,
) -> tuple[dict[str, Any], dict[str, Any], str, bool, int, str]:
    url = PLAYER_PAGE_URL.format(player_id=player_id)
    props, retrieved_at_utc, cache_hit, ttl = _request_page_props(
        url,
        ttl_seconds=PLAYER_HISTORY_CACHE_TTL_SECONDS,
    )
    player = props.get("player")
    if not isinstance(player, dict) or not player:
        raise WNBAStep7GFirstPartyNotFoundError(
            f"WNBA.com player payload is not available for player {player_id}."
        )

    identity_candidates: list[int] = []
    for value in (player.get("playerId"), player.get("personId"), player.get("id")):
        parsed = _to_int(value)
        if parsed is not None:
            identity_candidates.append(parsed)
    cms = player.get("cms")
    if isinstance(cms, dict):
        parsed = _to_int(cms.get("playerId"))
        if parsed is not None:
            identity_candidates.append(parsed)
    if identity_candidates and any(value != player_id for value in identity_candidates):
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com player payload player ID did not match the requested player ID."
        )
    return props, player, retrieved_at_utc, cache_hit, ttl, url


def get_first_party_game_box_score_dataset(
    game_id: str,
    season: int,
) -> dict[str, Any]:
    """Normalize WNBA.com server-rendered box-score data to the frozen Step 4D shape."""
    get_wnba_teams(season)
    game_id = _validate_game_id(game_id)
    _, game, retrieved_at_utc, cache_hit, ttl, url = _game_page(
        game_id,
        ttl_seconds=BOX_SCORE_CACHE_TTL_SECONDS,
    )

    home_raw = game.get("homeTeam")
    away_raw = game.get("awayTeam")
    if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com game payload is missing homeTeam or awayTeam."
        )
    try:
        home = _normalize_box_team(home_raw, season)
        away = _normalize_box_team(away_raw, season)
    except Exception as exc:
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com box score could not be normalized to the frozen Step 4D contract."
        ) from exc

    if home["official_team_id"] == away["official_team_id"]:
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com box score returned the same official team ID for home and away."
        )
    all_players = home["players"] + away["players"]
    player_ids = [
        player["player_id"] for player in all_players if player["player_id"] is not None
    ]
    duplicates = sorted(
        value for value in set(player_ids) if player_ids.count(value) > 1
    )
    if duplicates:
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com box score contains duplicate player IDs across the game."
        )

    return {
        "source": WNBA_FIRST_PARTY_SOURCE,
        "source_url": url,
        "source_endpoint": "wnba.com/game/[game_id]::__NEXT_DATA__.props.pageProps.game",
        "data_type": "official_traditional_box_score",
        "contract_shape": "Step 4D official_traditional_box_score",
        "season": season,
        "game_id": game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": ttl,
        "home": home,
        "away": away,
        "player_count": len(all_players),
        "verification": {
            "requested_game_id_matches_source": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
            "player_ids_unique": True,
            "normalized_with_frozen_step4d_box_contract": True,
            "production_provider_replaced": False,
        },
    }


def _season_id_for(season: int, season_type: str) -> str:
    prefix = _SEASON_TYPE_PREFIX.get(season_type)
    if prefix is None:
        raise ValueError(f"No WNBA season-ID prefix is defined for {season_type!r}.")
    return f"{prefix}{season}"


def get_first_party_player_recent_game_log_dataset(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
) -> dict[str, Any]:
    """Return recent player games exposed by WNBA.com's official player page.

    The WNBA page labels this surface ``latestGames``. It is intentionally not
    advertised as a complete full-season log.
    """
    get_wnba_teams(season)
    player_id = _validate_player_id(player_id)
    season_type = _normalize_season_type(season_type)
    wanted_season_id = _season_id_for(season, season_type)
    _, player, retrieved_at_utc, cache_hit, ttl, url = _player_page(player_id)

    raw_games = player.get("latestGames")
    if raw_games is None:
        raise WNBAStep7GFirstPartyNotFoundError(
            f"WNBA.com player.latestGames is not exposed for player {player_id}."
        )
    if not isinstance(raw_games, list):
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com player.latestGames has an unexpected schema."
        )

    selected_rows = [
        row for row in raw_games
        if isinstance(row, dict) and _clean(row.get("SEASON_ID")) == wanted_season_id
    ]
    games = [_normalize_game_log_row(row, season) for row in selected_rows]

    returned_player_ids = {
        game["player_id"] for game in games if game["player_id"] is not None
    }
    if returned_player_ids and returned_player_ids != {player_id}:
        raise WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com latestGames returned player IDs that did not match the request."
        )
    game_ids = [game["game_id"] for game in games if game["game_id"] is not None]
    duplicate_game_ids = sorted(
        value for value in set(game_ids) if game_ids.count(value) > 1
    )
    all_game_ids_valid = all(game["game_id_valid"] for game in games)
    all_matchup_teams_mapped = all(
        game["matchup"]["team_key"] is not None
        and game["matchup"]["opponent_team_key"] is not None
        for game in games
    )

    return {
        "source": WNBA_FIRST_PARTY_SOURCE,
        "source_url": url,
        "source_endpoint": "wnba.com/player/[player_id]::__NEXT_DATA__.props.pageProps.player.latestGames",
        "data_type": "official_recent_player_game_log",
        "contract_shape": "Step 4D official_player_game_log rows",
        "season": season,
        "season_type": season_type,
        "season_id_filter": wanted_season_id,
        "player_id": player_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": ttl,
        "history_scope": {
            "source_field": "player.latestGames",
            "source_row_count": len(raw_games),
            "selected_row_count": len(games),
            "full_season_history_guaranteed": False,
            "recent_history_only": True,
        },
        "game_count": len(games),
        "games": games,
        "verification": {
            "returned_player_ids_match_request": True,
            "all_game_ids_valid": all_game_ids_valid,
            "all_game_ids_unique": len(duplicate_game_ids) == 0,
            "duplicate_game_ids": duplicate_game_ids,
            "all_matchup_teams_mapped_to_registry": all_matchup_teams_mapped,
            "normalized_with_frozen_step4d_game_log_contract": True,
            "full_season_history_claimed": False,
            "production_provider_replaced": False,
        },
    }


def _looks_like_action(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    keys = set(value)
    return bool(keys & {"actionNumber", "actionId", "actionType"}) and (
        "period" in keys or "clock" in keys or "description" in keys
    )


def _extract_action_rows(value: Any) -> list[dict[str, Any]]:
    """Extract source-ordered action rows from the page's playByPlay surface."""
    if isinstance(value, list):
        direct = [item for item in value if _looks_like_action(item)]
        if direct:
            return direct
        combined: list[dict[str, Any]] = []
        for item in value:
            child = _extract_action_rows(item)
            if child:
                combined.extend(child)
        return combined

    if isinstance(value, dict):
        for key in ("actions", "playByPlay", "playbyplay", "game"):
            if key in value:
                child = _extract_action_rows(value[key])
                if child:
                    return child
        for child_value in value.values():
            child = _extract_action_rows(child_value)
            if child:
                return child
    return []


def get_first_party_play_by_play_dataset(
    game_id: str,
    season: int,
    *,
    event_category: str = "All",
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize WNBA.com server-rendered play-by-play to the frozen Step 4K shape."""
    get_wnba_teams(season)
    game_id = _validate_game_id(game_id)
    category = _normalize_choice(
        event_category,
        ALLOWED_EVENT_CATEGORIES,
        "event_category",
    )
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 1000:
        raise ValueError("WNBA play-by-play limit must be an integer from 0 through 1000.")

    props, _, retrieved_at_utc, cache_hit, ttl, url = _game_page(
        game_id,
        ttl_seconds=PLAY_BY_PLAY_CACHE_TTL_SECONDS,
    )
    raw_surface = props.get("playByPlay")
    if raw_surface is None:
        raise WNBAStep7GFirstPartyNotFoundError(
            f"WNBA.com playByPlay is not exposed for game {game_id}."
        )
    raw_actions = _extract_action_rows(raw_surface)
    if not raw_actions:
        raise WNBAStep7GFirstPartyNotFoundError(
            f"WNBA.com playByPlay did not expose action rows for game {game_id}."
        )

    actions = [_normalize_action(item, season) for item in raw_actions]
    _annotate_score_deltas(actions)
    action_ids = [
        action["action_id"] for action in actions if action["action_id"] is not None
    ]
    duplicate_action_ids = sorted(
        value for value in set(action_ids) if action_ids.count(value) > 1
    )
    unmapped = sum(
        action["team_tricode"] is not None and action["team_key"] is None
        for action in actions
    )
    filtered = actions if category == "All" else [
        action for action in actions if action["event_category"] == category
    ]
    if limit > 0:
        filtered = filtered[-limit:]

    return {
        "source": WNBA_FIRST_PARTY_SOURCE,
        "source_url": url,
        "source_endpoint": "wnba.com/game/[game_id]::__NEXT_DATA__.props.pageProps.playByPlay",
        "data_type": "official_live_play_by_play",
        "contract_shape": "Step 4K official_live_play_by_play",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game_id": game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": ttl,
        "filters": {"event_category": category, "limit": limit},
        "source_action_count": len(actions),
        "action_count": len(filtered),
        "latest_event": actions[-1] if actions else None,
        "actions": filtered,
        "verification": {
            "requested_game_id_matches_source": True,
            "action_ids_unique_when_present": len(duplicate_action_ids) == 0,
            "duplicate_action_ids": duplicate_action_ids,
            "unmapped_team_event_count": unmapped,
            "all_team_events_mapped_to_registry": unmapped == 0,
            "source_order_preserved": True,
            "normalized_with_frozen_step4k_action_contract": True,
            "production_provider_replaced": False,
        },
    }


def get_first_party_exact_rotation_dataset(
    game_id: str,
    season: int,
) -> dict[str, Any]:
    """Fail closed until an exact official Step 4R-equivalent source is proven."""
    get_wnba_teams(season)
    game_id = _validate_game_id(game_id)
    raise WNBAStep7GFirstPartyNotFoundError(
        "Exact WNBA rotation is intentionally unavailable in the Step 7G first-party "
        f"page bridge for game {game_id}: source IN_TIME_REAL/OUT_TIME_REAL stint "
        "records with PLAYER_PTS/PT_DIFF/USG_PCT have not been proven. "
        "PBP substitution reconstruction is intentionally disabled."
    )
