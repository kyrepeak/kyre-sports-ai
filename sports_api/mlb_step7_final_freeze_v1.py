"""MLB Step 7F final API-integration freeze attestation.

Step 7F is deliberately non-behavioral. It records the certified Step 7A-7E
API integration chain and provides a pure validation boundary for the final MLB
full-game API presentation state. It does not fetch data, mutate runtime state,
change projection/model math, alter simulation/probability/ranking/selection,
change sportsbook pricing inputs, persist data, place wagers, change production
exposure, or affect WNBA behavior.
"""
from __future__ import annotations

from typing import Any, Iterable

DATA_TYPE = "mlb_step7_final_freeze_v1"
SCHEMA_VERSION = 1
STEP7F_BASE_MAIN_SHA = "918a0ea3abf6c79d15ff6eac1654e7e5a1e773cc"
FINAL_FREEZE_STATUS = "STEP7_FROZEN_API_INTEGRATION_COMPLETE"
FINAL_CERTIFICATION_MARKER = "MLB_STEP7F_FINAL_API_INTEGRATION_FREEZE_GREEN"

STEP7_STAGE_CHAIN = (
    "7A_DAILY_GAME_PICKS_API_INTEGRATION",
    "7B_SPREAD_API_INTEGRATION",
    "7C_MONEYLINE_API_INTEGRATION",
    "7D_GAME_TOTAL_API_INTEGRATION",
    "7E_GAME_TOTAL_PRESENTATION_INTEGRATION",
)

STEP7_CERTIFICATION_MARKERS = (
    "MLB_STEP7A_DAILY_GAME_PICKS_API_INTEGRATION_GREEN",
    "MLB_STEP7B_SPREAD_API_INTEGRATION_GREEN",
    "MLB_STEP7C_MONEYLINE_API_INTEGRATION_GREEN",
    "MLB_STEP7D_GAME_TOTAL_API_INTEGRATION_GREEN",
    "MLB_STEP7E_GAME_TOTAL_PRESENTATION_INTEGRATION_GREEN",
)

STEP7_MERGED_PULL_REQUESTS = (24, 25, 26, 27, 28)

PROTECTED_INVARIANTS = {
    "model_math_impact": False,
    "simulation_impact": False,
    "probability_impact": False,
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


def validate_final_step7_certification(
    observed_markers: Iterable[Any] | None,
    *,
    runtime_base_sha: str | None,
) -> dict[str, Any]:
    """Validate the final Step 7 certification evidence without changing runtime."""
    observed = _marker_list(observed_markers)
    expected = list(STEP7_CERTIFICATION_MARKERS)
    observed_set = set(observed)
    expected_set = set(expected)

    failures: list[str] = []
    missing = [marker for marker in expected if marker not in observed_set]
    unexpected = [marker for marker in observed if marker not in expected_set]
    duplicates = sorted({marker for marker in observed if observed.count(marker) > 1})

    if str(runtime_base_sha or "") != STEP7F_BASE_MAIN_SHA:
        failures.append("STEP7F_RUNTIME_BASE_SHA_MISMATCH")
    if missing:
        failures.append("STEP7_CERTIFICATION_MARKERS_MISSING")
    if unexpected:
        failures.append("STEP7_UNEXPECTED_CERTIFICATION_MARKERS")
    if duplicates:
        failures.append("STEP7_DUPLICATE_CERTIFICATION_MARKERS")
    if len(observed) != len(expected):
        failures.append("STEP7_CERTIFICATION_MARKER_COUNT_MISMATCH")

    failures = list(dict.fromkeys(failures))
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "freeze_status": FINAL_FREEZE_STATUS if not failures else "STEP7_FREEZE_REJECTED",
        "freeze_eligible": not failures,
        "step7f_base_main_sha": STEP7F_BASE_MAIN_SHA,
        "runtime_base_sha": str(runtime_base_sha or ""),
        "stage_chain": list(STEP7_STAGE_CHAIN),
        "expected_certification_markers": expected,
        "observed_certification_markers": observed,
        "missing_certification_markers": missing,
        "unexpected_certification_markers": unexpected,
        "duplicate_certification_markers": duplicates,
        "merged_pull_requests": list(STEP7_MERGED_PULL_REQUESTS),
        "failures": failures,
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step7f": False,
        "exact_official_game_id_required": True,
        "fuzzy_matching_allowed": False,
        "stale_market_context_allowed": False,
        "missing_market_price_fabrication_allowed": False,
        "step6_frozen_state_required": True,
        **PROTECTED_INVARIANTS,
    }


def final_freeze_manifest() -> dict[str, Any]:
    """Return the immutable final Step 7 freeze contract."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step7f_base_main_sha": STEP7F_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "stage_chain": list(STEP7_STAGE_CHAIN),
        "certification_markers": list(STEP7_CERTIFICATION_MARKERS),
        "merged_pull_requests": list(STEP7_MERGED_PULL_REQUESTS),
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step7f": False,
        "exact_official_game_id_required": True,
        "fuzzy_matching_allowed": False,
        "stale_market_context_allowed": False,
        "missing_market_price_fabrication_allowed": False,
        "step6_frozen_state_required": True,
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP7F_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "STEP7_STAGE_CHAIN",
    "STEP7_CERTIFICATION_MARKERS",
    "STEP7_MERGED_PULL_REQUESTS",
    "PROTECTED_INVARIANTS",
    "validate_final_step7_certification",
    "final_freeze_manifest",
]
