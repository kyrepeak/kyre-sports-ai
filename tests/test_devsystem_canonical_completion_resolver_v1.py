from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from devsystem import canonical_completion_resolver_v1 as resolver
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt


TASK_ID = "wnba-pra-repair-v1-step3-data-completeness"
FREEZE_TOKEN = "WNBA_PRA_REPAIR_V1_STEP3_FROZEN"
CANDIDATE_SHA = "a" * 40
MERGED_MAIN_SHA = "c" * 40


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _registry(token: str = FREEZE_TOKEN) -> dict:
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 180,
        "source_main_sha": MERGED_MAIN_SHA,
        "entries": {
            token: {
                "status": "FROZEN",
                "checkpoint_id": token,
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
        proof_id="canonical-proof-1",
        task_id=TASK_ID,
        project="API2",
        workstream="api2-finalization-authority-v1-step1",
        step="merged-main-closeout",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={"sentinel.py": "b" * 40},
        dependency_map={},
        registry_before={"revision": 179},
        registry_after={"revision": 180},
        evidence_digests=["evidence-1"],
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


def test_stale_ledger_cannot_veto_valid_canonical_terminal_truth():
    receipt = _receipt()
    result = resolver.resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=_ledger(False),
        registry=_registry(),
        receipt=receipt,
        gate=_gate(receipt),
        merge_evidence=_merge(),
    )
    assert result["complete"] is True
    assert result["status"] == "GREEN_FROZEN"
    assert result["decision"] == "CANONICAL_GREEN_FROZEN"
    assert result["authority"] == "FROZEN_REGISTRY_RUNLESS"
    assert result["ledger_stale"] is True
    assert result["repair_recommended"] is True
    assert result["frozen_token"] == FREEZE_TOKEN
    assert result["merged_main_sha"] == MERGED_MAIN_SHA


def test_green_ledger_alone_cannot_manufacture_completion():
    receipt = _receipt()
    registry = _registry("SOME_OTHER_FROZEN_TOKEN")
    result = resolver.resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=_ledger(True),
        registry=registry,
        receipt=receipt,
        gate=_gate(receipt),
        merge_evidence=_merge(),
    )
    assert result["complete"] is False
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FREEZE_TOKEN_NOT_FROZEN"


def test_failed_runless_gate_fails_closed():
    receipt = _receipt()
    gate = _gate(receipt)
    gate["conclusion"] = "failure"
    result = resolver.resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=_ledger(True),
        registry=_registry(),
        receipt=receipt,
        gate=gate,
        merge_evidence=_merge(),
    )
    assert result["complete"] is False
    assert result["reason"] == "RUNLESS_FINAL_GATE_NOT_SUCCESS"


def test_gate_must_bind_exact_receipt_candidate_and_digest():
    receipt = _receipt()
    gate = _gate(receipt)
    gate["head_sha"] = "d" * 40
    result = resolver.resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=_ledger(False),
        registry=_registry(),
        receipt=receipt,
        gate=gate,
        merge_evidence=_merge(),
    )
    assert result["complete"] is False
    assert result["reason"] == "RUNLESS_GATE_RECEIPT_MISMATCH"


def test_candidate_must_be_proven_inside_registry_merged_main():
    receipt = _receipt()
    merge = _merge()
    merge["contains_candidate"] = False
    result = resolver.resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=_ledger(False),
        registry=_registry(),
        receipt=receipt,
        gate=_gate(receipt),
        merge_evidence=merge,
    )
    assert result["complete"] is False
    assert result["reason"] == "MERGE_PROVENANCE_MISSING"


def test_tampered_receipt_fails_closed_and_inputs_are_not_mutated():
    ledger = _ledger(False)
    registry = _registry()
    receipt = _receipt()
    gate = _gate(receipt)
    merge = _merge()
    snapshots = tuple(deepcopy(item) for item in (ledger, registry, receipt, gate, merge))
    receipt["task_id"] = "tampered-task"

    result = resolver.resolve_completion(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=ledger,
        registry=registry,
        receipt=receipt,
        gate=gate,
        merge_evidence=merge,
    )
    assert result["complete"] is False
    assert result["reason"] == "RUNLESS_RECEIPT_INVALID"
    assert ledger == snapshots[0]
    assert registry == snapshots[1]
    assert gate == snapshots[3]
    assert merge == snapshots[4]
