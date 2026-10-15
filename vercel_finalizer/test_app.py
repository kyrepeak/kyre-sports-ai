import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

import app as target
from vercel_finalizer.authority import AuthoritySnapshot, FinalizerAuthorityError
from vercel_finalizer.gate_publication import GateClaimDecision, GatePublicationError
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


def exact_check(*, proof_id="proof-1", digest=DIGEST, check_id=77):
    return {
        "id": check_id,
        "name": "runless-final-gate",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "app": {"id": 5204253},
        "output": {"summary": f"runless-v2 receipt={digest.removeprefix('sha256:')} proof={proof_id}"},
    }


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


def test_receipt_binding_failure_blocks_gate(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(
        target,
        "resolve_receipt_binding",
        lambda *args, **kwargs: (_ for _ in ()).throw(ReceiptBindingError("FINALIZER_RECEIPT_IDENTITY_MISMATCH")),
    )
    response = client().post("/prove", json=request())
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_RECEIPT_IDENTITY_MISMATCH"


def test_existing_gate_reuse_requires_exact_check_id_and_identity(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(
        target,
        "claim_publication",
        lambda *args, **kwargs: GateClaimDecision(publish=False, reused=True, gate_check_run_id=77),
    )
    monkeypatch.setattr(target, "_check_runs", lambda *args, **kwargs: [exact_check()])
    response = client().post("/prove", json=request())
    assert response.status_code == 200
    body = response.json()
    assert body["reused"] is True
    assert body["gate_check_run_id"] == 77
    assert body["proof_id"] == "proof-1"


def test_wrong_existing_gate_identity_fails_closed(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(
        target,
        "claim_publication",
        lambda *args, **kwargs: GateClaimDecision(publish=False, reused=True, gate_check_run_id=77),
    )
    monkeypatch.setattr(target, "_check_runs", lambda *args, **kwargs: [exact_check(proof_id="other-proof")])
    response = client().post("/prove", json=request())
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_GATE_IDENTITY_MISMATCH"


def test_claimed_publication_posts_once_and_completes_exact_check(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(
        target,
        "claim_publication",
        lambda *args, **kwargs: GateClaimDecision(publish=True, reused=False, claim_token="claim-1"),
    )
    states = iter([[], [exact_check()]])
    monkeypatch.setattr(target, "_check_runs", lambda *args, **kwargs: next(states))
    published = {"count": 0}
    monkeypatch.setattr(
        target,
        "_publish_success",
        lambda *args, **kwargs: published.update(count=published["count"] + 1) or {"id": 77},
    )
    completed = {}
    monkeypatch.setattr(
        target,
        "complete_publication",
        lambda *args, **kwargs: completed.update(kwargs) or 77,
    )
    response = client().post("/prove", json=request())
    assert response.status_code == 200
    assert response.json()["reused"] is False
    assert response.json()["gate_check_run_id"] == 77
    assert published["count"] == 1
    assert completed["gate_check_run_id"] == 77


def test_concurrent_publication_claim_fails_closed_without_post(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(target, "resolve_authority", lambda *args, **kwargs: authority())
    monkeypatch.setattr(target, "_installation_token", lambda settings, http: "tok")
    monkeypatch.setattr(
        target,
        "claim_publication",
        lambda *args, **kwargs: (_ for _ in ()).throw(GatePublicationError("FINALIZER_GATE_PUBLICATION_IN_PROGRESS")),
    )
    posted = {"count": 0}
    monkeypatch.setattr(target, "_publish_success", lambda *args, **kwargs: posted.update(count=1))
    response = client().post("/prove", json=request())
    assert response.status_code == 409
    assert response.json()["detail"] == "FINALIZER_GATE_PUBLICATION_IN_PROGRESS"
    assert posted["count"] == 0
