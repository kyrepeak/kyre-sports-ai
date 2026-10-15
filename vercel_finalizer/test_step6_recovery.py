from __future__ import annotations

from pathlib import Path

import pytest

from vercel_finalizer.authority import (
    FinalizerAuthorityError,
    recover_terminal_authority,
    resolve_authority,
)

NBA_WORKSTREAM = "nba-spread-provider-resilience-step1-r1"
NBA_TASK = NBA_WORKSTREAM
NBA_CANDIDATE = "0caf4fd0728b5ff666653b385a63d1c8ced9f154"
NBA_PROOF = "nba-spread-provider-resilience-step1-r1-0caf4fd0728b5ff6-2e3ee548a9f4e4aa"


class FakeResponse:
    def __init__(self, rows=None, status_code=200):
        self._rows = rows if rows is not None else []
        self.status_code = status_code

    def json(self):
        return self._rows


class FakeClient:
    def __init__(self, proof_rows, lease_rows, fail=False):
        self.proof_rows = proof_rows
        self.lease_rows = lease_rows
        self.fail = fail

    def get(self, url, *, headers, params):
        if self.fail:
            return FakeResponse(status_code=503)
        if url.endswith("/rest/v1/proof_runs"):
            return FakeResponse(self.proof_rows)
        if url.endswith("/rest/v1/workstream_leases"):
            return FakeResponse(self.lease_rows)
        raise AssertionError(url)


def nba_proof(**overrides):
    row = {
        "proof_id": NBA_PROOF,
        "task_id": NBA_TASK,
        "workstream": NBA_WORKSTREAM,
        "candidate_sha": NBA_CANDIDATE,
        "fencing_generation": 1,
        "proof_fingerprint": "",
        "state": "FAILED",
        "failure_class": "STATIC_PROOF",
        "detail": "RUNLESS_V2_STATIC_PROOF_FAILED",
        "scope_lease_id": "SCOPE-LEASE-8011CDC2EAD764B5CA9B76C7",
    }
    row.update(overrides)
    return row


def recover(client, **overrides):
    args = {
        "client": client,
        "supabase_url": "https://example.supabase.co",
        "service_role_key": "secret",
        "workstream": NBA_WORKSTREAM,
        "task_id": NBA_TASK,
        "candidate_sha": NBA_CANDIDATE,
        "fencing_generation": 1,
    }
    args.update(overrides)
    return recover_terminal_authority(**args)


def test_step6_recovers_existing_nba_failed_candidate_without_restart():
    result = recover(FakeClient([nba_proof()], []))
    assert result.proof_id == NBA_PROOF
    assert result.candidate_sha == NBA_CANDIDATE
    assert result.state == "FAILED"
    assert result.failure_class == "STATIC_PROOF"
    assert result.detail == "RUNLESS_V2_STATIC_PROOF_FAILED"
    assert result.restart_required is False
    assert result.next_legal_action == "DIAGNOSE_EXISTING_TERMINAL_FAILURE"


def test_step6_recovery_rejects_wrong_candidate():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_RECOVERY_NOT_FOUND"):
        recover(FakeClient([nba_proof()], []), candidate_sha="f" * 40)


def test_step6_recovery_rejects_ambiguous_exact_candidate():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_RECOVERY_AMBIGUOUS"):
        recover(FakeClient([nba_proof(), nba_proof(proof_id="duplicate")], []))


def test_step6_recovery_rejects_live_execution_lease():
    lease = {
        "workstream": NBA_WORKSTREAM,
        "owner_proof_id": NBA_PROOF,
        "fencing_generation": 1,
    }
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_RECOVERY_BUSY"):
        recover(FakeClient([nba_proof()], [lease]))


def test_step6_recovery_rejects_nonterminal_state():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_RECOVERY_NOT_TERMINAL"):
        recover(FakeClient([nba_proof(state="RECEIPT")], []))


def test_step6_green_frozen_readback_is_reused_without_restart():
    result = recover(
        FakeClient(
            [nba_proof(state="GREEN_FROZEN", failure_class="NONE", detail="")],
            [],
        )
    )
    assert result.restart_required is False
    assert result.next_legal_action == "NONE"


def test_step6_mutation_authority_still_requires_live_lease():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_AUTHORITY_AMBIGUOUS"):
        resolve_authority(
            FakeClient([nba_proof(state="RECEIPT")], []),
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            workstream=NBA_WORKSTREAM,
            task_id=NBA_TASK,
            candidate_sha=NBA_CANDIDATE,
            fencing_generation=1,
        )


def test_step6_recovery_code_does_not_hardcode_nba_or_historical_pr_authority():
    source = Path("vercel_finalizer/authority.py").read_text(encoding="utf-8")
    assert NBA_CANDIDATE not in source
    assert "1541" not in source
    assert "/pulls/1526" not in source
    assert "ALLOWED_BRANCH" not in source
