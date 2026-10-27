from types import SimpleNamespace

from fastapi.testclient import TestClient

import bridge_entrypoint  # noqa: F401 - installs the Guardian bridge on the base app
import app as target
from vercel_finalizer.authority import AuthoritySnapshot
from vercel_finalizer.gate_publication import GateClaimDecision

SHA = "a" * 40
DIGEST = "sha256:" + ("1" * 64)


def _configure_bridge(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GITHUB_APP_ID", "5204253")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("FINALIZER_CAPABILITY_TOKEN", "test-capability")


def _authority():
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


def _exact_check():
    return {
        "id": 77,
        "name": "runless-final-gate",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "app": {"id": 5204253},
        "output": {
            "summary": "runless-v2 receipt="
            + DIGEST.removeprefix("sha256:")
            + " proof=proof-1"
        },
    }


def test_health_reports_capability_configured_without_service_role(monkeypatch):
    _configure_bridge(monkeypatch)
    response = TestClient(target.app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["status"] == "ok"
    assert body["authority_transport"] == "capability_edge"


def test_health_stays_degraded_without_service_role_or_capability(monkeypatch):
    _configure_bridge(monkeypatch)
    monkeypatch.delenv("FINALIZER_CAPABILITY_TOKEN")
    response = TestClient(target.app).get("/health")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["status"] == "degraded"


def test_deep_authority_health_uses_capability_edge(monkeypatch):
    _configure_bridge(monkeypatch)
    monkeypatch.setattr(
        target,
        "authority_bridge_health",
        lambda client, *, supabase_url, capability_token: {
            "status": "ok",
            "authority": "runless_v2",
            "transport": "capability_edge",
        },
    )
    response = TestClient(target.app).get("/health/authority")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "transport": "capability_edge",
        "authority": "runless_v2",
    }


def test_prove_uses_capability_when_service_role_is_unavailable(monkeypatch):
    _configure_bridge(monkeypatch)
    monkeypatch.setattr(
        target,
        "resolve_authority_via_bridge",
        lambda client, *, supabase_url, capability_token, workstream, task_id, candidate_sha, fencing_generation: _authority(),
    )
    monkeypatch.setattr(target, "_installation_token", lambda settings, client: "installation-token")
    monkeypatch.setattr(
        target,
        "resolve_receipt_binding",
        lambda *args, **kwargs: SimpleNamespace(
            proof_digest=kwargs["requested_proof_digest"]
        ),
    )
    monkeypatch.setattr(
        target,
        "claim_publication_via_bridge",
        lambda client, *, supabase_url, capability_token, proof_id, candidate_sha, fencing_generation, proof_digest, claim_token: GateClaimDecision(
            publish=False,
            reused=True,
            gate_check_run_id=77,
        ),
    )
    monkeypatch.setattr(target, "_check_runs", lambda *args, **kwargs: [_exact_check()])
    response = TestClient(target.app).post(
        "/prove",
        json={
            "workstream": "ws-1",
            "task_id": "task-1",
            "candidate_sha": SHA,
            "fencing_generation": 7,
            "proof_digest": DIGEST,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reused"] is True
    assert body["gate_check_run_id"] == 77
    assert body["proof_id"] == "proof-1"
