from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from sports_api.mlb_step12_final_runtime_freeze_v1 import final_runtime_freeze_manifest
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    bounded_scheduler_manifest,
    build_bounded_scheduler_tick,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import build_runtime_supervision
from sports_api.mlb_step13c_reliability_recovery_v1 import build_recovery_decision
from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as s14b


def safe_env(*, read: bool = True, write: bool = True) -> dict[str, str]:
    return {
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
        "MLB_STEP14B_DATABASE_READ_ENABLED": "true" if read else "false",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED": "true" if write else "false",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_STEP14C_DURABLE_RESTART_ENABLED": "false",
        "MLB_STEP14C_DISTRIBUTED_LEASE_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
    }


def checkpoint_envelope(
    *,
    evaluated_at_utc: str = "2026-09-01T12:00:00Z",
    created_at_utc: str = "2026-09-01T12:00:05Z",
) -> dict:
    tick = build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated_at_utc,
        scheduler_anchor_utc="2026-09-01T00:00:00Z",
        scheduler_state=None,
        step12_final_manifest=final_runtime_freeze_manifest(),
        scheduler_enabled=True,
        interval_seconds=30,
    )
    supervision = build_runtime_supervision(
        tick,
        observed_at_utc=evaluated_at_utc,
        cycle_observation=None,
        step13a_manifest=bounded_scheduler_manifest(),
    )
    decision = build_recovery_decision(
        supervision,
        evaluated_at_utc=evaluated_at_utc,
    )
    scheduler_state = {
        "last_granted_slot_utc": tick["permit_slot_utc"],
        "active_cycle_id": tick["permit_cycle_id"],
        "active_cycle_slot_utc": tick["permit_slot_utc"],
    }
    return step14a.build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=scheduler_state,
        slate_date="2026-09-01",
        created_at_utc=created_at_utc,
    )


def head_row(envelope: dict, version: int = 1):
    checkpoint_id = s14b.checkpoint_id_for_envelope(envelope)
    return (
        version,
        checkpoint_id,
        envelope["envelope_content_sha256"],
        version,
        checkpoint_id,
        envelope["checkpoint_key"],
        envelope["slate_date"],
        envelope["step13d_merge_sha"],
        envelope["step13d_source_blob_sha"],
        envelope["step13d_freeze_manifest_sha256"],
        envelope["source_reliability_sha256"],
        envelope["source_supervision_sha256"],
        envelope["cycle_id"],
        envelope["cycle_slot_utc"],
        envelope["scheduler_state_sha256"],
        envelope["recovery_state_sha256"],
        envelope["recovery_handoff_sha256"],
        envelope["envelope_content_sha256"],
        deepcopy(envelope),
    )


class UniqueViolation(Exception):
    sqlstate = "23505"


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.rowcount = -1
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        if not self.script:
            raise AssertionError(f"unexpected SQL: {sql}")
        step = self.script.pop(0)
        contains = step.get("contains")
        if contains and contains not in sql:
            raise AssertionError(f"expected {contains!r} in SQL: {sql}")
        self.calls.append((sql, params))
        if step.get("raise") is not None:
            raise step["raise"]
        self.current = step
        self.rowcount = step.get("rowcount", -1)

    def fetchone(self):
        return None if self.current is None else self.current.get("fetchone")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, script):
        self.cursor_obj = FakeCursor(script)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def factory_for(script):
    box = {}

    def factory():
        box["connection"] = FakeConnection(script)
        return box["connection"]

    return factory, box


def schema_step(*, checkpoint=True, head=True):
    return {
        "contains": "to_regclass",
        "fetchone": (checkpoint, head),
    }


def load_script(row):
    return [
        schema_step(),
        {
            "contains": f"JOIN {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "fetchone": row,
        },
    ]


def save_initial_script():
    return [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": None},
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 1,
        },
    ]


def test_default_adapter_gate_is_off():
    assert s14b.step14b_database_checkpoint_adapter_enabled({}) is False


def test_default_read_gate_is_off():
    assert s14b.step14b_database_read_enabled({}) is False


def test_default_write_gate_is_off():
    assert s14b.step14b_database_write_enabled({}) is False


def test_exact_step14b_base_main_sha():
    assert s14b.STEP14B_BASE_MAIN_SHA == "3dae5181571dbfea45f6f0db87e916d25e971170"


def test_exact_step14a_merge_sha():
    assert s14b.STEP14A_MERGE_SHA == "3dae5181571dbfea45f6f0db87e916d25e971170"


def test_exact_step14a_source_blob_sha():
    assert s14b.STEP14A_SOURCE_BLOB_SHA == "373996a35959e5ad2252325062b250ddffd4286c"


def test_exact_step14a_sql_blob_sha():
    assert s14b.STEP14A_SQL_SOURCE_BLOB_SHA == "969c88c529486c8cde54f7928919e2a393a0f588"


def test_final_marker():
    assert s14b.FINAL_CERTIFICATION_MARKER == "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_GREEN"


def test_runtime_remains_shadow_only():
    assert s14b.RUNTIME_MODE == "SHADOW_ONLY"


def test_manifest_validates_exactly():
    manifest = s14b.database_checkpoint_adapter_manifest()
    result = s14b.validate_database_checkpoint_adapter_manifest(manifest)
    assert result["manifest_valid"] is True
    assert result["failures"] == []


def test_manifest_tamper_fails_exact_validation():
    manifest = s14b.database_checkpoint_adapter_manifest()
    manifest["runtime_mode"] = "TAMPERED"
    result = s14b.validate_database_checkpoint_adapter_manifest(manifest)
    assert result["manifest_valid"] is False


@pytest.mark.parametrize(
    "key",
    [
        "postgresql_database_read_allowed",
        "postgresql_database_write_allowed",
        "checkpoint_load_allowed",
        "checkpoint_save_allowed",
        "append_only_checkpoint_history_required",
        "atomic_head_compare_and_swap_required",
        "select_for_update_head_serialization_required",
        "deterministic_uuid5_checkpoint_id_required",
        "idempotent_same_envelope_save_required",
        "schema_presence_probe_required",
        "explicit_adapter_gate_required",
        "explicit_read_gate_required",
        "explicit_write_gate_required",
        "future_step14c_durable_restart_lease_required",
        "future_step14d_final_persistence_freeze_required",
    ],
)
def test_manifest_required_true_capabilities(key):
    assert s14b.database_checkpoint_adapter_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "schema_auto_apply_allowed",
        "persistence_runtime_enabled",
        "durable_restart_recovery_allowed",
        "durable_distributed_lease_allowed",
        "cross_process_duplicate_run_guard_allowed",
        "production_activation_allowed",
        "public_api_activation_allowed",
        "actionable_output_allowed",
        "background_worker_allowed",
        "supabase_rest_write_allowed",
        "runtime_cycle_execution_added_by_step14b",
        "retry_execution_added_by_step14b",
        "restart_execution_added_by_step14b",
        "provider_network_calls_added_by_step14b",
        "sportsbook_network_calls_added_by_step14b",
        "scheduler_state_mutation_added_by_step14b",
        "recovery_state_mutation_added_by_step14b",
    ],
)
def test_manifest_forbidden_capabilities_remain_false(key):
    assert s14b.database_checkpoint_adapter_manifest()[key] is False


def test_step14a_contract_still_forbids_database_reads():
    assert step14a.DATABASE_READ_ALLOWED is False


def test_step14a_contract_still_forbids_database_writes():
    assert step14a.DATABASE_WRITE_ALLOWED is False


def test_step14a_contract_still_forbids_runtime_persistence():
    assert step14a.PERSISTENCE_RUNTIME_ENABLED is False


def test_step14a_schema_still_has_no_lease_table():
    assert step14a.build_step14a_schema_manifest()["lease_table_defined"] is False


@pytest.mark.parametrize(
    "key",
    [
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_STEP14C_DURABLE_RESTART_ENABLED",
        "MLB_STEP14C_DISTRIBUTED_LEASE_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_SUPABASE_REST_WRITE_ENABLED",
    ],
)
def test_forbidden_runtime_switches_fail_closed(key):
    env = safe_env()
    env[key] = "true"
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterDisabledError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=env,
            connection_factory=lambda: None,
        )


@pytest.mark.parametrize("value", ["", "0", "false", "FALSE", "off", "disabled", "no"])
def test_adapter_falsey_gate_values_are_disabled(value):
    env = safe_env()
    env["MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"] = value
    assert s14b.step14b_database_checkpoint_adapter_enabled(env) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "enabled"])
def test_adapter_truthy_gate_values_are_enabled(value):
    env = safe_env()
    env["MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"] = value
    assert s14b.step14b_database_checkpoint_adapter_enabled(env) is True


def test_adapter_gate_required_before_opening_connection():
    env = safe_env()
    env["MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"] = "false"
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterDisabledError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=env,
            connection_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        )


def test_read_gate_required_for_load():
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterDisabledError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=False),
            connection_factory=lambda: None,
        )


def test_read_gate_required_for_save():
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterDisabledError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=checkpoint_envelope(),
            expected_head_version=0,
            env=safe_env(read=False, write=True),
            connection_factory=lambda: None,
        )


def test_write_gate_required_for_save():
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterDisabledError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=checkpoint_envelope(),
            expected_head_version=0,
            env=safe_env(read=True, write=False),
            connection_factory=lambda: None,
        )


def test_requirement_is_psycopg3_only():
    text = Path("sports_api/requirements-mlb-step14b-persistence.txt").read_text()
    assert "psycopg[binary]" in text
    assert "supabase" not in text.lower()
    assert "requests" not in text.lower()


def test_missing_database_url_fails_closed():
    env = safe_env(read=True, write=False)
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterDisabledError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=env,
        )


def test_connection_factory_failure_is_wrapped():
    def broken():
        raise OSError("boom")

    with pytest.raises(s14b.MLBStep14BDatabaseError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=broken,
        )


def test_connection_factory_none_is_wrapped():
    with pytest.raises(s14b.MLBStep14BDatabaseError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=lambda: None,
        )


def test_checkpoint_id_is_deterministic_uuid5():
    envelope = checkpoint_envelope()
    first = s14b.checkpoint_id_for_envelope(envelope)
    second = s14b.checkpoint_id_for_envelope(envelope)
    assert first == second
    assert UUID(first).version == 5


def test_checkpoint_id_changes_with_checkpoint_content():
    first = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:00Z",
        created_at_utc="2026-09-01T12:00:05Z",
    )
    second = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:30Z",
        created_at_utc="2026-09-01T12:00:35Z",
    )
    assert s14b.checkpoint_id_for_envelope(first) != s14b.checkpoint_id_for_envelope(second)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"checkpoint_key": "x"},
        {"envelope_content_sha256": "a" * 64},
        {"checkpoint_key": "x", "envelope_content_sha256": "z" * 64},
    ],
)
def test_checkpoint_id_rejects_invalid_identity(bad):
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterInputError):
        s14b.checkpoint_id_for_envelope(bad)


def test_schema_verify_is_read_only_and_closes_resources():
    factory, box = factory_for([schema_step()])
    result = s14b.verify_step14b_database_schema(
        env=safe_env(read=True, write=False),
        connection_factory=factory,
        generated_at_utc="2026-09-01T12:01:00Z",
    )
    assert result["tables_present"] is True
    assert result["database_write_performed"] is False
    assert result["schema_auto_apply_performed"] is False
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1
    assert box["connection"].cursor_obj.closed is True
    assert box["connection"].closed is True


@pytest.mark.parametrize(
    "probe",
    [
        (False, True),
        (True, False),
        (False, False),
    ],
)
def test_schema_verify_missing_table_fails_closed(probe):
    factory, box = factory_for([
        {"contains": "to_regclass", "fetchone": probe},
    ])
    with pytest.raises(s14b.MLBStep14BDatabaseSchemaError):
        s14b.verify_step14b_database_schema(
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )
    assert box["connection"].rollbacks >= 1


@pytest.mark.parametrize("shape", [None, (), (True,), (True, True, True), "bad"])
def test_schema_verify_invalid_probe_shape_fails_closed(shape):
    factory, _ = factory_for([
        {"contains": "to_regclass", "fetchone": shape},
    ])
    with pytest.raises(s14b.MLBStep14BDatabaseSchemaError):
        s14b.verify_step14b_database_schema(
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )


def test_load_not_found_returns_clean_result():
    factory, box = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
        generated_at_utc="2026-09-01T12:01:00Z",
    )
    assert result["status"] == "not_found"
    assert result["found"] is False
    assert result["checkpoint_version"] is None
    assert result["checkpoint_envelope"] is None
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is True


def test_load_valid_head_returns_exact_restart_handoff():
    envelope = checkpoint_envelope()
    factory, _ = factory_for(load_script(head_row(envelope, version=4)))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
        generated_at_utc="2026-09-01T12:01:00Z",
    )
    assert result["status"] == "loaded"
    assert result["checkpoint_version"] == 4
    assert result["checkpoint_envelope"] == envelope
    assert result["scheduler_state_for_restart"] == envelope["scheduler_state"]
    assert result["recovery_state_for_restart"] == envelope["recovery_state"]
    assert result["recovery_handoff_for_restart"] == envelope["recovery_handoff"]
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is True


def test_load_accepts_json_string_envelope_from_driver():
    envelope = checkpoint_envelope()
    row = list(head_row(envelope))
    row[-1] = json.dumps(envelope)
    factory, _ = factory_for(load_script(tuple(row)))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    assert result["found"] is True
    assert result["checkpoint_envelope"] == envelope


@pytest.mark.parametrize(
    "index,replacement",
    [
        (0, 0),
        (0, True),
        (3, 2),
        (4, "00000000-0000-0000-0000-000000000000"),
        (7, "0" * 40),
        (8, "0" * 40),
        (9, "0" * 64),
        (10, "0" * 64),
        (11, "0" * 64),
        (12, "0" * 64),
        (14, "0" * 64),
        (15, "0" * 64),
        (16, "0" * 64),
        (17, "0" * 64),
    ],
)
def test_load_corrupt_persisted_row_fails_closed(index, replacement):
    envelope = checkpoint_envelope()
    row = list(head_row(envelope))
    row[index] = replacement
    factory, _ = factory_for(load_script(tuple(row)))
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterIntegrityError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )


def test_load_tampered_envelope_fails_closed():
    envelope = checkpoint_envelope()
    row = list(head_row(envelope))
    tampered = deepcopy(envelope)
    tampered["scheduler_state"]["active_cycle_id"] = "0" * 64
    row[-1] = tampered
    factory, _ = factory_for(load_script(tuple(row)))
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterIntegrityError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )


def test_load_wrong_slate_fails_closed():
    envelope = checkpoint_envelope()
    row = list(head_row(envelope))
    row[6] = "2026-09-02"
    factory, _ = factory_for(load_script(tuple(row)))
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterIntegrityError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )


@pytest.mark.parametrize("row", [(), (1,), tuple(range(18)), tuple(range(20))])
def test_load_wrong_row_shape_fails_closed(row):
    factory, _ = factory_for(load_script(row))
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterIntegrityError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )


def test_save_initial_checkpoint_creates_version_one():
    envelope = checkpoint_envelope()
    factory, box = factory_for(save_initial_script())
    result = s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=safe_env(),
        connection_factory=factory,
        generated_at_utc="2026-09-01T12:01:00Z",
    )
    assert result["status"] == "created"
    assert result["checkpoint_version"] == 1
    assert result["checkpoint_id"] == s14b.checkpoint_id_for_envelope(envelope)
    assert box["connection"].commits == 1
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is True


def test_save_initial_insert_contains_exact_frozen_lineage():
    envelope = checkpoint_envelope()
    factory, box = factory_for(save_initial_script())
    s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=safe_env(),
        connection_factory=factory,
    )
    history_params = box["connection"].cursor_obj.calls[2][1]
    assert history_params[6] == envelope["step13d_merge_sha"]
    assert history_params[7] == envelope["step13d_source_blob_sha"]
    assert history_params[8] == envelope["step13d_freeze_manifest_sha256"]
    assert history_params[9] == envelope["source_reliability_sha256"]
    assert history_params[10] == envelope["source_supervision_sha256"]


def test_save_existing_checkpoint_advances_version_with_cas():
    old = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:00Z",
        created_at_utc="2026-09-01T12:00:05Z",
    )
    new = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:30Z",
        created_at_utc="2026-09-01T12:00:35Z",
    )
    script = [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 1)},
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"UPDATE {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 1,
        },
    ]
    factory, box = factory_for(script)
    result = s14b.save_step14b_checkpoint(
        checkpoint_envelope=new,
        expected_head_version=1,
        env=safe_env(),
        connection_factory=factory,
    )
    assert result["status"] == "advanced"
    assert result["checkpoint_version"] == 2
    update_params = box["connection"].cursor_obj.calls[-1][1]
    assert update_params[-1] == 1
    assert box["connection"].commits == 1


def test_save_stale_expected_version_conflicts_before_history_insert():
    old = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:00Z",
        created_at_utc="2026-09-01T12:00:05Z",
    )
    new = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:30Z",
        created_at_utc="2026-09-01T12:00:35Z",
    )
    factory, box = factory_for([
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 2)},
    ])
    with pytest.raises(s14b.MLBStep14BDatabaseConflictError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=new,
            expected_head_version=1,
            env=safe_env(),
            connection_factory=factory,
        )
    assert len(box["connection"].cursor_obj.calls) == 2
    assert box["connection"].rollbacks >= 1
    assert box["connection"].commits == 0


def test_save_idempotent_same_envelope_does_not_append():
    envelope = checkpoint_envelope()
    factory, box = factory_for([
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(envelope, 3)},
    ])
    result = s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=safe_env(),
        connection_factory=factory,
    )
    assert result["status"] == "idempotent"
    assert result["checkpoint_version"] == 3
    assert len(box["connection"].cursor_obj.calls) == 2
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1


@pytest.mark.parametrize("bad_version", [-1, True, False, 1.0, "1", None])
def test_save_rejects_invalid_expected_head_version(bad_version):
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterInputError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=checkpoint_envelope(),
            expected_head_version=bad_version,
            env=safe_env(),
            connection_factory=lambda: None,
        )


def test_save_rejects_tampered_envelope_before_database_open():
    envelope = checkpoint_envelope()
    envelope["envelope_content_sha256"] = "0" * 64
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterIntegrityError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        )


def test_save_history_insert_bad_rowcount_rolls_back():
    envelope = checkpoint_envelope()
    script = [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": None},
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 0,
        },
    ]
    factory, box = factory_for(script)
    with pytest.raises(s14b.MLBStep14BDatabaseError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=factory,
        )
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1


def test_save_head_insert_bad_rowcount_is_cas_conflict():
    envelope = checkpoint_envelope()
    script = [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": None},
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 0,
        },
    ]
    factory, box = factory_for(script)
    with pytest.raises(s14b.MLBStep14BDatabaseConflictError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=factory,
        )
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1


def test_save_update_head_bad_rowcount_is_cas_conflict():
    old = checkpoint_envelope()
    new = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:30Z",
        created_at_utc="2026-09-01T12:00:35Z",
    )
    script = [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 1)},
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"UPDATE {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 0,
        },
    ]
    factory, box = factory_for(script)
    with pytest.raises(s14b.MLBStep14BDatabaseConflictError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=new,
            expected_head_version=1,
            env=safe_env(),
            connection_factory=factory,
        )
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1


def test_save_unique_violation_maps_to_conflict():
    envelope = checkpoint_envelope()
    script = [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": None},
        {
            "contains": f"INSERT INTO {s14b.DATABASE_SCHEMA_NAME}.{s14b.CHECKPOINT_TABLE_NAME}",
            "raise": UniqueViolation("dupe"),
        },
    ]
    factory, box = factory_for(script)
    with pytest.raises(s14b.MLBStep14BDatabaseConflictError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=factory,
        )
    assert box["connection"].rollbacks >= 1


def test_save_generic_database_failure_is_wrapped():
    envelope = checkpoint_envelope()
    script = [
        schema_step(),
        {"contains": "FOR UPDATE OF h", "raise": RuntimeError("db down")},
    ]
    factory, box = factory_for(script)
    with pytest.raises(s14b.MLBStep14BDatabaseError):
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=factory,
        )
    assert box["connection"].rollbacks >= 1


def test_load_generic_database_failure_is_wrapped():
    factory, box = factory_for([
        schema_step(),
        {"contains": "JOIN", "raise": RuntimeError("db down")},
    ])
    with pytest.raises(s14b.MLBStep14BDatabaseError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )
    assert box["connection"].rollbacks >= 1


def test_result_content_hash_ignores_only_generated_timestamp():
    factory1, _ = factory_for(load_script(None))
    first = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory1,
        generated_at_utc="2026-09-01T12:01:00Z",
    )
    factory2, _ = factory_for(load_script(None))
    second = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory2,
        generated_at_utc="2026-09-01T12:02:00Z",
    )
    assert first["generated_at_utc"] != second["generated_at_utc"]
    assert first["adapter_content_sha256"] == second["adapter_content_sha256"]


def test_result_tampered_hash_fails_validation():
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["adapter_content_sha256"] = "0" * 64
    validation = s14b.validate_step14b_adapter_result(result)
    assert validation["result_valid"] is False


def test_result_unknown_key_fails_validation():
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["unexpected"] = True
    validation = s14b.validate_step14b_adapter_result(result)
    assert validation["result_valid"] is False


def test_result_missing_key_fails_validation():
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result.pop("status")
    validation = s14b.validate_step14b_adapter_result(result)
    assert validation["result_valid"] is False


@pytest.mark.parametrize(
    "guardrail",
    [
        "schema_auto_apply",
        "persistence_runtime_enabled",
        "durable_restart_recovery",
        "durable_distributed_lease",
        "cross_process_duplicate_run_guard",
        "production_activation",
        "public_api_activation",
        "actionable_output",
        "background_worker",
        "supabase_rest_write",
        "runtime_cycle_executed",
        "retry_executed",
        "restart_executed",
    ],
)
def test_result_forbidden_guardrail_tamper_fails_validation(guardrail):
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["guardrails"][guardrail] = True
    result["adapter_content_sha256"] = s14b._hash(s14b._result_hash_surface(result))
    validation = s14b.validate_step14b_adapter_result(result)
    assert validation["result_valid"] is False


def test_result_provider_call_tamper_fails_validation():
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["guardrails"]["provider_network_calls"] = 1
    result["adapter_content_sha256"] = s14b._hash(s14b._result_hash_surface(result))
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is False


def test_result_sportsbook_call_tamper_fails_validation():
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["guardrails"]["sportsbook_network_calls"] = 1
    result["adapter_content_sha256"] = s14b._hash(s14b._result_hash_surface(result))
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is False


def test_not_found_result_cannot_carry_restart_state():
    factory, _ = factory_for(load_script(None))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["scheduler_state_for_restart"] = {}
    result["adapter_content_sha256"] = s14b._hash(s14b._result_hash_surface(result))
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is False


def test_found_result_cannot_swap_checkpoint_id():
    envelope = checkpoint_envelope()
    factory, _ = factory_for(load_script(head_row(envelope)))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    result["checkpoint_id"] = "00000000-0000-0000-0000-000000000000"
    result["adapter_content_sha256"] = s14b._hash(s14b._result_hash_surface(result))
    assert s14b.validate_step14b_adapter_result(result)["result_valid"] is False


def test_history_insert_is_append_only_not_update():
    assert "INSERT INTO kyre_runtime.mlb_runtime_checkpoints" in s14b._INSERT_HISTORY_SQL
    assert "UPDATE kyre_runtime.mlb_runtime_checkpoints" not in s14b._INSERT_HISTORY_SQL


def test_head_update_is_version_guarded_cas():
    assert "AND checkpoint_version = %s" in s14b._UPDATE_HEAD_SQL


def test_head_read_for_save_locks_only_head():
    assert "FOR UPDATE OF h" in s14b._HEAD_SELECT_FOR_UPDATE_SQL


def test_no_schema_auto_apply_sql_in_adapter():
    module_text = Path("sports_api/mlb_step14b_database_checkpoint_adapter_v1.py").read_text()
    assert "CREATE TABLE" not in module_text
    assert "CREATE SCHEMA" not in module_text


@pytest.mark.parametrize(
    "forbidden",
    [
        "requests.",
        "httpx.",
        "urllib.request",
        "socket.socket",
        "time.sleep",
        "threading.Thread",
        "multiprocessing.",
        "asyncio.create_task",
        "supabase.create_client",
    ],
)
def test_adapter_has_no_forbidden_runtime_or_provider_machinery(forbidden):
    module_text = Path("sports_api/mlb_step14b_database_checkpoint_adapter_v1.py").read_text()
    assert forbidden not in module_text


def test_schema_check_has_zero_write_flags():
    factory, _ = factory_for([schema_step()])
    result = s14b.verify_step14b_database_schema(
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    assert result["database_write_performed"] is False
    assert result["schema_auto_apply_performed"] is False


def test_saved_result_keeps_runtime_and_recovery_execution_false():
    envelope = checkpoint_envelope()
    factory, _ = factory_for(save_initial_script())
    result = s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=safe_env(),
        connection_factory=factory,
    )
    guardrails = result["guardrails"]
    assert guardrails["runtime_cycle_executed"] is False
    assert guardrails["retry_executed"] is False
    assert guardrails["restart_executed"] is False
    assert guardrails["provider_network_calls"] == 0
    assert guardrails["sportsbook_network_calls"] == 0


def test_load_does_not_require_write_gate():
    envelope = checkpoint_envelope()
    factory, _ = factory_for(load_script(head_row(envelope)))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    assert result["found"] is True


def test_schema_verify_does_not_require_write_gate():
    factory, _ = factory_for([schema_step()])
    result = s14b.verify_step14b_database_schema(
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    assert result["tables_present"] is True


def test_checkpoint_envelope_source_remains_step14a_exact_contract():
    envelope = checkpoint_envelope()
    validation = step14a.validate_step14a_checkpoint_envelope(
        envelope,
        expected_slate_date="2026-09-01",
    )
    assert validation["envelope_valid"] is True


def test_checkpoint_cycle_slot_round_trips_database_datetime():
    envelope = checkpoint_envelope()
    row = list(head_row(envelope))
    row[13] = datetime.fromisoformat(
        envelope["cycle_slot_utc"].replace("Z", "+00:00")
    )
    factory, _ = factory_for(load_script(tuple(row)))
    result = s14b.load_step14b_checkpoint(
        slate_date="2026-09-01",
        env=safe_env(read=True, write=False),
        connection_factory=factory,
    )
    assert result["found"] is True


def test_naive_database_cycle_timestamp_fails_closed():
    envelope = checkpoint_envelope()
    row = list(head_row(envelope))
    row[13] = datetime(2026, 9, 1, 12, 0, 0)
    factory, _ = factory_for(load_script(tuple(row)))
    with pytest.raises(s14b.MLBStep14BDatabaseAdapterInputError):
        s14b.load_step14b_checkpoint(
            slate_date="2026-09-01",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )


def test_checkpoint_history_created_at_uses_envelope_timestamp():
    envelope = checkpoint_envelope()
    factory, box = factory_for(save_initial_script())
    s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=safe_env(),
        connection_factory=factory,
    )
    history_params = box["connection"].cursor_obj.calls[2][1]
    created_at = history_params[-1]
    assert created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") == envelope["created_at_utc"]


def test_head_updated_at_uses_adapter_generated_time():
    envelope = checkpoint_envelope()
    factory, box = factory_for(save_initial_script())
    s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=safe_env(),
        connection_factory=factory,
        generated_at_utc="2026-09-01T12:02:00Z",
    )
    head_params = box["connection"].cursor_obj.calls[3][1]
    updated_at = head_params[-1]
    assert updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") == "2026-09-01T12:02:00Z"
