from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step16b_packaging_lifecycle_contract_v1 as step16b_contract
from sports_api import mlb_step16b_production_lifecycle_v1 as lifecycle
from sports_api import mlb_step16c_live_postgresql_canary_v1 as step16c
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

def safe_env() -> dict[str, str]:
    return {
        step16c.STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED_ENV: "true",
        lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true",
        step14c.STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV: "true",
        step14b.STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV: "true",
        step14b.STEP14B_DATABASE_READ_ENABLED_ENV: "true",
        step14b.STEP14B_DATABASE_WRITE_ENABLED_ENV: "true",
        lifecycle.DATABASE_URL_ENV: "postgresql://user:password@example.invalid:5432/postgres",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
    }

def test_01_default_off() -> None:
    assert step16c.DEFAULT_ENABLED is False
    assert step16c.step16c_live_postgresql_canary_enabled({}) is False

def test_02_exact_step16b_parent_is_pinned() -> None:
    assert step16c.STEP16C_BASE_MAIN_SHA == "eb0ea430caea02f90b6367b8bc0ea28f698246bf"
    assert step16b_contract.FINAL_CERTIFICATION_MARKER == step16c.STEP16B_FINAL_MARKER

def test_03_explicit_step16c_gate_required() -> None:
    with pytest.raises(step16c.MLBStep16CCanaryDisabledError):
        step16c.validate_step16c_enablement({})

def test_04_database_secret_required() -> None:
    env = safe_env()
    env.pop(lifecycle.DATABASE_URL_ENV)
    with pytest.raises(step16c.MLBStep16CCanaryDisabledError):
        step16c.validate_step16c_enablement(env)

def test_05_all_parent_persistence_gates_required() -> None:
    for key in step16c._REQUIRED_TRUE_ENV_KEYS:
        env = safe_env()
        env[key] = "false"
        with pytest.raises(step16c.MLBStep16CCanaryDisabledError):
            step16c.validate_step16c_enablement(env)

def test_06_production_switches_refused() -> None:
    for key in step16c._FORBIDDEN_TRUE_ENV_KEYS:
        env = safe_env()
        env[key] = "true"
        with pytest.raises(step16c.MLBStep16CCanaryDisabledError):
            step16c.validate_step16c_enablement(env)

def test_07_safe_enablement_binds_without_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "persistence_driver_available", lambda: True)
    source = step16c.validate_step16c_enablement(safe_env())
    assert source[step16c.STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED_ENV] == "true"
    assert source["MLB_PRODUCTION_RUNTIME_ENABLED"] == "false"
    assert source["MLB_PRODUCTION_SCHEDULER_ENABLED"] == "false"

def test_08_step16b_still_records_canary_as_not_executed() -> None:
    assert step16b_contract.STEP16C_LIVE_CANARY_REQUIRED is True
    assert step16b_contract.LIVE_CANARY_EXECUTED is False
    assert lifecycle.PRODUCTION_ACTIVATION_ALLOWED is False

def test_09_protected_invariants_remain_false() -> None:
    assert PROTECTED_INVARIANTS
    assert all(value is False for value in PROTECTED_INVARIANTS.values())

def test_10_canary_capability_is_narrow() -> None:
    assert step16c.PACKAGED_FASTAPI_LIFECYCLE_CANARY_ALLOWED is True
    assert step16c.DIRECT_PSYCOG_CONNECTION_ALLOWED is True
    assert step16c.CHECKPOINT_READ_ALLOWED is True
    assert step16c.TEMPORARY_DURABLE_LEASE_ALLOWED is True
    assert step16c.CHECKPOINT_WRITE_ALLOWED is False
    assert step16c.PRODUCTION_RUNTIME_ALLOWED is False
    assert step16c.PRODUCTION_SCHEDULER_ALLOWED is False
    assert step16c.PRODUCTION_ACTIVATION_ALLOWED is False

def test_11_evidence_hash_ignores_observation_time() -> None:
    base = {
        "data_type": step16c.DATA_TYPE,
        "observed_at_utc": "2026-09-01T22:00:00Z",
        "value": {"ok": True},
    }
    first = step16c._hash(step16c._evidence_hash_surface(base))
    changed = deepcopy(base)
    changed["observed_at_utc"] = "2026-09-02T01:00:00Z"
    second = step16c._hash(step16c._evidence_hash_surface(changed))
    assert first == second

def test_12_canary_slate_uses_frozen_lease_key_contract() -> None:
    key = step14c.lease_key_for_slate(step16c.DEFAULT_CANARY_SLATE_DATE)
    assert key.endswith(":scheduler-recovery-lease")
