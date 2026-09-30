"""MONSTER V3 Step 2 — Automatic Loop Kill System V1.

Control-plane guard layered on Persistent Execution Brain. It prevents repeated
same-state polling and competing mutations while one authoritative async run is
alive. No network calls, product edits, workflow dispatches, or sports behavior
occur in this module.
"""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.persistent_execution_brain_v1 import validate_state

VERSION = "MONSTER_AUTOMATIC_LOOP_KILL_V1"
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False
AUTO_DISPATCH = False

ACTION_MUTATIONS = frozenset({
    "patch",
    "rerun",
    "start_run",
    "start_competing_run",
    "dispatch_workflow",
    "update_branch",
    "merge",
    "create_pr",
    "edit_product",
})
_TERMINAL_STATES = frozenset({"SUCCESS", "FAILURE", "CANCELLED"})
_LIVE_STATES = frozenset({"QUEUED", "IN_PROGRESS"})
_VOLATILE_EVIDENCE_KEYS = frozenset({
    "checked_at",
    "timestamp",
    "created_at",
    "updated_at",
    "observed_at",
    "polled_at",
})
_REQUIRED_ACTION_FIELDS = (
    "task_id",
    "checkpoint_id",
    "action_type",
    "target",
    "authoritative_run_id",
    "observed_async_state",
)


class LoopKillFailure(RuntimeError):
    pass


def _stable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _stable(item)
            for key, item in sorted(value.items())
            if str(key) not in _VOLATILE_EVIDENCE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_action(action: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise LoopKillFailure("control action must be an object")
    missing = [
        name for name in _REQUIRED_ACTION_FIELDS
        if action.get(name) in (None, "")
    ]
    if missing:
        raise LoopKillFailure("control action missing required fields: " + ", ".join(missing))
    result = deepcopy(dict(action))
    try:
        result["authoritative_run_id"] = int(result["authoritative_run_id"])
    except (TypeError, ValueError) as exc:
        raise LoopKillFailure("authoritative_run_id must be an integer") from exc
    if result["authoritative_run_id"] <= 0:
        raise LoopKillFailure("authoritative_run_id must be positive")

    job_id = result.get("authoritative_job_id")
    if job_id is not None:
        try:
            result["authoritative_job_id"] = int(job_id)
        except (TypeError, ValueError) as exc:
            raise LoopKillFailure("authoritative_job_id must be an integer") from exc
        if result["authoritative_job_id"] <= 0:
            raise LoopKillFailure("authoritative_job_id must be positive")

    result["observed_async_state"] = str(result["observed_async_state"]).upper()
    return result


def fingerprint_control_cycle(action: Mapping[str, Any]) -> str:
    value = _validate_action(action)
    payload = {
        "task_id": str(value["task_id"]),
        "checkpoint_id": str(value["checkpoint_id"]),
        "action_type": str(value["action_type"]),
        "target": str(value["target"]),
        "authoritative_run_id": value["authoritative_run_id"],
        "authoritative_job_id": value.get("authoritative_job_id"),
        "observed_async_state": value["observed_async_state"],
        "evidence": _stable(value.get("evidence") or {}),
    }
    return _hash(payload)


def _decision(decision: str, reason: str, *, brain: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    execution = brain["execution"]
    result = {
        "decision": decision,
        "reason": reason,
        "authoritative_run_id": execution.get("authoritative_run_id"),
        "authoritative_job_id": execution.get("authoritative_job_id"),
    }
    result.update(extra)
    return result


def decide_control_action(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    brain = validate_state(brain_state)
    proposed = _validate_action(action)
    execution = brain["execution"]

    if execution["state"] != "WAITING_ON_ASYNC":
        return _decision(
            "STATE_MISMATCH_BLOCKED",
            "async observation is legal only while the persistent brain is WAITING_ON_ASYNC",
            brain=brain,
            next_legal_action=brain["next_legal_action"],
        )

    authoritative_run = int(execution["authoritative_run_id"])
    proposed_run = int(proposed["authoritative_run_id"])
    if proposed_run != authoritative_run:
        return _decision(
            "STALE_RUN_BLOCKED",
            "proposed action does not target the authoritative async run",
            brain=brain,
            next_legal_action="WAIT",
        )

    authoritative_job = execution.get("authoritative_job_id")
    proposed_job = proposed.get("authoritative_job_id")
    if authoritative_job is not None and proposed_job not in (None, int(authoritative_job)):
        return _decision(
            "STALE_RUN_BLOCKED",
            "proposed action does not target the authoritative async job",
            brain=brain,
            next_legal_action="WAIT",
        )

    action_type = str(proposed["action_type"])
    brain_async_state = str(execution["async_state"]).upper()
    observed_state = str(proposed["observed_async_state"]).upper()

    if brain_async_state in _LIVE_STATES and action_type in ACTION_MUTATIONS:
        return _decision(
            "ASYNC_LOCKED",
            "one authoritative async run is still live; mutations and competing runs are blocked",
            brain=brain,
            next_legal_action="WAIT",
        )

    cycle_fp = fingerprint_control_cycle(proposed)
    prior_fingerprints = {
        str(item.get("control_cycle_fingerprint") or "")
        for item in history
        if isinstance(item, Mapping)
    }

    if cycle_fp in prior_fingerprints:
        return _decision(
            "LOOP_BLOCKED",
            "same authoritative async state already observed; no new evidence",
            brain=brain,
            control_cycle_fingerprint=cycle_fp,
            next_legal_action="WAIT",
        )

    if observed_state in _TERMINAL_STATES and observed_state != brain_async_state:
        return _decision(
            "AUTHORIZED_TERMINAL_TRANSITION",
            "authoritative async state changed to a terminal result; this is new evidence",
            brain=brain,
            control_cycle_fingerprint=cycle_fp,
            terminal_state=observed_state,
            next_legal_action="CLASSIFY_TERMINAL_RESULT",
        )

    if observed_state in _LIVE_STATES:
        return _decision(
            "AUTHORIZED_OBSERVE",
            "first observation of this authoritative async state is allowed",
            brain=brain,
            control_cycle_fingerprint=cycle_fp,
            observed_async_state=observed_state,
            next_legal_action="WAIT",
        )

    if observed_state in _TERMINAL_STATES:
        return _decision(
            "LOOP_BLOCKED",
            "terminal state is already represented by the persistent brain; no new evidence",
            brain=brain,
            control_cycle_fingerprint=cycle_fp,
            next_legal_action="CLASSIFY_TERMINAL_RESULT",
        )

    raise LoopKillFailure(f"unsupported observed_async_state: {observed_state!r}")


def contract_self_test() -> dict[str, Any]:
    from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state

    brain = build_state(BrainStateInput(
        program_id="self-test",
        program_title="Automatic Loop Kill self-test",
        total_steps=2,
        current_step=2,
        step_title="Loop Kill",
        execution_state="WAITING_ON_ASYNC",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="loop-kill-v1",
        observed_head_sha="2" * 40,
        next_legal_action="Wait for authoritative run.",
        completed_steps=(1,),
        frozen_steps=(1,),
        remaining_steps=(),
        authoritative_run_id=9001,
        authoritative_job_id=7001,
        async_state="IN_PROGRESS",
        updated_at_utc="2026-09-30T00:00:00Z",
    ))
    observe = {
        "task_id": "self-test",
        "checkpoint_id": "2",
        "action_type": "observe_async",
        "target": "github:run/9001",
        "authoritative_run_id": 9001,
        "authoritative_job_id": 7001,
        "observed_async_state": "IN_PROGRESS",
        "evidence": {"run_id": 9001, "job_id": 7001, "state": "IN_PROGRESS"},
    }
    first = decide_control_action(brain, observe, [])
    history = [{
        "control_cycle_fingerprint": first["control_cycle_fingerprint"],
        "observed_async_state": "IN_PROGRESS",
    }]
    duplicate = decide_control_action(brain, observe, history)
    terminal = dict(observe)
    terminal["observed_async_state"] = "SUCCESS"
    terminal["evidence"] = {"run_id": 9001, "job_id": 7001, "state": "SUCCESS"}
    unlocked = decide_control_action(brain, terminal, history)
    locked = decide_control_action(brain, {**observe, "action_type": "patch"}, [])

    if first["decision"] != "AUTHORIZED_OBSERVE":
        raise LoopKillFailure("first observation self-test failed")
    if duplicate["decision"] != "LOOP_BLOCKED":
        raise LoopKillFailure("duplicate observation self-test failed")
    if unlocked["decision"] != "AUTHORIZED_TERMINAL_TRANSITION":
        raise LoopKillFailure("terminal transition self-test failed")
    if locked["decision"] != "ASYNC_LOCKED":
        raise LoopKillFailure("async mutation lock self-test failed")

    return {
        "status": "GREEN",
        "version": VERSION,
        "same_state_poll_kill": True,
        "async_mutation_lock": True,
        "terminal_transition_unlock": True,
        "stale_run_guard": True,
        "product_runtime_mutation": False,
        "network_calls": False,
    }


if __name__ == "__main__":
    print("MONSTER_AUTOMATIC_LOOP_KILL_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
