"""MLB Step 8G — final player-prop integration freeze attestation.

Step 8G is deliberately non-behavioral. It records the certified Step 8A-8F
player-prop API/integration/presentation chain and provides a pure validation
boundary for that frozen state. It does not fetch data, mutate runtime state,
change model/projection math, alter simulation/probability/ranking/selection,
turn sportsbook evidence into a model input, persist data, place wagers, change
production exposure, or affect WNBA behavior.
"""
from __future__ import annotations

from typing import Any, Iterable

DATA_TYPE = "mlb_step8_final_freeze_v1"
SCHEMA_VERSION = 1
STEP8G_BASE_MAIN_SHA = "ac38a6a783d9b10933ddcff620782c3daf74d6c2"
FINAL_FREEZE_STATUS = "STEP8_FROZEN_PLAYER_PROP_INTEGRATION_COMPLETE"
FINAL_CERTIFICATION_MARKER = "MLB_STEP8G_FINAL_PLAYER_PROP_FREEZE_GREEN"

STEP8_STAGE_CHAIN = (
    "8A_PLAYER_PROP_API_CONTRACT",
    "8B_FANDUEL_PLAYER_PROP_COLLECTOR_API",
    "8C_PITCHER_STRIKEOUTS_INTEGRATION",
    "8D_PLAYER_HITS_INTEGRATION",
    "8E_HITS_RUNS_RBI_INTEGRATION",
    "8F_PLAYER_PROP_PRESENTATION_INTEGRATION",
)

STEP8_CERTIFICATION_MARKERS = (
    "MLB_STEP8A_PLAYER_PROP_API_CONTRACT_GREEN",
    "MLB_STEP8B_FANDUEL_PLAYER_PROP_COLLECTOR_API_GREEN",
    "MLB_STEP8C_PITCHER_STRIKEOUTS_INTEGRATION_GREEN",
    "MLB_STEP8D_PLAYER_HITS_INTEGRATION_GREEN",
    "MLB_STEP8E_HITS_RUNS_RBI_INTEGRATION_GREEN",
    "MLB_STEP8F_PLAYER_PROP_PRESENTATION_GREEN",
)

STEP8_MERGED_PULL_REQUESTS = (30, 31, 32, 33, 34, 35)

PROTECTED_INVARIANTS = {
    "model_math_impact": False,
    "projection_impact": False,
    "simulation_impact": False,
    "probability_impact": False,
    "line_grading_impact": False,
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


def validate_final_step8_certification(
    observed_markers: Iterable[Any] | None,
    *,
    runtime_base_sha: str | None,
) -> dict[str, Any]:
    """Validate final Step 8 evidence without changing any runtime behavior."""
    observed = _marker_list(observed_markers)
    expected = list(STEP8_CERTIFICATION_MARKERS)
    observed_set = set(observed)
    expected_set = set(expected)

    failures: list[str] = []
    missing = [marker for marker in expected if marker not in observed_set]
    unexpected = [marker for marker in observed if marker not in expected_set]
    duplicates = sorted({marker for marker in observed if observed.count(marker) > 1})

    if str(runtime_base_sha or "") != STEP8G_BASE_MAIN_SHA:
        failures.append("STEP8G_RUNTIME_BASE_SHA_MISMATCH")
    if missing:
        failures.append("STEP8_CERTIFICATION_MARKERS_MISSING")
    if unexpected:
        failures.append("STEP8_UNEXPECTED_CERTIFICATION_MARKERS")
    if duplicates:
        failures.append("STEP8_DUPLICATE_CERTIFICATION_MARKERS")
    if len(observed) != len(expected):
        failures.append("STEP8_CERTIFICATION_MARKER_COUNT_MISMATCH")

    failures = list(dict.fromkeys(failures))
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "freeze_status": FINAL_FREEZE_STATUS if not failures else "STEP8_FREEZE_REJECTED",
        "freeze_eligible": not failures,
        "step8g_base_main_sha": STEP8G_BASE_MAIN_SHA,
        "runtime_base_sha": str(runtime_base_sha or ""),
        "stage_chain": list(STEP8_STAGE_CHAIN),
        "expected_certification_markers": expected,
        "observed_certification_markers": observed,
        "missing_certification_markers": missing,
        "unexpected_certification_markers": unexpected,
        "duplicate_certification_markers": duplicates,
        "merged_pull_requests": list(STEP8_MERGED_PULL_REQUESTS),
        "failures": failures,
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step8g": False,
        "exact_official_game_id_required": True,
        "exact_official_player_id_required": True,
        "canonical_market_type_required": True,
        "player_name_matching_allowed": False,
        "fuzzy_matching_allowed": False,
        "stale_player_prop_context_allowed": False,
        "missing_player_prop_price_fabrication_allowed": False,
        "provider_contract_unavailable_may_fail_open": True,
        "step7_final_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


def final_freeze_manifest() -> dict[str, Any]:
    """Return the immutable final Step 8 freeze contract."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step8g_base_main_sha": STEP8G_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "stage_chain": list(STEP8_STAGE_CHAIN),
        "certification_markers": list(STEP8_CERTIFICATION_MARKERS),
        "merged_pull_requests": list(STEP8_MERGED_PULL_REQUESTS),
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step8g": False,
        "exact_official_game_id_required": True,
        "exact_official_player_id_required": True,
        "canonical_market_type_required": True,
        "player_name_matching_allowed": False,
        "fuzzy_matching_allowed": False,
        "stale_player_prop_context_allowed": False,
        "missing_player_prop_price_fabrication_allowed": False,
        "provider_contract_unavailable_may_fail_open": True,
        "step7_final_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP8G_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "STEP8_STAGE_CHAIN",
    "STEP8_CERTIFICATION_MARKERS",
    "STEP8_MERGED_PULL_REQUESTS",
    "PROTECTED_INVARIANTS",
    "validate_final_step8_certification",
    "final_freeze_manifest",
]
