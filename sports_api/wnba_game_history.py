"""Official WNBA traditional box scores and player game logs.

Step 4D is intentionally limited to observed game history. It does not contain
betting lines, projections, simulation outputs, injury assumptions, or model
probabilities.

Sources:
- stats.wnba.com/stats/boxscoretraditionalv3
- stats.wnba.com/stats/playergamelog

The box-score path uses the current V3 schema. The legacy V2 traditional
box-score endpoint is not used because it is deprecated upstream.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from threading import Lock
from time import monotonic
from typing import Any, Iterable

import httpx

from sports_api.wnba_league import get_wnba_teams

WNBA_LEAGUE_ID = "10"
WNBA_STATS_BASE_URL = "https://stats.wnba.com/stats"
WNBA_HISTORY_SOURCE = "WNBA Stats API"
WNBA_HISTORY_SOURCE_URL = "https://stats.wnba.com/"

BOX_SCORE_ENDPOINT = "boxscoretraditionalv3"
PLAYER_GAME_LOG_ENDPOINT = "playergamelog"

ALLOWED_SEASON_TYPES = (
    "Pre Season",
    "Regular Season",
    "Playoffs",
    "All-Star",
    "All Star",
)

_CACHE_TTL_BY_ENDPOINT = {
    BOX_SCORE_ENDPOINT: 30,
    PLAYER_GAME_LOG_ENDPOINT: 120,
}
_CACHE_MAX_ENTRIES = 1024

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


class WNBAHistoryUpstreamError(RuntimeError):
    """Raised when official WNBA historical data cannot be consumed safely."""


class WNBAHistoryNotFoundError(LookupError):
    """Raised when an official WNBA box score is not available for a game."""


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


def _minutes_to_float(value: Any) -> float | None:
    """Normalize NBA/WNBA Stats minute formats to decimal minutes."""

    text = _clean_text(value)
    if text is None:
        return None

    if text.startswith("PT"):
        match = re.fullmatch(
            r"PT(?:(?P<hours>\d+(?:\.\d+)?)H)?"
            r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
            r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?",
            text,
        )
        if not match:
            return None
        hours = float(match.group("hours") or 0.0)
        minutes = float(match.group("minutes") or 0.0)
        seconds = float(match.group("seconds") or 0.0)
        return round(hours * 60.0 + minutes + seconds / 60.0, 4)

    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            try:
                minutes = float(parts[0])
                seconds = float(parts[1])
            except ValueError:
                return None
            return round(minutes + seconds / 60.0, 4)

    try:
        return float(text)
    except ValueError:
        return None


def _game_date_iso(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.title(), fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _validate_game_id(game_id: str) -> str:
    normalized = str(game_id).strip()
    if len(normalized) != 10 or not normalized.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return normalized


def _normalize_season_type(season_type: str) -> str:
    normalized = str(season_type).strip()
    by_casefold = {value.casefold(): value for value in ALLOWED_SEASON_TYPES}
    resolved = by_casefold.get(normalized.casefold())
    if resolved is None:
        allowed = ", ".join(ALLOWED_SEASON_TYPES)
        raise ValueError(
            f"Unsupported WNBA season_type {season_type!r}. Allowed values: {allowed}."
        )
    return resolved


def _cache_key(endpoint: str, params: Iterable[tuple[str, Any]]) -> tuple[Any, ...]:
    return (
        endpoint,
        tuple((str(key), str(value)) for key, value in params),
    )


def _request_stats_json(
    endpoint: str,
    params: list[tuple[str, Any]],
) -> tuple[dict[str, Any], str, bool, int]:
    key = _cache_key(endpoint, params)
    ttl_seconds = _CACHE_TTL_BY_ENDPOINT.get(endpoint, 60)
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return (
                deepcopy(cached["payload"]),
                cached["retrieved_at_utc"],
                True,
                ttl_seconds,
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
        if response.status_code == 404:
            raise WNBAHistoryNotFoundError(
                f"Official WNBA Stats API did not find data for {endpoint}."
            )
        response.raise_for_status()
        payload = response.json()
    except WNBAHistoryNotFoundError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise WNBAHistoryUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBAHistoryUpstreamError(
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

        if len(_CACHE) >= _CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)

        _CACHE[key] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + ttl_seconds,
        }

    return payload, retrieved_at_utc, False, ttl_seconds


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
        raise WNBAHistoryUpstreamError(
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
        raise WNBAHistoryUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")

    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBAHistoryUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    rows: list[dict[str, Any]] = []
    for row in row_set:
        if isinstance(row, (list, tuple)):
            rows.append(dict(zip(headers, row)))
    return rows


def _registry_team_from_values(
    *,
    season: int,
    tricode: Any = None,
    slug: Any = None,
    team_name: Any = None,
    team_city: Any = None,
) -> dict[str, Any] | None:
    values = {
        (_clean_text(tricode) or "").casefold(),
        (_clean_text(slug) or "").casefold(),
        (_clean_text(team_name) or "").casefold(),
    }

    city = _clean_text(team_city)
    nickname = _clean_text(team_name)
    if city and nickname:
        values.add(f"{city} {nickname}".casefold())

    values.discard("")

    for team in get_wnba_teams(season):
        candidates = {
            team["team_key"].casefold(),
            team["slug"].casefold(),
            team["abbreviation"].casefold(),
            team["nickname"].casefold(),
            team["full_name"].casefold(),
        }
        if values & candidates:
            return team

    return None


def _registry_team_from_abbreviation(
    abbreviation: str | None,
    season: int,
) -> dict[str, Any] | None:
    if not abbreviation:
        return None

    normalized = abbreviation.casefold()
    for team in get_wnba_teams(season):
        if team["abbreviation"].casefold() == normalized:
            return team
    return None


def _normalize_traditional_stats(stats: dict[str, Any]) -> dict[str, Any]:
    minutes_raw = _clean_text(stats.get("minutes"))
    return {
        "minutes_raw": minutes_raw,
        "minutes": _minutes_to_float(minutes_raw),
        "field_goals_made": _to_int(stats.get("fieldGoalsMade")),
        "field_goals_attempted": _to_int(stats.get("fieldGoalsAttempted")),
        "field_goal_percentage": _to_float(stats.get("fieldGoalsPercentage")),
        "three_pointers_made": _to_int(stats.get("threePointersMade")),
        "three_pointers_attempted": _to_int(stats.get("threePointersAttempted")),
        "three_point_percentage": _to_float(stats.get("threePointersPercentage")),
        "free_throws_made": _to_int(stats.get("freeThrowsMade")),
        "free_throws_attempted": _to_int(stats.get("freeThrowsAttempted")),
        "free_throw_percentage": _to_float(stats.get("freeThrowsPercentage")),
        "offensive_rebounds": _to_int(stats.get("reboundsOffensive")),
        "defensive_rebounds": _to_int(stats.get("reboundsDefensive")),
        "rebounds": _to_int(stats.get("reboundsTotal")),
        "assists": _to_int(stats.get("assists")),
        "steals": _to_int(stats.get("steals")),
        "blocks": _to_int(stats.get("blocks")),
        "turnovers": _to_int(stats.get("turnovers")),
        "personal_fouls": _to_int(stats.get("foulsPersonal")),
        "points": _to_int(stats.get("points")),
        "plus_minus": _to_float(stats.get("plusMinusPoints")),
    }


def _normalize_box_player(
    player: dict[str, Any],
    team: dict[str, Any],
) -> dict[str, Any]:
    stats = player.get("statistics")
    if not isinstance(stats, dict):
        stats = {}

    first_name = _clean_text(player.get("firstName"))
    last_name = _clean_text(player.get("familyName"))
    full_name = " ".join(
        value for value in (first_name, last_name) if value
    ) or _clean_text(player.get("nameI"))

    normalized_stats = _normalize_traditional_stats(stats)
    start_position = _clean_text(player.get("position"))

    return {
        "player_id": _to_int(player.get("personId")),
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "name_initial": _clean_text(player.get("nameI")),
        "player_slug": _clean_text(player.get("playerSlug")),
        "jersey_number": _clean_text(player.get("jerseyNum")),
        "start_position": start_position,
        "is_starter": bool(start_position),
        "comment": _clean_text(player.get("comment")),
        "appeared": (normalized_stats.get("minutes") or 0.0) > 0.0,
        "official_team_id": team["official_team_id"],
        "team_key": team["team_key"],
        "team_abbreviation": team["team_abbreviation"],
        "stats": normalized_stats,
    }


def _normalize_team_split(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return _normalize_traditional_stats(value)


def _normalize_box_team(raw_team: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_values(
        season=season,
        tricode=raw_team.get("teamTricode"),
        slug=raw_team.get("teamSlug"),
        team_name=raw_team.get("teamName"),
        team_city=raw_team.get("teamCity"),
    )
    if registry is None:
        raise WNBAHistoryUpstreamError(
            "WNBA box score contains a team that does not map to the "
            f"verified {season} WNBA registry."
        )

    official_team_id = _to_int(raw_team.get("teamId"))
    if official_team_id in (None, 0):
        raise WNBAHistoryUpstreamError(
            "WNBA box score contains a missing or invalid official team ID."
        )

    statistics = raw_team.get("statistics")
    if not isinstance(statistics, dict):
        statistics = {}

    team = {
        "official_team_id": official_team_id,
        "team_key": registry["team_key"],
        "full_name": registry["full_name"],
        "conference": registry["conference"],
        "team_city": _clean_text(raw_team.get("teamCity")),
        "team_name": _clean_text(raw_team.get("teamName")),
        "team_abbreviation": _clean_text(raw_team.get("teamTricode")),
        "team_slug": _clean_text(raw_team.get("teamSlug")),
    }

    players_raw = raw_team.get("players")
    if not isinstance(players_raw, list):
        players_raw = []

    players = [
        _normalize_box_player(player, team)
        for player in players_raw
        if isinstance(player, dict)
    ]

    return {
        **team,
        "stats": _normalize_traditional_stats(statistics),
        "starters_stats": _normalize_team_split(raw_team.get("starters")),
        "bench_stats": _normalize_team_split(raw_team.get("bench")),
        "player_count": len(players),
        "players": players,
    }


def get_game_box_score_dataset(
    game_id: str,
    season: int,
) -> dict[str, Any]:
    get_wnba_teams(season)
    normalized_game_id = _validate_game_id(game_id)

    params = [
        ("EndPeriod", "14"),
        ("EndRange", "0"),
        ("GameID", normalized_game_id),
        ("RangeType", "0"),
        ("StartPeriod", "0"),
        ("StartRange", "0"),
    ]
    payload, retrieved_at_utc, cache_hit, cache_ttl_seconds = _request_stats_json(
        BOX_SCORE_ENDPOINT,
        params,
    )

    box_score = payload.get("boxScoreTraditional")
    if not isinstance(box_score, dict) or not box_score:
        raise WNBAHistoryNotFoundError(
            f"WNBA traditional box score is not available for game {normalized_game_id}."
        )

    returned_game_id = _clean_text(box_score.get("gameId"))
    if returned_game_id != normalized_game_id:
        raise WNBAHistoryUpstreamError(
            "WNBA box-score response game ID did not match the requested game ID."
        )

    home_raw = box_score.get("homeTeam")
    away_raw = box_score.get("awayTeam")
    if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
        raise WNBAHistoryUpstreamError(
            "WNBA box-score response is missing homeTeam or awayTeam."
        )

    home = _normalize_box_team(home_raw, season)
    away = _normalize_box_team(away_raw, season)

    if home["official_team_id"] == away["official_team_id"]:
        raise WNBAHistoryUpstreamError(
            "WNBA box score returned the same official team ID for home and away."
        )

    all_players = home["players"] + away["players"]
    player_ids = [
        player["player_id"]
        for player in all_players
        if player["player_id"] is not None
    ]
    duplicate_player_ids = sorted(
        player_id
        for player_id in set(player_ids)
        if player_ids.count(player_id) > 1
    )
    if duplicate_player_ids:
        raise WNBAHistoryUpstreamError(
            "WNBA box score contains duplicate player IDs across the game: "
            + ", ".join(str(value) for value in duplicate_player_ids)
        )

    return {
        "source": WNBA_HISTORY_SOURCE,
        "source_url": WNBA_HISTORY_SOURCE_URL,
        "source_endpoint": BOX_SCORE_ENDPOINT,
        "data_type": "official_traditional_box_score",
        "season": season,
        "game_id": normalized_game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": cache_ttl_seconds,
        "home": home,
        "away": away,
        "player_count": len(all_players),
        "verification": {
            "requested_game_id_matches_source": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
            "player_ids_unique": True,
        },
    }


def _parse_matchup(matchup: str | None, season: int) -> dict[str, Any]:
    text = _clean_text(matchup)
    if text is None:
        return {
            "raw": None,
            "location": "unknown",
            "team_abbreviation": None,
            "team_key": None,
            "opponent_abbreviation": None,
            "opponent_team_key": None,
        }

    marker = None
    location = "unknown"
    if " vs. " in text:
        marker = " vs. "
        location = "home"
    elif " @ " in text:
        marker = " @ "
        location = "away"

    if marker is None:
        return {
            "raw": text,
            "location": location,
            "team_abbreviation": None,
            "team_key": None,
            "opponent_abbreviation": None,
            "opponent_team_key": None,
        }

    team_abbreviation, opponent_abbreviation = [
        part.strip() for part in text.split(marker, 1)
    ]
    team_registry = _registry_team_from_abbreviation(team_abbreviation, season)
    opponent_registry = _registry_team_from_abbreviation(
        opponent_abbreviation,
        season,
    )

    return {
        "raw": text,
        "location": location,
        "team_abbreviation": team_abbreviation,
        "team_key": team_registry["team_key"] if team_registry else None,
        "opponent_abbreviation": opponent_abbreviation,
        "opponent_team_key": (
            opponent_registry["team_key"] if opponent_registry else None
        ),
    }


def _normalize_game_log_row(
    row: dict[str, Any],
    season: int,
) -> dict[str, Any]:
    game_id = _clean_text(row.get("Game_ID") if "Game_ID" in row else row.get("GAME_ID"))
    player_id = _to_int(
        row.get("Player_ID") if "Player_ID" in row else row.get("PLAYER_ID")
    )
    matchup = _parse_matchup(_clean_text(row.get("MATCHUP")), season)

    return {
        "season_id": _clean_text(row.get("SEASON_ID")),
        "player_id": player_id,
        "game_id": game_id,
        "game_id_valid": bool(game_id and len(game_id) == 10 and game_id.isdigit()),
        "game_date_raw": _clean_text(row.get("GAME_DATE")),
        "game_date": _game_date_iso(row.get("GAME_DATE")),
        "matchup": matchup,
        "result": _clean_text(row.get("WL")),
        "minutes": _to_float(row.get("MIN")),
        "field_goals_made": _to_int(row.get("FGM")),
        "field_goals_attempted": _to_int(row.get("FGA")),
        "field_goal_percentage": _to_float(row.get("FG_PCT")),
        "three_pointers_made": _to_int(row.get("FG3M")),
        "three_pointers_attempted": _to_int(row.get("FG3A")),
        "three_point_percentage": _to_float(row.get("FG3_PCT")),
        "free_throws_made": _to_int(row.get("FTM")),
        "free_throws_attempted": _to_int(row.get("FTA")),
        "free_throw_percentage": _to_float(row.get("FT_PCT")),
        "offensive_rebounds": _to_int(row.get("OREB")),
        "defensive_rebounds": _to_int(row.get("DREB")),
        "rebounds": _to_int(row.get("REB")),
        "assists": _to_int(row.get("AST")),
        "steals": _to_int(row.get("STL")),
        "blocks": _to_int(row.get("BLK")),
        "turnovers": _to_int(row.get("TOV")),
        "personal_fouls": _to_int(row.get("PF")),
        "points": _to_int(row.get("PTS")),
        "plus_minus": _to_float(row.get("PLUS_MINUS")),
        "video_available": _to_int(row.get("VIDEO_AVAILABLE")),
    }


def get_player_game_log_dataset(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
) -> dict[str, Any]:
    get_wnba_teams(season)

    if not isinstance(player_id, int) or isinstance(player_id, bool) or player_id <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")

    normalized_season_type = _normalize_season_type(season_type)

    params = [
        ("PlayerID", str(player_id)),
        ("Season", str(season)),
        ("SeasonType", normalized_season_type),
        ("LeagueID", WNBA_LEAGUE_ID),
        ("DateFrom", ""),
        ("DateTo", ""),
    ]
    payload, retrieved_at_utc, cache_hit, cache_ttl_seconds = _request_stats_json(
        PLAYER_GAME_LOG_ENDPOINT,
        params,
    )
    rows = _result_rows(payload, "PlayerGameLog")

    games = [_normalize_game_log_row(row, season) for row in rows]

    returned_player_ids = {
        game["player_id"]
        for game in games
        if game["player_id"] is not None
    }
    if returned_player_ids and returned_player_ids != {player_id}:
        raise WNBAHistoryUpstreamError(
            "WNBA player game log returned player IDs that did not match the request."
        )

    game_ids = [
        game["game_id"]
        for game in games
        if game["game_id"] is not None
    ]
    duplicate_game_ids = sorted(
        game_id
        for game_id in set(game_ids)
        if game_ids.count(game_id) > 1
    )

    all_game_ids_valid = all(game["game_id_valid"] for game in games)
    all_matchup_teams_mapped = all(
        game["matchup"]["team_key"] is not None
        and game["matchup"]["opponent_team_key"] is not None
        for game in games
    )

    return {
        "source": WNBA_HISTORY_SOURCE,
        "source_url": WNBA_HISTORY_SOURCE_URL,
        "source_endpoint": PLAYER_GAME_LOG_ENDPOINT,
        "data_type": "official_player_game_log",
        "season": season,
        "season_type": normalized_season_type,
        "player_id": player_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": cache_ttl_seconds,
        "game_count": len(games),
        "games": games,
        "verification": {
            "returned_player_ids_match_request": True,
            "all_game_ids_valid": all_game_ids_valid,
            "all_game_ids_unique": len(duplicate_game_ids) == 0,
            "duplicate_game_ids": duplicate_game_ids,
            "all_matchup_teams_mapped_to_registry": all_matchup_teams_mapped,
        },
    }
