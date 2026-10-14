import hashlib
import json

from fastapi.testclient import TestClient

from runless_v2.config import Settings
from runless_v2.models import ProofResult, ProofState, ProofStatus
from runless_v2.app import create_app

SHA = "a" * 40
MAIN = "b" * 40
PROOF = "sha256:" + "d" * 64
FREEZE = "RUNLESS_V2_TEST_FROZEN"
AUTH = {"Authorization": "Bearer proof-secret"}


def settings(*, enabled=False):
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-secret",
        github_app_id="5204253",
        github_app_installation_id="99",
        github_app_private_key="private-key",
        proof_auth_token="proof-secret",
        authority_enabled=enabled,
    )


def proof_status(state=ProofState.MERGE_AUTHORIZED, proof_id="proof-1"):
    return ProofStatus(
        proof_id=proof_id,
        task_id="task",
        workstream="ws",
        candidate_sha=SHA,
        expected_main_sha=MAIN,
        scope_lease_id="scope",
        authorization_id="auth",
        request_fingerprint="fp",
        state=state,
        fencing_generation=1,
    )


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def finalization_evidence():
    prior = {
        "version": "UNIVERSAL_SPORTS_FINALIZATION_LEDGER_V2_MANIFEST",
        "revision": 5,
        "previous_state_hash": "0" * 64,
        "latest_freeze_token": "OLD",
        "latest_record_path": "old.json",
        "latest_record_blob_sha": "e" * 40,
        "latest_merged_main_sha": "f" * 40,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    prior["state_hash"] = canonical_hash(prior)
    record = {
        "version": "UNIVERSAL_SPORTS_FINALIZATION_BOOTSTRAP_V1",
        "workstream": "ws",
        "freeze_token": FREEZE,
        "merged_main_sha": MAIN,
        "candidate_sha": SHA,
        "proof_digest": PROOF,
        "artifacts": {"artifact.py": "c" * 40},
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    record["record_hash"] = canonical_hash(record)
    manifest = {
        "version": "UNIVERSAL_SPORTS_FINALIZATION_LEDGER_V2_MANIFEST",
        "revision": 6,
        "previous_state_hash": prior["state_hash"],
        "latest_freeze_token": FREEZE,
        "latest_record_path": f"devsystem/finalization_ledger_v2/records/{FREEZE}.json",
        "latest_record_blob_sha": "1" * 40,
        "latest_merged_main_sha": MAIN,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    manifest["state_hash"] = canonical_hash(manifest)
    return {"record": record, "manifest": manifest, "previous_manifest": prior}


class FakeStore:
    def __init__(self):
        self.proof_mutations = 0
        self.statuses = {"proof-1": proof_status()}
        self.mirrors = {"proof-1": {"proof_id": "proof-1", "receipt_digest": "abc"}}
        self.closeouts = []

    def health(self):
        return True

    def status(self, proof_id):
        return self.statuses[proof_id]

    def receipt_mirror(self, proof_id):
        return self.mirrors[proof_id]

    def closeout_green_frozen(self, proof_id, **kwargs):
        self.closeouts.append((proof_id, kwargs))
        value = proof_status(ProofState.GREEN_FROZEN, proof_id=proof_id)
        self.statuses[proof_id] = value
        return value


class FakeGithub:
    def __init__(self, evidence=None):
        self.evidence = evidence or finalization_evidence()

    def read_finalization_evidence(self, freeze_token):
        return self.evidence


class FakeSandbox:
    pass


def client(*, enabled=False, store=None, github=None, proof_executor=None):
    store = store or FakeStore()
    app = create_app(
        settings=settings(enabled=enabled),
        state_store=store,
        github=github or FakeGithub(),
        sandbox_executor=FakeSandbox(),
        proof_executor=proof_executor,
    )
    return TestClient(app), store


def test_health_is_public_safe_and_reports_authority_disabled():
    c, _ = client(enabled=False)
    response = c.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "runless-v2"
    assert body["render_dependency"] is False
    assert body["github_actions_fallback"] == 0
    assert body["supabase"] == "healthy"
    assert body["github_app_configured"] is True
    assert body["proof_authority_enabled"] is False
    assert "service-secret" not in response.text
    assert "private-key" not in response.text


def test_openapi_declares_http_bearer_security_for_prove():
    c, _ = client(enabled=True)
    schema = c.get("/openapi.json").json()
    scheme = schema["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert {"HTTPBearer": []} in schema["paths"]["/prove"]["post"]["security"]


def test_missing_or_invalid_auth_fails_before_proof_mutation():
    calls = {"proof": 0}

    async def executor(*args, **kwargs):
        calls["proof"] += 1
        return ProofResult(proof_id="p", status=ProofState.MERGE_AUTHORIZED, candidate_sha=SHA)

    c, _ = client(enabled=True, proof_executor=executor)
    payload = {
        "task_id": "task", "workstream": "ws", "candidate_sha": SHA,
        "lease_id": "scope", "authorization_id": "auth", "expected_main_sha": MAIN,
    }
    assert c.post("/prove", json=payload).status_code == 401
    assert c.post("/prove", json=payload, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert calls["proof"] == 0


def test_authority_disabled_prove_fails_closed_after_valid_auth():
    calls = {"proof": 0}

    async def executor(*args, **kwargs):
        calls["proof"] += 1

    c, _ = client(enabled=False, proof_executor=executor)
    response = c.post("/prove", headers=AUTH, json={
        "task_id": "task", "workstream": "ws", "candidate_sha": SHA,
        "lease_id": "scope", "authorization_id": "auth", "expected_main_sha": MAIN,
    })
    assert response.status_code == 503
    assert response.json()["detail"] == "RUNLESS_V2_AUTHORITY_DISABLED"
    assert calls["proof"] == 0


def test_enabled_prove_delegates_exact_request_once():
    seen = []

    async def executor(req, **kwargs):
        seen.append(req)
        return ProofResult(
            proof_id="proof-live", status=ProofState.MERGE_AUTHORIZED,
            candidate_sha=req.candidate_sha, receipt_digest="digest",
        )

    c, _ = client(enabled=True, proof_executor=executor)
    response = c.post("/prove", headers=AUTH, json={
        "task_id": "task", "workstream": "ws", "candidate_sha": SHA,
        "lease_id": "scope", "authorization_id": "auth", "expected_main_sha": MAIN,
    })
    assert response.status_code == 200
    assert response.json()["status"] == "MERGE_AUTHORIZED"
    assert len(seen) == 1
    assert seen[0].candidate_sha == SHA


def test_status_persists_across_app_reinstantiation_via_durable_store():
    store = FakeStore()
    c1, _ = client(enabled=True, store=store)
    c2, _ = client(enabled=True, store=store)
    assert c1.get("/status/proof-1", headers=AUTH).json()["state"] == "MERGE_AUTHORIZED"
    assert c2.get("/status/proof-1", headers=AUTH).json()["state"] == "MERGE_AUTHORIZED"
    assert c2.get("/receipts/proof-1", headers=AUTH).json()["receipt_digest"] == "abc"


def test_closeout_mismatched_git_evidence_fails_before_durable_transition():
    evidence = finalization_evidence()
    evidence["record"] = dict(evidence["record"])
    evidence["record"]["freeze_token"] = "WRONG"
    # Leave old record_hash intentionally, proving independent tamper/readback validation.
    store = FakeStore()
    c, _ = client(enabled=True, store=store, github=FakeGithub(evidence))
    response = c.post("/closeout", headers=AUTH, json={
        "proof_id": "proof-1", "workstream": "ws", "candidate_sha": SHA,
        "merged_main_sha": MAIN, "freeze_token": FREEZE, "proof_digest": PROOF,
    })
    assert response.status_code == 409
    assert store.closeouts == []


def test_successful_closeout_reads_git_evidence_then_marks_green_frozen():
    store = FakeStore()
    c, _ = client(enabled=True, store=store, github=FakeGithub())
    response = c.post("/closeout", headers=AUTH, json={
        "proof_id": "proof-1", "workstream": "ws", "candidate_sha": SHA,
        "merged_main_sha": MAIN, "freeze_token": FREEZE, "proof_digest": PROOF,
    })
    assert response.status_code == 200
    assert response.json()["state"] == "GREEN_FROZEN"
    assert len(store.closeouts) == 1
    _, kwargs = store.closeouts[0]
    assert kwargs["manifest_state_hash"] == finalization_evidence()["manifest"]["state_hash"]


def test_vercel_package_is_self_contained_and_pins_python_313():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "runless_v2"
    assert (root / ".python-version").read_text().strip() == "3.13"
    requirements = (root / "requirements.txt").read_text()
    for dependency in ("fastapi", "httpx", "pydantic", "PyJWT", "vercel"):
        assert dependency.lower() in requirements.lower()
    config = json.loads((root / "vercel.json").read_text())
    assert config["$schema"] == "https://openapi.vercel.sh/vercel.json"
