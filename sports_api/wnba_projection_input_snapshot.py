"""Step 4W: game-specific WNBA pre-model projection input snapshot.

This layer captures a content-addressed package of observed/verified WNBA inputs
for one player and one scheduled game. It intentionally creates no projection,
Monte Carlo output, sportsbook probability, projected minutes, projected
starter, or defender assignment.

Required cores:
- Step 4V observed player opportunity/role context
- Step 4N official schedule/rest/travel game context

Optional enrichments fail soft when their upstream source is unavailable, but
any returned component that disagrees on game/player/team identity fails closed.
The snapshot is content-addressed by SHA-256 but is not yet persisted to a
database; persistence/version history belongs to a later layer.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable

from sports_api.wnba_advanced_stats import (
    WNBAAdvancedStatsUpstreamError,
    get_player_advanced_stats_dataset,
    get_team_advanced_stats_dataset,
)
from sports_api.wnba_availability import (
    WNBAAvailabilityNotFoundError,
    WNBAAvailabilityUpstreamError,
    get_game_availability_context_dataset,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_matchup_context import get_matchup_source_status
from sports_api.wnba_officiating_context import (
    WNBAOfficiatingNotFoundError,
    WNBAOfficiatingUpstreamError,
    get_game_whistle_context,
)
from sports_api.wnba_player_opportunity_context import (
    WNBAPlayerOpportunityNotFoundError,
    WNBAPlayerOpportunityUpstreamError,
    get_player_opportunity_context,
)
from sports_api.wnba_schedule import WNBAScheduleUpstreamError
from sports_api.wnba_schedule_context import (
    WNBARestTravelNotFoundError,
    WNBARestTravelUpstreamError,
    get_game_rest_travel_context,
)
from sports_api.wnba_shot_context import (
    WNBAShotContextNotFoundError,
    WNBAShotContextUpstreamError,
    get_opponent_defense_by_shot_zone_dataset,
    get_player_shot_chart_dataset,
)

SNAPSHOT_SOURCE = "Kyre Sports API WNBA Step 4W pre-model input snapshot"
MAX_RECENT_GAMES = 20


class WNBAProjectionInputSnapshotUpstreamError(RuntimeError):
    """Raised when required inputs or returned component identities disagree."""


class WNBAProjectionInputSnapshotNotFoundError(LookupError):
    """Raised when the required player/game evidence cannot be constructed."""


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


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


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


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _optional_component(
    name: str,
    func: Callable[..., dict[str, Any]],
    *args: Any,
    exceptions: tuple[type[BaseException], ...],
    **kwargs: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        value = func(*args, **kwargs)
    except exceptions as exc:
        return None, {
            "requested": True,
            "available": False,
            "error": str(exc),
            "component": name,
        }
    if not isinstance(value, dict):
        raise WNBAProjectionInputSnapshotUpstreamError(
            f"WNBA Step 4W component {name} returned a non-object payload."
        )
    return value, {
        "requested": True,
        "available": True,
        "error": None,
        "component": name,
    }


def _not_requested(name: str) -> tuple[None, dict[str, Any]]:
    return None, {
        "requested": False,
        "available": False,
        "error": None,
        "component": name,
    }


def _schedule_identity(rest: dict[str, Any], game_id: str) -> dict[str, Any]:
    game = rest.get("game")
    if not isinstance(game, dict):
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4N game rest/travel context is missing game identity."
        )
    returned_game_id = _clean(game.get("game_id"))
    if returned_game_id != game_id:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4N game rest/travel context returned the wrong game ID."
        )
    away_key = _clean(rest.get("away_team_key"))
    home_key = _clean(rest.get("home_team_key"))
    if not away_key or not home_key or away_key == home_key:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4N game rest/travel context has invalid away/home team identity."
        )
    target_date = _clean(game.get("date"))
    if target_date is None:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4N game rest/travel context is missing official schedule date."
        )
    return {
        "game_id": returned_game_id,
        "date": target_date,
        "away_team_key": away_key,
        "home_team_key": home_key,
        "game_datetime_utc": game.get("game_datetime_utc"),
        "game_datetime_eastern": game.get("game_datetime_eastern"),
        "venue": deepcopy(game.get("venue")),
        "status": deepcopy(game.get("status")),
        "schedule_change": deepcopy(game.get("schedule_change")),
    }


def _focal_game_identity(
    opportunity: dict[str, Any],
    schedule: dict[str, Any],
    player_id: int,
) -> dict[str, Any]:
    if _to_int(opportunity.get("player_id")) != player_id:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4V opportunity context returned the wrong player ID."
        )
    team_key = _clean(opportunity.get("latest_observed_team_key"))
    if team_key is None:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4V opportunity context is missing latest observed team."
        )
    away = schedule["away_team_key"]
    home = schedule["home_team_key"]
    if team_key == away:
        side = "away"
        opponent = home
    elif team_key == home:
        side = "home"
        opponent = away
    else:
        raise WNBAProjectionInputSnapshotNotFoundError(
            f"Player {player_id}'s latest observed team {team_key!r} is not in WNBA game {schedule['game_id']}."
        )
    return {
        "player_id": player_id,
        "team_key": team_key,
        "side": side,
        "opponent_team_key": opponent,
    }


def _validate_availability(
    availability: dict[str, Any],
    schedule: dict[str, Any],
    player_id: int,
    focal: dict[str, Any],
) -> dict[str, Any]:
    if _clean(availability.get("game_id")) != schedule["game_id"]:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I game availability returned the wrong game ID."
        )
    if _clean(availability.get("date")) != schedule["date"]:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I game availability returned the wrong schedule date."
        )
    away = availability.get("away")
    home = availability.get("home")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I game availability is missing away/home contexts."
        )
    if _clean(away.get("team_key")) != schedule["away_team_key"] or _clean(home.get("team_key")) != schedule["home_team_key"]:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I game availability teams disagree with Step 4N official schedule."
        )
    focal_side = availability.get(focal["side"])
    if not isinstance(focal_side, dict):
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I game availability is missing focal team context."
        )
    players = focal_side.get("players")
    if not isinstance(players, list):
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I focal team availability has malformed players."
        )
    focal_rows = [row for row in players if isinstance(row, dict) and _to_int(row.get("player_id")) == player_id]
    if len(focal_rows) > 1:
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4I focal team availability contains duplicate focal player rows."
        )
    return {
        "focal_player_current_roster_match": len(focal_rows) == 1,
        "focal_player_availability": deepcopy(focal_rows[0]) if focal_rows else None,
        "injury_report": deepcopy(availability.get("injury_report")),
        "starting_lineups": deepcopy(availability.get("starting_lineups")),
        "verification": deepcopy(availability.get("verification")),
    }


def _validate_player_component(
    component: dict[str, Any] | None,
    player_id: int,
    name: str,
) -> None:
    if component is None:
        return
    returned = _to_int(component.get("player_id"))
    if returned is not None and returned != player_id:
        raise WNBAProjectionInputSnapshotUpstreamError(
            f"Step 4W component {name} returned the wrong player ID."
        )
    filters = component.get("filters")
    if isinstance(filters, dict):
        filtered = _to_int(filters.get("player_id"))
        if filtered is not None and filtered != player_id:
            raise WNBAProjectionInputSnapshotUpstreamError(
                f"Step 4W component {name} contains a conflicting player filter."
            )


def _validate_team_component(
    component: dict[str, Any] | None,
    team_key: str,
    name: str,
) -> None:
    if component is None:
        return
    candidates = [
        _clean(component.get("team_key")),
        _clean((component.get("filters") or {}).get("team_key")) if isinstance(component.get("filters"), dict) else None,
    ]
    concrete = [item for item in candidates if item is not None]
    if concrete and any(item != team_key for item in concrete):
        raise WNBAProjectionInputSnapshotUpstreamError(
            f"Step 4W component {name} returned a conflicting team identity."
        )


def _collect_timestamps(value: Any, path: str = "inputs") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}"
            if key in {
                "retrieved_at_utc",
                "report_timestamp_eastern",
                "game_datetime_utc",
                "game_datetime_eastern",
            } and item is not None:
                rows.append({"path": next_path, "value": item})
            else:
                rows.extend(_collect_timestamps(item, next_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_collect_timestamps(item, f"{path}[{index}]"))
    return rows


def _status_summary(statuses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    requested = [name for name, row in statuses.items() if row.get("requested")]
    available = [name for name, row in statuses.items() if row.get("available")]
    unavailable = [name for name in requested if name not in available]
    return {
        "requested_component_count": len(requested),
        "available_component_count": len(available),
        "unavailable_component_count": len(unavailable),
        "available_components": available,
        "unavailable_components": unavailable,
        "all_requested_optional_components_available": not unavailable,
    }


def get_player_game_projection_input_snapshot(
    player_id: int,
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    include_current_availability: bool = True,
    include_shot_context: bool = True,
    include_advanced_context: bool = True,
    include_officiating_context: bool = True,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    include_current_availability = _bool(include_current_availability, "include_current_availability")
    include_shot_context = _bool(include_shot_context, "include_shot_context")
    include_advanced_context = _bool(include_advanced_context, "include_advanced_context")
    include_officiating_context = _bool(include_officiating_context, "include_officiating_context")
    captured_at_utc = _utc_now_iso()

    try:
        opportunity = get_player_opportunity_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            include_current_availability=False,
        )
    except WNBAPlayerOpportunityNotFoundError as exc:
        raise WNBAProjectionInputSnapshotNotFoundError(str(exc)) from exc
    except WNBAPlayerOpportunityUpstreamError as exc:
        raise WNBAProjectionInputSnapshotUpstreamError(str(exc)) from exc

    try:
        rest_travel = get_game_rest_travel_context(
            game_id,
            season,
            include_observed_workload=True,
        )
    except WNBARestTravelNotFoundError as exc:
        raise WNBAProjectionInputSnapshotNotFoundError(str(exc)) from exc
    except (WNBARestTravelUpstreamError, WNBAScheduleUpstreamError) as exc:
        raise WNBAProjectionInputSnapshotUpstreamError(str(exc)) from exc

    schedule = _schedule_identity(rest_travel, game_id)
    focal = _focal_game_identity(opportunity, schedule, player_id)
    opponent_key = focal["opponent_team_key"]
    team_key = focal["team_key"]

    statuses: dict[str, dict[str, Any]] = {}
    inputs: dict[str, Any] = {
        "player_opportunity_context": deepcopy(opportunity),
        "game_rest_travel_context": deepcopy(rest_travel),
    }

    if include_current_availability:
        availability, statuses["game_availability"] = _optional_component(
            "game_availability",
            get_game_availability_context_dataset,
            game_id,
            schedule["date"],
            season,
            last_n_games=last_n_games,
            exceptions=(WNBAAvailabilityNotFoundError, WNBAAvailabilityUpstreamError),
        )
    else:
        availability, statuses["game_availability"] = _not_requested("game_availability")
    availability_summary = None
    if availability is not None:
        availability_summary = _validate_availability(
            availability, schedule, player_id, focal
        )
        inputs["game_availability"] = deepcopy(availability)

    if include_shot_context:
        player_shot, statuses["player_recent_shot_chart"] = _optional_component(
            "player_recent_shot_chart",
            get_player_shot_chart_dataset,
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            exceptions=(WNBAShotContextNotFoundError, WNBAShotContextUpstreamError),
        )
        player_vs_opponent_shot, statuses["player_vs_opponent_shot_chart"] = _optional_component(
            "player_vs_opponent_shot_chart",
            get_player_shot_chart_dataset,
            player_id,
            season,
            season_type=season_type,
            last_n_games=0,
            opponent_team_key=opponent_key,
            exceptions=(WNBAShotContextNotFoundError, WNBAShotContextUpstreamError),
        )
        opponent_zone_defense, statuses["opponent_defense_by_shot_zone"] = _optional_component(
            "opponent_defense_by_shot_zone",
            get_opponent_defense_by_shot_zone_dataset,
            opponent_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            exceptions=(WNBAShotContextNotFoundError, WNBAShotContextUpstreamError),
        )
        _validate_player_component(player_shot, player_id, "player_recent_shot_chart")
        _validate_player_component(player_vs_opponent_shot, player_id, "player_vs_opponent_shot_chart")
        _validate_team_component(opponent_zone_defense, opponent_key, "opponent_defense_by_shot_zone")
        if player_shot is not None:
            inputs["player_recent_shot_chart"] = deepcopy(player_shot)
        if player_vs_opponent_shot is not None:
            inputs["player_vs_opponent_shot_chart"] = deepcopy(player_vs_opponent_shot)
        if opponent_zone_defense is not None:
            inputs["opponent_defense_by_shot_zone"] = deepcopy(opponent_zone_defense)
    else:
        for name in (
            "player_recent_shot_chart",
            "player_vs_opponent_shot_chart",
            "opponent_defense_by_shot_zone",
        ):
            _, statuses[name] = _not_requested(name)

    if include_advanced_context:
        player_advanced, statuses["player_advanced"] = _optional_component(
            "player_advanced",
            get_player_advanced_stats_dataset,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode="PerGame",
            player_id=player_id,
            exceptions=(WNBAAdvancedStatsUpstreamError,),
        )
        team_advanced, statuses["team_advanced"] = _optional_component(
            "team_advanced",
            get_team_advanced_stats_dataset,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode="PerGame",
            team_key=team_key,
            exceptions=(WNBAAdvancedStatsUpstreamError,),
        )
        opponent_advanced, statuses["opponent_advanced"] = _optional_component(
            "opponent_advanced",
            get_team_advanced_stats_dataset,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode="PerGame",
            team_key=opponent_key,
            exceptions=(WNBAAdvancedStatsUpstreamError,),
        )
        _validate_player_component(player_advanced, player_id, "player_advanced")
        _validate_team_component(team_advanced, team_key, "team_advanced")
        _validate_team_component(opponent_advanced, opponent_key, "opponent_advanced")
        if player_advanced is not None:
            inputs["player_advanced"] = deepcopy(player_advanced)
        if team_advanced is not None:
            inputs["team_advanced"] = deepcopy(team_advanced)
        if opponent_advanced is not None:
            inputs["opponent_advanced"] = deepcopy(opponent_advanced)
    else:
        for name in ("player_advanced", "team_advanced", "opponent_advanced"):
            _, statuses[name] = _not_requested(name)

    if include_officiating_context:
        whistle, statuses["game_whistle_context"] = _optional_component(
            "game_whistle_context",
            get_game_whistle_context,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            exceptions=(WNBAOfficiatingNotFoundError, WNBAOfficiatingUpstreamError),
        )
        if whistle is not None:
            returned_game = _clean(whistle.get("game_id"))
            if returned_game is not None and returned_game != game_id:
                raise WNBAProjectionInputSnapshotUpstreamError(
                    "Step 4O whistle context returned the wrong game ID."
                )
            inputs["game_whistle_context"] = deepcopy(whistle)
    else:
        whistle, statuses["game_whistle_context"] = _not_requested("game_whistle_context")

    matchup_source_status = get_matchup_source_status(season)
    if not isinstance(matchup_source_status, dict):
        raise WNBAProjectionInputSnapshotUpstreamError(
            "Step 4S matchup source status returned a non-object payload."
        )
    inputs["matchup_source_status"] = deepcopy(matchup_source_status)

    content = {
        "schema_version": "wnba_step_4w_v1",
        "season": season,
        "season_type": season_type,
        "game_id": game_id,
        "player_id": player_id,
        "recent_window_games": last_n_games,
        "game_identity": schedule,
        "focal_identity": focal,
        "component_status": statuses,
        "inputs": inputs,
    }
    content_sha256 = _canonical_hash(content)
    finalized_at_utc = _utc_now_iso()

    return {
        "source": SNAPSHOT_SOURCE,
        "data_type": "content_addressed_pre_model_projection_input_snapshot",
        "schema_version": "wnba_step_4w_v1",
        "snapshot_id": f"wnba-4w-{game_id}-{player_id}-{content_sha256[:16]}",
        "content_sha256": content_sha256,
        "captured_at_utc": captured_at_utc,
        "finalized_at_utc": finalized_at_utc,
        "season": season,
        "season_type": season_type,
        "game_id": game_id,
        "player_id": player_id,
        "recent_window_games": last_n_games,
        "game_identity": schedule,
        "focal_identity": focal,
        "availability_summary": availability_summary,
        "component_status": statuses,
        "component_status_summary": _status_summary(statuses),
        "source_timestamps": _collect_timestamps(inputs),
        "inputs": inputs,
        "snapshot_semantics": {
            "content_addressed": True,
            "hash_algorithm": "sha256",
            "hash_covers": "schema/version, requested window, game/player identity, component status, and captured input payloads",
            "persisted_to_database": False,
            "persistence_note": "Step 4W returns an immutable-by-value content-addressed package; durable snapshot storage/version history is not created in this step.",
        },
        "guardrails": {
            "snapshot_is_pre_model_input_not_projection": True,
            "no_projected_minutes_created": True,
            "no_projected_starters_created": True,
            "no_missing_teammate_opportunity_redistribution_created": True,
            "no_monte_carlo_created": True,
            "no_sportsbook_data_created": True,
            "no_betting_probability_created": True,
            "court_context_is_not_defender_assignment": True,
            "official_wnba_player_defender_assignment_remains_unavailable": True,
        },
        "verification": {
            "required_step_4v_opportunity_available": True,
            "required_official_game_schedule_rest_travel_available": True,
            "focal_latest_observed_team_is_in_requested_game": True,
            "opponent_resolved_from_official_game_identity": True,
            "step_4v_availability_disabled_to_avoid_duplicate_snapshot_report_fetch": True,
            "game_level_availability_captures_both_teams_when_available": True,
            "optional_returned_components_identity_checked": True,
            "optional_source_failures_do_not_fabricate_values": True,
            "content_hash_created": True,
        },
    }
