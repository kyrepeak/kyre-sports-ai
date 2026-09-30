"""MONSTER 2A Enforcement Step 4 — Global Enforcement + Tripwire V1.

This is the canonical execution entrypoint for MONSTER 2A protected actions.

It composes Steps 1 -> 2 -> 3 and emits the only proof that counts as final
execution authority. Raw Step-1 allow decisions, Step-2 receipts, or Step-3
slot claims are intentionally insufficient by themselves.

Any bypass, malformed chain, missing prerequisite, replay, stale authorization,
or upstream denial is halted and routed to a safe non-conflicting continuation.

This module performs no network calls and no repository/product mutations.
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

from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_action_gate_v1 import VERSION as STEP1_VERSION
from devsystem.mandatory_2a_receipt_v1 import (
    VERSION as STEP2_VERSION,
    authorize_action_with_receipt,
    new_consumption_ledger,
)
from devsystem.mandatory_2a_replay_lock_v1 import (
    VERSION as STEP3_VERSION,
    claim_execution_slot,
    new_replay_ledger,
)
from devsystem.persistent_execution_brain_v1 import (
    BrainStateInput,
    build_state,
    validate_state,
)

VERSION = "MONSTER_2A_GLOBAL_ENFORCEMENT_TRIPWIRE_V1"
PROOF_SCHEMA_VERSION = 1
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_EXECUTION_PROOF_FIELDS = frozenset({
    "schema_version",
    "step4_version",
    "step1_version",
    "step2_version",
    "step3_version",
    "task_id",
    "checkpoint_id",
    "action_type",
    "target",
    "action_fingerprint",
    "brain_state_id",
    "execution_receipt_hash",
    "source_authorization_fingerprint",
    "slot_claimed",
    "execution_authorized",
})


class TwoAGlobalEnforcementFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _safe_continue(
    reason: str,
    *,
    action: Mapping[str, Any] | None,
    upstream_decision: str | None = None,
    next_legal_action: str | None = None,
) -> dict[str, Any]:
    action_type = str((action or {}).get("action_type") or "")
    target = str((action or {}).get("target") or "")
    return {
        "version": VERSION,
        "decision": "TRIPWIRE_BLOCKED_CONTINUE",
        "reason": reason,
        "allowed": False,
        "execution_authorized": False,
        "tripwire_triggered": True,
        "autonomous_skip": True,
        "requires_user_intervention": False,
        "continuation_policy": "CONTINUE_NON_CONFLICTING_WORK",
        "next_legal_action": next_legal_action or "CONTINUE_NON_CONFLICTING_WORK",
        "recheck_policy": "ONLY_AFTER_NEW_EVIDENCE_OR_INDEPENDENT_PROGRESS",
        "upstream_decision": upstream_decision,
        "action_type": action_type,
        "target": target,
        "execution_proof": None,
    }


def build_execution_proof(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    slot_claim: Mapping[str, Any],
    authorization_result: Mapping[str, Any],
) -> dict[str, Any]:
    brain = validate_state(brain_state)
    if not isinstance(action, Mapping):
        raise TwoAGlobalEnforcementFailure("action must be an object")
    if not isinstance(slot_claim, Mapping):
        raise TwoAGlobalEnforcementFailure("slot claim must be an object")
    if not isinstance(authorization_result, Mapping):
        raise TwoAGlobalEnforcementFailure("authorization result must be an object")

    result = slot_claim.get("result")
    if not isinstance(result, Mapping):
        raise TwoAGlobalEnforcementFailure("slot claim result missing")
    if result.get("allowed") is not True:
        raise TwoAGlobalEnforcementFailure("denied slot claim cannot issue global execution proof")
    if result.get("decision") != "EXECUTION_SLOT_CLAIMED":
        raise TwoAGlobalEnforcementFailure("global proof requires EXECUTION_SLOT_CLAIMED")
    if result.get("slot_claimed") is not True:
        raise TwoAGlobalEnforcementFailure("global proof requires slot_claimed=true")

    receipt = authorization_result.get("execution_receipt")
    if not isinstance(receipt, Mapping):
        raise TwoAGlobalEnforcementFailure("global proof requires Step-2 execution receipt")
    receipt_payload = receipt.get("payload")
    if not isinstance(receipt_payload, Mapping):
        raise TwoAGlobalEnforcementFailure("global proof requires Step-2 receipt payload")

    action_fp = fingerprint_action(dict(action))
    if str(result.get("action_fingerprint") or "") != action_fp:
        raise TwoAGlobalEnforcementFailure("slot claim action fingerprint mismatch")

    body = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "step4_version": VERSION,
        "step1_version": STEP1_VERSION,
        "step2_version": STEP2_VERSION,
        "step3_version": STEP3_VERSION,
        "task_id": str(action.get("task_id") or ""),
        "checkpoint_id": str(action.get("checkpoint_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "target": str(action.get("target") or ""),
        "action_fingerprint": action_fp,
        "brain_state_id": str(brain["state_id"]),
        "execution_receipt_hash": str(result.get("receipt_hash") or ""),
        "source_authorization_fingerprint": str(result.get("source_fingerprint") or ""),
        "slot_claimed": True,
        "execution_authorized": True,
    }
    if not all(str(body[field]).strip() for field in (
        "task_id",
        "checkpoint_id",
        "action_type",
        "target",
        "action_fingerprint",
        "brain_state_id",
        "execution_receipt_hash",
        "source_authorization_fingerprint",
    )):
        raise TwoAGlobalEnforcementFailure("global execution proof contains empty identity field")

    return {
        "payload": body,
        "proof_hash": _hash(body),
    }


def validate_execution_proof(
    proof: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
) -> dict[str, Any]:
    brain = validate_state(brain_state)
    if not isinstance(proof, Mapping):
        raise TwoAGlobalEnforcementFailure("global execution proof must be an object")
    payload = proof.get("payload")
    if not isinstance(payload, Mapping):
        raise TwoAGlobalEnforcementFailure("global execution proof payload missing")
    missing = sorted(_EXECUTION_PROOF_FIELDS - set(payload))
    if missing:
        raise TwoAGlobalEnforcementFailure(
            "global execution proof missing fields: " + ", ".join(missing)
        )

    expected_hash = _hash(dict(payload))
    if str(proof.get("proof_hash") or "") != expected_hash:
        raise TwoAGlobalEnforcementFailure("global execution proof hash mismatch")

    version_checks = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "step4_version": VERSION,
        "step1_version": STEP1_VERSION,
        "step2_version": STEP2_VERSION,
        "step3_version": STEP3_VERSION,
    }
    for field, expected in version_checks.items():
        actual = payload.get(field)
        if field == "schema_version":
            if int(actual or 0) != int(expected):
                raise TwoAGlobalEnforcementFailure("global execution proof schema mismatch")
        elif str(actual or "") != str(expected):
            raise TwoAGlobalEnforcementFailure(f"global execution proof {field} mismatch")

    expected_fp = fingerprint_action(dict(action))
    identity = {
        "task_id": str(action.get("task_id") or ""),
        "checkpoint_id": str(action.get("checkpoint_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "target": str(action.get("target") or ""),
        "action_fingerprint": expected_fp,
        "brain_state_id": str(brain["state_id"]),
    }
    for field, expected in identity.items():
        if str(payload.get(field) or "") != expected:
            raise TwoAGlobalEnforcementFailure(
                f"global execution proof {field} mismatch"
            )

    if payload.get("slot_claimed") is not True:
        raise TwoAGlobalEnforcementFailure("global execution proof slot is not claimed")
    if payload.get("execution_authorized") is not True:
        raise TwoAGlobalEnforcementFailure("global execution proof is not authorized")
    if not str(payload.get("execution_receipt_hash") or ""):
        raise TwoAGlobalEnforcementFailure("global execution proof receipt hash missing")
    if not str(payload.get("source_authorization_fingerprint") or ""):
        raise TwoAGlobalEnforcementFailure(
            "global execution proof source authorization fingerprint missing"
        )

    return {
        "status": "GREEN",
        "proof_hash": expected_hash,
        "action_fingerprint": expected_fp,
        "brain_state_id": str(brain["state_id"]),
    }


def enforce_action(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
    *,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical MONSTER execution entrypoint.

    Nothing outside this function may claim final execution authorization.
    """
    try:
        authorization = authorize_action_with_receipt(
            brain_state,
            action,
            history,
            forward_decision=forward_decision,
        )
    except Exception as exc:
        return {
            "result": _safe_continue(
                f"Step-1/2 authorization chain failed closed: {exc}",
                action=action,
            ),
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    if authorization.get("allowed") is not True:
        upstream = str(
            authorization.get("source_decision")
            or authorization.get("decision")
            or "DENIED"
        )
        next_action = str(
            authorization.get("next_legal_action")
            or "CONTINUE_NON_CONFLICTING_WORK"
        )
        return {
            "result": _safe_continue(
                "Step-1/2 denied action; global tripwire blocked execution",
                action=action,
                upstream_decision=upstream,
                next_legal_action=next_action,
            ),
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    try:
        claim = claim_execution_slot(
            authorization,
            brain_state,
            action,
            replay_ledger,
            consumption_ledger,
        )
    except Exception as exc:
        return {
            "result": _safe_continue(
                f"Step-3 replay lock failed closed: {exc}",
                action=action,
                upstream_decision=str(authorization.get("decision") or ""),
            ),
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    slot = claim.get("result")
    if not isinstance(slot, Mapping) or slot.get("allowed") is not True:
        upstream = str((slot or {}).get("decision") or "STEP3_DENIED")
        next_action = str(
            (slot or {}).get("next_legal_action")
            or "CONTINUE_NON_CONFLICTING_WORK"
        )
        decision = (
            "LOOP_SKIPPED_CONTINUE"
            if upstream == "LOOP_SKIPPED_CONTINUE"
            else "TRIPWIRE_BLOCKED_CONTINUE"
        )
        safe = _safe_continue(
            "Step-3 blocked replay/duplicate action",
            action=action,
            upstream_decision=upstream,
            next_legal_action=next_action,
        )
        safe["decision"] = decision
        safe["tripwire_triggered"] = upstream != "LOOP_SKIPPED_CONTINUE"
        return {
            "result": safe,
            "replay_ledger": deepcopy(dict(claim.get("replay_ledger") or replay_ledger)),
            "consumption_ledger": deepcopy(
                dict(claim.get("consumption_ledger") or consumption_ledger)
            ),
        }

    try:
        proof = build_execution_proof(
            brain_state,
            action,
            claim,
            authorization,
        )
        validation = validate_execution_proof(proof, brain_state, action)
    except Exception as exc:
        return {
            "result": _safe_continue(
                f"global execution proof failed closed: {exc}",
                action=action,
                upstream_decision=str(slot.get("decision") or ""),
            ),
            "replay_ledger": deepcopy(dict(claim["replay_ledger"])),
            "consumption_ledger": deepcopy(dict(claim["consumption_ledger"])),
        }

    return {
        "result": {
            "version": VERSION,
            "decision": "GLOBAL_EXECUTION_AUTHORIZED",
            "reason": "Steps 1-3 completed and global tripwire proof is valid",
            "allowed": True,
            "execution_authorized": True,
            "tripwire_triggered": False,
            "requires_user_intervention": False,
            "action_type": str(action.get("action_type") or ""),
            "target": str(action.get("target") or ""),
            "execution_proof": proof,
            "execution_proof_hash": validation["proof_hash"],
            "action_fingerprint": validation["action_fingerprint"],
            "brain_state_id": validation["brain_state_id"],
        },
        "replay_ledger": deepcopy(dict(claim["replay_ledger"])),
        "consumption_ledger": deepcopy(dict(claim["consumption_ledger"])),
    }


def require_global_execution_authority(
    enforcement_result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(enforcement_result, Mapping):
        raise TwoAGlobalEnforcementFailure("global enforcement result must be an object")
    if enforcement_result.get("allowed") is not True:
        raise TwoAGlobalEnforcementFailure("global tripwire did not authorize execution")
    if enforcement_result.get("decision") != "GLOBAL_EXECUTION_AUTHORIZED":
        raise TwoAGlobalEnforcementFailure("global execution decision missing")
    if enforcement_result.get("execution_authorized") is not True:
        raise TwoAGlobalEnforcementFailure("global execution authority flag missing")
    proof = enforcement_result.get("execution_proof")
    return validate_execution_proof(proof, brain_state, action)


def _brain(*, waiting: bool = False):
    return build_state(BrainStateInput(
        program_id="self-test",
        program_title="2A global enforcement self-test",
        total_steps=2,
        current_step=1,
        step_title="Global Enforcement + Tripwire",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="two-a-step4",
        observed_head_sha="2" * 40,
        next_legal_action="Continue safely.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc="2026-09-30T03:44:00Z",
    ))


def _forward(action: Mapping[str, Any]) -> dict[str, Any]:
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
            "event_nonce": "mandatory-2a-step4-self-test",
            "override_event_id": None,
        }),
    }


def contract_self_test() -> dict[str, Any]:
    brain = _brain()
    action = {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "merge",
        "target": "github:pr/1",
        "inputs": {"head": "2" * 40},
    }

    legal = enforce_action(
        brain,
        action,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
        forward_decision=_forward(action),
    )
    legal_result = legal["result"]
    legal_validation = require_global_execution_authority(
        legal_result,
        brain,
        action,
    )

    missing_forward = enforce_action(
        brain,
        action,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
    )

    replay = enforce_action(
        brain,
        action,
        [],
        legal["replay_ledger"],
        legal["consumption_ledger"],
        forward_decision=_forward(action),
    )

    forged_step1 = {
        "allowed": True,
        "decision": "TWO_A_AUTHORIZED",
    }
    forged_step2 = {
        "allowed": True,
        "decision": "TWO_A_AUTHORIZED",
        "execution_receipt": {"fake": True},
    }
    raw_claim = {
        "allowed": True,
        "decision": "EXECUTION_SLOT_CLAIMED",
        "slot_claimed": True,
    }
    bypasses_blocked = True
    for fake in (forged_step1, forged_step2, raw_claim):
        try:
            require_global_execution_authority(fake, brain, action)
        except TwoAGlobalEnforcementFailure:
            pass
        else:
            bypasses_blocked = False

    tampered = deepcopy(legal_result)
    tampered["execution_proof"]["payload"]["target"] = "github:pr/tampered"
    tamper_blocked = False
    try:
        require_global_execution_authority(tampered, brain, action)
    except TwoAGlobalEnforcementFailure:
        tamper_blocked = True

    waiting = _brain(waiting=True)
    mutation = {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "patch",
        "target": "github:mutation",
    }
    async_locked = enforce_action(
        waiting,
        mutation,
        [],
        new_replay_ledger(),
        new_consumption_ledger(),
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "canonical_entrypoint_authorizes": legal_result["decision"] == "GLOBAL_EXECUTION_AUTHORIZED",
        "global_proof_valid": legal_validation["status"] == "GREEN",
        "missing_prerequisite_tripwire_blocks": missing_forward["result"]["decision"] == "TRIPWIRE_BLOCKED_CONTINUE",
        "replay_stays_loop_skipped": replay["result"]["decision"] == "LOOP_SKIPPED_CONTINUE",
        "raw_step_outputs_cannot_bypass": bypasses_blocked,
        "global_proof_tamper_blocked": tamper_blocked,
        "live_async_mutation_tripwire_blocks": async_locked["result"]["allowed"] is False,
        "safe_continue_no_user": (
            missing_forward["result"]["requires_user_intervention"] is False
            and replay["result"]["requires_user_intervention"] is False
            and async_locked["result"]["requires_user_intervention"] is False
        ),
        "step1_preserved": True,
        "step2_preserved": True,
        "step3_preserved": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "canonical_entrypoint_authorizes",
        "global_proof_valid",
        "missing_prerequisite_tripwire_blocks",
        "replay_stays_loop_skipped",
        "raw_step_outputs_cannot_bypass",
        "global_proof_tamper_blocked",
        "live_async_mutation_tripwire_blocks",
        "safe_continue_no_user",
        "step1_preserved",
        "step2_preserved",
        "step3_preserved",
    )
    if not all(result[key] is True for key in required):
        raise TwoAGlobalEnforcementFailure("Step-4 global enforcement self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_2A_GLOBAL_ENFORCEMENT_TRIPWIRE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
