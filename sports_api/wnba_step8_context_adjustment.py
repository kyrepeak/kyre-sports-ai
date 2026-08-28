"""Step 8C conservative WNBA context-adjustment engine.

Builds on the live-certified Step-8B neutral deterministic projection. Only two
mean adjustments are applied in v1 because they are directly supported by the
certified handoff:

1. recent official-box median minutes replaces the Step-8B mean-minute anchor as
   a robust central-tendency minutes estimate (still capped at 40 regulation
   minutes); and
2. P/R/A per-minute rates are scaled linearly by a transparent current-matchup
   pace proxy: mean(team recent estimated pace, opponent recent estimated pace)
   divided by the focal player's recent estimated pace.

Historical starter/bench role, teammate absences, rest/travel, advanced
ratings, and shot-zone matchup are carried as context but do not alter the mean
unless a future separately certified/calibrated rule exists. In particular,
missing teammate minutes/usage are never redistributed here.

No Monte Carlo, sportsbook probability, persistence, or production activation
is created in Step 8C.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Mapping

from sports_api.wnba_step8_core_projection import (
    MODEL_VERSION as STEP8B_MODEL_VERSION,
    build_step8_core_projection,
)
from sports_api.wnba_step8_official_box_baseline import build_step8_official_box_baseline
from sports_api.wnba_step8_projection_handoff import get_player_game_step8_projection_handoff

SOURCE = "Kyre Sports API WNBA Step 8C conservative context adjustment"
SCHEMA_VERSION = "wnba_step_8c_context_adjusted_projection_v1"
MODEL_VERSION = "wnba_step8c_median_minutes_matchup_pace_2026_regular_v1"
STEP8_CONTEXT_ADJUSTMENT_ENABLED_ENV = "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED"
REGULATION_MINUTES_CAP = 40.0
MIN_PLAUSIBLE_PACE = 40.0
MAX_PLAUSIBLE_PACE = 160.0
MIN_PLAUSIBLE_PACE_RATIO = 0.75
MAX_PLAUSIBLE_PACE_RATIO = 1.25

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep8ContextAdjustmentDisabledError(RuntimeError):
    """Raised when the isolated Step-8C engine is not explicitly enabled."""


class WNBAStep8ContextAdjustmentNotReadyError(RuntimeError):
    """Raised when current player state is too uncertain for an adjusted mean."""


class WNBAStep8ContextAdjustmentUpstreamError(RuntimeError):
    """Raised when certified Step-8 evidence is malformed or contradictory."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def step8_context_adjustment_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP8_CONTEXT_ADJUSTMENT_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [key for key in _OFF_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep8ContextAdjustmentDisabledError(
            "Step 8C refuses production switches: " + ", ".join(bad)
        )
    for key in (
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED",
        STEP8_CONTEXT_ADJUSTMENT_ENABLED_ENV,
    ):
        if not _truthy(source.get(key)):
            raise WNBAStep8ContextAdjustmentDisabledError(
                f"Step 8C requires isolated flag {key}=true."
            )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStep8ContextAdjustmentUpstreamError(f"Step 8C {label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep8ContextAdjustmentUpstreamError(
            f"Step 8C {label} must be numeric."
        ) from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise WNBAStep8ContextAdjustmentUpstreamError(f"Step 8C {label} must be finite.")
    return result


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _advanced_row(dataset: Any, collection: str, label: str) -> dict[str, Any]:
    if not isinstance(dataset, dict):
        raise WNBAStep8ContextAdjustmentUpstreamError(f"Step 8C {label} dataset is missing.")
    rows = dataset.get(collection)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise WNBAStep8ContextAdjustmentUpstreamError(
            f"Step 8C {label} dataset must contain exactly one row."
        )
    return rows[0]


def _pace(row: Mapping[str, Any], label: str) -> float:
    advanced = row.get("advanced")
    if not isinstance(advanced, Mapping):
        raise WNBAStep8ContextAdjustmentUpstreamError(f"Step 8C {label} advanced metrics are missing.")
    value = _number(advanced.get("estimated_pace"), f"{label} estimated pace")
    if not MIN_PLAUSIBLE_PACE < value < MAX_PLAUSIBLE_PACE:
        raise WNBAStep8ContextAdjustmentUpstreamError(
            f"Step 8C {label} estimated pace is outside plausible units: {value}."
        )
    return value


def _role_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    inputs = snapshot.get("inputs")
    opportunity = inputs.get("player_opportunity_context") if isinstance(inputs, dict) else None
    role = opportunity.get("observed_role_context") if isinstance(opportunity, dict) else None
    if not isinstance(role, dict):
        return {
            "available": False,
            "observed_role_band": None,
            "mean_adjustment_factor": 1.0,
            "adjustment_applied": False,
            "reason": "historical_role_context_missing_no_current_role_inferred",
        }
    available = role.get("available") is True
    return {
        "available": available,
        "observed_role_band": role.get("observed_role_band"),
        "mean_adjustment_factor": 1.0,
        "adjustment_applied": False,
        "reason": (
            "historical_role_is_descriptive_not_a_current_role_assignment"
            if available
            else "optional_first_party_role_context_unavailable_no_current_role_inferred"
        ),
    }


def _current_context(snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = snapshot.get("availability_summary")
    if not isinstance(summary, dict):
        raise WNBAStep8ContextAdjustmentNotReadyError("Step 8C requires current availability summary.")
    focal = summary.get("focal_player_availability")
    if not isinstance(focal, dict) or summary.get("focal_player_current_roster_match") is not True:
        raise WNBAStep8ContextAdjustmentNotReadyError("Step 8C focal current-roster availability is unresolved.")
    if focal.get("availability_blocking") is True:
        raise WNBAStep8ContextAdjustmentNotReadyError("Step 8C refuses a blocking focal availability state.")
    if focal.get("availability_uncertain") is True:
        raise WNBAStep8ContextAdjustmentNotReadyError(
            "Step 8C refuses to guess participation/minutes for an uncertain focal availability state."
        )

    inputs = snapshot.get("inputs")
    raw = inputs.get("game_availability") if isinstance(inputs, dict) else None
    side = _clean((snapshot.get("focal_identity") or {}).get("side"))
    side_obj = raw.get(side) if isinstance(raw, dict) and side in {"away", "home"} else None
    players = side_obj.get("players") if isinstance(side_obj, dict) else None
    flagged: list[dict[str, Any]] = []
    focal_player_id = snapshot.get("player_id")
    if isinstance(players, list):
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
                "availability_class": row.get("availability_class"),
                "availability_blocking": bool(row.get("availability_blocking")),
                "availability_uncertain": bool(row.get("availability_uncertain")),
                "recent_minutes_per_game": row.get("recent_minutes_per_game"),
                "observed_rotation_rank_by_recent_minutes": row.get("observed_rotation_rank_by_recent_minutes"),
            })
    flagged.sort(key=lambda row: (row.get("player_name") or "", row.get("player_id") or 0))
    teammate_context = {
        "flagged_teammate_count": len(flagged),
        "flagged_teammates": flagged,
        "mean_adjustment_factor": 1.0,
        "opportunity_redistribution_applied": False,
        "reason": "certified_teammate_minutes_and_usage_redistribution_inputs_not_complete",
    }
    return {
        "availability_class": focal.get("availability_class"),
        "listed_on_injury_report": bool(focal.get("listed_on_injury_report")),
        "availability_uncertain": False,
        "availability_blocking": False,
        "current_roster_match": True,
    }, teammate_context


def _rest_travel_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    inputs = snapshot.get("inputs")
    dataset = inputs.get("game_rest_travel_context") if isinstance(inputs, dict) else None
    side = _clean((snapshot.get("focal_identity") or {}).get("side"))
    opponent_side = "away" if side == "home" else "home" if side == "away" else None
    focal = dataset.get(f"{side}_context") if isinstance(dataset, dict) and side else None
    opponent = dataset.get(f"{opponent_side}_context") if isinstance(dataset, dict) and opponent_side else None

    def compact(context: Any) -> dict[str, Any] | None:
        if not isinstance(context, dict):
            return None
        travel = context.get("travel_to_target_or_next_game")
        workload = context.get("observed_workload")
        return {
            "team_key": ((context.get("team") or {}).get("team_key") if isinstance(context.get("team"), dict) else None),
            "rest": context.get("rest"),
            "schedule_density": context.get("schedule_density"),
            "road_trip": context.get("road_trip"),
            "travel": {
                "available": travel.get("available"),
                "great_circle_miles": travel.get("great_circle_miles"),
                "timezone_offset_change_hours": travel.get("timezone_offset_change_hours"),
                "same_city": travel.get("same_city"),
            } if isinstance(travel, dict) else None,
            "observed_workload": {
                "completed_games_previous_3_days": workload.get("completed_games_previous_3_days"),
                "completed_games_previous_5_days": workload.get("completed_games_previous_5_days"),
                "completed_games_previous_7_days": workload.get("completed_games_previous_7_days"),
                "team_minutes_previous_7_days": workload.get("team_minutes_previous_7_days"),
                "team_minutes_above_regulation_previous_7_days": workload.get("team_minutes_above_regulation_previous_7_days"),
            } if isinstance(workload, dict) else None,
        }

    return {
        "focal": compact(focal),
        "opponent": compact(opponent),
        "mean_adjustment_factor": 1.0,
        "fatigue_or_travel_mean_adjustment_applied": False,
        "reason": "rest_travel_is_certified_descriptive_context_without_a_calibrated_mean_effect",
    }


def _shot_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    inputs = snapshot.get("inputs")
    if not isinstance(inputs, dict):
        return {"available": False, "mean_adjustment_factor": 1.0, "adjustment_applied": False}
    recent = inputs.get("player_recent_shot_chart")
    h2h = inputs.get("player_vs_opponent_shot_chart")
    defense = inputs.get("opponent_defense_by_shot_zone")
    available = all(isinstance(item, dict) for item in (recent, h2h, defense))
    return {
        "available": available,
        "player_recent_attempts": recent.get("attempt_count") if isinstance(recent, dict) else None,
        "player_vs_opponent_attempts": h2h.get("attempt_count") if isinstance(h2h, dict) else None,
        "player_vs_opponent_game_count": h2h.get("selected_game_count") if isinstance(h2h, dict) else None,
        "opponent_defense_game_count": defense.get("selected_game_count") if isinstance(defense, dict) else None,
        "mean_adjustment_factor": 1.0,
        "adjustment_applied": False,
        "reason": "zone_context_has_no_certified_league_average_or_calibrated_conversion_to_player_points",
    }


def build_step8_context_adjusted_projection(
    handoff: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the conservative deterministic Step-8C adjusted projection."""
    core = build_step8_core_projection(handoff, baseline)
    if core.get("model_version") != STEP8B_MODEL_VERSION:
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C received an unsupported Step-8B core model.")
    snapshot = handoff.get("snapshot")
    if not isinstance(snapshot, dict):
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C handoff snapshot is missing.")
    if core.get("game_id") != snapshot.get("game_id") or core.get("player_id") != snapshot.get("player_id"):
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C core identity disagrees with Step 8A.")

    availability, teammates = _current_context(snapshot)
    role = _role_context(snapshot)
    rest_travel = _rest_travel_context(snapshot)
    shot = _shot_context(snapshot)

    dispersion = core.get("historical_dispersion")
    minute_dispersion = dispersion.get("minutes") if isinstance(dispersion, dict) else None
    if not isinstance(minute_dispersion, dict):
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C is missing official recent minute dispersion.")
    median_minutes = _number(minute_dispersion.get("recent_median"), "recent median minutes")
    if median_minutes <= 0.0 or median_minutes > 60.0:
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C recent median minutes are implausible.")
    adjusted_minutes = min(median_minutes, REGULATION_MINUTES_CAP)

    inputs = snapshot.get("inputs")
    if not isinstance(inputs, dict):
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C snapshot inputs are missing.")
    player_row = _advanced_row(inputs.get("player_advanced"), "players", "player advanced")
    team_row = _advanced_row(inputs.get("team_advanced"), "teams", "team advanced")
    opponent_row = _advanced_row(inputs.get("opponent_advanced"), "teams", "opponent advanced")
    focal = snapshot.get("focal_identity") or {}
    player_id = snapshot.get("player_id")
    team_key = _clean(focal.get("team_key"))
    opponent_key = _clean(focal.get("opponent_team_key"))
    if player_row.get("player_id") != player_id or _clean(player_row.get("team_key")) != team_key:
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C player advanced identity disagrees with focal identity.")
    if _clean(team_row.get("team_key")) != team_key or _clean(opponent_row.get("team_key")) != opponent_key:
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C team/opponent advanced identity disagrees with focal identity.")

    player_pace = _pace(player_row, "player")
    team_pace = _pace(team_row, "team")
    opponent_pace = _pace(opponent_row, "opponent")
    matchup_pace = (team_pace + opponent_pace) / 2.0
    pace_factor = matchup_pace / player_pace
    if not MIN_PLAUSIBLE_PACE_RATIO <= pace_factor <= MAX_PLAUSIBLE_PACE_RATIO:
        raise WNBAStep8ContextAdjustmentUpstreamError(
            f"Step 8C raw pace factor {pace_factor:.6f} is outside the fail-closed sanity range."
        )

    rates = core.get("official_per_minute_rates")
    if not isinstance(rates, dict):
        raise WNBAStep8ContextAdjustmentUpstreamError("Step 8C core official rates are missing.")
    adjusted_rates = {
        stat: round(_number(rates.get(stat), f"core {stat} rate") * pace_factor, 8)
        for stat in ("points", "rebounds", "assists", "points_rebounds_assists")
    }
    projection = {
        stat: round(adjusted_rates[stat] * adjusted_minutes, 6)
        for stat in ("points", "rebounds", "assists")
    }
    projection["minutes"] = round(adjusted_minutes, 6)
    projection["points_rebounds_assists"] = round(
        projection["points"] + projection["rebounds"] + projection["assists"], 6
    )

    neutral = core.get("projection") or {}
    adjustment = {
        "minutes": {
            "neutral_mean_minutes": core.get("neutral_regulation_minutes_anchor"),
            "official_recent_median_minutes": round(median_minutes, 6),
            "adjusted_minutes": round(adjusted_minutes, 6),
            "delta_minutes": round(adjusted_minutes - _number(core.get("neutral_regulation_minutes_anchor"), "neutral minutes"), 6),
            "method": "official_recent_box_median_capped_at_40_regulation_minutes",
            "applied": True,
        },
        "matchup_pace": {
            "player_recent_estimated_pace": round(player_pace, 6),
            "team_recent_estimated_pace": round(team_pace, 6),
            "opponent_recent_estimated_pace": round(opponent_pace, 6),
            "current_matchup_pace_proxy": round(matchup_pace, 6),
            "pace_factor": round(pace_factor, 8),
            "method": "mean_team_opponent_recent_estimated_pace_divided_by_player_recent_estimated_pace",
            "applied": True,
        },
        "role": role,
        "teammate_availability": teammates,
        "rest_travel": rest_travel,
        "shot_zone_matchup": shot,
    }
    total_scale = projection["points_rebounds_assists"] / _number(neutral.get("points_rebounds_assists"), "neutral PRA")

    content = {
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "step8b_core_projection_content_sha256": core.get("projection_content_sha256"),
        "game_id": core.get("game_id"),
        "player_id": core.get("player_id"),
        "adjusted_minutes": round(adjusted_minutes, 6),
        "pace_factor": round(pace_factor, 8),
        "adjusted_rates": adjusted_rates,
        "projection": projection,
    }
    digest = _canonical_hash(content)
    return {
        "source": SOURCE,
        "data_type": "context_adjusted_deterministic_player_projection",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "projection_id": f"wnba-8c-{core['game_id']}-{core['player_id']}-{digest[:16]}",
        "projection_content_sha256": digest,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": core.get("season"),
        "season_type": core.get("season_type"),
        "game_id": core.get("game_id"),
        "player_id": core.get("player_id"),
        "team_key": core.get("team_key"),
        "opponent_team_key": core.get("opponent_team_key"),
        "neutral_step8b_projection": neutral,
        "adjusted_official_per_minute_rates": adjusted_rates,
        "projection": projection,
        "adjustment_summary": adjustment,
        "combined_mean_scale_vs_step8b": round(total_scale, 8),
        "current_availability": availability,
        "provenance": {
            "step8a_handoff_id": handoff.get("handoff_id"),
            "step8a_handoff_content_sha256": handoff.get("handoff_content_sha256"),
            "step8b_baseline_id": baseline.get("baseline_id"),
            "step8b_baseline_content_sha256": baseline.get("baseline_content_sha256"),
            "step8b_core_projection_id": core.get("projection_id"),
            "step8b_core_projection_content_sha256": core.get("projection_content_sha256"),
        },
        "semantics": {
            "minutes_use_robust_recent_official_median": True,
            "matchup_pace_scales_opportunity_linearly": True,
            "historical_role_does_not_create_current_role_assignment": True,
            "teammate_absences_do_not_redistribute_missing_minutes_or_usage": True,
            "rest_travel_does_not_create_uncalibrated_fatigue_penalty": True,
            "shot_zone_context_does_not_create_uncalibrated_scoring_multiplier": True,
            "advanced_efficiency_ratings_do_not_create_uncalibrated_scoring_multiplier": True,
        },
        "guardrails": {
            "deterministic_context_adjusted_projection_created": True,
            "no_projected_starter_created": True,
            "no_teammate_opportunity_redistribution_created": True,
            "no_fatigue_score_created": True,
            "no_shot_zone_mean_multiplier_created": True,
            "no_advanced_rating_mean_multiplier_created": True,
            "no_monte_carlo_created": True,
            "no_sportsbook_data_created": True,
            "no_betting_probability_created": True,
            "no_persistence_created": True,
            "production_activation_allowed": False,
        },
        "verification": {
            "step8b_core_rebuilt_from_certified_handoff_and_baseline": True,
            "player_team_opponent_advanced_identity_verified": True,
            "current_focal_availability_certain_and_nonblocking": True,
            "official_recent_median_minutes_used": True,
            "pace_inputs_first_party_advanced_context": True,
            "pace_factor_sanity_checked_not_clipped": True,
            "pra_recomposed_from_adjusted_p_r_a": True,
            "third_party_sources_used": False,
        },
    }


def get_player_game_step8_context_adjusted_projection(player_id: int, game_id: str) -> dict[str, Any]:
    """OFF-by-default live wrapper for the conservative Step-8C engine."""
    _assert_safe_environment()
    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    baseline = build_step8_official_box_baseline(handoff)
    return build_step8_context_adjusted_projection(handoff, baseline)


__all__ = [
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "STEP8_CONTEXT_ADJUSTMENT_ENABLED_ENV",
    "WNBAStep8ContextAdjustmentDisabledError",
    "WNBAStep8ContextAdjustmentNotReadyError",
    "WNBAStep8ContextAdjustmentUpstreamError",
    "build_step8_context_adjusted_projection",
    "get_player_game_step8_context_adjusted_projection",
    "step8_context_adjustment_enabled",
]
