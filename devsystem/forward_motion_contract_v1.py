"""Permanent DevSystem contract for Monster anti-loop / forward-motion controls.

This validator is dependency-light and is called by the existing required
``permanent-contract`` test lane, avoiding an extra CI fan-out job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devsystem.a9_anti_loop_replay_v1 import run_replay
from devsystem.checkpoint_ledger_v1 import validate_ledger
from devsystem.forward_motion_v1 import decide, fingerprint_action, load_policy


class ForwardMotionContractFailure(RuntimeError):
    pass


def _ledger(*, done: bool = False) -> dict[str, Any]:
    checkpoints = [
        {
            "id": "1",
            "state": "DONE",
            "entry_condition": "approved",
            "exit_condition": "rules locked",
            "evidence": {"verified": True},
        },
        {
            "id": "2",
            "state": "DONE" if done else "ACTIVE",
            "entry_condition": "rules locked",
            "exit_condition": "contract green",
            "evidence": {"verified": True} if done else {},
        },
    ]
    return {
        "task_id": "monster-forward-motion-contract-v1",
        "title": "Monster Forward Motion Contract V1",
        "mode": "strict_auto_continue",
        "status": "DONE" if done else "ACTIVE",
        "current_checkpoint": None if done else "2",
        "total_checkpoints": 2,
        "completed_checkpoints": 2 if done else 1,
        "remaining_checkpoints": 0 if done else 1,
        "exit_conditions": ["contract green"],
        "active_blocker": None,
        "deferred_findings": [],
        "evidence_fingerprints": [],
        "action_history": [],
        "checkpoints": checkpoints,
    }


def _action(**overrides: Any) -> dict[str, Any]:
    action: dict[str, Any] = {
        "task_id": "monster-forward-motion-contract-v1",
        "checkpoint_id": "2",
        "action_type": "production_proof",
        "target": "render:/health",
        "inputs": {"commit": "abc123", "deployment": "dep-1"},
        "evidence_class": "production_identity",
        "scope_relation": "in_scope",
        "retry": False,
        "failure_class": None,
        "new_hypothesis": False,
        "requires_user": False,
        "resolvable_with_available_tools": True,
    }
    action.update(overrides)
    return action


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardMotionContractFailure(message)


def validate() -> dict[str, Any]:
    policy = load_policy()
    _require(policy.get("mode") == "strict_auto_continue", "strict auto-continue mode drift")

    budgets = policy.get("retry_budgets") or {}
    _require(int(budgets.get("deterministic-regression", -1)) == 0, "deterministic retry budget drift")
    _require(int(budgets.get("transient-capable", -1)) == 1, "transient retry budget drift")
    _require(int(budgets.get("unknown_evidence_actions", -1)) == 1, "unknown evidence budget drift")

    required_decisions = {
        "ALLOW_ADVANCE",
        "ALLOW_NEW_HYPOTHESIS",
        "ALLOW_CONTROLLED_RETRY",
        "REJECT_DUPLICATE_PROOF",
        "REJECT_CLOSED_CHECKPOINT_REOPEN",
        "DEFER_SIDE_QUEST",
        "STOP_EXTERNAL_BLOCKER",
        "TASK_COMPLETE",
    }
    _require(required_decisions.issubset(set(policy.get("decisions") or [])), "decision registry drift")

    ledger = _ledger()
    ledger_result = validate_ledger(ledger)
    _require(ledger_result["status"] == "GREEN", "checkpoint ledger validation failed")

    proof = _action()
    proof_fp = fingerprint_action(proof)
    duplicate = decide(ledger, proof, [{"fingerprint": proof_fp, "result": "success"}], policy)
    _require(duplicate["decision"] == "REJECT_DUPLICATE_PROOF", "duplicate proof guard drift")

    deterministic = _action(retry=True, failure_class="deterministic-regression")
    deterministic_result = decide(
        ledger,
        deterministic,
        [{"fingerprint": fingerprint_action(deterministic), "result": "failure"}],
        policy,
    )
    _require(
        deterministic_result["decision"] == "REJECT_DUPLICATE_PROOF"
        and deterministic_result.get("retry_budget_remaining") == 0,
        "deterministic zero-retry guard drift",
    )

    transient = _action(retry=True, failure_class="transient-capable")
    transient_fp = fingerprint_action(transient)
    first_retry = decide(
        ledger,
        transient,
        [{"fingerprint": transient_fp, "result": "failure", "failure_class": "transient-capable"}],
        policy,
    )
    _require(first_retry["decision"] == "ALLOW_CONTROLLED_RETRY", "transient first-retry guard drift")
    second_retry = decide(
        ledger,
        transient,
        [
            {"fingerprint": transient_fp, "result": "failure", "failure_class": "transient-capable"},
            {
                "fingerprint": transient_fp,
                "result": "failure",
                "failure_class": "transient-capable",
                "controlled_retry": True,
            },
        ],
        policy,
    )
    _require(second_retry["decision"] == "REJECT_DUPLICATE_PROOF", "transient retry cap drift")

    blocked_ledger = _ledger()
    blocked_ledger["active_blocker"] = {
        "blocker_id": "production-identity",
        "checkpoint_id": "2",
        "root_cause_class": "production_identity",
    }
    second_blocker = _action(
        action_type="open_blocker",
        target="posthog:event-proof",
        inputs={"blocker_id": "telemetry-proof"},
        evidence_class="telemetry",
    )
    blocker_result = decide(blocked_ledger, second_blocker, [], policy)
    _require(blocker_result["decision"] == "DEFER_SIDE_QUEST", "single-blocker guard drift")

    unrelated = decide(ledger, _action(scope_relation="unrelated"), [], policy)
    _require(unrelated["decision"] == "DEFER_SIDE_QUEST", "side-quest deferral drift")

    terminal = decide(_ledger(done=True), proof, [], policy)
    _require(terminal["decision"] == "TASK_COMPLETE", "terminal finish-line guard drift")

    replay = run_replay()
    _require(replay.get("status") == "GREEN", "A9 anti-loop replay failed")
    _require(replay.get("max_active_blockers") == 1, "A9 replay blocker cardinality drift")
    _require(replay.get("in_scope_approval_stops") == 0, "A9 replay approval-churn drift")
    _require(replay.get("post_finish_decision") == "TASK_COMPLETE", "A9 replay terminal drift")
    _require(replay.get("invented_post_finish_checkpoints") == 0, "A9 replay invented work")

    result = {
        "status": "GREEN",
        "mode": policy["mode"],
        "duplicate_proof_guard": True,
        "deterministic_zero_retry": True,
        "transient_single_retry": True,
        "one_active_blocker": True,
        "side_quest_deferral": True,
        "terminal_task_authoritative": True,
        "a9_replay_permanent": True,
    }
    print("DEVSYSTEM_FORWARD_MOTION_CONTRACT_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    validate()
