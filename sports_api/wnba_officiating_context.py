"""WNBA game officials and observed foul/free-throw environment.

Step 4O is descriptive context only. It does not infer referee bias, create
whistle probabilities, or convert foul/free-throw rates into betting edges.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import (
    WNBA_LEAGUE_ID,
    WNBA_STATS_SOURCE,
    WNBA_STATS_SOURCE_URL,
    WNBAStatsUpstreamError,
    _request_stats_json,
)
from sports_api.wnba_season_stats import (
    WNBASeasonStatsUpstreamError,
    get_player_season_stats_dataset,
    get_team_season_stats_dataset,
)

OFFICIALS_ENDPOINT = "boxscoresummaryv3"
ALLOWED_SEASON_TYPES = ("Regular Season",)
MAX_LAST_N_GAMES = 100


class WNBAOfficiatingUpstreamError(RuntimeError):
    """Raised when official WNBA officiating/context data cannot be consumed safely."""


class WNBAOfficiatingNotFoundError(LookupError):
    """Raised when requested game/team/player context does not exist."""


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
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return resolved


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_LAST_N_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
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
    raise WNBAOfficiatingNotFoundError(
        f"WNBA team key {team_key!r} was not found for the {season} season."
    )


def _registry_team_from_summary(raw: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean(raw.get("teamTricode")) or "").casefold(),
        (_clean(raw.get("teamSlug")) or "").casefold(),
        (_clean(raw.get("teamName")) or "").casefold(),
    }
    city = _clean(raw.get("teamCity"))
    name = _clean(raw.get("teamName"))
    if city and name:
        values.add(f"{city} {name}".casefold())
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


def _summary_team(raw: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_summary(raw, season)
    return {
        "official_team_id": _to_int(raw.get("teamId")),
        "team_key": registry["team_key"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "team_abbreviation": registry["abbreviation"] if registry else _clean(raw.get("teamTricode")),
        "source_team_city": _clean(raw.get("teamCity")),
        "source_team_name": _clean(raw.get("teamName")),
        "source_team_tricode": _clean(raw.get("teamTricode")),
        "mapped_to_registry": registry is not None,
    }


def _rate(numerator: Any, denominator: Any, *, scale: float = 1.0) -> float | None:
    n = _to_float(numerator)
    d = _to_float(denominator)
    if n is None or d is None or d <= 0:
        return None
    return round((n / d) * scale, 4)


def _difference(left: Any, right: Any) -> float | None:
    l = _to_float(left)
    r = _to_float(right)
    if l is None or r is None:
        return None
    return round(l - r, 4)


def _foul_ft_profile(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "minutes": _to_float(stats.get("minutes")),
        "field_goal_attempts": _to_float(stats.get("field_goals_attempted")),
        "free_throws_made": _to_float(stats.get("free_throws_made")),
        "free_throws_attempted": _to_float(stats.get("free_throws_attempted")),
        "free_throw_percentage": _to_float(stats.get("free_throw_percentage")),
        "personal_fouls": _to_float(stats.get("personal_fouls")),
        "personal_fouls_drawn": _to_float(stats.get("personal_fouls_drawn")),
        "points": _to_float(stats.get("points")),
        "derived_observed": {
            "free_throw_attempt_rate_per_fga": _rate(
                stats.get("free_throws_attempted"), stats.get("field_goals_attempted")
            ),
            "free_throw_points_share": _rate(
                stats.get("free_throws_made"), stats.get("points")
            ),
            "fouls_drawn_minus_committed": _difference(
                stats.get("personal_fouls_drawn"), stats.get("personal_fouls")
            ),
            "free_throw_attempts_per_36_minutes": _rate(
                stats.get("free_throws_attempted"), stats.get("minutes"), scale=36.0
            ),
            "personal_fouls_per_36_minutes": _rate(
                stats.get("personal_fouls"), stats.get("minutes"), scale=36.0
            ),
            "fouls_drawn_per_36_minutes": _rate(
                stats.get("personal_fouls_drawn"), stats.get("minutes"), scale=36.0
            ),
        },
    }


def _league_measure(rows: list[dict[str, Any]], target_key: str, field: str) -> dict[str, Any]:
    pairs: list[tuple[str, float]] = []
    for row in rows:
        key = row.get("team_key")
        value = _to_float((row.get("stats") or {}).get(field))
        if key and value is not None:
            pairs.append((key, value))
    target = next((value for key, value in pairs if key == target_key), None)
    if target is None:
        return {
            "value": None,
            "league_average": None,
            "higher_value_rank": None,
            "league_team_count": len(pairs),
        }
    values = [value for _, value in pairs]
    return {
        "value": target,
        "league_average": round(sum(values) / len(values), 4) if values else None,
        "higher_value_rank": 1 + sum(value > target for value in values),
        "league_team_count": len(values),
    }


def _official(row: dict[str, Any], requested_game_id: str) -> dict[str, Any]:
    source_game_id = _clean(row.get("gameId")) or requested_game_id
    if source_game_id != requested_game_id:
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA game summary returned an official attached to a different game ID."
        )
    return {
        "person_id": _to_int(row.get("personId")),
        "name": _clean(row.get("name")),
        "name_initial": _clean(row.get("nameI")),
        "first_name": _clean(row.get("firstName")),
        "family_name": _clean(row.get("familyName")),
        "jersey_number": _clean(row.get("jerseyNum")),
    }


def get_game_officials_dataset(game_id: str, season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    requested_game_id = _game_id(game_id)

    try:
        payload, retrieved_at_utc, cache_hit = _request_stats_json(
            OFFICIALS_ENDPOINT,
            [("GameID", requested_game_id)],
        )
    except WNBAStatsUpstreamError as exc:
        raise WNBAOfficiatingUpstreamError(str(exc)) from exc

    summary = payload.get("boxScoreSummary")
    if not isinstance(summary, dict):
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA box-score summary is missing boxScoreSummary."
        )

    source_game_id = _clean(summary.get("gameId"))
    if source_game_id != requested_game_id:
        raise WNBAOfficiatingUpstreamError(
            f"Official WNBA box-score summary returned game ID {source_game_id!r}; "
            f"expected {requested_game_id}."
        )

    away = _summary_team(summary.get("awayTeam") or {}, season)
    home = _summary_team(summary.get("homeTeam") or {}, season)
    if not away["mapped_to_registry"] or not home["mapped_to_registry"]:
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA box-score summary returned an unmapped team identity."
        )
    if (
        away["official_team_id"] is not None
        and home["official_team_id"] is not None
        and away["official_team_id"] == home["official_team_id"]
    ):
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA box-score summary returned identical home and away team IDs."
        )

    raw_officials = summary.get("officials")
    if raw_officials is None:
        raw_officials = []
    if not isinstance(raw_officials, list):
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA box-score summary officials field is malformed."
        )
    officials = [
        _official(row, requested_game_id)
        for row in raw_officials
        if isinstance(row, dict)
    ]
    person_ids = [item["person_id"] for item in officials if item["person_id"] is not None]
    duplicate_person_ids = sorted(
        person_id for person_id in set(person_ids) if person_ids.count(person_id) > 1
    )
    if duplicate_person_ids:
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA box-score summary returned duplicate official person IDs: "
            + ", ".join(str(item) for item in duplicate_person_ids)
            + "."
        )

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": OFFICIALS_ENDPOINT,
        "data_type": "official_game_official_assignment",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game_id": requested_game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "game_status": {
            "code": _to_int(summary.get("gameStatus")),
            "text": _clean(summary.get("gameStatusText")),
            "period": _to_int(summary.get("period")),
            "clock": _clean(summary.get("gameClock")),
        },
        "away": away,
        "home": home,
        "official_count": len(officials),
        "officials_available": bool(officials),
        "assignment_status": (
            "assigned_from_official_box_score_summary"
            if officials
            else "not_available_from_official_box_score_summary"
        ),
        "officials": officials,
        "verification": {
            "requested_game_id_matches_source": True,
            "home_away_teams_mapped": True,
            "official_person_ids_unique": True,
            "referee_tendencies_or_bias_inferred": False,
        },
    }


def get_team_foul_ft_context(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
) -> dict[str, Any]:
    stable = _registry_team(team_key, season)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)

    try:
        dataset = get_team_season_stats_dataset(
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode="PerGame",
        )
    except WNBASeasonStatsUpstreamError as exc:
        raise WNBAOfficiatingUpstreamError(str(exc)) from exc

    teams = dataset.get("teams")
    if not isinstance(teams, list):
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA team statistics are missing team rows."
        )
    matching = [team for team in teams if team.get("team_key") == stable["team_key"]]
    if not matching:
        raise WNBAOfficiatingNotFoundError(
            f"No WNBA team foul/free-throw row was found for {stable['team_key']}."
        )
    if len(matching) != 1:
        raise WNBAOfficiatingUpstreamError(
            f"Official WNBA team statistics returned {len(matching)} rows for "
            f"{stable['team_key']}."
        )

    row = matching[0]
    stats = row.get("stats") or {}
    profile = _foul_ft_profile(stats)
    league_context = {
        "free_throws_attempted_per_game": _league_measure(
            teams, stable["team_key"], "free_throws_attempted"
        ),
        "personal_fouls_per_game": _league_measure(
            teams, stable["team_key"], "personal_fouls"
        ),
        "personal_fouls_drawn_per_game": _league_measure(
            teams, stable["team_key"], "personal_fouls_drawn"
        ),
    }

    return {
        "source": dataset.get("source"),
        "source_url": dataset.get("source_url"),
        "source_endpoint": dataset.get("source_endpoint"),
        "data_type": "observed_team_foul_free_throw_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "last_n_games": last_n_games,
        "window_scope": dataset.get("window_scope"),
        "team": {
            "team_key": stable["team_key"],
            "team_full_name": stable["full_name"],
            "team_abbreviation": stable["abbreviation"],
            "official_team_id": row.get("official_team_id"),
            "games_played": row.get("games_played"),
        },
        "profile": profile,
        "league_context": league_context,
        "retrieved_at_utc": dataset.get("retrieved_at_utc"),
        "cache_hit": dataset.get("cache_hit"),
        "verification": {
            "official_base_stats_used": True,
            "team_row_unique": True,
            "rates_are_observed_not_predictive": True,
            "higher_value_rank_is_not_a_quality_rank": True,
        },
    }


def get_player_foul_ft_context(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
) -> dict[str, Any]:
    get_wnba_teams(season)
    player_id = _player_id(player_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)

    try:
        dataset = get_player_season_stats_dataset(
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode="PerGame",
        )
    except WNBASeasonStatsUpstreamError as exc:
        raise WNBAOfficiatingUpstreamError(str(exc)) from exc

    players = dataset.get("players")
    if not isinstance(players, list):
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA player statistics are missing player rows."
        )
    matching = [row for row in players if row.get("player_id") == player_id]
    if not matching:
        raise WNBAOfficiatingNotFoundError(
            f"No WNBA foul/free-throw row was found for player {player_id}."
        )

    rows = []
    for row in matching:
        rows.append(
            {
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name"),
                "team_key": row.get("team_key"),
                "team_full_name": row.get("team_full_name"),
                "official_team_id": row.get("official_team_id"),
                "games_played": row.get("games_played"),
                "mapped_to_registry": row.get("mapped_to_registry"),
                "profile": _foul_ft_profile(row.get("stats") or {}),
            }
        )

    return {
        "source": dataset.get("source"),
        "source_url": dataset.get("source_url"),
        "source_endpoint": dataset.get("source_endpoint"),
        "data_type": "observed_player_foul_free_throw_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "last_n_games": last_n_games,
        "window_scope": dataset.get("window_scope"),
        "player_id": player_id,
        "official_row_count": len(rows),
        "single_official_row": len(rows) == 1,
        "aggregation_status": (
            "single_official_row"
            if len(rows) == 1
            else "multiple_official_rows_preserved_no_guess"
        ),
        "rows": rows,
        "retrieved_at_utc": dataset.get("retrieved_at_utc"),
        "cache_hit": dataset.get("cache_hit"),
        "verification": {
            "official_base_stats_used": True,
            "multiple_team_or_tot_rows_are_not_silently_collapsed": True,
            "rates_are_observed_not_predictive": True,
        },
    }


def get_game_whistle_context(
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
) -> dict[str, Any]:
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    officials = get_game_officials_dataset(game_id, season)

    away_key = (officials.get("away") or {}).get("team_key")
    home_key = (officials.get("home") or {}).get("team_key")
    if not away_key or not home_key:
        raise WNBAOfficiatingUpstreamError(
            "Official WNBA game summary did not provide two mapped teams."
        )

    away = get_team_foul_ft_context(
        away_key,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
    )
    home = get_team_foul_ft_context(
        home_key,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
    )

    away_profile = away["profile"]
    home_profile = home["profile"]
    away_fta = _to_float(away_profile.get("free_throws_attempted"))
    home_fta = _to_float(home_profile.get("free_throws_attempted"))
    away_pf = _to_float(away_profile.get("personal_fouls"))
    home_pf = _to_float(home_profile.get("personal_fouls"))
    away_pfd = _to_float(away_profile.get("personal_fouls_drawn"))
    home_pfd = _to_float(home_profile.get("personal_fouls_drawn"))

    def combined(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return round(left + right, 4)

    return {
        "source": "Kyre Sports API composition of official WNBA sources",
        "data_type": "observed_game_whistle_environment_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "last_n_games": last_n_games,
        "game_id": officials["game_id"],
        "official_assignment": officials,
        "away_team_context": away,
        "home_team_context": home,
        "combined_observed_team_rates": {
            "sum_free_throw_attempts_per_game": combined(away_fta, home_fta),
            "sum_personal_fouls_per_game": combined(away_pf, home_pf),
            "sum_personal_fouls_drawn_per_game": combined(away_pfd, home_pfd),
            "away_minus_home_free_throw_attempts_per_game": _difference(away_fta, home_fta),
        },
        "verification": {
            "both_team_contexts_match_game": (
                away["team"]["team_key"] == away_key
                and home["team"]["team_key"] == home_key
            ),
            "officials_are_current_game_assignment_only": True,
            "historical_referee_tendencies_included": False,
            "combined_rates_are_not_expected_game_totals": True,
            "no_whistle_probability_created": True,
        },
    }
