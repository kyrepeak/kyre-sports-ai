from __future__ import annotations

import pytest

from devsystem import finalization_100_percent_finalizer_v1 as finalizer

EXPECTED = {
    1: "API2_FINALIZATION_AUTHORITY_V1_STEP1_FROZEN",
    2: "API2_FINALIZATION_AUTHORITY_V1_STEP2_FROZEN",
    3: "API2_FINALIZATION_AUTHORITY_V1_STEP3_FROZEN",
    4: "API2_FINALIZATION_AUTHORITY_V1_STEP4_FROZEN",
    5: "API2_FINALIZATION_AUTHORITY_V1_STEP5_FROZEN",
}


def _checkpoint(step: int, *, complete: bool = True, token: str | None = None):
    digit = str(step)
    return {
        "step": step,
        "task_id": f"step-{step}-task",
        "freeze_token": token or EXPECTED[step],
        "complete": complete,
        "status": "GREEN_FROZEN" if complete else "BLOCKED",
        "terminal_digest": digit * 64,
        "merged_main_sha": digit * 40,
    }


def _gc(*, remaining: int = 0, decision: str = "AUTHORITY_GC_COLLECTED"):
    return {
        "decision": decision,
        "remaining_target_mutation_authority": remaining,
        "next_legal_action": "RUN_100_PERCENT_FINALIZER",
        "receipt_digest": "f" * 64,
    }


def test_module_has_no_ambient_mutation_authority():
    assert finalizer.NETWORK_CALLS is False
    assert finalizer.AUTO_MUTATE is False
    assert finalizer.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert finalizer.MUTATION_AUTHORITY_GRANTED is False
    assert finalizer.GITHUB_ACTIONS_FALLBACK == 0


def test_missing_checkpoint_blocks_finalization():
    out = finalizer.finalize_to_100_percent(
        checkpoints=[_checkpoint(i) for i in range(1, 5)],
        authority_gc=_gc(),
    )
    assert out["result"]["decision"] == "FINALIZER_WAIT_CHECKPOINTS"
    assert out["result"]["finalized"] is False
    assert out["result"]["missing_steps"] == [5]


def test_incomplete_checkpoint_blocks_finalization():
    cps = [_checkpoint(i) for i in range(1, 6)]
    cps[2] = _checkpoint(3, complete=False)
    out = finalizer.finalize_to_100_percent(checkpoints=cps, authority_gc=_gc())
    assert out["result"]["decision"] == "FINALIZER_CHECKPOINT_NOT_TERMINAL"
    assert out["result"]["blocked_steps"] == [3]
    assert out["result"]["finalized"] is False


def test_wrong_freeze_token_fails_closed():
    cps = [_checkpoint(i) for i in range(1, 6)]
    cps[3] = _checkpoint(4, token="WRONG")
    out = finalizer.finalize_to_100_percent(checkpoints=cps, authority_gc=_gc())
    assert out["result"]["decision"] == "FINALIZER_FREEZE_TOKEN_MISMATCH"
    assert out["result"]["mismatched_steps"] == [4]


def test_authority_gc_must_report_zero_remaining_mutation_authority():
    out = finalizer.finalize_to_100_percent(
        checkpoints=[_checkpoint(i) for i in range(1, 6)],
        authority_gc=_gc(remaining=1),
    )
    assert out["result"]["decision"] == "FINALIZER_AUTHORITY_REMAINS"
    assert out["result"]["remaining_target_mutation_authority"] == 1
    assert out["result"]["next_legal_action"] == "RECONCILE_AUTHORITY_REMAINDER"


def test_authority_gc_decision_must_be_terminal_cleanup_state():
    out = finalizer.finalize_to_100_percent(
        checkpoints=[_checkpoint(i) for i in range(1, 6)],
        authority_gc=_gc(decision="AUTHORITY_GC_WAIT_CANONICAL_COMPLETION"),
    )
    assert out["result"]["decision"] == "FINALIZER_AUTHORITY_GC_NOT_TERMINAL"
    assert out["result"]["finalized"] is False


def test_valid_chain_emits_100_percent_ready_packet():
    out = finalizer.finalize_to_100_percent(
        checkpoints=[_checkpoint(i) for i in range(1, 6)],
        authority_gc=_gc(),
        active_thaws=["THAW-B", "THAW-A"],
    )
    result = out["result"]
    assert result["decision"] == "FINALIZATION_100_PERCENT_READY"
    assert result["finalized"] is True
    assert result["program_progress_percent"] == 100.0
    assert result["completed_prior_steps"] == 5
    assert result["total_steps"] == 6
    assert result["next_legal_action"] == "RUNLESS_PROVE_MERGE_FREEZE_STEP6"
    assert out["receipt"]["active_thaws_preserved"] == ["THAW-A", "THAW-B"]


def test_receipt_is_deterministic_across_checkpoint_and_thaw_order():
    cps = [_checkpoint(i) for i in range(1, 6)]
    a = finalizer.finalize_to_100_percent(
        checkpoints=cps, authority_gc=_gc(), active_thaws=["B", "A"]
    )
    b = finalizer.finalize_to_100_percent(
        checkpoints=list(reversed(cps)), authority_gc=_gc(), active_thaws=["A", "B"]
    )
    assert a["receipt"]["receipt_digest"] == b["receipt"]["receipt_digest"]
    assert a["receipt"]["checkpoint_terminal_digests"] == b["receipt"]["checkpoint_terminal_digests"]


def test_duplicate_step_ids_are_rejected():
    cps = [_checkpoint(i) for i in range(1, 6)] + [_checkpoint(5)]
    with pytest.raises(finalizer.Finalization100PercentFailure, match="duplicate step"):
        finalizer.finalize_to_100_percent(checkpoints=cps, authority_gc=_gc())


def test_malformed_terminal_digest_is_rejected():
    cp = _checkpoint(1)
    cp["terminal_digest"] = "bad"
    cps = [cp] + [_checkpoint(i) for i in range(2, 6)]
    with pytest.raises(finalizer.Finalization100PercentFailure, match="terminal_digest"):
        finalizer.finalize_to_100_percent(checkpoints=cps, authority_gc=_gc())
