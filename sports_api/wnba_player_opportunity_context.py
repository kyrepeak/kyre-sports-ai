"""Step 4V: observed WNBA player opportunity and role context.

This layer combines frozen Step 4R rotation stints, Step 4G official starter/bench
and five-player lineup context, Step 4I official availability context, and Step
4U event/floor-context features into one projection-ready descriptive record.

It deliberately does NOT create projected minutes, projected starters, missing-
player usage redistribution, Monte Carlo inputs, betting probabilities, or a
player-vs-defender assignment. Derived labels describe observed history only.
"""
from __future__ import annotations

from copy import deepcopy
from statistics import mean, median, pstdev
from typing import Any

from sports_api.wnba_availability import (
    WNBAAvailabilityNotFoundError,
    WNBAAvailabilityUpstreamError,
    get_team_availability_context_dataset,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_lineup_context import (
    WNBALineupContextNotFoundError,
    WNBALineupContextUpstreamError,
    get_lineups_dataset,
    get_player_role_context_dataset,
)
from sports_api.wnba_player_event_features import (
    WNBAPlayerEventFeatureNotFoundError,
    WNBAPlayerEventFeatureUpstreamError,
    get_player_recent_event_feature_context,
)
from sports_api.wnba_rotation_context import (
    WNBARotationNotFoundError,
    WNBARotationUpstreamError,
    get_player_recent_rotation_context,
)

OPPORTUNITY_SOURCE = "Kyre Sports API WNBA observed opportunity + role context"
MAX_RECENT_GAMES = 20
_EVENT_RATE_KEYS = (
    "field_goals_attempted",
    "field_goals_made",
    "three_pointers_attempted",
    "three_pointers_made",
    "free_throws_attempted",
    "free_throws_made",
    "offensive_rebounds",
    "defensive_rebounds",
    "rebounds",
    "assists",
    "turnovers",
    "blocks",
    "personal_fouls",
    "points",
)


class WNBAPlayerOpportunityUpstreamError(RuntimeError):
    """Raised when required observed components disagree or are malformed."""


class WNBAPlayerOpportunityNotFoundError(LookupError):
    """Raised when required player opportunity evidence is unavailable."""


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


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RECENT_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _share(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _per_game_counts(counts: dict[str, Any], games: int) -> dict[str, float | None]:
    if games <= 0:
        return {key: None for key in _EVENT_RATE_KEYS}
    result: dict[str, float | None] = {}
    for key in _EVENT_RATE_KEYS:
        value = _to_int(counts.get(key))
        if value is None or value < 0:
            raise WNBAPlayerOpportunityUpstreamError(
                f"Step 4U aggregate contains invalid {key}."
            )
        result[key] = round(value / games, 4)
    return result


def _rotation_games(rotation: dict[str, Any], player_id: int) -> list[dict[str, Any]]:
    games = rotation.get("games")
    if not isinstance(games, list):
        raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation contains malformed games.")
    result = []
    for game in games:
        if not isinstance(game, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation contains malformed game row.")
        player = game.get("player_rotation")
        if not isinstance(player, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation game is missing player_rotation.")
        if _to_int(player.get("player_id")) != player_id:
            raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation returned the wrong player ID.")
        minutes = _to_float(player.get("tracked_minutes"))
        if minutes is None or minutes < 0:
            raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation contains invalid tracked minutes.")
        result.append(game)
    return result


def _rotation_stability(rotation: dict[str, Any], player_id: int) -> dict[str, Any]:
    games = _rotation_games(rotation, player_id)
    minutes = [float(game["player_rotation"]["tracked_minutes"]) for game in games]
    stints = [_to_int(game["player_rotation"].get("stint_count")) for game in games]
    if any(value is None or value < 0 for value in stints):
        raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation contains invalid stint counts.")
    starts = [bool(game["player_rotation"].get("started_game")) for game in games]
    if not minutes:
        raise WNBAPlayerOpportunityNotFoundError(
            f"No observed Step 4R rotation games were available for player {player_id}."
        )
    avg = mean(minutes)
    std = pstdev(minutes) if len(minutes) > 1 else 0.0
    return {
        "rotation_game_count": len(games),
        "tracked_minutes_by_game": [round(value, 4) for value in minutes],
        "tracked_minutes_mean": round(avg, 4),
        "tracked_minutes_median": round(median(minutes), 4),
        "tracked_minutes_min": round(min(minutes), 4),
        "tracked_minutes_max": round(max(minutes), 4),
        "tracked_minutes_range": round(max(minutes) - min(minutes), 4),
        "tracked_minutes_population_stddev": round(std, 4),
        "tracked_minutes_coefficient_of_variation": round(std / avg, 6) if avg > 0 else None,
        "starts_in_rotation_games": sum(starts),
        "start_share": round(sum(starts) / len(starts), 6),
        "stints_per_game": round(sum(int(value) for value in stints if value is not None) / len(games), 4),
        "semantics": "All minute/stint values are observed official GameRotation history; none are projected.",
    }


def _latest_team_from_event(event_context: dict[str, Any]) -> str | None:
    games = event_context.get("games")
    if not isinstance(games, list):
        raise WNBAPlayerOpportunityUpstreamError("Step 4U recent feature context contains malformed games.")
    for game in games:
        if not isinstance(game, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4U recent feature context contains malformed game row.")
        features = game.get("features")
        if not isinstance(features, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4U recent feature game is missing features.")
        team = features.get("team")
        if isinstance(team, dict):
            key = _clean(team.get("team_key"))
            if key:
                return key
    return None


def _latest_team_from_rotation(rotation: dict[str, Any]) -> str | None:
    games = rotation.get("games")
    if not isinstance(games, list):
        raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation contains malformed games.")
    for game in games:
        if not isinstance(game, dict):
            continue
        player = game.get("player_rotation")
        if isinstance(player, dict):
            key = _clean(player.get("team_key"))
            if key:
                return key
    return None


def _validate_core_identity(
    rotation: dict[str, Any],
    event_context: dict[str, Any],
    player_id: int,
) -> str:
    if _to_int(rotation.get("player_id")) != player_id:
        raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation player ID does not match request.")
    if _to_int(event_context.get("player_id")) != player_id:
        raise WNBAPlayerOpportunityUpstreamError("Step 4U recent feature player ID does not match request.")
    rotation_team = _latest_team_from_rotation(rotation)
    event_team = _latest_team_from_event(event_context)
    if rotation_team is None or event_team is None:
        raise WNBAPlayerOpportunityUpstreamError(
            "Required Step 4R/4U evidence could not resolve the latest observed team."
        )
    if rotation_team != event_team:
        raise WNBAPlayerOpportunityUpstreamError(
            "Step 4R rotation and Step 4U event features disagree on the latest observed team."
        )
    return rotation_team


def _component_result(func, *args, **kwargs) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return func(*args, **kwargs), None
    except (
        WNBALineupContextNotFoundError,
        WNBALineupContextUpstreamError,
        WNBAAvailabilityNotFoundError,
        WNBAAvailabilityUpstreamError,
    ) as exc:
        return None, str(exc)


def _role_observation(role: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    if role is None:
        return {
            "available": False,
            "error": error,
            "role_summary": None,
            "starter": None,
            "bench": None,
            "observed_role_band": None,
        }
    summary = role.get("role_summary")
    if not isinstance(summary, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4G role context contains malformed role_summary.")
    share = _to_float(summary.get("starter_game_share"))
    if share is None:
        band = "unresolved"
    elif share >= .8:
        band = "mostly_starter"
    elif share <= .2:
        band = "mostly_bench"
    else:
        band = "mixed_starter_bench_history"
    return {
        "available": True,
        "error": None,
        "role_summary": deepcopy(summary),
        "starter": deepcopy(role.get("starter")),
        "bench": deepcopy(role.get("bench")),
        "observed_role_band": band,
        "semantics": "Role band describes official starter/bench game history only; it is not a projected role.",
    }


def _lineup_observation(lineups: dict[str, Any] | None, error: str | None, player_id: int) -> dict[str, Any]:
    if lineups is None:
        return {
            "available": False,
            "error": error,
            "lineup_count": 0,
            "top_five_player_lineups": [],
        }
    rows = lineups.get("lineups")
    if not isinstance(rows, list):
        raise WNBAPlayerOpportunityUpstreamError("Step 4G lineup context contains malformed lineups.")
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4G lineup context contains malformed lineup row.")
        ids = row.get("player_ids")
        if not isinstance(ids, list) or player_id not in ids:
            raise WNBAPlayerOpportunityUpstreamError("Targeted Step 4G lineup response contains a lineup without focal player.")
        stats = row.get("stats")
        if not isinstance(stats, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4G lineup row is missing stats.")
        filtered.append(
            {
                "group_id": row.get("group_id"),
                "group_name": row.get("group_name"),
                "player_ids": deepcopy(ids),
                "members": deepcopy(row.get("members")),
                "games_played": row.get("games_played"),
                "minutes": stats.get("minutes"),
                "points": stats.get("points"),
                "rebounds": stats.get("rebounds"),
                "assists": stats.get("assists"),
                "plus_minus": stats.get("plus_minus"),
            }
        )
    return {
        "available": True,
        "error": None,
        "lineup_count": len(filtered),
        "top_five_player_lineups": filtered[:10],
        "semantics": "Official five-player lineup history containing the focal player, ordered upstream by observed minutes.",
    }


def _availability_observation(
    availability: dict[str, Any] | None,
    error: str | None,
    player_id: int,
    expected_team_key: str,
    requested: bool,
) -> dict[str, Any]:
    if not requested:
        return {
            "requested": False,
            "available": False,
            "error": None,
            "current_roster_team_verified": False,
            "focal_player": None,
            "same_team_statuses": [],
        }
    if availability is None:
        return {
            "requested": True,
            "available": False,
            "error": error,
            "current_roster_team_verified": False,
            "focal_player": None,
            "same_team_statuses": [],
        }
    if _clean(availability.get("team_key")) != expected_team_key:
        raise WNBAPlayerOpportunityUpstreamError("Step 4I availability returned an unexpected team key.")
    team = availability.get("team")
    if not isinstance(team, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4I availability context is missing team object.")
    players = team.get("players")
    if not isinstance(players, list):
        raise WNBAPlayerOpportunityUpstreamError("Step 4I availability context contains malformed players.")
    focal = None
    rows = []
    for row in players:
        if not isinstance(row, dict):
            raise WNBAPlayerOpportunityUpstreamError("Step 4I availability contains malformed player row.")
        pid = _to_int(row.get("player_id"))
        item = {
            "player_id": pid,
            "player_name": row.get("player_name"),
            "position": row.get("position"),
            "injury_report_status": row.get("injury_report_status"),
            "injury_reason": row.get("injury_reason"),
            "listed_on_injury_report": bool(row.get("listed_on_injury_report")),
            "availability_class": row.get("availability_class"),
            "availability_blocking": bool(row.get("availability_blocking")),
            "availability_uncertain": bool(row.get("availability_uncertain")),
            "recent_minutes_per_game": row.get("recent_minutes_per_game"),
            "observed_rotation_rank_by_recent_minutes": row.get("observed_rotation_rank_by_recent_minutes"),
            "member_of_most_used_five_player_lineup": bool(row.get("member_of_most_used_five_player_lineup")),
        }
        rows.append(item)
        if pid == player_id:
            focal = item
    rows.sort(
        key=lambda item: (
            item["observed_rotation_rank_by_recent_minutes"] if isinstance(item["observed_rotation_rank_by_recent_minutes"], int) else 10_000,
            item["player_name"] or "",
        )
    )
    return {
        "requested": True,
        "available": True,
        "error": None,
        "current_roster_team_verified": focal is not None,
        "focal_player": focal,
        "same_team_statuses": rows,
        "team_report_not_yet_submitted": bool(team.get("team_report_not_yet_submitted")),
        "starter_verification": deepcopy(team.get("starter_verification")),
        "injury_report": deepcopy(availability.get("injury_report")),
        "semantics": (
            "Availability is reported exactly as observed. No teammate minutes, shots, rebounds, assists, "
            "or usage are redistributed to the focal player in Step 4V."
        ),
    }


def _event_observation(event_context: dict[str, Any]) -> dict[str, Any]:
    aggregate = event_context.get("aggregate")
    if not isinstance(aggregate, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4U recent feature context is missing aggregate.")
    own = aggregate.get("own_event_counts")
    environment = aggregate.get("on_court_event_environment")
    quality = aggregate.get("data_quality")
    co_presence = aggregate.get("co_presence")
    exposure = aggregate.get("derived_possession_exposure")
    if not isinstance(own, dict) or not isinstance(environment, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4U aggregate contains malformed event counts/environment.")
    if not isinstance(quality, dict) or not isinstance(co_presence, dict) or not isinstance(exposure, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4U aggregate is missing quality/co-presence/possession exposure.")
    game_count = _to_int(event_context.get("feature_game_count"))
    if game_count is None or game_count <= 0:
        raise WNBAPlayerOpportunityNotFoundError("Step 4U recent feature context has no feature games.")
    team = environment.get("team")
    opponent = environment.get("opponent")
    shares = environment.get("action_shares_of_team_events")
    if not isinstance(team, dict) or not isinstance(opponent, dict) or not isinstance(shares, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4U event environment is malformed.")
    return {
        "feature_game_count": game_count,
        "missing_feature_game_ids": deepcopy(event_context.get("missing_feature_game_ids")),
        "data_quality": deepcopy(quality),
        "own_event_counts": deepcopy(own),
        "own_event_counts_per_feature_game": _per_game_counts(own, game_count),
        "own_shot_profile": deepcopy(aggregate.get("own_shot_profile")),
        "action_shares_of_team_events": deepcopy(shares),
        "team_event_environment": deepcopy(team),
        "opponent_event_environment": deepcopy(opponent),
        "co_presence": deepcopy(co_presence),
        "derived_possession_exposure": deepcopy(exposure),
        "derived_offensive_segments_per_feature_game": (
            round((_to_int(exposure.get("stable_complete_offensive_segment_count")) or 0) / game_count, 4)
        ),
        "derived_defensive_segments_per_feature_game": (
            round((_to_int(exposure.get("stable_complete_defensive_segment_count")) or 0) / game_count, 4)
        ),
        "semantics": (
            "Event rates use only Step 4U feature-eligible events. Derived segments are not official possessions; "
            "action shares are not official usage percentage."
        ),
    }


def get_player_opportunity_context(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    include_current_availability: bool = True,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    if not isinstance(include_current_availability, bool):
        raise ValueError("WNBA include_current_availability must be boolean.")

    try:
        rotation = get_player_recent_rotation_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            rotation_stat="PLAYER_PTS",
        )
    except WNBARotationNotFoundError as exc:
        raise WNBAPlayerOpportunityNotFoundError(str(exc)) from exc
    except WNBARotationUpstreamError as exc:
        raise WNBAPlayerOpportunityUpstreamError(str(exc)) from exc

    try:
        event_context = get_player_recent_event_feature_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except WNBAPlayerEventFeatureNotFoundError as exc:
        raise WNBAPlayerOpportunityNotFoundError(str(exc)) from exc
    except WNBAPlayerEventFeatureUpstreamError as exc:
        raise WNBAPlayerOpportunityUpstreamError(str(exc)) from exc

    latest_team_key = _validate_core_identity(rotation, event_context, player_id)

    role, role_error = _component_result(
        get_player_role_context_dataset,
        player_id,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
        per_mode="PerGame",
    )
    lineups, lineup_error = _component_result(
        get_lineups_dataset,
        season,
        season_type=season_type,
        group_quantity=5,
        last_n_games=last_n_games,
        per_mode="PerGame",
        team_key=latest_team_key,
        player_id=player_id,
    )

    availability = None
    availability_error = None
    if include_current_availability:
        availability, availability_error = _component_result(
            get_team_availability_context_dataset,
            latest_team_key,
            season,
            last_n_games=last_n_games,
        )

    rotation_aggregate = rotation.get("aggregate")
    if not isinstance(rotation_aggregate, dict):
        raise WNBAPlayerOpportunityUpstreamError("Step 4R recent rotation is missing aggregate.")

    result = {
        "source": OPPORTUNITY_SOURCE,
        "data_type": "observed_player_opportunity_and_role_features",
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "requested_last_n_games": last_n_games,
        "latest_observed_team_key": latest_team_key,
        "components": {
            "rotation": {"available": True, "source": rotation.get("source"), "data_type": rotation.get("data_type")},
            "event_features": {"available": True, "source": event_context.get("source"), "data_type": event_context.get("data_type")},
            "starter_bench_role": {"available": role is not None, "error": role_error},
            "five_player_lineups": {"available": lineups is not None, "error": lineup_error},
            "current_availability": {
                "requested": include_current_availability,
                "available": availability is not None,
                "error": availability_error,
            },
        },
        "observed_minutes_opportunity": {
            "tracked_minutes": {
                "aggregate": deepcopy(rotation_aggregate),
                "stability": _rotation_stability(rotation, player_id),
            },
            "source_game_count": rotation.get("rotation_game_count"),
            "missing_rotation_game_ids": deepcopy(rotation.get("missing_rotation_game_ids")),
        },
        "observed_event_opportunity": _event_observation(event_context),
        "observed_role_context": _role_observation(role, role_error),
        "observed_five_player_lineup_context": _lineup_observation(lineups, lineup_error, player_id),
        "current_availability_context": _availability_observation(
            availability,
            availability_error,
            player_id,
            latest_team_key,
            include_current_availability,
        ),
        "guardrails": {
            "features_are_observed_descriptive_inputs_not_projections": True,
            "tracked_minutes_are_observed_not_projected_minutes": True,
            "starter_bench_role_is_historical_not_projected_role": True,
            "five_player_lineups_are_observed_not_projected_lineups": True,
            "injury_status_does_not_trigger_automatic_opportunity_redistribution": True,
            "no_missing_teammate_minutes_redistributed": True,
            "event_action_shares_are_not_official_usage_percentage": True,
            "derived_segments_are_not_official_possessions": True,
            "co_presence_events_are_not_shared_minutes": True,
            "court_context_is_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_projection_created": True,
            "no_monte_carlo_created": True,
            "no_betting_probability_created": True,
        },
        "verification": {
            "step_4r_and_step_4u_player_identity_match": True,
            "step_4r_and_step_4u_latest_team_identity_match": True,
            "required_rotation_and_event_feature_components_available": True,
            "optional_components_fail_soft": True,
            "availability_requires_current_roster_match_before_current_team_is_called_verified": True,
        },
    }
    return result
