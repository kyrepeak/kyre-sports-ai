from __future__ import annotations

import pytest

from sports_api.tools import mlb_step17b_render_activation as activation


def _baseline() -> dict[str, str]:
    return {
        "WNBA_KYRE_DURABLE_STORAGE_BACKEND": "supabase",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "KYRE_DATABASE_URL": "postgresql://user:secret@example.invalid/kyre",
        "KEEP_ME": "preserved",
        "MLB_STEP17B_ALWAYS_ON_ENABLED": "false",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
        "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED": "false",
        "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED": "false",
        "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED": "false",
    }


def test_certified_revision_is_immutable_sha() -> None:
    assert activation.SHA40.fullmatch(activation.CERTIFIED_REVISION)
    assert activation.CERTIFIED_RUN_ID == 33578176749


def test_build_activated_env_is_additive_and_preserves_existing_values() -> None:
    original = _baseline()
    activated = activation.build_activated_env(original)
    assert original["MLB_STEP17B_ALWAYS_ON_ENABLED"] == "false"
    assert activated["KEEP_ME"] == "preserved"
    assert activated["KYRE_DATABASE_URL"] == original["KYRE_DATABASE_URL"]
    assert activated["MLB_STEP17B_ALWAYS_ON_ENABLED"] == "true"
    assert activated["MLB_STEP17B_EXPECTED_REVISION"] == activation.CERTIFIED_REVISION
    assert activated["WEB_CONCURRENCY"] == "1"
    assert activated["MLB_DEPLOYMENT_MODE"] == "container"


def test_baseline_validation_accepts_safe_wnba_host() -> None:
    activation._validate_baseline_env(_baseline())


def test_baseline_validation_rejects_pre_enabled_step17b() -> None:
    values = _baseline()
    values["MLB_STEP17B_ALWAYS_ON_ENABLED"] = "true"
    with pytest.raises(activation.Step17BRenderActivationError):
        activation._validate_baseline_env(values)


def test_baseline_validation_rejects_frozen_legacy_runtime() -> None:
    values = _baseline()
    values["MLB_PRODUCTION_RUNTIME_ENABLED"] = "true"
    with pytest.raises(activation.Step17BRenderActivationError):
        activation._validate_baseline_env(values)


def test_baseline_validation_requires_protected_postgresql_url() -> None:
    values = _baseline()
    values["KYRE_DATABASE_URL"] = ""
    with pytest.raises(activation.Step17BRenderActivationError):
        activation._validate_baseline_env(values)


def test_activated_validation_accepts_exact_bounded_environment() -> None:
    activation._validate_activated_env(activation.build_activated_env(_baseline()))


def test_activated_validation_rejects_multiple_workers() -> None:
    values = activation.build_activated_env(_baseline())
    values["WEB_CONCURRENCY"] = "2"
    with pytest.raises(activation.Step17BRenderActivationError):
        activation._validate_activated_env(values)


def test_deploy_commit_id_supports_render_shapes() -> None:
    sha = activation.CERTIFIED_REVISION
    assert activation._deploy_commit_id({"commitId": sha}) == sha
    assert activation._deploy_commit_id({"commit": {"id": sha}}) == sha
    assert activation._deploy_commit_id({"commit": {"sha": sha}}) == sha


def test_deploy_rows_unwraps_render_list_shape() -> None:
    rows = activation._deploy_rows([
        {"deploy": {"id": "dep-1", "status": "live"}},
        {"id": "dep-2", "status": "building"},
    ])
    assert [row["id"] for row in rows] == ["dep-1", "dep-2"]


def test_service_validation_requires_exact_shared_free_docker_host() -> None:
    service = {
        "id": activation.EXPECTED_SERVICE_ID,
        "name": "kyre-sports-api",
        "repo": "https://github.com/kyrepeak/kyre-sports-ai",
        "autoDeploy": "no",
        "serviceDetails": {
            "runtime": "docker",
            "plan": "free",
        },
    }
    activation._validate_service(service)
    service["id"] = "srv-wrong"
    with pytest.raises(activation.Step17BRenderActivationError):
        activation._validate_service(service)
