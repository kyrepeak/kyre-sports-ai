from fastapi.testclient import TestClient

from runless_v2.app import create_app
from runless_v2.config import Settings
from runless_v2.models import AuthoritySupersession, ProofState, ProofStatus

OLD = "a" * 40
OLD_MAIN = "b" * 40
SUCCESSOR = "c" * 40
NEW_MAIN = "d" * 40
AUTH = {"Authorization": "Bearer proof-secret"}


def settings(*, enabled=True):
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-secret",
        github_app_id="5204253",
        github_app_installation_id="99",
        github_app_private_key="private-key",
        proof_auth_token="proof-secret",
        repository="kyrepeak/kyre-sports-ai",
        authority_enabled=enabled,
    )


def old_status(*, state=ProofState.MERGE_AUTHORIZED, receipt="receipt-old", gate=77):
    return ProofStatus(
        proof_id="proof-old",
        task_id="task-1",
        workstream="ws-1",
        candidate_sha=OLD,
        expected_main_sha=OLD_MAIN,
        scope_lease_id="scope-1",
        authorization_id="auth-1",
        request_fingerprint="fp-old",
        proof_fingerprint="proof-fp-old",
        state=state,
        failure_class="NONE",
        fencing_generation=4,
        receipt_digest=receipt,
        gate_check_run_id=gate,
    )


def supersession():
    return AuthoritySupersession(
        supersession_id="base-drift-1",
        workstream="ws-1",
        old_proof_id="proof-old",
        old_candidate_sha=OLD,
        old_expected_main_sha=OLD_MAIN,
        successor_candidate_sha=SUCCESSOR,
        successor_expected_main_sha=NEW_MAIN,
        reason="BASE_DRIFT",
        github_pr_number=1600,
        github_branch="feature",
        old_gate_check_run_id=77,
        old_receipt_digest="receipt-old",
        created_at="2026-10-17T02:30:00+00:00",
    )


class FakeStore:
    def __init__(self, *, leases=None, status=None):
        self._status = status or old_status()
        self.leases = list(leases or [])
        self.supersede_calls = []
        self.readbacks = 0

    def health(self):
        return True

    def status(self, proof_id):
        assert proof_id == "proof-old"
        return self._status

    def live_workstream_leases(self, workstream):
        assert workstream == "ws-1"
        return list(self.leases)

    def supersede_base_drift_authority(self, **kwargs):
        self.supersede_calls.append(kwargs)
        self._status = self._status.model_copy(update={
            "state": ProofState.SUPERSEDED_BASE_DRIFT,
            "detail": "RUNLESS_V2_BASE_DRIFT_AUTHORITY_SUPERSEDED:base-drift-1",
        })
        return supersession()

    def authority_supersession(self, old_proof_id):
        assert old_proof_id == "proof-old"
        self.readbacks += 1
        return supersession()


class FakeGithub:
    def __init__(self):
        self.calls = []

    def verify_base_drift_successor(self, **kwargs):
        self.calls.append(kwargs)
        return {"current_main_sha": NEW_MAIN, "successor_candidate_sha": SUCCESSOR}


class FakeSandbox:
    pass


def client(*, store=None, github=None, enabled=True):
    store = store or FakeStore()
    github = github or FakeGithub()
    app = create_app(
        settings=settings(enabled=enabled),
        state_store=store,
        github=github,
        sandbox_executor=FakeSandbox(),
    )
    return TestClient(app), store, github


def payload(**overrides):
    body = {
        "repository": "kyrepeak/kyre-sports-ai",
        "workstream": "ws-1",
        "task_id": "task-1",
        "old_proof_id": "proof-old",
        "old_candidate_sha": OLD,
        "successor_candidate_sha": SUCCESSOR,
        "successor_expected_main_sha": NEW_MAIN,
        "pr_number": 1600,
        "branch": "feature",
    }
    body.update(overrides)
    return body


def test_supersession_route_requires_authentication():
    c, _, _ = client()
    response = c.post("/supersede-base-drift", json=payload())
    assert response.status_code in {401, 403}


def test_supersession_route_fails_when_authority_disabled():
    c, _, _ = client(enabled=False)
    response = c.post("/supersede-base-drift", json=payload(), headers=AUTH)
    assert response.status_code == 503
    assert response.json()["detail"] == "RUNLESS_V2_AUTHORITY_DISABLED"


def test_supersession_route_rejects_repository_mismatch_before_mutation():
    c, store, github = client()
    response = c.post("/supersede-base-drift", json=payload(repository="other/repo"), headers=AUTH)
    assert response.status_code == 409
    assert response.json()["detail"] == "RUNLESS_V2_SUPERSESSION_REPOSITORY_MISMATCH"
    assert store.supersede_calls == []
    assert github.calls == []


def test_supersession_route_rejects_live_execution_lease_before_github_or_mutation():
    store = FakeStore(leases=[{"workstream": "ws-1", "owner_proof_id": "proof-live"}])
    c, store, github = client(store=store)
    response = c.post("/supersede-base-drift", json=payload(), headers=AUTH)
    assert response.status_code == 409
    assert response.json()["detail"] == "RUNLESS_V2_SUPERSESSION_WORKSTREAM_BUSY"
    assert store.supersede_calls == []
    assert github.calls == []


def test_supersession_route_rejects_missing_old_receipt_or_gate():
    store = FakeStore(status=old_status(receipt=None, gate=None))
    c, store, github = client(store=store)
    response = c.post("/supersede-base-drift", json=payload(), headers=AUTH)
    assert response.status_code == 409
    assert response.json()["detail"] == "RUNLESS_V2_SUPERSESSION_MISSING_EVIDENCE"
    assert store.supersede_calls == []
    assert github.calls == []


def test_supersession_route_corroborates_then_mutates_once_and_reads_back_exact_evidence():
    c, store, github = client()
    response = c.post("/supersede-base-drift", json=payload(), headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["supersession_id"] == "base-drift-1"
    assert body["reason"] == "BASE_DRIFT"
    assert body["old_receipt_digest"] == "receipt-old"
    assert body["old_gate_check_run_id"] == 77
    assert len(github.calls) == 1
    assert github.calls[0] == {
        "old_candidate_sha": OLD,
        "old_expected_main_sha": OLD_MAIN,
        "successor_candidate_sha": SUCCESSOR,
        "successor_expected_main_sha": NEW_MAIN,
        "pr_number": 1600,
        "branch": "feature",
    }
    assert len(store.supersede_calls) == 1
    assert store.readbacks == 1
    final = store.status("proof-old")
    assert final.state is ProofState.SUPERSEDED_BASE_DRIFT
    assert final.receipt_digest == "receipt-old"
    assert final.gate_check_run_id == 77
