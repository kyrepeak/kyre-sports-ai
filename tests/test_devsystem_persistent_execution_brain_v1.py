from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load():
    target = ROOT / "devsystem/persistent_execution_brain_v1.py"
    spec = importlib.util.spec_from_file_location("persistent_execution_brain_v1", target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["persistent_execution_brain_v1"] = module
    spec.loader.exec_module(module)
    return module


def _state(module, **overrides):
    values = {
        "program_id": "monster-v3",
        "program_title": "MONSTER V3 upgrades",
        "total_steps": 8,
        "current_step": 1,
        "step_title": "Persistent Execution Brain",
        "execution_state": "ACTIVE",
        "repository": "kyrepeak/kyre-sports-ai",
        "main_sha": "1" * 40,
        "work_branch": "monster-v3-step1-persistent-execution-brain",
        "observed_head_sha": "2" * 40,
        "next_legal_action": "Run focused Step-1 proof.",
        "completed_steps": (),
        "frozen_steps": (),
        "remaining_steps": (2, 3, 4, 5, 6, 7, 8),
        "updated_at_utc": "2026-09-30T00:00:00Z",
    }
    values.update(overrides)
    return module.build_state(module.BrainStateInput(**values))


def test_contract_self_test_is_green():
    module = _load()
    result = module.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["persistence_surface"] == "github_issue_ledger"
    assert result["fingerprint_guard"] is True
    assert result["step_monotonicity"] is True
    assert result["async_lock"] is True
    assert result["repo_drift_guard"] is True
    assert result["product_runtime_mutation"] is False


def test_issue_ledger_round_trip_preserves_exact_state():
    module = _load()
    state = _state(module)
    parsed = module.parse_issue_ledger(module.render_issue_ledger(state))
    assert parsed == state
    assert parsed["execution"]["current_step"] == 1
    assert parsed["progress"]["remaining_steps"] == [2, 3, 4, 5, 6, 7, 8]


def test_tampered_state_fails_closed():
    module = _load()
    state = _state(module)
    state["next_legal_action"] = "Do something else."
    with pytest.raises(module.BrainStateFailure, match="fingerprint mismatch"):
        module.validate_state(state)


def test_frozen_step_must_be_completed_and_monotonic():
    module = _load()
    frozen = _state(
        module,
        execution_state="FROZEN",
        completed_steps=(1,),
        frozen_steps=(1,),
        remaining_steps=(2, 3, 4, 5, 6, 7, 8),
        next_legal_action="Do not reopen Step 1 without contradictory evidence.",
    )
    assert module.validate_state(frozen)["execution"]["state"] == "FROZEN"

    with pytest.raises(module.BrainStateFailure, match="frozen step"):
        _state(
            module,
            execution_state="FROZEN",
            completed_steps=(),
            frozen_steps=(1,),
            remaining_steps=(2, 3, 4, 5, 6, 7, 8),
        )


def test_waiting_on_async_requires_one_authoritative_live_run():
    module = _load()
    waiting = _state(
        module,
        execution_state="WAITING_ON_ASYNC",
        authoritative_run_id=123456,
        async_state="IN_PROGRESS",
        next_legal_action="Wait for run 123456 to reach a terminal result.",
    )
    assert waiting["execution"]["authoritative_run_id"] == 123456

    with pytest.raises(module.BrainStateFailure, match="one live authoritative run"):
        _state(
            module,
            execution_state="WAITING_ON_ASYNC",
            async_state="IN_PROGRESS",
        )


def test_repo_drift_forces_revalidation_before_editing():
    module = _load()
    state = _state(module)
    packet = module.build_resume_packet(
        state,
        current_main_sha="3" * 40,
        current_head_sha="2" * 40,
    )
    assert packet["status"] == "REVALIDATE"
    assert packet["drift"]["requires_revalidation"] is True
    assert packet["next_legal_action"].startswith("Revalidate repository identity")


def test_blocked_state_requires_explicit_single_blocker():
    module = _load()
    blocked = _state(
        module,
        execution_state="BLOCKED",
        blocker="Deployment identity does not match expected main.",
        owner="DEPLOYMENT",
        failure_class="D_DEPLOYMENT",
        next_legal_action="Restore deployment identity before editing product code.",
    )
    assert blocked["execution"]["owner"] == "DEPLOYMENT"

    with pytest.raises(module.BrainStateFailure, match="requires a blocker"):
        _state(module, execution_state="BLOCKED")
