"""Official WNBA player-tracking opportunity context.

Step 4H adds observed player-tracking data only. It does not contain betting
lines, projections, simulations, injury assumptions, or model probabilities.

Primary official source:
- stats.wnba.com/stats/leaguedashptstats

The upstream endpoint changes its result columns according to PtMeasureType.
This collector intentionally validates each requested measure independently and
keeps unavailable fields as null rather than synthesizing tracking data.
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
WNBA_TRACKING_SOURCE = "WNBA Stats API"
WNBA_TRACKING_SOURCE_URL = "https://stats.wnba.com/"
TRACKING_ENDPOINT = "leaguedashptstats"
PLAYER_OR_TEAM = "Player"

TRACKING_MEASURES = ("Passing", "Rebounding", "Possessions")

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


class WNBATrackingUpstreamError(RuntimeError):
    """Raised when official WNBA tracking data cannot be consumed safely."""


class WNBATrackingMeasureUnavailableError(WNBATrackingUpstreamError):
    """Raised when an upstream response does not expose the requested measure."""


class WNBATrackingNotFoundError(LookupError):
    """Raised when a requested player's official tracking row is absent."""


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


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


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
        raise WNBATrackingUpstreamError(
            f"Official WNBA Stats API request failed for {endpoint}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBATrackingUpstreamError(
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
        raise WNBATrackingUpstreamError(
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
        raise WNBATrackingUpstreamError(
            f"WNBA payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    row_set = selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBATrackingUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )

    normalized_headers = [str(header) for header in headers]
    rows = [
        dict(zip(normalized_headers, row))
        for row in row_set
        if isinstance(row, (list, tuple))
    ]
    return normalized_headers, rows


def _validate_tracking_headers(headers: list[str], measure: str) -> None:
    header_set = set(headers)
    base_required = {
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ID",
        "TEAM_ABBREVIATION",
        "GP",
        "MIN",
    }
    missing_base = sorted(base_required - header_set)
    if missing_base:
        raise WNBATrackingUpstreamError(
            "WNBA player-tracking response is missing required identity fields: "
            + ", ".join(missing_base)
            + "."
        )

    measure_markers = {
        "Passing": {"PASSES_MADE", "AST", "POTENTIAL_AST"},
        "Rebounding": {"REB", "REB_CHANCES", "REB_CHANCE_PCT"},
        "Possessions": {"TOUCHES", "TIME_OF_POSS", "AVG_SEC_PER_TOUCH"},
    }
    markers = measure_markers[measure]
    found = markers & header_set

    # Require enough measure-specific evidence to ensure the endpoint did not
    # silently return another PtMeasureType schema (for example SpeedDistance).
    minimum = 2
    if len(found) < minimum:
        raise WNBATrackingMeasureUnavailableError(
            f"Official WNBA tracking response does not expose the requested {measure} "
            f"schema (found {len(found)} of {len(markers)} core fields)."
        )


def _identity(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team_from_row(row, season)
    return {
        "player_id": _to_int(row.get("PLAYER_ID")),
        "player_name": _clean_text(row.get("PLAYER_NAME")),
        "age": _to_float(row.get("AGE")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean_text(row.get("TEAM_ABBREVIATION")),
        "team_key": team["team_key"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "conference": team["conference"] if team else None,
        "games_played": _to_int(row.get("GP")),
        "wins": _to_int(row.get("W")),
        "losses": _to_int(row.get("L")),
        "minutes": _to_float(row.get("MIN")),
        "mapped_to_registry": team is not None,
    }


def _normalize_passing(row: dict[str, Any], season: int) -> dict[str, Any]:
    base = _identity(row, season)
    passes_made = _to_float(row.get("PASSES_MADE"))
    assists = _to_float(row.get("AST"))
    potential_assists = _to_float(row.get("POTENTIAL_AST"))
    return {
        **base,
        "tracking_measure": "Passing",
        "passing": {
            "passes_made": passes_made,
            "passes_received": _to_float(row.get("PASSES_RECEIVED")),
            "assists": assists,
            "free_throw_assists": _to_float(row.get("FT_AST")),
            "secondary_assists": _to_float(row.get("SECONDARY_AST")),
            "potential_assists": potential_assists,
            "assist_points_created": _to_float(row.get("AST_PTS_CREATED")),
            "adjusted_assists": _to_float(row.get("AST_ADJ")),
            "assist_percentage": _to_float(row.get("AST_PCT")),
            "assist_to_pass_percentage": _to_float(row.get("AST_TO_PASS_PCT")),
            "adjusted_assist_to_pass_percentage": _to_float(
                row.get("AST_TO_PASS_PCT_ADJ")
            ),
            "bad_pass_turnovers": _to_float(row.get("BAD_PASS_TURNOVER")),
            "bad_pass_to_turnover_ratio": _to_float(
                row.get("BAD_PASS_TO_TURNOVER_RATIO")
            ),
        },
        "derived_observed": {
            "assist_conversion_from_potential": _safe_ratio(assists, potential_assists),
            "passes_per_minute": _safe_ratio(passes_made, base["minutes"]),
            "potential_assists_per_minute": _safe_ratio(
                potential_assists, base["minutes"]
            ),
        },
    }


def _normalize_rebounding(row: dict[str, Any], season: int) -> dict[str, Any]:
    base = _identity(row, season)
    rebounds = _to_float(row.get("REB"))
    rebound_chances = _to_float(row.get("REB_CHANCES"))
    return {
        **base,
        "tracking_measure": "Rebounding",
        "rebounding": {
            "offensive_rebounds": _to_float(row.get("OREB")),
            "offensive_rebounds_contested": _to_float(row.get("OREB_CONTEST")),
            "offensive_rebounds_uncontested": _to_float(row.get("OREB_UNCONTEST")),
            "offensive_rebound_chances": _to_float(row.get("OREB_CHANCES")),
            "offensive_rebound_chance_percentage": _to_float(
                row.get("OREB_CHANCE_PCT")
            ),
            "offensive_rebound_chances_deferred": _to_float(
                row.get("OREB_CHANCE_DEFER")
            ),
            "adjusted_offensive_rebound_chance_percentage": _to_float(
                row.get("OREB_CHANCE_PCT_ADJ")
            ),
            "defensive_rebounds": _to_float(row.get("DREB")),
            "defensive_rebounds_contested": _to_float(row.get("DREB_CONTEST")),
            "defensive_rebounds_uncontested": _to_float(row.get("DREB_UNCONTEST")),
            "defensive_rebound_chances": _to_float(row.get("DREB_CHANCES")),
            "defensive_rebound_chance_percentage": _to_float(
                row.get("DREB_CHANCE_PCT")
            ),
            "defensive_rebound_chances_deferred": _to_float(
                row.get("DREB_CHANCE_DEFER")
            ),
            "adjusted_defensive_rebound_chance_percentage": _to_float(
                row.get("DREB_CHANCE_PCT_ADJ")
            ),
            "rebounds": rebounds,
            "contested_rebounds": _to_float(row.get("REB_CONTEST")),
            "uncontested_rebounds": _to_float(row.get("REB_UNCONTEST")),
            "rebound_chances": rebound_chances,
            "rebound_chance_percentage": _to_float(row.get("REB_CHANCE_PCT")),
            "rebound_chances_deferred": _to_float(row.get("REB_CHANCE_DEFER")),
            "adjusted_rebound_chance_percentage": _to_float(
                row.get("REB_CHANCE_PCT_ADJ")
            ),
            "average_rebound_distance_feet": _to_float(row.get("AVG_REB_DIST")),
        },
        "derived_observed": {
            "rebounds_per_chance": _safe_ratio(rebounds, rebound_chances),
            "rebound_chances_per_minute": _safe_ratio(
                rebound_chances, base["minutes"]
            ),
        },
    }


def _normalize_possessions(row: dict[str, Any], season: int) -> dict[str, Any]:
    base = _identity(row, season)
    touches = _to_float(row.get("TOUCHES"))
    time_of_possession = _to_float(row.get("TIME_OF_POSS"))
    return {
        **base,
        "tracking_measure": "Possessions",
        "possessions": {
            "touches": touches,
            "frontcourt_touches": _to_float(row.get("FRONT_CT_TOUCHES")),
            "time_of_possession_minutes": time_of_possession,
            "average_seconds_per_touch": _to_float(row.get("AVG_SEC_PER_TOUCH")),
            "average_dribbles_per_touch": _to_float(row.get("AVG_DRIB_PER_TOUCH")),
            "points_per_touch": _to_float(row.get("PTS_PER_TOUCH")),
            "elbow_touches": _to_float(row.get("ELBOW_TOUCHES")),
            "post_touches": _to_float(row.get("POST_TOUCHES")),
            "paint_touches": _to_float(row.get("PAINT_TOUCHES")),
            "points_per_elbow_touch": _to_float(row.get("PTS_PER_ELBOW_TOUCH")),
            "points_per_post_touch": _to_float(row.get("PTS_PER_POST_TOUCH")),
            "points_per_paint_touch": _to_float(row.get("PTS_PER_PAINT_TOUCH")),
        },
        "derived_observed": {
            "touches_per_minute": _safe_ratio(touches, base["minutes"]),
            "possession_time_share_of_minutes": _safe_ratio(
                time_of_possession, base["minutes"]
            ),
        },
    }


def _normalize_row(row: dict[str, Any], season: int, measure: str) -> dict[str, Any]:
    if measure == "Passing":
        return _normalize_passing(row, season)
    if measure == "Rebounding":
        return _normalize_rebounding(row, season)
    return _normalize_possessions(row, season)


def _params(
    season: int,
    season_type: str,
    measure: str,
    last_n_games: int,
    per_mode: str,
) -> list[tuple[str, Any]]:
    # LeagueID first is deliberate because WNBA Stats has shown query-order
    # sensitivity on some endpoints.
    return [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("PlayerOrTeam", PLAYER_OR_TEAM),
        ("PtMeasureType", measure),
        ("PerMode", per_mode),
        ("LastNGames", str(last_n_games)),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("College", ""),
        ("Conference", ""),
        ("Country", ""),
        ("DateFrom", ""),
        ("DateTo", ""),
        ("Division", ""),
        ("DraftPick", ""),
        ("DraftYear", ""),
        ("GameScope", ""),
        ("Height", ""),
        ("Location", ""),
        ("Outcome", ""),
        ("PORound", ""),
        ("PlayerExperience", ""),
        ("PlayerPosition", ""),
        ("SeasonSegment", ""),
        ("StarterBench", ""),
        ("TeamID", ""),
        ("VsConference", ""),
        ("VsDivision", ""),
        ("Weight", ""),
    ]


def _window_scope(last_n_games: int) -> str:
    return "season_to_date" if last_n_games == 0 else f"last_{last_n_games}_games"


def _availability(headers: list[str], measure: str) -> dict[str, bool]:
    header_set = set(headers)
    if measure == "Passing":
        return {
            "passes_made": "PASSES_MADE" in header_set,
            "secondary_assists": "SECONDARY_AST" in header_set,
            "potential_assists": "POTENTIAL_AST" in header_set,
            "assist_points_created": "AST_PTS_CREATED" in header_set,
        }
    if measure == "Rebounding":
        return {
            "rebound_chances": "REB_CHANCES" in header_set,
            "rebound_chance_percentage": "REB_CHANCE_PCT" in header_set,
            "adjusted_rebound_chance_percentage": "REB_CHANCE_PCT_ADJ" in header_set,
            "average_rebound_distance": "AVG_REB_DIST" in header_set,
        }
    return {
        "touches": "TOUCHES" in header_set,
        "frontcourt_touches": "FRONT_CT_TOUCHES" in header_set,
        "time_of_possession": "TIME_OF_POSS" in header_set,
        "average_seconds_per_touch": "AVG_SEC_PER_TOUCH" in header_set,
    }


def _verification(players: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [player["player_id"] for player in players if player["player_id"] is not None]
    duplicates = sorted({player_id for player_id in ids if ids.count(player_id) > 1})
    unmapped = sum(not player["mapped_to_registry"] for player in players)
    return {
        "schema_verified": True,
        "all_rows_have_player_ids": len(ids) == len(players),
        "player_ids_unique": not duplicates,
        "duplicate_player_ids": duplicates,
        "all_rows_mapped_to_registry": unmapped == 0,
        "unmapped_team_count": unmapped,
    }


def get_player_tracking_dataset(
    season: int,
    *,
    measure: str,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    per_mode: str = "PerGame",
    team_key: str | None = None,
    player_id: int | None = None,
) -> dict[str, Any]:
    get_wnba_teams(season)
    measure = _normalize_choice(measure, TRACKING_MEASURES, "tracking_measure")
    season_type = _normalize_choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    per_mode = _normalize_choice(per_mode, ALLOWED_PER_MODES, "per_mode")
    last_n_games = _normalize_last_n_games(last_n_games)
    team_key = _validate_team_key(team_key, season)
    player_id = _normalize_player_id(player_id)

    payload, retrieved_at_utc, cache_hit = _request_stats_json(
        TRACKING_ENDPOINT,
        _params(season, season_type, measure, last_n_games, per_mode),
    )
    headers, rows = _result_set(payload, "LeagueDashPtStats")
    _validate_tracking_headers(headers, measure)

    players = [_normalize_row(row, season, measure) for row in rows]
    if team_key is not None:
        players = [player for player in players if player["team_key"] == team_key]
    if player_id is not None:
        players = [player for player in players if player["player_id"] == player_id]

    players.sort(key=lambda player: (player["player_name"] or "", player["player_id"] or 0))

    return {
        "source": WNBA_TRACKING_SOURCE,
        "source_url": WNBA_TRACKING_SOURCE_URL,
        "source_endpoint": TRACKING_ENDPOINT,
        "data_type": "official_player_tracking",
        "player_or_team": PLAYER_OR_TEAM,
        "tracking_measure": measure,
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
        "field_availability": _availability(headers, measure),
        "player_count": len(players),
        "players": players,
        "verification": _verification(players),
    }


def _single_player_from_dataset(
    dataset: dict[str, Any],
    player_id: int,
) -> dict[str, Any] | None:
    rows = [
        row for row in dataset.get("players", []) if row.get("player_id") == player_id
    ]
    if len(rows) > 1:
        raise WNBATrackingUpstreamError(
            f"Official WNBA tracking data returned duplicate rows for player {player_id}."
        )
    return rows[0] if rows else None


def get_player_opportunity_context_dataset(
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

    measure_payloads: dict[str, dict[str, Any] | None] = {}
    unavailable_measures: dict[str, str] = {}
    retrieved_times: list[str] = []
    cache_hits: list[bool] = []

    for measure in TRACKING_MEASURES:
        try:
            dataset = get_player_tracking_dataset(
                season,
                measure=measure,
                season_type=season_type,
                last_n_games=last_n_games,
                per_mode=per_mode,
                player_id=player_id,
            )
        except WNBATrackingMeasureUnavailableError as exc:
            measure_payloads[measure] = None
            unavailable_measures[measure] = str(exc)
            continue

        retrieved_times.append(dataset["retrieved_at_utc"])
        cache_hits.append(bool(dataset["cache_hit"]))
        measure_payloads[measure] = {
            "field_availability": dataset["field_availability"],
            "player": _single_player_from_dataset(dataset, player_id),
        }

    present_players = [
        payload["player"]
        for payload in measure_payloads.values()
        if payload is not None and payload.get("player") is not None
    ]
    if not present_players:
        raise WNBATrackingNotFoundError(
            f"No official WNBA tracking data was found for player {player_id} in {season}."
        )

    identity = present_players[0]
    for player in present_players[1:]:
        if (
            player.get("player_name") != identity.get("player_name")
            or player.get("team_key") != identity.get("team_key")
        ):
            raise WNBATrackingUpstreamError(
                f"Official WNBA tracking measures disagree on player {player_id} identity."
            )

    passing_payload = measure_payloads.get("Passing")
    rebounding_payload = measure_payloads.get("Rebounding")
    possessions_payload = measure_payloads.get("Possessions")

    return {
        "source": WNBA_TRACKING_SOURCE,
        "source_url": WNBA_TRACKING_SOURCE_URL,
        "source_endpoint": TRACKING_ENDPOINT,
        "data_type": "official_player_opportunity_context",
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "player_name": identity.get("player_name"),
        "team_key": identity.get("team_key"),
        "team_full_name": identity.get("team_full_name"),
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": _window_scope(last_n_games),
        "retrieved_at_utc": max(retrieved_times) if retrieved_times else _utc_now_iso(),
        "cache_hit": bool(cache_hits) and all(cache_hits),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "passing": passing_payload["player"] if passing_payload else None,
        "rebounding": rebounding_payload["player"] if rebounding_payload else None,
        "possessions": possessions_payload["player"] if possessions_payload else None,
        "availability": {
            "passing": passing_payload is not None,
            "rebounding": rebounding_payload is not None,
            "possessions": possessions_payload is not None,
            "unavailable_measures": unavailable_measures,
        },
        "verification": {
            "identity_consistent_across_available_measures": True,
            "available_measure_count": sum(
                payload is not None for payload in measure_payloads.values()
            ),
            "all_three_measures_available": all(
                measure_payloads.get(measure) is not None
                for measure in TRACKING_MEASURES
            ),
            "no_synthetic_tracking_fields": True,
        },
    }
