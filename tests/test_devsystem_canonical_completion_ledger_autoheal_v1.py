from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from devsystem import canonical_completion_ledger_autoheal_v1 as autoheal
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
        "revision": 184,
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
        proof_id="ledger-autoheal-proof-1",
        task_id=TASK_ID,
        project="API2",
        workstream="api2-finalization-authority-v1-step2",
        step="merged-main-closeout",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={"sentinel.py": "b" * 40},
        dependency_map={},
        registry_before={"revision": 183},
        registry_after={"revision": 184},
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


def _ledger(*, claimed: bool = False, task_id: str = TASK_ID) -> dict:
    return {
        "version": 3,
        "task_id": task_id,
        "status": "DONE",
        "green_plus_frozen_claimed": claimed,
        "freeze_exit": {
            "frozen_token": FREEZE_TOKEN,
            "claimed": claimed,
        },
    }


def _call(ledger: dict, *, registry: dict | None = None, gate: dict | None = None):
    receipt = _receipt()
    return autoheal.resolve_and_plan_ledger_autoheal(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=ledger,
        registry=registry or _registry(),
        receipt=receipt,
        gate=gate or _gate(receipt),
        merge_evidence=_merge(),
    )


def test_canonical_completion_repairs_stale_ledger_without_mutating_input():
    ledger = _ledger(claimed=False)
    original = deepcopy(ledger)

    result = _call(ledger)

    assert result["decision"] == "LEDGER_AUTOHEAL_PLANNED"
    assert result["write_required"] is True
    assert ledger == original
    healed = result["healed_ledger"]
    assert healed["status"] == "DONE"
    assert healed["green_plus_frozen_claimed"] is True
    assert healed["freeze_exit"]["frozen_token"] == FREEZE_TOKEN
    assert healed["freeze_exit"]["claimed"] is True
    completion = healed["canonical_completion"]
    assert completion["authority"] == "FROZEN_REGISTRY_RUNLESS"
    assert completion["merged_main_sha"] == MERGED_MAIN_SHA
    assert completion["receipt_digest"] == result["canonical_completion"]["receipt_digest"]
    assert completion["registry_revision"] == 184
    assert completion["freeze_token"] == FREEZE_TOKEN


def test_invalid_canonical_chain_never_manufactures_ledger_completion():
    ledger = _ledger(claimed=False)
    original = deepcopy(ledger)
    receipt = _receipt()
    failed_gate = _gate(receipt)
    failed_gate["conclusion"] = "failure"

    result = autoheal.resolve_and_plan_ledger_autoheal(
        task_id=TASK_ID,
        freeze_token=FREEZE_TOKEN,
        ledger=ledger,
        registry=_registry(),
        receipt=receipt,
        gate=failed_gate,
        merge_evidence=_merge(),
    )

    assert result["decision"] == "LEDGER_AUTOHEAL_BLOCKED"
    assert result["write_required"] is False
    assert result["healed_ledger"] is None
    assert result["canonical_completion"]["complete"] is False
    assert ledger == original


def test_already_aligned_ledger_is_idempotent_and_requires_no_write():
    ledger = _ledger(claimed=True)
    first = _call(ledger)

    assert first["decision"] == "LEDGER_ALREADY_ALIGNED"
    assert first["write_required"] is False
    assert first["healed_ledger"] == ledger


def test_task_identity_mismatch_fails_closed_even_with_valid_canonical_evidence():
    ledger = _ledger(claimed=False, task_id="wrong-task")
    original = deepcopy(ledger)

    result = _call(ledger)

    assert result["decision"] == "LEDGER_AUTOHEAL_IDENTITY_MISMATCH"
    assert result["write_required"] is False
    assert result["healed_ledger"] is None
    assert ledger == original


def test_second_pass_after_planned_heal_is_noop():
    ledger = _ledger(claimed=False)
    first = _call(ledger)
    assert first["write_required"] is True

    second = _call(first["healed_ledger"])
    assert second["decision"] == "LEDGER_ALREADY_ALIGNED"
    assert second["write_required"] is False
