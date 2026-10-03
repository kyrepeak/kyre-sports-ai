"""API2 Control-Plane Efficiency V1 Step 5 — State-Aware Proof Contracts.

Read-only proof-contract evaluator. It proves stable, valid control-plane states
instead of treating temporary observations as terminal truth.

The contract composes the frozen Step-3 WAIT state machine and Step-4 frozen
registry reconciliation planner by version identity only. It never polls,
reruns, mutates Git, updates the registry, or changes product/runtime state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.wait_state_machine_v1 import VERSION as WAIT_PARENT_VERSION
from devsystem.frozen_registry_auto_reconciler_v1 import VERSION as RECONCILER_PARENT_VERSION

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP5_STATE_AWARE_PROOF_CONTRACTS_V1"
EXPECTED_WAIT_PARENT_VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP3_WAIT_NOT_FAIL_V1"
EXPECTED_RECONCILER_PARENT_VERSION = (
    "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP4_FROZEN_REGISTRY_AUTO_RECONCILIATION_V1"
)
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
BLIND_POLLING_ALLOWED = False
MUTATION_AUTHORITY_GRANTED = False

_ALLOWED_FAILURE_DOMAINS = {
    "PRODUCT",
    "CONTROL_PLANE",
    "DEPLOYMENT",
    "UPSTREAM_DEPENDENCY",
    "PROOF_VERIFIER",
}

_STATE_FIELDS = {
    "READY": (
        "source_contract_green",
        "focused_proof_green",
        "devsystem_final_gate_green",
        "terminal_receipt_green",
        "frozen_registry_aligned",
    ),
    "WAIT": (
        "wait_decision",
        "wait_state_token",
        "resume_trigger",
        "event_driven_resume",
    ),
    "RECONCILING": (
        "reconciliation_decision",
        "apply_allowed",
        "previous_state_hash",
        "next_state_hash",
        "retry_after_state_change_only",
    ),
    "FAILED": (
        "terminal_failure",
        "failure_domain",
        "root_cause_fingerprint",
        "next_legal_action",
    ),
    "BLOCKED": (
        "blocker",
        "next_legal_action",
        "mutation_allowed",
    ),
}

_PROOF_OBLIGATIONS = {
    "READY": (
        "SOURCE_CONTRACT",
        "FOCUSED_EXACT_HEAD",
        "DEVSYSTEM_FINAL_GATE",
        "TERMINAL_RECEIPT",
        "FROZEN_REGISTRY",
    ),
    "WAIT": (
        "WAIT_CLASSIFICATION",
        "STATE_TOKEN",
        "EVENT_DRIVEN_RESUME",
    ),
    "RECONCILING": (
        "AUTHORIZED_RECONCILIATION",
        "STATE_HASH_PROGRESS",
    ),
    "FAILED": (
        "TERMINAL_FAILURE_CLASSIFICATION",
        "FAILURE_DOMAIN",
        "ROOT_CAUSE_FINGERPRINT",
        "NEXT_LEGAL_ACTION",
    ),
    "BLOCKED": (
        "BLOCKER_IDENTITY",
        "NEXT_LEGAL_ACTION",
        "MUTATION_DENIED",
    ),
}


class StateAwareProofFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any) -> str:
    return "STATE-" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:32].upper()


def _nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def _stable_subset(state: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {key: evidence.get(key) for key in _STATE_FIELDS[state]}


def _parent_versions_green() -> None:
    if WAIT_PARENT_VERSION != EXPECTED_WAIT_PARENT_VERSION:
        raise StateAwareProofFailure("frozen Step-3 WAIT parent version drift")
    if RECONCILER_PARENT_VERSION != EXPECTED_RECONCILER_PARENT_VERSION:
        raise StateAwareProofFailure("frozen Step-4 reconciliation parent version drift")


def _validate_ready(evidence: Mapping[str, Any]) -> list[str]:
    required = (
        "source_contract_green",
        "focused_proof_green",
        "devsystem_final_gate_green",
        "terminal_receipt_green",
        "frozen_registry_aligned",
    )
    reasons = [f"{key.upper()}_NOT_GREEN" for key in required if evidence.get(key) is not True]
    if evidence.get("terminal_failure") is True:
        reasons.append("READY_CONTRADICTS_TERMINAL_FAILURE")
    if str(evidence.get("wait_decision") or "").upper() == "WAIT":
        reasons.append("READY_CONTRADICTS_WAIT")
    return reasons


def _validate_wait(evidence: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if str(evidence.get("wait_decision") or "").upper() != "WAIT":
        reasons.append("WAIT_DECISION_MISSING")
    if not _nonempty(evidence.get("wait_state_token")):
        reasons.append("WAIT_STATE_TOKEN_MISSING")
    if not _nonempty(evidence.get("resume_trigger")):
        reasons.append("RESUME_TRIGGER_MISSING")
    if evidence.get("event_driven_resume") is not True:
        reasons.append("EVENT_DRIVEN_RESUME_REQUIRED")
    if evidence.get("terminal_failure") is True:
        reasons.append("WAIT_CONTRADICTS_TERMINAL_FAILURE")
    return reasons


def _validate_reconciling(evidence: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if str(evidence.get("reconciliation_decision") or "") != "AUTO_RECONCILIATION_PLANNED":
        reasons.append("AUTHORIZED_RECONCILIATION_PLAN_MISSING")
    if evidence.get("apply_allowed") is not True:
        reasons.append("RECONCILIATION_APPLY_NOT_AUTHORIZED")
    before = str(evidence.get("previous_state_hash") or "")
    after = str(evidence.get("next_state_hash") or "")
    if not before or not after or before == after:
        reasons.append("REGISTRY_STATE_HASH_DID_NOT_ADVANCE")
    if evidence.get("retry_after_state_change_only") is not True:
        reasons.append("RETRY_NOT_BOUND_TO_STATE_CHANGE")
    if evidence.get("terminal_failure") is True:
        reasons.append("RECONCILING_CONTRADICTS_TERMINAL_FAILURE")
    return reasons


def _validate_failed(evidence: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if evidence.get("terminal_failure") is not True:
        reasons.append("TERMINAL_FAILURE_NOT_PROVEN")
    domain = str(evidence.get("failure_domain") or "").upper()
    if domain not in _ALLOWED_FAILURE_DOMAINS:
        reasons.append("FAILURE_DOMAIN_INVALID")
    if not _nonempty(evidence.get("root_cause_fingerprint")):
        reasons.append("ROOT_CAUSE_FINGERPRINT_MISSING")
    if not _nonempty(evidence.get("next_legal_action")):
        reasons.append("NEXT_LEGAL_ACTION_MISSING")
    if str(evidence.get("wait_decision") or "").upper() == "WAIT":
        reasons.append("FAILED_CONTRADICTS_WAIT")
    return reasons


def _validate_blocked(evidence: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not _nonempty(evidence.get("blocker")):
        reasons.append("BLOCKER_MISSING")
    if not _nonempty(evidence.get("next_legal_action")):
        reasons.append("NEXT_LEGAL_ACTION_MISSING")
    if evidence.get("mutation_allowed") is not False:
        reasons.append("BLOCKED_STATE_MUST_DENY_MUTATION")
    return reasons


_VALIDATORS = {
    "READY": _validate_ready,
    "WAIT": _validate_wait,
    "RECONCILING": _validate_reconciling,
    "FAILED": _validate_failed,
    "BLOCKED": _validate_blocked,
}


def evaluate_state(state: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a stable proof contract for one authoritative control-plane state."""
    _parent_versions_green()
    normalized = str(state or "").strip().upper()
    if normalized not in _STATE_FIELDS:
        raise StateAwareProofFailure(f"unsupported state: {normalized or '<empty>'}")
    if not isinstance(evidence, Mapping):
        raise StateAwareProofFailure("evidence must be a mapping")

    stable = _stable_subset(normalized, evidence)
    reasons = _VALIDATORS[normalized](evidence)
    ignored = sorted(set(str(key) for key in evidence) - set(_STATE_FIELDS[normalized]))
    contract_basis = {
        "version": VERSION,
        "state": normalized,
        "stable_evidence": stable,
        "wait_parent_version": WAIT_PARENT_VERSION,
        "reconciler_parent_version": RECONCILER_PARENT_VERSION,
    }
    valid = not reasons
    return {
        "version": VERSION,
        "state": normalized,
        "status": "GREEN" if valid else "BLOCKED",
        "valid_state": valid,
        "green_eligible": valid and normalized == "READY",
        "proof_obligations": list(_PROOF_OBLIGATIONS[normalized]),
        "stable_evidence": stable,
        "ignored_transient_keys": ignored,
        "contract_fingerprint": _fingerprint(contract_basis),
        "reasons": reasons,
        "rerun_allowed": (
            valid
            and normalized == "RECONCILING"
            and evidence.get("retry_after_state_change_only") is True
        ),
        "blind_polling_allowed": BLIND_POLLING_ALLOWED,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def self_test() -> dict[str, Any]:
    ready = evaluate_state(
        "READY",
        {
            "source_contract_green": True,
            "focused_proof_green": True,
            "devsystem_final_gate_green": True,
            "terminal_receipt_green": True,
            "frozen_registry_aligned": True,
            "observed_at": "2026-10-03T02:00:00Z",
            "poll_count": 17,
        },
    )
    wait_a = evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "WAIT-ABC123",
            "resume_trigger": "deployment_identity_changed",
            "event_driven_resume": True,
            "public_runtime_ready": False,
            "temporary_selector_present": False,
            "poll_count": 1,
        },
    )
    wait_b = evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "WAIT-ABC123",
            "resume_trigger": "deployment_identity_changed",
            "event_driven_resume": True,
            "public_runtime_ready": True,
            "temporary_selector_present": True,
            "poll_count": 999,
        },
    )
    reconciling = evaluate_state(
        "RECONCILING",
        {
            "reconciliation_decision": "AUTO_RECONCILIATION_PLANNED",
            "apply_allowed": True,
            "previous_state_hash": "a" * 64,
            "next_state_hash": "b" * 64,
            "retry_after_state_change_only": True,
            "observed_at": "later",
        },
    )
    failed = evaluate_state(
        "FAILED",
        {
            "terminal_failure": True,
            "failure_domain": "CONTROL_PLANE",
            "root_cause_fingerprint": "ROOT-123",
            "next_legal_action": "PATCH_ONE_CONTROL_PLANE_ROOT",
            "temporary_http_status": 502,
        },
    )
    blocked = evaluate_state(
        "BLOCKED",
        {
            "blocker": "LEASE_CONFLICT",
            "next_legal_action": "WAIT_FOR_LEASE_RELEASE",
            "mutation_allowed": False,
        },
    )
    invalid_wait = evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "",
            "resume_trigger": "",
            "event_driven_resume": False,
        },
    )

    if not ready["green_eligible"]:
        raise StateAwareProofFailure("READY contract did not become green-eligible")
    if not wait_a["valid_state"] or wait_a["green_eligible"]:
        raise StateAwareProofFailure("WAIT contract validity drift")
    if wait_a["contract_fingerprint"] != wait_b["contract_fingerprint"]:
        raise StateAwareProofFailure("transient evidence changed stable WAIT contract identity")
    if not reconciling["valid_state"] or reconciling["rerun_allowed"] is not True:
        raise StateAwareProofFailure("reconciliation state contract drift")
    if not failed["valid_state"] or failed["green_eligible"]:
        raise StateAwareProofFailure("terminal failure state contract drift")
    if not blocked["valid_state"]:
        raise StateAwareProofFailure("blocked state contract drift")
    if invalid_wait["valid_state"]:
        raise StateAwareProofFailure("invalid WAIT state was accepted")

    return {
        "status": "GREEN",
        "version": VERSION,
        "ready_contract_green": ready["green_eligible"] is True,
        "wait_is_valid_nonfailure_state": wait_a["valid_state"] is True,
        "transient_noise_ignored": wait_a["contract_fingerprint"] == wait_b["contract_fingerprint"],
        "reconciliation_requires_state_progress": reconciling["rerun_allowed"] is True,
        "terminal_failure_is_valid_but_not_green": failed["green_eligible"] is False,
        "blocked_state_denies_mutation": blocked["mutation_authority_granted"] is False,
        "invalid_wait_fails_closed": invalid_wait["valid_state"] is False,
        "blind_polling_allowed": BLIND_POLLING_ALLOWED,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="self-test", choices=["self-test"])
    parser.parse_args(argv)
    result = self_test()
    print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP5_STATE_AWARE_PROOF_CONTRACTS_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StateAwareProofFailure as exc:
        print(f"API2_CONTROL_PLANE_EFFICIENCY_V1_STEP5_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
