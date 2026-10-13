import pytest
from fastapi.testclient import TestClient

import app as target

SHA = "a" * 40
DIGEST = "sha256:" + ("1" * 64)


def client():
    return TestClient(target.app)


def test_health_unconfigured(monkeypatch):
    for key in ("GITHUB_APP_ID", "GITHUB_APP_INSTALLATION_ID", "GITHUB_APP_PRIVATE_KEY"):
        monkeypatch.delenv(key, raising=False)
    response = client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["render_dependency"] is False
    assert body["github_actions_fallback"] == 0


def test_invalid_sha_rejected():
    response = client().post("/prove", json={"candidate_sha": "bad", "proof_digest": DIGEST})
    assert response.status_code == 400
    assert response.json()["detail"] == "FINALIZER_INVALID_CANDIDATE_SHA"


def test_invalid_digest_rejected():
    response = client().post("/prove", json={"candidate_sha": SHA, "proof_digest": "bad"})
    assert response.status_code == 400
    assert response.json()["detail"] == "FINALIZER_INVALID_PROOF_DIGEST"


def test_deployment_sha_mismatch(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "b" * 40)
    response = client().post("/prove", json={"candidate_sha": SHA, "proof_digest": DIGEST})
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_DEPLOYMENT_SHA_MISMATCH"


def test_wrong_app_id_fails_closed(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GITHUB_APP_ID", "999")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "key")
    response = client().post("/prove", json={"candidate_sha": SHA, "proof_digest": DIGEST})
    assert response.status_code == 502
    assert response.json()["detail"] == "FINALIZER_GITHUB_ERROR:RuntimeError"


def test_pr_head_mismatch_fails_closed(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GITHUB_APP_ID", "5204253")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "key")
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(target, "_pr_head", lambda http, token: ("b" * 40, target.ALLOWED_BRANCH))
    response = client().post("/prove", json={"candidate_sha": SHA, "proof_digest": DIGEST})
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_PR_HEAD_MISMATCH"


def test_existing_success_is_reused(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GITHUB_APP_ID", "5204253")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "key")
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(target, "_pr_head", lambda http, token: (SHA, target.ALLOWED_BRANCH))
    monkeypatch.setattr(target, "_existing_success", lambda http, token, sha: True)
    response = client().post("/prove", json={"candidate_sha": SHA, "proof_digest": DIGEST})
    assert response.status_code == 200
    assert response.json()["reused"] is True


def test_publish_requires_readback(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GITHUB_APP_ID", "5204253")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "key")
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(target, "_pr_head", lambda http, token: (SHA, target.ALLOWED_BRANCH))
    states = iter([False, True])
    monkeypatch.setattr(target, "_existing_success", lambda http, token, sha: next(states))
    called = {"count": 0}
    monkeypatch.setattr(
        target,
        "_publish_success",
        lambda http, token, sha, proof_digest: called.__setitem__("count", called["count"] + 1),
    )
    response = client().post("/prove", json={"candidate_sha": SHA, "proof_digest": DIGEST})
    assert response.status_code == 200
    assert response.json()["reused"] is False
    assert called["count"] == 1
