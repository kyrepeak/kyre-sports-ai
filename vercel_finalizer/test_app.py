import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

import app as target
from vercel_finalizer.authority import AuthoritySnapshot, FinalizerAuthorityError
from vercel_finalizer.receipt_binding import ReceiptBindingError

SHA = "a" * 40
DIGEST = "sha256:" + ("1" * 64)
BASE_REQUEST = {
    "workstream": "ws-1",
    "task_id": "task-1",
    "candidate_sha": SHA,
    "fencing_generation": 7,
    "proof_digest": DIGEST,
}


def client():
    return TestClient(target.app)


def request(**overrides):
    body = dict(BASE_REQUEST)
    body.update(overrides)
    return body


def configured(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GITHUB_APP_ID", "5204253")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(
        target,
        "resolve_receipt_binding",
        lambda *args, **kwargs: SimpleNamespace(proof_digest=kwargs["requested_proof_digest"]),
    )


def authority():
    return AuthoritySnapshot(
        proof_id="proof-1",
        task_id="task-1",
        workstream="ws-1",
        candidate_sha=SHA,
        fencing_generation=7,
        proof_fingerprint="fp-1",
        state="RUNLESS_FINAL_GATE",
        scope_lease_id="lease-1",
    )


def test_health_unconfigured(monkeypatch):
    for key in (
        "GITHUB_APP_ID",
        "GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_PRIVATE_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    response = client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["render_dependency"] is False
    assert body["github_actions_fallback"] == 0
    assert body["authority"] == "runless_v2"


def test_invalid_sha_rejected():
    response = client().post("/prove", json=request(candidate_sha="bad"))
    assert response.status_code == 400
    assert response.json()["detail"] == "FINALIZER_INVALID_CANDIDATE_SHA"


def test_invalid_digest_rejected():
    response = client().post("/prove", json=request(proof_digest="bad"))
    assert response.status_code == 400
    assert response.json()["detail"] == "FINALIZER_INVALID_PROOF_DIGEST"


def test_deployment_sha_mismatch(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "b" * 40)
    response = client().post("/prove", json=request())
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_DEPLOYMENT_SHA_MISMATCH"


def test_wrong_app_id_fails_closed(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("GITHUB_APP_ID", "999")
    response = client().post("/prove", json=request())
    assert response.status_code == 502
    assert response.json()["detail"] == "FINALIZER_ERROR:RuntimeError"


def test_authority_failure_fails_closed(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(
        target,
        "resolve_authority",
        lambda *args, **kwargs: (_ for _ in ()).throw(FinalizerAuthorityError("FINALIZER_STALE_FENCE")),
    )
    response = client().post("/prove", json=request())
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_STALE_FENCE"


def test_existing_success_is_reused(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(target, "_existing_success", lambda http, token, sha: True)
    response = client().post("/prove", json=request())
    assert response.status_code == 200
    assert response.json()["reused"] is True
    assert response.json()["proof_id"] == "proof-1"


def test_publish_requires_readback(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    states = iter([False, True])
    monkeypatch.setattr(target, "_existing_success", lambda http, token, sha: next(states))
    called = {"count": 0}
    monkeypatch.setattr(
        target,
        "_publish_success",
        lambda http, token, sha, proof_digest: called.__setitem__("count", called["count"] + 1),
    )
    response = client().post("/prove", json=request())
    assert response.status_code == 200
    assert response.json()["reused"] is False
    assert called["count"] == 1


def test_publish_uses_bound_receipt_digest(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    bound_digest = "sha256:" + ("2" * 64)
    monkeypatch.setattr(
        target,
        "resolve_receipt_binding",
        lambda *args, **kwargs: SimpleNamespace(proof_digest=bound_digest),
    )
    states = iter([False, True])
    monkeypatch.setattr(target, "_existing_success", lambda http, token, sha: next(states))
    published = {}
    monkeypatch.setattr(
        target,
        "_publish_success",
        lambda http, token, sha, digest: published.update(sha=sha, digest=digest),
    )
    response = client().post("/prove", json=request())
    assert response.status_code == 200
    assert published == {"sha": SHA, "digest": bound_digest}
    assert response.json()["proof_digest"] == bound_digest


def test_receipt_binding_failure_blocks_existing_gate(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(target, "_existing_success", lambda http, token, sha: True)
    monkeypatch.setattr(
        target,
        "resolve_receipt_binding",
        lambda *args, **kwargs: (_ for _ in ()).throw(ReceiptBindingError("FINALIZER_RECEIPT_IDENTITY_MISMATCH")),
        raising=False,
    )
    response = client().post("/prove", json=request())
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_RECEIPT_IDENTITY_MISMATCH"
