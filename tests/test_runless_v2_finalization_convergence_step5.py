from types import SimpleNamespace

import pytest

from runless_v2.finalization_convergence import (
    FinalizationConvergenceError,
    FinalizationTarget,
    converge_green_frozen,
)
from runless_v2.models import ProofState

SHA = "a" * 40
MERGED = "b" * 40
DIGEST = "sha256:" + "c" * 64


def status(state, **extra):
    base = dict(
        proof_id="proof-5",
        workstream="runless-dynamic-finalization-authority-v1-step5",
        candidate_sha=SHA,
        receipt_digest="c" * 64,
        state=state,
        merged_main_sha="",
        freeze_token="",
    )
    base.update(extra)
    return SimpleNamespace(**base)


class Store:
    def __init__(self, initial):
        self.value = initial
        self.closeouts = 0

    def status(self, proof_id):
        assert proof_id == "proof-5"
        return self.value

    def closeout_green_frozen(self, proof_id, **kwargs):
        self.closeouts += 1
        self.value = status(
            ProofState.GREEN_FROZEN,
            merged_main_sha=kwargs["merged_main_sha"],
            freeze_token=kwargs["freeze_token"],
        )
        return self.value


class Github:
    def __init__(self, main=MERGED):
        self.main = main

    def main_sha(self):
        return self.main


def target():
    return FinalizationTarget(
        proof_id="proof-5",
        workstream="runless-dynamic-finalization-authority-v1-step5",
        candidate_sha=SHA,
        freeze_token="RUNLESS_DYNAMIC_FINALIZATION_AUTHORITY_V1_STEP5_FROZEN",
        proof_digest=DIGEST,
    )


def test_step5_connects_existing_merge_freeze_and_durable_readback_once():
    store = Store(status(ProofState.MERGE_AUTHORIZED))
    calls = {"merge": 0, "freeze": 0}

    def merge(candidate):
        calls["merge"] += 1
        return {"candidate_sha": candidate, "merged_main_sha": MERGED}

    def freeze(packet):
        calls["freeze"] += 1
        assert packet["candidate_sha"] == SHA
        assert packet["merged_main_sha"] == MERGED
        return {"status": "GREEN_FROZEN", "manifest_state_hash": "state-hash"}

    result = converge_green_frozen(
        target(), state_store=store, github=Github(),
        merge_exact_candidate=merge, finalize_certified_candidate=freeze,
    )
    assert result["status"] == "GREEN_FROZEN"
    assert result["merged_main_sha"] == MERGED
    assert calls == {"merge": 1, "freeze": 1}
    assert store.closeouts == 1


def test_step5_reuses_durable_green_frozen_without_duplicate_mutation():
    store = Store(status(ProofState.GREEN_FROZEN, merged_main_sha=MERGED, freeze_token=target().freeze_token))
    result = converge_green_frozen(
        target(), state_store=store, github=Github(),
        merge_exact_candidate=lambda _: pytest.fail("must not merge again"),
        finalize_certified_candidate=lambda _: pytest.fail("must not freeze again"),
    )
    assert result["decision"] == "STEP5_ALREADY_GREEN_FROZEN"
    assert result["reused"] is True
    assert store.closeouts == 0


def test_step5_fails_closed_before_merge_without_exact_gate_authority():
    store = Store(status(ProofState.EXECUTING))
    with pytest.raises(FinalizationConvergenceError, match="MERGE_NOT_AUTHORIZED"):
        converge_green_frozen(
            target(), state_store=store, github=Github(),
            merge_exact_candidate=lambda _: pytest.fail("must not merge"),
            finalize_certified_candidate=lambda _: pytest.fail("must not freeze"),
        )


def test_step5_fails_closed_on_merged_main_readback_drift():
    store = Store(status(ProofState.MERGE_AUTHORIZED))
    with pytest.raises(FinalizationConvergenceError, match="MERGED_MAIN_READBACK_MISMATCH"):
        converge_green_frozen(
            target(), state_store=store, github=Github(main="d" * 40),
            merge_exact_candidate=lambda candidate: {"candidate_sha": candidate, "merged_main_sha": MERGED},
            finalize_certified_candidate=lambda _: pytest.fail("must not freeze"),
        )
