import pytest

from runless_v2.github_authority import GithubAuthorityError
from runless_v2.proof_service import _put_receipt_with_transient_retry


class FakeGithub:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = 0

    def put_or_read_receipt(self, receipt):
        self.calls += 1
        if self.failures:
            detail = self.failures.pop(0)
            if detail:
                raise GithubAuthorityError(detail)
        return receipt


@pytest.mark.asyncio
async def test_transient_receipt_readback_failure_retries_same_receipt():
    github = FakeGithub(["RUNLESS_V2_RECEIPT_READBACK_FAILED", None])
    receipt = {"proof_id": "proof-1", "digest": "digest-1"}

    result = await _put_receipt_with_transient_retry(
        github,
        receipt,
        retries=2,
        delay_seconds=0,
    )

    assert result == receipt
    assert github.calls == 2


@pytest.mark.asyncio
async def test_receipt_identity_collision_still_fails_closed_without_retry():
    github = FakeGithub(["RUNLESS_V2_RECEIPT_IDENTITY_COLLISION"])
    receipt = {"proof_id": "proof-1", "digest": "digest-1"}

    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_RECEIPT_IDENTITY_COLLISION"):
        await _put_receipt_with_transient_retry(
            github,
            receipt,
            retries=3,
            delay_seconds=0,
        )

    assert github.calls == 1
