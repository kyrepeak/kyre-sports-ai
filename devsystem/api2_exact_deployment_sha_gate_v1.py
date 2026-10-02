"""API 2 Proof Architecture V1 Step 1 — Exact Deployment SHA Gate.

This is an additive pre-proof gate above the frozen MONSTER Deployment Truth
Control Plane V1. It performs no network calls and cannot mutate product state.

Expensive public/browser/product proof is legal only after exact deployment
identity parity is certified. Stale or incomplete deployment identity remains
DEPLOYMENT-owned and can never authorize a product patch.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem import deployment_truth_control_plane_v1 as deployment_truth

VERSION = "API2_PROOF_ARCHITECTURE_V1_STEP1_EXACT_DEPLOYMENT_SHA_GATE_V1"
FROZEN_PARENT_VERSION = "MONSTER_DEPLOYMENT_TRUTH_CONTROL_PLANE_V1"
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False
PATCH_PRODUCT_ALLOWED = False

_ACTIONS = {
    "DEPLOYMENT_PARITY": "PROCEED_PUBLIC_PRODUCT_PROOF",
    "STALE_DEPLOYMENT": "WAIT_FOR_EXACT_DEPLOYMENT",
    "IDENTITY_CONFLICT": "RECONCILE_DEPLOYMENT_IDENTITY",
    "INCOMPLETE": "COLLECT_DEPLOYMENT_IDENTITY",
    "PROOF_FAILED": "RESTORE_DEPLOYMENT_PROOF",
}


class ExactDeploymentGateFailure(RuntimeError):
    pass


def build_exact_deployment_gate(
    *,
    expected_sha: str,
    production_sha: str,
    build_id: str,
    deploy_id: str,
    health_sha: str,
    readiness_sha: str,
    ui_proof_sha: str,
    health_ok: bool,
    readiness_ok: bool,
    ui_proof_ok: bool,
) -> dict[str, Any]:
    if deployment_truth.VERSION != FROZEN_PARENT_VERSION:
        raise ExactDeploymentGateFailure(
            "frozen deployment-truth parent version drift"
        )

    truth = deployment_truth.build_deployment_truth(
        github_main_sha=expected_sha,
        production_sha=production_sha,
        build_id=build_id,
        deploy_id=deploy_id,
        health_sha=health_sha,
        readiness_sha=readiness_sha,
        ui_proof_sha=ui_proof_sha,
        health_ok=health_ok,
        readiness_ok=readiness_ok,
        ui_proof_ok=ui_proof_ok,
    )
    state = str(truth["state"])
    gate_open = state == "DEPLOYMENT_PARITY"
    result = {
        "version": VERSION,
        "state": state,
        "gate_open": gate_open,
        "public_product_proof_allowed": gate_open,
        "product_patch_allowed": False,
        "product_mutation_allowed": False,
        "owner": truth["owner"],
        "expected_sha": str(expected_sha or "").strip().lower(),
        "observed_production_sha": str(production_sha or "").strip().lower(),
        "next_legal_action": _ACTIONS[state],
        "deployment_truth_decision_id": truth["decision_id"],
        "deployment_truth_certified": bool(truth["certified"]),
        "protections": {
            "exact_sha_required_before_product_proof": True,
            "stale_deployment_never_becomes_product_failure": True,
            "identity_unavailable_fails_closed": True,
            "product_patch_blocked_until_parity": True,
            "network_calls": NETWORK_CALLS,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    return validate_exact_deployment_gate(result)


def validate_exact_deployment_gate(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("version") != VERSION:
        raise ExactDeploymentGateFailure("gate version drift")
    state = str(payload.get("state") or "")
    if state not in _ACTIONS:
        raise ExactDeploymentGateFailure("unsupported deployment state")
    expected_open = state == "DEPLOYMENT_PARITY"
    if bool(payload.get("gate_open")) is not expected_open:
        raise ExactDeploymentGateFailure("gate-open state drift")
    if bool(payload.get("public_product_proof_allowed")) is not expected_open:
        raise ExactDeploymentGateFailure("public-proof authority drift")
    if payload.get("product_patch_allowed") is not False:
        raise ExactDeploymentGateFailure("gate may not authorize product patch")
    if payload.get("product_mutation_allowed") is not False:
        raise ExactDeploymentGateFailure("gate may not authorize product mutation")
    if payload.get("owner") != "DEPLOYMENT":
        raise ExactDeploymentGateFailure("deployment ownership drift")
    if payload.get("next_legal_action") != _ACTIONS[state]:
        raise ExactDeploymentGateFailure("next legal action drift")
    if bool(payload.get("deployment_truth_certified")) is not expected_open:
        raise ExactDeploymentGateFailure("parent certification drift")
    expected_protections = {
        "exact_sha_required_before_product_proof": True,
        "stale_deployment_never_becomes_product_failure": True,
        "identity_unavailable_fails_closed": True,
        "product_patch_blocked_until_parity": True,
        "network_calls": False,
        "may_modify_product_runtime": False,
    }
    if payload.get("protections") != expected_protections:
        raise ExactDeploymentGateFailure("gate protections drift")
    if not str(payload.get("deployment_truth_decision_id") or "").startswith("DEPLOY-"):
        raise ExactDeploymentGateFailure("missing parent deployment decision")
    return dict(payload)


def require_exact_deployment_gate(**evidence: Any) -> dict[str, Any]:
    result = build_exact_deployment_gate(**evidence)
    if not result["gate_open"]:
        raise ExactDeploymentGateFailure(
            f"{result['state']}: {result['next_legal_action']}"
        )
    return result


def contract_self_test() -> dict[str, Any]:
    current = "a" * 40
    old = "b" * 40
    common = {
        "expected_sha": current,
        "build_id": "build-1",
        "deploy_id": "deploy-1",
        "health_ok": True,
        "readiness_ok": True,
        "ui_proof_ok": True,
    }
    parity = build_exact_deployment_gate(
        **common,
        production_sha=current,
        health_sha=current,
        readiness_sha=current,
        ui_proof_sha=current,
    )
    stale = build_exact_deployment_gate(
        **common,
        production_sha=old,
        health_sha=old,
        readiness_sha=old,
        ui_proof_sha=old,
    )
    incomplete = build_exact_deployment_gate(
        expected_sha=current,
        production_sha="",
        build_id="",
        deploy_id="",
        health_sha="",
        readiness_sha="",
        ui_proof_sha="",
        health_ok=False,
        readiness_ok=False,
        ui_proof_ok=False,
    )
    return {
        "status": "GREEN",
        "version": VERSION,
        "exact_parity_opens_gate": parity["gate_open"] is True,
        "stale_deployment_blocks_product_proof": (
            stale["gate_open"] is False
            and stale["state"] == "STALE_DEPLOYMENT"
            and stale["product_patch_allowed"] is False
        ),
        "missing_identity_fails_closed": (
            incomplete["gate_open"] is False
            and incomplete["state"] == "INCOMPLETE"
        ),
        "frozen_parent_version": deployment_truth.VERSION,
        "network_calls": NETWORK_CALLS,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


if __name__ == "__main__":
    result = contract_self_test()
    if not all(
        result[key] is True
        for key in (
            "exact_parity_opens_gate",
            "stale_deployment_blocks_product_proof",
            "missing_identity_fails_closed",
        )
    ):
        raise SystemExit("API2 exact-deployment SHA gate self-test failed")
    print("API2_PROOF_ARCHITECTURE_V1_STEP1_EXACT_DEPLOYMENT_SHA_GATE_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
