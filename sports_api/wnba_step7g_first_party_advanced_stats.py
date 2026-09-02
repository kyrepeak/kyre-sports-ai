"""Step 7G first-party adapter for frozen Step 4F advanced context.

The public WNBA advanced-stat pages are first party but load their league-dash
rows from stats.wnba.com in the browser. That direct transport is not reliable
from the Step 7G CI/runtime environment. This adapter therefore derives only the
advanced metrics that can be reproduced from already-certified WNBA.com game
pages and exact recent-game identities.

Important semantic boundary:
- fields named ``estimated_*`` are box-score-derived estimates and are never
  presented as the official on-court LeagueDash values;
- exact shooting/rebounding/assist/turnover rates that are reproducible from
  official counting stats are populated explicitly;
- player on-court offensive/defensive/net rating and official pace remain null
  because the certified first-party page surface does not expose the required
  on-court possession split;
- no projection, betting, sportsbook, persistence, scheduler, or production
  behavior exists in this module.

The adapter is intentionally scoped to 2026 Regular Season and PerGame because
that is the frozen Step 4W readiness path currently being certified.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable

from sports_api.wnba_advanced_stats import WNBAAdvancedStatsUpstreamError
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_step7g_first_party_history import (
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_game_box_score_dataset,
    get_first_party_player_recent_game_log_dataset,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)
from sports_api.wnba_step7g_first_party_team_history_cup_safe import (
    CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON,
    get_first_party_team_game_log_dataset,
)

WNBA_LEAGUE_ID = "10"
CERTIFIED_SEASON = 2026
CERTIFIED_SEASON_TYPE = "Regular Season"
CERTIFIED_PER_MODE = "PerGame"
REGULAR_GAME_PREFIX_BY_SEASON = {2026: "10226"}
MAX_CERTIFIED_PLAYER_LATEST_GAMES = 5

SOURCE = "WNBA.com First-Party Box Score Derived Advanced Context"
SOURCE_URL = "https://www.wnba.com/"
SOURCE_ENDPOINT = (
    "wnba.com player.latestGames/team-history exact IDs + "
    "wnba.com/game/[game_id]::__NEXT_DATA__.props.pageProps.game"
)
SOURCE_VARIANT = "certified_box_count_advanced_derivation_v1"

_REQUIRED_COUNT_KEYS = (
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
)


class _AdvancedNotFound(WNBAAdvancedStatsUpstreamError):
    """Internal fail-soft-compatible not-found classification."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WNBAAdvancedStatsUpstreamError(
            f"Official WNBA.com box score is missing numeric {label}."
        )
    return float(value)


def _safe_div(numerator: float, denominator: float, *, scale: float = 1.0) -> float | None:
    if denominator <= 0.0:
        return None
    return round(scale * numerator / denominator, 6)


def _validate_scope(season: int, season_type: str, per_mode: str, last_n_games: int) -> tuple[str, str, int]:
    get_wnba_teams(season)
    if season != CERTIFIED_SEASON:
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G first-party advanced adapter is certified only for {CERTIFIED_SEASON}."
        )
    normalized_type = str(season_type).strip()
    if normalized_type.casefold() != CERTIFIED_SEASON_TYPE.casefold():
        raise WNBAAdvancedStatsUpstreamError(
            "Step 7G first-party advanced adapter is certified only for Regular Season."
        )
    normalized_mode = str(per_mode).strip()
    if normalized_mode.casefold() != CERTIFIED_PER_MODE.casefold():
        raise WNBAAdvancedStatsUpstreamError(
            "Step 7G first-party advanced adapter is certified only for PerGame."
        )
    if not isinstance(last_n_games, int) or isinstance(last_n_games, bool) or last_n_games <= 0:
        raise WNBAAdvancedStatsUpstreamError(
            "Step 7G first-party advanced adapter requires last_n_games >= 1."
        )
    return CERTIFIED_SEASON_TYPE, CERTIFIED_PER_MODE, last_n_games


def _validate_player_id(player_id: int | None) -> int:
    if not isinstance(player_id, int) or isinstance(player_id, bool) or player_id <= 0:
        raise WNBAAdvancedStatsUpstreamError(
            "Step 7G first-party advanced player adapter requires a positive player_id."
        )
    return player_id


def _validate_team_key(team_key: str | None, season: int) -> str:
    if team_key is None:
        raise WNBAAdvancedStatsUpstreamError(
            "Step 7G first-party advanced team adapter requires team_key."
        )
    folded = str(team_key).strip().casefold()
    matches = [team for team in get_wnba_teams(season) if team["team_key"].casefold() == folded]
    if len(matches) != 1:
        raise WNBAAdvancedStatsUpstreamError(
            f"Step 7G advanced team_key {team_key!r} did not resolve exactly once."
        )
    return str(matches[0]["team_key"])


def _regular_game_id(game_id: str, season: int) -> bool:
    if game_id in CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON.get(season, frozenset()):
        return False
    prefix = REGULAR_GAME_PREFIX_BY_SEASON.get(season)
    return bool(prefix and len(game_id) == 10 and game_id.isdigit() and game_id.startswith(prefix))


def _stats(row: dict[str, Any], *, label: str) -> dict[str, Any]:
    stats = row.get("stats")
    if not isinstance(stats, dict):
        raise WNBAAdvancedStatsUpstreamError(f"{label} is missing normalized box-score stats.")
    for key in _REQUIRED_COUNT_KEYS:
        _number(stats.get(key), label=f"{label}.{key}")
    if _number(stats.get("minutes"), label=f"{label}.minutes") <= 0.0:
        raise WNBAAdvancedStatsUpstreamError(f"{label} has non-positive minutes.")
    return stats


def _box_teams(box: dict[str, Any], game_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if _clean(box.get("game_id")) != game_id:
        raise WNBAAdvancedStatsUpstreamError(
            f"Official WNBA.com box returned wrong game ID for {game_id}."
        )
    away = box.get("away")
    home = box.get("home")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise WNBAAdvancedStatsUpstreamError(f"Official WNBA.com box {game_id} is missing away/home teams.")
    if _clean(away.get("team_key")) == _clean(home.get("team_key")):
        raise WNBAAdvancedStatsUpstreamError(f"Official WNBA.com box {game_id} has duplicate team identity.")
    _stats(away, label=f"{game_id}.away")
    _stats(home, label=f"{game_id}.home")
    return away, home


def _team_side(box: dict[str, Any], game_id: str, team_key: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    away, home = _box_teams(box, game_id)
    matches: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    if _clean(away.get("team_key")) == team_key:
        matches.append((away, home, "away"))
    if _clean(home.get("team_key")) == team_key:
        matches.append((home, away, "home"))
    if len(matches) != 1:
        raise WNBAAdvancedStatsUpstreamError(
            f"Team {team_key} did not resolve exactly once in official box {game_id}."
        )
    return matches[0]


def _player_side(box: dict[str, Any], game_id: str, player_id: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    away, home = _box_teams(box, game_id)
    found: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]] = []
    for side_name, team, opponent in (("away", away, home), ("home", home, away)):
        players = team.get("players")
        if not isinstance(players, list):
            raise WNBAAdvancedStatsUpstreamError(
                f"Official WNBA.com box {game_id} has malformed {side_name} players."
            )
        for row in players:
            if isinstance(row, dict) and _to_int(row.get("player_id")) == player_id:
                found.append((row, team, opponent, side_name))
    if len(found) != 1:
        raise WNBAAdvancedStatsUpstreamError(
            f"Player {player_id} did not resolve exactly once in official box {game_id}."
        )
    player, team, opponent, side_name = found[0]
    if player.get("appeared") is not True:
        raise WNBAAdvancedStatsUpstreamError(
            f"Player {player_id} did not appear in official box {game_id}."
        )
    _stats(player, label=f"{game_id}.player.{player_id}")
    return player, team, opponent, side_name


def _sum_stats(rows: Iterable[dict[str, Any]], *, label: str) -> dict[str, float]:
    totals = {key: 0.0 for key in _REQUIRED_COUNT_KEYS}
    count = 0
    for row in rows:
        stats = _stats(row, label=f"{label}[{count}]")
        for key in totals:
            totals[key] += _number(stats[key], label=f"{label}[{count}].{key}")
        count += 1
    if count == 0:
        raise WNBAAdvancedStatsUpstreamError(f"No official box rows were available for {label}.")
    return totals


def _pie_numerator(stats: dict[str, float]) -> float:
    return (
        stats["points"]
        + stats["field_goals_made"]
        + stats["free_throws_made"]
        - stats["field_goals_attempted"]
        - stats["free_throws_attempted"]
        + stats["defensive_rebounds"]
        + 0.5 * stats["offensive_rebounds"]
        + stats["assists"]
        + stats["steals"]
        + 0.5 * stats["blocks"]
        - stats["personal_fouls"]
        - stats["turnovers"]
    )


def _estimated_possessions(team: dict[str, float], opp: dict[str, float]) -> float:
    def side(a: dict[str, float], b: dict[str, float]) -> float:
        rebound_denom = a["offensive_rebounds"] + b["defensive_rebounds"]
        oreb_factor = 0.0
        if rebound_denom > 0.0:
            oreb_factor = (
                1.07
                * (a["offensive_rebounds"] / rebound_denom)
                * (a["field_goals_attempted"] - a["field_goals_made"])
            )
        return (
            a["field_goals_attempted"]
            + 0.4 * a["free_throws_attempted"]
            - oreb_factor
            + a["turnovers"]
        )
    value = 0.5 * (side(team, opp) + side(opp, team))
    if value <= 0.0:
        raise WNBAAdvancedStatsUpstreamError("Derived possession estimate was non-positive.")
    return value


def _team_advanced(team: dict[str, float], opp: dict[str, float], game_count: int) -> dict[str, Any]:
    possessions = _estimated_possessions(team, opp)
    team_minutes = team["minutes"] / 5.0
    estimated_pace = _safe_div(possessions, team_minutes, scale=40.0)
    pie_den = _pie_numerator(team) + _pie_numerator(opp)
    return {
        "estimated_offensive_rating": _safe_div(team["points"], possessions, scale=100.0),
        "offensive_rating": None,
        "estimated_defensive_rating": _safe_div(opp["points"], possessions, scale=100.0),
        "defensive_rating": None,
        "estimated_net_rating": (
            None
            if possessions <= 0.0
            else round(100.0 * (team["points"] - opp["points"]) / possessions, 6)
        ),
        "net_rating": None,
        "assist_percentage": _safe_div(team["assists"], team["field_goals_made"], scale=100.0),
        "assist_to_turnover_ratio": _safe_div(team["assists"], team["turnovers"]),
        "estimated_assist_ratio": _safe_div(
            team["assists"],
            team["field_goals_attempted"] + 0.44 * team["free_throws_attempted"] + team["assists"] + team["turnovers"],
            scale=100.0,
        ),
        "assist_ratio": None,
        "estimated_offensive_rebound_percentage": _safe_div(
            team["offensive_rebounds"], team["offensive_rebounds"] + opp["defensive_rebounds"], scale=100.0
        ),
        "offensive_rebound_percentage": None,
        "estimated_defensive_rebound_percentage": _safe_div(
            team["defensive_rebounds"], team["defensive_rebounds"] + opp["offensive_rebounds"], scale=100.0
        ),
        "defensive_rebound_percentage": None,
        "estimated_rebound_percentage": _safe_div(
            team["rebounds"], team["rebounds"] + opp["rebounds"], scale=100.0
        ),
        "rebound_percentage": None,
        "estimated_turnover_percentage": _safe_div(
            team["turnovers"],
            team["field_goals_attempted"] + 0.44 * team["free_throws_attempted"] + team["turnovers"],
            scale=100.0,
        ),
        "team_turnover_percentage": None,
        "effective_field_goal_percentage": _safe_div(
            team["field_goals_made"] + 0.5 * team["three_pointers_made"],
            team["field_goals_attempted"],
        ),
        "true_shooting_percentage": _safe_div(
            team["points"], 2.0 * (team["field_goals_attempted"] + 0.44 * team["free_throws_attempted"])
        ),
        "estimated_pace": estimated_pace,
        "pace": None,
        "pace_per_40": estimated_pace,
        "possessions": round(possessions / game_count, 6),
        "player_impact_estimate": _safe_div(_pie_numerator(team), pie_den),
    }


def _player_advanced(
    player: dict[str, float],
    team: dict[str, float],
    opp: dict[str, float],
    game_count: int,
) -> dict[str, Any]:
    player_minutes = player["minutes"]
    team_floor_minutes = team["minutes"] / 5.0
    if player_minutes <= 0.0 or team_floor_minutes <= 0.0:
        raise WNBAAdvancedStatsUpstreamError("Player/team minutes were insufficient for advanced derivation.")

    usage_den = player_minutes * (
        team["field_goals_attempted"] + 0.44 * team["free_throws_attempted"] + team["turnovers"]
    )
    usage_num = (
        player["field_goals_attempted"] + 0.44 * player["free_throws_attempted"] + player["turnovers"]
    ) * team_floor_minutes

    expected_team_fgm_while_on_floor = (player_minutes / team_floor_minutes) * team["field_goals_made"]
    ast_den = expected_team_fgm_while_on_floor - player["field_goals_made"]
    possessions = _estimated_possessions(team, opp)
    estimated_pace = _safe_div(possessions, team_floor_minutes, scale=40.0)
    pie_den = _pie_numerator(team) + _pie_numerator(opp)

    return {
        "estimated_offensive_rating": None,
        "offensive_rating": None,
        "estimated_defensive_rating": None,
        "defensive_rating": None,
        "estimated_net_rating": None,
        "net_rating": None,
        "assist_percentage": _safe_div(player["assists"], ast_den, scale=100.0),
        "assist_to_turnover_ratio": _safe_div(player["assists"], player["turnovers"]),
        "estimated_assist_ratio": _safe_div(
            player["assists"],
            player["field_goals_attempted"] + 0.44 * player["free_throws_attempted"] + player["assists"] + player["turnovers"],
            scale=100.0,
        ),
        "assist_ratio": None,
        "estimated_offensive_rebound_percentage": _safe_div(
            player["offensive_rebounds"] * team_floor_minutes,
            player_minutes * (team["offensive_rebounds"] + opp["defensive_rebounds"]),
            scale=100.0,
        ),
        "offensive_rebound_percentage": None,
        "estimated_defensive_rebound_percentage": _safe_div(
            player["defensive_rebounds"] * team_floor_minutes,
            player_minutes * (team["defensive_rebounds"] + opp["offensive_rebounds"]),
            scale=100.0,
        ),
        "defensive_rebound_percentage": None,
        "estimated_rebound_percentage": _safe_div(
            player["rebounds"] * team_floor_minutes,
            player_minutes * (team["rebounds"] + opp["rebounds"]),
            scale=100.0,
        ),
        "rebound_percentage": None,
        "estimated_turnover_percentage": _safe_div(
            player["turnovers"],
            player["field_goals_attempted"] + 0.44 * player["free_throws_attempted"] + player["turnovers"],
            scale=100.0,
        ),
        "team_turnover_percentage": None,
        "effective_field_goal_percentage": _safe_div(
            player["field_goals_made"] + 0.5 * player["three_pointers_made"],
            player["field_goals_attempted"],
        ),
        "true_shooting_percentage": _safe_div(
            player["points"],
            2.0 * (player["field_goals_attempted"] + 0.44 * player["free_throws_attempted"]),
        ),
        "estimated_pace": estimated_pace,
        "pace": None,
        "pace_per_40": estimated_pace,
        "possessions": None,
        "player_impact_estimate": _safe_div(_pie_numerator(player), pie_den),
        "estimated_usage_percentage": _safe_div(usage_num, usage_den, scale=100.0),
        "usage_percentage": None,
        "field_goals_made": round(player["field_goals_made"] / game_count, 6),
        "field_goals_attempted": round(player["field_goals_attempted"] / game_count, 6),
        "field_goals_made_per_game": round(player["field_goals_made"] / game_count, 6),
        "field_goals_attempted_per_game": round(player["field_goals_attempted"] / game_count, 6),
        "field_goal_percentage": _safe_div(player["field_goals_made"], player["field_goals_attempted"]),
    }


def _schedule_by_id(season: int) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    schedule = get_step7g_step4n_season_schedule_dataset(season)
    games = schedule.get("games")
    if not isinstance(games, list):
        raise WNBAAdvancedStatsUpstreamError("Certified Step 4N schedule returned malformed games.")
    by_id: dict[str, dict[str, Any]] = {}
    for game in games:
        if not isinstance(game, dict):
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4N schedule contains malformed game row.")
        game_id = _clean(game.get("game_id"))
        if not game_id:
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4N schedule contains missing game ID.")
        if game_id in by_id:
            raise WNBAAdvancedStatsUpstreamError(f"Certified Step 4N schedule duplicates game {game_id}.")
        by_id[game_id] = game
    return schedule, by_id


def _verify_schedule_box(game: dict[str, Any], box: dict[str, Any], season: int) -> None:
    game_id = str(game["game_id"])
    away, home = _box_teams(box, game_id)
    schedule_away = game.get("away") or {}
    schedule_home = game.get("home") or {}
    for scheduled, boxed, side in ((schedule_away, away, "away"), (schedule_home, home, "home")):
        if _clean(scheduled.get("team_key")) != _clean(boxed.get("team_key")):
            raise WNBAAdvancedStatsUpstreamError(
                f"Step 4N/{side} box team key mismatch for advanced game {game_id}."
            )
        if _to_int(scheduled.get("official_team_id")) != _to_int(boxed.get("official_team_id")):
            raise WNBAAdvancedStatsUpstreamError(
                f"Step 4N/{side} official team ID mismatch for advanced game {game_id}."
            )
    if not _regular_game_id(game_id, season):
        raise WNBAAdvancedStatsUpstreamError(
            f"Advanced derivation refused non-certified regular game ID {game_id}."
        )
    status = game.get("status") or {}
    if status.get("category") != "final":
        raise WNBAAdvancedStatsUpstreamError(
            f"Advanced derivation refused non-final game {game_id}."
        )


def _player_games(player_id: int, season: int, last_n_games: int) -> tuple[list[dict[str, Any]], str | None, str, list[dict[str, Any]], dict[str, Any]]:
    if last_n_games > MAX_CERTIFIED_PLAYER_LATEST_GAMES:
        raise WNBAAdvancedStatsUpstreamError(
            f"WNBA.com player.latestGames certifies at most {MAX_CERTIFIED_PLAYER_LATEST_GAMES} recent games; requested {last_n_games}."
        )
    try:
        history = get_first_party_player_recent_game_log_dataset(
            player_id, season, season_type=CERTIFIED_SEASON_TYPE
        )
    except (WNBAStep7GFirstPartyNotFoundError, WNBAStep7GFirstPartyUpstreamError) as exc:
        raise WNBAAdvancedStatsUpstreamError(str(exc)) from exc
    rows = history.get("games")
    if not isinstance(rows, list):
        raise WNBAAdvancedStatsUpstreamError("WNBA.com player.latestGames returned malformed games.")
    schedule, by_id = _schedule_by_id(season)
    candidates: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        returned_pid = _to_int(row.get("player_id"))
        if returned_pid not in {None, player_id}:
            raise WNBAAdvancedStatsUpstreamError("player.latestGames returned conflicting player ID.")
        game_id = _clean(row.get("game_id"))
        if not game_id or not _regular_game_id(game_id, season):
            continue
        if game_id in seen:
            raise WNBAAdvancedStatsUpstreamError("player.latestGames duplicated a regular game ID.")
        seen.add(game_id)
        game = by_id.get(game_id)
        if game is None:
            raise WNBAAdvancedStatsUpstreamError(
                f"player.latestGames game {game_id} was absent from certified Step 4N schedule."
            )
        if (game.get("status") or {}).get("category") != "final":
            continue
        sort_key = _clean(game.get("game_datetime_utc")) or _clean(game.get("official_schedule_date")) or ""
        candidates.append((sort_key, game))
    candidates.sort(key=lambda pair: (pair[0], str(pair[1].get("game_id"))), reverse=True)
    selected = [game for _, game in candidates[:last_n_games]]
    if len(selected) != last_n_games:
        raise WNBAAdvancedStatsUpstreamError(
            f"player.latestGames exposed only {len(selected)} certified completed regular games; requested {last_n_games}."
        )

    player_rows: list[dict[str, Any]] = []
    team_rows: list[dict[str, Any]] = []
    opp_rows: list[dict[str, Any]] = []
    identity: list[dict[str, Any]] = []
    names: set[str] = set()
    team_keys: list[str] = []
    official_team_ids: list[int] = []
    for game in selected:
        game_id = str(game["game_id"])
        box = get_first_party_game_box_score_dataset(game_id, season)
        _verify_schedule_box(game, box, season)
        player, team, opp, side = _player_side(box, game_id, player_id)
        name = _clean(player.get("full_name"))
        if name:
            names.add(name)
        team_key = _clean(team.get("team_key"))
        team_id = _to_int(team.get("official_team_id"))
        if not team_key or team_id is None:
            raise WNBAAdvancedStatsUpstreamError("Player box identity is missing team key/ID.")
        team_keys.append(team_key)
        official_team_ids.append(team_id)
        player_rows.append(player)
        team_rows.append(team)
        opp_rows.append(opp)
        identity.append({
            "game_id": game_id,
            "player_resolved_once": True,
            "player_id": player_id,
            "player_side": side,
            "player_team_key": team_key,
            "player_official_team_id": team_id,
            "box_schedule_identity_match": True,
        })
    if len(names) > 1:
        raise WNBAAdvancedStatsUpstreamError("Official boxes returned conflicting full names for player.")
    latest_team_key = team_keys[0]
    latest_team_id = official_team_ids[0]
    return selected, next(iter(names), None), latest_team_key, identity, {
        "player_rows": player_rows,
        "team_rows": team_rows,
        "opp_rows": opp_rows,
        "latest_official_team_id": latest_team_id,
        "schedule_retrieved_at_utc": schedule.get("retrieved_at_utc"),
        "history_retrieved_at_utc": history.get("retrieved_at_utc"),
    }


def _team_games(team_key: str, season: int, last_n_games: int) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], int, dict[str, Any]]:
    history = get_first_party_team_game_log_dataset(
        team_key,
        season,
        season_type=CERTIFIED_SEASON_TYPE,
        last_n_games=last_n_games,
    )
    games = history.get("games")
    if not isinstance(games, list):
        raise WNBAAdvancedStatsUpstreamError("Certified Step 4J team history returned malformed games.")
    if len(games) != last_n_games:
        raise WNBAAdvancedStatsUpstreamError(
            f"Certified Step 4J returned {len(games)} games for {team_key}; requested {last_n_games}."
        )
    schedule, by_id = _schedule_by_id(season)
    game_ids: list[str] = []
    team_rows: list[dict[str, Any]] = []
    opp_rows: list[dict[str, Any]] = []
    official_ids: set[int] = set()
    for row in games:
        if not isinstance(row, dict):
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4J contains malformed team game row.")
        game_id = _clean(row.get("game_id"))
        if not game_id or not _regular_game_id(game_id, season):
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4J exposed invalid/non-regular game ID.")
        if game_id in game_ids:
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4J duplicated selected game ID.")
        game = by_id.get(game_id)
        if game is None:
            raise WNBAAdvancedStatsUpstreamError(f"Team game {game_id} absent from certified Step 4N schedule.")
        box = get_first_party_game_box_score_dataset(game_id, season)
        _verify_schedule_box(game, box, season)
        team, opp, _ = _team_side(box, game_id, team_key)
        team_id = _to_int(team.get("official_team_id"))
        if team_id is None:
            raise WNBAAdvancedStatsUpstreamError(f"Team {team_key} missing official ID in box {game_id}.")
        official_ids.add(team_id)
        game_ids.append(game_id)
        team_rows.append(team)
        opp_rows.append(opp)
    if len(official_ids) != 1:
        raise WNBAAdvancedStatsUpstreamError(
            f"Team {team_key} resolved to conflicting official team IDs across recent boxes."
        )
    return game_ids, team_rows, opp_rows, next(iter(official_ids)), {
        "history_retrieved_at_utc": history.get("retrieved_at_utc"),
        "schedule_retrieved_at_utc": schedule.get("retrieved_at_utc"),
    }


def _registry_row(team_key: str, season: int) -> dict[str, Any]:
    matches = [team for team in get_wnba_teams(season) if team["team_key"] == team_key]
    if len(matches) != 1:
        raise WNBAAdvancedStatsUpstreamError(f"Registry team {team_key} did not resolve exactly once.")
    return matches[0]


def get_first_party_player_advanced_stats_dataset(
    season: int,
    *,
    season_type: str = CERTIFIED_SEASON_TYPE,
    last_n_games: int = 0,
    per_mode: str = CERTIFIED_PER_MODE,
    team_key: str | None = None,
    player_id: int | None = None,
) -> dict[str, Any]:
    season_type, per_mode, last_n_games = _validate_scope(season, season_type, per_mode, last_n_games)
    player_id = _validate_player_id(player_id)
    selected, player_name, latest_team_key, identity, rows = _player_games(
        player_id, season, last_n_games
    )
    if team_key is not None:
        stable_team_key = _validate_team_key(team_key, season)
        if latest_team_key != stable_team_key:
            raise WNBAAdvancedStatsUpstreamError(
                f"Requested player team {stable_team_key} disagrees with latest official box team {latest_team_key}."
            )
    else:
        stable_team_key = None

    player_total = _sum_stats(rows["player_rows"], label="player_rows")
    team_total = _sum_stats(rows["team_rows"], label="player_team_rows")
    opp_total = _sum_stats(rows["opp_rows"], label="player_opponent_rows")
    registry = _registry_row(latest_team_key, season)
    game_count = len(selected)
    advanced = _player_advanced(player_total, team_total, opp_total, game_count)
    non_null_advanced = sorted(key for key, value in advanced.items() if value is not None)
    required_reproducible = {
        "estimated_usage_percentage",
        "effective_field_goal_percentage",
        "true_shooting_percentage",
        "estimated_rebound_percentage",
        "estimated_pace",
        "player_impact_estimate",
    }
    if not required_reproducible.issubset(set(non_null_advanced)):
        raise WNBAAdvancedStatsUpstreamError(
            "First-party player advanced derivation is missing reproducible core metrics."
        )

    player = {
        "player_id": player_id,
        "player_name": player_name,
        "nickname": None,
        "age": None,
        "official_team_id": rows["latest_official_team_id"],
        "team_abbreviation": registry["abbreviation"],
        "team_key": latest_team_key,
        "team_full_name": registry["full_name"],
        "conference": registry["conference"],
        "games_played": game_count,
        "record": {"wins": None, "losses": None, "win_percentage": None},
        "minutes": round(player_total["minutes"] / game_count, 6),
        "advanced": advanced,
        "mapped_to_registry": True,
    }
    retrieved_candidates = [rows.get("schedule_retrieved_at_utc"), rows.get("history_retrieved_at_utc")]
    retrieved = next((value for value in retrieved_candidates if value), _utc_now_iso())
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "source_endpoint": SOURCE_ENDPOINT,
        "source_variant": SOURCE_VARIANT,
        "data_type": "official_advanced_player_stats",
        "measure_type": "Advanced",
        "season": season,
        "season_type": season_type,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": f"last_{last_n_games}_certified_completed_regular_games",
        "filters": {"team_key": stable_team_key, "player_id": player_id},
        "retrieved_at_utc": retrieved,
        "cache_hit": False,
        "cache_ttl_seconds": None,
        "source_header_count": 0,
        "player_count": 1,
        "players": [player],
        "selected_game_ids": [str(game["game_id"]) for game in selected],
        "identity_evidence": identity,
        "derivation": {
            "input_surface": "certified official WNBA.com recent game IDs and traditional box counts",
            "estimated_metrics_are_explicitly_labeled": True,
            "official_on_court_ratings_claimed": False,
            "official_player_pace_claimed": False,
            "player_usage_formula": "100 * (FGA + 0.44*FTA + TOV) * (team_minutes/5) / (player_minutes * (team_FGA + 0.44*team_FTA + team_TOV))",
            "true_shooting_formula": "PTS / (2 * (FGA + 0.44*FTA))",
            "effective_field_goal_formula": "(FGM + 0.5*3PM) / FGA",
            "pie_formula": "official NBA/WNBA PIE box-score numerator divided by both-team numerator",
            "estimated_possessions_formula": "Basketball-Reference style two-team possession estimate using FGA/FTA/OREB/DREB/TOV",
            "not_a_projection": True,
        },
        "verification": {
            "requested_player_matches_all_rows": True,
            "selected_game_count_matches_request": game_count == last_n_games,
            "all_selected_games_final": True,
            "all_selected_game_ids_certified_regular_season": True,
            "box_schedule_identity_cross_checked": True,
            "player_resolved_exactly_once_per_box": True,
            "latest_team_mapped_to_registry": True,
            "reproducible_advanced_core_present": True,
            "non_null_advanced_fields": non_null_advanced,
            "estimated_fields_not_mislabeled_as_official": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
    }


def get_first_party_team_advanced_stats_dataset(
    season: int,
    *,
    season_type: str = CERTIFIED_SEASON_TYPE,
    last_n_games: int = 0,
    per_mode: str = CERTIFIED_PER_MODE,
    team_key: str | None = None,
) -> dict[str, Any]:
    season_type, per_mode, last_n_games = _validate_scope(season, season_type, per_mode, last_n_games)
    team_key = _validate_team_key(team_key, season)
    game_ids, team_rows, opp_rows, official_team_id, evidence = _team_games(
        team_key, season, last_n_games
    )
    team_total = _sum_stats(team_rows, label=f"{team_key}.team_rows")
    opp_total = _sum_stats(opp_rows, label=f"{team_key}.opp_rows")
    advanced = _team_advanced(team_total, opp_total, len(game_ids))
    non_null_advanced = sorted(key for key, value in advanced.items() if value is not None)
    required_reproducible = {
        "estimated_offensive_rating",
        "estimated_defensive_rating",
        "estimated_net_rating",
        "effective_field_goal_percentage",
        "true_shooting_percentage",
        "estimated_rebound_percentage",
        "estimated_pace",
        "player_impact_estimate",
    }
    if not required_reproducible.issubset(set(non_null_advanced)):
        raise WNBAAdvancedStatsUpstreamError(
            "First-party team advanced derivation is missing reproducible core metrics."
        )
    registry = _registry_row(team_key, season)
    games_played = len(game_ids)
    team = {
        "official_team_id": official_team_id,
        "team_name": registry["full_name"],
        "team_key": team_key,
        "team_abbreviation": registry["abbreviation"],
        "team_full_name": registry["full_name"],
        "conference": registry["conference"],
        "games_played": games_played,
        "record": {"wins": None, "losses": None, "win_percentage": None},
        "minutes": round(team_total["minutes"] / games_played, 6),
        "advanced": advanced,
        "mapped_to_registry": True,
    }
    retrieved = evidence.get("history_retrieved_at_utc") or evidence.get("schedule_retrieved_at_utc") or _utc_now_iso()
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "source_endpoint": SOURCE_ENDPOINT,
        "source_variant": SOURCE_VARIANT,
        "data_type": "official_advanced_team_stats",
        "measure_type": "Advanced",
        "season": season,
        "season_type": season_type,
        "per_mode": per_mode,
        "last_n_games": last_n_games,
        "window_scope": f"last_{last_n_games}_certified_completed_regular_games",
        "filters": {"team_key": team_key},
        "retrieved_at_utc": retrieved,
        "cache_hit": False,
        "cache_ttl_seconds": None,
        "source_header_count": 0,
        "team_count": 1,
        "teams": [team],
        "selected_game_ids": game_ids,
        "derivation": {
            "input_surface": "certified official WNBA.com team history IDs and traditional box counts",
            "estimated_metrics_are_explicitly_labeled": True,
            "official_on_court_ratings_claimed": False,
            "official_pace_claimed": False,
            "estimated_ratings_formula": "100 * points / estimated possessions",
            "true_shooting_formula": "PTS / (2 * (FGA + 0.44*FTA))",
            "effective_field_goal_formula": "(FGM + 0.5*3PM) / FGA",
            "pie_formula": "official NBA/WNBA PIE box-score numerator divided by both-team numerator",
            "estimated_possessions_formula": "Basketball-Reference style two-team possession estimate using FGA/FTA/OREB/DREB/TOV",
            "not_a_projection": True,
        },
        "verification": {
            "requested_team_matches_all_rows": True,
            "selected_game_count_matches_request": games_played == last_n_games,
            "all_selected_games_final": True,
            "all_selected_game_ids_certified_regular_season": True,
            "box_schedule_identity_cross_checked": True,
            "official_team_id_stable_across_selected_boxes": True,
            "team_mapped_to_registry": True,
            "reproducible_advanced_core_present": True,
            "non_null_advanced_fields": non_null_advanced,
            "estimated_fields_not_mislabeled_as_official": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
    }
