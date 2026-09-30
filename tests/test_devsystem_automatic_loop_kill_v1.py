from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.automatic_loop_kill_v1 import (
    ACTION_MUTATIONS,
    LoopKillFailure,
    decide_control_action,
    fingerprint_control_cycle,
)
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state


def _waiting_brain() -> dict:
    return build_state(BrainStateInput(
        program_id="monster-v3",
        program_title="MONSTER V3 upgrades",
        total_steps=8,
        current_step=2,
        step_title="Automatic Loop Kill System",
        execution_state="WAITING_ON_ASYNC",
        repository="kyrepeak/kyre-sports-ai",
        main_sha="1" * 40,
        work_branch="monster-v3-step2-automatic-loop-kill",
        observed_head_sha="2" * 40,
        next_legal_action="Wait for run 9001 to reach a terminal result.",
        completed_steps=(1,),
        frozen_steps=(1,),
        remaining_steps=(3, 4, 5, 6, 7, 8),
        authoritative_run_id=9001,
        authoritative_job_id=7001,
        async_state="IN_PROGRESS",
        updated_at_utc="2026-09-30T00:55:00Z",
    ))


def _observe(state: str = "IN_PROGRESS", **overrides) -> dict:
    action = {
        "task_id": "monster-v3",
        "checkpoint_id": "2",
        "action_type": "observe_async",
        "target": "github:run/9001",
        "authoritative_run_id": 9001,
        "authoritative_job_id": 7001,
        "observed_async_state": state,
        "evidence": {"run_id": 9001, "job_id": 7001, "state": state},
    }
    action.update(overrides)
    return action


def _history(action: dict) -> dict:
    return {
        "control_cycle_fingerprint": fingerprint_control_cycle(action),
        "task_id": action["task_id"],
        "checkpoint_id": action["checkpoint_id"],
        "action_type": action["action_type"],
        "authoritative_run_id": action["authoritative_run_id"],
        "authoritative_job_id": action["authoritative_job_id"],
        "observed_async_state": action["observed_async_state"],
        "result": "AUTHORIZED_OBSERVE",
    }


def test_first_same_run_observation_is_authorized_once():
    result = decide_control_action(_waiting_brain(), _observe(), [])
    assert result["decision"] == "AUTHORIZED_OBSERVE"
    assert result["authoritative_run_id"] == 9001


def test_second_identical_same_state_poll_is_loop_blocked():
    action = _observe()
    result = decide_control_action(_waiting_brain(), action, [_history(action)])
    assert result["decision"] == "LOOP_BLOCKED"
    assert result["reason"] == "same authoritative async state already observed; no new evidence"
    assert result["next_legal_action"] == "WAIT"


def test_same_state_poll_remains_blocked_even_if_timestamp_changes():
    first = _observe()
    repeated = _observe(evidence={
        "run_id": 9001,
        "job_id": 7001,
        "state": "IN_PROGRESS",
        "checked_at": "2026-09-30T00:56:00Z",
    })
    result = decide_control_action(_waiting_brain(), repeated, [_history(first)])
    assert result["decision"] == "LOOP_BLOCKED"


def test_live_async_lock_denies_patch_rerun_and_competing_run():
    for action_type in sorted(ACTION_MUTATIONS):
        action = _observe(action_type=action_type, target="github:mutation")
        result = decide_control_action(_waiting_brain(), action, [])
        assert result["decision"] == "ASYNC_LOCKED", action_type
        assert result["next_legal_action"] == "WAIT"


def test_terminal_transition_is_new_evidence_and_unlocks_next_action():
    prior = _observe("IN_PROGRESS")
    terminal = _observe("SUCCESS")
    result = decide_control_action(_waiting_brain(), terminal, [_history(prior)])
    assert result["decision"] == "AUTHORIZED_TERMINAL_TRANSITION"
    assert result["terminal_state"] == "SUCCESS"
    assert result["next_legal_action"] == "CLASSIFY_TERMINAL_RESULT"


def test_failure_terminal_transition_is_also_new_evidence():
    prior = _observe("IN_PROGRESS")
    terminal = _observe("FAILURE")
    result = decide_control_action(_waiting_brain(), terminal, [_history(prior)])
    assert result["decision"] == "AUTHORIZED_TERMINAL_TRANSITION"
    assert result["terminal_state"] == "FAILURE"


def test_wrong_run_cannot_replace_authoritative_async_run():
    action = _observe(
        authoritative_run_id=9002,
        target="github:run/9002",
        evidence={"run_id": 9002, "job_id": 7001, "state": "IN_PROGRESS"},
    )
    result = decide_control_action(_waiting_brain(), action, [])
    assert result["decision"] == "STALE_RUN_BLOCKED"
    assert result["authoritative_run_id"] == 9001


def test_control_cycle_fingerprint_ignores_volatile_check_time():
    first = _observe(evidence={
        "run_id": 9001,
        "job_id": 7001,
        "state": "IN_PROGRESS",
        "checked_at": "2026-09-30T00:56:00Z",
    })
    second = _observe(evidence={
        "run_id": 9001,
        "job_id": 7001,
        "state": "IN_PROGRESS",
        "checked_at": "2026-09-30T00:57:00Z",
    })
    assert fingerprint_control_cycle(first) == fingerprint_control_cycle(second)


def test_control_cycle_fingerprint_changes_when_async_state_changes():
    assert fingerprint_control_cycle(_observe("IN_PROGRESS")) != fingerprint_control_cycle(_observe("SUCCESS"))


def test_non_waiting_brain_rejects_async_observation_as_state_mismatch():
    brain = build_state(BrainStateInput(
        program_id="monster-v3",
        program_title="MONSTER V3 upgrades",
        total_steps=8,
        current_step=2,
        step_title="Automatic Loop Kill System",
        execution_state="ACTIVE",
        repository="kyrepeak/kyre-sports-ai",
        main_sha="1" * 40,
        work_branch="monster-v3-step2-automatic-loop-kill",
        observed_head_sha="2" * 40,
        next_legal_action="Run local proof.",
        completed_steps=(1,),
        frozen_steps=(1,),
        remaining_steps=(3, 4, 5, 6, 7, 8),
        updated_at_utc="2026-09-30T00:55:00Z",
    ))
    result = decide_control_action(brain, _observe(), [])
    assert result["decision"] == "STATE_MISMATCH_BLOCKED"


def test_malformed_action_fails_closed():
    try:
        fingerprint_control_cycle({"task_id": "monster-v3"})
    except LoopKillFailure as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("malformed action must fail closed")


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "automatic_loop_kill_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_AUTOMATIC_LOOP_KILL_V1_GREEN" in completed.stdout
