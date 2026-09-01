from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step12_final_runtime_freeze_v1 import final_runtime_freeze_manifest
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    bounded_scheduler_manifest,
    build_bounded_scheduler_tick,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import build_runtime_supervision
from sports_api.mlb_step13c_reliability_recovery_v1 import build_recovery_decision
from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as s14c

SLATE = "2026-09-01"
ANCHOR = "2026-09-01T00:00:00Z"
BASE = "2026-09-01T12:00:00Z"
TOKEN = "11111111-1111-4111-8111-111111111111"
TOKEN2 = "22222222-2222-4222-8222-222222222222"


def safe_env() -> dict[str, str]:
    return {
        "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED": "true",
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
        "MLB_STEP14B_DATABASE_READ_ENABLED": "true",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED": "true",
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
    evaluated_at_utc: str = BASE,
    created_at_utc: str = "2026-09-01T12:00:05Z",
) -> dict:
    tick = build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated_at_utc,
        scheduler_anchor_utc=ANCHOR,
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
        slate_date=SLATE,
        created_at_utc=created_at_utc,
    )


def head_row(envelope: dict, version: int = 1):
    checkpoint_id = step14b.checkpoint_id_for_envelope(envelope)
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


def lease_row(
    *,
    token: str = TOKEN,
    owner: str = "worker-a",
    generation: int = 1,
    acquired: str = "2026-09-01T12:00:00+00:00",
    renewed: str = "2026-09-01T12:00:01+00:00",
    expires: str = "2026-09-01T12:05:01+00:00",
):
    return (
        s14c.lease_key_for_slate(SLATE),
        owner,
        token,
        generation,
        acquired,
        renewed,
        expires,
    )


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


def lease_schema_step(present=True):
    return {"contains": "to_regclass", "fetchone": (present,)}


def checkpoint_schema_step():
    return {"contains": "to_regclass", "fetchone": (True, True)}


def acquire_script(row=None):
    if row is None:
        row = lease_row()
    return [
        lease_schema_step(),
        {
            "contains": f"INSERT INTO {s14c.DATABASE_SCHEMA_NAME}.{s14c.LEASE_TABLE_NAME}",
            "fetchone": row,
        },
    ]


def renew_script(row=None):
    if row is None:
        row = lease_row()
    return [
        lease_schema_step(),
        {
            "contains": f"UPDATE {s14c.DATABASE_SCHEMA_NAME}.{s14c.LEASE_TABLE_NAME}",
            "fetchone": row,
        },
    ]


def release_script(*, key=None):
    return [
        lease_schema_step(),
        {
            "contains": f"DELETE FROM {s14c.DATABASE_SCHEMA_NAME}.{s14c.LEASE_TABLE_NAME}",
            "fetchone": (key or s14c.lease_key_for_slate(SLATE),),
        },
    ]


def load_script(row):
    return [
        checkpoint_schema_step(),
        {
            "contains": f"JOIN {step14b.DATABASE_SCHEMA_NAME}.{step14b.CHECKPOINT_TABLE_NAME}",
            "fetchone": row,
        },
    ]


def save_initial_script():
    return [
        checkpoint_schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": None},
        {
            "contains": f"INSERT INTO {step14b.DATABASE_SCHEMA_NAME}.{step14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"INSERT INTO {step14b.DATABASE_SCHEMA_NAME}.{step14b.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 1,
        },
    ]


def save_advance_script(old_envelope, version=1):
    return [
        checkpoint_schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(old_envelope, version)},
        {
            "contains": f"INSERT INTO {step14b.DATABASE_SCHEMA_NAME}.{step14b.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"UPDATE {step14b.DATABASE_SCHEMA_NAME}.{step14b.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 1,
        },
    ]


def safe_lease_handle(*, token=TOKEN, generation=1):
    return {
        "lease_key": s14c.lease_key_for_slate(SLATE),
        "owner_id": "worker-a",
        "lease_token": token,
        "fencing_generation": generation,
        "acquired_at_utc": "2026-09-01T12:00:00Z",
        "renewed_at_utc": "2026-09-01T12:00:01Z",
        "expires_at_utc": "2026-09-01T12:05:01Z",
    }


def fresh_context():
    lease_factory, _ = factory_for(acquire_script())
    cp_factory, _ = factory_for(load_script(None))
    return s14c.load_step14c_restart_context(
        slate_date=SLATE,
        owner_id="worker-a",
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
        token_factory=lambda: TOKEN,
        generated_at_utc="2026-09-01T12:00:02Z",
    )


def recovered_context(envelope=None, version=1):
    envelope = envelope or checkpoint_envelope()
    lease_factory, _ = factory_for(acquire_script())
    cp_factory, _ = factory_for(load_script(head_row(envelope, version)))
    return s14c.load_step14c_restart_context(
        slate_date=SLATE,
        owner_id="worker-a",
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
        token_factory=lambda: TOKEN,
        generated_at_utc="2026-09-01T12:00:06Z",
    )


def rehash_context(context):
    surface = {
        k: deepcopy(v)
        for k, v in context.items()
        if k not in {"generated_at_utc", "restart_context_sha256"}
    }
    context["restart_context_sha256"] = hashlib.sha256(
        json.dumps(
            surface,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        ).encode()
    ).hexdigest()


def rehash_persist_result(result):
    surface = {
        k: deepcopy(v)
        for k, v in result.items()
        if k not in {"generated_at_utc", "persist_result_sha256"}
    }
    result["persist_result_sha256"] = hashlib.sha256(
        json.dumps(
            surface,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        ).encode()
    ).hexdigest()


def test_identity_and_lineage_constants_are_exact():
    assert s14c.STEP14C_BASE_MAIN_SHA == "195df0c15de1998754204080f9db4a76bca74e4b"
    assert s14c.STEP14B_MERGE_SHA == s14c.STEP14C_BASE_MAIN_SHA
    assert s14c.STEP14B_SOURCE_BLOB_SHA == "ee7ffe3117edc33b1377f883c25613d63760095b"
    assert s14c.FINAL_CERTIFICATION_MARKER == "MLB_STEP14C_DURABLE_RESTART_LEASE_GREEN"
    assert s14c.RUNTIME_MODE == "SHADOW_ONLY"
    assert s14c.RUNTIME_STATUS == "STEP14C_DURABLE_RESTART_LEASE_READY"


def test_lease_schema_identity_is_pinned_and_matches_bytes():
    path = Path(s14c.LEASE_SQL_SCHEMA_PATH)
    assert path.exists()
    assert s14c.LEASE_TABLE_NAME == "mlb_runtime_leases"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == s14c.LEASE_SQL_SCHEMA_SHA256


def test_step14c_is_default_off():
    assert s14c.DEFAULT_ENABLED is False
    assert s14c.step14c_durable_restart_lease_enabled({}) is False


@pytest.mark.parametrize(
    "value",
    [
        s14c.FOREGROUND_DURABLE_RESTART_CONTEXT_ALLOWED,
        s14c.DURABLE_RESTART_RECOVERY_ALLOWED,
        s14c.DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        s14c.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        s14c.FENCING_GENERATION_REQUIRED,
        s14c.LEASE_EXPIRY_REQUIRED,
        s14c.LEASE_REVALIDATION_BEFORE_SAVE_REQUIRED,
        s14c.CHECKPOINT_CAS_REQUIRED,
        s14c.CHECKPOINT_PERSIST_UNDER_LEASE_ALLOWED,
    ],
)
def test_required_step14c_capabilities_are_true(value):
    assert value is True


@pytest.mark.parametrize(
    "value",
    [
        s14c.DEFAULT_ENABLED,
        s14c.SCHEMA_AUTO_APPLY_ALLOWED,
        s14c.PERSISTENCE_RUNTIME_ENABLED,
        s14c.AUTOMATIC_RESTART_EXECUTION_ALLOWED,
        s14c.AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED,
        s14c.PRODUCTION_ACTIVATION_ALLOWED,
        s14c.PUBLIC_API_ACTIVATION_ALLOWED,
        s14c.ACTIONABLE_OUTPUT_ALLOWED,
        s14c.BACKGROUND_WORKER_ALLOWED,
        s14c.BACKGROUND_THREAD_ALLOWED,
        s14c.SUPABASE_REST_WRITE_ALLOWED,
    ],
)
def test_forbidden_step14c_capabilities_are_false(value):
    assert value is False


def test_manifest_validates_exactly():
    manifest = s14c.durable_restart_lease_manifest()
    result = s14c.validate_durable_restart_lease_manifest(manifest)
    assert result["manifest_valid"] is True
    assert result["failures"] == []


def test_manifest_tamper_fails_exactly():
    manifest = s14c.durable_restart_lease_manifest()
    manifest["production_activation_allowed"] = True
    result = s14c.validate_durable_restart_lease_manifest(manifest)
    assert result["manifest_valid"] is False


@pytest.mark.parametrize("key", sorted(PROTECTED_INVARIANTS))
def test_manifest_preserves_every_step9_protected_invariant(key):
    assert PROTECTED_INVARIANTS[key] is False
    assert s14c.durable_restart_lease_manifest()[key] is False


@pytest.mark.parametrize(
    "key,expected",
    [
        ("foreground_durable_restart_context_allowed", True),
        ("durable_restart_recovery_allowed", True),
        ("durable_distributed_lease_allowed", True),
        ("cross_process_duplicate_run_guard_allowed", True),
        ("lease_uuid_token_required", True),
        ("monotonic_fencing_generation_required", True),
        ("lease_expiry_required", True),
        ("lease_revalidation_before_checkpoint_save_required", True),
        ("checkpoint_compare_and_swap_required", True),
        ("append_only_checkpoint_history_required", True),
        ("checkpoint_persist_under_lease_allowed", True),
        ("schema_presence_probe_required", True),
        ("schema_auto_apply_allowed", False),
        ("persistence_runtime_enabled", False),
        ("automatic_restart_execution_allowed", False),
        ("automatic_production_restart_activation_allowed", False),
        ("production_activation_allowed", False),
        ("public_api_activation_allowed", False),
        ("actionable_output_allowed", False),
        ("background_worker_allowed", False),
        ("background_thread_allowed", False),
        ("supabase_rest_write_allowed", False),
        ("runtime_cycle_execution_added_by_step14c", False),
        ("retry_execution_added_by_step14c", False),
        ("restart_execution_added_by_step14c", False),
        ("provider_network_calls_added_by_step14c", False),
        ("sportsbook_network_calls_added_by_step14c", False),
        ("future_step14d_final_persistence_freeze_required", True),
    ],
)
def test_manifest_capability_boundary(key, expected):
    assert s14c.durable_restart_lease_manifest()[key] is expected


def test_parent_step14b_manifest_is_green_and_restart_off():
    manifest = step14b.database_checkpoint_adapter_manifest()
    assert step14b.validate_database_checkpoint_adapter_manifest(manifest)["manifest_valid"]
    assert manifest["runtime_mode"] == "SHADOW_ONLY"
    assert manifest["durable_restart_recovery_allowed"] is False
    assert manifest["durable_distributed_lease_allowed"] is False
    assert manifest["cross_process_duplicate_run_guard_allowed"] is False


@pytest.mark.parametrize(
    "key",
    [
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_SUPABASE_REST_WRITE_ENABLED",
    ],
)
def test_production_or_actionable_switches_fail_closed(key):
    env = safe_env()
    env[key] = "true"
    with pytest.raises(s14c.MLBStep14CDurableRuntimeDisabledError):
        s14c.verify_step14c_lease_schema(env=env, connection_factory=lambda: None)


@pytest.mark.parametrize(
    "key",
    [
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
        "MLB_STEP14B_DATABASE_READ_ENABLED",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED",
        "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    ],
)
def test_required_gates_fail_closed_when_disabled(key):
    env = safe_env()
    env[key] = "false"
    with pytest.raises(s14c.MLBStep14CDurableRuntimeDisabledError):
        s14c.verify_step14c_lease_schema(env=env, connection_factory=lambda: None)


def test_verify_lease_schema_is_read_only():
    factory, box = factory_for([lease_schema_step()])
    result = s14c.verify_step14c_lease_schema(
        env=safe_env(),
        connection_factory=factory,
        generated_at_utc="2026-09-01T12:00:00Z",
    )
    assert result["table_present"] is True
    assert result["database_write_performed"] is False
    assert result["schema_auto_apply_performed"] is False
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1
    assert box["connection"].closed is True


@pytest.mark.parametrize("row", [None, (), (False,), (True, False)])
def test_verify_lease_schema_fails_closed_on_bad_probe(row):
    factory, _ = factory_for([{"contains": "to_regclass", "fetchone": row}])
    with pytest.raises(s14c.MLBStep14CLeaseSchemaError):
        s14c.verify_step14c_lease_schema(env=safe_env(), connection_factory=factory)


def test_lease_key_is_deterministic_and_slate_scoped():
    key = s14c.lease_key_for_slate(SLATE)
    assert key == "mlb:runtime:2026:regular-season:2026-09-01:scheduler-recovery-lease"
    assert key == s14c.lease_key_for_slate(SLATE)


@pytest.mark.parametrize("bad", ["", "2025-09-01", "2027-09-01", "09/01/2026"])
def test_lease_key_rejects_bad_slate(bad):
    with pytest.raises(step14a.MLBStep14APersistenceContractError):
        s14c.lease_key_for_slate(bad)


@pytest.mark.parametrize("ttl", [0, 1, 59, 3601, 999999, True, False, 60.0, "300", None])
def test_acquire_rejects_invalid_lease_ttl(ttl):
    with pytest.raises(s14c.MLBStep14CDurableRuntimeInputError):
        s14c.acquire_step14c_lease(
            slate_date=SLATE,
            owner_id="worker-a",
            lease_ttl_seconds=ttl,
            env=safe_env(),
            connection_factory=lambda: None,
        )


@pytest.mark.parametrize("owner", ["", "   ", "x" * 256, None])
def test_acquire_rejects_invalid_owner(owner):
    with pytest.raises(s14c.MLBStep14CDurableRuntimeInputError):
        s14c.acquire_step14c_lease(
            slate_date=SLATE,
            owner_id=owner,
            env=safe_env(),
            connection_factory=lambda: None,
        )


@pytest.mark.parametrize("ttl", [60, 61, 300, 3599, 3600])
def test_acquire_accepts_certified_ttl_boundaries(ttl):
    factory, box = factory_for(acquire_script())
    result = s14c.acquire_step14c_lease(
        slate_date=SLATE,
        owner_id="worker-a",
        lease_ttl_seconds=ttl,
        env=safe_env(),
        connection_factory=factory,
        token_factory=lambda: TOKEN,
    )
    assert result["lease_token"] == TOKEN
    assert result["fencing_generation"] == 1
    assert box["connection"].commits == 1


def test_acquire_uses_uuid_token_and_exact_sql_parameters():
    factory, box = factory_for(acquire_script())
    result = s14c.acquire_step14c_lease(
        slate_date=SLATE,
        owner_id="worker-a",
        lease_ttl_seconds=300,
        env=safe_env(),
        connection_factory=factory,
        token_factory=lambda: UUID(TOKEN),
    )
    assert result["lease_key"] == s14c.lease_key_for_slate(SLATE)
    call = box["connection"].cursor_obj.calls[-1]
    assert call[1] == (s14c.lease_key_for_slate(SLATE), "worker-a", TOKEN, 300, 300)


def test_acquire_duplicate_unexpired_lease_fails_closed():
    factory, box = factory_for([
        lease_schema_step(),
        {"contains": "INSERT INTO", "fetchone": None},
    ])
    with pytest.raises(s14c.MLBStep14CLeaseUnavailableError):
        s14c.acquire_step14c_lease(
            slate_date=SLATE,
            owner_id="worker-b",
            env=safe_env(),
            connection_factory=factory,
            token_factory=lambda: TOKEN2,
        )
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: ("bad-key",) + row[1:],
        lambda row: (row[0], "other-owner") + row[2:],
        lambda row: row[:2] + ("not-a-uuid",) + row[3:],
        lambda row: row[:3] + (0,) + row[4:],
        lambda row: row[:4] + ("2026-09-01T12:06:00Z",) + row[5:],
        lambda row: row[:5] + ("2026-09-01T12:06:00Z", "2026-09-01T12:05:00Z"),
    ],
)
def test_acquire_rejects_tampered_lease_rows(mutation):
    factory, _ = factory_for(acquire_script(row=mutation(lease_row())))
    with pytest.raises(s14c.MLBStep14CDurableRuntimeIntegrityError):
        s14c.acquire_step14c_lease(
            slate_date=SLATE,
            owner_id="worker-a",
            env=safe_env(),
            connection_factory=factory,
            token_factory=lambda: TOKEN,
        )


def test_renew_preserves_fencing_generation_and_token():
    renewed_row = lease_row(
        renewed="2026-09-01T12:01:00+00:00",
        expires="2026-09-01T12:06:00+00:00",
    )
    factory, box = factory_for(renew_script(renewed_row))
    renewed = s14c.renew_step14c_lease(
        handle=safe_lease_handle(), env=safe_env(), connection_factory=factory
    )
    assert renewed["lease_token"] == TOKEN
    assert renewed["fencing_generation"] == 1
    assert box["connection"].commits == 1


def test_renew_lost_or_expired_lease_fails_closed():
    factory, box = factory_for([
        lease_schema_step(),
        {"contains": "UPDATE", "fetchone": None},
    ])
    with pytest.raises(s14c.MLBStep14CLeaseLostError):
        s14c.renew_step14c_lease(
            handle=safe_lease_handle(), env=safe_env(), connection_factory=factory
        )
    assert box["connection"].commits == 0


@pytest.mark.parametrize(
    "field,bad",
    [
        ("lease_key", ""),
        ("owner_id", ""),
        ("owner_id", "x" * 256),
        ("lease_token", "bad"),
        ("fencing_generation", 0),
        ("fencing_generation", True),
        ("fencing_generation", "1"),
    ],
)
def test_renew_rejects_invalid_handle(field, bad):
    handle = safe_lease_handle()
    handle[field] = bad
    with pytest.raises(s14c.MLBStep14CDurableRuntimeInputError):
        s14c.renew_step14c_lease(
            handle=handle, env=safe_env(), connection_factory=lambda: None
        )


def test_release_exact_owner_token_generation_succeeds():
    factory, box = factory_for(release_script())
    assert s14c.release_step14c_lease(
        handle=safe_lease_handle(), env=safe_env(), connection_factory=factory
    ) is True
    assert box["connection"].commits == 1


@pytest.mark.parametrize("row", [None, (), ("wrong-key",)])
def test_release_stale_owner_fails_closed(row):
    factory, box = factory_for([
        lease_schema_step(),
        {"contains": "DELETE", "fetchone": row},
    ])
    with pytest.raises(s14c.MLBStep14CLeaseLostError):
        s14c.release_step14c_lease(
            handle=safe_lease_handle(), env=safe_env(), connection_factory=factory
        )
    assert box["connection"].commits == 0


def test_fresh_restart_context_acquires_lease_then_returns_version_zero():
    context = fresh_context()
    assert context["status"] == "fresh_start"
    assert context["found"] is False
    assert context["loaded_checkpoint_version"] is None
    assert context["expected_head_version"] == 0
    assert context["scheduler_state_for_restart"] is None
    assert context["recovery_state_for_restart"] is None
    assert context["recovery_handoff_for_restart"] is None
    assert context["lease"]["fencing_generation"] == 1
    assert s14c.validate_step14c_restart_context(context)["context_valid"] is True


def test_recovered_restart_context_restores_exact_step14a_state():
    envelope = checkpoint_envelope()
    context = recovered_context(envelope)
    assert context["status"] == "recovered"
    assert context["found"] is True
    assert context["loaded_checkpoint_version"] == 1
    assert context["expected_head_version"] == 1
    assert context["checkpoint_envelope"] == envelope
    assert context["scheduler_state_for_restart"] == envelope["scheduler_state"]
    assert context["recovery_state_for_restart"] == envelope["recovery_state"]
    assert context["recovery_handoff_for_restart"] == envelope["recovery_handoff"]


def test_restart_inputs_are_deep_copy_isolated():
    context = recovered_context()
    inputs = s14c.restart_inputs_from_context(context)
    original_cycle = context["scheduler_state_for_restart"]["active_cycle_id"]
    inputs["scheduler_state"]["active_cycle_id"] = "0" * 64
    inputs["lease"]["owner_id"] = "changed"
    assert context["scheduler_state_for_restart"]["active_cycle_id"] == original_cycle
    assert context["lease"]["owner_id"] == "worker-a"


@pytest.mark.parametrize(
    "field,bad",
    [
        ("data_type", "bad"), ("schema_version", 999),
        ("runtime_version", "bad"), ("runtime_status", "bad"),
        ("runtime_mode", "PRODUCTION"), ("status", "bad"),
        ("slate_date", "2025-09-01"), ("checkpoint_key", "bad"),
        ("found", "yes"), ("expected_head_version", -1),
        ("expected_head_version", True), ("checkpoint_id", "bad"),
        ("envelope_content_sha256", "0" * 64),
        ("scheduler_state_sha256", "0" * 64),
        ("recovery_state_sha256", "0" * 64),
        ("recovery_handoff_sha256", "0" * 64),
        ("lineage", {}), ("guardrails", {}), ("generated_at_utc", "bad"),
    ],
)
def test_recovered_context_tamper_fails_validation(field, bad):
    context = recovered_context()
    context[field] = bad
    rehash_context(context)
    assert s14c.validate_step14c_restart_context(context)["context_valid"] is False


@pytest.mark.parametrize(
    "field",
    [
        "checkpoint_id", "envelope_content_sha256", "scheduler_state_sha256",
        "recovery_state_sha256", "recovery_handoff_sha256", "checkpoint_envelope",
        "scheduler_state_for_restart", "recovery_state_for_restart",
        "recovery_handoff_for_restart",
    ],
)
def test_fresh_context_rejects_checkpoint_payload(field):
    context = fresh_context()
    context[field] = {} if "state" in field or "envelope" in field or "handoff" in field else "x"
    rehash_context(context)
    assert s14c.validate_step14c_restart_context(context)["context_valid"] is False


def test_context_missing_or_unknown_fields_fail_closed():
    context = fresh_context()
    context.pop("lease")
    assert s14c.validate_step14c_restart_context(context)["context_valid"] is False
    context = fresh_context()
    context["extra"] = 1
    assert s14c.validate_step14c_restart_context(context)["context_valid"] is False


def test_context_hash_tamper_fails_closed():
    context = recovered_context()
    context["restart_context_sha256"] = "0" * 64
    assert s14c.validate_step14c_restart_context(context)["context_valid"] is False


def test_initial_checkpoint_persist_under_lease_creates_version_one():
    context = fresh_context()
    envelope = checkpoint_envelope()
    lease_factory, lease_box = factory_for(renew_script())
    cp_factory, cp_box = factory_for(save_initial_script())
    result = s14c.persist_step14c_checkpoint_under_lease(
        restart_context=context,
        checkpoint_envelope=envelope,
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
        generated_at_utc="2026-09-01T12:00:07Z",
    )
    assert result["status"] == "persisted"
    assert result["previous_checkpoint_version"] == 0
    assert result["saved_checkpoint_version"] == 1
    assert result["saved_checkpoint_status"] == "created"
    assert lease_box["connection"].commits == 1
    assert cp_box["connection"].commits == 1
    assert s14c.validate_step14c_persist_result(result)["result_valid"] is True


def test_recovered_checkpoint_persist_advances_exactly_one_version():
    old = checkpoint_envelope()
    new = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:30Z",
        created_at_utc="2026-09-01T12:00:35Z",
    )
    context = recovered_context(old, 1)
    lease_factory, _ = factory_for(renew_script())
    cp_factory, _ = factory_for(save_advance_script(old, 1))
    result = s14c.persist_step14c_checkpoint_under_lease(
        restart_context=context,
        checkpoint_envelope=new,
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
        generated_at_utc="2026-09-01T12:00:36Z",
    )
    assert result["previous_checkpoint_version"] == 1
    assert result["saved_checkpoint_version"] == 2
    assert result["saved_checkpoint_status"] == "advanced"


def test_same_envelope_persist_is_idempotent():
    old = checkpoint_envelope()
    context = recovered_context(old, 1)
    lease_factory, _ = factory_for(renew_script())
    cp_factory, cp_box = factory_for([
        checkpoint_schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 1)},
    ])
    result = s14c.persist_step14c_checkpoint_under_lease(
        restart_context=context,
        checkpoint_envelope=old,
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
    )
    assert result["saved_checkpoint_status"] == "idempotent"
    assert result["saved_checkpoint_version"] == 1
    assert cp_box["connection"].commits == 0


def test_stale_context_cas_conflict_fails_closed():
    old = checkpoint_envelope()
    current = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:00:30Z",
        created_at_utc="2026-09-01T12:00:35Z",
    )
    new = checkpoint_envelope(
        evaluated_at_utc="2026-09-01T12:01:00Z",
        created_at_utc="2026-09-01T12:01:05Z",
    )
    context = recovered_context(old, 1)
    lease_factory, _ = factory_for(renew_script())
    cp_factory, cp_box = factory_for([
        checkpoint_schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": head_row(current, 2)},
    ])
    with pytest.raises(step14b.MLBStep14BDatabaseConflictError):
        s14c.persist_step14c_checkpoint_under_lease(
            restart_context=context,
            checkpoint_envelope=new,
            env=safe_env(),
            lease_connection_factory=lease_factory,
            checkpoint_connection_factory=cp_factory,
        )
    assert cp_box["connection"].commits == 0
    assert cp_box["connection"].rollbacks >= 1


def test_lost_lease_fences_checkpoint_persist_before_database_save():
    context = fresh_context()
    lease_factory, _ = factory_for([
        lease_schema_step(),
        {"contains": "UPDATE", "fetchone": None},
    ])
    called = {"checkpoint": 0}

    def checkpoint_factory():
        called["checkpoint"] += 1
        raise AssertionError("checkpoint save must not run after lease loss")

    with pytest.raises(s14c.MLBStep14CLeaseLostError):
        s14c.persist_step14c_checkpoint_under_lease(
            restart_context=context,
            checkpoint_envelope=checkpoint_envelope(),
            env=safe_env(),
            lease_connection_factory=lease_factory,
            checkpoint_connection_factory=checkpoint_factory,
        )
    assert called["checkpoint"] == 0


def test_persist_rejects_tampered_envelope_before_database_work():
    context = fresh_context()
    envelope = checkpoint_envelope()
    envelope["checkpoint_key"] = "bad"
    with pytest.raises(s14c.MLBStep14CDurableRuntimeIntegrityError):
        s14c.persist_step14c_checkpoint_under_lease(
            restart_context=context,
            checkpoint_envelope=envelope,
            env=safe_env(),
            lease_connection_factory=lambda: None,
            checkpoint_connection_factory=lambda: None,
        )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("data_type", "bad"), ("schema_version", 999),
        ("runtime_version", "bad"), ("runtime_status", "bad"),
        ("runtime_mode", "PRODUCTION"), ("status", "bad"),
        ("slate_date", "2025-09-01"), ("checkpoint_key", "bad"),
        ("previous_checkpoint_version", -1), ("saved_checkpoint_version", 0),
        ("saved_checkpoint_status", "bad"), ("saved_checkpoint_id", "bad"),
        ("saved_envelope_content_sha256", "bad"),
        ("scheduler_state_sha256", "bad"), ("recovery_state_sha256", "bad"),
        ("recovery_handoff_sha256", "bad"), ("lineage", {}),
        ("guardrails", {}), ("generated_at_utc", "bad"),
    ],
)
def test_persist_result_tamper_fails_validation(field, bad):
    context = fresh_context()
    envelope = checkpoint_envelope()
    lease_factory, _ = factory_for(renew_script())
    cp_factory, _ = factory_for(save_initial_script())
    result = s14c.persist_step14c_checkpoint_under_lease(
        restart_context=context,
        checkpoint_envelope=envelope,
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
        generated_at_utc="2026-09-01T12:00:07Z",
    )
    result[field] = bad
    rehash_persist_result(result)
    assert s14c.validate_step14c_persist_result(result)["result_valid"] is False


def test_persist_result_hash_tamper_fails_closed():
    context = fresh_context()
    envelope = checkpoint_envelope()
    lease_factory, _ = factory_for(renew_script())
    cp_factory, _ = factory_for(save_initial_script())
    result = s14c.persist_step14c_checkpoint_under_lease(
        restart_context=context,
        checkpoint_envelope=envelope,
        env=safe_env(),
        lease_connection_factory=lease_factory,
        checkpoint_connection_factory=cp_factory,
    )
    result["persist_result_sha256"] = "0" * 64
    assert s14c.validate_step14c_persist_result(result)["result_valid"] is False


def test_no_live_database_dsn_required_with_injected_factories():
    factory, _ = factory_for(acquire_script())
    env = safe_env()
    env.pop("KYRE_DATABASE_URL", None)
    result = s14c.acquire_step14c_lease(
        slate_date=SLATE,
        owner_id="worker-a",
        env=env,
        connection_factory=factory,
        token_factory=lambda: TOKEN,
    )
    assert result["lease_token"] == TOKEN


def test_live_database_without_dsn_fails_closed():
    env = safe_env()
    env.pop("KYRE_DATABASE_URL", None)
    with pytest.raises(s14c.MLBStep14CDurableRuntimeDisabledError):
        s14c.acquire_step14c_lease(
            slate_date=SLATE,
            owner_id="worker-a",
            env=env,
            connection_factory=None,
            token_factory=lambda: TOKEN,
        )


def test_step14c_module_has_no_provider_or_background_execution_machinery():
    text = Path("sports_api/mlb_step14c_durable_restart_lease_v1.py").read_text()
    banned = [
        "import requests", "import httpx", "import urllib", "import socket",
        "import threading", "import multiprocessing", "import apscheduler",
        "time.sleep(", "asyncio.create_task", "threading.Thread",
        "multiprocessing.", "subprocess.", "Popen(", "os.system(",
    ]
    for needle in banned:
        assert needle not in text


def test_lease_schema_is_additive_only_and_does_not_touch_checkpoint_tables():
    text = Path(s14c.LEASE_SQL_SCHEMA_PATH).read_text()
    assert "CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_leases" in text
    assert "ALTER TABLE" not in text.upper()
    assert "DROP TABLE" not in text.upper()
    assert "mlb_runtime_checkpoints (" not in text
    assert "mlb_runtime_checkpoint_heads (" not in text


@pytest.mark.parametrize(
    "key",
    [
        "production_activation", "public_api_activation", "actionable_output",
        "background_worker", "background_thread", "supabase_rest_write",
        "runtime_cycle_executed", "retry_executed", "restart_executed",
    ],
)
def test_restart_context_forbidden_guardrails_remain_false(key):
    assert fresh_context()["guardrails"][key] is False


@pytest.mark.parametrize(
    "key",
    [
        "explicit_foreground_restart_context", "durable_restart_recovery",
        "durable_distributed_lease", "cross_process_duplicate_run_guard",
        "fencing_generation_enforced", "lease_expiry_enforced",
        "lease_revalidated_before_checkpoint_save", "checkpoint_cas_enforced",
        "append_only_checkpoint_history",
    ],
)
def test_restart_context_required_guardrails_are_true(key):
    assert fresh_context()["guardrails"][key] is True


def test_restart_context_network_call_counters_are_zero():
    context = fresh_context()
    assert context["guardrails"]["provider_network_calls"] == 0
    assert context["guardrails"]["sportsbook_network_calls"] == 0


def test_step14c_never_changes_parent_source_files():
    assert Path("sports_api/mlb_step14a_persistence_contract_v1.py").exists()
    assert Path("sports_api/mlb_step14b_database_checkpoint_adapter_v1.py").exists()
