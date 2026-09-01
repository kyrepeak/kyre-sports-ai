"""MLB Step 9F — final live API/consumer integration freeze attestation.

Step 9F is deliberately non-behavioral. It records the certified Step 9A-9E
live-game-state and live-market API/consumer chain and provides a pure validation
boundary for that frozen state. It does not fetch data, mutate runtime state,
change model/projection math, alter simulation/probability/run expectancy/edge
math, change sportsbook inputs, persist data, place wagers, change production
exposure, or affect WNBA behavior.
"""
from __future__ import annotations

from typing import Any, Iterable

DATA_TYPE = "mlb_step9_final_freeze_v1"
SCHEMA_VERSION = 1
STEP9F_BASE_MAIN_SHA = "fa33eaaeb8004d8090c540757a4f38bf507c578e"
FINAL_FREEZE_STATUS = "STEP9_FROZEN_LIVE_API_CONSUMER_INTEGRATION_COMPLETE"
FINAL_CERTIFICATION_MARKER = "MLB_STEP9F_FINAL_LIVE_INTEGRATION_FREEZE_GREEN"

STEP9_STAGE_CHAIN = (
    "9A_LIVE_GAME_STATE_API_CONTRACT",
    "9B_LIVE_GAME_STATE_COLLECTOR_API",
    "9C_LIVE_STATE_CONSUMER_INTEGRATION",
    "9D_LIVE_INPLAY_MARKET_COLLECTOR_API",
    "9E_LIVE_MARKET_CONSUMER_INTEGRATION",
)

STEP9_CERTIFICATION_MARKERS = (
    "MLB_STEP9A_LIVE_GAME_STATE_API_CONTRACT_GREEN",
    "MLB_STEP9B_LIVE_GAME_STATE_COLLECTOR_API_GREEN",
    "MLB_STEP9C_LIVE_STATE_CONSUMER_GREEN",
    "MLB_STEP9D_LIVE_INPLAY_MARKET_COLLECTOR_API_GREEN",
    "MLB_STEP9E_LIVE_MARKET_CONSUMER_GREEN",
)

STEP9_MERGED_PULL_REQUESTS = (37, 38, 39, 40, 41)

PROTECTED_INVARIANTS = {
    "model_math_impact": False,
    "projection_impact": False,
    "simulation_math_impact": False,
    "probability_math_impact": False,
    "run_expectancy_math_impact": False,
    "line_grading_impact": False,
    "edge_grading_math_impact": False,
    "history_adjustment_impact": False,
    "ranking_impact": False,
    "selection_impact": False,
    "fair_odds_impact": False,
    "sportsbook_price_model_input": False,
    "production_exposure_impact": False,
    "wagering_impact": False,
    "durable_persistence": False,
    "wnba_impact": False,
}


def _marker_list(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    try:
        return [str(value) for value in values]
    except TypeError:
        return []


def validate_final_step9_certification(
    observed_markers: Iterable[Any] | None,
    *,
    runtime_base_sha: str | None,
) -> dict[str, Any]:
    """Validate final Step 9 evidence without changing any runtime behavior."""
    observed = _marker_list(observed_markers)
    expected = list(STEP9_CERTIFICATION_MARKERS)
    observed_set = set(observed)
    expected_set = set(expected)

    failures: list[str] = []
    missing = [marker for marker in expected if marker not in observed_set]
    unexpected = [marker for marker in observed if marker not in expected_set]
    duplicates = sorted({marker for marker in observed if observed.count(marker) > 1})

    if str(runtime_base_sha or "") != STEP9F_BASE_MAIN_SHA:
        failures.append("STEP9F_RUNTIME_BASE_SHA_MISMATCH")
    if missing:
        failures.append("STEP9_CERTIFICATION_MARKERS_MISSING")
    if unexpected:
        failures.append("STEP9_UNEXPECTED_CERTIFICATION_MARKERS")
    if duplicates:
        failures.append("STEP9_DUPLICATE_CERTIFICATION_MARKERS")
    if len(observed) != len(expected):
        failures.append("STEP9_CERTIFICATION_MARKER_COUNT_MISMATCH")

    failures = list(dict.fromkeys(failures))
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "freeze_status": FINAL_FREEZE_STATUS if not failures else "STEP9_FREEZE_REJECTED",
        "freeze_eligible": not failures,
        "step9f_base_main_sha": STEP9F_BASE_MAIN_SHA,
        "runtime_base_sha": str(runtime_base_sha or ""),
        "stage_chain": list(STEP9_STAGE_CHAIN),
        "expected_certification_markers": expected,
        "observed_certification_markers": observed,
        "missing_certification_markers": missing,
        "unexpected_certification_markers": unexpected,
        "duplicate_certification_markers": duplicates,
        "merged_pull_requests": list(STEP9_MERGED_PULL_REQUESTS),
        "failures": failures,
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step9f": False,
        "exact_official_game_id_required": True,
        "team_name_matching_allowed": False,
        "player_name_matching_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "stale_live_state_context_allowed": False,
        "stale_live_market_context_allowed": False,
        "missing_live_market_price_fabrication_allowed": False,
        "provider_contract_unavailable_may_fall_back": True,
        "legacy_direct_live_state_fallback_preserved": True,
        "legacy_odds_api_io_fallback_preserved": True,
        "live_game_state_api_first": True,
        "live_market_api_first": True,
        "v1922_market_sync_function_preserved": True,
        "step8_final_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


def final_freeze_manifest() -> dict[str, Any]:
    """Return the immutable final Step 9 freeze contract."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step9f_base_main_sha": STEP9F_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "stage_chain": list(STEP9_STAGE_CHAIN),
        "certification_markers": list(STEP9_CERTIFICATION_MARKERS),
        "merged_pull_requests": list(STEP9_MERGED_PULL_REQUESTS),
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step9f": False,
        "exact_official_game_id_required": True,
        "team_name_matching_allowed": False,
        "player_name_matching_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "stale_live_state_context_allowed": False,
        "stale_live_market_context_allowed": False,
        "missing_live_market_price_fabrication_allowed": False,
        "provider_contract_unavailable_may_fall_back": True,
        "legacy_direct_live_state_fallback_preserved": True,
        "legacy_odds_api_io_fallback_preserved": True,
        "live_game_state_api_first": True,
        "live_market_api_first": True,
        "v1922_market_sync_function_preserved": True,
        "step8_final_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP9F_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "STEP9_STAGE_CHAIN",
    "STEP9_CERTIFICATION_MARKERS",
    "STEP9_MERGED_PULL_REQUESTS",
    "PROTECTED_INVARIANTS",
    "validate_final_step9_certification",
    "final_freeze_manifest",
]
