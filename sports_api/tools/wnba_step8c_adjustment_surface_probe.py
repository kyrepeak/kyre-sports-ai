"""OFF-only sanitized Step-8C adjustment-surface probe.

Consumes the certified Step-8A handoff, live-certified Step-8B official-box
baseline, and certified neutral Step-8B core in one process. It exposes only
observed inputs that could support later minutes/role/matchup adjustments.

No adjustment, fatigue score, opportunity redistribution, Monte Carlo result,
sportsbook probability, or persistence record is created here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step8_core_projection import build_step8_core_projection
from sports_api.wnba_step8_official_box_baseline import build_step8_official_box_baseline
from sports_api.wnba_step8_projection_handoff import get_player_game_step8_projection_handoff

REPORT_PATH = Path("step8c-adjustment-surface-probe.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Step 8C probe refuses production switches: " + ", ".join(bad))
    for key in (
        "WNBA_STEP7G_FIRST_PARTY_ENABLED",
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED",
    ):
        if not _truthy(os.getenv(key)):
            raise RuntimeError(f"Step 8C probe requires isolated flag {key}=true.")


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _advanced_row(dataset: Any, collection: str) -> dict[str, Any] | None:
    if not isinstance(dataset, dict):
        return None
    rows = dataset.get(collection)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    return rows[0]


def _advanced_metrics(row: dict[str, Any] | None, *, player: bool) -> dict[str, Any] | None:
    if row is None:
        return None
    advanced = row.get("advanced")
    if not isinstance(advanced, dict):
        return None
    keys = [
        "estimated_pace",
        "effective_field_goal_percentage",
        "true_shooting_percentage",
        "estimated_rebound_percentage",
        "player_impact_estimate",
    ]
    if player:
        keys += [
            "estimated_usage_percentage",
            "assist_percentage",
            "estimated_assist_ratio",
            "assist_to_turnover_ratio",
        ]
    else:
        keys += [
            "estimated_offensive_rating",
            "estimated_defensive_rating",
            "estimated_net_rating",
        ]
    return {
        "team_key": row.get("team_key"),
        "player_id": row.get("player_id") if player else None,
        "games_played": row.get("games_played"),
        "minutes": row.get("minutes"),
        "metrics": {key: advanced.get(key) for key in keys},
    }


def _shot_zones(dataset: Any, *, defense: bool = False) -> dict[str, Any] | None:
    if not isinstance(dataset, dict):
        return None
    rows = dataset.get("zones_allowed" if defense else "zone_summary")
    if not isinstance(rows, list):
        return None
    sanitized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if defense:
            sanitized.append({
                "canonical_zone": row.get("canonical_zone"),
                "shot_zone_basic": row.get("shot_zone_basic"),
                "field_goals_made_allowed": row.get("field_goals_made_allowed"),
                "field_goals_attempted_allowed": row.get("field_goals_attempted_allowed"),
                "field_goal_percentage_allowed": row.get("field_goal_percentage_allowed"),
            })
        else:
            sanitized.append({
                "canonical_zone": row.get("canonical_zone"),
                "shot_zone_basic": row.get("shot_zone_basic"),
                "field_goals_made": row.get("field_goals_made"),
                "field_goals_attempted": row.get("field_goals_attempted"),
                "field_goal_percentage": row.get("field_goal_percentage"),
                "attempt_share": row.get("attempt_share"),
                "observed_points_per_attempt": row.get("observed_points_per_attempt"),
            })
    return {
        "data_type": dataset.get("data_type"),
        "selected_game_count": dataset.get("selected_game_count"),
        "selected_game_ids": dataset.get("selected_game_ids"),
        "shot_count": dataset.get("shot_count"),
        "attempt_count": dataset.get("attempt_count"),
        "made_count": dataset.get("made_count"),
        "field_goal_percentage": dataset.get("field_goal_percentage"),
        "defending_team_key": dataset.get("defending_team_key"),
        "zones": sanitized,
    }


def _availability_teammates(availability: Any, side: str, focal_player_id: int) -> dict[str, Any]:
    side_obj = availability.get(side) if isinstance(availability, dict) else None
    players = side_obj.get("players") if isinstance(side_obj, dict) else None
    if not isinstance(players, list):
        return {"available": False, "flagged_teammates": [], "player_count": None}
    flagged = []
    for row in players:
        if not isinstance(row, dict) or row.get("player_id") == focal_player_id:
            continue
        if not (
            row.get("availability_blocking") is True
            or row.get("availability_uncertain") is True
            or row.get("listed_on_injury_report") is True
        ):
            continue
        flagged.append({
            "player_id": row.get("player_id"),
            "player_name": row.get("player_name"),
            "position": row.get("position"),
            "availability_class": row.get("availability_class"),
            "availability_blocking": row.get("availability_blocking"),
            "availability_uncertain": row.get("availability_uncertain"),
            "listed_on_injury_report": row.get("listed_on_injury_report"),
            "injury_report_status": row.get("injury_report_status"),
            "injury_reason": row.get("injury_reason"),
            "recent_minutes_per_game": row.get("recent_minutes_per_game"),
            "observed_rotation_rank_by_recent_minutes": row.get("observed_rotation_rank_by_recent_minutes"),
        })
    flagged.sort(key=lambda row: (row.get("player_name") or "", row.get("player_id") or 0))
    return {
        "available": True,
        "player_count": len(players),
        "flagged_teammate_count": len(flagged),
        "flagged_teammates": flagged,
        "automatic_opportunity_redistribution_allowed": False,
    }


def _team_schedule_context(rest_travel: Any, side: str) -> dict[str, Any] | None:
    context = rest_travel.get(f"{side}_context") if isinstance(rest_travel, dict) else None
    if not isinstance(context, dict):
        return None
    workload = context.get("observed_workload")
    return {
        "team_key": _dig(context, "team", "team_key"),
        "rest": context.get("rest"),
        "schedule_density": context.get("schedule_density"),
        "road_trip": context.get("road_trip"),
        "travel_to_target": context.get("travel_to_target_or_next_game"),
        "observed_workload": {
            "completed_games_previous_3_days": _dig(workload, "completed_games_previous_3_days"),
            "completed_games_previous_5_days": _dig(workload, "completed_games_previous_5_days"),
            "completed_games_previous_7_days": _dig(workload, "completed_games_previous_7_days"),
            "team_minutes_previous_7_days": _dig(workload, "team_minutes_previous_7_days"),
            "team_minutes_above_regulation_previous_7_days": _dig(workload, "team_minutes_above_regulation_previous_7_days"),
            "games_above_regulation_team_minutes_previous_7_days": _dig(workload, "games_above_regulation_team_minutes_previous_7_days"),
        } if isinstance(workload, dict) else None,
    }


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])

    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    baseline = build_step8_official_box_baseline(handoff)
    core = build_step8_core_projection(handoff, baseline)
    snapshot = handoff["snapshot"]
    inputs = snapshot["inputs"]
    opportunity = inputs["player_opportunity_context"]
    focal = snapshot["focal_identity"]
    side = str(focal["side"])
    opponent_side = "away" if side == "home" else "home"

    stability = _dig(opportunity, "observed_minutes_opportunity", "tracked_minutes", "stability") or {}
    role = opportunity.get("observed_role_context")
    availability = inputs.get("game_availability")
    rest_travel = inputs.get("game_rest_travel_context")
    player_advanced = _advanced_row(inputs.get("player_advanced"), "players")
    team_advanced = _advanced_row(inputs.get("team_advanced"), "teams")
    opponent_advanced = _advanced_row(inputs.get("opponent_advanced"), "teams")

    report = {
        "data_type": "wnba_step8c_adjustment_surface_probe_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "core_projection": {
            "projection_id": core.get("projection_id"),
            "projection_content_sha256": core.get("projection_content_sha256"),
            "model_version": core.get("model_version"),
            "minutes": _dig(core, "projection", "minutes"),
            "points": _dig(core, "projection", "points"),
            "rebounds": _dig(core, "projection", "rebounds"),
            "assists": _dig(core, "projection", "assists"),
            "points_rebounds_assists": _dig(core, "projection", "points_rebounds_assists"),
        },
        "minutes_surface": {
            "tracked_minutes_by_game": stability.get("tracked_minutes_by_game"),
            "mean": stability.get("tracked_minutes_mean"),
            "median": stability.get("tracked_minutes_median"),
            "minimum": stability.get("tracked_minutes_min"),
            "maximum": stability.get("tracked_minutes_max"),
            "population_stddev": stability.get("tracked_minutes_population_stddev"),
            "coefficient_of_variation": stability.get("tracked_minutes_coefficient_of_variation"),
            "start_share": stability.get("start_share"),
            "neutral_core_minutes": core.get("neutral_regulation_minutes_anchor"),
        },
        "role_surface": {
            "available": role.get("available") if isinstance(role, dict) else False,
            "error": role.get("error") if isinstance(role, dict) else None,
            "observed_role_band": role.get("observed_role_band") if isinstance(role, dict) else None,
            "role_summary": role.get("role_summary") if isinstance(role, dict) else None,
            "starter": role.get("starter") if isinstance(role, dict) else None,
            "bench": role.get("bench") if isinstance(role, dict) else None,
            "projected_role_inferred": False,
        },
        "current_team_availability_surface": {
            "focal_summary": snapshot.get("availability_summary"),
            "teammates": _availability_teammates(availability, side, player_id),
            "teammate_missing_minutes_redistributed": False,
        },
        "rest_travel_surface": {
            "focal": _team_schedule_context(rest_travel, side),
            "opponent": _team_schedule_context(rest_travel, opponent_side),
            "fatigue_score_created": False,
        },
        "advanced_surface": {
            "player": _advanced_metrics(player_advanced, player=True),
            "team": _advanced_metrics(team_advanced, player=False),
            "opponent": _advanced_metrics(opponent_advanced, player=False),
        },
        "shot_matchup_surface": {
            "player_recent": _shot_zones(inputs.get("player_recent_shot_chart")),
            "player_vs_opponent": _shot_zones(inputs.get("player_vs_opponent_shot_chart")),
            "opponent_defense": _shot_zones(inputs.get("opponent_defense_by_shot_zone"), defense=True),
            "matchup_multiplier_created": False,
        },
        "safety": {
            "new_adjusted_projection_created": False,
            "projected_minutes_created": False,
            "projected_role_created": False,
            "fatigue_score_created": False,
            "teammate_opportunity_redistributed": False,
            "matchup_multiplier_created": False,
            "monte_carlo_created": False,
            "sportsbook_called": False,
            "betting_probability_created": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8C_ADJUSTMENT_SURFACE_PROBED_NO_ADJUSTMENT_CREATED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
