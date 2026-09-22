"""Official WNBA player identity and roster collectors.

Step 4B is deliberately isolated from model, betting, schedule, standings, and
advanced-stat logic. It consumes the official WNBA Stats API roster endpoints,
normalizes their tabular result-set schema, and maps official team/player IDs
onto the stable team keys introduced in Step 4A.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Iterable

import httpx

from sports_api.wnba_league import get_wnba_teams

WNBA_LEAGUE_ID = "10"
WNBA_STATS_BASE_URL = "https://stats.wnba.com/stats"
WNBA_STATS_SOURCE = "WNBA Stats API"
WNBA_STATS_SOURCE_URL = "https://stats.wnba.com/"
WNBA_HEADSHOT_BASE_URL = "https://cdn.wnba.com/headshots/wnba/latest/1040x760"

CACHE_TTL_SECONDS = 120
CACHE_MAX_ENTRIES = 512

WNBA_STATS_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class WNBAStatsUpstreamError(RuntimeError):
    """Raised when the official WNBA Stats API cannot be consumed safely."""


class WNBAEntityNotFoundError(LookupError):
    """Raised when a requested WNBA team/player does not exist in loaded data."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _headshot_url(player_id: int | None) -> str | None:
    if player_id is None:
        return None
    return f"{WNBA_HEADSHOT_BASE_URL}/{player_id}.png"


def _cache_key(endpoint: str, params: Iterable[tuple[str, Any]]) -> tuple[Any, ...]:
    return (
        endpoint,
        tuple((str(key), str(value)) for key, value in params),
    )


def _request_stats_json(
    endpoint: str,
    params: list[tuple[str, Any]],
) -> tuple[dict[str, Any], str, bool]:
    """Fetch one official WNBA Stats API payload with a short TTL cache.

    ``params`` stays an ordered list of tuples intentionally. The WNBA stats
    edge has historically been sensitive to query-string construction, so
    LeagueID is kept first in every Step 4B request.
    """

    key = _cache_key(endpoint, params)
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return (
                deepcopy(cached["payload"]),
                cached["retrieved_at_utc"],
                True,
            )
        if cached:
            _CACHE.pop(key, None)

    url = f"{WNBA_STATS_BASE_URL}/{endpoint}"

    try:
        response = httpx.get(
            url,
            params=params,
            headers=WNBA_STATS_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WNBAStatsUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBAStatsUpstreamError(
            f"Official WNBA Stats API returned a non-object payload for {endpoint}."
        )

    retrieved_at_utc = _utc_now_iso()

    with _CACHE_LOCK:
        expired = [
            cache_key
            for cache_key, item in _CACHE.items()
            if item["expires_at"] <= now
        ]
        for cache_key in expired:
            _CACHE.pop(cache_key, None)

        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)

        _CACHE[key] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + CACHE_TTL_SECONDS,
        }

    return payload, retrieved_at_utc, False


def _result_rows(
    payload: dict[str, Any],
    result_name: str,
) -> list[dict[str, Any]]:
    result_sets = payload.get("resultSets")
    if result_sets is None:
        result_sets = payload.get("resultSet")

    if isinstance(result_sets, dict):
        candidates = [result_sets]
    elif isinstance(result_sets, list):
        candidates = result_sets
    else:
        raise WNBAStatsUpstreamError(
            f"WNBA payload is missing result sets for {result_name}."
        )

    selected = None
    for result_set in candidates:
        if not isinstance(result_set, dict):
            continue
        name = _clean_text(result_set.get("name"))
        if name and name.casefold() == result_name.casefold():
            selected = result_set
            break

    if selected is None and len(candidates) == 1 and isinstance(candidates[0], dict):
        selected = candidates[0]

    if selected is None:
        raise WNBAStatsUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")

    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBAStatsUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    return [
        dict(zip(headers, row))
        for row in row_set
        if isinstance(row, (list, tuple))
    ]


def _registry_team_for_key(team_key: str, season: int) -> dict[str, Any]:
    normalized_key = team_key.strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == normalized_key:
            return team

    raise WNBAEntityNotFoundError(
        f"WNBA team key {team_key!r} was not found for the {season} season."
    )


def _team_key_from_row(row: dict[str, Any], season: int) -> str | None:
    teams = get_wnba_teams(season)

    row_values = {
        (_clean_text(row.get("TEAM_ABBREVIATION")) or "").casefold(),
        (_clean_text(row.get("TEAM_SLUG")) or "").casefold(),
        (_clean_text(row.get("TEAM_NAME")) or "").casefold(),
    }

    team_city = _clean_text(row.get("TEAM_CITY"))
    team_name = _clean_text(row.get("TEAM_NAME"))
    if team_city and team_name:
        row_values.add(f"{team_city} {team_name}".casefold())

    row_values.discard("")

    for team in teams:
        candidates = {
            team["team_key"].casefold(),
            team["slug"].casefold(),
            team["abbreviation"].casefold(),
            team["nickname"].casefold(),
            team["full_name"].casefold(),
        }
        if row_values & candidates:
            return team["team_key"]

    return None


def _normalize_current_player(
    row: dict[str, Any],
    season: int,
) -> dict[str, Any]:
    player_id = _to_int(row.get("PERSON_ID"))
    roster_status = _to_int(
        row.get("ROSTERSTATUS")
        if "ROSTERSTATUS" in row
        else row.get("ROSTER_STATUS")
    )

    return {
        "player_id": player_id,
        "full_name": _clean_text(row.get("DISPLAY_FIRST_LAST")),
        "display_last_comma_first": _clean_text(
            row.get("DISPLAY_LAST_COMMA_FIRST")
        ),
        "player_code": _clean_text(row.get("PLAYERCODE")),
        "player_slug": _clean_text(row.get("PLAYER_SLUG")),
        "from_year": _to_int(row.get("FROM_YEAR")),
        "to_year": _to_int(row.get("TO_YEAR")),
        "roster_status": roster_status,
        "is_current_roster": roster_status == 1,
        "games_played_flag": _to_int(row.get("GAMES_PLAYED_FLAG")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_key": _team_key_from_row(row, season),
        "team_city": _clean_text(row.get("TEAM_CITY")),
        "team_name": _clean_text(row.get("TEAM_NAME")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_code": _clean_text(row.get("TEAM_CODE")),
        "team_slug": _clean_text(row.get("TEAM_SLUG")),
        "headshot_url": _headshot_url(player_id),
    }


def _normalize_roster_player(row: dict[str, Any]) -> dict[str, Any]:
    player_id = _to_int(row.get("PLAYER_ID"))

    return {
        "player_id": player_id,
        "full_name": _clean_text(row.get("PLAYER")),
        "nickname": _clean_text(row.get("NICKNAME")),
        "player_slug": _clean_text(row.get("PLAYER_SLUG")),
        "jersey_number": _clean_text(row.get("NUM")),
        "position": _clean_text(row.get("POSITION")),
        "height": _clean_text(row.get("HEIGHT")),
        "weight_lbs": _to_int(row.get("WEIGHT")),
        "birth_date": _clean_text(row.get("BIRTH_DATE")),
        "age": _to_float(row.get("AGE")),
        "experience": _clean_text(row.get("EXP")),
        "school": _clean_text(row.get("SCHOOL")),
        "how_acquired": _clean_text(row.get("HOW_ACQUIRED")),
        "headshot_url": _headshot_url(player_id),
    }


def _normalize_player_profile(row: dict[str, Any]) -> dict[str, Any]:
    player_id = _to_int(row.get("PERSON_ID"))
    roster_status = _to_int(row.get("ROSTERSTATUS"))

    return {
        "player_id": player_id,
        "first_name": _clean_text(row.get("FIRST_NAME")),
        "last_name": _clean_text(row.get("LAST_NAME")),
        "full_name": _clean_text(row.get("DISPLAY_FIRST_LAST")),
        "display_last_comma_first": _clean_text(
            row.get("DISPLAY_LAST_COMMA_FIRST")
        ),
        "player_slug": _clean_text(row.get("PLAYER_SLUG")),
        "birth_date": _clean_text(row.get("BIRTHDATE")),
        "school": _clean_text(row.get("SCHOOL")),
        "country": _clean_text(row.get("COUNTRY")),
        "last_affiliation": _clean_text(row.get("LAST_AFFILIATION")),
        "height": _clean_text(row.get("HEIGHT")),
        "weight_lbs": _to_int(row.get("WEIGHT")),
        "season_experience": _clean_text(row.get("SEASON_EXP")),
        "jersey_number": _clean_text(row.get("JERSEY")),
        "position": _clean_text(row.get("POSITION")),
        "roster_status": roster_status,
        "is_current_roster": roster_status == 1,
        "games_played_current_season_flag": _to_int(
            row.get("GAMES_PLAYED_CURRENT_SEASON_FLAG")
        ),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_name": _clean_text(row.get("TEAM_NAME")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_code": _clean_text(row.get("TEAM_CODE")),
        "team_city": _clean_text(row.get("TEAM_CITY")),
        "player_code": _clean_text(row.get("PLAYERCODE")),
        "from_year": _to_int(row.get("FROM_YEAR")),
        "to_year": _to_int(row.get("TO_YEAR")),
        "draft_year": _clean_text(row.get("DRAFT_YEAR")),
        "draft_round": _clean_text(row.get("DRAFT_ROUND")),
        "draft_number": _clean_text(row.get("DRAFT_NUMBER")),
        "headshot_url": _headshot_url(player_id),
    }


def get_current_players_dataset(
    season: int,
    *,
    current_roster_only: bool = True,
) -> dict[str, Any]:
    # Reuse Step 4A's fail-closed season validation.
    get_wnba_teams(season)

    params = [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("IsOnlyCurrentSeason", "1"),
    ]
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        "commonallplayers",
        params,
    )
    rows = _result_rows(payload, "CommonAllPlayers")

    players = [
        _normalize_current_player(row, season)
        for row in rows
    ]

    if current_roster_only:
        players = [
            player
            for player in players
            if player["is_current_roster"] and player["team_key"] is not None
        ]

    # Fail closed on malformed duplicates rather than returning ambiguous IDs.
    by_player_id: dict[int, dict[str, Any]] = {}
    no_id_players: list[dict[str, Any]] = []
    for player in players:
        player_id = player["player_id"]
        if player_id is None:
            no_id_players.append(player)
            continue
        by_player_id[player_id] = player

    players = list(by_player_id.values()) + no_id_players
    players.sort(
        key=lambda player: (
            player.get("team_key") or "zzzz",
            player.get("full_name") or "",
        )
    )

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": "commonallplayers",
        "season": season,
        "current_roster_only": current_roster_only,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "player_count": len(players),
        "players": players,
    }


def _resolve_official_team_id(team_key: str, season: int) -> int:
    _registry_team_for_key(team_key, season)
    dataset = get_current_players_dataset(
        season,
        current_roster_only=True,
    )

    team_ids = [
        player["official_team_id"]
        for player in dataset["players"]
        if player["team_key"] == team_key
        and player["official_team_id"] not in (None, 0)
    ]

    if not team_ids:
        raise WNBAStatsUpstreamError(
            f"Could not resolve an official WNBA team ID for {team_key!r} "
            f"in the {season} current-player feed."
        )

    return int(Counter(team_ids).most_common(1)[0][0])


def get_team_roster_dataset(team_key: str, season: int) -> dict[str, Any]:
    team = _registry_team_for_key(team_key, season)
    official_team_id = _resolve_official_team_id(team["team_key"], season)

    params = [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("TeamID", str(official_team_id)),
    ]
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        "commonteamroster",
        params,
    )
    rows = _result_rows(payload, "CommonTeamRoster")

    players = [_normalize_roster_player(row) for row in rows]
    players.sort(
        key=lambda player: (
            player.get("full_name") or "",
            player.get("player_id") or 0,
        )
    )

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": "commonteamroster",
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "team": {
            **team,
            "official_team_id": official_team_id,
        },
        "roster_count": len(players),
        "players": players,
    }


def get_player_profile_dataset(player_id: int) -> dict[str, Any]:
    params = [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("PlayerID", str(player_id)),
    ]
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        "commonplayerinfo",
        params,
    )

    profile_rows = _result_rows(payload, "CommonPlayerInfo")
    if not profile_rows:
        raise WNBAEntityNotFoundError(
            f"WNBA player {player_id} was not found."
        )

    headline_rows = _result_rows(payload, "PlayerHeadlineStats")
    season_rows = _result_rows(payload, "AvailableSeasons")

    profile = _normalize_player_profile(profile_rows[0])
    if profile["player_id"] is not None and profile["player_id"] != player_id:
        raise WNBAStatsUpstreamError(
            "WNBA commonplayerinfo returned a different player ID than requested."
        )

    headline = None
    if headline_rows:
        row = headline_rows[0]
        headline = {
            "player_id": _to_int(row.get("PLAYER_ID")),
            "player_name": _clean_text(row.get("PLAYER_NAME")),
            "timeframe": _clean_text(row.get("TimeFrame")),
            "points": _to_float(row.get("PTS")),
            "assists": _to_float(row.get("AST")),
            "rebounds": _to_float(row.get("REB")),
            "all_star_appearances": _to_int(row.get("ALL_STAR_APPEARANCES")),
        }

    available_seasons = [
        value
        for row in season_rows
        if (value := _clean_text(row.get("SEASON_ID"))) is not None
    ]

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": "commonplayerinfo",
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "player": profile,
        "headline_stats": headline,
        "available_seasons": available_seasons,
    }
