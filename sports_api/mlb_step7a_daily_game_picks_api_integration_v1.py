"""Step 7A contract for the MLB Daily Game Picks API presentation boundary.

This module is intentionally pure and read-only. It evaluates whether the
already-certified Step 5.2 exact-ID FanDuel market context and the frozen Step 6G
graduated-production state are both present and healthy enough for the Daily
Game Picks page to claim API integration.

It never fetches network data, changes a candidate, changes selection, or mutates
production exposure. If any evidence is missing or inconsistent, callers must
fall back to the frozen Step 6 page behavior.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

DATA_TYPE = "mlb_step7a_daily_game_picks_api_integration_v1"
SCHEMA_VERSION = 1
EXPECTED_LIVE_CONTEXT_DATA_TYPE = "mlb_live_market_context_v1"
EXPECTED_API_DATA_TYPE = "mlb_live_odds_api_response_v1"
EXPECTED_STEP6G_DATA_TYPE = "mlb_step6g_controlled_graduation_presentation_v1"
EXPECTED_SOURCE = "FanDuel"
EXPECTED_MATCH_METHOD = "official_mlb_game_id_exact"
API_CONNECTED = "API_ENRICHED_FROZEN_STEP6"
FALLBACK = "FROZEN_STEP6_FALLBACK"

_PROTECTED_FALSE_FLAGS = (
    "model_math_impact",
    "pick_strength_impact",
    "ranking_math_impact",
    "risk_logic_impact",
    "wnba_impact",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def evaluate_daily_game_picks_api_integration(
    live_market_state: Mapping[str, Any] | None,
    step6g_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a fail-open page-integration decision without mutating inputs."""
    live = deepcopy(_mapping(live_market_state))
    step6 = deepcopy(_mapping(step6g_state))
    failures: list[str] = []

    if live.get("available") is not True:
        failures.append("live_market_context_unavailable")
    if live.get("data_type") != EXPECTED_LIVE_CONTEXT_DATA_TYPE:
        failures.append("unexpected_live_market_context_data_type")
    if live.get("api_data_type") != EXPECTED_API_DATA_TYPE:
        failures.append("unexpected_api_data_type")
    if live.get("source") != EXPECTED_SOURCE:
        failures.append("unexpected_live_market_source")
    if live.get("match_method") != EXPECTED_MATCH_METHOD:
        failures.append("exact_official_game_id_join_not_proven")
    if live.get("fallback_matching_used") is not False:
        failures.append("fallback_or_fuzzy_matching_detected")

    contexts = live.get("contexts_by_game_id")
    if not isinstance(contexts, Mapping):
        failures.append("contexts_by_game_id_missing")
        context_count = 0
    else:
        context_count = len(contexts)

    attached_count = live.get("attached_count")
    if isinstance(attached_count, bool) or not isinstance(attached_count, int) or attached_count < 0:
        failures.append("invalid_attached_count")
        attached_count = 0
    elif attached_count != context_count:
        failures.append("attached_count_context_count_mismatch")

    if step6.get("data_type") != EXPECTED_STEP6G_DATA_TYPE:
        failures.append("step6g_presentation_state_unavailable")
    if step6.get("graduated_production_active") is not True:
        failures.append("step6g_graduated_production_not_active")
    if step6.get("production_exposure_changed") is not False:
        failures.append("step6g_exposure_change_detected")
    if step6.get("same_step5_10_cohort") is not True:
        failures.append("step5_10_cohort_not_preserved")
    if step6.get("same_step5_9_gate") is not True:
        failures.append("step5_9_gate_not_preserved")
    if step6.get("exact_session_rollback") is not True:
        failures.append("exact_session_rollback_not_preserved")
    if step6.get("global_kill_switch_available") is not True:
        failures.append("global_kill_switch_not_preserved")
    if step6.get("player_props_passthrough") is not True:
        failures.append("player_prop_passthrough_not_preserved")
    for key in _PROTECTED_FALSE_FLAGS:
        if step6.get(key) is not False:
            failures.append(f"{key}_drift")

    active = not failures
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_status": API_CONNECTED if active else FALLBACK,
        "api_integration_active": active,
        "page_fallback_behavior_preserved": True,
        "source": EXPECTED_SOURCE,
        "api_data_type": live.get("api_data_type"),
        "collected_at_utc": live.get("collected_at_utc"),
        "match_method": EXPECTED_MATCH_METHOD,
        "fallback_matching_used": False,
        "attached_game_count": int(attached_count or 0),
        "context_game_count": context_count,
        "step6g_preserved": not any(item.startswith("step6g_") for item in failures),
        "production_exposure_changed": False,
        "same_step5_10_cohort": step6.get("same_step5_10_cohort") is True,
        "same_step5_9_gate": step6.get("same_step5_9_gate") is True,
        "exact_session_rollback": step6.get("exact_session_rollback") is True,
        "global_kill_switch_available": step6.get("global_kill_switch_available") is True,
        "player_props_passthrough": step6.get("player_props_passthrough") is True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
        "failures": failures,
    }


__all__ = [
    "API_CONNECTED",
    "DATA_TYPE",
    "FALLBACK",
    "SCHEMA_VERSION",
    "evaluate_daily_game_picks_api_integration",
]
