"""MONSTER V7 Step 6 — Final-Mile Autopilot V1.

Deterministic controller for the final execution path:

    WAIT/ACQUIRE -> PROVE -> MERGE -> MERGED-MAIN CERTIFY
    -> DEPLOY/CERTIFY (when required) -> FREEZE -> DONE

The controller never performs network calls itself. It emits exactly one guarded
external action when work is required, then waits for a new event/evidence
packet. Each external action has a single-use budget within an autopilot run, so
unchanged evidence cannot cause duplicate proof, merge, deploy, or freeze
actions.

Evidence-backed stages auto-advance in one call. Terminal failures stop and
route to root-cause classification instead of retrying.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.atomic_wait_queue_lease_handoff_v1 import (
    VERSION as WAIT_QUEUE_VERSION,
)
from devsystem.deployment_convergence_controller_v1 import (
    VERSION as DEPLOYMENT_CONVERGENCE_VERSION,
    validate_convergence_decision,
)
from devsystem.terminal_proof_receipt_v1 import (
    VERSION as TERMINAL_RECEIPT_VERSION,
    validate_receipt,
)

VERSION = "MONSTER_V7_FINAL_MILE_AUTOPILOT_V1"
REQUIRED_WAIT_QUEUE_VERSION = "MONSTER_V7_ATOMIC_WAIT_QUEUE_LEASE_HANDOFF_V1"
REQUIRED_DEPLOYMENT_VERSION = "MONSTER_V6_DEPLOYMENT_CONVERGENCE_CONTROLLER_V1"
REQUIRED_RECEIPT_VERSION = "MONSTER_V4_TERMINAL_PROOF_RECEIPT_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PHASES = {
    "WAITING_FOR_LEASE",
    "PROVE_EXACT_HEAD",
    "MERGE_EXACT_HEAD",
    "CERTIFY_MERGED_MAIN",
    "DEPLOY_CERTIFY",
    "FREEZE",
    "DONE",
    "BLOCKED",
}
_MUTATING_ACTIONS = {
    "ACQUIRE_OR_QUEUE_SCOPE_LEASE",
    "MERGE_EXACT_PROVEN_HEAD",
    "REFRESH_DEPLOYMENT",
    "FULL_REDEPLOY",
    "REGISTER_FROZEN_CHECKPOINT",
}
_EXTERNAL_ACTIONS = {
    "ACQUIRE_OR_QUEUE_SCOPE_LEASE",
    "RUN_EXACT_HEAD_PROOF",
    "MERGE_EXACT_PROVEN_HEAD",
    "RUN_MERGED_MAIN_CERTIFICATION",
    "START_OR_RESUME_DEPLOYMENT_CONVERGENCE",
    "REFRESH_DEPLOYMENT",
    "FULL_REDEPLOY",
    "VERIFY_RUNTIME",
    "REGISTER_FROZEN_CHECKPOINT",
}


class FinalMileAutopilotFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise FinalMileAutopilotFailure(f"{field} is required")
    return out


def _sha(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _SHA40.fullmatch(out):
        raise FinalMileAutopilotFailure(f"{field} must be a 40-char git SHA")
    return out


def _rehash(state: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(state))
    out.pop("state_hash", None)
    out["state_hash"] = _digest(out)
    return validate_state(out)


def new_state(
    *,
    task_id: str,
    checkpoint_id: str,
    target_head_sha: str,
    deployment_required: bool,
    wait_ticket_id: str = "",
) -> dict[str, Any]:
    state = {
        "schema_version": 1,
        "version": VERSION,
        "task_id": _text(task_id, "task_id"),
        "checkpoint_id": _text(checkpoint_id, "checkpoint_id"),
        "target_head_sha": _sha(target_head_sha, "target_head_sha"),
        "deployment_required": bool(deployment_required),
        "wait_ticket_id": str(wait_ticket_id or "").strip(),
        "phase": "WAITING_FOR_LEASE",
        "revision": 0,
        "merge_sha": "",
        "issued_actions": {},
        "history": [],
        "blocked": None,
    }
    state["state_hash"] = _digest(state)
    return validate_state(state)


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise FinalMileAutopilotFailure("state must be an object")
    state = deepcopy(dict(payload))
    if int(state.get("schema_version", 0)) != 1 or state.get("version") != VERSION:
        raise FinalMileAutopilotFailure("state version/schema mismatch")
    _text(state.get("task_id"), "task_id")
    _text(state.get("checkpoint_id"), "checkpoint_id")
    _sha(state.get("target_head_sha"), "target_head_sha")
    if state.get("phase") not in _PHASES:
        raise FinalMileAutopilotFailure("unknown autopilot phase")
    if int(state.get("revision", -1)) < 0:
        raise FinalMileAutopilotFailure("revision invalid")
    merge_sha = str(state.get("merge_sha") or "")
    if merge_sha:
        _sha(merge_sha, "merge_sha")
    actions = state.get("issued_actions")
    if not isinstance(actions, Mapping):
        raise FinalMileAutopilotFailure("issued_actions must be an object")
    if any(action not in _EXTERNAL_ACTIONS for action in actions):
        raise FinalMileAutopilotFailure("unknown issued action")
    if not isinstance(state.get("history"), list):
        raise FinalMileAutopilotFailure("history must be a list")
    blocked = state.get("blocked")
    if state["phase"] == "BLOCKED" and not isinstance(blocked, Mapping):
        raise FinalMileAutopilotFailure("BLOCKED phase requires blocked receipt")
    supplied = str(state.get("state_hash") or "").lower()
    unsigned = deepcopy(state)
    unsigned.pop("state_hash", None)
    if supplied != _digest(unsigned):
        raise FinalMileAutopilotFailure("autopilot state hash mismatch")
    return state


def _record_transition(
    state: Mapping[str, Any],
    *,
    from_phase: str,
    to_phase: str,
    reason: str,
) -> dict[str, Any]:
    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["phase"] = to_phase
    updated["history"].append(
        {
            "revision": updated["revision"],
            "from_phase": from_phase,
            "to_phase": to_phase,
            "reason": reason,
        }
    )
    return _rehash(updated)


def _block(
    state: Mapping[str, Any],
    *,
    reason: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["phase"] = "BLOCKED"
    updated["blocked"] = {
        "reason": reason,
        "evidence_digest": _digest(evidence or {}),
        "next_legal_action": "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE",
    }
    updated["history"].append(
        {
            "revision": updated["revision"],
            "from_phase": state["phase"],
            "to_phase": "BLOCKED",
            "reason": reason,
        }
    )
    return _rehash(updated)


def _action_result(
    state: Mapping[str, Any],
    *,
    action: str,
    evidence: Mapping[str, Any],
    wait_action: str,
) -> dict[str, Any]:
    if action not in _EXTERNAL_ACTIONS:
        raise FinalMileAutopilotFailure("unsupported external action")
    fingerprint = _digest(
        {
            "phase": state["phase"],
            "action": action,
            "evidence": evidence,
            "target_head_sha": state["target_head_sha"],
            "merge_sha": state["merge_sha"],
        }
    )
    issued = dict(state["issued_actions"])
    if action in issued:
        return {
            "result": {
                "decision": wait_action,
                "phase": state["phase"],
                "next_legal_action": wait_action,
                "polling_required": False,
                "duplicate_action_suppressed": True,
                "previous_action_fingerprint": issued[action],
                "mutation_authority": False,
            },
            "state": state,
        }

    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["issued_actions"][action] = fingerprint
    updated["history"].append(
        {
            "revision": updated["revision"],
            "from_phase": state["phase"],
            "to_phase": state["phase"],
            "reason": f"ISSUED:{action}",
        }
    )
    updated = _rehash(updated)
    return {
        "result": {
            "decision": "AUTOPILOT_ACTION_ISSUED",
            "phase": state["phase"],
            "action": action,
            "action_fingerprint": fingerprint,
            "requires_external_executor": True,
            "step_2a_required": True,
            "scope_lease_required": True,
            "mutating_action": action in _MUTATING_ACTIONS,
            "polling_required": False,
            "mutation_authority": False,
        },
        "state": updated,
    }


def _terminal_failure(
    evidence: Mapping[str, Any],
    key: str,
) -> Mapping[str, Any] | None:
    failures = evidence.get("failures") or {}
    if not isinstance(failures, Mapping):
        raise FinalMileAutopilotFailure("failures evidence must be an object")
    value = failures.get(key)
    if not value:
        return None
    if not isinstance(value, Mapping) or value.get("terminal") is not True:
        raise FinalMileAutopilotFailure(
            f"{key} failure must be terminal evidence"
        )
    return value


def _validated_receipt(
    evidence: Mapping[str, Any],
    key: str,
) -> Mapping[str, Any] | None:
    raw = evidence.get(key)
    if raw is None:
        return None
    validate_receipt(raw)
    return raw


def _lease_status(evidence: Mapping[str, Any]) -> Mapping[str, Any] | None:
    raw = evidence.get("lease")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise FinalMileAutopilotFailure("lease evidence must be an object")
    return raw


def advance(
    payload: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Auto-advance satisfied stages until an action, wait, blocker, or DONE."""
    state = validate_state(payload)
    if not isinstance(evidence, Mapping):
        raise FinalMileAutopilotFailure("evidence must be an object")

    if WAIT_QUEUE_VERSION != REQUIRED_WAIT_QUEUE_VERSION:
        raise FinalMileAutopilotFailure("Step-5 wait queue version mismatch")
    if DEPLOYMENT_CONVERGENCE_VERSION != REQUIRED_DEPLOYMENT_VERSION:
        raise FinalMileAutopilotFailure("deployment convergence version mismatch")
    if TERMINAL_RECEIPT_VERSION != REQUIRED_RECEIPT_VERSION:
        raise FinalMileAutopilotFailure("terminal receipt version mismatch")

    for _ in range(12):
        phase = state["phase"]

        if phase == "DONE":
            return {
                "result": {
                    "decision": "FINAL_MILE_DONE",
                    "phase": "DONE",
                    "complete": True,
                    "next_legal_action": "NONE",
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }

        if phase == "BLOCKED":
            return {
                "result": {
                    "decision": "FINAL_MILE_BLOCKED",
                    "phase": "BLOCKED",
                    "complete": False,
                    "blocker": state["blocked"],
                    "next_legal_action": state["blocked"]["next_legal_action"],
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }

        if phase == "WAITING_FOR_LEASE":
            failure = _terminal_failure(evidence, "lease")
            if failure:
                state = _block(
                    state,
                    reason="TERMINAL_LEASE_ACQUISITION_FAILURE",
                    evidence=failure,
                )
                continue
            lease = _lease_status(evidence)
            if lease and str(lease.get("state") or "").upper() == "HELD":
                if _sha(lease.get("head_sha"), "lease head_sha") != state["target_head_sha"]:
                    state = _block(
                        state,
                        reason="LEASE_BOUND_TO_WRONG_HEAD",
                        evidence=lease,
                    )
                    continue
                expected_ticket = state["wait_ticket_id"]
                observed_ticket = str(lease.get("wait_ticket_id") or "").strip()
                if expected_ticket and observed_ticket != expected_ticket:
                    state = _block(
                        state,
                        reason="LEASE_HANDOFF_TICKET_MISMATCH",
                        evidence=lease,
                    )
                    continue
                state = _record_transition(
                    state,
                    from_phase=phase,
                    to_phase="PROVE_EXACT_HEAD",
                    reason="EXACT_HEAD_LEASE_HELD",
                )
                continue
            if state["wait_ticket_id"]:
                return {
                    "result": {
                        "decision": "WAIT_FOR_LEASE_HANDOFF_EVENT",
                        "phase": phase,
                        "next_legal_action": "WAIT_FOR_LEASE_HANDOFF_EVENT",
                        "polling_required": False,
                        "duplicate_action_suppressed": False,
                        "mutation_authority": False,
                    },
                    "state": state,
                }
            return _action_result(
                state,
                action="ACQUIRE_OR_QUEUE_SCOPE_LEASE",
                evidence=evidence,
                wait_action="WAIT_FOR_LEASE_STATE_EVENT",
            )

        if phase == "PROVE_EXACT_HEAD":
            failure = _terminal_failure(evidence, "exact_head_proof")
            if failure:
                state = _block(
                    state,
                    reason="TERMINAL_EXACT_HEAD_PROOF_FAILURE",
                    evidence=failure,
                )
                continue
            receipt = _validated_receipt(evidence, "exact_head_receipt")
            if receipt is not None:
                if str(receipt["head_sha"]).lower() != state["target_head_sha"]:
                    state = _block(
                        state,
                        reason="EXACT_HEAD_RECEIPT_SHA_MISMATCH",
                        evidence=receipt,
                    )
                    continue
                state = _record_transition(
                    state,
                    from_phase=phase,
                    to_phase="MERGE_EXACT_HEAD",
                    reason="EXACT_HEAD_PROOF_GREEN",
                )
                continue
            return _action_result(
                state,
                action="RUN_EXACT_HEAD_PROOF",
                evidence=evidence,
                wait_action="WAIT_FOR_EXACT_HEAD_PROOF_EVENT",
            )

        if phase == "MERGE_EXACT_HEAD":
            failure = _terminal_failure(evidence, "merge")
            if failure:
                state = _block(
                    state,
                    reason="TERMINAL_MERGE_FAILURE",
                    evidence=failure,
                )
                continue
            merge = evidence.get("merge")
            if merge is not None:
                if not isinstance(merge, Mapping):
                    raise FinalMileAutopilotFailure("merge evidence must be an object")
                if merge.get("merged") is True:
                    if _sha(merge.get("head_sha"), "merged head_sha") != state["target_head_sha"]:
                        state = _block(
                            state,
                            reason="MERGED_HEAD_SHA_MISMATCH",
                            evidence=merge,
                        )
                        continue
                    merge_sha = _sha(merge.get("merge_sha"), "merge_sha")
                    updated = deepcopy(state)
                    updated["merge_sha"] = merge_sha
                    updated = _rehash(updated)
                    state = _record_transition(
                        updated,
                        from_phase=phase,
                        to_phase="CERTIFY_MERGED_MAIN",
                        reason="EXACT_PROVEN_HEAD_MERGED",
                    )
                    continue
            return _action_result(
                state,
                action="MERGE_EXACT_PROVEN_HEAD",
                evidence=evidence,
                wait_action="WAIT_FOR_MERGE_EVENT",
            )

        if phase == "CERTIFY_MERGED_MAIN":
            failure = _terminal_failure(evidence, "merged_main_proof")
            if failure:
                state = _block(
                    state,
                    reason="TERMINAL_MERGED_MAIN_PROOF_FAILURE",
                    evidence=failure,
                )
                continue
            receipt = _validated_receipt(evidence, "merged_main_receipt")
            if receipt is not None:
                if str(receipt["head_sha"]).lower() != state["merge_sha"]:
                    state = _block(
                        state,
                        reason="MERGED_MAIN_RECEIPT_SHA_MISMATCH",
                        evidence=receipt,
                    )
                    continue
                next_phase = (
                    "DEPLOY_CERTIFY"
                    if state["deployment_required"]
                    else "FREEZE"
                )
                state = _record_transition(
                    state,
                    from_phase=phase,
                    to_phase=next_phase,
                    reason="MERGED_MAIN_CERTIFICATION_GREEN",
                )
                continue
            return _action_result(
                state,
                action="RUN_MERGED_MAIN_CERTIFICATION",
                evidence=evidence,
                wait_action="WAIT_FOR_MERGED_MAIN_CERT_EVENT",
            )

        if phase == "DEPLOY_CERTIFY":
            failure = _terminal_failure(evidence, "deployment")
            if failure:
                state = _block(
                    state,
                    reason="TERMINAL_DEPLOYMENT_FAILURE",
                    evidence=failure,
                )
                continue
            deployment = evidence.get("deployment")
            if deployment is None:
                return _action_result(
                    state,
                    action="START_OR_RESUME_DEPLOYMENT_CONVERGENCE",
                    evidence=evidence,
                    wait_action="WAIT_FOR_DEPLOYMENT_EVENT",
                )
            if not isinstance(deployment, Mapping):
                raise FinalMileAutopilotFailure("deployment evidence must be an object")
            validated = validate_convergence_decision(deployment)
            if str(validated["expected_sha"]).lower() != state["merge_sha"]:
                state = _block(
                    state,
                    reason="DEPLOYMENT_EXPECTED_SHA_MISMATCH",
                    evidence=validated,
                )
                continue
            if validated["converged"] is True:
                if (
                    str(validated["observed_sha"]).lower() != state["merge_sha"]
                    or validated["next_legal_action"] != "FREEZE_DEPLOYMENT_CONVERGENCE"
                ):
                    state = _block(
                        state,
                        reason="DEPLOYMENT_CONVERGENCE_IDENTITY_MISMATCH",
                        evidence=validated,
                    )
                    continue
                state = _record_transition(
                    state,
                    from_phase=phase,
                    to_phase="FREEZE",
                    reason="DEPLOYMENT_CONVERGED",
                )
                continue

            next_action = str(validated["next_legal_action"])
            if next_action == "WAIT_FOR_DEPLOYMENT_EVENT":
                return {
                    "result": {
                        "decision": "WAIT_FOR_DEPLOYMENT_EVENT",
                        "phase": phase,
                        "next_legal_action": "WAIT_FOR_DEPLOYMENT_EVENT",
                        "polling_required": False,
                        "mutation_authority": False,
                    },
                    "state": state,
                }
            if next_action in {
                "REFRESH_DEPLOYMENT",
                "FULL_REDEPLOY",
                "VERIFY_RUNTIME",
            }:
                return _action_result(
                    state,
                    action=next_action,
                    evidence=evidence,
                    wait_action="WAIT_FOR_DEPLOYMENT_EVENT",
                )
            state = _block(
                state,
                reason="DEPLOYMENT_CONVERGENCE_REQUIRES_CLASSIFICATION",
                evidence=validated,
            )
            continue

        if phase == "FREEZE":
            failure = _terminal_failure(evidence, "freeze")
            if failure:
                state = _block(
                    state,
                    reason="TERMINAL_FREEZE_FAILURE",
                    evidence=failure,
                )
                continue
            frozen = evidence.get("freeze")
            if frozen is not None:
                if not isinstance(frozen, Mapping):
                    raise FinalMileAutopilotFailure("freeze evidence must be an object")
                if str(frozen.get("status") or "").upper() == "FROZEN":
                    if _text(frozen.get("checkpoint_id"), "freeze checkpoint_id") != state["checkpoint_id"]:
                        state = _block(
                            state,
                            reason="FROZEN_CHECKPOINT_ID_MISMATCH",
                            evidence=frozen,
                        )
                        continue
                    if _sha(frozen.get("source_main_sha"), "freeze source_main_sha") != state["merge_sha"]:
                        state = _block(
                            state,
                            reason="FROZEN_SOURCE_SHA_MISMATCH",
                            evidence=frozen,
                        )
                        continue
                    state = _record_transition(
                        state,
                        from_phase=phase,
                        to_phase="DONE",
                        reason="AUTHORITATIVE_FREEZE_REGISTERED",
                    )
                    continue
            return _action_result(
                state,
                action="REGISTER_FROZEN_CHECKPOINT",
                evidence=evidence,
                wait_action="WAIT_FOR_FREEZE_REGISTRY_EVENT",
            )

        raise FinalMileAutopilotFailure("unreachable autopilot phase")

    raise FinalMileAutopilotFailure("autopilot transition budget exhausted")


def contract_self_test() -> dict[str, Any]:
    from devsystem.deployment_convergence_controller_v1 import (
        build_convergence_decision,
    )
    from devsystem.terminal_proof_receipt_v1 import build_receipt

    head = "a" * 40
    merge_sha = "b" * 40
    lanes = {"focused": "success", "devsystem": "success"}
    scope = ["devsystem/example.py"]
    tokens = ["GREEN", "FROZEN"]

    def receipt(sha: str, run: int) -> dict[str, Any]:
        return build_receipt(
            repository="owner/repo",
            checkpoint_id="CP",
            head_sha=sha,
            authoritative_run=run,
            authoritative_workflow="proof",
            test_count=10,
            required_lanes=lanes,
            scope_diff=scope,
            freeze_tokens=tokens,
        )

    static = new_state(
        task_id="static",
        checkpoint_id="CP",
        target_head_sha=head,
        deployment_required=False,
    )
    acquire = advance(static, {})
    acquire_repeat = advance(acquire["state"], {})
    leased = advance(
        acquire["state"],
        {"lease": {"state": "HELD", "head_sha": head}},
    )
    proven = advance(
        leased["state"],
        {
            "lease": {"state": "HELD", "head_sha": head},
            "exact_head_receipt": receipt(head, 1),
        },
    )
    merged = advance(
        proven["state"],
        {
            "lease": {"state": "HELD", "head_sha": head},
            "exact_head_receipt": receipt(head, 1),
            "merge": {
                "merged": True,
                "head_sha": head,
                "merge_sha": merge_sha,
            },
        },
    )
    certified = advance(
        merged["state"],
        {
            "exact_head_receipt": receipt(head, 1),
            "merge": {
                "merged": True,
                "head_sha": head,
                "merge_sha": merge_sha,
            },
            "merged_main_receipt": receipt(merge_sha, 2),
        },
    )
    done = advance(
        certified["state"],
        {
            "merged_main_receipt": receipt(merge_sha, 2),
            "freeze": {
                "status": "FROZEN",
                "checkpoint_id": "CP",
                "source_main_sha": merge_sha,
            },
        },
    )

    queued = new_state(
        task_id="queued",
        checkpoint_id="CP",
        target_head_sha=head,
        deployment_required=False,
        wait_ticket_id="WAIT-123",
    )
    queued_wait = advance(queued, {})
    ticket_mismatch = advance(
        queued,
        {
            "lease": {
                "state": "HELD",
                "head_sha": head,
                "wait_ticket_id": "WAIT-WRONG",
            }
        },
    )

    failed_proof_state = new_state(
        task_id="proof-fail",
        checkpoint_id="CP",
        target_head_sha=head,
        deployment_required=False,
    )
    failed_proof_state = advance(
        failed_proof_state,
        {"lease": {"state": "HELD", "head_sha": head}},
    )["state"]
    failed_proof = advance(
        failed_proof_state,
        {
            "failures": {
                "exact_head_proof": {
                    "terminal": True,
                    "run_id": 99,
                    "class": "DETERMINISTIC",
                }
            }
        },
    )

    deployed_state = new_state(
        task_id="deploy",
        checkpoint_id="CP",
        target_head_sha=head,
        deployment_required=True,
    )
    step = advance(
        deployed_state,
        {"lease": {"state": "HELD", "head_sha": head}},
    )
    step = advance(
        step["state"],
        {
            "exact_head_receipt": receipt(head, 3),
        },
    )
    step = advance(
        step["state"],
        {
            "merge": {
                "merged": True,
                "head_sha": head,
                "merge_sha": merge_sha,
            },
        },
    )
    step = advance(
        step["state"],
        {"merged_main_receipt": receipt(merge_sha, 4)},
    )
    deployment_request = step
    converged = build_convergence_decision(
        expected_sha=merge_sha,
        observed_sha=merge_sha,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    deployment_green = advance(
        deployment_request["state"],
        {"deployment": converged},
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "step5_wait_queue_version_bound": WAIT_QUEUE_VERSION == REQUIRED_WAIT_QUEUE_VERSION,
        "deployment_controller_version_bound": DEPLOYMENT_CONVERGENCE_VERSION == REQUIRED_DEPLOYMENT_VERSION,
        "terminal_receipt_version_bound": TERMINAL_RECEIPT_VERSION == REQUIRED_RECEIPT_VERSION,
        "first_acquire_action_issued_once": (
            acquire["result"]["action"] == "ACQUIRE_OR_QUEUE_SCOPE_LEASE"
            and acquire_repeat["result"]["decision"] == "WAIT_FOR_LEASE_STATE_EVENT"
            and acquire_repeat["result"]["duplicate_action_suppressed"] is True
        ),
        "exact_head_proof_action_reached": leased["result"]["action"] == "RUN_EXACT_HEAD_PROOF",
        "merge_action_reached": proven["result"]["action"] == "MERGE_EXACT_PROVEN_HEAD",
        "merged_main_cert_action_reached": merged["result"]["action"] == "RUN_MERGED_MAIN_CERTIFICATION",
        "static_path_skips_deployment": certified["state"]["phase"] == "FREEZE",
        "freeze_action_reached": certified["result"]["action"] == "REGISTER_FROZEN_CHECKPOINT",
        "static_path_finishes": done["result"]["decision"] == "FINAL_MILE_DONE",
        "queued_path_waits_without_polling": (
            queued_wait["result"]["decision"] == "WAIT_FOR_LEASE_HANDOFF_EVENT"
            and queued_wait["result"]["polling_required"] is False
        ),
        "handoff_ticket_mismatch_blocks": (
            ticket_mismatch["result"]["decision"] == "FINAL_MILE_BLOCKED"
            and ticket_mismatch["state"]["blocked"]["reason"] == "LEASE_HANDOFF_TICKET_MISMATCH"
        ),
        "terminal_proof_failure_routes_to_backtrace": (
            failed_proof["result"]["decision"] == "FINAL_MILE_BLOCKED"
            and failed_proof["result"]["next_legal_action"] == "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"
        ),
        "deployment_required_path_requests_convergence": (
            deployment_request["state"]["phase"] == "DEPLOY_CERTIFY"
            and deployment_request["result"]["action"] == "START_OR_RESUME_DEPLOYMENT_CONVERGENCE"
        ),
        "converged_deployment_advances_to_freeze": (
            deployment_green["state"]["phase"] == "FREEZE"
            and deployment_green["result"]["action"] == "REGISTER_FROZEN_CHECKPOINT"
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "step5_wait_queue_version_bound",
        "deployment_controller_version_bound",
        "terminal_receipt_version_bound",
        "first_acquire_action_issued_once",
        "exact_head_proof_action_reached",
        "merge_action_reached",
        "merged_main_cert_action_reached",
        "static_path_skips_deployment",
        "freeze_action_reached",
        "static_path_finishes",
        "queued_path_waits_without_polling",
        "handoff_ticket_mismatch_blocks",
        "terminal_proof_failure_routes_to_backtrace",
        "deployment_required_path_requests_convergence",
        "converged_deployment_advances_to_freeze",
    ]
    if not all(result[name] is True for name in required):
        raise FinalMileAutopilotFailure("final-mile autopilot self-test failed")
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise FinalMileAutopilotFailure("pure-controller safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP6_FINAL_MILE_AUTOPILOT_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FinalMileAutopilotFailure as exc:
        print("MONSTER_V7_STEP6_FINAL_MILE_AUTOPILOT_BLOCKED: " + str(exc))
        raise SystemExit(1)
