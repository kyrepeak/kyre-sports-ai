from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sports_api import mlb_step13a_bounded_scheduler_v1 as step13a
from sports_api import mlb_step13b_runtime_supervisor_v1 as step13b
from sports_api import mlb_step13c_reliability_recovery_v1 as step13c
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step16b_packaging_lifecycle_contract_v1 as contract
from sports_api import mlb_step16b_production_lifecycle_v1 as lifecycle
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS


def safe_enabled_env() -> dict[str, str]:
    return {
        lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true",
        lifecycle.DATABASE_URL_ENV: "postgresql://user:password@example.invalid:5432/postgres",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
    }


def test_01_default_off() -> None:
    assert lifecycle.DEFAULT_ENABLED is False
    assert lifecycle.step16b_durable_lifecycle_enabled({}) is False
    assert lifecycle.get_step16b_runtime_binding({}) is None


def test_02_exact_step16a_lineage_is_pinned() -> None:
    assert lifecycle.STEP16A_CERTIFIED_MAIN_SHA == "c5ad6047224aaf014cec13f5efa6e5cd650da939"
    assert lifecycle.STEP16A_SOURCE_BLOB_SHA == "a8ce0bfef0918fd471c383964ccbf0f99f13611f"
    assert lifecycle.STEP16A_CONTRACT_CONTENT_SHA256 == "fc5d15c1d38367c76d4fb7dc1ed611dea001d2b48459af3afc297e432c686a1d"


def test_03_step15_release_lineage_is_preserved() -> None:
    assert lifecycle.STEP15C_CERTIFIED_MAIN_SHA == "a67d415e5e1d8614d632fd34cfa09d551792a71f"
    assert lifecycle.STEP15_RELEASE_MANIFEST_SHA256 == "d5c184988de8db66af6ef2c4e158dd8016a3403f968d42296f41dfa69bf83ada"


def test_04_evidence_hash_is_frozen() -> None:
    evidence = contract.load_step16b_evidence()
    assert evidence["evidence_content_sha256"] == contract.EVIDENCE_CONTENT_SHA256


def test_05_deployment_blob_identities_are_exact() -> None:
    assert contract.validate_step16b_packaging_files() == contract.EXPECTED_BLOB_SHAS


def test_06_container_packages_psycopg_requirement() -> None:
    docker = Path(contract.DOCKERFILE_PATH).read_text(encoding="utf-8")
    assert "requirements-mlb-step14b-persistence.txt" in docker
    assert "pip install --no-cache-dir -r /app/sports_api/requirements-mlb-step14b-persistence.txt" in docker


def test_07_deployment_template_keeps_mlb_switches_off() -> None:
    text = Path(contract.ENV_EXAMPLE_PATH).read_text(encoding="utf-8")
    for line in (
        "MLB_PRODUCTION_RUNTIME_ENABLED=false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED=false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED=false",
        "MLB_WAGERING_ENABLED=false",
        "MLB_SUPABASE_REST_WRITE_ENABLED=false",
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED=false",
    ):
        assert line in text


def test_08_database_secret_value_is_not_committed() -> None:
    text = Path(contract.ENV_EXAMPLE_PATH).read_text(encoding="utf-8")
    assert "Required secret-manager key: KYRE_DATABASE_URL" in text
    assert not contract._noncomment_assignment_exists(text, "KYRE_DATABASE_URL")


def test_09_fastapi_lifespan_is_bound() -> None:
    text = Path(contract.MAIN_PATH).read_text(encoding="utf-8")
    assert "from sports_api.mlb_step16b_production_lifecycle_v1 import step16b_lifespan" in text
    assert "lifespan=step16b_lifespan" in text


def test_10_disabled_status_executes_nothing() -> None:
    status = lifecycle.build_step16b_lifecycle_status({})
    assert status["enabled"] is False
    assert status["database_connected"] is False
    assert status["runtime_executed"] is False
    assert status["background_task_started"] is False
    assert status["production_activation"] is False


def test_11_explicit_gate_is_required() -> None:
    with pytest.raises(lifecycle.MLBStep16BLifecycleDisabledError):
        lifecycle.validate_step16b_enablement({})


def test_12_database_secret_is_required_only_when_enabled() -> None:
    env = safe_enabled_env()
    env.pop(lifecycle.DATABASE_URL_ENV)
    with pytest.raises(lifecycle.MLBStep16BLifecycleDisabledError):
        lifecycle.validate_step16b_enablement(env)


def test_13_invalid_database_scheme_fails_closed() -> None:
    env = safe_enabled_env()
    env[lifecycle.DATABASE_URL_ENV] = "https://example.invalid/postgres"
    with pytest.raises(lifecycle.MLBStep16BLifecycleIntegrityError):
        lifecycle.validate_step16b_enablement(env)


def test_14_production_switches_are_refused() -> None:
    for key in (
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_SUPABASE_REST_WRITE_ENABLED",
    ):
        env = safe_enabled_env()
        env[key] = "true"
        with pytest.raises(lifecycle.MLBStep16BLifecycleDisabledError):
            lifecycle.validate_step16b_enablement(env)


def test_15_enabled_binding_uses_exact_frozen_modules() -> None:
    binding = lifecycle.get_step16b_runtime_binding(safe_enabled_env())
    assert binding is not None
    expected = {
        "scheduler_tick": step13a.__name__,
        "runtime_supervision": step13b.__name__,
        "recovery_decision": step13c.__name__,
        "load_restart_context": step14c.__name__,
        "restart_inputs": step14c.__name__,
        "persist_checkpoint": step14c.__name__,
        "renew_lease": step14c.__name__,
        "release_lease": step14c.__name__,
    }
    assert {name: fn.__module__ for name, fn in binding.items()} == expected


def test_16_enabled_status_binds_without_execution() -> None:
    status = lifecycle.build_step16b_lifecycle_status(safe_enabled_env())
    assert status["enabled"] is True
    assert status["status"] == "bound_not_executed"
    assert status["runtime_binding_count"] == 8
    assert status["database_connected"] is False
    assert status["runtime_executed"] is False
    assert status["credential_value_exposed"] is False


def test_17_lifespan_default_off_sets_and_clears_state() -> None:
    async def exercise() -> None:
        app = SimpleNamespace(state=SimpleNamespace())
        with patch.dict("os.environ", {}, clear=True):
            manager = lifecycle.step16b_lifespan(app)
            async with manager:
                assert app.state.mlb_step16b_lifecycle["enabled"] is False
                assert app.state.mlb_step16b_runtime_binding is None
            assert app.state.mlb_step16b_lifecycle["status"] == "shutdown_disabled"
            assert app.state.mlb_step16b_runtime_binding is None
    asyncio.run(exercise())


def test_18_lifespan_enabled_still_does_not_execute_runtime() -> None:
    async def exercise() -> None:
        app = SimpleNamespace(state=SimpleNamespace())
        with patch.dict("os.environ", safe_enabled_env(), clear=True):
            manager = lifecycle.step16b_lifespan(app)
            async with manager:
                status = app.state.mlb_step16b_lifecycle
                assert status["enabled"] is True
                assert status["database_connected"] is False
                assert status["runtime_executed"] is False
                assert app.state.mlb_step16b_runtime_binding is not None
            assert app.state.mlb_step16b_lifecycle["status"] == "shutdown_bound_never_executed"
            assert app.state.mlb_step16b_runtime_binding is None
    asyncio.run(exercise())


def test_19_all_step16a_blockers_are_closed() -> None:
    evidence = contract.validate_step16b_evidence(contract.load_step16b_evidence())
    blockers = evidence["blocker_resolution"]
    assert blockers["all_step16a_packaging_lifecycle_blockers_closed"] is True
    assert blockers["docker_installs_mlb_persistence_requirements"] is True
    assert blockers["deployment_secret_manager_contract_declares_kyre_database_url"] is True
    assert blockers["mlb_activation_switches_declared_default_off"] is True
    assert blockers["fastapi_lifespan_binds_frozen_step13_step14_runtime"] is True


def test_20_step16c_canary_is_still_required() -> None:
    manifest = contract.build_step16b_contract_manifest(generated_at_utc="2026-09-01T21:20:00+00:00")
    assert manifest["runtime_contract"]["production_activation_ready"] is False
    assert manifest["runtime_contract"]["step16c_live_canary_required"] is True
    assert manifest["phase_boundary"]["step16c_live_postgresql_canary_required"] is True


def test_21_safety_contract_is_all_false() -> None:
    assert contract.SAFETY_CONTRACT
    assert all(value is False for value in contract.SAFETY_CONTRACT.values())
    assert all(value is False for value in lifecycle.SAFETY_CONTRACT.values())


def test_22_protected_invariants_remain_false() -> None:
    assert PROTECTED_INVARIANTS
    assert all(value is False for value in PROTECTED_INVARIANTS.values())


def test_23_contract_hash_is_stable_across_generation_time() -> None:
    first = contract.build_step16b_contract_manifest(generated_at_utc="2026-09-01T21:20:00+00:00")
    second = contract.build_step16b_contract_manifest(generated_at_utc="2026-09-02T01:20:00+00:00")
    assert first["generated_at_utc"] != second["generated_at_utc"]
    assert first["contract_content_sha256"] == second["contract_content_sha256"]


def test_24_tampered_evidence_fails_closed() -> None:
    evidence = deepcopy(contract.load_step16b_evidence())
    evidence["activation_boundary"]["production_runtime_activated"] = True
    with pytest.raises(contract.MLBStep16BContractIntegrityError):
        contract.validate_step16b_evidence(evidence)


def test_25_packaging_contract_certifies_zero_startup_execution() -> None:
    manifest = contract.build_step16b_contract_manifest(generated_at_utc="2026-09-01T21:20:00+00:00")
    runtime = manifest["runtime_contract"]
    assert runtime["database_connection_on_app_startup"] is False
    assert runtime["scheduler_cycle_on_app_startup"] is False
    assert runtime["background_task_on_app_startup"] is False
    assert runtime["provider_calls_on_app_startup"] == 0
    assert runtime["sportsbook_calls_on_app_startup"] == 0
