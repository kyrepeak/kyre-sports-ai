from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from sports_api import mlb_step16d_controlled_production_activation_v1 as step16d
from sports_api import mlb_step16e_final_production_freeze_v1 as step16e


def safe_env() -> dict[str, str]:
    return {
        step16e.STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV: "true",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED": "false",
        "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED": "false",
        "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED": "false",
        "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED": "false",
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "false",
        "MLB_STEP14B_DATABASE_READ_ENABLED": "false",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED": "false",
    }


def canonical(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def test_01_default_off() -> None:
    assert step16e.DEFAULT_ENABLED is False
    assert step16e.step16e_freeze_enabled({}) is False


def test_02_exact_step16d_tested_head_and_merge_are_pinned() -> None:
    assert step16e.STEP16D_TESTED_HEAD_SHA == "b325ddeb1df0d23fcdebf7b1d498ef473a0054f5"
    assert step16e.STEP16D_MAIN_MERGE_SHA == "4261c872cc94c55a466b7e1bb9d80e62abdc95c8"


def test_03_step16d_contract_and_marker_are_exact() -> None:
    assert step16d.CONTRACT_ID == step16e.STEP16D_CONTRACT_ID
    assert step16d.FINAL_CERTIFICATION_MARKER == step16e.STEP16D_FINAL_MARKER
    assert step16d.RUNTIME_MODE == step16e.RUNTIME_MODE == "SHADOW_ONLY"


def test_04_final_release_identity_is_exact() -> None:
    assert step16e.RELEASE_ID == "mlb_step16_controlled_production_activation_2026_regular_season_frozen_v1"
    assert step16e.FINAL_CERTIFICATION_MARKER == "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_GREEN"


def test_05_final_evidence_hash_is_exact() -> None:
    evidence = step16e.load_step16e_final_evidence()
    surface = deepcopy(evidence)
    surface.pop("evidence_content_sha256", None)
    assert canonical(surface) == step16e.FINAL_EVIDENCE_CONTENT_SHA256


def test_06_final_live_runtime_tables_are_present_and_empty() -> None:
    live = step16e.validate_step16e_final_evidence(
        step16e.load_step16e_final_evidence()
    )["final_live_state"]
    assert live["checkpoints_present"] is True
    assert live["heads_present"] is True
    assert live["leases_present"] is True
    assert (live["checkpoint_rows"], live["checkpoint_head_rows"], live["lease_rows"]) == (0, 0, 0)


def test_07_runtime_schema_privileges_remain_server_only() -> None:
    live = step16e.load_step16e_final_evidence()["final_live_state"]
    assert live["postgres_schema_usage"] is True
    assert live["anon_schema_usage"] is False
    assert live["authenticated_schema_usage"] is False
    assert live["service_role_schema_usage"] is False


def test_08_step16d_live_result_and_artifact_digest_are_frozen() -> None:
    parent = step16e.load_step16e_final_evidence()["step16d_certification"]
    assert parent["live_result_content_sha256"] == step16e.STEP16D_LIVE_RESULT_CONTENT_SHA256
    assert parent["artifact_digest_sha256"] == step16e.STEP16D_ARTIFACT_DIGEST_SHA256
    assert parent["artifact_id"] == step16e.STEP16D_ARTIFACT_ID


def test_09_step16d_two_cycle_restart_lineage_is_exact() -> None:
    parent = step16e.load_step16e_final_evidence()["step16d_certification"]
    assert parent["cycle_count"] == 2
    assert parent["cycle_1_saved_version"] == 1
    assert parent["cycle_2_recovered_version"] == 1
    assert parent["cycle_2_saved_version"] == 2
    assert parent["two_cycle_durable_restart_certified"] is True


def test_10_step16d_cleanup_and_fencing_are_certified() -> None:
    parent = step16e.load_step16e_final_evidence()["step16d_certification"]
    assert parent["checkpoint_history_rows_before_cleanup"] == 2
    assert parent["checkpoint_head_rows_before_cleanup"] == 1
    assert parent["lease_rows_before_cleanup"] == 0
    assert parent["checkpoint_rows_after_cleanup"] == 0
    assert parent["checkpoint_head_rows_after_cleanup"] == 0
    assert parent["lease_rows_after_cleanup"] == 0
    assert parent["fenced_lease_certified"] is True
    assert parent["checkpoint_cas_certified"] is True
    assert parent["zero_residue_certified"] is True


def test_11_step16_regression_counts_are_frozen() -> None:
    parent = step16e.load_step16e_final_evidence()["step16d_certification"]
    assert parent["targeted_step16d_tests"] == 7
    assert parent["step16c_guard_tests"] == 12
    assert parent["step16b_guard_tests"] == 25
    assert parent["current_mlb_regression_tests"] == 3591


def test_12_full_step16_and_step15_lineage_is_frozen() -> None:
    evidence = step16e.load_step16e_final_evidence()
    assert evidence["lineage"] == {
        "step16c_main_merge_sha": step16e.STEP16C_MAIN_MERGE_SHA,
        "step16b_main_merge_sha": step16e.STEP16B_MAIN_MERGE_SHA,
        "step16a_certified_sha": step16e.STEP16A_CERTIFIED_SHA,
        "step15c_certified_main_sha": step16e.STEP15C_CERTIFIED_MAIN_SHA,
        "step15_release_id": step16e.STEP15_RELEASE_ID,
        "step15_release_manifest_sha256": step16e.STEP15_RELEASE_MANIFEST_SHA256,
    }


def test_13_release_safety_contract_is_all_false() -> None:
    assert step16e.SAFETY_CONTRACT
    assert all(value is False for value in step16e.SAFETY_CONTRACT.values())


def test_14_manifest_certifies_controlled_activation_not_continuous_host() -> None:
    manifest = step16e.validate_step16_release_manifest(
        step16e.build_step16_release_manifest(
            env=safe_env(), generated_at_utc="2026-09-01T22:15:00Z"
        )
    )
    assert manifest["certification"]["controlled_production_activation"] is True
    assert manifest["certification"]["direct_psycopg_live_connection"] is True
    assert manifest["certification"]["two_cycle_durable_restart"] is True
    assert manifest["certification"]["zero_residue"] is True
    assert manifest["scope_boundary"]["continuous_production_runtime_started"] is False
    assert manifest["scope_boundary"]["production_scheduler_started"] is False
    assert manifest["scope_boundary"]["hosted_always_on_service_certified"] is False


def test_15_manifest_freezes_step16_as_complete() -> None:
    manifest = step16e.build_step16_release_manifest(env=safe_env())
    assert manifest["phase_boundary"]["step16_complete"] is True
    assert manifest["phase_boundary"]["final_controlled_production_freeze"] is True
    assert manifest["phase_boundary"]["continuous_hosted_runtime_intentionally_not_activated"] is True
    assert manifest["phase_boundary"]["future_hosted_always_on_step_required"] is True


def test_16_release_hash_is_stable_across_generation_time() -> None:
    first = step16e.build_step16_release_manifest(
        env=safe_env(), generated_at_utc="2026-09-01T22:15:00Z"
    )
    second = step16e.build_step16_release_manifest(
        env=safe_env(), generated_at_utc="2026-09-02T02:15:00Z"
    )
    assert first["generated_at_utc"] != second["generated_at_utc"]
    assert first["release_content_sha256"] == second["release_content_sha256"]


def test_17_step16e_explicit_gate_is_required() -> None:
    env = safe_env()
    env[step16e.STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV] = "false"
    with pytest.raises(step16e.MLBStep16EFreezeDisabledError):
        step16e.build_step16_release_manifest(env=env)


def test_18_live_runtime_switches_and_database_secret_are_refused() -> None:
    for key in (
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
        "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED",
    ):
        env = safe_env()
        env[key] = "true"
        with pytest.raises(step16e.MLBStep16EFreezeDisabledError):
            step16e.build_step16_release_manifest(env=env)
    env = safe_env()
    env["KYRE_DATABASE_URL"] = "postgresql://should-not-be-used.invalid/postgres"
    with pytest.raises(step16e.MLBStep16EFreezeDisabledError):
        step16e.build_step16_release_manifest(env=env)


def test_19_evidence_tamper_fails_closed() -> None:
    evidence = step16e.load_step16e_final_evidence()
    tampered = deepcopy(evidence)
    tampered["final_live_state"]["lease_rows"] = 1
    with pytest.raises(step16e.MLBStep16EFreezeIntegrityError):
        step16e.validate_step16e_final_evidence(tampered)


def test_20_manifest_tamper_fails_closed() -> None:
    manifest = step16e.build_step16_release_manifest(env=safe_env())
    tampered = deepcopy(manifest)
    tampered["scope_boundary"]["continuous_production_runtime_started"] = True
    with pytest.raises(step16e.MLBStep16EFreezeIntegrityError):
        step16e.validate_step16_release_manifest(tampered)
