from __future__ import annotations

from runless_v2 import api2_authority_isolation_v1 as isolation


class _FakeGithub:
    def __init__(self) -> None:
        self.content_reads: list[tuple[str, str]] = []
        self.requests: list[str] = []

    def _content_json(self, path: str, ref: str):
        self.content_reads.append((path, ref))
        if path.endswith("manifest.json"):
            return {"revision": 1, "state_hash": "state"}
        return {"freeze_token": "API2_TEST_FROZEN"}

    def _request(self, method: str, path: str):
        assert method == "GET"
        self.requests.append(path)
        return []


def test_api2_freeze_reads_only_api2_finalization_ledger() -> None:
    github = _FakeGithub()
    evidence = isolation._read_finalization_evidence_isolated(github, "API2_TEST_FROZEN")

    assert evidence["authority_system"] == "api2"
    assert evidence["ledger_branch"] == isolation.API2_FINALIZATION_BRANCH
    assert github.content_reads
    assert all(ref == isolation.API2_FINALIZATION_BRANCH for _path, ref in github.content_reads)
    assert all("monster-finalization-ledger-v2" not in ref for _path, ref in github.content_reads)
    assert github.requests
    assert all("api2-finalization-ledger-v2" in path for path in github.requests)
    assert all("monster-finalization-ledger-v2" not in path for path in github.requests)


def test_non_api2_freeze_preserves_legacy_branch_without_affecting_api2() -> None:
    github = _FakeGithub()
    evidence = isolation._read_finalization_evidence_isolated(github, "LEGACY_TEST_FROZEN")

    assert evidence["authority_system"] == "legacy"
    assert evidence["ledger_branch"] == isolation.LEGACY_FINALIZATION_BRANCH
