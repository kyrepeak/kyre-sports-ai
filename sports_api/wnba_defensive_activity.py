"""WNBA defensive tracking and hustle-source availability context.

Step 4P deliberately does *not* resurrect the legacy WNBA hustle endpoints.
Current wehoop diagnostics mark the WNBA hustle family (league hustle, hustle
box score, boxscore hustle) dead with no replacement.  The supported official
source used here is ``boxscoreplayertrackv3``, which exposes game-level player
and team tracking such as rebound chances, offensive contested/uncontested
shooting, and defended-at-rim field goals.

This module is descriptive only.  It creates no defensive grade, fatigue score,
matchup probability, or betting edge.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import (
    WNBA_LEAGUE_ID,
    WNBA_STATS_SOURCE,
    WNBA_STATS_SOURCE_URL,
    WNBAStatsUpstreamError,
    _request_stats_json,
)
from sports_api.wnba_team_history import (
    WNBATeamHistoryUpstreamError,
    get_team_game_log_dataset,
)

PLAYERTRACK_ENDPOINT = "boxscoreplayertrackv3"
MAX_AGGREGATE_GAMES = 20

LEGACY_HUSTLE_ENDPOINTS = (
    "leaguehustlestatsplayer",
    "leaguehustlestatsteam",
    "leaguehustlestatsplayerleaders",
    "leaguehustlestatsteamleaders",
    "hustlestatsboxscore",
    "boxscorehustlev2",
)

UNAVAILABLE_LEGACY_HUSTLE_METRICS = (
    "defensive_contested_shots",
    "defensive_contested_shots_2pt",
    "defensive_contested_shots_3pt",
    "deflections",
    "charges_drawn",
    "screen_assists",
    "screen_assist_points",
    "offensive_loose_balls_recovered",
    "defensive_loose_balls_recovered",
    "loose_balls_recovered",
    "offensive_box_outs",
    "defensive_box_outs",
    "box_outs",
)


class WNBADefensiveActivityUpstreamError(RuntimeError):
    """Raised when supported official tracking data cannot be consumed safely."""


class WNBADefensiveActivityNotFoundError(LookupError):
    """Raised when requested supported tracking data is not available."""


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
        result = float(text)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _minutes_to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None

    numeric = _to_float(text)
    if numeric is not None:
        return numeric

    if text.upper().startswith("PT"):
        body = text.upper()[2:]
        hours = minutes = seconds = 0.0
        try:
            if "H" in body:
                hours_text, body = body.split("H", 1)
                hours = float(hours_text or 0)
            if "M" in body:
                minutes_text, body = body.split("M", 1)
                minutes = float(minutes_text or 0)
            if body.endswith("S"):
                seconds = float(body[:-1] or 0)
            return hours * 60.0 + minutes + seconds / 60.0
        except ValueError:
            return None

    if ":" in text:
        try:
            minute_text, second_text = text.split(":", 1)
            return float(minute_text) + float(second_text) / 60.0
        except ValueError:
            return None
    return None


def _ratio(numerator: Any, denominator: Any) -> float | None:
    n = _to_float(numerator)
    d = _to_float(denominator)
    if n is None or d is None or d <= 0:
        return None
    return round(n / d, 4)


def _per_minutes(value: Any, minutes: Any, scale: float) -> float | None:
    v = _to_float(value)
    m = _to_float(minutes)
    if v is None or m is None or m <= 0:
        return None
    return round((v / m) * scale, 4)


def _choice(value: str, allowed: Iterable[str], label: str) -> str:
    text = str(value).strip()
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(text.casefold())
    if resolved is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return resolved


def _aggregate_game_count(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_AGGREGATE_GAMES
    ):
        raise ValueError(
            f"WNBA last_n_games must be an integer from 1 through {MAX_AGGREGATE_GAMES} "
            "for defensive-tracking aggregation."
        )
    return value


def _game_id(value: str) -> str:
    text = str(value).strip()
    if len(text) != 10 or not text.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return text


def _player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _registry_team(team_key: str, season: int) -> dict[str, Any]:
    key = str(team_key).strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == key:
            return team
    raise WNBADefensiveActivityNotFoundError(
        f"WNBA team key {team_key!r} was not found for the {season} season."
    )


def _registry_team_from_raw(raw: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean(raw.get("teamTricode")) or "").casefold(),
        (_clean(raw.get("teamSlug")) or "").casefold(),
        (_clean(raw.get("teamName")) or "").casefold(),
    }
    city = _clean(raw.get("teamCity"))
    name = _clean(raw.get("teamName"))
    if city and name:
        values.add(f"{city} {name}".casefold())

    # Current WNBA feeds can use PDX for Portland even though the stable
    # project abbreviation remains POR.
    if "pdx" in values:
        values.update({"por", "portland-fire"})
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


def _tracking_profile(stats: dict[str, Any]) -> dict[str, Any]:
    minutes = _minutes_to_float(stats.get("minutes"))
    contested_made = _to_float(stats.get("contestedFieldGoalsMade"))
    contested_attempted = _to_float(stats.get("contestedFieldGoalsAttempted"))
    uncontested_made = _to_float(stats.get("uncontestedFieldGoalsMade"))
    uncontested_attempted = _to_float(stats.get("uncontestedFieldGoalsAttempted"))
    rim_made = _to_float(stats.get("defendedAtRimFieldGoalsMade"))
    rim_attempted = _to_float(stats.get("defendedAtRimFieldGoalsAttempted"))
    rebound_chances_total = _to_float(stats.get("reboundChancesTotal"))

    return {
        "minutes": minutes,
        "movement": {
            "speed": _to_float(stats.get("speed")),
            "distance": _to_float(stats.get("distance")),
        },
        "rebound_opportunity": {
            "offensive_rebound_chances": _to_float(stats.get("reboundChancesOffensive")),
            "defensive_rebound_chances": _to_float(stats.get("reboundChancesDefensive")),
            "total_rebound_chances": rebound_chances_total,
            "rebound_chances_per_36_minutes": _per_minutes(
                rebound_chances_total, minutes, 36.0
            ),
        },
        "ball_activity": {
            "touches": _to_float(stats.get("touches")),
            "passes": _to_float(stats.get("passes")),
            "assists": _to_float(stats.get("assists")),
            "secondary_assists": _to_float(stats.get("secondaryAssists")),
            "free_throw_assists": _to_float(stats.get("freeThrowAssists")),
        },
        # IMPORTANT: contested/uncontested FGM/FGA in PlayerTrack V3 describe
        # the player's/team's own shot attempts, not defensive shot contests.
        "offensive_contested_shooting": {
            "contested_field_goals_made": contested_made,
            "contested_field_goals_attempted": contested_attempted,
            "source_contested_field_goal_percentage": _to_float(
                stats.get("contestedFieldGoalPercentage")
            ),
            "derived_contested_field_goal_percentage": _ratio(
                contested_made, contested_attempted
            ),
            "uncontested_field_goals_made": uncontested_made,
            "uncontested_field_goals_attempted": uncontested_attempted,
            "source_uncontested_field_goal_percentage": _to_float(
                stats.get("uncontestedFieldGoalPercentage")
            ),
            "derived_uncontested_field_goal_percentage": _ratio(
                uncontested_made, uncontested_attempted
            ),
            "source_overall_field_goal_percentage": _to_float(
                stats.get("fieldGoalPercentage")
            ),
            "this_is_offensive_shot_context_not_defensive_contests": True,
        },
        "defended_at_rim": {
            "field_goals_made_against": rim_made,
            "field_goals_attempted_defended": rim_attempted,
            "source_field_goal_percentage_against": _to_float(
                stats.get("defendedAtRimFieldGoalPercentage")
            ),
            "derived_field_goal_percentage_against": _ratio(rim_made, rim_attempted),
            "attempts_defended_per_36_minutes": _per_minutes(
                rim_attempted, minutes, 36.0
            ),
            "observed_context_not_causal_defensive_effect": True,
        },
    }


def _normalize_player(raw: dict[str, Any], team: dict[str, Any], game_id: str) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "player_id": _to_int(raw.get("personId")),
        "first_name": _clean(raw.get("firstName")),
        "family_name": _clean(raw.get("familyName")),
        "name_initial": _clean(raw.get("nameI")),
        "player_slug": _clean(raw.get("playerSlug")),
        "position": _clean(raw.get("position")),
        "comment": _clean(raw.get("comment")),
        "jersey_number": _clean(raw.get("jerseyNum")),
        "team_key": team["team_key"],
        "team_full_name": team["full_name"],
        "tracking": _tracking_profile(raw.get("statistics") or {}),
    }


def _normalize_team(raw: dict[str, Any], season: int, game_id: str) -> dict[str, Any]:
    registry = _registry_team_from_raw(raw, season)
    if registry is None:
        raise WNBADefensiveActivityUpstreamError(
            "WNBA PlayerTrack V3 returned an unmapped team identity."
        )

    raw_players = raw.get("players")
    if raw_players is None:
        raw_players = []
    if not isinstance(raw_players, list):
        raise WNBADefensiveActivityUpstreamError(
            "WNBA PlayerTrack V3 returned a malformed players field."
        )

    players = [
        _normalize_player(player, registry, game_id)
        for player in raw_players
        if isinstance(player, dict)
    ]
    return {
        "official_team_id": _to_int(raw.get("teamId")),
        "team_key": registry["team_key"],
        "team_full_name": registry["full_name"],
        "team_abbreviation": registry["abbreviation"],
        "source_team_tricode": _clean(raw.get("teamTricode")),
        "source_team_slug": _clean(raw.get("teamSlug")),
        "tracking": _tracking_profile(raw.get("statistics") or {}),
        "player_count": len(players),
        "players": players,
    }


def get_hustle_source_status(season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    return {
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "data_type": "wnba_hustle_source_capability_status",
        "legacy_hustle_endpoints": {
            "status": "disabled_dead_no_current_wnba_replacement",
            "endpoints": list(LEGACY_HUSTLE_ENDPOINTS),
            "metrics_not_claimed": list(UNAVAILABLE_LEGACY_HUSTLE_METRICS),
        },
        "supported_replacement_context": {
            "source": WNBA_STATS_SOURCE,
            "source_endpoint": PLAYERTRACK_ENDPOINT,
            "available": True,
            "provides": [
                "rebound_chances",
                "touches_and_passes",
                "offensive_contested_and_uncontested_shooting",
                "defended_at_rim_field_goals",
                "movement_speed_and_distance",
            ],
            "does_not_provide_legacy_hustle_fields": True,
        },
        "verification": {
            "dead_hustle_endpoints_are_not_called": True,
            "unavailable_metrics_are_not_fabricated": True,
            "no_defensive_grade_created": True,
        },
    }


def get_game_defensive_tracking(game_id: str, season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    requested_game_id = _game_id(game_id)

    try:
        payload, retrieved_at_utc, cache_hit = _request_stats_json(
            PLAYERTRACK_ENDPOINT,
            [("GameID", requested_game_id)],
        )
    except WNBAStatsUpstreamError as exc:
        raise WNBADefensiveActivityUpstreamError(str(exc)) from exc

    if "boxScorePlayerTrack" not in payload:
        raise WNBADefensiveActivityNotFoundError(
            f"WNBA PlayerTrack V3 is not available for game {requested_game_id}."
        )
    root = payload.get("boxScorePlayerTrack")
    if not isinstance(root, dict):
        raise WNBADefensiveActivityUpstreamError(
            "WNBA PlayerTrack V3 boxScorePlayerTrack field is malformed."
        )

    source_game_id = _clean(root.get("gameId"))
    if source_game_id != requested_game_id:
        raise WNBADefensiveActivityUpstreamError(
            f"WNBA PlayerTrack V3 returned game ID {source_game_id!r}; expected {requested_game_id}."
        )

    home_raw = root.get("homeTeam")
    away_raw = root.get("awayTeam")
    if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
        raise WNBADefensiveActivityUpstreamError(
            "WNBA PlayerTrack V3 is missing homeTeam or awayTeam."
        )

    home = _normalize_team(home_raw, season, requested_game_id)
    away = _normalize_team(away_raw, season, requested_game_id)
    if (
        home["official_team_id"] is not None
        and away["official_team_id"] is not None
        and home["official_team_id"] == away["official_team_id"]
    ):
        raise WNBADefensiveActivityUpstreamError(
            "WNBA PlayerTrack V3 returned identical home and away team IDs."
        )

    all_players = away["players"] + home["players"]
    player_ids = [item["player_id"] for item in all_players if item["player_id"] is not None]
    duplicate_ids = sorted(
        player_id for player_id in set(player_ids) if player_ids.count(player_id) > 1
    )
    if duplicate_ids:
        raise WNBADefensiveActivityUpstreamError(
            "WNBA PlayerTrack V3 returned duplicate player IDs across the game: "
            + ", ".join(str(item) for item in duplicate_ids)
            + "."
        )

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": PLAYERTRACK_ENDPOINT,
        "data_type": "official_game_player_tracking_defensive_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game_id": requested_game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "away": away,
        "home": home,
        "player_count": len(all_players),
        "legacy_hustle_metrics": {
            "available": False,
            "not_returned_by_playertrack_v3": list(UNAVAILABLE_LEGACY_HUSTLE_METRICS),
        },
        "verification": {
            "requested_game_id_matches_source": True,
            "home_away_teams_mapped": True,
            "player_ids_unique": True,
            "contested_fg_fields_labeled_as_offensive_shot_context": True,
            "defended_at_rim_labeled_observed_not_causal": True,
            "unavailable_hustle_fields_fabricated": False,
        },
    }


_TOTAL_PATHS = (
    ("minutes",),
    ("movement", "distance"),
    ("rebound_opportunity", "offensive_rebound_chances"),
    ("rebound_opportunity", "defensive_rebound_chances"),
    ("rebound_opportunity", "total_rebound_chances"),
    ("ball_activity", "touches"),
    ("ball_activity", "passes"),
    ("ball_activity", "assists"),
    ("ball_activity", "secondary_assists"),
    ("ball_activity", "free_throw_assists"),
    ("offensive_contested_shooting", "contested_field_goals_made"),
    ("offensive_contested_shooting", "contested_field_goals_attempted"),
    ("offensive_contested_shooting", "uncontested_field_goals_made"),
    ("offensive_contested_shooting", "uncontested_field_goals_attempted"),
    ("defended_at_rim", "field_goals_made_against"),
    ("defended_at_rim", "field_goals_attempted_defended"),
)


def _path_value(profile: dict[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = profile
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return _to_float(value)


def _path_name(path: tuple[str, ...]) -> str:
    return "__".join(path)


def _aggregate_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, float | None] = {}
    for path in _TOTAL_PATHS:
        values = [
            value
            for profile in profiles
            if (value := _path_value(profile, path)) is not None
        ]
        totals[_path_name(path)] = round(sum(values), 4) if values else None

    game_count = len(profiles)
    per_game = {
        key: (round(value / game_count, 4) if value is not None and game_count else None)
        for key, value in totals.items()
    }

    total_minutes = totals.get("minutes")
    total_rim_attempts = totals.get("defended_at_rim__field_goals_attempted_defended")
    total_rim_makes = totals.get("defended_at_rim__field_goals_made_against")
    total_contested_attempts = totals.get(
        "offensive_contested_shooting__contested_field_goals_attempted"
    )
    total_contested_makes = totals.get(
        "offensive_contested_shooting__contested_field_goals_made"
    )
    total_uncontested_attempts = totals.get(
        "offensive_contested_shooting__uncontested_field_goals_attempted"
    )
    total_uncontested_makes = totals.get(
        "offensive_contested_shooting__uncontested_field_goals_made"
    )

    speed_pairs = [
        (
            _path_value(profile, ("movement", "speed")),
            _path_value(profile, ("minutes",)),
        )
        for profile in profiles
    ]
    weighted_speed_num = sum(
        speed * minutes
        for speed, minutes in speed_pairs
        if speed is not None and minutes is not None and minutes > 0
    )
    weighted_speed_den = sum(
        minutes
        for speed, minutes in speed_pairs
        if speed is not None and minutes is not None and minutes > 0
    )

    return {
        "games_with_tracking": game_count,
        "totals": totals,
        "per_game": per_game,
        "weighted_rates": {
            "offensive_contested_field_goal_percentage": _ratio(
                total_contested_makes, total_contested_attempts
            ),
            "offensive_uncontested_field_goal_percentage": _ratio(
                total_uncontested_makes, total_uncontested_attempts
            ),
            "defended_at_rim_field_goal_percentage_against": _ratio(
                total_rim_makes, total_rim_attempts
            ),
            "minute_weighted_speed": (
                round(weighted_speed_num / weighted_speed_den, 4)
                if weighted_speed_den > 0
                else None
            ),
        },
        "per_36_minutes": {
            "defended_at_rim_attempts": _per_minutes(
                total_rim_attempts, total_minutes, 36.0
            ),
            "total_rebound_chances": _per_minutes(
                totals.get("rebound_opportunity__total_rebound_chances"),
                total_minutes,
                36.0,
            ),
            "touches": _per_minutes(
                totals.get("ball_activity__touches"), total_minutes, 36.0
            ),
        },
        "verification": {
            "advanced_percentages_are_weighted_from_makes_and_attempts": True,
            "speed_is_minute_weighted_not_summed": True,
            "no_defensive_grade_created": True,
        },
    }


def get_player_defensive_tracking(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
) -> dict[str, Any]:
    get_wnba_teams(season)
    player_id = _player_id(player_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _aggregate_game_count(last_n_games)

    try:
        history = get_player_game_log_dataset(
            player_id,
            season,
            season_type=season_type,
        )
    except WNBAHistoryUpstreamError as exc:
        raise WNBADefensiveActivityUpstreamError(str(exc)) from exc

    games = history.get("games")
    if not isinstance(games, list):
        raise WNBADefensiveActivityUpstreamError(
            "WNBA player game log returned a malformed games field."
        )
    selected = games[:last_n_games]
    if not selected:
        raise WNBADefensiveActivityNotFoundError(
            f"No WNBA games were found for player {player_id} in {season}."
        )

    profiles: list[dict[str, Any]] = []
    game_rows: list[dict[str, Any]] = []
    missing_game_ids: list[str] = []
    team_keys: list[str] = []
    player_name: str | None = None

    for history_game in selected:
        game_id = _clean(history_game.get("game_id"))
        if game_id is None:
            continue
        try:
            dataset = get_game_defensive_tracking(game_id, season)
        except WNBADefensiveActivityNotFoundError:
            missing_game_ids.append(game_id)
            continue

        matches = [
            player
            for side in (dataset["away"], dataset["home"])
            for player in side["players"]
            if player.get("player_id") == player_id
        ]
        if len(matches) > 1:
            raise WNBADefensiveActivityUpstreamError(
                f"WNBA PlayerTrack V3 returned player {player_id} more than once in game {game_id}."
            )
        if not matches:
            missing_game_ids.append(game_id)
            continue

        player = matches[0]
        profile = player["tracking"]
        profiles.append(profile)
        if player["team_key"] not in team_keys:
            team_keys.append(player["team_key"])
        player_name = " ".join(
            part for part in (player.get("first_name"), player.get("family_name")) if part
        ) or player.get("name_initial") or player_name
        game_rows.append(
            {
                "game_id": game_id,
                "game_date": history_game.get("game_date"),
                "team_key": player["team_key"],
                "opponent_team_key": (history_game.get("matchup") or {}).get(
                    "opponent_team_key"
                ),
                "tracking": profile,
            }
        )

    if not profiles:
        raise WNBADefensiveActivityNotFoundError(
            f"PlayerTrack V3 was unavailable for the selected recent games for player {player_id}."
        )

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": PLAYERTRACK_ENDPOINT,
        "data_type": "official_recent_player_defensive_tracking_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "player_name": player_name,
        "team_keys_observed": team_keys,
        "requested_last_n_games": last_n_games,
        "selected_game_count": len(selected),
        "tracking_game_count": len(profiles),
        "missing_tracking_game_ids": missing_game_ids,
        "aggregate": _aggregate_profiles(profiles),
        "games": game_rows,
        "legacy_hustle_metrics": {
            "available": False,
            "not_returned_by_playertrack_v3": list(UNAVAILABLE_LEGACY_HUSTLE_METRICS),
        },
        "verification": {
            "selected_games_come_from_official_player_game_log": True,
            "missing_tracking_games_are_reported_not_fabricated": True,
            "multi_team_history_preserved": len(team_keys) > 1,
            "no_defensive_grade_created": True,
        },
    }


def get_team_defensive_tracking(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
) -> dict[str, Any]:
    team = _registry_team(team_key, season)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _aggregate_game_count(last_n_games)

    try:
        history = get_team_game_log_dataset(
            team["team_key"],
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except WNBATeamHistoryUpstreamError as exc:
        raise WNBADefensiveActivityUpstreamError(str(exc)) from exc

    games = history.get("games")
    if not isinstance(games, list):
        raise WNBADefensiveActivityUpstreamError(
            "WNBA team game log returned a malformed games field."
        )
    if not games:
        raise WNBADefensiveActivityNotFoundError(
            f"No WNBA games were found for {team['team_key']} in {season}."
        )

    profiles: list[dict[str, Any]] = []
    game_rows: list[dict[str, Any]] = []
    missing_game_ids: list[str] = []

    for history_game in games:
        game_id = _clean(history_game.get("game_id"))
        if game_id is None:
            continue
        try:
            dataset = get_game_defensive_tracking(game_id, season)
        except WNBADefensiveActivityNotFoundError:
            missing_game_ids.append(game_id)
            continue

        sides = [side for side in (dataset["away"], dataset["home"]) if side["team_key"] == team["team_key"]]
        if len(sides) != 1:
            raise WNBADefensiveActivityUpstreamError(
                f"WNBA PlayerTrack V3 could not uniquely resolve {team['team_key']} in game {game_id}."
            )
        side = sides[0]
        profile = side["tracking"]
        profiles.append(profile)
        game_rows.append(
            {
                "game_id": game_id,
                "game_date": history_game.get("game_date"),
                "location": history_game.get("location"),
                "opponent_team_key": history_game.get("opponent_team_key"),
                "tracking": profile,
            }
        )

    if not profiles:
        raise WNBADefensiveActivityNotFoundError(
            f"PlayerTrack V3 was unavailable for the selected recent games for {team['team_key']}."
        )

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": PLAYERTRACK_ENDPOINT,
        "data_type": "official_recent_team_defensive_tracking_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "team": team,
        "requested_last_n_games": last_n_games,
        "selected_game_count": len(games),
        "tracking_game_count": len(profiles),
        "missing_tracking_game_ids": missing_game_ids,
        "aggregate": _aggregate_profiles(profiles),
        "games": game_rows,
        "legacy_hustle_metrics": {
            "available": False,
            "not_returned_by_playertrack_v3": list(UNAVAILABLE_LEGACY_HUSTLE_METRICS),
        },
        "verification": {
            "selected_games_come_from_official_team_game_log": True,
            "missing_tracking_games_are_reported_not_fabricated": True,
            "no_defensive_grade_created": True,
        },
    }
