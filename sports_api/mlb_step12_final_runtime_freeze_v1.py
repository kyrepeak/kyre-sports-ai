"""MLB Step 12D — final shadow-runtime freeze and future activation boundary.

Steps 12A-12C established the deterministic shadow runtime cycle, exact-game
live assembly, and consumer-shaped observational live board. Step 12D is
intentionally non-behavioral: it freezes that complete runtime block without
making any board row actionable, activating DraftKings, enabling production
consensus/failover, changing persistence, or wiring any new production path.

A later step may schedule or activate this runtime only after satisfying the
explicit requirements recorded here. Nothing in this module performs network
I/O, writes persistence, or changes frozen model/sportsbook inputs.
"""
from __future__ import annotations

from typing import Any, Mapping

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11_final_provider_expansion_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP11_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP11_FINAL_FREEZE_STATUS,
    final_provider_expansion_freeze_manifest,
)
from sports_api.mlb_step12a_shadow_runtime_runner_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12A_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP12A_RUNTIME_MODE,
    RUNTIME_STATUS as STEP12A_RUNTIME_STATUS,
    shadow_runtime_manifest,
)
from sports_api.mlb_step12b_live_runtime_assembly_v1 import (
    ASSEMBLY_STATUS as STEP12B_ASSEMBLY_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP12B_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP12B_RUNTIME_MODE,
    live_runtime_assembly_manifest,
)
from sports_api.mlb_step12c_live_board_runtime_v1 import (
    BOARD_STATUS as STEP12C_BOARD_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP12C_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP12C_RUNTIME_MODE,
    live_board_runtime_manifest,
)

DATA_TYPE = "mlb_step12_final_runtime_freeze_v1"
SCHEMA_VERSION = 1
STEP12D_BASE_MAIN_SHA = "fc3eacbda9162cf1bd0abd6ec30c6368a9df767b"
FINAL_FREEZE_STATUS = "STEP12_FROZEN_SHADOW_RUNTIME_COMPLETE"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP12D_FINAL_RUNTIME_FREEZE_GREEN"

STEP12_STAGE_CHAIN = (
    "12A_DETERMINISTIC_SHADOW_RUNTIME_RUNNER",
    "12B_EXACT_GAME_LIVE_RUNTIME_ASSEMBLY",
    "12C_DETERMINISTIC_LIVE_BOARD_RUNTIME",
)

STEP12_CERTIFICATION_MARKERS = (
    STEP12A_FINAL_CERTIFICATION_MARKER,
    STEP12B_FINAL_CERTIFICATION_MARKER,
    STEP12C_FINAL_CERTIFICATION_MARKER,
)

FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS = (
    "explicit_future_activation_step_required",
    "bounded_scheduler_or_supervisor_required_before_always_on_runtime",
    "verified_live_secondary_provider_endpoint_required_before_secondary_network_calls",
    "exact_secondary_provider_event_to_official_gamepk_map_required",
    "exact_official_game_id_join_required",
    "freshness_gate_required",
    "source_complete_gate_required",
    "same_line_required_for_run_line_total_consensus",
    "no_price_fabrication_required",
    "bounded_failure_isolation_required",
    "provider_disable_or_rollback_switch_required",
    "shadow_evidence_window_required",
    "production_smoke_certification_required",
)


def final_runtime_freeze_manifest() -> dict[str, Any]:
    """Return the immutable Step 12 final runtime freeze boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step12d_base_main_sha": STEP12D_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step11_final_freeze_status_required": STEP11_FINAL_FREEZE_STATUS,
        "step11_final_certification_marker_required": STEP11_FINAL_CERTIFICATION_MARKER,
        "step12_stage_chain": list(STEP12_STAGE_CHAIN),
        "step12_certification_markers": list(STEP12_CERTIFICATION_MARKERS),
        "step12a_runtime_status_required": STEP12A_RUNTIME_STATUS,
        "step12a_runtime_mode_required": STEP12A_RUNTIME_MODE,
        "step12b_assembly_status_required": STEP12B_ASSEMBLY_STATUS,
        "step12b_runtime_mode_required": STEP12B_RUNTIME_MODE,
        "step12c_board_status_required": STEP12C_BOARD_STATUS,
        "step12c_runtime_mode_required": STEP12C_RUNTIME_MODE,
        "runtime_block_frozen": True,
        "step12a_shadow_runtime_frozen": True,
        "step12b_exact_game_assembly_frozen": True,
        "step12c_live_board_runtime_frozen": True,
        "deterministic_runtime_required": True,
        "exact_official_game_id_required": True,
        "freshness_gate_required": True,
        "source_complete_gate_required": True,
        "same_line_required_for_run_line_total_consensus": True,
        "observational_only": True,
        "actionable_output_enabled": False,
        "live_secondary_provider_network_calls_enabled": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "network_io_added_by_step12d": False,
        "production_api_wiring_added_by_step12d": False,
        "production_runtime_wiring_added_by_step12d": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step12d": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "shadow_output_as_model_input_allowed": False,
        "shadow_output_as_sportsbook_input_allowed": False,
        "live_board_as_model_input_allowed": False,
        "live_board_as_sportsbook_input_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        "production_activation_allowed_by_step12d": False,
        "explicit_future_activation_step_required": True,
        "future_runtime_activation_requirements": list(FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS),
        **PROTECTED_INVARIANTS,
    }


def validate_final_runtime_freeze(
    *,
    step11_manifest: Mapping[str, Any] | None,
    step12a_manifest: Mapping[str, Any] | None,
    step12b_manifest: Mapping[str, Any] | None,
    step12c_manifest: Mapping[str, Any] | None,
    shadow_runtime_evidence_ok: bool,
    exact_game_assembly_evidence_ok: bool,
    live_board_evidence_ok: bool,
    zero_actionable_rows_ok: bool,
    zero_live_secondary_provider_calls_ok: bool,
    zero_price_fabrication_ok: bool,
    zero_production_consensus_failover_ok: bool,
    zero_production_runtime_changes_ok: bool,
    zero_production_database_writes_ok: bool,
) -> dict[str, Any]:
    """Fail closed unless the entire frozen Step 12 chain is exact and green."""
    failures: list[str] = []

    if step11_manifest != final_provider_expansion_freeze_manifest():
        failures.append("STEP12D_STEP11_FINAL_FREEZE_MANIFEST_MISMATCH")
    if step12a_manifest != shadow_runtime_manifest():
        failures.append("STEP12D_STEP12A_MANIFEST_MISMATCH")
    if step12b_manifest != live_runtime_assembly_manifest():
        failures.append("STEP12D_STEP12B_MANIFEST_MISMATCH")
    if step12c_manifest != live_board_runtime_manifest():
        failures.append("STEP12D_STEP12C_MANIFEST_MISMATCH")

    evidence = {
        "shadow_runtime_evidence_ok": shadow_runtime_evidence_ok,
        "exact_game_assembly_evidence_ok": exact_game_assembly_evidence_ok,
        "live_board_evidence_ok": live_board_evidence_ok,
        "zero_actionable_rows_ok": zero_actionable_rows_ok,
        "zero_live_secondary_provider_calls_ok": zero_live_secondary_provider_calls_ok,
        "zero_price_fabrication_ok": zero_price_fabrication_ok,
        "zero_production_consensus_failover_ok": zero_production_consensus_failover_ok,
        "zero_production_runtime_changes_ok": zero_production_runtime_changes_ok,
        "zero_production_database_writes_ok": zero_production_database_writes_ok,
    }
    for field, value in evidence.items():
        if value is not True:
            failures.append(f"STEP12D_{field.upper()}_NOT_GREEN")

    result = final_runtime_freeze_manifest()
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
    "STEP12D_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "STEP12_STAGE_CHAIN",
    "STEP12_CERTIFICATION_MARKERS",
    "FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS",
    "final_runtime_freeze_manifest",
    "validate_final_runtime_freeze",
]
