"""MLB Step 14A — durable scheduler/recovery persistence contract.

Step 13D froze the complete bounded scheduler, supervisor, and recovery-policy
block in SHADOW_ONLY mode. Step 14A defines the only durable checkpoint envelope
and relational schema that later Step-14 adapters may persist.

Step 14A performs no database reads or writes. It does not execute a runtime
cycle, retry, restart, mutate scheduler/recovery state, create a lease, spawn a
background worker, call a provider, or activate production. It only validates
caller-owned Step-13 state and produces a content-addressed checkpoint candidate.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import re
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step13_final_scheduler_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13D_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP13D_FINAL_FREEZE_STATUS,
    RUNTIME_MODE as STEP13D_RUNTIME_MODE,
    final_scheduler_freeze_manifest,
    validate_final_scheduler_freeze_manifest,
)
from sports_api.mlb_step13c_reliability_recovery_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13C_FINAL_CERTIFICATION_MARKER,
    RECOVERY_STATE_DATA_TYPE,
    RUNTIME_MODE as STEP13C_RUNTIME_MODE,
    validate_recovery_decision,
)

DATA_TYPE = "mlb_step14a_persistence_contract_v1"
ENVELOPE_DATA_TYPE = "mlb_step14a_checkpoint_envelope_v1"
SCHEMA_MANIFEST_DATA_TYPE = "mlb_step14a_persistence_schema_manifest_v1"
SCHEMA_VERSION = 1
STEP14A_BASE_MAIN_SHA = "e0c79e2ccb9e34846ed4499f29878853e7e1114a"
STEP13D_MERGE_SHA = STEP14A_BASE_MAIN_SHA
STEP13D_SOURCE_BLOB_SHA = "b53400fe205717ca075231f841b4ca7aabed90bc"
CONTRACT_ID = "mlb_step14a_scheduler_recovery_checkpoint_contract_2026_v1"
CONTRACT_STATUS = "STEP14A_PERSISTENCE_CONTRACT_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP14A_PERSISTENCE_CONTRACT_GREEN"

SEASON = 2026
SEASON_TYPE = "Regular Season"
DATABASE_DIALECT = "postgresql"
DATABASE_SCHEMA_NAME = "kyre_runtime"
CHECKPOINT_TABLE_NAME = "mlb_runtime_checkpoints"
CHECKPOINT_HEAD_TABLE_NAME = "mlb_runtime_checkpoint_heads"
SQL_SCHEMA_PATH = "sports_api/sql/mlb_step14a_persistence_schema.sql"

DEFAULT_ENABLED = False
DATABASE_SCHEMA_DEFINITION_ALLOWED = True
DURABLE_CHECKPOINT_ENVELOPE_ALLOWED = True
DATABASE_READ_ALLOWED = False
DATABASE_WRITE_ALLOWED = False
PERSISTENCE_RUNTIME_ENABLED = False
DURABLE_RESTART_RECOVERY_ALLOWED = False
DURABLE_DISTRIBUTED_LEASE_ALLOWED = False
CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_API_ACTIVATION_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False

_SCHEDULER_STATE_KEYS = {
    "last_granted_slot_utc",
    "active_cycle_id",
    "active_cycle_slot_utc",
}
_RECOVERY_HANDOFF_KEYS = {
    "supervision_state",
    "failure_code",
    "recovery_action",
    "recovery_reason",
    "retry_authorized",
    "restart_authorized",
    "scheduler_state_release_authorized",
    "stuck_cycle_release_authorized",
    "cooldown_required",
    "cooldown_seconds",
    "cooldown_until_utc",
    "recovery_attempt_number",
    "recovery_token_sha256",
}
_ENVELOPE_KEYS = {
    "data_type",
    "schema_version",
    "contract_id",
    "contract_status",
    "runtime_mode",
    "season",
    "season_type",
    "slate_date",
    "checkpoint_key",
    "step14a_base_main_sha",
    "step13d_merge_sha",
    "step13d_source_blob_sha",
    "step13d_final_certification_marker",
    "step13d_freeze_manifest_sha256",
    "source_step13c_final_certification_marker",
    "source_reliability_sha256",
    "source_supervision_sha256",
    "source_evaluated_at_utc",
    "scheduler_anchor_utc",
    "interval_seconds",
    "cycle_id",
    "cycle_slot_utc",
    "scheduler_state",
    "scheduler_state_sha256",
    "recovery_state",
    "recovery_state_sha256",
    "recovery_handoff",
    "recovery_handoff_sha256",
    "created_at_utc",
    "envelope_content_sha256",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_CYCLE_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class MLBStep14APersistenceContractError(ValueError):
    """Raised when a Step 14A checkpoint candidate fails closed."""


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _strict_json_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBStep14APersistenceContractError(f"{field} must be a mapping")
    try:
        raw = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        normalized = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise MLBStep14APersistenceContractError(
            f"{field} must be strict JSON-compatible"
        ) from exc
    if not isinstance(normalized, dict):
        raise MLBStep14APersistenceContractError(f"{field} must normalize to an object")
    return normalized


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z") or "T" not in value or " " in value:
        raise MLBStep14APersistenceContractError(
            f"{field} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBStep14APersistenceContractError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBStep14APersistenceContractError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _slate_date(value: Any) -> str:
    text = value.isoformat() if isinstance(value, date) else str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise MLBStep14APersistenceContractError(
            "slate_date must be YYYY-MM-DD"
        ) from exc
    if parsed.year != SEASON:
        raise MLBStep14APersistenceContractError(
            "Step 14A is certified only for the 2026 MLB season"
        )
    return parsed.isoformat()


def _valid_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise MLBStep14APersistenceContractError(
            f"{field} must be lowercase 64-character SHA-256 hex"
        )
    return value


def _step13d_manifest() -> dict[str, Any]:
    manifest = final_scheduler_freeze_manifest()
    validation = validate_final_scheduler_freeze_manifest(manifest)
    if validation.get("freeze_manifest_valid") is not True:
        raise MLBStep14APersistenceContractError(
            f"Step 13D freeze manifest validation failed: {validation.get('failures')}"
        )
    if manifest.get("runtime_mode") != RUNTIME_MODE:
        raise MLBStep14APersistenceContractError("Step 13D runtime mode drift")
    if manifest.get("final_freeze_status") != STEP13D_FINAL_FREEZE_STATUS:
        raise MLBStep14APersistenceContractError("Step 13D final freeze status drift")
    if manifest.get("final_certification_marker") != STEP13D_FINAL_CERTIFICATION_MARKER:
        raise MLBStep14APersistenceContractError("Step 13D certification marker drift")
    freeze_hash = manifest.get("freeze_manifest_sha256")
    _valid_sha256(freeze_hash, "Step 13D freeze_manifest_sha256")
    return manifest


def _normalize_scheduler_state(value: Mapping[str, Any]) -> dict[str, Any]:
    state = _strict_json_object(value, "scheduler_state")
    unknown = set(state) - _SCHEDULER_STATE_KEYS
    missing = _SCHEDULER_STATE_KEYS - set(state)
    if missing:
        raise MLBStep14APersistenceContractError(
            f"scheduler_state missing keys: {sorted(missing)!r}"
        )
    if unknown:
        raise MLBStep14APersistenceContractError(
            f"scheduler_state has unsupported keys: {sorted(unknown)!r}"
        )

    last_slot = state["last_granted_slot_utc"]
    active_id = state["active_cycle_id"]
    active_slot = state["active_cycle_slot_utc"]
    if last_slot is not None:
        last_slot, _ = _utc_z(last_slot, "scheduler_state.last_granted_slot_utc")
    if active_id is not None:
        if not isinstance(active_id, str) or _CYCLE_ID_RE.fullmatch(active_id) is None:
            raise MLBStep14APersistenceContractError(
                "scheduler_state.active_cycle_id must be lowercase SHA-256 hex or None"
            )
    if active_slot is not None:
        active_slot, _ = _utc_z(active_slot, "scheduler_state.active_cycle_slot_utc")
    if (active_id is None) != (active_slot is None):
        raise MLBStep14APersistenceContractError(
            "scheduler_state active_cycle_id and active_cycle_slot_utc must both be set or both be None"
        )
    if active_id is not None:
        if last_slot is None or active_slot != last_slot:
            raise MLBStep14APersistenceContractError(
                "active scheduler cycle requires last_granted_slot_utc equal to active_cycle_slot_utc"
            )
    return {
        "last_granted_slot_utc": last_slot,
        "active_cycle_id": active_id,
        "active_cycle_slot_utc": active_slot,
    }


def _verify_recovery_decision(value: Mapping[str, Any]) -> dict[str, Any]:
    decision = _strict_json_object(value, "recovery_decision")
    validation = validate_recovery_decision(decision)
    if validation.get("recovery_decision_valid") is not True:
        raise MLBStep14APersistenceContractError(
            f"Step 13C recovery decision validation failed: {validation.get('failures')}"
        )
    if decision.get("runtime_mode") != RUNTIME_MODE or STEP13C_RUNTIME_MODE != RUNTIME_MODE:
        raise MLBStep14APersistenceContractError("Step 13C runtime mode drift")
    if decision.get("step13b_final_certification_marker") is None:
        raise MLBStep14APersistenceContractError("Step 13B certification marker missing")
    reliability_sha = decision.get("reliability_sha256")
    _valid_sha256(reliability_sha, "recovery_decision.reliability_sha256")
    return decision


def _recovery_handoff(decision: Mapping[str, Any]) -> dict[str, Any]:
    handoff = {key: deepcopy(decision.get(key)) for key in _RECOVERY_HANDOFF_KEYS}
    if set(handoff) != _RECOVERY_HANDOFF_KEYS:
        raise MLBStep14APersistenceContractError("recovery handoff field drift")
    for field in (
        "retry_authorized",
        "restart_authorized",
        "scheduler_state_release_authorized",
        "stuck_cycle_release_authorized",
        "cooldown_required",
    ):
        if type(handoff[field]) is not bool:
            raise MLBStep14APersistenceContractError(f"recovery_handoff.{field} must be boolean")
    if not isinstance(handoff["cooldown_seconds"], int) or isinstance(handoff["cooldown_seconds"], bool) or handoff["cooldown_seconds"] < 0:
        raise MLBStep14APersistenceContractError(
            "recovery_handoff.cooldown_seconds must be a nonnegative integer"
        )
    if handoff["cooldown_until_utc"] is not None:
        handoff["cooldown_until_utc"], _ = _utc_z(
            handoff["cooldown_until_utc"], "recovery_handoff.cooldown_until_utc"
        )
    if handoff["recovery_attempt_number"] is not None:
        if not isinstance(handoff["recovery_attempt_number"], int) or isinstance(handoff["recovery_attempt_number"], bool) or handoff["recovery_attempt_number"] < 1:
            raise MLBStep14APersistenceContractError(
                "recovery_handoff.recovery_attempt_number must be a positive integer or None"
            )
    _valid_sha256(handoff["recovery_token_sha256"], "recovery_handoff.recovery_token_sha256")
    return handoff


def checkpoint_key_for_slate(slate_date: str | date) -> str:
    """Return the deterministic slate-scoped durable checkpoint key."""
    parsed = _slate_date(slate_date)
    return f"mlb:runtime:{SEASON}:regular-season:{parsed}"


def persistence_contract_manifest() -> dict[str, Any]:
    """Return the immutable Step 14A durable-persistence boundary."""
    step13 = _step13d_manifest()
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step14a_base_main_sha": STEP14A_BASE_MAIN_SHA,
        "contract_id": CONTRACT_ID,
        "contract_status": CONTRACT_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step13d_merge_sha_required": STEP13D_MERGE_SHA,
        "step13d_source_blob_sha_required": STEP13D_SOURCE_BLOB_SHA,
        "step13d_final_freeze_status_required": STEP13D_FINAL_FREEZE_STATUS,
        "step13d_final_certification_marker_required": STEP13D_FINAL_CERTIFICATION_MARKER,
        "step13d_freeze_manifest_sha256_required": step13["freeze_manifest_sha256"],
        "step13c_final_certification_marker_required": STEP13C_FINAL_CERTIFICATION_MARKER,
        "database_dialect": DATABASE_DIALECT,
        "database_schema_name": DATABASE_SCHEMA_NAME,
        "checkpoint_table_name": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table_name": CHECKPOINT_HEAD_TABLE_NAME,
        "sql_schema_path": SQL_SCHEMA_PATH,
        "schema_definition_allowed": True,
        "durable_checkpoint_envelope_allowed": True,
        "append_only_checkpoint_history_required": True,
        "one_head_per_checkpoint_key_required": True,
        "compare_and_swap_version_boundary_required": True,
        "exact_step13c_recovery_decision_required": True,
        "exact_scheduler_state_required": True,
        "exact_recovery_state_required": True,
        "recovery_cooldown_handoff_persisted": True,
        "content_addressed_envelope_required": True,
        "slate_scoped_checkpoint_key_required": True,
        "database_read_allowed": False,
        "database_write_allowed": False,
        "persistence_runtime_enabled": False,
        "durable_restart_recovery_allowed": False,
        "durable_distributed_lease_allowed": False,
        "cross_process_duplicate_run_guard_allowed": False,
        "production_activation_allowed": False,
        "public_api_activation_allowed": False,
        "background_worker_allowed": False,
        "runtime_cycle_execution_added_by_step14a": False,
        "retry_execution_added_by_step14a": False,
        "restart_execution_added_by_step14a": False,
        "scheduler_state_mutation_added_by_step14a": False,
        "recovery_state_mutation_added_by_step14a": False,
        "network_io_added_by_step14a": False,
        "provider_network_calls_enabled_by_step14a": False,
        "production_database_writes_enabled": False,
        "actionable_output_enabled": False,
        "future_step14b_database_adapter_required": True,
        "future_step14c_durable_restart_lease_required": True,
        "future_step14d_final_persistence_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


def validate_persistence_contract_manifest(
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(manifest, Mapping):
        failures.append("STEP14A_MANIFEST_NOT_MAPPING")
    else:
        try:
            expected = persistence_contract_manifest()
        except Exception as exc:
            failures.append(f"STEP14A_MANIFEST_REBUILD_FAILED:{type(exc).__name__}:{exc}")
        else:
            if dict(manifest) != expected:
                failures.append("STEP14A_MANIFEST_EXACT_CONTRACT_MISMATCH")
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "manifest_valid": not failures,
        "failures": failures,
    }


def _envelope_hash_surface(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in envelope.items()
        if key not in {"created_at_utc", "envelope_content_sha256"}
    }


def _assert_state_identity(
    *,
    scheduler_state: Mapping[str, Any],
    cycle_id: str | None,
    cycle_slot_utc: str | None,
) -> None:
    active_id = scheduler_state.get("active_cycle_id")
    active_slot = scheduler_state.get("active_cycle_slot_utc")
    if cycle_id is None:
        if active_id is not None or active_slot is not None:
            raise MLBStep14APersistenceContractError(
                "checkpoint cannot contain an active scheduler cycle when Step 13C has no cycle identity"
            )
        return
    if not isinstance(cycle_id, str) or _CYCLE_ID_RE.fullmatch(cycle_id) is None:
        raise MLBStep14APersistenceContractError("cycle_id is invalid")
    if cycle_slot_utc is None:
        raise MLBStep14APersistenceContractError("cycle_slot_utc is required for a cycle identity")
    cycle_slot_utc, _ = _utc_z(cycle_slot_utc, "cycle_slot_utc")
    if active_id is not None and active_id != cycle_id:
        raise MLBStep14APersistenceContractError(
            "scheduler_state active_cycle_id does not match Step 13C cycle identity"
        )
    if active_slot is not None and active_slot != cycle_slot_utc:
        raise MLBStep14APersistenceContractError(
            "scheduler_state active_cycle_slot_utc does not match Step 13C cycle slot"
        )


def build_step14a_checkpoint_envelope(
    *,
    recovery_decision: Mapping[str, Any],
    scheduler_state: Mapping[str, Any],
    slate_date: str | date,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build one validated, JSON-safe checkpoint candidate without database I/O."""
    step13 = _step13d_manifest()
    decision = _verify_recovery_decision(recovery_decision)
    state = _normalize_scheduler_state(scheduler_state)
    parsed_slate = _slate_date(slate_date)

    nested_supervision = decision.get("step13b_supervision")
    if not isinstance(nested_supervision, Mapping):
        raise MLBStep14APersistenceContractError("Step 13C supervision payload missing")
    nested_tick = nested_supervision.get("scheduler_tick")
    if not isinstance(nested_tick, Mapping):
        raise MLBStep14APersistenceContractError("Step 13A scheduler tick missing")

    scheduler_anchor, _ = _utc_z(
        nested_tick.get("scheduler_anchor_utc"), "scheduler_anchor_utc"
    )
    interval_seconds = nested_tick.get("interval_seconds")
    if not isinstance(interval_seconds, int) or isinstance(interval_seconds, bool) or interval_seconds <= 0:
        raise MLBStep14APersistenceContractError("interval_seconds must be a positive integer")

    cycle_id = decision.get("cycle_id")
    cycle_slot = decision.get("cycle_slot_utc")
    if cycle_slot is not None:
        cycle_slot, _ = _utc_z(cycle_slot, "cycle_slot_utc")
    _assert_state_identity(
        scheduler_state=state,
        cycle_id=cycle_id,
        cycle_slot_utc=cycle_slot,
    )

    recovery_state = _strict_json_object(
        decision.get("next_recovery_state"), "next_recovery_state"
    )
    if recovery_state.get("data_type") != RECOVERY_STATE_DATA_TYPE:
        raise MLBStep14APersistenceContractError("Step 13C recovery-state data type drift")
    recovery_state_hash = recovery_state.get("recovery_state_sha256")
    _valid_sha256(recovery_state_hash, "recovery_state.recovery_state_sha256")
    computed_recovery_hash = _hash(
        {key: value for key, value in recovery_state.items() if key != "recovery_state_sha256"}
    )
    if recovery_state_hash != computed_recovery_hash:
        raise MLBStep14APersistenceContractError("Step 13C recovery-state hash mismatch")
    if recovery_state.get("cycle_id") != cycle_id:
        raise MLBStep14APersistenceContractError("recovery_state cycle identity mismatch")

    handoff = _recovery_handoff(decision)
    source_evaluated, source_evaluated_dt = _utc_z(
        decision.get("evaluated_at_utc"), "source_evaluated_at_utc"
    )
    created, created_dt = (
        _utc_z(created_at_utc, "created_at_utc")
        if created_at_utc is not None
        else (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            datetime.now(timezone.utc),
        )
    )
    if created_dt < source_evaluated_dt:
        raise MLBStep14APersistenceContractError(
            "created_at_utc cannot be before the Step 13C decision evaluation"
        )

    supervision_sha = nested_supervision.get("supervision_sha256")
    _valid_sha256(supervision_sha, "source_supervision_sha256")
    reliability_sha = decision.get("reliability_sha256")
    _valid_sha256(reliability_sha, "source_reliability_sha256")

    envelope: dict[str, Any] = {
        "data_type": ENVELOPE_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "contract_status": CONTRACT_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "slate_date": parsed_slate,
        "checkpoint_key": checkpoint_key_for_slate(parsed_slate),
        "step14a_base_main_sha": STEP14A_BASE_MAIN_SHA,
        "step13d_merge_sha": STEP13D_MERGE_SHA,
        "step13d_source_blob_sha": STEP13D_SOURCE_BLOB_SHA,
        "step13d_final_certification_marker": STEP13D_FINAL_CERTIFICATION_MARKER,
        "step13d_freeze_manifest_sha256": step13["freeze_manifest_sha256"],
        "source_step13c_final_certification_marker": STEP13C_FINAL_CERTIFICATION_MARKER,
        "source_reliability_sha256": reliability_sha,
        "source_supervision_sha256": supervision_sha,
        "source_evaluated_at_utc": source_evaluated,
        "scheduler_anchor_utc": scheduler_anchor,
        "interval_seconds": interval_seconds,
        "cycle_id": cycle_id,
        "cycle_slot_utc": cycle_slot,
        "scheduler_state": state,
        "scheduler_state_sha256": _hash(state),
        "recovery_state": recovery_state,
        "recovery_state_sha256": recovery_state_hash,
        "recovery_handoff": handoff,
        "recovery_handoff_sha256": _hash(handoff),
        "created_at_utc": created,
    }
    envelope["envelope_content_sha256"] = _hash(_envelope_hash_surface(envelope))
    return envelope


def validate_step14a_checkpoint_envelope(
    envelope: Mapping[str, Any] | None,
    *,
    expected_slate_date: str | date | None = None,
) -> dict[str, Any]:
    """Validate a stored/candidate envelope without touching a database."""
    failures: list[str] = []
    if not isinstance(envelope, Mapping):
        return {
            "data_type": ENVELOPE_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "envelope_valid": False,
            "failures": ["STEP14A_ENVELOPE_NOT_MAPPING"],
        }

    value = dict(envelope)
    missing = sorted(_ENVELOPE_KEYS - set(value))
    unknown = sorted(set(value) - _ENVELOPE_KEYS)
    if missing:
        failures.append("STEP14A_ENVELOPE_MISSING_KEYS:" + ",".join(missing))
    if unknown:
        failures.append("STEP14A_ENVELOPE_UNKNOWN_KEYS:" + ",".join(unknown))
    if failures:
        return {
            "data_type": ENVELOPE_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "envelope_valid": False,
            "failures": failures,
        }

    try:
        step13 = _step13d_manifest()
        parsed_slate = _slate_date(value.get("slate_date"))
        if expected_slate_date is not None and parsed_slate != _slate_date(expected_slate_date):
            raise MLBStep14APersistenceContractError(
                "checkpoint belongs to a different requested slate"
            )
        if value.get("checkpoint_key") != checkpoint_key_for_slate(parsed_slate):
            raise MLBStep14APersistenceContractError("checkpoint key/slate mismatch")

        exact = {
            "data_type": value.get("data_type") == ENVELOPE_DATA_TYPE,
            "schema_version": value.get("schema_version") == SCHEMA_VERSION,
            "contract_id": value.get("contract_id") == CONTRACT_ID,
            "contract_status": value.get("contract_status") == CONTRACT_STATUS,
            "runtime_mode": value.get("runtime_mode") == RUNTIME_MODE,
            "season": value.get("season") == SEASON,
            "season_type": value.get("season_type") == SEASON_TYPE,
            "step14a_base_main_sha": value.get("step14a_base_main_sha") == STEP14A_BASE_MAIN_SHA,
            "step13d_merge_sha": value.get("step13d_merge_sha") == STEP13D_MERGE_SHA,
            "step13d_source_blob_sha": value.get("step13d_source_blob_sha") == STEP13D_SOURCE_BLOB_SHA,
            "step13d_marker": value.get("step13d_final_certification_marker") == STEP13D_FINAL_CERTIFICATION_MARKER,
            "step13d_manifest_hash": value.get("step13d_freeze_manifest_sha256") == step13["freeze_manifest_sha256"],
            "step13c_marker": value.get("source_step13c_final_certification_marker") == STEP13C_FINAL_CERTIFICATION_MARKER,
        }
        bad_exact = [name for name, ok in exact.items() if not ok]
        if bad_exact:
            raise MLBStep14APersistenceContractError(
                "checkpoint lineage/contract drift: " + ", ".join(bad_exact)
            )
        if _GIT_SHA_RE.fullmatch(value["step13d_merge_sha"]) is None or _GIT_SHA_RE.fullmatch(value["step13d_source_blob_sha"]) is None:
            raise MLBStep14APersistenceContractError("checkpoint Git lineage SHA invalid")

        source_evaluated, source_dt = _utc_z(
            value.get("source_evaluated_at_utc"), "source_evaluated_at_utc"
        )
        created, created_dt = _utc_z(value.get("created_at_utc"), "created_at_utc")
        if created_dt < source_dt:
            raise MLBStep14APersistenceContractError(
                "created_at_utc cannot precede source_evaluated_at_utc"
            )
        _utc_z(value.get("scheduler_anchor_utc"), "scheduler_anchor_utc")
        if not isinstance(value.get("interval_seconds"), int) or isinstance(value.get("interval_seconds"), bool) or value["interval_seconds"] <= 0:
            raise MLBStep14APersistenceContractError("interval_seconds is invalid")

        cycle_id = value.get("cycle_id")
        cycle_slot = value.get("cycle_slot_utc")
        if cycle_id is not None:
            if not isinstance(cycle_id, str) or _CYCLE_ID_RE.fullmatch(cycle_id) is None:
                raise MLBStep14APersistenceContractError("cycle_id is invalid")
            if cycle_slot is None:
                raise MLBStep14APersistenceContractError("cycle_slot_utc missing for cycle")
            cycle_slot, _ = _utc_z(cycle_slot, "cycle_slot_utc")
        elif cycle_slot is not None:
            raise MLBStep14APersistenceContractError("cycle_slot_utc cannot exist without cycle_id")

        scheduler_state = _normalize_scheduler_state(value.get("scheduler_state"))
        _assert_state_identity(
            scheduler_state=scheduler_state,
            cycle_id=cycle_id,
            cycle_slot_utc=cycle_slot,
        )
        scheduler_hash = _valid_sha256(
            value.get("scheduler_state_sha256"), "scheduler_state_sha256"
        )
        if scheduler_hash != _hash(scheduler_state):
            raise MLBStep14APersistenceContractError("scheduler_state hash mismatch")

        recovery_state = _strict_json_object(value.get("recovery_state"), "recovery_state")
        recovery_hash = _valid_sha256(
            value.get("recovery_state_sha256"), "recovery_state_sha256"
        )
        if recovery_state.get("data_type") != RECOVERY_STATE_DATA_TYPE:
            raise MLBStep14APersistenceContractError("recovery_state data type mismatch")
        if recovery_state.get("cycle_id") != cycle_id:
            raise MLBStep14APersistenceContractError("recovery_state cycle identity mismatch")
        if recovery_state.get("recovery_state_sha256") != recovery_hash:
            raise MLBStep14APersistenceContractError("recovery_state embedded hash mismatch")
        computed_recovery_hash = _hash(
            {key: val for key, val in recovery_state.items() if key != "recovery_state_sha256"}
        )
        if computed_recovery_hash != recovery_hash:
            raise MLBStep14APersistenceContractError("recovery_state content hash mismatch")

        handoff = _strict_json_object(value.get("recovery_handoff"), "recovery_handoff")
        if set(handoff) != _RECOVERY_HANDOFF_KEYS:
            raise MLBStep14APersistenceContractError("recovery_handoff exact field mismatch")
        handoff_hash = _valid_sha256(
            value.get("recovery_handoff_sha256"), "recovery_handoff_sha256"
        )
        if handoff_hash != _hash(handoff):
            raise MLBStep14APersistenceContractError("recovery_handoff hash mismatch")
        if handoff.get("cooldown_until_utc") is not None:
            _utc_z(handoff.get("cooldown_until_utc"), "recovery_handoff.cooldown_until_utc")

        _valid_sha256(value.get("source_reliability_sha256"), "source_reliability_sha256")
        _valid_sha256(value.get("source_supervision_sha256"), "source_supervision_sha256")
        observed_envelope_hash = _valid_sha256(
            value.get("envelope_content_sha256"), "envelope_content_sha256"
        )
        expected_envelope_hash = _hash(_envelope_hash_surface(value))
        if observed_envelope_hash != expected_envelope_hash:
            raise MLBStep14APersistenceContractError("checkpoint envelope content hash mismatch")

        # Reassign canonical values only to prove normalization does not change the stored contract.
        if source_evaluated != value["source_evaluated_at_utc"] or created != value["created_at_utc"]:
            raise MLBStep14APersistenceContractError("checkpoint timestamp is not canonical UTC")
    except Exception as exc:
        failures.append(f"STEP14A_ENVELOPE_INVALID:{type(exc).__name__}:{exc}")

    return {
        "data_type": ENVELOPE_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "envelope_valid": not failures,
        "checkpoint_key": value.get("checkpoint_key"),
        "envelope_content_sha256": value.get("envelope_content_sha256"),
        "failures": failures,
    }


def build_step14a_schema_manifest() -> dict[str, Any]:
    """Return the relational DDL contract; this function performs no I/O."""
    contract = persistence_contract_manifest()
    manifest: dict[str, Any] = {
        "data_type": SCHEMA_MANIFEST_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "contract_status": CONTRACT_STATUS,
        "database_dialect": DATABASE_DIALECT,
        "database_schema": DATABASE_SCHEMA_NAME,
        "sql_schema_path": SQL_SCHEMA_PATH,
        "tables": {
            "checkpoints": {
                "name": CHECKPOINT_TABLE_NAME,
                "append_only": True,
                "unique_checkpoint_key_version": True,
                "unique_checkpoint_key_envelope_hash": True,
                "envelope_json_required": True,
                "scheduler_state_hash_required": True,
                "recovery_state_hash_required": True,
                "recovery_handoff_hash_required": True,
                "source_reliability_hash_required": True,
            },
            "heads": {
                "name": CHECKPOINT_HEAD_TABLE_NAME,
                "one_head_per_checkpoint_key": True,
                "points_to_append_only_checkpoint": True,
                "compare_and_swap_version_boundary": True,
            },
        },
        "lease_table_defined": False,
        "database_read_allowed": False,
        "database_write_allowed": False,
        "persistence_runtime_enabled": False,
        "durable_restart_recovery_allowed": False,
        "durable_distributed_lease_allowed": False,
        "production_activation_allowed": False,
        "step13d_freeze_manifest_sha256": contract["step13d_freeze_manifest_sha256_required"],
    }
    manifest["manifest_content_sha256"] = _hash(manifest)
    return manifest


__all__ = [
    "DATA_TYPE",
    "ENVELOPE_DATA_TYPE",
    "SCHEMA_MANIFEST_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP14A_BASE_MAIN_SHA",
    "STEP13D_MERGE_SHA",
    "STEP13D_SOURCE_BLOB_SHA",
    "CONTRACT_ID",
    "CONTRACT_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "SEASON",
    "SEASON_TYPE",
    "DATABASE_DIALECT",
    "DATABASE_SCHEMA_NAME",
    "CHECKPOINT_TABLE_NAME",
    "CHECKPOINT_HEAD_TABLE_NAME",
    "SQL_SCHEMA_PATH",
    "DEFAULT_ENABLED",
    "DATABASE_SCHEMA_DEFINITION_ALLOWED",
    "DURABLE_CHECKPOINT_ENVELOPE_ALLOWED",
    "DATABASE_READ_ALLOWED",
    "DATABASE_WRITE_ALLOWED",
    "PERSISTENCE_RUNTIME_ENABLED",
    "DURABLE_RESTART_RECOVERY_ALLOWED",
    "DURABLE_DISTRIBUTED_LEASE_ALLOWED",
    "CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "PUBLIC_API_ACTIVATION_ALLOWED",
    "BACKGROUND_WORKER_ALLOWED",
    "ACTIONABLE_OUTPUT_ALLOWED",
    "MLBStep14APersistenceContractError",
    "checkpoint_key_for_slate",
    "persistence_contract_manifest",
    "validate_persistence_contract_manifest",
    "build_step14a_checkpoint_envelope",
    "validate_step14a_checkpoint_envelope",
    "build_step14a_schema_manifest",
]
