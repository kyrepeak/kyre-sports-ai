from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from sports_api import mlb_step16a_production_activation_contract_v1 as s16a


def safe_env() -> dict[str, str]:
    return {
        s16a.STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV: "true",
        "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED": "true",
        "MLB_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED": "true",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
    }


def test_01_default_off() -> None:
    assert s16a.DEFAULT_ENABLED is False
    assert s16a.step16a_production_activation_contract_enabled({}) is False


def test_02_exact_frozen_step15c_parent() -> None:
    assert s16a.STEP15C_CERTIFIED_MAIN_SHA == "a67d415e5e1d8614d632fd34cfa09d551792a71f"
    assert s16a.STEP15C_SOURCE_BLOB_SHA == "2ba73d80704054a5de8da4ea6daab8b9537bc7e0"


def test_03_step15_release_identity_and_hash() -> None:
    assert s16a.STEP15_RELEASE_ID == "mlb_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
    assert s16a.STEP15_RELEASE_MANIFEST_SHA256 == "d5c184988de8db66af6ef2c4e158dd8016a3403f968d42296f41dfa69bf83ada"


def test_04_readiness_evidence_hash_is_frozen() -> None:
    evidence = s16a.load_step16a_readiness_evidence()
    assert evidence["evidence_content_sha256"] == s16a.EVIDENCE_CONTENT_SHA256


def test_05_deployment_file_identities_are_exact() -> None:
    evidence = s16a.load_step16a_readiness_evidence()
    assert evidence["deployment_files"] == s16a.EXPECTED_DEPLOYMENT_BLOBS


def test_06_existing_container_contract_is_preserved() -> None:
    observed = s16a.inspect_current_deployment_surface()
    assert observed["container_runtime"] is True
    assert observed["uvicorn_entrypoint"] == "sports_api.main:app"
    assert observed["default_web_concurrency"] == 2
    assert observed["deployment_replica_count"] == 1
    assert observed["hosted_staging_provider"] == "render"
    assert observed["persistent_volume_root"] == "/var/lib/kyre-sports-api"


def test_07_persistence_requirement_is_defined() -> None:
    observed = s16a.inspect_current_deployment_surface()
    assert observed["persistence_requirement_defined"] is True
    assert observed["persistence_requirement"] == "psycopg[binary]>=3.2,<4"


def test_08_docker_currently_misses_mlb_persistence_dependency() -> None:
    observed = s16a.inspect_current_deployment_surface()
    assert observed["docker_installs_base_requirements"] is True
    assert observed["docker_installs_mlb_persistence_requirements"] is False


def test_09_production_env_currently_misses_database_url_contract() -> None:
    observed = s16a.inspect_current_deployment_surface()
    assert observed["production_env_declares_kyre_database_url"] is False


def test_10_mlb_activation_switch_defaults_are_not_packaged_yet() -> None:
    observed = s16a.inspect_current_deployment_surface()
    assert observed["mlb_production_runtime_default_off"] is False
    assert observed["mlb_production_scheduler_default_off"] is False


def test_11_fastapi_startup_does_not_bind_step13_to_step15_runtime() -> None:
    observed = s16a.inspect_current_deployment_surface()
    assert observed["fastapi_startup_binds_step13_to_step15_runtime"] is False


def test_12_exact_four_blockers_are_certified() -> None:
    evidence = s16a.validate_step16a_readiness_evidence(s16a.load_step16a_readiness_evidence())
    assert tuple(evidence["blocking_requirements"]) == s16a.BLOCKING_REQUIREMENTS
    assert len(s16a.BLOCKING_REQUIREMENTS) == 4


def test_13_production_activation_is_not_ready() -> None:
    evidence = s16a.load_step16a_readiness_evidence()
    assert evidence["readiness_findings"]["production_activation_ready"] is False
    assert s16a.PRODUCTION_ACTIVATION_ALLOWED is False
    assert s16a.PRODUCTION_CANARY_ALLOWED is False


def test_14_step15_live_certifications_are_preserved() -> None:
    findings = s16a.load_step16a_readiness_evidence()["readiness_findings"]
    assert findings["live_step15_schema_certified"] is True
    assert findings["live_step15_transactions_certified"] is True
    assert findings["live_step15_release_frozen"] is True


def test_15_activation_boundary_is_all_false() -> None:
    activation = s16a.load_step16a_readiness_evidence()["activation_boundary"]
    assert activation
    assert all(value is False for value in activation.values())
    assert all(value is False for value in s16a.SAFETY_CONTRACT.values())


def test_16_future_canary_prerequisites_are_explicit() -> None:
    manifest = s16a.build_step16a_production_activation_contract(env=safe_env())
    required = manifest["required_before_any_future_production_canary"]
    assert required["install_psycopg_in_production_image"] is True
    assert required["supply_kyre_database_url_via_deployment_secret_manager"] is True
    assert required["never_commit_database_secret"] is True
    assert required["declare_mlb_production_runtime_default_off"] is True
    assert required["declare_mlb_production_scheduler_default_off"] is True
    assert required["require_durable_lease_before_scheduler_execution"] is True
    assert required["recover_valid_checkpoint_before_first_scheduler_cycle"] is True


def test_17_frozen_step15_manifest_is_revalidated() -> None:
    manifest = s16a.build_step16a_production_activation_contract(env=safe_env(), generated_at_utc="2026-09-01T21:07:00+00:00")
    assert manifest["lineage"]["step15_release_manifest_sha256"] == s16a.STEP15_RELEASE_MANIFEST_SHA256
    assert manifest["phase_boundary"]["step15_complete_and_frozen"] is True


def test_18_contract_hash_is_stable_across_generation_time() -> None:
    first = s16a.build_step16a_production_activation_contract(env=safe_env(), generated_at_utc="2026-09-01T21:07:00+00:00")
    second = s16a.build_step16a_production_activation_contract(env=safe_env(), generated_at_utc="2026-09-02T03:07:00+00:00")
    assert first["generated_at_utc"] != second["generated_at_utc"]
    assert first["contract_content_sha256"] == second["contract_content_sha256"]


def test_19_step16a_gate_is_required() -> None:
    with pytest.raises(s16a.MLBStep16AProductionActivationContractDisabledError):
        s16a.build_step16a_production_activation_contract(env={})


def test_20_frozen_parent_gates_are_required() -> None:
    env = safe_env()
    env["MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED"] = "false"
    with pytest.raises(s16a.MLBStep16AProductionActivationContractDisabledError):
        s16a.build_step16a_production_activation_contract(env=env)


def test_21_unsafe_runtime_switches_are_refused() -> None:
    keys = (
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_SUPABASE_REST_WRITE_ENABLED",
    )
    for key in keys:
        env = safe_env()
        env[key] = "true"
        with pytest.raises(s16a.MLBStep16AProductionActivationContractDisabledError):
            s16a.build_step16a_production_activation_contract(env=env)


def test_22_evidence_tamper_fails_closed() -> None:
    evidence = deepcopy(s16a.load_step16a_readiness_evidence())
    evidence["readiness_findings"]["production_activation_ready"] = True
    with pytest.raises(s16a.MLBStep16AProductionActivationContractIntegrityError):
        s16a.validate_step16a_readiness_evidence(evidence)


def test_23_safety_constant_drift_fails_closed() -> None:
    with patch.object(s16a, "PRODUCTION_ACTIVATION_ALLOWED", True):
        with pytest.raises(s16a.MLBStep16AProductionActivationContractIntegrityError):
            s16a.build_step16a_production_activation_contract(env=safe_env())
