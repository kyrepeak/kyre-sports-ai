"""Bounded recent-game overlay for Step 7G Step 4F team advanced context.

The base advanced adapter is deliberately conservative and can reuse Step 4J's
full team-history builder. For live Step 4W readiness we only need the requested
recent window. This overlay selects the exact last N completed Regular Season
game IDs from the already-certified Step 4N schedule *before* loading boxes,
then applies the same box/schedule identity checks and derivation helpers.

This avoids full-season network fan-out while preserving the frozen Step 4F
payload shape and fail-closed identity semantics.
"""
from __future__ import annotations

from typing import Any

import sports_api.wnba_step7g_first_party_advanced_stats as base
from sports_api.wnba_advanced_stats import WNBAAdvancedStatsUpstreamError
from sports_api.wnba_step7g_first_party_history import get_first_party_game_box_score_dataset

SOURCE_VARIANT = base.SOURCE_VARIANT + "+bounded_step4n_recent_team_window_v2"


def _game_sort_key(game: dict[str, Any]) -> tuple[str, str]:
    return (
        base._clean(game.get("game_datetime_utc"))
        or base._clean(game.get("official_schedule_date"))
        or "",
        base._clean(game.get("game_id")) or "",
    )


def _participants(game: dict[str, Any]) -> tuple[str | None, str | None]:
    away = game.get("away")
    home = game.get("home")
    return (
        base._clean(away.get("team_key")) if isinstance(away, dict) else None,
        base._clean(home.get("team_key")) if isinstance(home, dict) else None,
    )


def _fast_team_games(
    team_key: str,
    season: int,
    last_n_games: int,
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], int, dict[str, Any]]:
    schedule, _ = base._schedule_by_id(season)
    games = schedule.get("games")
    if not isinstance(games, list):
        raise WNBAAdvancedStatsUpstreamError("Certified Step 4N schedule returned malformed games.")

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game in games:
        if not isinstance(game, dict):
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4N schedule contains malformed game row.")
        game_id = base._clean(game.get("game_id"))
        if not game_id:
            raise WNBAAdvancedStatsUpstreamError("Certified Step 4N schedule contains missing game ID.")
        if game_id in seen:
            raise WNBAAdvancedStatsUpstreamError(f"Certified Step 4N schedule duplicates game {game_id}.")
        seen.add(game_id)
        away_key, home_key = _participants(game)
        if team_key not in {away_key, home_key}:
            continue
        if (game.get("status") or {}).get("category") != "final":
            continue
        if not base._regular_game_id(game_id, season):
            continue
        candidates.append(game)

    candidates.sort(key=_game_sort_key, reverse=True)
    selected = candidates[:last_n_games]
    if len(selected) != last_n_games:
        raise WNBAAdvancedStatsUpstreamError(
            f"Certified Step 4N exposed only {len(selected)} completed regular games for {team_key}; requested {last_n_games}."
        )

    game_ids: list[str] = []
    team_rows: list[dict[str, Any]] = []
    opp_rows: list[dict[str, Any]] = []
    official_ids: set[int] = set()
    identity_evidence: list[dict[str, Any]] = []
    for game in selected:
        game_id = str(game["game_id"])
        box = get_first_party_game_box_score_dataset(game_id, season)
        base._verify_schedule_box(game, box, season)
        team, opp, side = base._team_side(box, game_id, team_key)
        team_id = base._to_int(team.get("official_team_id"))
        opponent_id = base._to_int(opp.get("official_team_id"))
        if team_id is None or opponent_id is None or team_id == opponent_id:
            raise WNBAAdvancedStatsUpstreamError(
                f"Team/opponent official ID is invalid in advanced box {game_id}."
            )
        official_ids.add(team_id)
        game_ids.append(game_id)
        team_rows.append(team)
        opp_rows.append(opp)
        identity_evidence.append(
            {
                "game_id": game_id,
                "team_key": team_key,
                "team_side": side,
                "official_team_id": team_id,
                "opponent_official_team_id": opponent_id,
                "box_schedule_identity_match": True,
            }
        )

    if len(official_ids) != 1:
        raise WNBAAdvancedStatsUpstreamError(
            f"Team {team_key} resolved to conflicting official team IDs across selected boxes."
        )
    return game_ids, team_rows, opp_rows, next(iter(official_ids)), {
        "history_retrieved_at_utc": schedule.get("retrieved_at_utc"),
        "schedule_retrieved_at_utc": schedule.get("retrieved_at_utc"),
        "identity_evidence": identity_evidence,
        "selection_method": "certified_step4n_schedule_last_n_before_box_fetch",
        "full_season_box_fanout_performed": False,
    }


def get_first_party_player_advanced_stats_dataset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = base.get_first_party_player_advanced_stats_dataset(*args, **kwargs)
    result["source_variant"] = SOURCE_VARIANT
    result.setdefault("derivation", {})["team_window_fetch_bounded_before_boxes"] = True
    return result


def get_first_party_team_advanced_stats_dataset(
    season: int,
    *,
    season_type: str = base.CERTIFIED_SEASON_TYPE,
    last_n_games: int = 0,
    per_mode: str = base.CERTIFIED_PER_MODE,
    team_key: str | None = None,
) -> dict[str, Any]:
    season_type, per_mode, last_n_games = base._validate_scope(
        season, season_type, per_mode, last_n_games
    )
    team_key = base._validate_team_key(team_key, season)
    game_ids, team_rows, opp_rows, official_team_id, evidence = _fast_team_games(
        team_key, season, last_n_games
    )
    team_total = base._sum_stats(team_rows, label=f"{team_key}.team_rows")
    opp_total = base._sum_stats(opp_rows, label=f"{team_key}.opp_rows")
    advanced = base._team_advanced(team_total, opp_total, len(game_ids))
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
            "First-party bounded team advanced derivation is missing reproducible core metrics."
        )

    registry = base._registry_row(team_key, season)
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
    retrieved = evidence.get("schedule_retrieved_at_utc") or base._utc_now_iso()
    return {
        "source": base.SOURCE,
        "source_url": base.SOURCE_URL,
        "source_endpoint": base.SOURCE_ENDPOINT,
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
        "identity_evidence": evidence["identity_evidence"],
        "derivation": {
            "input_surface": "certified official WNBA.com Step 4N schedule IDs and traditional game-page box counts",
            "game_selection_before_box_fetch": True,
            "full_season_box_fanout_performed": False,
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
            "full_season_box_fanout_performed": False,
        },
    }
