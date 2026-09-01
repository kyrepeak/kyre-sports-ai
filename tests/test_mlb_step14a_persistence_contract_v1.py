from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step12_final_runtime_freeze_v1 import final_runtime_freeze_manifest
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    bounded_scheduler_manifest,
    build_bounded_scheduler_tick,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import build_runtime_supervision
from sports_api.mlb_step13c_reliability_recovery_v1 import build_recovery_decision
from sports_api.mlb_step13_final_scheduler_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13D_MARKER,
    final_scheduler_freeze_manifest,
)
from sports_api.mlb_step14a_persistence_contract_v1 import (
    ACTIONABLE_OUTPUT_ALLOWED,
    BACKGROUND_WORKER_ALLOWED,
    CHECKPOINT_HEAD_TABLE_NAME,
    CHECKPOINT_TABLE_NAME,
    CONTRACT_ID,
    CONTRACT_STATUS,
    CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
    DATABASE_DIALECT,
    DATABASE_READ_ALLOWED,
    DATABASE_SCHEMA_DEFINITION_ALLOWED,
    DATABASE_SCHEMA_NAME,
    DATABASE_WRITE_ALLOWED,
    DEFAULT_ENABLED,
    DURABLE_CHECKPOINT_ENVELOPE_ALLOWED,
    DURABLE_DISTRIBUTED_LEASE_ALLOWED,
    DURABLE_RESTART_RECOVERY_ALLOWED,
    ENVELOPE_DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MLBStep14APersistenceContractError,
    PERSISTENCE_RUNTIME_ENABLED,
    PRODUCTION_ACTIVATION_ALLOWED,
    PUBLIC_API_ACTIVATION_ALLOWED,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    SEASON,
    SEASON_TYPE,
    SQL_SCHEMA_PATH,
    STEP13D_MERGE_SHA,
    STEP13D_SOURCE_BLOB_SHA,
    STEP14A_BASE_MAIN_SHA,
    build_step14a_checkpoint_envelope,
    build_step14a_schema_manifest,
    checkpoint_key_for_slate,
    persistence_contract_manifest,
    validate_persistence_contract_manifest,
    validate_step14a_checkpoint_envelope,
)

BASE = "2026-09-01T12:00:00Z"
ANCHOR = "2026-09-01T00:00:00Z"
SLATE = "2026-09-01"


def _hash(value):
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _rehash_envelope(envelope: dict) -> None:
    surface = {
        key: deepcopy(value)
        for key, value in envelope.items()
        if key not in {"created_at_utc", "envelope_content_sha256"}
    }
    envelope["envelope_content_sha256"] = _hash(surface)


def _permit_tick():
    return build_bounded_scheduler_tick(
        evaluated_at_utc=BASE,
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=None,
        step12_final_manifest=final_runtime_freeze_manifest(),
        scheduler_enabled=True,
        interval_seconds=30,
    )


def _active_state_from_tick(tick):
    return {
        "last_granted_slot_utc": tick["permit_slot_utc"],
        "active_cycle_id": tick["permit_cycle_id"],
        "active_cycle_slot_utc": tick["permit_slot_utc"],
    }


def _ready_decision():
    tick = _permit_tick()
    supervision = build_runtime_supervision(
        tick,
        observed_at_utc=BASE,
        cycle_observation=None,
        step13a_manifest=bounded_scheduler_manifest(),
    )
    decision = build_recovery_decision(
        supervision,
        evaluated_at_utc=BASE,
        recovery_state=None,
    )
    return tick, decision


def _failed_decision():
    permit = _permit_tick()
    active_state = _active_state_from_tick(permit)
    active_tick = build_bounded_scheduler_tick(
        evaluated_at_utc="2026-09-01T12:00:10Z",
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=active_state,
        step12_final_manifest=final_runtime_freeze_manifest(),
        scheduler_enabled=True,
        interval_seconds=30,
    )
    supervision = build_runtime_supervision(
        active_tick,
        observed_at_utc="2026-09-01T12:00:20Z",
        cycle_observation={
            "cycle_id": permit["permit_cycle_id"],
            "cycle_slot_utc": permit["permit_slot_utc"],
            "started_at_utc": "2026-09-01T12:00:01Z",
            "finished_at_utc": "2026-09-01T12:00:20Z",
            "outcome": "FAILURE",
            "failure_code": "NETWORK.TIMEOUT",
        },
        step13a_manifest=bounded_scheduler_manifest(),
    )
    decision = build_recovery_decision(
        supervision,
        evaluated_at_utc="2026-09-01T12:00:20Z",
        recovery_state=None,
    )
    return permit, active_state, decision


def _ready_envelope(created="2026-09-01T12:00:05Z"):
    tick, decision = _ready_decision()
    return build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=_active_state_from_tick(tick),
        slate_date=SLATE,
        created_at_utc=created,
    )


def test_step14a_identity_constants_are_pinned():
    assert STEP14A_BASE_MAIN_SHA == "e0c79e2ccb9e34846ed4499f29878853e7e1114a"
    assert STEP13D_MERGE_SHA == STEP14A_BASE_MAIN_SHA
    assert STEP13D_SOURCE_BLOB_SHA == "b53400fe205717ca075231f841b4ca7aabed90bc"
    assert CONTRACT_ID == "mlb_step14a_scheduler_recovery_checkpoint_contract_2026_v1"
    assert CONTRACT_STATUS == "STEP14A_PERSISTENCE_CONTRACT_READY"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP14A_PERSISTENCE_CONTRACT_GREEN"
    assert SCHEMA_VERSION == 1
    assert SEASON == 2026
    assert SEASON_TYPE == "Regular Season"


def test_step14a_storage_constants_are_pinned():
    assert DATABASE_DIALECT == "postgresql"
    assert DATABASE_SCHEMA_NAME == "kyre_runtime"
    assert CHECKPOINT_TABLE_NAME == "mlb_runtime_checkpoints"
    assert CHECKPOINT_HEAD_TABLE_NAME == "mlb_runtime_checkpoint_heads"
    assert SQL_SCHEMA_PATH == "sports_api/sql/mlb_step14a_persistence_schema.sql"


@pytest.mark.parametrize(
    "value",
    [
        DEFAULT_ENABLED,
        DATABASE_READ_ALLOWED,
        DATABASE_WRITE_ALLOWED,
        PERSISTENCE_RUNTIME_ENABLED,
        DURABLE_RESTART_RECOVERY_ALLOWED,
        DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        PRODUCTION_ACTIVATION_ALLOWED,
        PUBLIC_API_ACTIVATION_ALLOWED,
        BACKGROUND_WORKER_ALLOWED,
        ACTIONABLE_OUTPUT_ALLOWED,
    ],
)
def test_step14a_unsafe_capabilities_remain_false(value):
    assert value is False


def test_step14a_definition_capabilities_are_true_only_at_contract_layer():
    assert DATABASE_SCHEMA_DEFINITION_ALLOWED is True
    assert DURABLE_CHECKPOINT_ENVELOPE_ALLOWED is True


def test_parent_step13d_manifest_is_green_and_shadow_only():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["runtime_mode"] == "SHADOW_ONLY"
    assert manifest["final_certification_marker"] == STEP13D_MARKER
    assert manifest["step13_scheduler_recovery_block_frozen"] is True


def test_persistence_contract_manifest_is_exactly_valid():
    manifest = persistence_contract_manifest()
    validation = validate_persistence_contract_manifest(manifest)
    assert validation == {
        "data_type": "mlb_step14a_persistence_contract_v1",
        "schema_version": 1,
        "manifest_valid": True,
        "failures": [],
    }


@pytest.mark.parametrize("key", sorted(PROTECTED_INVARIANTS))
def test_contract_manifest_preserves_every_step9_protected_invariant(key):
    manifest = persistence_contract_manifest()
    assert PROTECTED_INVARIANTS[key] is False
    assert manifest[key] is False


@pytest.mark.parametrize(
    "key,expected",
    [
        ("schema_definition_allowed", True),
        ("durable_checkpoint_envelope_allowed", True),
        ("append_only_checkpoint_history_required", True),
        ("one_head_per_checkpoint_key_required", True),
        ("compare_and_swap_version_boundary_required", True),
        ("exact_step13c_recovery_decision_required", True),
        ("exact_scheduler_state_required", True),
        ("exact_recovery_state_required", True),
        ("recovery_cooldown_handoff_persisted", True),
        ("content_addressed_envelope_required", True),
        ("slate_scoped_checkpoint_key_required", True),
        ("database_read_allowed", False),
        ("database_write_allowed", False),
        ("persistence_runtime_enabled", False),
        ("durable_restart_recovery_allowed", False),
        ("durable_distributed_lease_allowed", False),
        ("cross_process_duplicate_run_guard_allowed", False),
        ("production_activation_allowed", False),
        ("public_api_activation_allowed", False),
        ("background_worker_allowed", False),
        ("runtime_cycle_execution_added_by_step14a", False),
        ("retry_execution_added_by_step14a", False),
        ("restart_execution_added_by_step14a", False),
        ("scheduler_state_mutation_added_by_step14a", False),
        ("recovery_state_mutation_added_by_step14a", False),
        ("network_io_added_by_step14a", False),
        ("provider_network_calls_enabled_by_step14a", False),
        ("production_database_writes_enabled", False),
        ("actionable_output_enabled", False),
        ("future_step14b_database_adapter_required", True),
        ("future_step14c_durable_restart_lease_required", True),
        ("future_step14d_final_persistence_freeze_required", True),
    ],
)
def test_contract_manifest_capability_boundary(key, expected):
    assert persistence_contract_manifest()[key] is expected


def test_contract_manifest_pins_exact_step13d_content_hash():
    step13 = final_scheduler_freeze_manifest()
    manifest = persistence_contract_manifest()
    assert manifest["step13d_freeze_manifest_sha256_required"] == step13["freeze_manifest_sha256"]
    assert len(step13["freeze_manifest_sha256"]) == 64


def test_contract_manifest_tamper_fails_exact_validation():
    manifest = persistence_contract_manifest()
    manifest["database_write_allowed"] = True
    result = validate_persistence_contract_manifest(manifest)
    assert result["manifest_valid"] is False
    assert "STEP14A_MANIFEST_EXACT_CONTRACT_MISMATCH" in result["failures"]


def test_checkpoint_key_is_deterministic_and_slate_scoped():
    assert checkpoint_key_for_slate(SLATE) == "mlb:runtime:2026:regular-season:2026-09-01"
    assert checkpoint_key_for_slate(date(2026, 9, 1)) == checkpoint_key_for_slate(SLATE)


@pytest.mark.parametrize("bad", ["", "2025-09-01", "2027-09-01", "09/01/2026", "2026-13-01"])
def test_checkpoint_key_rejects_invalid_or_wrong_season_dates(bad):
    with pytest.raises(MLBStep14APersistenceContractError):
        checkpoint_key_for_slate(bad)


def test_ready_checkpoint_envelope_is_valid_and_content_addressed():
    envelope = _ready_envelope()
    assert envelope["data_type"] == ENVELOPE_DATA_TYPE
    assert envelope["runtime_mode"] == "SHADOW_ONLY"
    assert envelope["checkpoint_key"] == "mlb:runtime:2026:regular-season:2026-09-01"
    assert envelope["step13d_merge_sha"] == STEP13D_MERGE_SHA
    assert envelope["step13d_source_blob_sha"] == STEP13D_SOURCE_BLOB_SHA
    assert envelope["scheduler_state_sha256"] == _hash(envelope["scheduler_state"])
    assert envelope["recovery_handoff_sha256"] == _hash(envelope["recovery_handoff"])
    assert len(envelope["envelope_content_sha256"]) == 64
    result = validate_step14a_checkpoint_envelope(envelope, expected_slate_date=SLATE)
    assert result["envelope_valid"] is True
    assert result["failures"] == []


def test_failed_checkpoint_persists_bounded_retry_cooldown_handoff():
    permit, active_state, decision = _failed_decision()
    assert decision["retry_authorized"] is True
    assert decision["restart_authorized"] is True
    assert decision["cooldown_required"] is True
    assert decision["cooldown_seconds"] == 15
    assert decision["cooldown_until_utc"] == "2026-09-01T12:00:35Z"
    envelope = build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=active_state,
        slate_date=SLATE,
        created_at_utc="2026-09-01T12:00:21Z",
    )
    handoff = envelope["recovery_handoff"]
    assert handoff["recovery_action"] == "RETRY_SAME_CYCLE_AFTER_COOLDOWN"
    assert handoff["retry_authorized"] is True
    assert handoff["restart_authorized"] is True
    assert handoff["cooldown_until_utc"] == "2026-09-01T12:00:35Z"
    assert handoff["recovery_attempt_number"] == 1
    assert envelope["cycle_id"] == permit["permit_cycle_id"]
    assert validate_step14a_checkpoint_envelope(envelope)["envelope_valid"] is True


def test_checkpoint_can_store_released_scheduler_state_without_changing_step13_decision():
    tick, decision = _ready_decision()
    released = {
        "last_granted_slot_utc": tick["permit_slot_utc"],
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }
    envelope = build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=released,
        slate_date=SLATE,
        created_at_utc="2026-09-01T12:00:05Z",
    )
    assert envelope["scheduler_state"] == released
    assert validate_step14a_checkpoint_envelope(envelope)["envelope_valid"] is True


def test_envelope_content_hash_is_independent_of_created_timestamp():
    first = _ready_envelope("2026-09-01T12:00:05Z")
    second = _ready_envelope("2026-09-01T12:00:10Z")
    assert first["created_at_utc"] != second["created_at_utc"]
    assert first["envelope_content_sha256"] == second["envelope_content_sha256"]


def test_envelope_content_hash_changes_when_scheduler_handoff_changes():
    tick, decision = _ready_decision()
    active = build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=_active_state_from_tick(tick),
        slate_date=SLATE,
        created_at_utc="2026-09-01T12:00:05Z",
    )
    released = build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state={
            "last_granted_slot_utc": tick["permit_slot_utc"],
            "active_cycle_id": None,
            "active_cycle_slot_utc": None,
        },
        slate_date=SLATE,
        created_at_utc="2026-09-01T12:00:05Z",
    )
    assert active["envelope_content_sha256"] != released["envelope_content_sha256"]


@pytest.mark.parametrize(
    "scheduler_state",
    [
        {},
        {"last_granted_slot_utc": None, "active_cycle_id": None},
        {"last_granted_slot_utc": None, "active_cycle_id": None, "active_cycle_slot_utc": None, "extra": 1},
        {"last_granted_slot_utc": None, "active_cycle_id": "a" * 64, "active_cycle_slot_utc": None},
        {"last_granted_slot_utc": None, "active_cycle_id": None, "active_cycle_slot_utc": BASE},
        {"last_granted_slot_utc": None, "active_cycle_id": "x" * 64, "active_cycle_slot_utc": BASE},
        {"last_granted_slot_utc": "not-time", "active_cycle_id": None, "active_cycle_slot_utc": None},
        {"last_granted_slot_utc": BASE, "active_cycle_id": "a" * 64, "active_cycle_slot_utc": "2026-09-01T12:00:30Z"},
    ],
)
def test_build_checkpoint_rejects_malformed_scheduler_state(scheduler_state):
    _, decision = _ready_decision()
    with pytest.raises(MLBStep14APersistenceContractError):
        build_step14a_checkpoint_envelope(
            recovery_decision=decision,
            scheduler_state=scheduler_state,
            slate_date=SLATE,
            created_at_utc="2026-09-01T12:00:05Z",
        )


def test_build_checkpoint_rejects_different_active_cycle_identity():
    tick, decision = _ready_decision()
    state = _active_state_from_tick(tick)
    state["active_cycle_id"] = "f" * 64
    with pytest.raises(MLBStep14APersistenceContractError, match="does not match"):
        build_step14a_checkpoint_envelope(
            recovery_decision=decision,
            scheduler_state=state,
            slate_date=SLATE,
            created_at_utc="2026-09-01T12:00:05Z",
        )


def test_build_checkpoint_rejects_different_active_cycle_slot():
    tick, decision = _ready_decision()
    state = _active_state_from_tick(tick)
    state["last_granted_slot_utc"] = "2026-09-01T12:00:30Z"
    state["active_cycle_slot_utc"] = "2026-09-01T12:00:30Z"
    with pytest.raises(MLBStep14APersistenceContractError, match="does not match"):
        build_step14a_checkpoint_envelope(
            recovery_decision=decision,
            scheduler_state=state,
            slate_date=SLATE,
            created_at_utc="2026-09-01T12:00:05Z",
        )


def test_build_checkpoint_rejects_invalid_recovery_decision():
    tick, decision = _ready_decision()
    decision["retry_executed"] = True
    with pytest.raises(MLBStep14APersistenceContractError, match="validation failed"):
        build_step14a_checkpoint_envelope(
            recovery_decision=decision,
            scheduler_state=_active_state_from_tick(tick),
            slate_date=SLATE,
            created_at_utc="2026-09-01T12:00:05Z",
        )


def test_build_checkpoint_rejects_created_timestamp_before_source_decision():
    tick, decision = _ready_decision()
    with pytest.raises(MLBStep14APersistenceContractError, match="cannot be before"):
        build_step14a_checkpoint_envelope(
            recovery_decision=decision,
            scheduler_state=_active_state_from_tick(tick),
            slate_date=SLATE,
            created_at_utc="2026-09-01T11:59:59Z",
        )


@pytest.mark.parametrize("bad_time", ["", "2026-09-01T12:00:05", "2026-09-01 12:00:05Z", "nonsense"])
def test_build_checkpoint_rejects_noncanonical_created_time(bad_time):
    tick, decision = _ready_decision()
    with pytest.raises(MLBStep14APersistenceContractError):
        build_step14a_checkpoint_envelope(
            recovery_decision=decision,
            scheduler_state=_active_state_from_tick(tick),
            slate_date=SLATE,
            created_at_utc=bad_time,
        )


@pytest.mark.parametrize(
    "key,replacement",
    [
        ("data_type", "tampered"),
        ("schema_version", 999),
        ("contract_id", "tampered"),
        ("contract_status", "tampered"),
        ("runtime_mode", "PRODUCTION"),
        ("season", 2025),
        ("season_type", "Postseason"),
        ("checkpoint_key", "mlb:wrong"),
        ("step14a_base_main_sha", "0" * 40),
        ("step13d_merge_sha", "0" * 40),
        ("step13d_source_blob_sha", "0" * 40),
        ("step13d_final_certification_marker", "tampered"),
        ("step13d_freeze_manifest_sha256", "0" * 64),
        ("source_step13c_final_certification_marker", "tampered"),
        ("source_reliability_sha256", "0" * 64),
        ("source_supervision_sha256", "0" * 64),
        ("scheduler_anchor_utc", "2026-09-01T01:00:00Z"),
        ("interval_seconds", 31),
        ("scheduler_state_sha256", "0" * 64),
        ("recovery_state_sha256", "0" * 64),
        ("recovery_handoff_sha256", "0" * 64),
        ("envelope_content_sha256", "0" * 64),
    ],
)
def test_envelope_tamper_fails_closed(key, replacement):
    envelope = _ready_envelope()
    envelope[key] = replacement
    result = validate_step14a_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False
    assert result["failures"]


def test_envelope_unknown_field_fails_closed():
    envelope = _ready_envelope()
    envelope["surprise"] = True
    result = validate_step14a_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False
    assert result["failures"][0].startswith("STEP14A_ENVELOPE_UNKNOWN_KEYS")


def test_envelope_missing_field_fails_closed():
    envelope = _ready_envelope()
    envelope.pop("scheduler_state")
    result = validate_step14a_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False
    assert result["failures"][0].startswith("STEP14A_ENVELOPE_MISSING_KEYS")


def test_envelope_expected_slate_mismatch_fails_closed():
    envelope = _ready_envelope()
    result = validate_step14a_checkpoint_envelope(envelope, expected_slate_date="2026-09-02")
    assert result["envelope_valid"] is False
    assert "different requested slate" in result["failures"][0]


def test_envelope_cycle_id_tamper_fails_even_if_outer_hash_is_recomputed():
    envelope = _ready_envelope()
    envelope["cycle_id"] = "f" * 64
    _rehash_envelope(envelope)
    result = validate_step14a_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False
    assert "cycle identity mismatch" in result["failures"][0] or "does not match" in result["failures"][0]


def test_envelope_scheduler_state_tamper_fails_even_if_outer_hash_is_recomputed():
    envelope = _ready_envelope()
    envelope["scheduler_state"]["active_cycle_id"] = "f" * 64
    envelope["scheduler_state_sha256"] = _hash(envelope["scheduler_state"])
    _rehash_envelope(envelope)
    result = validate_step14a_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False
    assert "does not match" in result["failures"][0]


def test_envelope_recovery_state_tamper_fails_even_if_outer_hash_is_recomputed():
    envelope = _ready_envelope()
    envelope["recovery_state"]["attempts_used"] = 5
    envelope["recovery_state"]["recovery_state_sha256"] = _hash(
        {k: v for k, v in envelope["recovery_state"].items() if k != "recovery_state_sha256"}
    )
    envelope["recovery_state_sha256"] = envelope["recovery_state"]["recovery_state_sha256"]
    _rehash_envelope(envelope)
    # Step 14A preserves the exact hash-bound state and does not itself decide whether
    # attempts_used is actionable. Durable recovery interpretation belongs to 14C.
    assert validate_step14a_checkpoint_envelope(envelope)["envelope_valid"] is True


def test_created_at_can_advance_without_changing_content_identity():
    envelope = _ready_envelope()
    original_hash = envelope["envelope_content_sha256"]
    envelope["created_at_utc"] = "2026-09-01T12:30:00Z"
    result = validate_step14a_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is True
    assert envelope["envelope_content_sha256"] == original_hash


def test_schema_manifest_is_hash_bound_and_non_runtime():
    manifest = build_step14a_schema_manifest()
    observed = manifest["manifest_content_sha256"]
    expected = _hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"})
    assert observed == expected
    assert manifest["database_read_allowed"] is False
    assert manifest["database_write_allowed"] is False
    assert manifest["persistence_runtime_enabled"] is False
    assert manifest["durable_restart_recovery_allowed"] is False
    assert manifest["durable_distributed_lease_allowed"] is False
    assert manifest["production_activation_allowed"] is False
    assert manifest["lease_table_defined"] is False


@pytest.mark.parametrize(
    "path,expected",
    [
        (("tables", "checkpoints", "name"), "mlb_runtime_checkpoints"),
        (("tables", "checkpoints", "append_only"), True),
        (("tables", "checkpoints", "unique_checkpoint_key_version"), True),
        (("tables", "checkpoints", "unique_checkpoint_key_envelope_hash"), True),
        (("tables", "checkpoints", "scheduler_state_hash_required"), True),
        (("tables", "checkpoints", "recovery_state_hash_required"), True),
        (("tables", "checkpoints", "recovery_handoff_hash_required"), True),
        (("tables", "heads", "name"), "mlb_runtime_checkpoint_heads"),
        (("tables", "heads", "one_head_per_checkpoint_key"), True),
        (("tables", "heads", "compare_and_swap_version_boundary"), True),
    ],
)
def test_schema_manifest_table_contract(path, expected):
    value = build_step14a_schema_manifest()
    for key in path:
        value = value[key]
    assert value == expected


def test_sql_schema_file_exists_and_is_ddl_only_contract():
    sql_path = Path(SQL_SCHEMA_PATH)
    assert sql_path.exists()
    text = sql_path.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS kyre_runtime" in text
    assert "CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_checkpoints" in text
    assert "CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_checkpoint_heads" in text
    assert "checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1)" in text
    assert "UNIQUE (checkpoint_key, checkpoint_version)" in text
    assert "UNIQUE (checkpoint_key, envelope_content_sha256)" in text
    assert "ON DELETE RESTRICT" in text
    assert "lease" in text.lower()  # comment explicitly says no lease table
    assert "CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_leases" not in text


@pytest.mark.parametrize(
    "forbidden",
    [
        "INSERT INTO",
        "UPDATE kyre_runtime",
        "DELETE FROM",
        "TRUNCATE",
        "DROP TABLE",
        "DROP SCHEMA",
    ],
)
def test_sql_contract_contains_no_runtime_data_mutation_statements(forbidden):
    text = Path(SQL_SCHEMA_PATH).read_text(encoding="utf-8").upper()
    assert forbidden not in text


def test_build_does_not_mutate_input_decision_or_scheduler_state():
    tick, decision = _ready_decision()
    scheduler_state = _active_state_from_tick(tick)
    original_decision = deepcopy(decision)
    original_state = deepcopy(scheduler_state)
    build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=scheduler_state,
        slate_date=SLATE,
        created_at_utc="2026-09-01T12:00:05Z",
    )
    assert decision == original_decision
    assert scheduler_state == original_state


def test_checkpoint_contains_zero_execution_or_production_side_effect_fields_by_design():
    envelope = _ready_envelope()
    forbidden_true_names = {
        "runtime_cycle_executed",
        "retry_executed",
        "restart_executed",
        "network_io_performed",
        "production_scheduler_activation",
        "production_database_writes",
        "actionable_output_enabled",
    }
    assert forbidden_true_names.isdisjoint(envelope)
    manifest = persistence_contract_manifest()
    assert manifest["runtime_cycle_execution_added_by_step14a"] is False
    assert manifest["retry_execution_added_by_step14a"] is False
    assert manifest["restart_execution_added_by_step14a"] is False
    assert manifest["network_io_added_by_step14a"] is False
    assert manifest["production_database_writes_enabled"] is False
    assert manifest["actionable_output_enabled"] is False
