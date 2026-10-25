"""Permanent API2 execution controller with mandatory Step 2D data-truth verification."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import devsystem.api2_anti_loop_v1 as anti
from devsystem.api2_step2a_authority_v1 import (
    Step2AError,
    authority_snapshot,
    authorize_repair as step2a_authorize,
    begin_problem,
    consume_authorization,
    restore_authority,
)
from devsystem.api2_step2b_reliability_gate_v1 import validate_repair
from devsystem.api2_step2d_data_truth_gate_v1 import evaluate_field

VERSION = "API2_EXECUTION_CONTROLLER_V4_HARD_AUTHORITY"


class ControllerError(RuntimeError):
    pass


def new_state(
    *,
    problem_id: str,
    branch: str,
    proof_path: str,
    acceptance_criteria: Sequence[str] | None = None,
    authority_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = dict(authority_identity or {})
    authority = begin_problem(
        {},
        problem_id=problem_id,
        branch=branch,
        proof_path=proof_path,
        **identity,
    )
    return {
        "system": "api2",
        "authority": authority,
        "problem_id": problem_id,
        "branch": branch,
        "proof_path": proof_path,
        "acceptance_criteria": list(acceptance_criteria or []),
        "phase": "READY",
        "anti_loop": {},
        "step2c": None,
        "step2b": None,
        "step2d": None,
        "authorization": None,
        "verification_status": "NOT_STARTED",
        "green": False,
        "frozen": False,
        "blocker": None,
    }


def state_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    """Create a handoff snapshot that cannot silently reset authority or failures."""
    out = deepcopy(dict(state))
    try:
        out["authority_snapshot"] = authority_snapshot(out.get("authority") or {})
        out["anti_loop_snapshot"] = anti.state_snapshot(out.get("anti_loop") or {})
    except (Step2AError, anti.AntiLoopError) as exc:
        raise ControllerError("API2_CONTROLLER_SNAPSHOT_INVALID") from exc
    return out


def restore_state(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Resume exactly the snapshotted API2 execution identity; never create a new path."""
    out = deepcopy(dict(snapshot))
    if out.get("system") != "api2":
        raise ControllerError("API2_CONTROLLER_RESUME_SYSTEM_INVALID")
    try:
        restored_authority = restore_authority(out.get("authority_snapshot") or {})
        restored_anti_loop = anti.restore_state(out.get("anti_loop_snapshot") or {})
    except Step2AError as exc:
        raise ControllerError("API2_CONTROLLER_RESUME_AUTHORITY_INVALID") from exc
    except anti.AntiLoopError as exc:
        raise ControllerError("API2_CONTROLLER_RESUME_ANTI_LOOP_INVALID") from exc

    active = dict(restored_authority.get("active_problem") or {})
    expected = {
        "problem_id": out.get("problem_id"),
        "branch": out.get("branch"),
        "proof_path": out.get("proof_path"),
    }
    observed = {key: active.get(key) for key in expected}
    if observed != expected:
        raise ControllerError("API2_CONTROLLER_RESUME_PATH_MISMATCH")

    out["authority"] = restored_authority
    out["anti_loop"] = restored_anti_loop
    return out


def record_failure(
    state: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    evidence: Sequence[Any],
    hypothesis: str,
    classification: str | None = None,
) -> dict[str, Any]:
    out = deepcopy(dict(state))
    out["anti_loop"] = anti.record_failure(
        out.get("anti_loop") or {},
        action=action,
        evidence=evidence,
        hypothesis=hypothesis,
        classification=classification,
    )
    out["failed_action"] = dict(action)
    out["failure_evidence"] = list(evidence)
    out["failure_hypothesis"] = hypothesis
    out["failure_classification"] = classification or "UNCLASSIFIED"
    out["phase"] = "STEP_2C"
    out["step2c_status"] = "REQUIRED"
    out["step2b_status"] = "WAITING"
    out["step2a_status"] = "BLOCKED"
    out["step2d_status"] = "NOT_STARTED"
    return out


def submit_step2c(state: Mapping[str, Any], investigation: Mapping[str, Any]) -> dict[str, Any]:
    if state.get("phase") != "STEP_2C":
        raise ControllerError("API2_STEP2C_OUT_OF_ORDER")
    out = deepcopy(dict(state))
    out["step2c"] = dict(investigation)
    if investigation.get("human_only_blocker") is True:
        out["phase"] = "HUMAN_ONLY_BLOCKER"
        out["blocker"] = dict(investigation)
        out["step2c_status"] = "HUMAN_ONLY_BLOCKER"
        return out
    if (
        investigation.get("next_phase") != "STEP_2B"
        or not investigation.get("root_cause")
        or not investigation.get("evidence_digest")
    ):
        raise ControllerError("API2_STEP2C_EVIDENCE_INCOMPLETE")
    out["phase"] = "STEP_2B"
    out["step2c_status"] = "GREEN"
    out["step2b_status"] = "REQUIRED"
    return out


def submit_step2b(state: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    if state.get("phase") != "STEP_2B":
        raise ControllerError("API2_STEP2B_OUT_OF_ORDER")
    out = deepcopy(dict(state))
    decision = validate_repair(payload)
    out["step2b"] = decision
    if decision.get("allowed") is not True:
        out["phase"] = "STEP_2C"
        out["step2b_status"] = "BLOCKED"
        out["step2c_status"] = "REQUIRED_DEEPER_INVESTIGATION"
        out["step2a_status"] = "BLOCKED"
        return out
    inv = state.get("step2c") or {}
    anti_decision = anti.authorize_retry(
        state.get("anti_loop") or {},
        action=state.get("failed_action") or {},
        evidence=[inv.get("evidence_digest")],
        hypothesis=str(inv.get("hypothesis") or inv.get("root_cause") or ""),
    )
    out["anti_loop_decision"] = anti_decision
    if anti_decision.get("allowed") is not True:
        out["phase"] = "STEP_2C"
        out["step2b_status"] = "GREEN"
        out["step2c_status"] = "REQUIRED_DEEPER_INVESTIGATION"
        out["step2a_status"] = "BLOCKED"
        return out
    out["phase"] = "STEP_2A"
    out["step2b_status"] = "GREEN"
    out["step2a_status"] = "READY"
    return out


def authorize_repair(state: Mapping[str, Any], repair: Mapping[str, Any]):
    if state.get("phase") != "STEP_2A":
        raise ControllerError("API2_STEP2A_OUT_OF_ORDER")
    token = step2a_authorize(
        state["authority"],
        repair=repair,
        reliability=state["step2b"],
        anti_loop=state["anti_loop_decision"],
    )
    out = deepcopy(dict(state))
    out["authorization"] = token
    out["phase"] = "EXECUTE"
    out["step2a_status"] = "AUTHORIZED"
    return out, token


def mark_repair_executed(
    state: Mapping[str, Any], authorization: Mapping[str, Any]
) -> dict[str, Any]:
    if state.get("phase") != "EXECUTE" or state.get("authorization") != dict(authorization):
        raise ControllerError("API2_EXECUTION_OUT_OF_ORDER")
    out = deepcopy(dict(state))
    out["authority"] = consume_authorization(out["authority"], authorization)
    out["phase"] = "STEP_2D"
    out["step2a_status"] = "CONSUMED"
    out["step2d_status"] = "REQUIRED"
    out["verification_status"] = "WAITING_FOR_STEP_2D"
    return out


def submit_step2d(
    state: Mapping[str, Any],
    field_payloads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if state.get("phase") != "STEP_2D":
        raise ControllerError("API2_STEP2D_OUT_OF_ORDER")
    payloads = [dict(item) for item in (field_payloads or [])]
    if not payloads:
        raise ControllerError("API2_STEP2D_PROOF_MISSING")

    decisions = [evaluate_field(payload) for payload in payloads]
    out = deepcopy(dict(state))
    out["step2d"] = decisions
    failures = [decision for decision in decisions if decision.get("allowed") is not True]
    if failures:
        action = dict(out.get("failed_action") or {"type": "VERIFY", "target": "STEP_2D"})
        evidence = [
            {
                "state": failure.get("state"),
                "resolved_provider": failure.get("resolved_provider"),
            }
            for failure in failures
        ]
        out["anti_loop"] = anti.record_failure(
            out.get("anti_loop") or {},
            action=action,
            evidence=evidence,
            hypothesis="step2d_data_truth_failure",
        )
        out["failure_evidence"] = evidence
        out["failure_hypothesis"] = "step2d_data_truth_failure"
        out["phase"] = "STEP_2C"
        out["step2d_status"] = "BLOCKED"
        out["step2c_status"] = "REQUIRED_DEEPER_INVESTIGATION"
        out["step2b_status"] = "WAITING"
        out["step2a_status"] = "BLOCKED"
        out["verification_status"] = "BLOCKED_BY_STEP_2D"
        return out

    out["step2d_status"] = "GREEN"
    out["phase"] = "VERIFY"
    out["verification_status"] = "REQUIRED"
    return out


def record_verification(
    state: Mapping[str, Any], proofs: Mapping[str, bool]
) -> dict[str, Any]:
    if state.get("phase") != "VERIFY":
        raise ControllerError("API2_VERIFICATION_OUT_OF_ORDER")
    if state.get("step2d_status") != "GREEN":
        raise ControllerError("API2_GREEN_BEFORE_STEP2D")
    criteria = list(state.get("acceptance_criteria") or [])
    if not criteria or any(proofs.get(c) is not True for c in criteria):
        raise ControllerError("API2_GREEN_PROOF_INCOMPLETE")
    out = deepcopy(dict(state))
    out["verification_status"] = "VERIFIED"
    out["green"] = True
    out["frozen"] = False
    out["phase"] = "GREEN"
    out["verification_proofs"] = dict(proofs)
    return out


def record_freeze_readback(
    state: Mapping[str, Any], checkpoint: Mapping[str, Any]
) -> dict[str, Any]:
    if state.get("phase") != "GREEN" or state.get("green") is not True:
        raise ControllerError("API2_FREEZE_BEFORE_GREEN")
    if (
        checkpoint.get("status") != "FROZEN"
        or not str(checkpoint.get("checkpoint_id") or "").startswith("API2_")
    ):
        raise ControllerError("API2_FREEZE_READBACK_INVALID")
    out = deepcopy(dict(state))
    out["frozen"] = True
    out["phase"] = "FROZEN"
    out["freeze_checkpoint"] = dict(checkpoint)
    return out


def status_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    phase = str(state.get("phase") or "UNKNOWN")
    progress = {
        "READY": 5,
        "STEP_2C": 30,
        "STEP_2B": 50,
        "STEP_2A": 65,
        "EXECUTE": 78,
        "STEP_2D": 88,
        "VERIFY": 94,
        "GREEN": 97,
        "FROZEN": 100,
        "HUMAN_ONLY_BLOCKER": 0,
    }.get(phase, 10)
    root = (state.get("step2c") or {}).get("root_cause") or state.get("failure_hypothesis")
    return {
        "current_phase": phase,
        "progress_percent": progress,
        "active_problem": state.get("problem_id"),
        "authoritative_api2_path": {
            "branch": state.get("branch"),
            "proof_path": state.get("proof_path"),
            "authority_digest": (state.get("authority") or {}).get("authority_digest"),
        },
        "current_root_cause_hypothesis": root,
        "step_2c_status": state.get("step2c_status", "NOT_REQUIRED"),
        "step_2b_status": state.get("step2b_status", "NOT_STARTED"),
        "step_2a_authorization_status": state.get("step2a_status", "NOT_AUTHORIZED"),
        "step_2d_status": state.get("step2d_status", "NOT_STARTED"),
        "anti_loop_status": (
            "SATISFIED"
            if (state.get("anti_loop_decision") or {}).get("allowed")
            else ("ACTIVE" if state.get("anti_loop") else "IDLE")
        ),
        "verification_status": state.get("verification_status"),
        "blocker": state.get("blocker"),
        "green_frozen_checkpoint": (
            "FROZEN" if state.get("frozen") else ("GREEN" if state.get("green") else "PENDING")
        ),
    }
