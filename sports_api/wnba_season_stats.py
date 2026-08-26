"""Official WNBA team/player season statistics and rolling-form summaries.

Step 4E adds observed season aggregates only. It intentionally excludes betting
lines, projections, simulations, injuries, and model probabilities.

Official sources:
- stats.wnba.com/stats/leaguedashplayerstats
- stats.wnba.com/stats/leaguedashteamstats

Player rolling windows are computed from the official Step 4D player game-log
feed so Last-5/Last-10 summaries remain traceable back to individual games.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Iterable

import httpx

from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    get_player_game_log_dataset,
)
from sports_api.wnba_league import get_wnba_teams

WNBA_LEAGUE_ID = "10"
WNBA_STATS_BASE_URL = "https://stats.wnba.com/stats"
WNBA_SEASON_STATS_SOURCE = "WNBA Stats API"
WNBA_SEASON_STATS_SOURCE_URL = "https://stats.wnba.com/"

PLAYER_STATS_ENDPOINT = "leaguedashplayerstats"
TEAM_STATS_ENDPOINT = "leaguedashteamstats"
ALLOWED_PER_MODES = ("PerGame", "Totals")
DEFAULT_ROLLING_WINDOWS = (5, 10)

CACHE_TTL_SECONDS = 90
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


class WNBASeasonStatsUpstreamError(RuntimeError):
    """Raised when official WNBA season statistics cannot be consumed safely."""


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


def _normalize_season_type(value: str) -> str:
    normalized = str(value).strip()
    by_casefold = {item.casefold(): item for item in ALLOWED_SEASON_TYPES}
    resolved = by_casefold.get(normalized.casefold())
    if resolved is None:
        allowed = ", ".join(ALLOWED_SEASON_TYPES)
        raise ValueError(
            f"Unsupported WNBA season_type {value!r}. Allowed values: {allowed}."
        )
    return resolved


def _normalize_per_mode(value: str) -> str:
    normalized = str(value).strip()
    by_casefold = {item.casefold(): item for item in ALLOWED_PER_MODES}
    resolved = by_casefold.get(normalized.casefold())
    if resolved is None:
        allowed = ", ".join(ALLOWED_PER_MODES)
        raise ValueError(
            f"Unsupported WNBA per_mode {value!r}. Allowed values: {allowed}."
        )
    return resolved


def _normalize_last_n_games(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    if value < 0 or value > 100:
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    return value


def _normalize_windows(value: str | Iterable[int]) -> tuple[int, ...]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        try:
            windows = [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError(
                "WNBA rolling windows must be comma-separated integers from 1 through 50."
            ) from exc
    else:
        try:
            windows = [int(item) for item in value]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "WNBA rolling windows must contain integers from 1 through 50."
            ) from exc

    if not windows:
        raise ValueError("WNBA rolling windows cannot be empty.")

    deduped: list[int] = []
    for window in windows:
        if window < 1 or window > 50:
            raise ValueError("WNBA rolling windows must be integers from 1 through 50.")
        if window not in deduped:
            deduped.append(window)

    return tuple(deduped)


def _cache_key(endpoint: str, params: Iterable[tuple[str, Any]]) -> tuple[Any, ...]:
    return (
        endpoint,
        tuple((str(key), str(value)) for key, value in params),
    )


def _request_stats_json(
    endpoint: str,
    params: list[tuple[str, Any]],
) -> tuple[dict[str, Any], str, bool]:
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
        raise WNBASeasonStatsUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBASeasonStatsUpstreamError(
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


def _result_rows(payload: dict[str, Any], result_name: str) -> list[dict[str, Any]]:
    result_sets = payload.get("resultSets")
    if result_sets is None:
        result_sets = payload.get("resultSet")

    if isinstance(result_sets, dict):
        candidates = [result_sets]
    elif isinstance(result_sets, list):
        candidates = result_sets
    else:
        raise WNBASeasonStatsUpstreamError(
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
        raise WNBASeasonStatsUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBASeasonStatsUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    return [
        dict(zip(headers, row))
        for row in row_set
        if isinstance(row, (list, tuple))
    ]


def _registry_team_from_row(row: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean_text(row.get("TEAM_ABBREVIATION")) or "").casefold(),
        (_clean_text(row.get("TEAM_NAME")) or "").casefold(),
    }
    values.discard("")

    for team in get_wnba_teams(season):
        candidates = {
            team["abbreviation"].casefold(),
            team["nickname"].casefold(),
            team["full_name"].casefold(),
            team["team_key"].casefold(),
        }
        if values & candidates:
            return team
    return None


def _validate_team_key(team_key: str | None, season: int) -> str | None:
    if team_key is None:
        return None
    normalized = team_key.strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == normalized:
            return team["team_key"]
    raise ValueError(f"WNBA team key {team_key!r} was not found for the {season} season.")


def _normalize_common_stats(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "minutes": _to_float(row.get("MIN")),
        "field_goals_made": _to_float(row.get("FGM")),
        "field_goals_attempted": _to_float(row.get("FGA")),
        "field_goal_percentage": _to_float(row.get("FG_PCT")),
        "three_pointers_made": _to_float(row.get("FG3M")),
        "three_pointers_attempted": _to_float(row.get("FG3A")),
        "three_point_percentage": _to_float(row.get("FG3_PCT")),
        "free_throws_made": _to_float(row.get("FTM")),
        "free_throws_attempted": _to_float(row.get("FTA")),
        "free_throw_percentage": _to_float(row.get("FT_PCT")),
        "offensive_rebounds": _to_float(row.get("OREB")),
        "defensive_rebounds": _to_float(row.get("DREB")),
        "rebounds": _to_float(row.get("REB")),
        "assists": _to_float(row.get("AST")),
        "turnovers": _to_float(row.get("TOV")),
        "steals": _to_float(row.get("STL")),
        "blocks": _to_float(row.get("BLK")),
        "blocked_attempts": _to_float(row.get("BLKA")),
        "personal_fouls": _to_float(row.get("PF")),
        "personal_fouls_drawn": _to_float(row.get("PFD")),
        "points": _to_float(row.get("PTS")),
        "plus_minus": _to_float(row.get("PLUS_MINUS")),
    }


def _normalize_player_row(row: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_row(row, season)
    return {
        "player_id": _to_int(row.get("PLAYER_ID")),
        "player_name": _clean_text(row.get("PLAYER_NAME")),
        "age": _to_float(row.get("AGE")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_key": registry["team_key"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "conference": registry["conference"] if registry else None,
        "games_played": _to_int(row.get("GP")),
        "record": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "stats": {
            **_normalize_common_stats(row),
            "fantasy_points": _to_float(row.get("NBA_FANTASY_PTS")),
            "double_doubles": _to_float(row.get("DD2")),
            "triple_doubles": _to_float(row.get("TD3")),
        },
        "mapped_to_registry": registry is not None,
    }


def _normalize_team_row(row: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_row(row, season)
    return {
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_name": _clean_text(row.get("TEAM_NAME")),
        "team_key": registry["team_key"] if registry else None,
        "team_abbreviation": registry["abbreviation"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "conference": registry["conference"] if registry else None,
        "games_played": _to_int(row.get("GP")),
        "record": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "stats": _normalize_common_stats(row),
        "mapped_to_registry": registry is not None,
    }


def _player_params(
    season: int,
    season_type: str,
    last_n_games: int,
    per_mode: str,
) -> list[tuple[str, Any]]:
    return [
        ("LastNGames", str(last_n_games)),
        ("MeasureType", "Base"),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("PerMode", per_mode),
        ("Period", "0"),
        ("PlusMinus", "N"),
        ("Rank", "N"),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("College", ""),
        ("Conference", ""),
        ("Country", ""),
        ("DateFrom", ""),
        ("DateTo", ""),
        ("Division", ""),
        ("DraftPick", ""),
        ("DraftYear", ""),
        ("GameScope", ""),
        ("GameSegment", ""),
        ("Height", ""),
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Location", ""),
        ("Outcome", ""),
        ("PORound", "0"),
        ("PlayerExperience", ""),
        ("PlayerPosition", ""),
        ("SeasonSegment", ""),
        ("ShotClockRange", ""),
        ("StarterBench", ""),
        ("TeamID", ""),
        ("TwoWay", ""),
        ("VsConference", ""),
        ("VsDivision", ""),
        ("Weight", ""),
    ]


def _team_params(
    season: int,
    season_type: str,
    last_n_games: int,
    per_mode: str,
) -> list[tuple[str, Any]]:
    return [
        ("LastNGames", str(last_n_games)),
        ("MeasureType", "Base"),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("PerMode", per_mode),
        ("Period", "0"),
        ("PlusMinus", "N"),
        ("Rank", "N"),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("Conference", ""),
        ("DateFrom", ""),
        ("DateTo", ""),
        ("Division", ""),
        ("GameScope", ""),
        ("GameSegment", ""),
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Location", ""),
        ("Outcome", ""),
        ("PORound", "0"),
        ("PlayerExperience", ""),
        ("PlayerPosition", ""),
        ("SeasonSegment", ""),
        ("ShotClockRange", ""),
        ("StarterBench", ""),
        ("TeamID", ""),
        ("TwoWay", ""),
        ("VsConference", ""),
        ("VsDivision", ""),
    ]


def get_player_season_stats_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "PerGame",
    team_key: str | None = None,
) -> dict[str, Any]:
    get_wnba_teams(season)
    normalized_season_type = _normalize_season_type(season_type)
    normalized_last_n = _normalize_last_n_games(last_n_games)
    normalized_per_mode = _normalize_per_mode(per_mode)
    normalized_team_key = _validate_team_key(team_key, season)

    params = _player_params(
        season,
        normalized_season_type,
        normalized_last_n,
        normalized_per_mode,
    )
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        PLAYER_STATS_ENDPOINT,
        params,
    )
    rows = _result_rows(payload, "LeagueDashPlayerStats")
    players = [_normalize_player_row(row, season) for row in rows]

    if normalized_team_key is not None:
        players = [player for player in players if player["team_key"] == normalized_team_key]

    players.sort(key=lambda player: (player.get("player_name") or "", player.get("player_id") or 0))

    player_ids = [player["player_id"] for player in players if player["player_id"] is not None]
    duplicate_player_ids = sorted(
        player_id for player_id in set(player_ids) if player_ids.count(player_id) > 1
    )
    unmapped_team_count = sum(1 for player in players if not player["mapped_to_registry"])

    return {
        "source": WNBA_SEASON_STATS_SOURCE,
        "source_url": WNBA_SEASON_STATS_SOURCE_URL,
        "source_endpoint": PLAYER_STATS_ENDPOINT,
        "data_type": "official_player_season_statistics",
        "season": season,
        "season_type": normalized_season_type,
        "last_n_games": normalized_last_n,
        "window_scope": "season_to_date" if normalized_last_n == 0 else f"last_{normalized_last_n}_games",
        "per_mode": normalized_per_mode,
        "team_key_filter": normalized_team_key,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "player_count": len(players),
        "players": players,
        "verification": {
            "duplicate_player_ids": duplicate_player_ids,
            "player_ids_unique": len(duplicate_player_ids) == 0,
            "unmapped_team_count": unmapped_team_count,
            "all_rows_mapped_to_registry": unmapped_team_count == 0,
        },
    }


def get_team_season_stats_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "PerGame",
    team_key: str | None = None,
) -> dict[str, Any]:
    get_wnba_teams(season)
    normalized_season_type = _normalize_season_type(season_type)
    normalized_last_n = _normalize_last_n_games(last_n_games)
    normalized_per_mode = _normalize_per_mode(per_mode)
    normalized_team_key = _validate_team_key(team_key, season)

    params = _team_params(
        season,
        normalized_season_type,
        normalized_last_n,
        normalized_per_mode,
    )
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        TEAM_STATS_ENDPOINT,
        params,
    )
    rows = _result_rows(payload, "LeagueDashTeamStats")
    teams = [_normalize_team_row(row, season) for row in rows]

    if normalized_team_key is not None:
        teams = [team for team in teams if team["team_key"] == normalized_team_key]

    teams.sort(key=lambda team: (team.get("team_full_name") or team.get("team_name") or ""))

    team_ids = [team["official_team_id"] for team in teams if team["official_team_id"] is not None]
    duplicate_team_ids = sorted(
        team_id for team_id in set(team_ids) if team_ids.count(team_id) > 1
    )
    unmapped_team_count = sum(1 for team in teams if not team["mapped_to_registry"])

    return {
        "source": WNBA_SEASON_STATS_SOURCE,
        "source_url": WNBA_SEASON_STATS_SOURCE_URL,
        "source_endpoint": TEAM_STATS_ENDPOINT,
        "data_type": "official_team_season_statistics",
        "season": season,
        "season_type": normalized_season_type,
        "last_n_games": normalized_last_n,
        "window_scope": "season_to_date" if normalized_last_n == 0 else f"last_{normalized_last_n}_games",
        "per_mode": normalized_per_mode,
        "team_key_filter": normalized_team_key,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "team_count": len(teams),
        "teams": teams,
        "verification": {
            "duplicate_team_ids": duplicate_team_ids,
            "team_ids_unique": len(duplicate_team_ids) == 0,
            "unmapped_team_count": unmapped_team_count,
            "all_rows_mapped_to_registry": unmapped_team_count == 0,
        },
    }


_ROLLING_COUNT_FIELDS = (
    "minutes",
    "field_goals_made",
    "field_goals_attempted",
    "three_pointers_made",
    "three_pointers_attempted",
    "free_throws_made",
    "free_throws_attempted",
    "offensive_rebounds",
    "defensive_rebounds",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "personal_fouls",
    "points",
    "plus_minus",
)


def _numeric_values(games: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for game in games:
        value = game.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def _sum_field(games: list[dict[str, Any]], field: str) -> float:
    return round(sum(_numeric_values(games, field)), 4)


def _weighted_percentage(games: list[dict[str, Any]], made_field: str, attempted_field: str) -> float | None:
    made = _sum_field(games, made_field)
    attempted = _sum_field(games, attempted_field)
    if attempted <= 0:
        return None
    return round(made / attempted, 4)


def _summarize_rolling_window(games: list[dict[str, Any]], window: int) -> dict[str, Any]:
    selected = games[:window]
    totals: dict[str, float | None] = {}
    averages: dict[str, float | None] = {}

    for field in _ROLLING_COUNT_FIELDS:
        values = _numeric_values(selected, field)
        totals[field] = round(sum(values), 4) if values else None
        averages[field] = round(sum(values) / len(values), 4) if values else None

    averages["points_rebounds_assists"] = None
    if all(averages.get(field) is not None for field in ("points", "rebounds", "assists")):
        averages["points_rebounds_assists"] = round(
            float(averages["points"])
            + float(averages["rebounds"])
            + float(averages["assists"]),
            4,
        )

    shooting = {
        "field_goal_percentage": _weighted_percentage(
            selected, "field_goals_made", "field_goals_attempted"
        ),
        "three_point_percentage": _weighted_percentage(
            selected, "three_pointers_made", "three_pointers_attempted"
        ),
        "free_throw_percentage": _weighted_percentage(
            selected, "free_throws_made", "free_throws_attempted"
        ),
    }

    return {
        "window": window,
        "games_available": len(games),
        "games_used": len(selected),
        "complete_window": len(selected) == window,
        "most_recent_game_date": selected[0].get("game_date") if selected else None,
        "oldest_game_date": selected[-1].get("game_date") if selected else None,
        "averages": averages,
        "totals": totals,
        "shooting": shooting,
    }


def get_player_rolling_stats_dataset(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    windows: str | Iterable[int] = "5,10",
) -> dict[str, Any]:
    get_wnba_teams(season)
    if not isinstance(player_id, int) or isinstance(player_id, bool) or player_id <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")

    normalized_season_type = _normalize_season_type(season_type)
    normalized_windows = _normalize_windows(windows)

    game_log = get_player_game_log_dataset(
        player_id,
        season,
        season_type=normalized_season_type,
    )
    raw_games = list(game_log.get("games") or [])
    games = sorted(
        raw_games,
        key=lambda game: game.get("game_date") or "",
        reverse=True,
    )

    summaries = {
        f"last_{window}": _summarize_rolling_window(games, window)
        for window in normalized_windows
    }

    return {
        "source": game_log.get("source"),
        "source_url": game_log.get("source_url"),
        "source_endpoint": game_log.get("source_endpoint"),
        "data_type": "derived_player_rolling_statistics_from_official_game_log",
        "season": season,
        "season_type": normalized_season_type,
        "player_id": player_id,
        "windows": list(normalized_windows),
        "game_count_available": len(games),
        "retrieved_at_utc": game_log.get("retrieved_at_utc"),
        "game_log_cache_hit": game_log.get("cache_hit"),
        "rolling": summaries,
        "verification": {
            "source_player_id_matches_request": game_log.get("player_id") == player_id,
            "source_game_ids_valid": game_log.get("verification", {}).get("all_game_ids_valid"),
            "source_game_ids_unique": game_log.get("verification", {}).get("all_game_ids_unique"),
            "source_matchup_teams_mapped": game_log.get("verification", {}).get(
                "all_matchup_teams_mapped_to_registry"
            ),
        },
    }
