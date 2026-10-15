from __future__ import annotations

import pytest

from vercel_finalizer.authority import FinalizerAuthorityError, resolve_authority


class FakeResponse:
    def __init__(self, rows=None, status_code=200, text=""):
        self._rows = rows if rows is not None else []
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._rows


class FakeClient:
    def __init__(self, proof_rows, lease_rows, fail=False):
        self.proof_rows = proof_rows
        self.lease_rows = lease_rows
        self.fail = fail

    def get(self, url, *, headers, params):
        if self.fail:
            return FakeResponse(status_code=503, text="store unavailable")
        if url.endswith("/rest/v1/proof_runs"):
            return FakeResponse(self.proof_rows)
        if url.endswith("/rest/v1/workstream_leases"):
            return FakeResponse(self.lease_rows)
        raise AssertionError(url)


def proof(**overrides):
    row = {
        "proof_id": "proof-1",
        "task_id": "task-1",
        "workstream": "ws-1",
        "candidate_sha": "a" * 40,
        "fencing_generation": 7,
        "proof_fingerprint": "fp-1",
        "state": "RECEIPT",
        "scope_lease_id": "lease-1",
    }
    row.update(overrides)
    return row


def lease(**overrides):
    row = {
        "workstream": "ws-1",
        "owner_proof_id": "proof-1",
        "fencing_generation": 7,
    }
    row.update(overrides)
    return row


def call(client, **overrides):
    args = {
        "client": client,
        "supabase_url": "https://example.supabase.co",
        "service_role_key": "secret",
        "workstream": "ws-1",
        "task_id": "task-1",
        "candidate_sha": "a" * 40,
        "fencing_generation": 7,
    }
    args.update(overrides)
    return resolve_authority(**args)


def test_resolves_exact_current_authority():
    result = call(FakeClient([proof()], [lease()]))
    assert result.proof_id == "proof-1"
    assert result.candidate_sha == "a" * 40
    assert result.fencing_generation == 7


@pytest.mark.parametrize(
    ("overrides", "marker"),
    [
        ({"candidate_sha": "b" * 40}, "FINALIZER_AUTHORITY_NOT_FOUND"),
        ({"task_id": "task-other"}, "FINALIZER_AUTHORITY_NOT_FOUND"),
        ({"fencing_generation": 8}, "FINALIZER_STALE_FENCE"),
    ],
)
def test_rejects_identity_mismatch(overrides, marker):
    with pytest.raises(FinalizerAuthorityError, match=marker):
        call(FakeClient([proof()], [lease()]), **overrides)


def test_rejects_missing_authority():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_AUTHORITY_NOT_FOUND"):
        call(FakeClient([], []))


def test_rejects_ambiguous_authority():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_AUTHORITY_AMBIGUOUS"):
        call(FakeClient([proof(), proof(proof_id="proof-2")], [lease()]))


def test_rejects_stale_fence():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_STALE_FENCE"):
        call(FakeClient([proof()], [lease(fencing_generation=9)]))


def test_store_failure_fails_closed():
    with pytest.raises(FinalizerAuthorityError, match="FINALIZER_AUTHORITY_STORE_UNAVAILABLE"):
        call(FakeClient([], [], fail=True))
