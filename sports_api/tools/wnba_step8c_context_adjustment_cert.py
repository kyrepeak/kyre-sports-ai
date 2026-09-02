"""OFF-only live certification for the conservative Step-8C adjustment engine."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step8_context_adjustment import (
    MODEL_VERSION,
    SCHEMA_VERSION,
    get_player_game_step8_context_adjusted_projection,
    step8_context_adjustment_enabled,
)

REPORT_PATH = Path("step8c-context-adjustment-cert.json")
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
        raise RuntimeError("Step 8C cert refuses production switches: " + ", ".join(bad))
    for key in (
        "WNBA_STEP7G_FIRST_PARTY_ENABLED",
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED",
        "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED",
    ):
        if not _truthy(os.getenv(key)):
            raise RuntimeError(f"Step 8C cert requires isolated flag {key}=true.")
    if not step8_context_adjustment_enabled():
        raise RuntimeError("Step 8C context-adjustment flag is not enabled in isolated CI.")


def _num(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Step 8C cert expected numeric {label}.")
    result = float(value)
    if result != result:
        raise RuntimeError(f"Step 8C cert expected finite {label}.")
    return result


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])

    result = get_player_game_step8_context_adjusted_projection(player_id, game_id)
    if result.get("data_type") != "context_adjusted_deterministic_player_projection":
        raise RuntimeError("Step 8C returned wrong data type.")
    if result.get("schema_version") != SCHEMA_VERSION or result.get("model_version") != MODEL_VERSION:
        raise RuntimeError("Step 8C returned wrong schema/model version.")
    if result.get("game_id") != game_id or result.get("player_id") != player_id:
        raise RuntimeError("Step 8C returned wrong requested identity.")

    projection = result.get("projection")
    neutral = result.get("neutral_step8b_projection")
    adjustments = result.get("adjustment_summary")
    adjusted_rates = result.get("adjusted_official_per_minute_rates")
    if not all(isinstance(item, dict) for item in (projection, neutral, adjustments, adjusted_rates)):
        raise RuntimeError("Step 8C is missing projection/adjustment objects.")

    minutes_adj = adjustments.get("minutes") or {}
    pace_adj = adjustments.get("matchup_pace") or {}
    expected_minutes = min(_num(minutes_adj.get("official_recent_median_minutes"), "recent median minutes"), 40.0)
    actual_minutes = _num(projection.get("minutes"), "adjusted minutes")
    if abs(actual_minutes - expected_minutes) > 1e-6:
        raise RuntimeError("Step 8C adjusted minutes do not equal capped official recent median.")
    if minutes_adj.get("applied") is not True:
        raise RuntimeError("Step 8C did not mark the certified robust minutes adjustment as applied.")

    player_pace = _num(pace_adj.get("player_recent_estimated_pace"), "player pace")
    team_pace = _num(pace_adj.get("team_recent_estimated_pace"), "team pace")
    opponent_pace = _num(pace_adj.get("opponent_recent_estimated_pace"), "opponent pace")
    expected_matchup_pace = (team_pace + opponent_pace) / 2.0
    expected_pace_factor = expected_matchup_pace / player_pace
    actual_pace_factor = _num(pace_adj.get("pace_factor"), "pace factor")
    if abs(actual_pace_factor - expected_pace_factor) > 1e-7:
        raise RuntimeError("Step 8C pace factor does not reproduce the certified transparent formula.")
    if pace_adj.get("applied") is not True:
        raise RuntimeError("Step 8C did not mark matchup pace as applied.")

    for stat in ("points", "rebounds", "assists"):
        rate = _num(adjusted_rates.get(stat), f"adjusted {stat} rate")
        expected = rate * actual_minutes
        actual = _num(projection.get(stat), f"adjusted {stat}")
        if abs(actual - expected) > 2e-6:
            raise RuntimeError(f"Step 8C adjusted {stat} does not equal adjusted rate x adjusted minutes.")
    component_pra = sum(_num(projection.get(stat), stat) for stat in ("points", "rebounds", "assists"))
    if abs(component_pra - _num(projection.get("points_rebounds_assists"), "adjusted PRA")) > 2e-6:
        raise RuntimeError("Step 8C adjusted PRA does not equal P+R+A.")

    role = adjustments.get("role") or {}
    teammates = adjustments.get("teammate_availability") or {}
    rest = adjustments.get("rest_travel") or {}
    shot = adjustments.get("shot_zone_matchup") or {}
    if role.get("adjustment_applied") is not False or _num(role.get("mean_adjustment_factor"), "role factor") != 1.0:
        raise RuntimeError("Step 8C illegally applied an unverified current-role mean multiplier.")
    if teammates.get("opportunity_redistribution_applied") is not False or _num(teammates.get("mean_adjustment_factor"), "teammate factor") != 1.0:
        raise RuntimeError("Step 8C illegally redistributed missing teammate opportunity.")
    if rest.get("fatigue_or_travel_mean_adjustment_applied") is not False or _num(rest.get("mean_adjustment_factor"), "rest factor") != 1.0:
        raise RuntimeError("Step 8C illegally created an uncalibrated fatigue/travel penalty.")
    if shot.get("adjustment_applied") is not False or _num(shot.get("mean_adjustment_factor"), "shot factor") != 1.0:
        raise RuntimeError("Step 8C illegally created an uncalibrated shot-zone mean multiplier.")

    availability = result.get("current_availability") or {}
    if availability.get("current_roster_match") is not True:
        raise RuntimeError("Step 8C focal current-roster verification failed.")
    if availability.get("availability_blocking") is not False or availability.get("availability_uncertain") is not False:
        raise RuntimeError("Step 8C live focal availability is not certain/nonblocking.")

    semantics = result.get("semantics") or {}
    guardrails = result.get("guardrails") or {}
    verification = result.get("verification") or {}
    for key in (
        "minutes_use_robust_recent_official_median",
        "matchup_pace_scales_opportunity_linearly",
        "historical_role_does_not_create_current_role_assignment",
        "teammate_absences_do_not_redistribute_missing_minutes_or_usage",
        "rest_travel_does_not_create_uncalibrated_fatigue_penalty",
        "shot_zone_context_does_not_create_uncalibrated_scoring_multiplier",
        "advanced_efficiency_ratings_do_not_create_uncalibrated_scoring_multiplier",
    ):
        if semantics.get(key) is not True:
            raise RuntimeError(f"Step 8C semantic proof {key!r} is not true.")
    for key in (
        "no_projected_starter_created",
        "no_teammate_opportunity_redistribution_created",
        "no_fatigue_score_created",
        "no_shot_zone_mean_multiplier_created",
        "no_advanced_rating_mean_multiplier_created",
        "no_monte_carlo_created",
        "no_sportsbook_data_created",
        "no_betting_probability_created",
        "no_persistence_created",
    ):
        if guardrails.get(key) is not True:
            raise RuntimeError(f"Step 8C guardrail {key!r} is not true.")
    if guardrails.get("production_activation_allowed") is not False:
        raise RuntimeError("Step 8C unexpectedly permits production activation.")
    for key in (
        "step8b_core_rebuilt_from_certified_handoff_and_baseline",
        "player_team_opponent_advanced_identity_verified",
        "current_focal_availability_certain_and_nonblocking",
        "official_recent_median_minutes_used",
        "pace_inputs_first_party_advanced_context",
        "pace_factor_sanity_checked_not_clipped",
        "pra_recomposed_from_adjusted_p_r_a",
    ):
        if verification.get(key) is not True:
            raise RuntimeError(f"Step 8C verification {key!r} is not true.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError("Step 8C unexpectedly used a third-party source.")

    report = {
        "data_type": "wnba_step8c_context_adjustment_cert_v1",
        "certification_result": "STEP8C_CONSERVATIVE_CONTEXT_ADJUSTMENT_LIVE_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "projection": {
            "projection_id": result.get("projection_id"),
            "projection_content_sha256": result.get("projection_content_sha256"),
            "model_version": result.get("model_version"),
            "neutral_step8b": {
                "minutes": neutral.get("minutes"),
                "points": neutral.get("points"),
                "rebounds": neutral.get("rebounds"),
                "assists": neutral.get("assists"),
                "points_rebounds_assists": neutral.get("points_rebounds_assists"),
            },
            "adjusted": {
                "minutes": projection.get("minutes"),
                "points": projection.get("points"),
                "rebounds": projection.get("rebounds"),
                "assists": projection.get("assists"),
                "points_rebounds_assists": projection.get("points_rebounds_assists"),
            },
            "combined_mean_scale_vs_step8b": result.get("combined_mean_scale_vs_step8b"),
        },
        "applied_adjustments": {
            "minutes": minutes_adj,
            "matchup_pace": pace_adj,
        },
        "neutral_context": {
            "role": role,
            "teammate_availability": teammates,
            "rest_travel": rest,
            "shot_zone_matchup": shot,
        },
        "safety": {
            "context_adjusted_projection_created": True,
            "teammate_opportunity_redistributed": False,
            "fatigue_score_created": False,
            "shot_zone_mean_multiplier_created": False,
            "advanced_rating_mean_multiplier_created": False,
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
    print("STEP8C_CONSERVATIVE_CONTEXT_ADJUSTMENT_LIVE_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
