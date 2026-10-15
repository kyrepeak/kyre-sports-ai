from __future__ import annotations

import base64
import json
import pytest

from runless_v2.receipt_contract import build_receipt, finalization_proof_digest
from vercel_finalizer.authority import AuthoritySnapshot
from vercel_finalizer.receipt_binding import ReceiptBindingError, resolve_receipt_binding

SHA = "a" * 40


def authority(**overrides):
    values = dict(
        proof_id="proof-1", task_id="task-1", workstream="ws-1",
        candidate_sha=SHA, fencing_generation=7, proof_fingerprint="fp-1",
        state="RUNLESS_FINAL_GATE", scope_lease_id="lease-1",
    )
    values.update(overrides)
    return AuthoritySnapshot(**values)


def receipt(**overrides):
    values = dict(
        proof_id="proof-1", task_id="task-1", project="API2", workstream="ws-1",
        step="runless-v2-premerge", candidate_sha=SHA,
        artifact_map={"a.py": "blob-1"}, dependency_map={},
        registry_before={"revision": 1}, registry_after={"revision": 1},
        evidence_digests=["e" * 64], failure_class="NONE",
        proof_fingerprint="fp-1", request_fingerprint="req-1",
    )
    values.update(overrides)
    return build_receipt(**values)


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
    def json(self):
        return self._payload


class Client:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
    def get(self, url, **kwargs):
        if self.status_code == 404:
            return Response(404, {})
        raw = json.dumps(self.payload, sort_keys=True).encode()
        return Response(self.status_code, {"content": base64.b64encode(raw).decode()})


def resolve(client, durable=None, proof_digest=None):
    durable = durable or authority()
    payload = receipt()
    return resolve_receipt_binding(
        client,
        token="test-token",
        repository="kyrepeak/kyre-sports-ai",
        receipt_ref="runless-proof-receipts",
        receipt_path="devsystem/runless_proof_receipts",
        authority=durable,
        requested_proof_digest=proof_digest or finalization_proof_digest(payload),
    )


def test_resolves_exact_immutable_receipt_binding():
    payload = receipt()
    result = resolve(Client(payload), proof_digest=finalization_proof_digest(payload))
    assert result.proof_id == "proof-1"
    assert result.candidate_sha == SHA
    assert result.workstream == "ws-1"
    assert result.task_id == "task-1"
    assert result.fencing_generation == 7
    assert result.proof_digest == finalization_proof_digest(payload)


def test_missing_receipt_fails_closed():
    with pytest.raises(ReceiptBindingError, match="FINALIZER_RECEIPT_NOT_FOUND"):
        resolve(Client({}, status_code=404))


@pytest.mark.parametrize("durable", [
    authority(proof_id="proof-2"), authority(task_id="task-2"),
    authority(workstream="ws-2"), authority(candidate_sha="b" * 40),
    authority(proof_fingerprint="fp-2"),
])
def test_receipt_identity_mismatch_fails_closed(durable):
    payload = receipt()
    with pytest.raises(ReceiptBindingError, match="FINALIZER_RECEIPT_IDENTITY_MISMATCH"):
        resolve_receipt_binding(
            Client(payload), token="test-token", repository="kyrepeak/kyre-sports-ai",
            receipt_ref="runless-proof-receipts", receipt_path="devsystem/runless_proof_receipts",
            authority=durable, requested_proof_digest=finalization_proof_digest(payload),
        )


def test_wrong_requested_digest_fails_closed():
    with pytest.raises(ReceiptBindingError, match="FINALIZER_PROOF_DIGEST_MISMATCH"):
        resolve(Client(receipt()), proof_digest="sha256:" + ("9" * 64))


def test_tampered_receipt_fails_closed():
    payload = receipt()
    payload["candidate_sha"] = "b" * 40
    with pytest.raises(ReceiptBindingError, match="FINALIZER_RECEIPT_TAMPERED"):
        resolve(Client(payload))


def test_wrong_authority_state_fails_closed():
    with pytest.raises(ReceiptBindingError, match="FINALIZER_RECEIPT_STATE_INVALID"):
        resolve(Client(receipt()), durable=authority(state="FINGERPRINT"))
