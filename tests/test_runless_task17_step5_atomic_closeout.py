from __future__ import annotations

import importlib

import pytest


MAIN_SHA = "0" * 40
CANDIDATE_SHA = "c" * 40
LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
REGISTRY_HASH = "a" * 64


def _engine():
    try:
        return importlib.import_module("runless_proof_plane.atomic_closeout")
    except ModuleNotFoundError:
        pytest.fail("Runless Task 17 Step 5 atomic closeout engine is missing")


def _request(**overrides):
    base = {
        "main_sha": MAIN_SHA,
        "source_candidate_sha": CANDIDATE_SHA,
        "lease_id": LEASE_ID,
        "lease_owner": "monster-v2-runless-task17-step5",
        "registry_revision": 174,
        "registry_state_hash": REGISTRY_HASH,
        "premerge_proof_id": "runless-task17-step5-atomic-closeout-candidate",
        "premerge_receipt_digest": "d" * 64,
        "freeze_token": "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT_FROZEN",
        "freeze_artifacts": {
            "runless_proof_plane/atomic_closeout.py": "1" * 40,
            "tests/test_runless_task17_step5_atomic_closeout.py": "2" * 40,
        },
        "github_actions_fallback_authorized": False,
    }
    base.update(overrides)
    return base


def _state():
    return {
        "main_sha": MAIN_SHA,
        "candidate_parent_shas": [CANDIDATE_SHA],
        "lease": {
            "lease_id": LEASE_ID,
            "owner_id": "monster-v2-runless-task17-step5",
            "resource_identity": {
                "main_sha": MAIN_SHA,
                "registry_state_hash": REGISTRY_HASH,
            },
        },
        "registry": {
            "revision": 174,
            "state_hash": REGISTRY_HASH,
            "source_main_sha": MAIN_SHA,
            "entries": {},
            "active_thaws": [{"thaw_id": "UNRELATED", "status": "ACTIVE"}],
        },
        "merged_receipt": None,
        "gate_receipt_digest": None,
    }


def test_atomic_closeout_completes_all_safe_steps_in_one_decision():
    engine = _engine()
    result = engine.evaluate_atomic_closeout(_request(), _state())
    assert result["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_READY"
    assert result["allowed"] is True
    assert result["github_actions_fallback"] == 0
    assert result["static_evidence_reexecuted"] is False
    assert result["required_operations"] == [
        "PERSIST_OR_VERIFY_MERGED_RECEIPT",
        "PUBLISH_OR_VERIFY_RUNLESS_GATE",
        "FREEZE_OR_VERIFY_EXACT_ARTIFACTS",
        "CANONICAL_READBACK",
    ]


def test_exact_replay_is_idempotent_not_duplicate_work():
    engine = _engine()
    state = _state()
    state["merged_receipt"] = {"prior_digest": "d" * 64, "candidate_sha": MAIN_SHA}
    state["gate_receipt_digest"] = "m" * 64
    state["registry"]["entries"]["RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT_FROZEN"] = {
        "status": "FROZEN",
        "checkpoint_id": "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT_FROZEN",
        "source_main_sha": MAIN_SHA,
        "artifacts": _request()["freeze_artifacts"],
    }
    result = engine.evaluate_atomic_closeout(_request(), state)
    assert result["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_ALREADY_COMPLETE"
    assert result["duplicate_write_required"] is False


def test_registry_cas_drift_fails_closed_without_retry_loop():
    engine = _engine()
    state = _state()
    state["registry"]["revision"] = 175
    result = engine.evaluate_atomic_closeout(_request(), state)
    assert result["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_REGISTRY_STALE"
    assert result["allowed"] is False
    assert result["retry_allowed_now"] is False
    assert result["next_legal_action"] == "REREAD_REGISTRY_AND_STEP2A"


def test_main_or_candidate_ancestry_drift_fails_closed():
    engine = _engine()
    moved = _state()
    moved["main_sha"] = "9" * 40
    assert engine.evaluate_atomic_closeout(_request(), moved)["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_MAIN_DRIFT"

    wrong_parent = _state()
    wrong_parent["candidate_parent_shas"] = ["8" * 40]
    assert engine.evaluate_atomic_closeout(_request(), wrong_parent)["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_ANCESTRY_DRIFT"


def test_lease_identity_drift_fails_closed():
    engine = _engine()
    state = _state()
    state["lease"]["owner_id"] = "other-owner"
    result = engine.evaluate_atomic_closeout(_request(), state)
    assert result["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_STEP2A_REQUIRED"
    assert result["allowed"] is False


def test_actions_fallback_or_product_mutation_can_never_be_authorized():
    engine = _engine()
    assert engine.NETWORK_CALLS is False
    assert engine.AUTO_MUTATE is False
    assert engine.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert engine.GITHUB_ACTIONS_FALLBACK == 0
    result = engine.evaluate_atomic_closeout(
        _request(github_actions_fallback_authorized=True),
        _state(),
    )
    assert result["decision"] == "RUNLESS_ATOMIC_CLOSEOUT_ACTIONS_FALLBACK_BLOCKED"
    assert result["allowed"] is False
