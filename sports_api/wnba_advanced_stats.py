"""Official WNBA advanced player and team statistics.

Step 4F exposes observed advanced metrics from the official WNBA Stats API.
It contains no betting lines, projections, simulations, injury assumptions, or
model probabilities.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Iterable

import httpx

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_season_stats import ALLOWED_PER_MODES

WNBA_LEAGUE_ID = "10"
WNBA_STATS_BASE_URL = "https://stats.wnba.com/stats"
WNBA_ADVANCED_SOURCE = "WNBA Stats API"
WNBA_ADVANCED_SOURCE_URL = "https://stats.wnba.com/"
PLAYER_ADVANCED_ENDPOINT = "leaguedashplayerstats"
TEAM_ADVANCED_ENDPOINT = "leaguedashteamstats"
MEASURE_TYPE = "Advanced"

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


class WNBAAdvancedStatsUpstreamError(RuntimeError):
    """Raised when official WNBA advanced statistics cannot be consumed safely."""


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


def _normalize_choice(value: str, allowed: Iterable[str], label: str) -> str:
    normalized = str(value).strip()
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(normalized.casefold())
    if resolved is None:
        choices = ", ".join(allowed)
        raise ValueError(f"Unsupported WNBA {label} {value!r}. Allowed values: {choices}.")
    return resolved


def _normalize_last_n_games(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 100:
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    return value


def _normalize_player_id(value: int | None) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _validate_team_key(team_key: str | None, season: int) -> str | None:
    if team_key is None:
        return None
    normalized = team_key.strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == normalized:
            return team["team_key"]
    raise ValueError(f"WNBA team key {team_key!r} was not found for the {season} season.")


def _cache_key(endpoint: str, params: Iterable[tuple[str, Any]]) -> tuple[Any, ...]:
    return endpoint, tuple((str(key), str(value)) for key, value in params)


def _request_stats_json(
    endpoint: str,
    params: list[tuple[str, Any]],
) -> tuple[dict[str, Any], str, bool]:
    key = _cache_key(endpoint, params)
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return deepcopy(cached["payload"]), cached["retrieved_at_utc"], True
        if cached:
            _CACHE.pop(key, None)

    try:
        response = httpx.get(
            f"{WNBA_STATS_BASE_URL}/{endpoint}",
            params=params,
            headers=WNBA_STATS_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WNBAAdvancedStatsUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBAAdvancedStatsUpstreamError(
            f"Official WNBA Stats API returned a non-object payload for {endpoint}."
        )

    retrieved_at_utc = _utc_now_iso()
    with _CACHE_LOCK:
        for expired_key in [
            item_key
            for item_key, item in _CACHE.items()
            if item["expires_at"] <= now
        ]:
            _CACHE.pop(expired_key, None)
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[key] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + CACHE_TTL_SECONDS,
        }

    return payload, retrieved_at_utc, False


def _result_set(
    payload: dict[str, Any],
    result_name: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    raw = payload.get("resultSets")
    if raw is None:
        raw = payload.get("resultSet")
    candidates = [raw] if isinstance(raw, dict) else raw
    if not isinstance(candidates, list):
        raise WNBAAdvancedStatsUpstreamError(
            f"WNBA payload is missing result sets for {result_name}."
        )

    selected = next(
        (
            item
            for item in candidates
            if isinstance(item, dict)
            and (_clean_text(item.get("name")) or "").casefold()
            == result_name.casefold()
        ),
        None,
    )
    if selected is None and len(candidates) == 1 and isinstance(candidates[0], dict):
        selected = candidates[0]
    if selected is None:
        raise WNBAAdvancedStatsUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBAAdvancedStatsUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    normalized_headers = [str(header) for header in headers]
    rows = [
        dict(zip(normalized_headers, row))
        for row in row_set
        if isinstance(row, (list, tuple))
    ]
    return normalized_headers, rows


def _validate_advanced_headers(headers: list[str], *, player: bool) -> None:
    header_set = set(headers)
    markers = {
        "OFF_RATING", "E_OFF_RATING", "DEF_RATING", "E_DEF_RATING",
        "NET_RATING", "E_NET_RATING", "AST_PCT", "AST_RATIO",
        "E_AST_RATIO", "REB_PCT", "E_REB_PCT", "TS_PCT", "EFG_PCT",
        "PACE", "E_PACE", "PIE",
    }
    if player:
        markers |= {"USG_PCT", "E_USG_PCT"}

    minimum = 5 if player else 4
    found = len(header_set & markers)
    if found < minimum:
        raise WNBAAdvancedStatsUpstreamError(
            "WNBA advanced-stats response does not contain enough advanced "
            f"metric fields (found {found}; expected at least {minimum})."
        )
    if player and not ({"USG_PCT", "E_USG_PCT"} & header_set):
        raise WNBAAdvancedStatsUpstreamError(
            "WNBA advanced player response is missing usage percentage."
        )
    if not ({"PACE", "E_PACE"} & header_set):
        raise WNBAAdvancedStatsUpstreamError(
            "WNBA advanced-stats response is missing pace."
        )


def _registry_team(row: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean_text(row.get("TEAM_ABBREVIATION")) or "").casefold(),
        (_clean_text(row.get("TEAM_NAME")) or "").casefold(),
    }
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


def _advanced_metrics(row: dict[str, Any], *, include_usage: bool) -> dict[str, Any]:
    metrics = {
        "estimated_offensive_rating": _to_float(row.get("E_OFF_RATING")),
        "offensive_rating": _to_float(row.get("OFF_RATING")),
        "estimated_defensive_rating": _to_float(row.get("E_DEF_RATING")),
        "defensive_rating": _to_float(row.get("DEF_RATING")),
        "estimated_net_rating": _to_float(row.get("E_NET_RATING")),
        "net_rating": _to_float(row.get("NET_RATING")),
        "assist_percentage": _to_float(row.get("AST_PCT")),
        "assist_to_turnover_ratio": _to_float(row.get("AST_TO")),
        "estimated_assist_ratio": _to_float(row.get("E_AST_RATIO")),
        "assist_ratio": _to_float(row.get("AST_RATIO")),
        "estimated_offensive_rebound_percentage": _to_float(row.get("E_OREB_PCT")),
        "offensive_rebound_percentage": _to_float(row.get("OREB_PCT")),
        "estimated_defensive_rebound_percentage": _to_float(row.get("E_DREB_PCT")),
        "defensive_rebound_percentage": _to_float(row.get("DREB_PCT")),
        "estimated_rebound_percentage": _to_float(row.get("E_REB_PCT")),
        "rebound_percentage": _to_float(row.get("REB_PCT")),
        "estimated_turnover_percentage": _to_float(row.get("E_TOV_PCT")),
        "team_turnover_percentage": _to_float(row.get("TM_TOV_PCT")),
        "effective_field_goal_percentage": _to_float(row.get("EFG_PCT")),
        "true_shooting_percentage": _to_float(row.get("TS_PCT")),
        "estimated_pace": _to_float(row.get("E_PACE")),
        "pace": _to_float(row.get("PACE")),
        "pace_per_40": _to_float(row.get("PACE_PER40")),
        "possessions": _to_float(row.get("POSS")),
        "player_impact_estimate": _to_float(row.get("PIE")),
    }
    if include_usage:
        metrics |= {
            "estimated_usage_percentage": _to_float(row.get("E_USG_PCT")),
            "usage_percentage": _to_float(row.get("USG_PCT")),
            "field_goals_made": _to_float(row.get("FGM")),
            "field_goals_attempted": _to_float(row.get("FGA")),
            "field_goals_made_per_game": _to_float(row.get("FGM_PG")),
            "field_goals_attempted_per_game": _to_float(row.get("FGA_PG")),
            "field_goal_percentage": _to_float(row.get("FG_PCT")),
        }
    return metrics


def _normalize_player(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team(row, season)
    return {
        "player_id": _to_int(row.get("PLAYER_ID")),
        "player_name": _clean_text(row.get("PLAYER_NAME")),
        "nickname": _clean_text(row.get("NICKNAME")),
        "age": _to_float(row.get("AGE")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_key": team["team_key"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "conference": team["conference"] if team else None,
        "games_played": _to_int(row.get("GP")),
        "record": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "minutes": _to_float(row.get("MIN")),
        "advanced": _advanced_metrics(row, include_usage=True),
        "mapped_to_registry": team is not None,
    }


def _normalize_team(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team(row, season)
    return {
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_name": _clean_text(row.get("TEAM_NAME")),
        "team_key": team["team_key"] if team else None,
        "team_abbreviation": team["abbreviation"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "conference": team["conference"] if team else None,
        "games_played": _to_int(row.get("GP")),
        "record": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "minutes": _to_float(row.get("MIN")),
        "advanced": _advanced_metrics(row, include_usage=False),
        "mapped_to_registry": team is not None,
    }


def _params(
    season: int,
    season_type: str,
    last_n_games: int,
    per_mode: str,
    *,
    player: bool,
) -> list[tuple[str, Any]]:
    # LeagueID first is deliberate: WNBA Stats has shown ordering sensitivity.
    params: list[tuple[str, Any]] = [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("MeasureType", MEASURE_TYPE),
        ("PerMode", per_mode),
        ("LastNGames", str(last_n_games)),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("Period", "0"),
        ("PlusMinus", "N"),
        ("Rank", "N"),
    ]
    if player:
        params += [
            ("College", ""), ("Country", ""), ("DraftPick", ""), ("DraftYear", ""),
            ("Height", ""), ("Weight", ""),
        ]
    params += [
        ("Conference", ""), ("DateFrom", ""), ("DateTo", ""), ("Division", ""),
        ("GameScope", ""), ("GameSegment", ""), ("Location", ""), ("Outcome", ""),
        ("PORound", "0"), ("PlayerExperience", ""), ("PlayerPosition", ""),
        ("SeasonSegment", ""), ("ShotClockRange", ""), ("StarterBench", ""),
        ("TeamID", ""), ("TwoWay", ""), ("VsConference", ""), ("VsDivision", ""),
    ]
    return params


def _window_scope(last_n_games: int) -> str:
    return "season_to_date" if last_n_games == 0 else f"last_{last_n_games}_games"


def _player_verification(players: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [player["player_id"] for player in players if player["player_id"] is not None]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    unmapped = sum(not player["mapped_to_registry"] for player in players)
    return {
        "advanced_schema_verified": True,
        "all_rows_have_player_ids": len(ids) == len(players),
        "all_rows_mapped_to_registry": unmapped == 0,
        "unmapped_team_count": unmapped,
        "player_ids_unique": not duplicates,
        "duplicate_player_ids": duplicates,
        "usage_metric_available_for_all_rows": all(
            p["advanced"]["usage_percentage"] is not None
            or p["advanced"]["estimated_usage_percentage"] is not None
            for p in players
        ),
        "pace_metric_available_for_all_rows": all(
            p["advanced"]["pace"] is not None
            or p["advanced"]["estimated_pace"] is not None
            for p in players
        ),
    }


def _team_verification(teams: list[dict[str, Any]], registry_count: int) -> dict[str, Any]:
    ids = [team["official_team_id"] for team in teams if team["official_team_id"] is not None]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    unmapped = sum(not team["mapped_to_registry"] for team in teams)
    mapped_keys = {team["team_key"] for team in teams if team["team_key"] is not None}
    return {
        "advanced_schema_verified": True,
        "all_rows_have_official_team_ids": len(ids) == len(teams),
        "all_rows_mapped_to_registry": unmapped == 0,
        "unmapped_team_count": unmapped,
        "official_team_ids_unique": not duplicates,
        "duplicate_official_team_ids": duplicates,
        "pace_metric_available_for_all_rows": all(
            t["advanced"]["pace"] is not None
            or t["advanced"]["estimated_pace"] is not None
            for t in teams
        ),
        "mapped_registry_team_count": len(mapped_keys),
        "registry_team_count": registry_count,
    }


def get_player_advanced_stats_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "PerGame",
    team_key: str | None = None,
    player_id: int | None = None,
) -> dict[str, Any]:
    get_wnba_teams(season)
    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    per_mode = _normalize_choice(per_mode, ALLOWED_PER_MODES, "per_mode")
    last_n_games = _normalize_last_n_games(last_n_games)
    team_key = _validate_team_key(team_key, season)
    player_id = _normalize_player_id(player_id)

    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        PLAYER_ADVANCED_ENDPOINT,
        _params(season, season_type, last_n_games, per_mode, player=True),
    )
    headers, rows = _result_set(payload, "LeagueDashPlayerStats")
    _validate_advanced_headers(headers, player=True)
    players = [_normalize_player(row, season) for row in rows]
    if team_key is not None:
        players = [player for player in players if player["team_key"] == team_key]
    if player_id is not None:
        players = [player for player in players if player["player_id"] == player_id]
    players.sort(key=lambda player: (player["player_name"] or "", player["player_id"] or 0))

    return {
        "source": WNBA_ADVANCED_SOURCE,
        "source_url": WNBA_ADVANCED_SOURCE_URL,
        "source_endpoint": PLAYER_ADVANCED_ENDPOINT,
        "data_type": "official_advanced_player_stats",
        "measure_type": MEASURE_TYPE,
        "season": season,
        "season_type": season_type,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": _window_scope(last_n_games),
        "filters": {"team_key": team_key, "player_id": player_id},
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_header_count": len(headers),
        "player_count": len(players),
        "players": players,
        "verification": _player_verification(players),
    }


def get_team_advanced_stats_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "PerGame",
    team_key: str | None = None,
) -> dict[str, Any]:
    registry = get_wnba_teams(season)
    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    per_mode = _normalize_choice(per_mode, ALLOWED_PER_MODES, "per_mode")
    last_n_games = _normalize_last_n_games(last_n_games)
    team_key = _validate_team_key(team_key, season)

    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        TEAM_ADVANCED_ENDPOINT,
        _params(season, season_type, last_n_games, per_mode, player=False),
    )
    headers, rows = _result_set(payload, "LeagueDashTeamStats")
    _validate_advanced_headers(headers, player=False)
    teams = [_normalize_team(row, season) for row in rows]
    if team_key is not None:
        teams = [team for team in teams if team["team_key"] == team_key]
    teams.sort(key=lambda team: team["team_full_name"] or team["team_name"] or "")

    return {
        "source": WNBA_ADVANCED_SOURCE,
        "source_url": WNBA_ADVANCED_SOURCE_URL,
        "source_endpoint": TEAM_ADVANCED_ENDPOINT,
        "data_type": "official_advanced_team_stats",
        "measure_type": MEASURE_TYPE,
        "season": season,
        "season_type": season_type,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": _window_scope(last_n_games),
        "filters": {"team_key": team_key},
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_header_count": len(headers),
        "team_count": len(teams),
        "teams": teams,
        "verification": _team_verification(teams, len(registry)),
    }
