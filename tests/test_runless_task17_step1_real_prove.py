from fastapi.testclient import TestClient

import runless_proof_plane.api as api_module
from runless_proof_plane.api import create_app
from runless_proof_plane.config import Settings


def _full_settings(**overrides):
    values = dict(
        bootstrap=False,
        github_app_id="1",
        github_app_installation_id="2",
        github_app_private_key="k",
        github_webhook_secret="secret",
    )
    values.update(overrides)
    return Settings(**values)


def _request():
    return {
        "task_id": "runless-task17-step1-real-prove",
        "workstream": "runless-task17-step1",
        "candidate_sha": "a" * 40,
        "lease_id": "lease-1",
        "authorization_id": "auth-1",
        "expected_main_sha": "b" * 40,
    }


def test_full_mode_prove_delegates_to_real_runner(monkeypatch):
    seen = {}

    def fake_execute(req, *, settings, github_client, orchestrator, receipts):
        seen["task_id"] = req.task_id
        seen["workstream"] = req.workstream
        seen["candidate_sha"] = req.candidate_sha
        assert settings.bootstrap is False
        assert github_client is not None
        assert orchestrator is not None
        assert receipts is not None
        return {
            "proof_id": "proof-123",
            "status": "GREEN",
            "candidate_sha": req.candidate_sha,
            "receipt": {"proof_id": "proof-123", "digest": "digest-123"},
        }

    monkeypatch.setattr(api_module, "execute_proof_request", fake_execute, raising=False)
    app = create_app(_full_settings())
    client = TestClient(app)

    response = client.post("/prove", json=_request())

    assert response.status_code == 200
    assert response.json()["proof_id"] == "proof-123"
    assert response.json()["status"] == "GREEN"
    assert seen == {
        "task_id": "runless-task17-step1-real-prove",
        "workstream": "runless-task17-step1",
        "candidate_sha": "a" * 40,
    }


def test_bootstrap_mode_still_fails_closed_before_runner(monkeypatch):
    called = {"value": False}

    def fake_execute(*args, **kwargs):
        called["value"] = True
        raise AssertionError("runner must not execute in bootstrap mode")

    monkeypatch.setattr(api_module, "execute_proof_request", fake_execute, raising=False)
    response = TestClient(create_app(Settings())).post("/prove", json=_request())

    assert response.status_code == 503
    assert response.json()["detail"] == "RUNLESS_PROOF_AUTHORITY_DISABLED"
    assert called["value"] is False
