from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    target = ROOT / path
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_permanent_contract_is_green():
    module = _load("permanent_gate_v1", "devsystem/permanent_gate_v1.py")
    result = module.validate()
    assert result["status"] == "GREEN"
    assert result["active_domains"] == ["cfb", "mlb", "wnba"]
    assert "nfl" in result["blocked_until_activated"]
    assert result["critical_test_count"] == 17


def test_final_gate_accepts_success_and_skipped_only():
    module = _load("final_gate_v1", "devsystem/final_gate_v1.py")
    result = module.evaluate({
        "classify": {"result": "success"},
        "browser-qa": {"result": "skipped"},
        "mlb-critical": {"result": "success"},
    })
    assert result["status"] == "GREEN"

    with pytest.raises(module.FinalGateFailure):
        module.evaluate({
            "classify": {"result": "success"},
            "cfb-critical": {"result": "failure"},
        })


def test_production_contract_separates_hosting_config_from_release_parity():
    contract = _load("production_contract_v1", "devsystem/production_contract_v1.py")
    service = {
        "name": contract.SERVICE_NAME,
        "id": contract.SERVICE_ID,
        "repo": contract.REPOSITORY,
        "branch": contract.RENDER_RELEASE_BRANCH,
        "autoDeploy": contract.EXPECTED_AUTO_DEPLOY,
        "suspended": "not_suspended",
        "serviceDetails": {
            "healthCheckPath": contract.EXPECTED_HEALTH_PATH,
            "url": contract.PUBLIC_URL,
        },
    }
    hosting = contract.evaluate_render_service(service)
    assert hosting["status"] == "GREEN"

    parity = contract.evaluate_release_parity(
        {"status": "diverged", "ahead_by": 1199, "behind_by": 63}
    )
    assert parity["status"] == "RED"
    assert parity["main_only_commits"] == 1199
    assert parity["release_only_commits"] == 63


def test_observability_core_is_dependency_light_and_secret_safe(monkeypatch):
    obs = _load("observability_v1", "sports_api/observability_v1.py")

    fingerprint = obs.error_fingerprint(ValueError("one"), path="/health")
    assert fingerprint == obs.error_fingerprint(ValueError("two"), path="/health")
    assert fingerprint.startswith("KYRE-")

    redacted = obs.sanitize_error_message("token=abc password=xyz")
    assert "abc" not in redacted
    assert "xyz" not in redacted

    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    monkeypatch.setenv("API_KEY", "do-not-leak")
    runtime = obs.runtime_metadata()
    assert runtime["deploy_branch"] == "main"
    assert runtime["deploy_commit"] == "abc123"
    assert "do-not-leak" not in repr(runtime)
