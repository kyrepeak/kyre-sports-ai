"""MONSTER Step 2B — First/Second-Pass Reliability Gate V1.

Fail-closed pre-implementation gate for implementation-producing actions.
It requires a complete preflight before attempt 1, requires classified new
evidence before attempt 2, and hands control to Anti-Loop / root-cause reset
after two failed implementation attempts.

This module performs no network calls and no repository/product mutations.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_2B_FIRST_SECOND_PASS_RELIABILITY_GATE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

IMPLEMENTATION_ACTION_TYPES = frozenset({"patch", "edit_product"})
_FAILURE_CLASSES = frozenset({
    "architecture",
    "provider/data",
    "authentication",
    "network",
    "parser",
    "normalization",
    "canonical-id",
    "frontend",
    "configuration/environment",
    "deployment",
    "caching/state",
    "verification/test",
})
_PATH_FIELDS = ("repository", "branch", "target", "proof_path")
_CRITERION_FIELDS = ("id", "requirement", "source", "verification", "expected_result")
_DEPENDENCY_FLAGS = ("reachable", "auth_ok", "response_shape_ok", "required_fields_ok", "freshness_ok")


class Mandatory2BReliabilityGateFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _result(decision: str, reason: str, *, allowed: bool, **extra: Any) -> dict[str, Any]:
    result = {
        "version": VERSION,
        "decision": decision,
        "reason": reason,
        "allowed": bool(allowed),
        "two_b_enforced": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    result.update(extra)
    return result


def _validate_action_identity(action: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise Mandatory2BReliabilityGateFailure("action must be an object")
    required = ("task_id", "checkpoint_id", "action_type", "target")
    missing = [field for field in required if not str(action.get(field) or "").strip()]
    if missing:
        raise Mandatory2BReliabilityGateFailure(
            "action missing required fields: " + ", ".join(missing)
        )
    return {
        "task_id": str(action["task_id"]),
        "checkpoint_id": str(action["checkpoint_id"]),
        "action_type": str(action["action_type"]),
        "target": str(action["target"]),
    }


def _failed_attempts(history: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, Mapping):
            raise Mandatory2BReliabilityGateFailure("attempt history entries must be objects")
        if str(item.get("outcome") or "").upper() == "FAILED":
            failed.append(deepcopy(dict(item)))
    return failed


def _validate_preflight(preflight: Mapping[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(preflight, Mapping):
        return False, "reliability_preflight is required", {}

    if not str(preflight.get("finished_state") or "").strip():
        return False, "finished_state is required", {}
    if preflight.get("current_state_inspected") is not True:
        return False, "current-state inspection must be proven before implementation", {}
    if preflight.get("root_cause_proven") is not True:
        return False, "root cause must be proven before implementation", {}

    path = preflight.get("authoritative_path")
    if not isinstance(path, Mapping):
        return False, "authoritative_path is required", {}
    path_missing = [field for field in _PATH_FIELDS if not str(path.get(field) or "").strip()]
    if path_missing:
        return False, "authoritative_path missing: " + ", ".join(path_missing), {}

    criteria = preflight.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        return False, "at least one acceptance criterion is required", {}
    criterion_ids: set[str] = set()
    for criterion in criteria:
        if not isinstance(criterion, Mapping):
            return False, "acceptance criteria must be objects", {}
        missing = [field for field in _CRITERION_FIELDS if not str(criterion.get(field) or "").strip()]
        if missing:
            return False, "acceptance criterion missing: " + ", ".join(missing), {}
        cid = str(criterion["id"])
        if cid in criterion_ids:
            return False, "acceptance criterion ids must be unique", {}
        criterion_ids.add(cid)

    dependencies = preflight.get("dependency_checks", [])
    if not isinstance(dependencies, list):
        return False, "dependency_checks must be a list", {}
    for dependency in dependencies:
        if not isinstance(dependency, Mapping):
            return False, "dependency checks must be objects", {}
        name = str(dependency.get("name") or "").strip()
        if not name:
            return False, "dependency check name is required", {}
        failed_flags = [flag for flag in _DEPENDENCY_FLAGS if dependency.get(flag) is not True]
        if failed_flags:
            return False, f"dependency {name} failed: " + ", ".join(failed_flags), {
                "dependency_name": name,
                "failed_dependency_checks": failed_flags,
            }

    normalized = {
        "finished_state": str(preflight["finished_state"]),
        "current_state_inspected": True,
        "root_cause_proven": True,
        "authoritative_path": {field: str(path[field]) for field in _PATH_FIELDS},
        "acceptance_criteria": [dict(item) for item in criteria],
        "dependency_checks": [dict(item) for item in dependencies],
    }
    return True, "preflight complete", normalized


def authorize_implementation(action: Mapping[str, Any]) -> dict[str, Any]:
    """Authorize implementation attempt 1 or 2, or fail closed.

    The action carries `reliability_preflight` and optional
    `implementation_attempt_history`. This keeps the proof bound to the exact
    Step-2A action rather than to an out-of-band chat instruction.
    """
    identity = _validate_action_identity(action)
    action_type = identity["action_type"]
    if action_type not in IMPLEMENTATION_ACTION_TYPES:
        return _result(
            "TWO_B_NOT_REQUIRED",
            "action does not produce an implementation mutation",
            allowed=True,
            implementation_attempt=None,
            reliability_receipt_hash=None,
        )

    preflight = action.get("reliability_preflight")
    if not isinstance(preflight, Mapping):
        return _result(
            "TWO_B_PREFLIGHT_REQUIRED",
            "implementation-producing actions require Step 2B preflight",
            allowed=False,
            implementation_attempt=1,
            next_legal_action="COMPLETE_RELIABILITY_PREFLIGHT",
        )

    ok, reason, normalized = _validate_preflight(preflight)
    if not ok:
        decision = (
            "TWO_B_DEPENDENCY_PREFLIGHT_BLOCKED"
            if "dependency_name" in normalized
            else "TWO_B_PREFLIGHT_INCOMPLETE"
        )
        return _result(
            decision,
            reason,
            allowed=False,
            implementation_attempt=1,
            next_legal_action="REPAIR_PREFLIGHT",
            **normalized,
        )

    history = action.get("implementation_attempt_history", [])
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes, bytearray)):
        return _result(
            "TWO_B_ATTEMPT_HISTORY_INVALID",
            "implementation_attempt_history must be a sequence",
            allowed=False,
            next_legal_action="REPAIR_ATTEMPT_HISTORY",
        )
    failed = _failed_attempts(history)

    if len(failed) >= 2:
        return _result(
            "TWO_B_ROOT_CAUSE_RESET_REQUIRED",
            "two implementation attempts already failed; no third patch without root-cause reset",
            allowed=False,
            implementation_attempt=3,
            anti_loop_handoff=True,
            next_legal_action="ROOT_CAUSE_RESET",
            recheck_policy="ONLY_AFTER_MATERIALLY_NEW_EVIDENCE",
        )

    attempt = len(failed) + 1
    if attempt == 2:
        classification = str(preflight.get("failure_classification") or "").strip()
        failed_assumption = str(preflight.get("failed_assumption") or "").strip()
        new_evidence = preflight.get("new_evidence")
        new_fp = str(new_evidence.get("fingerprint") or "").strip() if isinstance(new_evidence, Mapping) else ""
        new_summary = str(new_evidence.get("summary") or "").strip() if isinstance(new_evidence, Mapping) else ""
        prior_fps = {str(item.get("evidence_fingerprint") or "").strip() for item in failed}
        if (
            classification not in _FAILURE_CLASSES
            or not failed_assumption
            or not new_fp
            or not new_summary
            or new_fp in prior_fps
        ):
            return _result(
                "TWO_B_ATTEMPT_2_EVIDENCE_REQUIRED",
                "attempt 2 requires failure classification, failed assumption, and materially new evidence",
                allowed=False,
                implementation_attempt=2,
                next_legal_action="CLASSIFY_FAILED_ASSUMPTION",
            )
        normalized["failure_classification"] = classification
        normalized["failed_assumption"] = failed_assumption
        normalized["new_evidence"] = dict(new_evidence)

    receipt_payload = {
        "version": VERSION,
        "identity": identity,
        "implementation_attempt": attempt,
        "preflight": normalized,
        "failed_attempt_count": len(failed),
    }
    receipt_hash = _hash(receipt_payload)
    decision = "TWO_B_ATTEMPT_1_AUTHORIZED" if attempt == 1 else "TWO_B_ATTEMPT_2_AUTHORIZED"
    return _result(
        decision,
        "reliability preflight authorizes implementation",
        allowed=True,
        implementation_attempt=attempt,
        reliability_receipt_hash=receipt_hash,
        reliability_receipt={"payload": receipt_payload, "receipt_hash": receipt_hash},
        next_legal_action="IMPLEMENT_COMPLETE_REPAIR",
    )


def require_reliability_authority(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping) or result.get("allowed") is not True:
        decision = str(result.get("decision") if isinstance(result, Mapping) else "missing")
        raise Mandatory2BReliabilityGateFailure(
            f"Step 2B reliability authorization required before implementation: {decision}"
        )
    return deepcopy(dict(result))


def contract_self_test() -> dict[str, Any]:
    base_preflight = {
        "finished_state": "self-test complete",
        "current_state_inspected": True,
        "root_cause_proven": True,
        "authoritative_path": {
            "repository": "owner/repo",
            "branch": "step2b-self-test",
            "target": "github:mutation",
            "proof_path": "production",
        },
        "acceptance_criteria": [{
            "id": "ac1",
            "requirement": "self-test passes",
            "source": "control-plane",
            "verification": "contract_self_test",
            "expected_result": "GREEN",
        }],
        "dependency_checks": [],
    }
    action = {
        "task_id": "self-test",
        "checkpoint_id": "2B",
        "action_type": "patch",
        "target": "github:mutation",
        "reliability_preflight": base_preflight,
        "implementation_attempt_history": [],
    }
    attempt1 = authorize_implementation(action)
    attempt3 = authorize_implementation({
        **action,
        "implementation_attempt_history": [
            {"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "e1"},
            {"attempt": 2, "outcome": "FAILED", "evidence_fingerprint": "e2"},
        ],
    })
    if attempt1["decision"] != "TWO_B_ATTEMPT_1_AUTHORIZED" or attempt1["allowed"] is not True:
        raise Mandatory2BReliabilityGateFailure("attempt-1 self-test failed")
    if attempt3["decision"] != "TWO_B_ROOT_CAUSE_RESET_REQUIRED" or attempt3["allowed"] is not False:
        raise Mandatory2BReliabilityGateFailure("two-attempt anti-loop self-test failed")
    return {
        "status": "GREEN",
        "version": VERSION,
        "first_pass_gate": True,
        "second_pass_requires_new_evidence": True,
        "third_patch_blocked": True,
        "anti_loop_root_cause_reset": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


if __name__ == "__main__":
    print("MONSTER_2B_FIRST_SECOND_PASS_RELIABILITY_GATE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
