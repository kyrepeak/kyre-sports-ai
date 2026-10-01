"""MONSTER V6 Step 3 — Deployment Convergence Controller V1.

Read-only bounded deployment recovery state machine.

Purpose:
- distinguish code defects from deployment lag / stale activation / verifier timing;
- allow at most one refresh, one full redeploy, and one runtime verification;
- stop escalation once the bounded recovery budget is consumed;
- never authorize a product-code patch from deployment evidence.

The controller performs no network calls and no mutations. Any external refresh
or redeploy still requires MONSTER Step 2A authorization and the correct
scope-aware lease.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.deployment_truth_control_plane_v1 import VERSION as DEPLOYMENT_TRUTH_VERSION

VERSION = "MONSTER_V6_DEPLOYMENT_CONVERGENCE_CONTROLLER_V1"
OWNER = "DEPLOYMENT"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
PRODUCT_PATCH_ALLOWED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PHASES = {"QUEUED", "BUILDING", "ACTIVATING", "LIVE", "FAILED", "UNKNOWN"}

REFRESH = "REFRESH_DEPLOYMENT_ONCE"
FULL_REDEPLOY = "FULL_REDEPLOY_ONCE"
VERIFY_RUNTIME = "VERIFY_RUNTIME_ONCE"

_CONSUMABLE_ACTIONS = {REFRESH, FULL_REDEPLOY, VERIFY_RUNTIME}


class DeploymentConvergenceFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(value))
    payload.pop("decision_id", None)
    return "CONVERGE-" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()


def _sha(value: Any, *, required: bool) -> str:
    text = str(value or "").strip().lower()
    if not text and not required:
        return ""
    if not _SHA40.fullmatch(text):
        raise DeploymentConvergenceFailure("deployment SHA must be a full 40-character lowercase hex SHA")
    return text


def _consumed(values: Sequence[Any]) -> list[str]:
    out = sorted({str(value or "").strip().upper() for value in values if str(value or "").strip()})
    unknown = sorted(set(out) - _CONSUMABLE_ACTIONS)
    if unknown:
        raise DeploymentConvergenceFailure(f"unknown consumed deployment action(s): {unknown}")
    return out


def _proof_flags(health_ok: bool | None, readiness_ok: bool | None, ui_ok: bool | None) -> dict[str, bool | None]:
    return {
        "health_ok": health_ok if health_ok is None else bool(health_ok),
        "readiness_ok": readiness_ok if readiness_ok is None else bool(readiness_ok),
        "ui_ok": ui_ok if ui_ok is None else bool(ui_ok),
    }


def _bounded_action(
    *,
    preferred: str,
    consumed: set[str],
    fallback: str,
) -> str:
    return fallback if preferred in consumed else preferred


def build_convergence_decision(
    *,
    expected_sha: str,
    observed_sha: str = "",
    deploy_phase: str,
    health_ok: bool | None = None,
    readiness_ok: bool | None = None,
    ui_ok: bool | None = None,
    consumed_actions: Sequence[str] = (),
) -> dict[str, Any]:
    expected = _sha(expected_sha, required=True)
    phase = str(deploy_phase or "").strip().upper()
    if phase not in _PHASES:
        raise DeploymentConvergenceFailure(f"unsupported deployment phase: {phase or '<empty>'}")

    observed_required = phase == "LIVE"
    observed = _sha(observed_sha, required=False)
    consumed = set(_consumed(consumed_actions))
    proof = _proof_flags(health_ok, readiness_ok, ui_ok)

    state: str
    diagnosis: str
    next_action: str

    if phase in {"QUEUED", "BUILDING", "ACTIVATING"}:
        state = "DEPLOYMENT_IN_FLIGHT"
        diagnosis = "deployment is still progressing; mutation before a terminal deployment event would be premature"
        next_action = "WAIT_FOR_DEPLOYMENT_EVENT"

    elif phase == "UNKNOWN":
        state = "DEPLOYMENT_STATE_INCOMPLETE"
        diagnosis = "deployment phase is not yet known"
        next_action = "COLLECT_DEPLOYMENT_STATE"

    elif phase == "FAILED":
        if FULL_REDEPLOY not in consumed:
            state = "DEPLOYMENT_FAILED_RECOVERABLE"
            diagnosis = "deployment failed before convergence; one full redeploy remains in the bounded recovery budget"
            next_action = FULL_REDEPLOY
        else:
            state = "DEPLOYMENT_RECOVERY_EXHAUSTED"
            diagnosis = "deployment failed after the one allowed full redeploy"
            next_action = "CLASSIFY_DEPLOYMENT_CONVERGENCE_FAILURE"

    elif phase == "LIVE" and not observed:
        state = "DEPLOYMENT_IDENTITY_NOT_READY"
        diagnosis = "deployment reports LIVE but the production identity is not available yet"
        next_action = "WAIT_FOR_DEPLOYMENT_IDENTITY_EVENT"

    elif phase == "LIVE" and observed != expected:
        if REFRESH not in consumed:
            state = "STALE_DEPLOYMENT"
            diagnosis = "production is live but still serves an older SHA; one refresh remains"
            next_action = REFRESH
        elif FULL_REDEPLOY not in consumed:
            state = "STALE_AFTER_REFRESH"
            diagnosis = "production remains stale after the one allowed refresh; one full redeploy remains"
            next_action = FULL_REDEPLOY
        else:
            state = "DEPLOYMENT_RECOVERY_EXHAUSTED"
            diagnosis = "production remains stale after the bounded refresh plus full-redeploy sequence"
            next_action = "CLASSIFY_DEPLOYMENT_CONVERGENCE_FAILURE"

    else:
        # LIVE and exact deployment identity.
        missing = sorted(name for name, value in proof.items() if value is None)
        failed = sorted(name for name, value in proof.items() if value is False)

        if not missing and not failed:
            state = "DEPLOYMENT_CONVERGED"
            diagnosis = "production SHA, health, readiness, and UI proof all match the expected release"
            next_action = "FREEZE_DEPLOYMENT_CONVERGENCE"
        elif VERIFY_RUNTIME not in consumed:
            state = "RUNTIME_PROOF_PENDING" if missing else "RUNTIME_PROOF_FAILED"
            diagnosis = (
                "exact production SHA is live but runtime proof is incomplete"
                if missing
                else "exact production SHA is live but runtime/UI proof is not green"
            )
            next_action = VERIFY_RUNTIME
        else:
            state = "RUNTIME_OR_VERIFIER_FAILURE"
            diagnosis = "exact production SHA is live and one runtime verification was already consumed; redeploy is not justified"
            next_action = "CLASSIFY_RUNTIME_OR_VERIFIER_FAILURE"

    action_budget = {
        REFRESH: 0 if REFRESH in consumed else 1,
        FULL_REDEPLOY: 0 if FULL_REDEPLOY in consumed else 1,
        VERIFY_RUNTIME: 0 if VERIFY_RUNTIME in consumed else 1,
    }
    deployment_mutation_requested = next_action in {REFRESH, FULL_REDEPLOY}

    result: dict[str, Any] = {
        "schema_version": 1,
        "version": VERSION,
        "deployment_truth_version": DEPLOYMENT_TRUTH_VERSION,
        "owner": OWNER,
        "state": state,
        "diagnosis": diagnosis,
        "expected_sha": expected,
        "observed_sha": observed,
        "deploy_phase": phase,
        "proof": proof,
        "consumed_actions": sorted(consumed),
        "action_budget_remaining": action_budget,
        "next_legal_action": next_action,
        "converged": state == "DEPLOYMENT_CONVERGED",
        "deployment_mutation_requested": deployment_mutation_requested,
        "product_patch_allowed": PRODUCT_PATCH_ALLOWED,
        "protections": {
            "one_refresh_max": True,
            "one_full_redeploy_max": True,
            "one_runtime_verify_max": True,
            "wait_during_in_flight_phase": True,
            "exact_sha_before_runtime_diagnosis": True,
            "no_redeploy_after_exact_sha_runtime_failure": True,
            "product_patch_blocked_from_deployment_evidence": True,
            "step_2a_required_for_external_action": True,
            "scope_lease_required_for_external_action": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        },
    }
    result["decision_id"] = _fingerprint(result)
    return validate_convergence_decision(result)


def validate_convergence_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DeploymentConvergenceFailure("deployment convergence decision must be an object")
    value = deepcopy(dict(payload))
    supplied = str(value.get("decision_id") or "")
    if not supplied:
        raise DeploymentConvergenceFailure("decision_id is required")
    if supplied != _fingerprint(value):
        raise DeploymentConvergenceFailure("deployment convergence decision fingerprint mismatch")
    if value.get("version") != VERSION or int(value.get("schema_version", 0)) != 1:
        raise DeploymentConvergenceFailure("deployment convergence version/schema mismatch")
    if value.get("owner") != OWNER:
        raise DeploymentConvergenceFailure("deployment convergence owner drift")
    if value.get("product_patch_allowed") is not False:
        raise DeploymentConvergenceFailure("deployment evidence may not authorize a product patch")
    protections = value.get("protections") or {}
    required_true = [
        "one_refresh_max",
        "one_full_redeploy_max",
        "one_runtime_verify_max",
        "wait_during_in_flight_phase",
        "exact_sha_before_runtime_diagnosis",
        "no_redeploy_after_exact_sha_runtime_failure",
        "product_patch_blocked_from_deployment_evidence",
        "step_2a_required_for_external_action",
        "scope_lease_required_for_external_action",
    ]
    if not all(protections.get(name) is True for name in required_true):
        raise DeploymentConvergenceFailure("deployment convergence protections drift")
    if protections.get("network_calls") or protections.get("auto_mutate") or protections.get("may_modify_product_runtime") or protections.get("mutation_authority_granted"):
        raise DeploymentConvergenceFailure("read-only deployment convergence invariant failed")
    return value


def contract_self_test() -> dict[str, Any]:
    expected = "a" * 40
    stale = "b" * 40

    queued = build_convergence_decision(expected_sha=expected, deploy_phase="QUEUED")
    building = build_convergence_decision(expected_sha=expected, deploy_phase="BUILDING")
    activating = build_convergence_decision(expected_sha=expected, deploy_phase="ACTIVATING")

    stale_first = build_convergence_decision(
        expected_sha=expected,
        observed_sha=stale,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    stale_after_refresh = build_convergence_decision(
        expected_sha=expected,
        observed_sha=stale,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
        consumed_actions=[REFRESH],
    )
    stale_exhausted = build_convergence_decision(
        expected_sha=expected,
        observed_sha=stale,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
        consumed_actions=[REFRESH, FULL_REDEPLOY],
    )
    failed_first = build_convergence_decision(
        expected_sha=expected,
        deploy_phase="FAILED",
    )
    failed_exhausted = build_convergence_decision(
        expected_sha=expected,
        deploy_phase="FAILED",
        consumed_actions=[FULL_REDEPLOY],
    )
    exact_pending = build_convergence_decision(
        expected_sha=expected,
        observed_sha=expected,
        deploy_phase="LIVE",
    )
    exact_failed = build_convergence_decision(
        expected_sha=expected,
        observed_sha=expected,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=False,
        ui_ok=True,
    )
    exact_after_verify = build_convergence_decision(
        expected_sha=expected,
        observed_sha=expected,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=False,
        ui_ok=True,
        consumed_actions=[VERIFY_RUNTIME],
    )
    converged = build_convergence_decision(
        expected_sha=expected,
        observed_sha=expected,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "queued_waits": queued["next_legal_action"] == "WAIT_FOR_DEPLOYMENT_EVENT",
        "building_waits": building["next_legal_action"] == "WAIT_FOR_DEPLOYMENT_EVENT",
        "activating_waits": activating["next_legal_action"] == "WAIT_FOR_DEPLOYMENT_EVENT",
        "stale_gets_one_refresh": stale_first["next_legal_action"] == REFRESH,
        "stale_after_refresh_gets_one_redeploy": stale_after_refresh["next_legal_action"] == FULL_REDEPLOY,
        "stale_after_both_stops": stale_exhausted["next_legal_action"] == "CLASSIFY_DEPLOYMENT_CONVERGENCE_FAILURE",
        "failed_gets_one_redeploy": failed_first["next_legal_action"] == FULL_REDEPLOY,
        "failed_after_redeploy_stops": failed_exhausted["next_legal_action"] == "CLASSIFY_DEPLOYMENT_CONVERGENCE_FAILURE",
        "exact_sha_proof_pending_verifies_once": exact_pending["next_legal_action"] == VERIFY_RUNTIME,
        "exact_sha_failed_proof_verifies_once": exact_failed["next_legal_action"] == VERIFY_RUNTIME,
        "exact_sha_after_verify_never_redeploys": exact_after_verify["next_legal_action"] == "CLASSIFY_RUNTIME_OR_VERIFIER_FAILURE",
        "exact_green_converges": converged["next_legal_action"] == "FREEZE_DEPLOYMENT_CONVERGENCE" and converged["converged"] is True,
        "product_patch_always_blocked": all(
            item["product_patch_allowed"] is False
            for item in [
                queued,
                stale_first,
                stale_after_refresh,
                stale_exhausted,
                exact_failed,
                exact_after_verify,
                converged,
            ]
        ),
        "mutation_authority_never_granted": converged["protections"]["mutation_authority_granted"] is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        "queued_waits",
        "building_waits",
        "activating_waits",
        "stale_gets_one_refresh",
        "stale_after_refresh_gets_one_redeploy",
        "stale_after_both_stops",
        "failed_gets_one_redeploy",
        "failed_after_redeploy_stops",
        "exact_sha_proof_pending_verifies_once",
        "exact_sha_failed_proof_verifies_once",
        "exact_sha_after_verify_never_redeploys",
        "exact_green_converges",
        "product_patch_always_blocked",
        "mutation_authority_never_granted",
    ]
    if not all(result[name] is True for name in required):
        raise DeploymentConvergenceFailure("deployment convergence self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"]:
        raise DeploymentConvergenceFailure("read-only deployment convergence safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V6_DEPLOYMENT_CONVERGENCE_CONTROLLER_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeploymentConvergenceFailure as exc:
        print(f"MONSTER_V6_DEPLOYMENT_CONVERGENCE_CONTROLLER_BLOCKED: {exc}")
        raise SystemExit(1)
