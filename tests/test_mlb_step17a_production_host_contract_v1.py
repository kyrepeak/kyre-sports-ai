from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from sports_api import mlb_step16e_final_production_freeze_v1 as step16e
from sports_api import mlb_step17a_production_host_contract_v1 as step17a


def _api_service() -> dict:
    return {
        "id": step17a.EXPECTED_RENDER_SERVICE_ID,
        "name": step17a.EXPECTED_RENDER_SERVICE_NAME,
        "type": "web_service",
        "repo": step17a.EXPECTED_RENDER_REPOSITORY,
        "branch": "wnba-step20b-rollover-runtime-diagnostic-20260830",
        "autoDeploy": "no",
        "rootDir": "",
        "serviceDetails": {
            "runtime": "docker",
            "url": step17a.EXPECTED_RENDER_URL,
            "region": "oregon",
            "healthCheckPath": "/health",
            "numInstances": 1,
        },
    }


def test_01_default_off_and_manifest_is_non_activating() -> None:
    assert step17a.step17a_enabled({}) is False
    manifest = step17a.production_host_manifest()
    assert manifest["default_enabled"] is False
    assert manifest["existing_shared_host_identified"] is True
    assert manifest["read_only_render_inventory_allowed"] is True
    assert manifest["local_frozen_container_health_proof_allowed"] is True
    assert manifest["render_service_mutation_allowed"] is False
    assert manifest["render_deploy_allowed"] is False
    assert manifest["new_render_service_creation_allowed"] is False
    assert manifest["continuous_production_runtime_allowed"] is False
    assert manifest["production_scheduler_allowed"] is False
    assert manifest["step17b_required_for_hosted_activation"] is True
    assert all(value is False for value in manifest["safety_contract"].values())


def test_02_exact_step16e_lineage_is_frozen() -> None:
    assert step17a.STEP16E_FROZEN_SHA == "9676d4b657b4928a61563014e1bc519dfe52fa26"
    assert step17a.STEP16E_TESTED_HEAD_SHA == "b4a69b96c9783006d8dd463fc6407c44958081e5"
    assert step17a.STEP16E_TREE_SHA == "d87955d61fa7c463ebe4f03601dab854ccc40622"
    assert step17a.STEP16E_RELEASE_CONTENT_SHA256 == "769e16a66c87a49a627e9bec80f3d119ec10410f44abc5e10444b0ec3b0617ff"
    assert step17a.STEP16E_FINAL_EVIDENCE_CONTENT_SHA256 == step16e.FINAL_EVIDENCE_CONTENT_SHA256
    assert step16e.FINAL_CERTIFICATION_MARKER == "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_GREEN"


def test_03_frozen_docker_and_main_blobs_are_exact() -> None:
    observed = step17a.validate_frozen_packaging()
    assert observed == {
        "dockerfile_blob_sha": "34a542b0a32456de58b81fd711fef215e618469f",
        "main_blob_sha": "839a7cae1b69b456260031803856df1f7f9661ec",
    }


def test_04_static_evidence_hash_and_inventory_are_exact() -> None:
    evidence = step17a.load_step17a_evidence()
    validated = step17a.validate_step17a_evidence(evidence)
    assert validated["render_inventory"]["github_run_id"] == 33571003479
    assert validated["render_inventory"]["github_job_id"] == 100064723826
    assert validated["render_inventory"]["artifact_id"] == 9824909774
    assert validated["render_inventory"]["mutation_performed"] is False
    assert validated["render_inventory"]["service_count"] == 1


def test_05_evidence_tamper_fails_closed() -> None:
    evidence = step17a.load_step17a_evidence()
    tampered = deepcopy(evidence)
    tampered["host_boundary"]["render_mutated"] = True
    with pytest.raises(step17a.MLBStep17AHostContractIntegrityError):
        step17a.validate_step17a_evidence(tampered)


def test_06_existing_render_identity_is_exact() -> None:
    identity = step17a.validate_render_service_identity(_api_service())
    assert identity["id"] == "srv-da84q6ifngtc73bdbm6g"
    assert identity["name"] == "kyre-sports-api"
    assert identity["runtime"] == "docker"
    assert identity["url"] == "https://kyre-sports-api.onrender.com"
    assert identity["region"] == "oregon"
    assert identity["health_check_path"] == "/health"
    assert identity["num_instances"] == 1
    assert identity["auto_deploy"] == "no"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "srv-wrong"),
        ("name", "wrong-service"),
        ("type", "private_service"),
        ("repo", "https://github.com/example/wrong"),
        ("autoDeploy", "yes"),
        ("rootDir", "sports_api"),
    ],
)
def test_07_render_top_level_identity_drift_is_refused(field: str, value: object) -> None:
    service = _api_service()
    service[field] = value
    with pytest.raises(step17a.MLBStep17AHostContractIntegrityError):
        step17a.validate_render_service_identity(service)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime", "python"),
        ("url", "https://wrong.onrender.com"),
        ("region", "frankfurt"),
        ("healthCheckPath", "/wrong"),
        ("numInstances", 2),
    ],
)
def test_08_render_service_detail_drift_is_refused(field: str, value: object) -> None:
    service = _api_service()
    service["serviceDetails"][field] = value
    with pytest.raises(step17a.MLBStep17AHostContractIntegrityError):
        step17a.validate_render_service_identity(service)


def test_09_host_contract_accepts_exact_frozen_release_with_every_runtime_gate_off() -> None:
    env = step17a.expected_host_env()
    report = step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)
    assert report["status"] == "host_contract_ready_shared_host_unchanged_activation_deferred"
    assert report["frozen_step16e_sha"] == step17a.STEP16E_FROZEN_SHA
    assert report["database_secret_configured"] is True
    assert report["database_connection_opened"] is False
    assert report["database_secret_exposed"] is False
    assert report["render_service_mutation_allowed"] is False
    assert report["render_deploy_allowed"] is False
    assert report["production_runtime_enabled"] is False
    assert report["production_scheduler_enabled"] is False
    assert report["provider_calls"] == 0
    assert report["sportsbook_calls"] == 0
    assert report["step17b_required_for_hosted_activation"] is True


def test_10_step17a_gate_is_required() -> None:
    env = step17a.expected_host_env()
    env[step17a.STEP17A_ENABLED_ENV] = "false"
    with pytest.raises(step17a.MLBStep17AHostContractDisabledError):
        step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)


@pytest.mark.parametrize(
    "key",
    [
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_SUPABASE_REST_WRITE_ENABLED",
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED",
        "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
        "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
        "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED",
        "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
        "MLB_STEP14B_DATABASE_READ_ENABLED",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED",
    ],
)
def test_11_unsafe_runtime_or_persistence_switch_is_refused(key: str) -> None:
    env = step17a.expected_host_env()
    env[key] = "true"
    with pytest.raises(step17a.MLBStep17AHostContractDisabledError):
        step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)


def test_12_wrong_revision_is_refused() -> None:
    env = step17a.expected_host_env()
    env[step17a.EXPECTED_REVISION_ENV] = "0" * 40
    with pytest.raises(step17a.MLBStep17AHostContractIntegrityError):
        step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)

    env = step17a.expected_host_env()
    with pytest.raises(step17a.MLBStep17AHostContractIntegrityError):
        step17a.validate_host_contract(env, build_revision="1" * 40)


def test_13_database_secret_is_required_but_never_returned() -> None:
    env = step17a.expected_host_env(database_url="")
    with pytest.raises(step17a.MLBStep17AHostContractDisabledError):
        step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)

    env = step17a.expected_host_env(database_url="https://not-postgres.invalid")
    with pytest.raises(step17a.MLBStep17AHostContractDisabledError):
        step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)

    secret = "postgresql://secret-user:secret-pass@example.invalid/postgres"
    env = step17a.expected_host_env(database_url=secret)
    report = step17a.validate_host_contract(env, build_revision=step17a.STEP16E_FROZEN_SHA)
    assert secret not in json.dumps(report, sort_keys=True)


def test_14_container_start_health_and_shutdown_contract_is_frozen() -> None:
    report = step17a.validate_host_contract(
        step17a.expected_host_env(), build_revision=step17a.STEP16E_FROZEN_SHA
    )
    assert report["container_default_port"] == 8000
    assert report["container_exposed_port"] == 8000
    assert report["container_default_workers"] == 2
    assert report["health_path"] == "/health"
    assert report["health_expected_status"] == "ok"
    assert report["health_expected_service"] == "kyre-sports-api"
    assert report["start_command"] == step17a.START_COMMAND
    assert report["fastapi_lifespan_shutdown_required"] is True


def test_15_packaging_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = step17a._git_blob_sha

    def drift(path):
        value = original(path)
        if str(path).endswith("Dockerfile"):
            return "0" * 40
        return value

    monkeypatch.setattr(step17a, "_git_blob_sha", drift)
    with pytest.raises(step17a.MLBStep17AHostContractIntegrityError):
        step17a.validate_frozen_packaging()


def test_16_evidence_hash_excludes_only_observation_time_and_hash_field() -> None:
    evidence = step17a.load_step17a_evidence()
    surface = deepcopy(evidence)
    surface.pop("observed_at_utc", None)
    surface.pop("evidence_content_sha256", None)
    raw = json.dumps(
        surface,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == step17a.EVIDENCE_CONTENT_SHA256
