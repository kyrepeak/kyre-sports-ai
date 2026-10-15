import asyncio

import pytest

from runless_v2.models import LeaseClaim, ProofRequest, ProofState
from runless_v2.proof_service import _execute_with_lease_heartbeat
from runless_v2.sandbox_executor import SandboxEvidence, SandboxProofResult
from runless_v2.state_store import StaleFence

SHA = "a" * 40
MAIN = "b" * 40
TOKEN = "11111111-1111-1111-1111-111111111111"


def request():
    return ProofRequest(
        task_id="task-heartbeat",
        workstream="ws-heartbeat",
        candidate_sha=SHA,
        lease_id="scope-heartbeat",
        authorization_id="auth-heartbeat",
        expected_main_sha=MAIN,
    )


class FakeGithub:
    def installation_token(self):
        return "installation-token"


class FakeStore:
    def __init__(self):
        self.renew_calls = 0
        self.renew_error = None

    def renew(self, claim, ttl_seconds):
        self.renew_calls += 1
        if self.renew_error:
            raise self.renew_error
        return claim.model_copy(update={"expires_at": "2026-10-15T17:00:00+00:00"})


class HeartbeatSandbox:
    def __init__(self, delay=1.2):
        self.delay = delay
        self.calls = 0

    async def execute(self, **kwargs):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return SandboxProofResult(
            ok=True,
            candidate_sha=kwargs["candidate_sha"],
            task_id=kwargs["task_id"],
            plan={"task_id": kwargs["task_id"], "freeze_token": "FREEZE"},
            evidence=[SandboxEvidence(name="proof", ok=True)],
        )


def claim():
    return LeaseClaim(
        proof_id="proof-heartbeat",
        workstream="ws-heartbeat",
        lease_token=TOKEN,
        fencing_generation=7,
        expires_at="2026-10-15T16:00:00+00:00",
        state=ProofState.REUSE_OR_PROVE,
    )


@pytest.mark.asyncio
async def test_heartbeat_renews_existing_claim_and_returns_latest_claim():
    store = FakeStore()
    sandbox = HeartbeatSandbox()
    result, latest = await _execute_with_lease_heartbeat(
        sandbox=sandbox,
        state_store=store,
        claim=claim(),
        request=request(),
        github=FakeGithub(),
        ttl_seconds=3,
        timeout_seconds=120,
    )
    assert result.ok is True
    assert store.renew_calls >= 1
    assert latest.lease_token == TOKEN
    assert latest.fencing_generation == 7
    assert sandbox.calls == 1


@pytest.mark.asyncio
async def test_heartbeat_stale_fence_fails_closed_without_second_execution():
    store = FakeStore()
    store.renew_error = StaleFence("RUNLESS_V2_STALE_FENCE")
    sandbox = HeartbeatSandbox()
    with pytest.raises(StaleFence, match="RUNLESS_V2_STALE_FENCE"):
        await _execute_with_lease_heartbeat(
            sandbox=sandbox,
            state_store=store,
            claim=claim(),
            request=request(),
            github=FakeGithub(),
            ttl_seconds=3,
            timeout_seconds=120,
        )
    assert sandbox.calls == 1
