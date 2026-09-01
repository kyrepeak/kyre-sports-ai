"""MLB Step 10D — final persistence/recovery freeze and activation boundary.

Steps 10A-10C established the durable snapshot contract, append-only SQLite
adapter, and read-only restart recovery verifier. Step 10D is deliberately
non-behavioral: it freezes those persistence guarantees and defines the exact
conditions a later production-activation step must satisfy before automatic
writes may ever be enabled.

Nothing in this module writes to a database or feeds persisted snapshots back
into the frozen MLB model/runtime.
"""
from __future__ import annotations

from typing import Any, Mapping

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    CONTRACT_STATUS as STEP10A_CONTRACT_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP10A_FINAL_CERTIFICATION_MARKER,
    persistence_contract_manifest,
)
from sports_api.database.mlb_live_snapshot_store import (
    ADAPTER_STATUS as STEP10B_ADAPTER_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP10B_FINAL_CERTIFICATION_MARKER,
    adapter_manifest,
)
from sports_api.database.mlb_live_snapshot_recovery import (
    FINAL_CERTIFICATION_MARKER as STEP10C_FINAL_CERTIFICATION_MARKER,
    RECOVERY_STATUS as STEP10C_RECOVERY_STATUS,
    recovery_manifest,
)

DATA_TYPE = "mlb_step10_final_persistence_freeze_v1"
SCHEMA_VERSION = 1
STEP10D_BASE_MAIN_SHA = "a043c6a1cd0a68540332f01da15f350d3fb2b0b9"
FINAL_FREEZE_STATUS = "STEP10_FROZEN_DURABLE_PERSISTENCE_RECOVERY_COMPLETE"
FINAL_CERTIFICATION_MARKER = "MLB_STEP10D_FINAL_PERSISTENCE_RECOVERY_FREEZE_GREEN"

STEP10_STAGE_CHAIN = (
    "10A_DURABLE_LIVE_SNAPSHOT_PERSISTENCE_CONTRACT",
    "10B_APPEND_ONLY_LIVE_SNAPSHOT_STORE",
    "10C_DURABLE_RESTART_RECOVERY",
)

STEP10_CERTIFICATION_MARKERS = (
    STEP10A_FINAL_CERTIFICATION_MARKER,
    STEP10B_FINAL_CERTIFICATION_MARKER,
    STEP10C_FINAL_CERTIFICATION_MARKER,
)

ACTIVATION_REQUIREMENTS = (
    "explicit_future_activation_step_required",
    "durable_storage_path_or_managed_database_required",
    "startup_recovery_verification_required",
    "append_only_guards_required",
    "payload_sha256_verification_required",
    "exact_official_game_id_identity_required",
    "no_fabricated_market_records_required",
    "bounded_failure_isolation_required",
    "rollback_or_disable_switch_required",
    "production_smoke_certification_required",
)


def final_persistence_freeze_manifest() -> dict[str, Any]:
    """Return the immutable Step 10D freeze and future-activation boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step10d_base_main_sha": STEP10D_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step10_stage_chain": list(STEP10_STAGE_CHAIN),
        "step10_certification_markers": list(STEP10_CERTIFICATION_MARKERS),
        "step10a_contract_status_required": STEP10A_CONTRACT_STATUS,
        "step10b_adapter_status_required": STEP10B_ADAPTER_STATUS,
        "step10c_recovery_status_required": STEP10C_RECOVERY_STATUS,
        "persistence_block_frozen": True,
        "step10a_contract_frozen": True,
        "step10b_adapter_frozen": True,
        "step10c_recovery_frozen": True,
        "append_only_required": True,
        "update_allowed": False,
        "upsert_allowed": False,
        "delete_allowed": False,
        "backfill_fabrication_allowed": False,
        "restart_recovery_required": True,
        "read_only_recovery_required": True,
        "sqlite_integrity_check_required": True,
        "payload_sha256_reverification_required": True,
        "production_runtime_wiring_added_by_step10d": False,
        "automatic_production_writes_enabled": False,
        "production_activation_allowed_by_step10d": False,
        "explicit_future_activation_step_required": True,
        "activation_requirements": list(ACTIVATION_REQUIREMENTS),
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def validate_final_persistence_freeze(
    *,
    step10a_manifest: Mapping[str, Any] | None,
    step10b_manifest: Mapping[str, Any] | None,
    step10c_manifest: Mapping[str, Any] | None,
    append_only_evidence_ok: bool,
    restart_recovery_evidence_ok: bool,
    zero_production_writes_ok: bool,
) -> dict[str, Any]:
    """Fail closed unless all frozen Step 10 prerequisites are exact and green."""
    failures: list[str] = []

    if step10a_manifest != persistence_contract_manifest():
        failures.append("STEP10D_STEP10A_MANIFEST_MISMATCH")
    if step10b_manifest != adapter_manifest():
        failures.append("STEP10D_STEP10B_MANIFEST_MISMATCH")
    if step10c_manifest != recovery_manifest():
        failures.append("STEP10D_STEP10C_MANIFEST_MISMATCH")
    if append_only_evidence_ok is not True:
        failures.append("STEP10D_APPEND_ONLY_EVIDENCE_NOT_GREEN")
    if restart_recovery_evidence_ok is not True:
        failures.append("STEP10D_RESTART_RECOVERY_EVIDENCE_NOT_GREEN")
    if zero_production_writes_ok is not True:
        failures.append("STEP10D_ZERO_PRODUCTION_WRITES_NOT_GREEN")

    result = final_persistence_freeze_manifest()
    result.update(
        {
            "freeze_valid": not failures,
            "failures": failures,
            "append_only_evidence_ok": append_only_evidence_ok is True,
            "restart_recovery_evidence_ok": restart_recovery_evidence_ok is True,
            "zero_production_writes_ok": zero_production_writes_ok is True,
        }
    )
    return result


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP10D_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "STEP10_STAGE_CHAIN",
    "STEP10_CERTIFICATION_MARKERS",
    "ACTIVATION_REQUIREMENTS",
    "final_persistence_freeze_manifest",
    "validate_final_persistence_freeze",
]
