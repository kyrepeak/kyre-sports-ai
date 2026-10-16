from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from runless_v2.finalization_convergence import (
    FinalizationConvergenceError,
    FinalizationTarget,
    converge_green_frozen,
)
from runless_v2.models import ProofState


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261016_runless_v2_authorized_proof_supersession_v1.sql"


def _target() -> FinalizationTarget:
    return FinalizationTarget(
        proof_id="proof-old",
        workstream="monster-cfb-game-total-page2-unified-flow-repair-v1",
        candidate_sha="a" * 40,
        freeze_token="STEP8_FROZEN",
        proof_digest="sha256:" + "b" * 64,
    )


class _Store:
    def status(self, proof_id: str):
        assert proof_id == "proof-old"
        return SimpleNamespace(
            proof_id=proof_id,
            workstream="monster-cfb-game-total-page2-unified-flow-repair-v1",
            candidate_sha="a" * 40,
            state=ProofState.MERGE_AUTHORIZED,
            receipt_digest="b" * 64,
            detail="AUTHORITY_SUPERSEDED:" + "c" * 40 + ":proof-before-merge-review",
        )


class _Github:
    def main_sha(self) -> str:
        return "d" * 40


def test_superseded_merge_authority_fails_before_github_merge() -> None:
    merge_calls: list[str] = []

    def merge(candidate: str):
        merge_calls.append(candidate)
        return {"candidate_sha": candidate, "merged_main_sha": "d" * 40}

    with pytest.raises(
        FinalizationConvergenceError,
        match="RUNLESS_V2_STEP5_AUTHORITY_SUPERSEDED",
    ):
        converge_green_frozen(
            _target(),
            state_store=_Store(),
            github=_Github(),
            merge_exact_candidate=merge,
            finalize_certified_candidate=lambda packet: pytest.fail("must not freeze"),
        )

    assert merge_calls == []


def test_supersession_migration_is_durable_idempotent_and_fail_closed() -> None:
    assert MIGRATION.exists(), "authorized-proof supersession migration is not implemented yet"
    text = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function runless_v2.is_merge_authority_superseded" in text
    assert "create or replace function runless_v2.supersede_merge_authorized_authority" in text
    assert "authority_superseded:" in text
    assert "state <> 'merge_authorized'" in text or "state != 'merge_authorized'" in text
    assert "replacement_candidate_sha" in text
    assert "proof_authority_supersession_guard" in text
    assert "runless_v2_authority_superseded" in text

    # A different candidate may claim the workstream only after old merge authority
    # has been explicitly superseded; ordinary authorized rows remain blocking.
    assert "not runless_v2.is_merge_authority_superseded(p.detail)" in text

    # The mutation must be idempotent for the exact same replacement identity and
    # fail closed for conflicting attempts rather than silently rewriting history.
    assert "runless_v2_supersession_identity_conflict" in text
    assert "return v_proof" in text


def test_supersession_migration_never_deletes_or_relabels_proof_history() -> None:
    assert MIGRATION.exists(), "authorized-proof supersession migration is not implemented yet"
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "delete from runless_v2.proof_runs" not in text
    assert "set state = 'failed'" not in text
    assert "set state='failed'" not in text
    assert "set state = 'green_frozen'" not in text
    assert "set state='green_frozen'" not in text
