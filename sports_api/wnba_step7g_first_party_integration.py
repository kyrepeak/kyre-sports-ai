"""Default-OFF Step 7G first-party integration for the frozen WNBA core chain.

This module installs only certified first-party transport seams used by Step 4X
model-input readiness. ``sports_api.main`` imports it before WNBA routers bind
their functions, but nothing changes unless
``WNBA_STEP7G_FIRST_PARTY_ENABLED=true`` is explicitly set.

The integration does NOT enable production runtime, schedulers, market sync,
persistence, Supabase, or sportsbook access. It does not modify frozen source
files. It only replaces module-local transport dependencies with certified
WNBA.com first-party adapters or explicit fail-soft/bypass sentinels where the
frozen layer already defines those semantics.
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any, Callable

import sports_api.wnba_availability as availability
import sports_api.wnba_event_lineup_context as event_lineup
import sports_api.wnba_player_event_features as event_features
import sports_api.wnba_player_opportunity_context as opportunity
import sports_api.wnba_projection_input_snapshot as projection_snapshot
import sports_api.wnba_rotation_context as rotation
import sports_api.wnba_schedule_context as schedule_context
from sports_api.wnba_game_history import WNBAHistoryUpstreamError
from sports_api.wnba_schedule import WNBAScheduleUpstreamError
from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_step7g_first_party_availability import (
    get_step7g_step4i_daily_schedule_dataset,
)
from sports_api.wnba_step7g_first_party_history import (
    get_first_party_player_recent_game_log_dataset,
    get_first_party_play_by_play_dataset,
)
from sports_api.wnba_step7g_first_party_injury_report import (
    get_step7g_first_party_injury_report_dataset,
)
from sports_api.wnba_step7g_first_party_rosters import (
    get_first_party_current_players_dataset,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)
from sports_api.wnba_step7g_first_party_shot_context import (
    get_first_party_opponent_defense_by_shot_zone_dataset,
    get_first_party_player_shot_chart_dataset,
)
from sports_api.wnba_step7g_first_party_team_history_cup_safe import (
    get_first_party_team_game_log_dataset,
    install_exact_cup_exclusion,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 7G first-party core integration"
MODEL_VERSION = "wnba_step_7g_first_party_core_integration_v6"
STEP7G_FIRST_PARTY_ENABLED_ENV = "WNBA_STEP7G_FIRST_PARTY_ENABLED"

_ORIGINAL_ROTATION_REQUEST = rotation._request_stats_json
_ORIGINAL_ROTATION_PLAYER_HISTORY = rotation.get_player_game_log_dataset
_ORIGINAL_EVENT_LINEUP_PBP = event_lineup.get_play_by_play_dataset
_ORIGINAL_EVENT_FEATURE_PLAYER_HISTORY = event_features.get_player_game_log_dataset
_ORIGINAL_OPPORTUNITY_ROLE = opportunity.get_player_role_context_dataset
_ORIGINAL_OPPORTUNITY_LINEUPS = opportunity.get_lineups_dataset
_ORIGINAL_SCHEDULE_CONTEXT_SEASON = schedule_context._season_schedule_dataset
_ORIGINAL_SCHEDULE_CONTEXT_TEAM_HISTORY = schedule_context.get_team_game_log_dataset
_ORIGINAL_AVAILABILITY_DAILY_SCHEDULE = availability.get_daily_schedule_dataset
_ORIGINAL_AVAILABILITY_CURRENT_ROSTER = availability.get_current_players_dataset
_ORIGINAL_AVAILABILITY_INJURY_REPORT = availability.get_latest_injury_report_dataset
_ORIGINAL_AVAILABILITY_RECENT_STATS = availability.get_player_season_stats_dataset
_ORIGINAL_AVAILABILITY_LINEUPS = availability.get_lineups_dataset
_ORIGINAL_PROJECTION_PLAYER_SHOT = projection_snapshot.get_player_shot_chart_dataset
_ORIGINAL_PROJECTION_OPPONENT_ZONE = (
    projection_snapshot.get_opponent_defense_by_shot_zone_dataset
)


def _environment(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _truthy(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step7g_first_party_enabled(env: Mapping[str, str] | None = None) -> bool:
    return _truthy(_environment(env), STEP7G_FIRST_PARTY_ENABLED_ENV, False)


def _rotation_stats_transport_unavailable(*args: Any, **kwargs: Any) -> Any:
    raise WNBAHistoryUpstreamError(
        "Step 7G first-party mode bypasses the unreachable direct WNBA Stats "
        "gamerotation transport so the certified WNBA.com reconstruction fallback runs."
    )


def _optional_lineup_stats_unavailable(*args: Any, **kwargs: Any) -> Any:
    raise opportunity.WNBALineupContextUpstreamError(
        "Step 7G first-party mode has no separately certified Step 4G Stats "
        "transport; this frozen Step 4V component is optional and unavailable."
    )


def _availability_recent_stats_unavailable(*args: Any, **kwargs: Any) -> Any:
    raise availability.WNBASeasonStatsUpstreamError(
        "Step 7G first-party mode leaves optional Step 4I recent aggregate stats "
        "unavailable rather than waiting on the unreachable Stats transport."
    )


def _availability_lineups_unavailable(*args: Any, **kwargs: Any) -> Any:
    raise availability.WNBALineupContextUpstreamError(
        "Step 7G first-party mode leaves optional Step 4I five-player lineup "
        "context unavailable rather than waiting on the unreachable Stats transport."
    )


def _availability_daily_schedule_first_party(
    target_date: str,
    season: int,
) -> dict[str, Any]:
    try:
        return get_step7g_step4i_daily_schedule_dataset(target_date, season)
    except (WNBAScheduleUpstreamError, WNBARestTravelUpstreamError) as exc:
        raise availability.WNBAAvailabilityUpstreamError(
            "Step 7G first-party daily schedule was unavailable for Step 4I: "
            f"{exc}"
        ) from exc


def _guarded_replace(
    *,
    label: str,
    current: Callable[..., Any],
    original: Callable[..., Any],
    target: Callable[..., Any],
) -> Callable[..., Any]:
    if current is target:
        return target
    if current is not original:
        raise RuntimeError(
            f"Step 7G first-party integration refuses to replace an unknown {label} override."
        )
    return target


def _install_enabled_seams() -> None:
    install_exact_cup_exclusion()

    rotation._request_stats_json = _guarded_replace(
        label="Step 4R rotation requester",
        current=rotation._request_stats_json,
        original=_ORIGINAL_ROTATION_REQUEST,
        target=_rotation_stats_transport_unavailable,
    )
    rotation.get_player_game_log_dataset = _guarded_replace(
        label="Step 4R player-history provider",
        current=rotation.get_player_game_log_dataset,
        original=_ORIGINAL_ROTATION_PLAYER_HISTORY,
        target=get_first_party_player_recent_game_log_dataset,
    )
    event_lineup.get_play_by_play_dataset = _guarded_replace(
        label="Step 4T play-by-play provider",
        current=event_lineup.get_play_by_play_dataset,
        original=_ORIGINAL_EVENT_LINEUP_PBP,
        target=get_first_party_play_by_play_dataset,
    )
    event_features.get_player_game_log_dataset = _guarded_replace(
        label="Step 4U player-history provider",
        current=event_features.get_player_game_log_dataset,
        original=_ORIGINAL_EVENT_FEATURE_PLAYER_HISTORY,
        target=get_first_party_player_recent_game_log_dataset,
    )
    opportunity.get_player_role_context_dataset = _guarded_replace(
        label="optional Step 4G role provider",
        current=opportunity.get_player_role_context_dataset,
        original=_ORIGINAL_OPPORTUNITY_ROLE,
        target=_optional_lineup_stats_unavailable,
    )
    opportunity.get_lineups_dataset = _guarded_replace(
        label="optional Step 4G lineup provider",
        current=opportunity.get_lineups_dataset,
        original=_ORIGINAL_OPPORTUNITY_LINEUPS,
        target=_optional_lineup_stats_unavailable,
    )
    schedule_context._season_schedule_dataset = _guarded_replace(
        label="Step 4N season-schedule provider",
        current=schedule_context._season_schedule_dataset,
        original=_ORIGINAL_SCHEDULE_CONTEXT_SEASON,
        target=get_step7g_step4n_season_schedule_dataset,
    )
    schedule_context.get_team_game_log_dataset = _guarded_replace(
        label="Step 4N team-history provider",
        current=schedule_context.get_team_game_log_dataset,
        original=_ORIGINAL_SCHEDULE_CONTEXT_TEAM_HISTORY,
        target=get_first_party_team_game_log_dataset,
    )
    availability.get_daily_schedule_dataset = _guarded_replace(
        label="Step 4I daily-schedule provider",
        current=availability.get_daily_schedule_dataset,
        original=_ORIGINAL_AVAILABILITY_DAILY_SCHEDULE,
        target=_availability_daily_schedule_first_party,
    )
    availability.get_current_players_dataset = _guarded_replace(
        label="Step 4I current-roster provider",
        current=availability.get_current_players_dataset,
        original=_ORIGINAL_AVAILABILITY_CURRENT_ROSTER,
        target=get_first_party_current_players_dataset,
    )
    availability.get_latest_injury_report_dataset = _guarded_replace(
        label="Step 4I injury-report provider",
        current=availability.get_latest_injury_report_dataset,
        original=_ORIGINAL_AVAILABILITY_INJURY_REPORT,
        target=get_step7g_first_party_injury_report_dataset,
    )
    availability.get_player_season_stats_dataset = _guarded_replace(
        label="optional Step 4I recent-stats provider",
        current=availability.get_player_season_stats_dataset,
        original=_ORIGINAL_AVAILABILITY_RECENT_STATS,
        target=_availability_recent_stats_unavailable,
    )
    availability.get_lineups_dataset = _guarded_replace(
        label="optional Step 4I lineup provider",
        current=availability.get_lineups_dataset,
        original=_ORIGINAL_AVAILABILITY_LINEUPS,
        target=_availability_lineups_unavailable,
    )
    projection_snapshot.get_player_shot_chart_dataset = _guarded_replace(
        label="Step 4W player-shot provider",
        current=projection_snapshot.get_player_shot_chart_dataset,
        original=_ORIGINAL_PROJECTION_PLAYER_SHOT,
        target=get_first_party_player_shot_chart_dataset,
    )
    projection_snapshot.get_opponent_defense_by_shot_zone_dataset = _guarded_replace(
        label="Step 4W opponent-zone provider",
        current=projection_snapshot.get_opponent_defense_by_shot_zone_dataset,
        original=_ORIGINAL_PROJECTION_OPPONENT_ZONE,
        target=get_first_party_opponent_defense_by_shot_zone_dataset,
    )


def get_step7g_first_party_status(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    enabled = step7g_first_party_enabled(env)
    seams = {
        "rotation_stats_bypass": rotation._request_stats_json
        is _rotation_stats_transport_unavailable,
        "rotation_player_history": rotation.get_player_game_log_dataset
        is get_first_party_player_recent_game_log_dataset,
        "event_lineup_play_by_play": event_lineup.get_play_by_play_dataset
        is get_first_party_play_by_play_dataset,
        "event_feature_player_history": event_features.get_player_game_log_dataset
        is get_first_party_player_recent_game_log_dataset,
        "optional_role_fail_soft": opportunity.get_player_role_context_dataset
        is _optional_lineup_stats_unavailable,
        "optional_lineup_fail_soft": opportunity.get_lineups_dataset
        is _optional_lineup_stats_unavailable,
        "schedule_context": schedule_context._season_schedule_dataset
        is get_step7g_step4n_season_schedule_dataset,
        "team_history": schedule_context.get_team_game_log_dataset
        is get_first_party_team_game_log_dataset,
        "availability_daily_schedule": availability.get_daily_schedule_dataset
        is _availability_daily_schedule_first_party,
        "availability_current_roster": availability.get_current_players_dataset
        is get_first_party_current_players_dataset,
        "availability_injury_report": availability.get_latest_injury_report_dataset
        is get_step7g_first_party_injury_report_dataset,
        "availability_recent_stats_fail_soft": availability.get_player_season_stats_dataset
        is _availability_recent_stats_unavailable,
        "availability_lineups_fail_soft": availability.get_lineups_dataset
        is _availability_lineups_unavailable,
        "projection_player_shot_context": projection_snapshot.get_player_shot_chart_dataset
        is get_first_party_player_shot_chart_dataset,
        "projection_opponent_zone_defense": (
            projection_snapshot.get_opponent_defense_by_shot_zone_dataset
            is get_first_party_opponent_defense_by_shot_zone_dataset
        ),
    }
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "enabled_flag": enabled,
        "all_core_seams_installed": all(seams.values()),
        "seams": seams,
        "certified_scope": {
            "season": 2026,
            "season_type": "Regular Season",
            "core_model_input_readiness": True,
            "current_availability_daily_schedule": True,
            "current_availability_roster": True,
            "current_availability_injury_report": True,
            "current_availability": True,
            "shot_context": False,
            "advanced_context": False,
            "officiating_context": False,
        },
        "safety": {
            "default_enabled": False,
            "production_runtime_enabled_by_this_module": False,
            "scheduler_started_by_this_module": False,
            "sportsbook_called_by_this_module": False,
            "supabase_mutation_supported_by_this_module": False,
            "persistence_supported_by_this_module": False,
            "frozen_step4x_source_modified": False,
            "frozen_step4j_source_modified": False,
            "frozen_step4n_source_modified": False,
            "frozen_step4i_source_modified": False,
            "frozen_step4l_source_modified": False,
            "frozen_step4c_source_modified": False,
            "frozen_step4b_source_modified": False,
        },
    }


def install_step7g_first_party_integration(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    enabled = step7g_first_party_enabled(env)
    if enabled:
        _install_enabled_seams()
    result = get_step7g_first_party_status(env)
    result["installed"] = bool(enabled and result["all_core_seams_installed"])
    return result


INSTALLATION = install_step7g_first_party_integration()
