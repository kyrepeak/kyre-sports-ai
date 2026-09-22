"""Official WNBA team game logs, recent form, and head-to-head history.

Step 4J is an observed-history layer only. It does not create projections,
betting probabilities, or matchup ratings.

Primary official source:
- stats.wnba.com/stats/leaguegamelog with LeagueID=10 and PlayerOrTeam=T

The league game-log feed returns one team row per game. This collector pairs the
two rows sharing a GAME_ID so points allowed, opponent statistics, and margins
remain traceable to the official source rather than inferred from schedule data.
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

WNBA_LEAGUE_ID = "10"
WNBA_STATS_BASE_URL = "https://stats.wnba.com/stats"
WNBA_TEAM_HISTORY_SOURCE = "WNBA Stats API"
WNBA_TEAM_HISTORY_SOURCE_URL = "https://stats.wnba.com/"
TEAM_GAME_LOG_ENDPOINT = "leaguegamelog"

PLAYER_OR_TEAM = "T"
SORTER = "DATE"
DIRECTION = "DESC"
ALLOWED_LOCATIONS = ("All", "Home", "Away")

CACHE_TTL_SECONDS = 90
CACHE_MAX_ENTRIES = 256

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


class WNBATeamHistoryUpstreamError(RuntimeError):
    """Raised when official WNBA team history cannot be consumed safely."""


class WNBATeamHistoryNotFoundError(LookupError):
    """Raised when requested WNBA team/history rows do not exist."""


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
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: {choices}."
        )
    return resolved


def _normalize_last_n_games(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 100:
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    return value


def _validate_team_key(team_key: str, season: int) -> str:
    normalized = str(team_key).strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == normalized:
            return team["team_key"]
    raise ValueError(f"WNBA team key {team_key!r} was not found for the {season} season.")


def _registry_team_from_values(
    abbreviation: Any,
    name: Any,
    season: int,
) -> dict[str, Any] | None:
    values = {
        (_clean_text(abbreviation) or "").casefold(),
        (_clean_text(name) or "").casefold(),
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


def _registry_team_from_abbreviation(
    abbreviation: str | None,
    season: int,
) -> dict[str, Any] | None:
    text = _clean_text(abbreviation)
    if text is None:
        return None
    for team in get_wnba_teams(season):
        if team["abbreviation"].casefold() == text.casefold():
            return team
    return None


def _game_date_iso(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_matchup(matchup: Any, season: int) -> dict[str, Any]:
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
    team = _registry_team_from_abbreviation(team_abbreviation, season)
    opponent = _registry_team_from_abbreviation(opponent_abbreviation, season)

    return {
        "raw": text,
        "location": location,
        "team_abbreviation": team_abbreviation,
        "team_key": team["team_key"] if team else None,
        "opponent_abbreviation": opponent_abbreviation,
        "opponent_team_key": opponent["team_key"] if opponent else None,
    }


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
        raise WNBATeamHistoryUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBATeamHistoryUpstreamError(
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
        raise WNBATeamHistoryUpstreamError(
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
        raise WNBATeamHistoryUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBATeamHistoryUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    normalized_headers = [str(header) for header in headers]
    rows = [
        dict(zip(normalized_headers, row))
        for row in row_set
        if isinstance(row, (list, tuple))
    ]
    return normalized_headers, rows


def _require_headers(headers: list[str]) -> None:
    required = {
        "TEAM_ID",
        "TEAM_ABBREVIATION",
        "TEAM_NAME",
        "GAME_ID",
        "GAME_DATE",
        "MATCHUP",
        "WL",
        "MIN",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "PF",
        "PTS",
        "PLUS_MINUS",
    }
    missing = sorted(required - set(headers))
    if missing:
        raise WNBATeamHistoryUpstreamError(
            "WNBA team game-log response is missing required fields: "
            + ", ".join(missing)
            + "."
        )


def _normalize_team_game(row: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_values(
        row.get("TEAM_ABBREVIATION"),
        row.get("TEAM_NAME"),
        season,
    )
    matchup = _parse_matchup(row.get("MATCHUP"), season)
    game_id = _clean_text(row.get("GAME_ID"))

    return {
        "season_id": _clean_text(row.get("SEASON_ID")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_name_source": _clean_text(row.get("TEAM_NAME")),
        "team_key": registry["team_key"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "conference": registry["conference"] if registry else None,
        "mapped_to_registry": registry is not None,
        "game_id": game_id,
        "game_id_valid": bool(game_id and len(game_id) == 10 and game_id.isdigit()),
        "game_date_raw": _clean_text(row.get("GAME_DATE")),
        "game_date": _game_date_iso(row.get("GAME_DATE")),
        "matchup": matchup,
        "location": matchup["location"],
        "opponent_team_key": matchup["opponent_team_key"],
        "opponent_abbreviation": matchup["opponent_abbreviation"],
        "result": _clean_text(row.get("WL")),
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
        "steals": _to_float(row.get("STL")),
        "blocks": _to_float(row.get("BLK")),
        "turnovers": _to_float(row.get("TOV")),
        "personal_fouls": _to_float(row.get("PF")),
        "points": _to_float(row.get("PTS")),
        "plus_minus": _to_float(row.get("PLUS_MINUS")),
        "video_available": _to_int(row.get("VIDEO_AVAILABLE")),
        "opponent_points": None,
        "point_margin_from_scores": None,
        "opponent_stats": None,
        "paired_opponent_row": False,
    }


def _opponent_stats(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_team_id": row["official_team_id"],
        "team_key": row["team_key"],
        "team_full_name": row["team_full_name"],
        "points": row["points"],
        "rebounds": row["rebounds"],
        "assists": row["assists"],
        "turnovers": row["turnovers"],
        "field_goals_made": row["field_goals_made"],
        "field_goals_attempted": row["field_goals_attempted"],
        "three_pointers_made": row["three_pointers_made"],
        "three_pointers_attempted": row["three_pointers_attempted"],
        "free_throws_made": row["free_throws_made"],
        "free_throws_attempted": row["free_throws_attempted"],
    }


def _difference(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _pair_game_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_game: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        game_id = row.get("game_id")
        if game_id is not None:
            by_game.setdefault(game_id, []).append(row)

    invalid_pair_game_ids: list[str] = []
    opponent_mismatches: list[str] = []
    paired_count = 0

    for game_id, game_rows in by_game.items():
        if len(game_rows) != 2:
            invalid_pair_game_ids.append(game_id)
            continue

        first, second = game_rows
        first["opponent_points"] = second.get("points")
        second["opponent_points"] = first.get("points")
        first["point_margin_from_scores"] = _difference(first.get("points"), second.get("points"))
        second["point_margin_from_scores"] = _difference(second.get("points"), first.get("points"))
        first["opponent_stats"] = _opponent_stats(second)
        second["opponent_stats"] = _opponent_stats(first)
        first["paired_opponent_row"] = True
        second["paired_opponent_row"] = True
        paired_count += 1

        if (
            first.get("opponent_team_key") is not None
            and second.get("team_key") is not None
            and first["opponent_team_key"] != second["team_key"]
        ):
            opponent_mismatches.append(game_id)
        if (
            second.get("opponent_team_key") is not None
            and first.get("team_key") is not None
            and second["opponent_team_key"] != first["team_key"]
        ):
            opponent_mismatches.append(game_id)

    return {
        "game_id_count": len(by_game),
        "paired_game_count": paired_count,
        "all_game_ids_have_two_team_rows": not invalid_pair_game_ids,
        "invalid_pair_game_ids": sorted(set(invalid_pair_game_ids)),
        "opponent_identity_matches_pair": not opponent_mismatches,
        "opponent_identity_mismatch_game_ids": sorted(set(opponent_mismatches)),
    }


def _params(season: int, season_type: str) -> list[tuple[str, Any]]:
    # LeagueID first is deliberate because WNBA Stats has shown query-order
    # sensitivity for leaguegamelog in 2026.
    return [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("PlayerOrTeam", PLAYER_OR_TEAM),
        ("Counter", "0"),
        ("Direction", DIRECTION),
        ("Sorter", SORTER),
        ("DateFrom", ""),
        ("DateTo", ""),
    ]


def _fetch_league_team_games(
    season: int,
    season_type: str,
) -> tuple[list[str], list[dict[str, Any]], str, bool, dict[str, Any]]:
    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        TEAM_GAME_LOG_ENDPOINT,
        _params(season, season_type),
    )
    headers, source_rows = _result_set(payload, "LeagueGameLog")
    _require_headers(headers)

    rows = [_normalize_team_game(row, season) for row in source_rows]

    composite_ids = [
        (row["official_team_id"], row["game_id"])
        for row in rows
        if row["official_team_id"] is not None and row["game_id"] is not None
    ]
    duplicate_composite_ids = sorted(
        {
            item
            for item in composite_ids
            if composite_ids.count(item) > 1
        },
        key=lambda item: (item[0], item[1]),
    )
    if duplicate_composite_ids:
        raise WNBATeamHistoryUpstreamError(
            "WNBA team game log returned duplicate team/game rows: "
            + ", ".join(f"{team_id}:{game_id}" for team_id, game_id in duplicate_composite_ids)
        )

    pair_verification = _pair_game_rows(rows)
    return headers, rows, retrieved_at_utc, cache_hit, pair_verification


def _weighted_percentage(
    games: list[dict[str, Any]],
    made_field: str,
    attempted_field: str,
) -> float | None:
    made = sum(
        float(game[made_field])
        for game in games
        if isinstance(game.get(made_field), (int, float))
        and not isinstance(game.get(made_field), bool)
    )
    attempted = sum(
        float(game[attempted_field])
        for game in games
        if isinstance(game.get(attempted_field), (int, float))
        and not isinstance(game.get(attempted_field), bool)
    )
    if attempted <= 0:
        return None
    return round(made / attempted, 4)


def _average(games: list[dict[str, Any]], field: str) -> float | None:
    values = [
        float(game[field])
        for game in games
        if isinstance(game.get(field), (int, float))
        and not isinstance(game.get(field), bool)
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _record_summary(games: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum((game.get("result") or "").upper() == "W" for game in games)
    losses = sum((game.get("result") or "").upper() == "L" for game in games)
    decided = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "win_percentage": round(wins / decided, 4) if decided else None,
    }


def _streak(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {"result": None, "length": 0, "label": None}
    first = (games[0].get("result") or "").upper()
    if first not in {"W", "L"}:
        return {"result": None, "length": 0, "label": None}
    length = 0
    for game in games:
        if (game.get("result") or "").upper() != first:
            break
        length += 1
    return {"result": first, "length": length, "label": f"{first}{length}"}


def _summary(games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "game_count": len(games),
        "record": _record_summary(games),
        "current_streak": _streak(games),
        "averages": {
            "points_for": _average(games, "points"),
            "points_against": _average(games, "opponent_points"),
            "point_margin": _average(games, "point_margin_from_scores"),
            "rebounds": _average(games, "rebounds"),
            "assists": _average(games, "assists"),
            "turnovers": _average(games, "turnovers"),
            "steals": _average(games, "steals"),
            "blocks": _average(games, "blocks"),
        },
        "weighted_shooting": {
            "field_goal_percentage": _weighted_percentage(
                games, "field_goals_made", "field_goals_attempted"
            ),
            "three_point_percentage": _weighted_percentage(
                games, "three_pointers_made", "three_pointers_attempted"
            ),
            "free_throw_percentage": _weighted_percentage(
                games, "free_throws_made", "free_throws_attempted"
            ),
        },
    }


def _apply_filters(
    rows: list[dict[str, Any]],
    *,
    team_key: str,
    opponent_team_key: str | None,
    location: str,
    last_n_games: int,
) -> list[dict[str, Any]]:
    games = [row for row in rows if row.get("team_key") == team_key]
    if opponent_team_key is not None:
        games = [
            row
            for row in games
            if row.get("opponent_team_key") == opponent_team_key
        ]
    if location != "All":
        target = location.casefold()
        games = [row for row in games if row.get("location") == target]

    games.sort(
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
        ),
        reverse=True,
    )
    if last_n_games > 0:
        games = games[:last_n_games]
    return games


def get_team_game_log_dataset(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    location: str = "All",
    opponent_team_key: str | None = None,
) -> dict[str, Any]:
    stable_team_key = _validate_team_key(team_key, season)
    stable_opponent_key = (
        _validate_team_key(opponent_team_key, season)
        if opponent_team_key is not None
        else None
    )
    if stable_opponent_key == stable_team_key:
        raise ValueError("WNBA opponent_team_key must be different from team_key.")

    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _normalize_last_n_games(last_n_games)
    location = _normalize_choice(location, ALLOWED_LOCATIONS, "location")

    headers, rows, retrieved_at_utc, cache_hit, pair_verification = (
        _fetch_league_team_games(season, season_type)
    )
    games = _apply_filters(
        rows,
        team_key=stable_team_key,
        opponent_team_key=stable_opponent_key,
        location=location,
        last_n_games=last_n_games,
    )

    unmapped = sum(not row["mapped_to_registry"] for row in rows)
    invalid_game_ids = sorted(
        {
            row["game_id"]
            for row in rows
            if row["game_id"] is not None and not row["game_id_valid"]
        }
    )
    requested_team_rows = [row for row in rows if row.get("team_key") == stable_team_key]

    return {
        "source": WNBA_TEAM_HISTORY_SOURCE,
        "source_url": WNBA_TEAM_HISTORY_SOURCE_URL,
        "source_endpoint": TEAM_GAME_LOG_ENDPOINT,
        "data_type": "official_team_game_log",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "team_key": stable_team_key,
        "filters": {
            "last_n_games": last_n_games,
            "location": location,
            "opponent_team_key": stable_opponent_key,
        },
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_header_count": len(headers),
        "season_team_game_count": len(requested_team_rows),
        "game_count": len(games),
        "summary": _summary(games),
        "games": games,
        "verification": {
            "schema_verified": True,
            "all_rows_mapped_to_registry": unmapped == 0,
            "unmapped_team_count": unmapped,
            "all_game_ids_valid": not invalid_game_ids,
            "invalid_game_ids": invalid_game_ids,
            **pair_verification,
        },
    }


def get_team_recent_form_dataset(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    location: str = "All",
) -> dict[str, Any]:
    if last_n_games == 0:
        raise ValueError("WNBA recent form last_n_games must be from 1 through 100.")
    dataset = get_team_game_log_dataset(
        team_key,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
        location=location,
    )
    return {
        "source": dataset["source"],
        "source_url": dataset["source_url"],
        "source_endpoint": dataset["source_endpoint"],
        "data_type": "official_team_recent_form",
        "league_id": dataset["league_id"],
        "season": dataset["season"],
        "season_type": dataset["season_type"],
        "team_key": dataset["team_key"],
        "last_n_games": last_n_games,
        "location": dataset["filters"]["location"],
        "retrieved_at_utc": dataset["retrieved_at_utc"],
        "cache_hit": dataset["cache_hit"],
        "cache_ttl_seconds": dataset["cache_ttl_seconds"],
        "summary": dataset["summary"],
        "games": dataset["games"],
        "verification": dataset["verification"],
    }


def get_head_to_head_dataset(
    team_key: str,
    opponent_team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    location: str = "All",
) -> dict[str, Any]:
    stable_team_key = _validate_team_key(team_key, season)
    stable_opponent_key = _validate_team_key(opponent_team_key, season)
    if stable_team_key == stable_opponent_key:
        raise ValueError("WNBA head-to-head teams must be different.")

    dataset = get_team_game_log_dataset(
        stable_team_key,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
        location=location,
        opponent_team_key=stable_opponent_key,
    )
    meetings = dataset["games"]

    counterpart_complete = all(
        game.get("paired_opponent_row")
        and (game.get("opponent_stats") or {}).get("team_key") == stable_opponent_key
        for game in meetings
    )

    if meetings:
        first_date = meetings[-1].get("game_date")
        most_recent_date = meetings[0].get("game_date")
    else:
        first_date = None
        most_recent_date = None

    return {
        "source": dataset["source"],
        "source_url": dataset["source_url"],
        "source_endpoint": dataset["source_endpoint"],
        "data_type": "official_team_head_to_head",
        "league_id": dataset["league_id"],
        "season": dataset["season"],
        "season_type": dataset["season_type"],
        "team_key": stable_team_key,
        "opponent_team_key": stable_opponent_key,
        "filters": {
            "last_n_games": last_n_games,
            "location": dataset["filters"]["location"],
        },
        "retrieved_at_utc": dataset["retrieved_at_utc"],
        "cache_hit": dataset["cache_hit"],
        "cache_ttl_seconds": dataset["cache_ttl_seconds"],
        "meeting_count": len(meetings),
        "first_meeting_date": first_date,
        "most_recent_meeting_date": most_recent_date,
        "summary": dataset["summary"],
        "meetings": meetings,
        "verification": {
            **dataset["verification"],
            "all_returned_rows_match_requested_opponent": all(
                game.get("opponent_team_key") == stable_opponent_key
                for game in meetings
            ),
            "all_meetings_have_paired_opponent_row": counterpart_complete,
        },
    }
