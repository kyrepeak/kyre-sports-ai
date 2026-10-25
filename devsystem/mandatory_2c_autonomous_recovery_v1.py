"""MONSTER Step 2C — Autonomous Recovery + Green Convergence V1.

Read-only recovery controller used after one Step 2B diagnosis generation has
exhausted its two implementation attempts. Step 2C never patches code, starts
runs, or mutates product/runtime state. It keeps diagnosis moving, deduplicates
evidence, recognizes verified human-only blockers, and issues a deterministic
recovery receipt only when materially new root-cause evidence is proven.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_2C_AUTONOMOUS_RECOVERY_GREEN_CONVERGENCE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

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
_HUMAN_BLOCKER_TYPES = frozenset({
    "missing_credentials",
    "billing_or_plan",
    "required_human_approval",
    "irreversible_or_destructive_decision",
    "external_service_no_fallback",
})
_PATH_FIELDS = ("repository", "branch", "target", "proof_path")


class Mandatory2CAutonomousRecoveryFailure(RuntimeError):
    pass


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identity(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise Mandatory2CAutonomousRecoveryFailure(f"{label} is required")
    return text


def _normalize_path(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("authoritative_path is required")
    normalized: dict[str, str] = {}
    for field in _PATH_FIELDS:
        normalized[field] = _identity(value.get(field), f"authoritative_path.{field}")
    return normalized


def _history_fingerprints(
    failed_attempts: Sequence[Mapping[str, Any]],
    diagnostic_history: Sequence[Mapping[str, Any]],
) -> set[str]:
    fingerprints: set[str] = set()
    for item in failed_attempts:
        if not isinstance(item, Mapping):
            raise Mandatory2CAutonomousRecoveryFailure("failed_attempts entries must be objects")
        value = str(item.get("evidence_fingerprint") or item.get("fingerprint") or "").strip()
        if value:
            fingerprints.add(value)
    for item in diagnostic_history:
        if not isinstance(item, Mapping):
            raise Mandatory2CAutonomousRecoveryFailure("diagnostic_history entries must be objects")
        value = str(item.get("evidence_fingerprint") or item.get("fingerprint") or "").strip()
        if value:
            fingerprints.add(value)
    return fingerprints


def _base_result(decision: str, reason: str, *, allowed: bool, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "version": VERSION,
        "decision": decision,
        "reason": reason,
        "allowed": bool(allowed),
        "two_c_enforced": True,
        "requires_user_intervention": False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "recovery_receipt_hash": None,
    }
    result.update(extra)
    return result


def _normalize_context(context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(context, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("recovery context must be an object")
    task_id = _identity(context.get("task_id"), "task_id")
    checkpoint_id = _identity(context.get("checkpoint_id"), "checkpoint_id")
    authoritative_path = _normalize_path(context.get("authoritative_path"))
    try:
        failed_generation = int(context.get("failed_generation", 1))
    except (TypeError, ValueError) as exc:
        raise Mandatory2CAutonomousRecoveryFailure("failed_generation must be an integer") from exc
    if failed_generation < 1:
        raise Mandatory2CAutonomousRecoveryFailure("failed_generation must be >= 1")

    failed_attempts = context.get("failed_attempts", [])
    diagnostic_history = context.get("diagnostic_history", [])
    evidence_candidates = context.get("evidence_candidates", [])
    for value, label in (
        (failed_attempts, "failed_attempts"),
        (diagnostic_history, "diagnostic_history"),
        (evidence_candidates, "evidence_candidates"),
    ):
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise Mandatory2CAutonomousRecoveryFailure(f"{label} must be a sequence")

    return {
        "task_id": task_id,
        "checkpoint_id": checkpoint_id,
        "authoritative_path": authoritative_path,
        "failed_generation": failed_generation,
        "failed_attempts": [deepcopy(dict(item)) for item in failed_attempts],
        "diagnostic_history": [deepcopy(dict(item)) for item in diagnostic_history],
        "evidence_candidates": [deepcopy(dict(item)) for item in evidence_candidates],
        "root_cause": deepcopy(dict(context.get("root_cause") or {})),
        "human_blocker": deepcopy(dict(context.get("human_blocker") or {})),
    }


def decide_recovery(context: Mapping[str, Any]) -> dict[str, Any]:
    """Choose the next autonomous recovery action without performing it."""
    normalized = _normalize_context(context)
    used = _history_fingerprints(
        normalized["failed_attempts"],
        normalized["diagnostic_history"],
    )

    blocker = normalized["human_blocker"]
    blocker_type = str(blocker.get("type") or "").strip()
    blocker_evidence = str(blocker.get("evidence") or "").strip()
    if (
        blocker.get("verified") is True
        and blocker_type in _HUMAN_BLOCKER_TYPES
        and blocker_evidence
    ):
        return _base_result(
            "TWO_C_HUMAN_BLOCKER",
            "verified human-only blocker prevents autonomous convergence",
            allowed=False,
            requires_user_intervention=True,
            human_blocker_type=blocker_type,
            human_blocker_evidence=blocker_evidence,
            next_legal_action="REQUEST_EXACT_HUMAN_INPUT",
        )

    root = normalized["root_cause"]
    root_fp = str(root.get("evidence_fingerprint") or "").strip()
    classification = str(root.get("classification") or "").strip()
    failed_assumption = str(root.get("failed_assumption") or "").strip()
    repair_summary = str(root.get("repair_summary") or "").strip()
    if root.get("proven") is True:
        if (
            classification in _FAILURE_CLASSES
            and root_fp
            and root_fp not in used
            and failed_assumption
            and repair_summary
        ):
            payload = {
                "version": VERSION,
                "task_id": normalized["task_id"],
                "checkpoint_id": normalized["checkpoint_id"],
                "authoritative_path": normalized["authoritative_path"],
                "failed_generation": normalized["failed_generation"],
                "recovery_generation": normalized["failed_generation"] + 1,
                "consumed_evidence_fingerprints": sorted(used),
                "root_cause": {
                    "classification": classification,
                    "failed_assumption": failed_assumption,
                    "evidence_fingerprint": root_fp,
                    "repair_summary": repair_summary,
                },
            }
            receipt_hash = _hash(payload)
            receipt = {"payload": payload, "receipt_hash": receipt_hash}
            return _base_result(
                "TWO_C_RECOVERY_AUTHORIZED",
                "materially new root cause proven; a new diagnosis generation may re-enter Step 2B",
                allowed=True,
                recovery_generation=payload["recovery_generation"],
                root_cause=deepcopy(payload["root_cause"]),
                recovery_receipt_hash=receipt_hash,
                recovery_receipt=receipt,
                next_legal_action="REENTER_STEP_2B_WITH_RECOVERY_RECEIPT",
            )
        # A claimed root cause that reuses old evidence or is incomplete cannot
        # unlock another implementation generation. Keep diagnosis autonomous.

    for candidate in normalized["evidence_candidates"]:
        fingerprint = str(candidate.get("fingerprint") or "").strip()
        source = str(candidate.get("source") or "").strip()
        summary = str(candidate.get("summary") or "").strip()
        if (
            candidate.get("material") is True
            and fingerprint
            and fingerprint not in used
            and source
            and summary
        ):
            return _base_result(
                "TWO_C_GATHER_NEW_EVIDENCE",
                "unconsumed material evidence exists; investigate it before any repair",
                allowed=False,
                selected_evidence={
                    "fingerprint": fingerprint,
                    "source": source,
                    "summary": summary,
                },
                next_legal_action="GATHER_SELECTED_EVIDENCE",
            )

    return _base_result(
        "TWO_C_EXPAND_DIAGNOSIS",
        "no materially new proven root cause is available; expand diagnosis instead of repeating a repair",
        allowed=False,
        next_legal_action="GATHER_EVIDENCE_NEW_SOURCE",
    )


def validate_recovery_receipt(
    receipt: Mapping[str, Any],
    action: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a Step 2C receipt against the exact Step 2A/2B action."""
    if not isinstance(receipt, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt must be an object")
    payload = receipt.get("payload")
    if not isinstance(payload, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt payload is missing")
    if str(payload.get("version") or "") != VERSION:
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt version mismatch")
    expected_hash = _hash(payload)
    if str(receipt.get("receipt_hash") or "") != expected_hash:
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt hash mismatch")

    if not isinstance(action, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("action must be an object")
    if str(payload.get("task_id") or "") != str(action.get("task_id") or ""):
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt task mismatch")
    if str(payload.get("checkpoint_id") or "") != str(action.get("checkpoint_id") or ""):
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt checkpoint mismatch")

    preflight = action.get("reliability_preflight")
    if not isinstance(preflight, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("action reliability preflight is required")
    action_path = _normalize_path(preflight.get("authoritative_path"))
    receipt_path = _normalize_path(payload.get("authoritative_path"))
    if action_path != receipt_path:
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt authoritative path mismatch")
    if str(action.get("target") or "") != receipt_path["target"]:
        raise Mandatory2CAutonomousRecoveryFailure("recovery receipt target mismatch")

    try:
        failed_generation = int(payload.get("failed_generation"))
        recovery_generation = int(payload.get("recovery_generation"))
    except (TypeError, ValueError) as exc:
        raise Mandatory2CAutonomousRecoveryFailure("recovery generation is invalid") from exc
    if failed_generation < 1 or recovery_generation != failed_generation + 1:
        raise Mandatory2CAutonomousRecoveryFailure("recovery generation transition is invalid")

    root = payload.get("root_cause")
    if not isinstance(root, Mapping):
        raise Mandatory2CAutonomousRecoveryFailure("recovery root cause is missing")
    root_fp = _identity(root.get("evidence_fingerprint"), "root_cause.evidence_fingerprint")

    return {
        "valid": True,
        "version": VERSION,
        "receipt_hash": expected_hash,
        "failed_generation": failed_generation,
        "recovery_generation": recovery_generation,
        "root_cause_evidence_fingerprint": root_fp,
        "authoritative_path": receipt_path,
    }


def contract_self_test() -> dict[str, Any]:
    path = {
        "repository": "owner/repo",
        "branch": "step2c-self-test",
        "target": "github:mutation",
        "proof_path": "runless-v2",
    }
    base = {
        "task_id": "step2c-self-test",
        "checkpoint_id": "2C",
        "authoritative_path": path,
        "failed_generation": 1,
        "failed_attempts": [
            {"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "old-1"},
            {"attempt": 2, "outcome": "FAILED", "evidence_fingerprint": "old-2"},
        ],
        "diagnostic_history": [],
        "evidence_candidates": [],
    }

    duplicate = decide_recovery({
        **base,
        "evidence_candidates": [
            {"fingerprint": "old-2", "source": "log", "summary": "duplicate", "material": True},
        ],
    })
    recovered = decide_recovery({
        **base,
        "root_cause": {
            "proven": True,
            "classification": "verification/test",
            "failed_assumption": "old proof assumption",
            "evidence_fingerprint": "new-proof-evidence",
            "repair_summary": "repair the proof contract",
        },
    })
    action = {
        "task_id": "step2c-self-test",
        "checkpoint_id": "2C",
        "action_type": "patch",
        "target": "github:mutation",
        "reliability_preflight": {"authoritative_path": path},
    }
    validated = validate_recovery_receipt(recovered["recovery_receipt"], action)
    blocker = decide_recovery({
        **base,
        "human_blocker": {
            "verified": True,
            "type": "missing_credentials",
            "evidence": "credential required",
        },
    })

    result = {
        "status": "GREEN",
        "version": VERSION,
        "autonomous_diagnosis": duplicate["decision"] == "TWO_C_EXPAND_DIAGNOSIS",
        "duplicate_evidence_blocked": duplicate["allowed"] is False,
        "new_root_cause_recovery": (
            recovered["decision"] == "TWO_C_RECOVERY_AUTHORIZED"
            and recovered["allowed"] is True
            and validated["valid"] is True
        ),
        "human_blocker_fail_closed": (
            blocker["decision"] == "TWO_C_HUMAN_BLOCKER"
            and blocker["requires_user_intervention"] is True
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "autonomous_diagnosis",
        "duplicate_evidence_blocked",
        "new_root_cause_recovery",
        "human_blocker_fail_closed",
    )
    if not all(result[key] is True for key in required):
        raise Mandatory2CAutonomousRecoveryFailure("Step 2C contract self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_2C_AUTONOMOUS_RECOVERY_GREEN_CONVERGENCE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
