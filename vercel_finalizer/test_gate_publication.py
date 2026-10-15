from __future__ import annotations

import pytest

from vercel_finalizer.gate_publication import (
    GatePublicationError,
    exact_gate_check,
    project_claim_result,
)

SHA = "a" * 40
DIGEST = "sha256:" + ("1" * 64)
PROOF_ID = "proof-1"


def check(*, sha: str = SHA, digest: str = DIGEST, proof_id: str = PROOF_ID, app_id: int = 5204253, check_id: int = 77):
    return {
        "id": check_id,
        "name": "runless-final-gate",
        "head_sha": sha,
        "status": "completed",
        "conclusion": "success",
        "app": {"id": app_id},
        "output": {"summary": f"runless-v2 receipt={digest.removeprefix('sha256:')} proof={proof_id}"},
    }


def test_exact_gate_check_requires_bound_receipt_and_proof():
    assert exact_gate_check([check()], candidate_sha=SHA, proof_digest=DIGEST, proof_id=PROOF_ID)["id"] == 77


@pytest.mark.parametrize(
    "bad",
    [
        check(sha="b" * 40),
        check(digest="sha256:" + ("2" * 64)),
        check(proof_id="proof-2"),
        check(app_id=999),
    ],
)
def test_wrong_gate_identity_is_not_reusable(bad):
    with pytest.raises(GatePublicationError, match="FINALIZER_GATE_IDENTITY_MISMATCH"):
        exact_gate_check([bad], candidate_sha=SHA, proof_digest=DIGEST, proof_id=PROOF_ID)


def test_claim_projection_allows_exactly_one_publisher():
    claimed = project_claim_result({"decision": "CLAIMED", "claim_token": "token-1"})
    assert claimed.publish is True
    assert claimed.reused is False
    assert claimed.claim_token == "token-1"


def test_claim_projection_blocks_concurrent_duplicate():
    with pytest.raises(GatePublicationError, match="FINALIZER_GATE_PUBLICATION_IN_PROGRESS"):
        project_claim_result({"decision": "IN_PROGRESS"})


def test_claim_projection_reuses_existing_gate_only_by_id():
    reused = project_claim_result({"decision": "EXISTING", "gate_check_run_id": 77})
    assert reused.publish is False
    assert reused.reused is True
    assert reused.gate_check_run_id == 77
