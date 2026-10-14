import copy

import pytest

from runless_v2.github_authority import GithubAuthorityError
from runless_v2.models import FailureClass, LeaseClaim, ProofRequest, ProofState, ProofStatus
from runless_v2.receipt_contract import build_receipt
from runless_v2.sandbox_executor import SandboxEvidence, SandboxProofResult
from runless_v2.state_store import AuthorityConflict, StaleFence
from runless_v2.proof_service import build_proof_id, execute_proof_request

SHA = "a" * 40
MAIN = "b" * 40
TOKEN = "11111111-1111-1111-1111-111111111111"


def request(**overrides):
    values = dict(
        task_id="task-5",
        workstream="ws-5",
        candidate_sha=SHA,
        lease_id="scope-5",
        authorization_id="auth-5",
        expected_main_sha=MAIN,
    )
    values.update(overrides)
    return ProofRequest(**values)


def plan(**overrides):
    value = {
        "task_id": "task-5",
        "workstream": "ws-5",
        "commands": [["python", "-m", "pytest", "-q", "tests/x.py"]],
        "artifacts": ["artifact.py"],
        "dependencies": ["dependency.py"],
        "probes": [],
        "timeout_seconds": 120,
        "live_ttl_seconds": 900,
        "freeze_token": "FREEZE-5",
    }
    value.update(overrides)
    return value


def status(state=ProofState.IDENTIFY, **overrides):
    values = dict(
        proof_id="proof-placeholder",
        task_id="task-5",
        workstream="ws-5",
        candidate_sha=SHA,
        expected_main_sha=MAIN,
        scope_lease_id="scope-5",
        authorization_id="auth-5",
        request_fingerprint="request-fp",
        proof_fingerprint="proof-fp",
        state=state,
        failure_class=FailureClass.NONE,
        detail="",
        fencing_generation=1,
    )
    values.update(overrides)
    return ProofStatus(**values)


class FakeGithub:
    def __init__(self):
        self.plan = plan()
        self.main = MAIN
        self.receipts = {}
        self.gates = []
        self.step2a_calls = 0
        self.fail_receipt = None
        self.fail_gate = None

    def _content_json(self, path, ref):
        assert ref == SHA
        return copy.deepcopy(self.plan)

    def tree_blobs(self, sha):
        if sha == SHA:
            return {"artifact.py": "1" * 40, "dependency.py": "2" * 40, "frozen.py": "3" * 40}
        return {"frozen.py": "3" * 40}

    def main_sha(self):
        return self.main

    def verify_step2a(self, req, proof_plan, candidate_tree, main_tree):
        self.step2a_calls += 1
        if self.main != req.expected_main_sha:
            raise GithubAuthorityError("RUNLESS_V2_MAIN_IDENTITY_DRIFT")
        return {
            "candidate_sha": req.candidate_sha,
            "main_sha": self.main,
            "scope_lease": {"lease_id": req.lease_id},
            "registry": {"revision": 301, "state_hash": "registry", "active_thaws": []},
            "artifact_map": {"artifact.py": "1" * 40},
            "dependency_map": {"dependency.py": "2" * 40},
        }

    def installation_token(self):
        return "github-token"

    def commit(self, sha):
        return {"sha": sha}

    def put_or_read_receipt(self, receipt):
        if self.fail_receipt:
            raise GithubAuthorityError(self.fail_receipt)
        existing = self.receipts.get(receipt["proof_id"])
        if existing:
            return existing
        self.receipts[receipt["proof_id"]] = receipt
        return receipt

    def publish_gate_and_readback(self, candidate_sha, receipt):
        if self.fail_gate:
            raise GithubAuthorityError(self.fail_gate)
        gate = {"id": 77, "head_sha": candidate_sha, "receipt": receipt["digest"]}
        self.gates.append(gate)
        return gate


class FakeStore:
    def __init__(self):
        self.claims = []
        self.advances = []
        self.failures = []
        self.infra = []
        self.authorized = []
        self.renew_calls = 0
        self.reused_state = None
        self.claim_error = None
        self.renew_error = None
        self.mirror = None

    def claim(self, req, request_fingerprint, ttl_seconds, *, proof_id):
        if self.claim_error:
            raise self.claim_error
        reused = self.reused_state is not None
        claim = LeaseClaim(
            proof_id=proof_id,
            workstream=req.workstream,
            lease_token=TOKEN,
            fencing_generation=1,
            expires_at="2026-10-13T21:00:00+00:00",
            state=self.reused_state or ProofState.IDENTIFY,
            reused=reused,
        )
        self.claims.append((req, request_fingerprint, ttl_seconds, claim))
        return claim

    def status(self, proof_id):
        return status(self.reused_state or ProofState.IDENTIFY, proof_id=proof_id)

    def receipt_mirror(self, proof_id):
        if self.mirror is None:
            raise RuntimeError("missing mirror")
        return self.mirror

    def advance(self, proof_id, expected, target, claim, detail=""):
        self.advances.append((expected, target))
        claim.state = target
        return status(target, proof_id=proof_id, fencing_generation=claim.fencing_generation)

    def renew(self, claim, ttl_seconds):
        self.renew_calls += 1
        if self.renew_error:
            raise self.renew_error
        return claim.model_copy(update={"expires_at": "2026-10-13T22:00:00+00:00"})

    def record_failure_and_release(self, claim, *, failure_class, detail, record_fingerprint=True):
        self.failures.append((failure_class, detail, record_fingerprint))
        return status(
            ProofState.FAILED,
            proof_id=claim.proof_id,
            failure_class=failure_class,
            detail=detail,
        )

    def release_infra(self, claim, *, detail):
        self.infra.append(detail)
        return status(
            ProofState.FAILED,
            proof_id=claim.proof_id,
            failure_class=FailureClass.INFRA,
            detail=detail,
        )

    def record_merge_authorized_and_release_execution(self, claim, **kwargs):
        self.authorized.append(kwargs)
        return status(
            ProofState.MERGE_AUTHORIZED,
            proof_id=claim.proof_id,
            receipt_digest=kwargs["receipt_digest"],
            gate_check_run_id=kwargs["gate_check_run_id"],
        )


class FakeSandbox:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.error = error
        self.result = result or SandboxProofResult(
            ok=True,
            candidate_sha=SHA,
            task_id="task-5",
            plan=plan(),
            evidence=[SandboxEvidence(
                name="pytest", ok=True, command=["python", "-m", "pytest"],
                stdout_digest="out", stderr_digest="err", failure_class=FailureClass.NONE,
            )],
        )

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


@pytest.mark.asyncio
async def test_happy_path_reaches_merge_authorized_and_releases_execution_lease():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.MERGE_AUTHORIZED
    assert len(sandbox.calls) == 1
    assert [target for _, target in store.advances] == [
        ProofState.LOCK_2A,
        ProofState.FINGERPRINT,
        ProofState.REUSE_OR_PROVE,
        ProofState.PUBLIC_CHECK_IF_REQUIRED,
        ProofState.RECEIPT,
        ProofState.RUNLESS_FINAL_GATE,
    ]
    assert store.renew_calls == 1
    assert len(github.gates) == 1
    assert len(store.authorized) == 1
    assert store.authorized[0]["gate_check_run_id"] == 77


@pytest.mark.asyncio
async def test_same_authorized_proof_reuses_receipt_without_second_sandbox():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    store.reused_state = ProofState.MERGE_AUTHORIZED
    receipt = build_receipt(
        proof_id=build_proof_id(request()), task_id="task-5", project="API2", workstream="ws-5",
        step="runless-v2-premerge", candidate_sha=SHA,
        artifact_map={"artifact.py": "1" * 40}, dependency_map={"dependency.py": "2" * 40},
        registry_before={"revision": 301}, registry_after={"revision": 301},
        evidence_digests=["e"], failure_class="NONE",
    )
    store.mirror = {"proof_id": "ignored", "receipt_json": receipt, "receipt_digest": receipt["digest"]}
    github.put_or_read_receipt = lambda value: value
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.MERGE_AUTHORIZED
    assert sandbox.calls == []


@pytest.mark.asyncio
async def test_different_candidate_authority_conflict_does_not_start_sandbox():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    store.claim_error = AuthorityConflict("RUNLESS_V2_AUTHORITY_CONFLICT")
    with pytest.raises(AuthorityConflict):
        await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert sandbox.calls == []


@pytest.mark.asyncio
async def test_static_failure_records_deterministic_fingerprint_and_stops_chain():
    failed = SandboxProofResult(
        ok=False, candidate_sha=SHA, task_id="task-5", plan=plan(),
        evidence=[SandboxEvidence(
            name="pytest", ok=False, command=["python", "-m", "pytest"],
            stdout_digest="out", stderr_digest="err", failure_class=FailureClass.STATIC_PROOF,
            detail="RUNLESS_V2_STATIC_PROOF_FAILED",
        )],
    )
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox(result=failed)
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.FAILED
    assert store.failures == [(FailureClass.STATIC_PROOF, "RUNLESS_V2_STATIC_PROOF_FAILED", True)]
    assert github.gates == []


@pytest.mark.asyncio
async def test_infra_failure_releases_without_poisoning_failed_fingerprint():
    failed = SandboxProofResult(
        ok=False, candidate_sha=SHA, task_id="task-5", plan=plan(),
        evidence=[SandboxEvidence(
            name="pytest", ok=False, command=["python", "-m", "pytest"],
            stdout_digest="", stderr_digest="", failure_class=FailureClass.INFRA,
            detail="RUNLESS_V2_SANDBOX_COMMAND_TIMEOUT",
        )],
    )
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox(result=failed)
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.FAILED
    assert store.infra == ["RUNLESS_V2_SANDBOX_COMMAND_TIMEOUT"]
    assert store.failures == []


@pytest.mark.asyncio
async def test_stale_fence_before_gate_prevents_gate_publication():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    store.renew_error = StaleFence("RUNLESS_V2_STALE_FENCE")
    with pytest.raises(StaleFence):
        await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert github.gates == []
    assert store.authorized == []


@pytest.mark.asyncio
async def test_main_movement_before_gate_fails_identity_and_does_not_publish():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    original_renew = store.renew

    def renew_then_move(claim, ttl_seconds):
        value = original_renew(claim, ttl_seconds)
        github.main = "c" * 40
        return value

    store.renew = renew_then_move
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.FAILED
    assert store.failures[-1][0] is FailureClass.IDENTITY
    assert github.gates == []


@pytest.mark.asyncio
async def test_receipt_collision_fails_closed_as_security_failure():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    github.fail_receipt = "RUNLESS_V2_RECEIPT_IDENTITY_COLLISION"
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.FAILED
    assert store.failures[-1][0] is FailureClass.SECURITY
    assert github.gates == []


@pytest.mark.asyncio
async def test_gate_readback_failure_releases_as_infra_not_success():
    store, github, sandbox = FakeStore(), FakeGithub(), FakeSandbox()
    github.fail_gate = "RUNLESS_V2_GATE_READBACK_FAILED"
    result = await execute_proof_request(request(), state_store=store, github=github, sandbox=sandbox)
    assert result.status is ProofState.FAILED
    assert store.infra == ["RUNLESS_V2_GATE_READBACK_FAILED"]
    assert store.authorized == []
