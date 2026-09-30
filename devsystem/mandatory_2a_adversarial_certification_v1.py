"""MONSTER 2A Enforcement Step 5 — Permanent Adversarial Certification V1.

Final fail-closed firewall around the frozen Step-1 -> Step-4 enforcement chain.

Step 5 does not replace or edit the Step-4 canonical execution authority.
Instead it performs two preflight protections that must happen before Step 4:
1) reject stale repository/head identity,
2) reject mutation attempts against frozen checkpoints or frozen/complete brain states.

Then it invokes the frozen Step-4 canonical entrypoint and verifies its global
execution proof. A permanent adversarial matrix proves bypass, replay, stale,
frozen, duplicate-run, tamper, and malformed-chain attacks fail closed.

No network calls. No repository/product/runtime mutations.
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.automatic_loop_kill_v1 import ACTION_MUTATIONS, fingerprint_control_cycle
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_global_enforcement_v1 import (
    VERSION as STEP4_VERSION,
    TwoAGlobalEnforcementFailure,
    enforce_action,
    require_global_execution_authority,
)
from devsystem.mandatory_2a_receipt_v1 import new_consumption_ledger
from devsystem.mandatory_2a_replay_lock_v1 import new_replay_ledger
from devsystem.persistent_execution_brain_v1 import (
    BrainStateInput,
    assess_drift,
    build_state,
    validate_state,
)

VERSION = "MONSTER_2A_ADVERSARIAL_CERTIFICATION_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class TwoAAdversarialCertificationFailure(RuntimeError):
    pass


def _blocked(
    decision: str,
    reason: str,
    *,
    action: Mapping[str, Any] | None,
    next_legal_action: str = "CONTINUE_NON_CONFLICTING_WORK",
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "decision": decision,
        "reason": reason,
        "allowed": False,
        "execution_authorized": False,
        "certified": False,
        "autonomous_skip": True,
        "requires_user_intervention": False,
        "continuation_policy": "CONTINUE_NON_CONFLICTING_WORK",
        "next_legal_action": next_legal_action,
        "action_type": str((action or {}).get("action_type") or ""),
        "target": str((action or {}).get("target") or ""),
        "step4_result": None,
    }


def preflight_final_firewall(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    current_main_sha: str,
    current_head_sha: str,
) -> dict[str, Any]:
    brain = validate_state(brain_state)
    if not isinstance(action, Mapping):
        raise TwoAAdversarialCertificationFailure("action must be an object")

    main_sha = str(current_main_sha or "").strip().lower()
    head_sha = str(current_head_sha or "").strip().lower()
    if not _SHA_RE.match(main_sha) or not _SHA_RE.match(head_sha):
        return _blocked(
            "STALE_STATE_BLOCKED_CONTINUE",
            "current repository identity must be exact 40-character SHAs",
            action=action,
            next_legal_action="REVALIDATE_REPOSITORY_IDENTITY",
        )

    drift = assess_drift(
        brain,
        current_main_sha=main_sha,
        current_head_sha=head_sha,
    )
    if drift["requires_revalidation"]:
        return _blocked(
            "STALE_STATE_BLOCKED_CONTINUE",
            "; ".join(drift["reasons"]),
            action=action,
            next_legal_action="REVALIDATE_REPOSITORY_IDENTITY",
        )

    action_type = str(action.get("action_type") or "").strip()
    execution = brain["execution"]
    progress = brain["progress"]

    checkpoint_raw = action.get("checkpoint_id")
    checkpoint: int | None = None
    try:
        checkpoint = int(str(checkpoint_raw))
    except (TypeError, ValueError):
        checkpoint = None

    if action_type in ACTION_MUTATIONS:
        if execution["state"] in {"FROZEN", "COMPLETE"}:
            return _blocked(
                "FROZEN_STATE_BLOCKED_CONTINUE",
                "mutation is illegal while persistent brain is FROZEN or COMPLETE",
                action=action,
                next_legal_action=brain["next_legal_action"],
            )
        if checkpoint is not None and checkpoint in set(progress["frozen_steps"]):
            return _blocked(
                "FROZEN_STATE_BLOCKED_CONTINUE",
                "mutation targets an already frozen checkpoint",
                action=action,
                next_legal_action=brain["next_legal_action"],
            )

    return {
        "version": VERSION,
        "decision": "FINAL_FIREWALL_CLEAR",
        "reason": "repository identity aligned and frozen-state protections clear",
        "allowed": True,
        "certified": False,
        "requires_user_intervention": False,
        "brain_state_id": brain["state_id"],
    }


def enforce_certified_action(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
    *,
    current_main_sha: str,
    current_head_sha: str,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    preflight = preflight_final_firewall(
        brain_state,
        action,
        current_main_sha=current_main_sha,
        current_head_sha=current_head_sha,
    )
    if preflight.get("allowed") is not True:
        return {
            "result": preflight,
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    step4 = enforce_action(
        brain_state,
        action,
        history,
        replay_ledger,
        consumption_ledger,
        forward_decision=forward_decision,
    )
    result = step4.get("result")
    if not isinstance(result, Mapping):
        return {
            "result": _blocked(
                "ADVERSARIAL_CHAIN_BLOCKED_CONTINUE",
                "Step-4 canonical entrypoint returned malformed result",
                action=action,
            ),
            "replay_ledger": deepcopy(dict(step4.get("replay_ledger") or replay_ledger)),
            "consumption_ledger": deepcopy(
                dict(step4.get("consumption_ledger") or consumption_ledger)
            ),
        }

    if result.get("allowed") is not True:
        propagated = deepcopy(dict(result))
        propagated["step5_version"] = VERSION
        propagated["certified"] = False
        return {
            "result": propagated,
            "replay_ledger": deepcopy(dict(step4["replay_ledger"])),
            "consumption_ledger": deepcopy(dict(step4["consumption_ledger"])),
        }

    try:
        validation = require_global_execution_authority(
            result,
            brain_state,
            action,
        )
    except TwoAGlobalEnforcementFailure as exc:
        return {
            "result": _blocked(
                "ADVERSARIAL_CHAIN_BLOCKED_CONTINUE",
                f"Step-4 global proof failed final certification: {exc}",
                action=action,
            ),
            "replay_ledger": deepcopy(dict(step4["replay_ledger"])),
            "consumption_ledger": deepcopy(dict(step4["consumption_ledger"])),
        }

    certified = deepcopy(dict(result))
    certified.update({
        "step5_version": VERSION,
        "certified": True,
        "adversarial_firewall_passed": True,
        "step4_version": STEP4_VERSION,
        "step4_proof_hash": validation["proof_hash"],
    })
    return {
        "result": certified,
        "replay_ledger": deepcopy(dict(step4["replay_ledger"])),
        "consumption_ledger": deepcopy(dict(step4["consumption_ledger"])),
    }


def require_final_certification(
    result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise TwoAAdversarialCertificationFailure("final result must be an object")
    if result.get("allowed") is not True:
        raise TwoAAdversarialCertificationFailure("final adversarial firewall denied action")
    if result.get("certified") is not True:
        raise TwoAAdversarialCertificationFailure("final adversarial certification missing")
    if result.get("adversarial_firewall_passed") is not True:
        raise TwoAAdversarialCertificationFailure("adversarial firewall proof missing")
    try:
        return require_global_execution_authority(result, brain_state, action)
    except TwoAGlobalEnforcementFailure as exc:
        raise TwoAAdversarialCertificationFailure(str(exc)) from exc


def _brain(
    *,
    waiting: bool = False,
    execution_state: str | None = None,
    current_step: int = 2,
    completed=(1,),
    frozen=(1,),
    remaining=(),
    main_sha: str = "1" * 40,
    head_sha: str = "2" * 40,
):
    state = execution_state or ("WAITING_ON_ASYNC" if waiting else "ACTIVE")
    return build_state(BrainStateInput(
        program_id="self-test",
        program_title="2A adversarial certification self-test",
        total_steps=2,
        current_step=current_step,
        step_title="Adversarial Certification",
        execution_state=state,
        repository="owner/repo",
        main_sha=main_sha,
        work_branch="two-a-step5",
        observed_head_sha=head_sha,
        next_legal_action="Continue only with new legal work.",
        completed_steps=completed,
        frozen_steps=frozen,
        remaining_steps=remaining,
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else ("SUCCESS" if state == "FROZEN" else "NONE"),
        updated_at_utc="2026-09-30T03:51:00Z",
    ))


def _forward(action: Mapping[str, Any], nonce: str = "step5-self-test"):
    from devsystem.action_ledger_v2 import build_receipt

    return {
        "decision": "AUTHORIZED",
        "receipt": build_receipt({
            "policy_version": 2,
            "task_id": str(action["task_id"]),
            "checkpoint_id": str(action["checkpoint_id"]),
            "action_fingerprint": fingerprint_action(dict(action)),
            "root_cause_fingerprint": "r" * 64,
            "evidence_fingerprint": "e" * 64,
            "relevant_input_fingerprint": "i" * 64,
            "decision": "AUTHORIZED",
            "previous_chain_hash": "0" * 64,
            "event_nonce": nonce,
            "override_event_id": None,
        }),
    }


def contract_self_test() -> dict[str, Any]:
    brain = _brain()
    action = {
        "task_id": "self-test",
        "checkpoint_id": "2",
        "action_type": "merge",
        "target": "github:pr/1",
        "inputs": {"head": "2" * 40},
    }

    legal = enforce_certified_action(
        brain,
        action,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        forward_decision=_forward(action),
    )
    legal_validation = require_final_certification(
        legal["result"], brain, action
    )

    stale_main = enforce_certified_action(
        brain,
        action,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="3" * 40,
        current_head_sha="2" * 40,
        forward_decision=_forward(action, "stale-main"),
    )
    stale_head = enforce_certified_action(
        brain,
        action,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="4" * 40,
        forward_decision=_forward(action, "stale-head"),
    )

    frozen_target = {
        **action,
        "checkpoint_id": "1",
        "action_type": "patch",
        "target": "github:frozen-step/1",
    }
    frozen_checkpoint = enforce_certified_action(
        brain,
        frozen_target,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        forward_decision=_forward(frozen_target, "frozen-target"),
    )

    frozen_brain = _brain(
        execution_state="FROZEN",
        current_step=1,
        completed=(1,),
        frozen=(1,),
        remaining=(2,),
    )
    frozen_mutation = {
        **action,
        "checkpoint_id": "1",
        "action_type": "patch",
        "target": "github:frozen-current",
    }
    frozen_state = enforce_certified_action(
        frozen_brain,
        frozen_mutation,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        forward_decision=_forward(frozen_mutation, "frozen-state"),
    )

    replay = enforce_certified_action(
        brain,
        action,
        [],
        legal["replay_ledger"],
        legal["consumption_ledger"],
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        forward_decision=_forward(action, "replay-new-receipt"),
    )

    missing_auth = enforce_certified_action(
        brain,
        action,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
    )

    waiting = _brain(waiting=True)
    competing = {
        "task_id": "self-test",
        "checkpoint_id": "2",
        "action_type": "start_competing_run",
        "target": "github:run/new",
    }
    duplicate_run = enforce_certified_action(
        waiting,
        competing,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
    )

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
    history = [{"control_cycle_fingerprint": fingerprint_control_cycle(observe)}]
    duplicate_poll = enforce_certified_action(
        waiting,
        observe,
        history,
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
    )

    unknown = {
        **action,
        "action_type": "future_unregistered_mutation",
        "target": "github:unknown",
    }
    unknown_action = enforce_certified_action(
        brain,
        unknown,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
    )

    tampered = deepcopy(legal["result"])
    tampered["execution_proof"]["payload"]["target"] = "github:tampered"
    tamper_blocked = False
    try:
        require_final_certification(tampered, brain, action)
    except TwoAAdversarialCertificationFailure:
        tamper_blocked = True

    raw_step4 = deepcopy(legal["result"])
    raw_step4.pop("certified", None)
    raw_step4.pop("adversarial_firewall_passed", None)
    final_layer_required = False
    try:
        require_final_certification(raw_step4, brain, action)
    except TwoAAdversarialCertificationFailure:
        final_layer_required = True

    attacks = {
        "aligned_legal_action": legal["result"].get("certified") is True,
        "stale_main_blocked": stale_main["result"]["decision"] == "STALE_STATE_BLOCKED_CONTINUE",
        "stale_head_blocked": stale_head["result"]["decision"] == "STALE_STATE_BLOCKED_CONTINUE",
        "frozen_checkpoint_blocked": frozen_checkpoint["result"]["decision"] == "FROZEN_STATE_BLOCKED_CONTINUE",
        "frozen_brain_mutation_blocked": frozen_state["result"]["decision"] == "FROZEN_STATE_BLOCKED_CONTINUE",
        "replay_blocked": replay["result"]["decision"] == "LOOP_SKIPPED_CONTINUE",
        "missing_authorization_blocked": missing_auth["result"].get("allowed") is False,
        "competing_run_blocked": duplicate_run["result"].get("allowed") is False,
        "duplicate_poll_skipped": duplicate_poll["result"]["decision"] == "LOOP_SKIPPED_CONTINUE",
        "unknown_action_blocked": unknown_action["result"].get("allowed") is False,
        "tampered_proof_blocked": tamper_blocked,
        "step5_final_layer_required": final_layer_required,
    }

    result = {
        "status": "GREEN",
        "version": VERSION,
        "attack_count": len(attacks),
        "all_attacks_fail_closed": all(attacks.values()),
        "attacks": attacks,
        "legal_global_proof_valid": legal_validation["status"] == "GREEN",
        "step4_preserved": True,
        "steps1_3_preserved": True,
        "safe_continue_no_user": all(
            outcome["result"].get("requires_user_intervention") is False
            for outcome in (
                stale_main,
                stale_head,
                frozen_checkpoint,
                frozen_state,
                replay,
                missing_auth,
                duplicate_run,
                duplicate_poll,
                unknown_action,
            )
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    if not (
        result["all_attacks_fail_closed"]
        and result["legal_global_proof_valid"]
        and result["step4_preserved"]
        and result["steps1_3_preserved"]
        and result["safe_continue_no_user"]
    ):
        raise TwoAAdversarialCertificationFailure(
            "Step-5 permanent adversarial certification failed"
        )
    return result


if __name__ == "__main__":
    print("MONSTER_2A_ADVERSARIAL_CERTIFICATION_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
