"""MLB Step 11E — final provider-expansion freeze and activation boundary.

Steps 11A-11D established the provider-neutral market contract, shadow-only
DraftKings adapter, deterministic two-provider comparison board, and the
shadow consensus/failover policy. Step 11E is deliberately non-behavioral: it
freezes that complete provider-expansion block without activating DraftKings,
consensus, failover, best-price selection, or any new production runtime path.

A later step may activate a secondary provider only after satisfying the
explicit future-activation requirements recorded here. Nothing in this module
performs network I/O, writes persistence, or changes frozen model inputs.
"""
from __future__ import annotations

from typing import Any, Mapping

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP10_FINAL_FREEZE_STATUS,
    final_persistence_freeze_manifest,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    CONTRACT_STATUS as STEP11A_CONTRACT_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11A_FINAL_CERTIFICATION_MARKER,
    provider_contract_manifest,
)
from sports_api.collectors.mlb_draftkings_provider import (
    ADAPTER_STATUS as STEP11B_ADAPTER_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11B_FINAL_CERTIFICATION_MARKER,
    adapter_manifest as draftkings_adapter_manifest,
)
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import (
    BOARD_STATUS as STEP11C_BOARD_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11C_FINAL_CERTIFICATION_MARKER,
    SUPPORTED_PROVIDERS,
    shadow_board_manifest,
)
from sports_api.mlb_step11d_provider_consensus_failover_shadow_policy_v1 import (
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_PRIMARY_PROVIDER,
    FINAL_CERTIFICATION_MARKER as STEP11D_FINAL_CERTIFICATION_MARKER,
    POLICY_STATUS as STEP11D_POLICY_STATUS,
    policy_manifest,
)

DATA_TYPE = "mlb_step11_final_provider_expansion_freeze_v1"
SCHEMA_VERSION = 1
STEP11E_BASE_MAIN_SHA = "9559b6d98ff1193051ea064060db21d13d5428e6"
FINAL_FREEZE_STATUS = "STEP11_FROZEN_MULTI_PROVIDER_EXPANSION_COMPLETE"
FINAL_CERTIFICATION_MARKER = "MLB_STEP11E_FINAL_PROVIDER_EXPANSION_FREEZE_GREEN"

STEP11_STAGE_CHAIN = (
    "11A_PROVIDER_NEUTRAL_CORE_MARKET_CONTRACT",
    "11B_DRAFTKINGS_SHADOW_PROVIDER_ADAPTER",
    "11C_MULTI_PROVIDER_SHADOW_BOARD",
    "11D_PROVIDER_CONSENSUS_FAILOVER_SHADOW_POLICY",
)

STEP11_CERTIFICATION_MARKERS = (
    STEP11A_FINAL_CERTIFICATION_MARKER,
    STEP11B_FINAL_CERTIFICATION_MARKER,
    STEP11C_FINAL_CERTIFICATION_MARKER,
    STEP11D_FINAL_CERTIFICATION_MARKER,
)

FUTURE_ACTIVATION_REQUIREMENTS = (
    "explicit_future_activation_step_required",
    "verified_live_secondary_provider_endpoint_required",
    "exact_secondary_provider_event_to_official_gamepk_map_required",
    "freshness_gate_required",
    "source_complete_gate_required",
    "no_price_fabrication_required",
    "same_line_required_for_run_line_total_consensus",
    "bounded_failure_isolation_required",
    "provider_disable_or_rollback_switch_required",
    "shadow_evidence_window_required",
    "production_smoke_certification_required",
)


def final_provider_expansion_freeze_manifest() -> dict[str, Any]:
    """Return the immutable Step 11 provider-expansion freeze boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step11e_base_main_sha": STEP11E_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step10_final_freeze_status_required": STEP10_FINAL_FREEZE_STATUS,
        "step10_final_certification_marker_required": STEP10_FINAL_CERTIFICATION_MARKER,
        "step11_stage_chain": list(STEP11_STAGE_CHAIN),
        "step11_certification_markers": list(STEP11_CERTIFICATION_MARKERS),
        "step11a_contract_status_required": STEP11A_CONTRACT_STATUS,
        "step11b_adapter_status_required": STEP11B_ADAPTER_STATUS,
        "step11c_board_status_required": STEP11C_BOARD_STATUS,
        "step11d_policy_status_required": STEP11D_POLICY_STATUS,
        "supported_providers": list(SUPPORTED_PROVIDERS),
        "primary_provider": DEFAULT_PRIMARY_PROVIDER,
        "fallback_provider": DEFAULT_FALLBACK_PROVIDER,
        "provider_expansion_block_frozen": True,
        "step11a_provider_contract_frozen": True,
        "step11b_draftkings_adapter_frozen": True,
        "step11c_shadow_board_frozen": True,
        "step11d_consensus_failover_policy_frozen": True,
        "exact_official_game_id_required": True,
        "exact_secondary_provider_event_map_required": True,
        "freshness_required": True,
        "source_complete_required": True,
        "same_line_required_for_run_line_total_consensus": True,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "live_secondary_provider_network_calls_enabled": False,
        "network_io_added_by_step11e": False,
        "production_api_wiring_added_by_step11e": False,
        "production_runtime_wiring_added_by_step11e": False,
        "persistence_schema_changed_by_step11e": False,
        "production_database_writes_enabled": False,
        "consensus_as_model_input_allowed": False,
        "shadow_route_as_model_input_allowed": False,
        "shadow_route_as_sportsbook_input_allowed": False,
        "production_activation_allowed_by_step11e": False,
        "explicit_future_activation_step_required": True,
        "future_activation_requirements": list(FUTURE_ACTIVATION_REQUIREMENTS),
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def validate_final_provider_expansion_freeze(
    *,
    step10_manifest: Mapping[str, Any] | None,
    step11a_manifest: Mapping[str, Any] | None,
    step11b_manifest: Mapping[str, Any] | None,
    step11c_manifest: Mapping[str, Any] | None,
    step11d_manifest: Mapping[str, Any] | None,
    provider_contract_evidence_ok: bool,
    draftkings_adapter_evidence_ok: bool,
    shadow_board_evidence_ok: bool,
    consensus_failover_shadow_evidence_ok: bool,
    zero_live_secondary_provider_calls_ok: bool,
    zero_price_fabrication_ok: bool,
    zero_production_consensus_failover_ok: bool,
    zero_production_runtime_changes_ok: bool,
    zero_production_database_writes_ok: bool,
) -> dict[str, Any]:
    """Fail closed unless the complete frozen Step 11 chain is exact and green."""
    failures: list[str] = []

    if step10_manifest != final_persistence_freeze_manifest():
        failures.append("STEP11E_STEP10_FINAL_FREEZE_MANIFEST_MISMATCH")
    if step11a_manifest != provider_contract_manifest():
        failures.append("STEP11E_STEP11A_MANIFEST_MISMATCH")
    if step11b_manifest != draftkings_adapter_manifest():
        failures.append("STEP11E_STEP11B_MANIFEST_MISMATCH")
    if step11c_manifest != shadow_board_manifest():
        failures.append("STEP11E_STEP11C_MANIFEST_MISMATCH")
    if step11d_manifest != policy_manifest():
        failures.append("STEP11E_STEP11D_MANIFEST_MISMATCH")

    evidence = {
        "provider_contract_evidence_ok": provider_contract_evidence_ok,
        "draftkings_adapter_evidence_ok": draftkings_adapter_evidence_ok,
        "shadow_board_evidence_ok": shadow_board_evidence_ok,
        "consensus_failover_shadow_evidence_ok": consensus_failover_shadow_evidence_ok,
        "zero_live_secondary_provider_calls_ok": zero_live_secondary_provider_calls_ok,
        "zero_price_fabrication_ok": zero_price_fabrication_ok,
        "zero_production_consensus_failover_ok": zero_production_consensus_failover_ok,
        "zero_production_runtime_changes_ok": zero_production_runtime_changes_ok,
        "zero_production_database_writes_ok": zero_production_database_writes_ok,
    }
    for field, value in evidence.items():
        if value is not True:
            failures.append(f"STEP11E_{field.upper()}_NOT_GREEN")

    result = final_provider_expansion_freeze_manifest()
    result.update(
        {
            "freeze_valid": not failures,
            "failures": failures,
            **{field: value is True for field, value in evidence.items()},
        }
    )
    return result


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP11E_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "STEP11_STAGE_CHAIN",
    "STEP11_CERTIFICATION_MARKERS",
    "FUTURE_ACTIVATION_REQUIREMENTS",
    "final_provider_expansion_freeze_manifest",
    "validate_final_provider_expansion_freeze",
]
