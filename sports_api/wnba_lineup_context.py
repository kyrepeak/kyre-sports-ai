"""Official WNBA lineup, on/off, and starter/bench role context.

Step 4G adds observed lineup and role context only. It does not contain betting
lines, projections, simulations, injury assumptions, or model probabilities.

Official sources:
- stats.wnba.com/stats/leaguedashlineups
- stats.wnba.com/stats/teamplayeronoffsummary
- stats.wnba.com/stats/leaguedashplayerstats (StarterBench split)
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import re
from threading import Lock
from time import monotonic
from typing import Any, Iterable

import httpx

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import get_current_players_dataset
from sports_api.wnba_season_stats import ALLOWED_PER_MODES

WNBA_LEAGUE_ID = "10"
WNBA_STATS_BASE_URL = "https://stats.wnba.com/stats"
WNBA_LINEUP_CONTEXT_SOURCE = "WNBA Stats API"
WNBA_LINEUP_CONTEXT_SOURCE_URL = "https://stats.wnba.com/"

LINEUPS_ENDPOINT = "leaguedashlineups"
ON_OFF_ENDPOINT = "teamplayeronoffsummary"
PLAYER_STATS_ENDPOINT = "leaguedashplayerstats"
MEASURE_TYPE = "Base"
ALLOWED_STARTER_BENCH = ("Starters", "Bench")

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


class WNBALineupContextUpstreamError(RuntimeError):
    """Raised when official WNBA lineup/context data cannot be consumed safely."""


class WNBALineupContextNotFoundError(LookupError):
    """Raised when requested lineup/role context is absent from official data."""


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


def _normalize_group_quantity(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 2 or value > 5:
        raise ValueError("WNBA group_quantity must be an integer from 2 through 5.")
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


def _registry_team_from_row(row: dict[str, Any], season: int) -> dict[str, Any] | None:
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


def _resolve_official_team_id(team_key: str, season: int) -> int:
    stable_key = _validate_team_key(team_key, season)
    dataset = get_current_players_dataset(season, current_roster_only=True)
    team_ids = [
        player.get("official_team_id")
        for player in dataset.get("players", [])
        if player.get("team_key") == stable_key
        and isinstance(player.get("official_team_id"), int)
        and player.get("official_team_id") not in (None, 0)
    ]
    if not team_ids:
        raise WNBALineupContextUpstreamError(
            f"Could not resolve an official WNBA team ID for {team_key!r}."
        )
    counts = Counter(team_ids)
    official_team_id, count = counts.most_common(1)[0]
    if sum(1 for value in counts.values() if value == count) > 1:
        raise WNBALineupContextUpstreamError(
            f"Official WNBA team ID resolution is ambiguous for {team_key!r}."
        )
    return official_team_id


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
        raise WNBALineupContextUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBALineupContextUpstreamError(
            f"Official WNBA Stats API returned a non-object payload for {endpoint}."
        )

    retrieved_at_utc = _utc_now_iso()
    with _CACHE_LOCK:
        for expired_key in [
            item_key for item_key, item in _CACHE.items() if item["expires_at"] <= now
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
        raise WNBALineupContextUpstreamError(
            f"WNBA payload is missing result sets for {result_name}."
        )

    selected = next(
        (
            item
            for item in candidates
            if isinstance(item, dict)
            and (_clean_text(item.get("name")) or "").casefold() == result_name.casefold()
        ),
        None,
    )
    if selected is None and len(candidates) == 1 and isinstance(candidates[0], dict):
        selected = candidates[0]
    if selected is None:
        raise WNBALineupContextUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBALineupContextUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    normalized_headers = [str(header) for header in headers]
    rows = [
        dict(zip(normalized_headers, row))
        for row in row_set
        if isinstance(row, (list, tuple))
    ]
    return normalized_headers, rows


def _require_headers(headers: list[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(headers))
    if missing:
        raise WNBALineupContextUpstreamError(
            f"WNBA {label} response is missing required fields: {', '.join(missing)}."
        )


def _base_stats(row: dict[str, Any]) -> dict[str, Any]:
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


def _extract_group_player_ids(group_id: Any) -> list[int]:
    text = _clean_text(group_id)
    if text is None:
        return []
    return [int(value) for value in re.findall(r"\d+", text)]


def _split_group_names(group_name: Any) -> list[str]:
    text = _clean_text(group_name)
    if text is None:
        return []
    return [part.strip() for part in text.split(" - ") if part.strip()]


def _normalize_lineup(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team_from_row(row, season)
    player_ids = _extract_group_player_ids(row.get("GROUP_ID"))
    names = _split_group_names(row.get("GROUP_NAME"))
    members = [
        {
            "player_id": player_id,
            "player_name": names[index] if index < len(names) else None,
        }
        for index, player_id in enumerate(player_ids)
    ]
    return {
        "group_set": _clean_text(row.get("GROUP_SET")),
        "group_id": _clean_text(row.get("GROUP_ID")),
        "group_name": _clean_text(row.get("GROUP_NAME")),
        "player_ids": player_ids,
        "member_names": names,
        "members": members,
        "member_count": len(player_ids),
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
        "stats": _base_stats(row),
        "mapped_to_registry": team is not None,
    }


def _normalize_on_off_row(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team_from_row(row, season)
    return {
        "player_id": _to_int(row.get("VS_PLAYER_ID")),
        "player_name": _clean_text(row.get("VS_PLAYER_NAME")),
        "court_status": _clean_text(row.get("COURT_STATUS")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_key": team["team_key"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "games_played": _to_int(row.get("GP")),
        "minutes": _to_float(row.get("MIN")),
        "plus_minus": _to_float(row.get("PLUS_MINUS")),
        "offensive_rating": _to_float(row.get("OFF_RATING")),
        "defensive_rating": _to_float(row.get("DEF_RATING")),
        "net_rating": _to_float(row.get("NET_RATING")),
        "mapped_to_registry": team is not None,
    }


def _normalize_overall_team(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team_from_row(row, season)
    return {
        "group_set": _clean_text(row.get("GROUP_SET")),
        "group_value": _clean_text(row.get("GROUP_VALUE")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_name": _clean_text(row.get("TEAM_NAME")),
        "team_key": team["team_key"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "games_played": _to_int(row.get("GP")),
        "record": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "stats": _base_stats(row),
        "mapped_to_registry": team is not None,
    }


def _difference(on_value: float | None, off_value: float | None) -> float | None:
    if on_value is None or off_value is None:
        return None
    return on_value - off_value


def _join_on_off(
    on_rows: list[dict[str, Any]],
    off_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    on_by_id = {row["player_id"]: row for row in on_rows if row["player_id"] is not None}
    off_by_id = {row["player_id"]: row for row in off_rows if row["player_id"] is not None}
    player_ids = sorted(set(on_by_id) | set(off_by_id))
    joined: list[dict[str, Any]] = []
    for player_id in player_ids:
        on = on_by_id.get(player_id)
        off = off_by_id.get(player_id)
        name = (on or off or {}).get("player_name")
        joined.append(
            {
                "player_id": player_id,
                "player_name": name,
                "on_court": on,
                "off_court": off,
                "has_complete_pair": on is not None and off is not None,
                "deltas_on_minus_off": {
                    "plus_minus": _difference(
                        on.get("plus_minus") if on else None,
                        off.get("plus_minus") if off else None,
                    ),
                    "offensive_rating": _difference(
                        on.get("offensive_rating") if on else None,
                        off.get("offensive_rating") if off else None,
                    ),
                    "defensive_rating": _difference(
                        on.get("defensive_rating") if on else None,
                        off.get("defensive_rating") if off else None,
                    ),
                    "net_rating": _difference(
                        on.get("net_rating") if on else None,
                        off.get("net_rating") if off else None,
                    ),
                },
            }
        )
    return joined


def _normalize_role_row(row: dict[str, Any], season: int, role: str) -> dict[str, Any]:
    team = _registry_team_from_row(row, season)
    return {
        "role": role,
        "player_id": _to_int(row.get("PLAYER_ID")),
        "player_name": _clean_text(row.get("PLAYER_NAME")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_key": team["team_key"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "games_played": _to_int(row.get("GP")),
        "record": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "stats": _base_stats(row),
        "mapped_to_registry": team is not None,
    }


def _lineup_params(
    season: int,
    season_type: str,
    group_quantity: int,
    last_n_games: int,
    per_mode: str,
    official_team_id: int | None,
) -> list[tuple[str, Any]]:
    return [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("GroupQuantity", str(group_quantity)),
        ("LastNGames", str(last_n_games)),
        ("MeasureType", MEASURE_TYPE),
        ("PerMode", per_mode),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("Period", "0"),
        ("PlusMinus", "N"),
        ("Rank", "N"),
        ("Conference", ""),
        ("DateFrom", ""),
        ("DateTo", ""),
        ("Division", ""),
        ("GameSegment", ""),
        ("Location", ""),
        ("Outcome", ""),
        ("PORound", ""),
        ("SeasonSegment", ""),
        ("ShotClockRange", ""),
        ("TeamID", "" if official_team_id is None else str(official_team_id)),
        ("VsConference", ""),
        ("VsDivision", ""),
    ]


def _on_off_params(
    season: int,
    season_type: str,
    last_n_games: int,
    per_mode: str,
    official_team_id: int,
) -> list[tuple[str, Any]]:
    return [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("TeamID", str(official_team_id)),
        ("LastNGames", str(last_n_games)),
        ("MeasureType", MEASURE_TYPE),
        ("PerMode", per_mode),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("Period", "0"),
        ("PlusMinus", "N"),
        ("Rank", "N"),
        ("DateFrom", ""),
        ("DateTo", ""),
        ("GameSegment", ""),
        ("Location", ""),
        ("Outcome", ""),
        ("SeasonSegment", ""),
        ("VsConference", ""),
        ("VsDivision", ""),
    ]


def _role_params(
    season: int,
    season_type: str,
    last_n_games: int,
    per_mode: str,
    starter_bench: str,
) -> list[tuple[str, Any]]:
    return [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("StarterBench", starter_bench),
        ("LastNGames", str(last_n_games)),
        ("MeasureType", MEASURE_TYPE),
        ("PerMode", per_mode),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("Period", "0"),
        ("PlusMinus", "N"),
        ("Rank", "N"),
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
        ("Location", ""),
        ("Outcome", ""),
        ("PORound", "0"),
        ("PlayerExperience", ""),
        ("PlayerPosition", ""),
        ("SeasonSegment", ""),
        ("ShotClockRange", ""),
        ("TeamID", ""),
        ("TwoWay", ""),
        ("VsConference", ""),
        ("VsDivision", ""),
        ("Weight", ""),
    ]


def _window_scope(last_n_games: int) -> str:
    return "season_to_date" if last_n_games == 0 else f"last_{last_n_games}_games"


def get_lineups_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    group_quantity: int = 5,
    last_n_games: int = 0,
    per_mode: str = "PerGame",
    team_key: str | None = None,
    player_id: int | None = None,
) -> dict[str, Any]:
    get_wnba_teams(season)
    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    per_mode = _normalize_choice(per_mode, ALLOWED_PER_MODES, "per_mode")
    group_quantity = _normalize_group_quantity(group_quantity)
    last_n_games = _normalize_last_n_games(last_n_games)
    team_key = _validate_team_key(team_key, season)
    player_id = _normalize_player_id(player_id)
    official_team_id = (
        _resolve_official_team_id(team_key, season) if team_key is not None else None
    )

    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        LINEUPS_ENDPOINT,
        _lineup_params(
            season,
            season_type,
            group_quantity,
            last_n_games,
            per_mode,
            official_team_id,
        ),
    )
    headers, rows = _result_set(payload, "Lineups")
    _require_headers(
        headers,
        {"GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "MIN"},
        "lineups",
    )

    lineups = [_normalize_lineup(row, season) for row in rows]
    if team_key is not None:
        lineups = [lineup for lineup in lineups if lineup["team_key"] == team_key]
    if player_id is not None:
        lineups = [lineup for lineup in lineups if player_id in lineup["player_ids"]]
    lineups.sort(
        key=lambda lineup: (
            -(lineup["stats"]["minutes"] or 0.0),
            lineup["team_full_name"] or "",
            lineup["group_name"] or "",
        )
    )

    composite_ids = [
        (lineup["official_team_id"], lineup["group_id"])
        for lineup in lineups
        if lineup["official_team_id"] is not None and lineup["group_id"] is not None
    ]
    duplicate_groups = sorted(
        {group for group in composite_ids if composite_ids.count(group) > 1},
        key=lambda item: (item[0], item[1]),
    )
    wrong_size = [
        lineup["group_id"]
        for lineup in lineups
        if lineup["member_count"] != group_quantity
    ]
    unmapped = sum(not lineup["mapped_to_registry"] for lineup in lineups)

    return {
        "source": WNBA_LINEUP_CONTEXT_SOURCE,
        "source_url": WNBA_LINEUP_CONTEXT_SOURCE_URL,
        "source_endpoint": LINEUPS_ENDPOINT,
        "data_type": "official_lineup_stats",
        "measure_type": MEASURE_TYPE,
        "season": season,
        "season_type": season_type,
        "group_quantity": group_quantity,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": _window_scope(last_n_games),
        "filters": {"team_key": team_key, "player_id": player_id},
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_header_count": len(headers),
        "lineup_count": len(lineups),
        "lineups": lineups,
        "verification": {
            "schema_verified": True,
            "all_rows_mapped_to_registry": unmapped == 0,
            "unmapped_team_count": unmapped,
            "all_groups_match_requested_quantity": not wrong_size,
            "wrong_size_group_ids": wrong_size,
            "composite_group_ids_unique": not duplicate_groups,
            "duplicate_composite_group_ids": [
                {"official_team_id": team_id, "group_id": group_id}
                for team_id, group_id in duplicate_groups
            ],
        },
    }


def get_team_on_off_dataset(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "Totals",
) -> dict[str, Any]:
    stable_key = _validate_team_key(team_key, season)
    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    per_mode = _normalize_choice(per_mode, ALLOWED_PER_MODES, "per_mode")
    last_n_games = _normalize_last_n_games(last_n_games)
    official_team_id = _resolve_official_team_id(stable_key, season)

    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        ON_OFF_ENDPOINT,
        _on_off_params(season, season_type, last_n_games, per_mode, official_team_id),
    )
    overall_headers, overall_rows = _result_set(payload, "OverallTeamPlayerOnOffSummary")
    on_headers, on_rows_raw = _result_set(payload, "PlayersOnCourtTeamPlayerOnOffSummary")
    off_headers, off_rows_raw = _result_set(payload, "PlayersOffCourtTeamPlayerOnOffSummary")

    _require_headers(
        on_headers,
        {"TEAM_ID", "VS_PLAYER_ID", "VS_PLAYER_NAME", "COURT_STATUS", "GP", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING"},
        "on-court summary",
    )
    _require_headers(
        off_headers,
        {"TEAM_ID", "VS_PLAYER_ID", "VS_PLAYER_NAME", "COURT_STATUS", "GP", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING"},
        "off-court summary",
    )
    _require_headers(overall_headers, {"TEAM_ID", "TEAM_NAME", "GP", "MIN"}, "on/off overall")

    on_rows = [_normalize_on_off_row(row, season) for row in on_rows_raw]
    off_rows = [_normalize_on_off_row(row, season) for row in off_rows_raw]
    overall = [_normalize_overall_team(row, season) for row in overall_rows]
    players = _join_on_off(on_rows, off_rows)
    players.sort(key=lambda row: row["player_name"] or "")

    incomplete = [row["player_id"] for row in players if not row["has_complete_pair"]]
    unmapped_on = sum(not row["mapped_to_registry"] for row in on_rows)
    unmapped_off = sum(not row["mapped_to_registry"] for row in off_rows)

    return {
        "source": WNBA_LINEUP_CONTEXT_SOURCE,
        "source_url": WNBA_LINEUP_CONTEXT_SOURCE_URL,
        "source_endpoint": ON_OFF_ENDPOINT,
        "data_type": "official_team_player_on_off_summary",
        "measure_type": MEASURE_TYPE,
        "season": season,
        "season_type": season_type,
        "team_key": stable_key,
        "official_team_id": official_team_id,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": _window_scope(last_n_games),
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "overall_team_summary": overall,
        "player_count": len(players),
        "players": players,
        "verification": {
            "schema_verified": True,
            "on_court_player_count": len(on_rows),
            "off_court_player_count": len(off_rows),
            "complete_pair_count": sum(row["has_complete_pair"] for row in players),
            "all_players_have_on_off_pair": not incomplete,
            "incomplete_player_ids": incomplete,
            "all_on_court_rows_mapped_to_registry": unmapped_on == 0,
            "all_off_court_rows_mapped_to_registry": unmapped_off == 0,
        },
    }


def _get_role_rows(
    player_id: int,
    season: int,
    season_type: str,
    last_n_games: int,
    per_mode: str,
    role: str,
) -> tuple[list[dict[str, Any]], str, bool, int]:
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        PLAYER_STATS_ENDPOINT,
        _role_params(season, season_type, last_n_games, per_mode, role),
    )
    headers, rows = _result_set(payload, "LeagueDashPlayerStats")
    _require_headers(
        headers,
        {"PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "MIN", "PTS", "REB", "AST"},
        f"{role.lower()} player role split",
    )
    normalized = [
        _normalize_role_row(row, season, role)
        for row in rows
        if _to_int(row.get("PLAYER_ID")) == player_id
    ]
    return normalized, retrieved_at_utc, cache_hit, len(headers)


def get_player_role_context_dataset(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "PerGame",
) -> dict[str, Any]:
    get_wnba_teams(season)
    player_id = _normalize_player_id(player_id)
    assert player_id is not None
    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    per_mode = _normalize_choice(per_mode, ALLOWED_PER_MODES, "per_mode")
    last_n_games = _normalize_last_n_games(last_n_games)

    starter_rows, starter_retrieved, starter_cache, starter_header_count = _get_role_rows(
        player_id,
        season,
        season_type,
        last_n_games,
        per_mode,
        "Starters",
    )
    bench_rows, bench_retrieved, bench_cache, bench_header_count = _get_role_rows(
        player_id,
        season,
        season_type,
        last_n_games,
        per_mode,
        "Bench",
    )

    if not starter_rows and not bench_rows:
        raise WNBALineupContextNotFoundError(
            f"No official WNBA starter/bench role data was found for player {player_id} in {season}."
        )

    starter = starter_rows[0] if len(starter_rows) == 1 else None
    bench = bench_rows[0] if len(bench_rows) == 1 else None
    starter_gp = starter["games_played"] if starter else None
    bench_gp = bench["games_played"] if bench else None
    total_role_games = (starter_gp or 0) + (bench_gp or 0)
    starter_game_share = (
        (starter_gp or 0) / total_role_games if total_role_games > 0 else None
    )
    if starter_gp is None and bench_gp is None:
        primary_role = None
    elif (starter_gp or 0) > (bench_gp or 0):
        primary_role = "starter"
    elif (bench_gp or 0) > (starter_gp or 0):
        primary_role = "bench"
    else:
        primary_role = "even"

    return {
        "source": WNBA_LINEUP_CONTEXT_SOURCE,
        "source_url": WNBA_LINEUP_CONTEXT_SOURCE_URL,
        "source_endpoint": PLAYER_STATS_ENDPOINT,
        "data_type": "official_player_starter_bench_role_context",
        "measure_type": MEASURE_TYPE,
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": _window_scope(last_n_games),
        "retrieved_at_utc": max(starter_retrieved, bench_retrieved),
        "cache_hit": starter_cache and bench_cache,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "starter": starter,
        "bench": bench,
        "starter_rows": starter_rows,
        "bench_rows": bench_rows,
        "role_summary": {
            "starter_games": starter_gp,
            "bench_games": bench_gp,
            "starter_game_share": starter_game_share,
            "primary_observed_role": primary_role,
        },
        "verification": {
            "schema_verified": True,
            "starter_source_header_count": starter_header_count,
            "bench_source_header_count": bench_header_count,
            "starter_row_count": len(starter_rows),
            "bench_row_count": len(bench_rows),
            "starter_row_unambiguous": len(starter_rows) <= 1,
            "bench_row_unambiguous": len(bench_rows) <= 1,
            "all_rows_mapped_to_registry": all(
                row["mapped_to_registry"] for row in starter_rows + bench_rows
            ),
        },
    }
