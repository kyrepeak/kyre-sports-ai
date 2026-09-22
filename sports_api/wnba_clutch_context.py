"""Official WNBA clutch and game-situation statistics.

Step 4Q exposes observed clutch splits from the official WNBA Stats API.
It intentionally keeps clutch samples descriptive: no clutch grade, predictive
probability, betting edge, or causal inference is created here.
"""

from __future__ import annotations

from typing import Any, Iterable

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import (
    WNBA_LEAGUE_ID,
    WNBA_STATS_SOURCE,
    WNBA_STATS_SOURCE_URL,
    WNBAStatsUpstreamError,
    _request_stats_json,
)

PLAYER_CLUTCH_ENDPOINT = "leaguedashplayerclutch"
TEAM_CLUTCH_ENDPOINT = "leaguedashteamclutch"
MEASURE_TYPE = "Base"
MAX_LAST_N_GAMES = 100
MAX_POINT_DIFF = 20
MAX_PERIOD = 14

ALLOWED_CLUTCH_TIMES = (
    "Last 5 Minutes",
    "Last 4 Minutes",
    "Last 3 Minutes",
    "Last 2 Minutes",
    "Last 1 Minute",
    "Last 30 Seconds",
    "Last 10 Seconds",
)
ALLOWED_AHEAD_BEHIND = (
    "Ahead or Behind",
    "Behind or Tied",
    "Ahead or Tied",
)
ALLOWED_LOCATIONS = ("", "Home", "Road")
ALLOWED_OUTCOMES = ("", "W", "L")
ALLOWED_PER_MODES = ("Totals", "PerGame", "Per36")


class WNBAClutchUpstreamError(RuntimeError):
    """Raised when official WNBA clutch data cannot be consumed safely."""


class WNBAClutchNotFoundError(LookupError):
    """Raised when a requested player/team has no matching clutch row."""


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


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _choice(value: str, allowed: Iterable[str], label: str) -> str:
    text = str(value).strip()
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(text.casefold())
    if resolved is None:
        printable = [item if item else "(blank)" for item in allowed]
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(printable)
            + "."
        )
    return resolved


def _normalize_last_n_games(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > MAX_LAST_N_GAMES
    ):
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    return value


def _normalize_point_diff(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_POINT_DIFF
    ):
        raise ValueError("WNBA point_diff must be an integer from 1 through 20.")
    return value


def _normalize_period(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > MAX_PERIOD
    ):
        raise ValueError("WNBA period must be an integer from 0 through 14 (0 = all periods).")
    return value


def _normalize_player_id(value: int | None) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _normalize_team_key(value: str | None, season: int) -> str | None:
    if value is None:
        return None
    key = str(value).strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == key:
            return team["team_key"]
    raise ValueError(f"WNBA team key {value!r} was not found for the {season} season.")


def _registry_team(row: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean(row.get("TEAM_ABBREVIATION")) or "").casefold(),
        (_clean(row.get("TEAM_NAME")) or "").casefold(),
    }
    if "pdx" in values:
        values.update({"por", "portland-fire"})
    if "gs" in values:
        values.update({"gsv", "golden-state-valkyries"})
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


def _result_set(
    payload: dict[str, Any],
    result_name: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    raw = payload.get("resultSets")
    if raw is None:
        raw = payload.get("resultSet")
    candidates = [raw] if isinstance(raw, dict) else raw
    if not isinstance(candidates, list):
        raise WNBAClutchUpstreamError(
            f"WNBA clutch payload is missing result sets for {result_name}."
        )

    selected = next(
        (
            item
            for item in candidates
            if isinstance(item, dict)
            and (_clean(item.get("name")) or "").casefold() == result_name.casefold()
        ),
        None,
    )
    if selected is None and len(candidates) == 1 and isinstance(candidates[0], dict):
        selected = candidates[0]
    if selected is None:
        raise WNBAClutchUpstreamError(
            f"WNBA clutch payload is missing the {result_name} result set."
        )

    headers = selected.get("headers")
    rows = selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise WNBAClutchUpstreamError(
            f"WNBA {result_name} result set has an unexpected schema."
        )
    normalized_headers = [str(header) for header in headers]
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != len(normalized_headers):
            raise WNBAClutchUpstreamError(
                f"WNBA {result_name} result set contains a malformed row."
            )
        normalized_rows.append(dict(zip(normalized_headers, row)))
    return normalized_headers, normalized_rows


def _validate_headers(headers: list[str], *, player: bool) -> None:
    required = {
        "TEAM_ID",
        "GP",
        "W",
        "L",
        "MIN",
        "FGM",
        "FGA",
        "FTA",
        "REB",
        "AST",
        "TOV",
        "PTS",
        "PLUS_MINUS",
    }
    required.add("PLAYER_ID" if player else "TEAM_NAME")
    missing = sorted(required - set(headers))
    if missing:
        raise WNBAClutchUpstreamError(
            "WNBA clutch response is missing required fields: " + ", ".join(missing) + "."
        )


def _stats(row: dict[str, Any]) -> dict[str, Any]:
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
        "wnba_fantasy_points": _to_float(row.get("WNBA_FANTASY_PTS")),
    }


def _normalize_player(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team(row, season)
    return {
        "group_set": _clean(row.get("GROUP_SET")),
        "player_id": _to_int(row.get("PLAYER_ID")),
        "player_name": _clean(row.get("PLAYER_NAME")),
        "nickname": _clean(row.get("NICKNAME")),
        "age": _to_float(row.get("AGE")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_abbreviation": _clean(row.get("TEAM_ABBREVIATION")),
        "team_key": team["team_key"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "conference": team["conference"] if team else None,
        "games_played_in_sample": _to_int(row.get("GP")),
        "record_in_sample": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "stats": _stats(row),
        "mapped_to_registry": team is not None,
    }


def _normalize_team(row: dict[str, Any], season: int) -> dict[str, Any]:
    team = _registry_team(row, season)
    return {
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "source_team_name": _clean(row.get("TEAM_NAME")),
        "team_key": team["team_key"] if team else None,
        "team_abbreviation": team["abbreviation"] if team else None,
        "team_full_name": team["full_name"] if team else None,
        "conference": team["conference"] if team else None,
        "games_played_in_sample": _to_int(row.get("GP")),
        "record_in_sample": {
            "wins": _to_int(row.get("W")),
            "losses": _to_int(row.get("L")),
            "win_percentage": _to_float(row.get("W_PCT")),
        },
        "stats": _stats(row),
        "mapped_to_registry": team is not None,
    }


def _params(
    season: int,
    season_type: str,
    *,
    clutch_time: str,
    point_diff: int,
    ahead_behind: str,
    last_n_games: int,
    per_mode: str,
    period: int,
    location: str,
    outcome: str,
    player: bool,
) -> list[tuple[str, Any]]:
    # LeagueID first is deliberate; WNBA Stats has shown query-order sensitivity.
    params: list[tuple[str, Any]] = [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("AheadBehind", ahead_behind),
        ("ClutchTime", clutch_time),
        ("LastNGames", str(last_n_games)),
        ("MeasureType", MEASURE_TYPE),
        ("Month", "0"),
        ("OpponentTeamID", "0"),
        ("PaceAdjust", "N"),
        ("PerMode", per_mode),
        ("Period", str(period)),
        ("PlusMinus", "N"),
        ("PointDiff", str(point_diff)),
        ("Rank", "N"),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("Conference", ""),
        ("DateFrom", ""),
        ("DateTo", ""),
        ("Division", ""),
        ("GameScope", ""),
        ("GameSegment", ""),
        ("Location", location),
        ("Outcome", outcome),
        ("PORound", "0"),
        ("PlayerExperience", ""),
        ("PlayerPosition", ""),
        ("SeasonSegment", ""),
        ("ShotClockRange", ""),
        ("StarterBench", ""),
        ("TeamID", ""),
        ("VsConference", ""),
        ("VsDivision", ""),
    ]
    if player:
        params += [
            ("College", ""),
            ("Country", ""),
            ("DraftPick", ""),
            ("DraftYear", ""),
            ("Height", ""),
            ("Weight", ""),
        ]
    return params


def _normalize_controls(
    season: int,
    season_type: str,
    clutch_time: str,
    point_diff: int,
    ahead_behind: str,
    last_n_games: int,
    per_mode: str,
    period: int,
    location: str,
    outcome: str,
) -> dict[str, Any]:
    get_wnba_teams(season)
    return {
        "season_type": _choice(season_type, ALLOWED_SEASON_TYPES, "season_type"),
        "clutch_time": _choice(clutch_time, ALLOWED_CLUTCH_TIMES, "clutch_time"),
        "point_diff": _normalize_point_diff(point_diff),
        "ahead_behind": _choice(ahead_behind, ALLOWED_AHEAD_BEHIND, "ahead_behind"),
        "last_n_games": _normalize_last_n_games(last_n_games),
        "per_mode": _choice(per_mode, ALLOWED_PER_MODES, "per_mode"),
        "period": _normalize_period(period),
        "location": _choice(location, ALLOWED_LOCATIONS, "location"),
        "outcome": _choice(outcome, ALLOWED_OUTCOMES, "outcome"),
    }


def _definition(controls: dict[str, Any]) -> dict[str, Any]:
    return {
        "clutch_time": controls["clutch_time"],
        "point_diff": controls["point_diff"],
        "ahead_behind": controls["ahead_behind"],
        "period": controls["period"],
        "location": controls["location"] or "All",
        "outcome": controls["outcome"] or "All",
        "standard_clutch_default": (
            controls["clutch_time"] == "Last 5 Minutes"
            and controls["point_diff"] == 5
            and controls["ahead_behind"] == "Ahead or Behind"
            and controls["period"] == 0
            and not controls["location"]
            and not controls["outcome"]
        ),
        "sample_is_game_situation_subset_not_full_game_performance": True,
        "small_sample_warning": (
            "Clutch splits can contain very small samples. Games and minutes in the returned "
            "sample should be reviewed before downstream modeling."
        ),
    }


def get_player_clutch_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    clutch_time: str = "Last 5 Minutes",
    point_diff: int = 5,
    ahead_behind: str = "Ahead or Behind",
    last_n_games: int = 0,
    per_mode: str = "Totals",
    period: int = 0,
    location: str = "",
    outcome: str = "",
    team_key: str | None = None,
    player_id: int | None = None,
) -> dict[str, Any]:
    controls = _normalize_controls(
        season, season_type, clutch_time, point_diff, ahead_behind,
        last_n_games, per_mode, period, location, outcome,
    )
    team_key = _normalize_team_key(team_key, season)
    player_id = _normalize_player_id(player_id)
    params = _params(season, player=True, **controls)

    try:
        payload, retrieved_at_utc, cache_hit = _request_stats_json(
            PLAYER_CLUTCH_ENDPOINT, params
        )
    except WNBAStatsUpstreamError as exc:
        raise WNBAClutchUpstreamError(str(exc)) from exc

    headers, rows = _result_set(payload, "LeagueDashPlayerClutch")
    _validate_headers(headers, player=True)
    players = [_normalize_player(row, season) for row in rows]
    if team_key is not None:
        players = [row for row in players if row["team_key"] == team_key]
    if player_id is not None:
        players = [row for row in players if row["player_id"] == player_id]
    players.sort(key=lambda row: (row.get("player_name") or "", row.get("player_id") or 0))

    ids = [row["player_id"] for row in players if row["player_id"] is not None]
    duplicates = sorted(value for value in set(ids) if ids.count(value) > 1)
    unmapped = sum(1 for row in players if not row["mapped_to_registry"])

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": PLAYER_CLUTCH_ENDPOINT,
        "data_type": "official_player_clutch_game_situation_statistics",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": controls["season_type"],
        "last_n_games": controls["last_n_games"],
        "per_mode": controls["per_mode"],
        "definition": _definition(controls),
        "team_key_filter": team_key,
        "player_id_filter": player_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "player_count": len(players),
        "players": players,
        "verification": {
            "required_schema_verified": True,
            "duplicate_player_ids": duplicates,
            "player_ids_unique": len(duplicates) == 0,
            "unmapped_team_count": unmapped,
            "all_rows_mapped_to_registry": unmapped == 0,
            "clutch_sample_is_descriptive_not_predictive": True,
            "no_clutch_grade_created": True,
            "no_betting_probability_created": True,
        },
    }


def get_team_clutch_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
    clutch_time: str = "Last 5 Minutes",
    point_diff: int = 5,
    ahead_behind: str = "Ahead or Behind",
    last_n_games: int = 0,
    per_mode: str = "Totals",
    period: int = 0,
    location: str = "",
    outcome: str = "",
    team_key: str | None = None,
) -> dict[str, Any]:
    controls = _normalize_controls(
        season, season_type, clutch_time, point_diff, ahead_behind,
        last_n_games, per_mode, period, location, outcome,
    )
    team_key = _normalize_team_key(team_key, season)
    params = _params(season, player=False, **controls)

    try:
        payload, retrieved_at_utc, cache_hit = _request_stats_json(
            TEAM_CLUTCH_ENDPOINT, params
        )
    except WNBAStatsUpstreamError as exc:
        raise WNBAClutchUpstreamError(str(exc)) from exc

    headers, rows = _result_set(payload, "LeagueDashTeamClutch")
    _validate_headers(headers, player=False)
    teams = [_normalize_team(row, season) for row in rows]
    if team_key is not None:
        teams = [row for row in teams if row["team_key"] == team_key]
    teams.sort(key=lambda row: row.get("team_full_name") or row.get("source_team_name") or "")

    ids = [row["official_team_id"] for row in teams if row["official_team_id"] is not None]
    duplicates = sorted(value for value in set(ids) if ids.count(value) > 1)
    unmapped = sum(1 for row in teams if not row["mapped_to_registry"])

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": TEAM_CLUTCH_ENDPOINT,
        "data_type": "official_team_clutch_game_situation_statistics",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": controls["season_type"],
        "last_n_games": controls["last_n_games"],
        "per_mode": controls["per_mode"],
        "definition": _definition(controls),
        "team_key_filter": team_key,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "team_count": len(teams),
        "teams": teams,
        "verification": {
            "required_schema_verified": True,
            "duplicate_official_team_ids": duplicates,
            "official_team_ids_unique": len(duplicates) == 0,
            "unmapped_team_count": unmapped,
            "all_rows_mapped_to_registry": unmapped == 0,
            "clutch_sample_is_descriptive_not_predictive": True,
            "no_clutch_grade_created": True,
            "no_betting_probability_created": True,
        },
    }


def get_player_clutch_context(player_id: int, season: int, **kwargs: Any) -> dict[str, Any]:
    player_id = _normalize_player_id(player_id)
    dataset = get_player_clutch_dataset(season, player_id=player_id, **kwargs)
    if dataset["player_count"] == 0:
        raise WNBAClutchNotFoundError(
            f"No WNBA clutch row was found for player {player_id} under the requested situation filters."
        )
    return dataset


def get_team_clutch_context(team_key: str, season: int, **kwargs: Any) -> dict[str, Any]:
    normalized_team_key = _normalize_team_key(team_key, season)
    dataset = get_team_clutch_dataset(season, team_key=normalized_team_key, **kwargs)
    if dataset["team_count"] == 0:
        raise WNBAClutchNotFoundError(
            f"No WNBA clutch row was found for {normalized_team_key} under the requested situation filters."
        )
    return dataset
