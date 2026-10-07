from __future__ import annotations

import hashlib
import json

from devsystem import terminal_completion_latch_v1 as latch
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt


TASK_ID = "example-terminal-task"
FREEZE_TOKEN = "EXAMPLE_TERMINAL_TASK_FROZEN"
CANDIDATE_SHA = "a" * 40
MERGED_MAIN_SHA = "c" * 40


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _registry() -> dict:
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 190,
        "source_main_sha": MERGED_MAIN_SHA,
        "entries": {
            FREEZE_TOKEN: {
                "status": "FROZEN",
                "checkpoint_id": FREEZE_TOKEN,
                "source_main_sha": MERGED_MAIN_SHA,
                "artifacts": {"sentinel.py": "b" * 40},
            }
        },
        "active_thaws": [],
    }
    payload["state_hash"] = _hash(payload)
    return payload


def _receipt() -> dict:
    return build_runless_receipt(
        proof_id="terminal-latch-proof",
        task_id=TASK_ID,
        project="API2",
        workstream="api2-finalization-authority-v1-step3",
        step="merged-main-closeout",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={"sentinel.py": "b" * 40},
        dependency_map={},
        registry_before={"revision": 189},
        registry_after={"revision": 190},
        evidence_digests=["terminal-latch-evidence"],
        failure_class="NONE",
    )


def _gate(receipt: dict | None = None) -> dict:
    receipt = receipt or _receipt()
    return {
        "name": "runless-final-gate",
        "conclusion": "success",
        "head_sha": CANDIDATE_SHA,
        "receipt_digest": receipt["digest"],
    }


def _merge() -> dict:
    return {
        "candidate_sha": CANDIDATE_SHA,
        "merged_main_sha": MERGED_MAIN_SHA,
        "contains_candidate": True,
    }


def _ledger(claimed: bool = False) -> dict:
    return {
        "task_id": TASK_ID,
        "status": "DONE",
        "green_plus_frozen_claimed": claimed,
        "freeze_exit": {"frozen_token": FREEZE_TOKEN},
    }


def _kwargs(*, claimed: bool = False) -> dict:
    receipt = _receipt()
    return {
        "task_id": TASK_ID,
        "freeze_token": FREEZE_TOKEN,
        "ledger": _ledger(claimed),
        "registry": _registry(),
        "receipt": receipt,
        "gate": _gate(receipt),
        "merge_evidence": _merge(),
    }


def test_terminal_tuple_short_circuits_duplicate_finalization_actions():
    for action in ("PROVE", "RECHECK", "MERGE", "FREEZE", "DEPLOY", "LEDGER_RECHECK"):
        result = latch.evaluate_terminal_latch(
            requested_action=action,
            reopen_authorization=None,
            **_kwargs(claimed=False),
        )
        assert result["decision"] == "TERMINAL_LATCH_ALREADY_COMPLETE"
        assert result["allowed"] is False
        assert result["short_circuit"] is True
        assert result["duplicate_work_blocked"] is True
        assert result["next_legal_action"] == "MOVE_TO_NEXT_STEP"
        assert len(result["terminal_digest"]) == 64


def test_stale_ledger_cannot_reopen_or_change_terminal_digest():
    stale = latch.evaluate_terminal_latch(
        requested_action="PROVE", reopen_authorization=None, **_kwargs(claimed=False)
    )
    aligned = latch.evaluate_terminal_latch(
        requested_action="PROVE", reopen_authorization=None, **_kwargs(claimed=True)
    )
    assert stale["decision"] == "TERMINAL_LATCH_ALREADY_COMPLETE"
    assert aligned["decision"] == "TERMINAL_LATCH_ALREADY_COMPLETE"
    assert stale["terminal_digest"] == aligned["terminal_digest"]


def test_incomplete_canonical_truth_keeps_latch_open():
    kwargs = _kwargs(claimed=True)
    kwargs["gate"] = dict(kwargs["gate"])
    kwargs["gate"]["conclusion"] = "failure"
    result = latch.evaluate_terminal_latch(
        requested_action="PROVE", reopen_authorization=None, **kwargs
    )
    assert result["decision"] == "TERMINAL_LATCH_OPEN"
    assert result["allowed"] is True
    assert result["short_circuit"] is False
    assert result["terminal_digest"] is None


def test_explicit_thaw_without_new_task_cannot_reopen_terminal_work():
    result = latch.evaluate_terminal_latch(
        requested_action="PROVE",
        reopen_authorization={"mode": "EXPLICIT_THAW", "thaw_id": "THAW-123", "new_task_id": TASK_ID},
        **_kwargs(),
    )
    assert result["decision"] == "TERMINAL_LATCH_REOPEN_BLOCKED"
    assert result["allowed"] is False
    assert result["short_circuit"] is True


def test_explicit_thaw_plus_distinct_new_task_allows_new_workstream_only():
    result = latch.evaluate_terminal_latch(
        requested_action="PROVE",
        reopen_authorization={
            "mode": "EXPLICIT_THAW",
            "thaw_id": "THAW-123",
            "new_task_id": "example-terminal-task-v2",
        },
        **_kwargs(),
    )
    assert result["decision"] == "TERMINAL_LATCH_REOPEN_AUTHORIZED"
    assert result["allowed"] is True
    assert result["short_circuit"] is False
    assert result["new_task_id"] == "example-terminal-task-v2"
    assert len(result["reopen_from_terminal_digest"]) == 64


def test_read_only_terminal_query_is_allowed_without_reopening():
    result = latch.evaluate_terminal_latch(
        requested_action="READ_CANONICAL_STATE", reopen_authorization=None, **_kwargs()
    )
    assert result["decision"] == "TERMINAL_LATCH_READ_ONLY"
    assert result["allowed"] is True
    assert result["short_circuit"] is True
    assert result["duplicate_work_blocked"] is True


def test_safety_flags_are_runless_only_and_non_mutating():
    result = latch.evaluate_terminal_latch(
        requested_action="MERGE", reopen_authorization=None, **_kwargs()
    )
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["mutation_authority_granted"] is False
    assert result["github_actions_fallback"] == 0
