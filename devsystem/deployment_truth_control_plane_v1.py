"""MONSTER V3 Step 5 — Deployment Truth Control Plane V1.

Read-only, dependency-light deployment identity reconciliation.

The control plane binds current GitHub main identity to the observed public
runtime chain:

GitHub main SHA -> build ID -> deploy ID -> production SHA -> /health SHA
-> /health/ready SHA -> public UI proof SHA.

It performs no network calls and never mutates product/runtime state. Any
non-parity result remains DEPLOYMENT-owned and may not authorize a product patch.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping

try:
    from devsystem.failure_ownership_engine_v1 import classify_failure
except ModuleNotFoundError:  # direct `python devsystem/deployment_truth_control_plane_v1.py`
    from failure_ownership_engine_v1 import classify_failure

VERSION = "MONSTER_DEPLOYMENT_TRUTH_CONTROL_PLANE_V1"
OWNER = "DEPLOYMENT"
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False
PATCH_PRODUCT_ALLOWED = False

_STATES = {
    "DEPLOYMENT_PARITY",
    "STALE_DEPLOYMENT",
    "IDENTITY_CONFLICT",
    "INCOMPLETE",
    "PROOF_FAILED",
}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class DeploymentTruthFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    raw = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()
    return f"DEPLOY-{raw}"


def _sha(value: Any) -> str:
    return str(value or "").strip().lower()


def _valid_sha(value: str) -> bool:
    return bool(_SHA_RE.match(value))


def _owner_decision(state: str) -> dict[str, Any]:
    signal = "deployment-identity"
    diagnosis = "deployment parity certified"
    if state == "STALE_DEPLOYMENT":
        signal = "deployment-drift"
        diagnosis = "public deployment is internally consistent but behind GitHub main"
    elif state == "IDENTITY_CONFLICT":
        signal = "deployment-identity"
        diagnosis = "deployment identity sources disagree"
    elif state == "INCOMPLETE":
        signal = "deployment-identity"
        diagnosis = "deployment identity chain is incomplete"
    elif state == "PROOF_FAILED":
        signal = "hosting-drift"
        diagnosis = "deployment runtime or UI proof is not green"

    return classify_failure({
        "job": "deployment-truth-control-plane",
        "layer": "deployment",
        "evidence_signal": signal,
        "diagnosis": diagnosis,
        "confidence": "high",
    })


def _next_action(state: str) -> str:
    if state == "DEPLOYMENT_PARITY":
        return "FREEZE_DEPLOYMENT_TRUTH"
    if state == "STALE_DEPLOYMENT":
        return "REFRESH_OR_REDEPLOY_PRODUCTION"
    if state == "IDENTITY_CONFLICT":
        return "RECONCILE_DEPLOYMENT_IDENTITY"
    if state == "INCOMPLETE":
        return "COLLECT_DEPLOYMENT_IDENTITY"
    return "RESTORE_RUNTIME_AND_UI_PROOF"


def build_deployment_truth(
    *,
    github_main_sha: str,
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
    main = _sha(github_main_sha)
    production = _sha(production_sha)
    health = _sha(health_sha)
    readiness = _sha(readiness_sha)
    ui = _sha(ui_proof_sha)
    build = str(build_id or "").strip()
    deploy = str(deploy_id or "").strip()

    identities = {
        "github_main_sha": main,
        "production_sha": production,
        "build_id": build,
        "deploy_id": deploy,
        "health_sha": health,
        "readiness_sha": readiness,
        "ui_proof_sha": ui,
    }
    proof = {
        "health_ok": bool(health_ok),
        "readiness_ok": bool(readiness_ok),
        "ui_proof_ok": bool(ui_proof_ok),
    }

    sha_values = {
        "github_main_sha": main,
        "production_sha": production,
        "health_sha": health,
        "readiness_sha": readiness,
        "ui_proof_sha": ui,
    }
    invalid_identity = sorted(
        name for name, value in sha_values.items() if not _valid_sha(value)
    )
    missing_ids = sorted(
        name for name, value in (("build_id", build), ("deploy_id", deploy)) if not value
    )

    if invalid_identity or missing_ids:
        state = "INCOMPLETE"
        mismatch_fields = invalid_identity + missing_ids
    elif not all(proof.values()):
        state = "PROOF_FAILED"
        mismatch_fields = sorted(name for name, ok in proof.items() if not ok)
    else:
        public_chain = {production, health, readiness, ui}
        if len(public_chain) != 1:
            state = "IDENTITY_CONFLICT"
            mismatch_fields = sorted(
                name
                for name, value in (
                    ("production_sha", production),
                    ("health_sha", health),
                    ("readiness_sha", readiness),
                    ("ui_proof_sha", ui),
                )
                if value != production
            )
        elif production != main:
            state = "STALE_DEPLOYMENT"
            mismatch_fields = ["github_main_sha", "production_sha"]
        else:
            state = "DEPLOYMENT_PARITY"
            mismatch_fields = []

    ownership = _owner_decision(state)
    if ownership["owner"] != OWNER:
        raise DeploymentTruthFailure(
            f"failure ownership drift: expected {OWNER}, got {ownership['owner']}"
        )

    result: dict[str, Any] = {
        "version": VERSION,
        "state": state,
        "parity": state == "DEPLOYMENT_PARITY",
        "certified": state == "DEPLOYMENT_PARITY",
        "owner": OWNER,
        "product_mutation_allowed": False,
        "patch_product_allowed": PATCH_PRODUCT_ALLOWED,
        "next_legal_action": _next_action(state),
        "identities": identities,
        "proof": proof,
        "mismatch_fields": mismatch_fields,
        "ownership_decision_id": ownership["decision_id"],
        "protections": {
            "exact_main_to_public_identity_required": True,
            "build_id_required": True,
            "deploy_id_required": True,
            "health_ready_ui_chain_required": True,
            "deployment_owner_only": True,
            "product_patch_blocked": True,
            "network_calls": NETWORK_CALLS,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    result["decision_id"] = _fingerprint(result)
    return validate_deployment_truth(result)


def validate_deployment_truth(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DeploymentTruthFailure("deployment truth must be an object")

    value = deepcopy(dict(payload))
    supplied = str(value.pop("decision_id", ""))
    if not supplied:
        raise DeploymentTruthFailure("deployment truth requires decision_id")
    expected = _fingerprint(value)
    if supplied != expected:
        raise DeploymentTruthFailure("deployment truth fingerprint mismatch")

    if value.get("version") != VERSION:
        raise DeploymentTruthFailure("unsupported deployment truth version")

    state = str(value.get("state") or "")
    if state not in _STATES:
        raise DeploymentTruthFailure("deployment truth state is invalid")
    if value.get("owner") != OWNER:
        raise DeploymentTruthFailure("deployment truth owner drift")
    if bool(value.get("parity")) is not (state == "DEPLOYMENT_PARITY"):
        raise DeploymentTruthFailure("deployment parity flag drift")
    if bool(value.get("certified")) is not (state == "DEPLOYMENT_PARITY"):
        raise DeploymentTruthFailure("deployment certification flag drift")
    if value.get("product_mutation_allowed") is not False:
        raise DeploymentTruthFailure("deployment truth may not authorize product mutation")
    if value.get("patch_product_allowed") is not False:
        raise DeploymentTruthFailure("deployment truth may not authorize product patch")

    expected_action = _next_action(state)
    if value.get("next_legal_action") != expected_action:
        raise DeploymentTruthFailure("deployment next action drift")

    protections = value.get("protections")
    expected_protections = {
        "exact_main_to_public_identity_required": True,
        "build_id_required": True,
        "deploy_id_required": True,
        "health_ready_ui_chain_required": True,
        "deployment_owner_only": True,
        "product_patch_blocked": True,
        "network_calls": False,
        "may_modify_product_runtime": False,
    }
    if protections != expected_protections:
        raise DeploymentTruthFailure("deployment protections drift")

    value["decision_id"] = supplied
    return value


def contract_self_test() -> dict[str, Any]:
    main = "a" * 40
    old = "b" * 40

    parity = build_deployment_truth(
        github_main_sha=main,
        production_sha=main,
        build_id="build-green",
        deploy_id="deploy-green",
        health_sha=main,
        readiness_sha=main,
        ui_proof_sha=main,
        health_ok=True,
        readiness_ok=True,
        ui_proof_ok=True,
    )
    stale = build_deployment_truth(
        github_main_sha=main,
        production_sha=old,
        build_id="build-stale",
        deploy_id="deploy-stale",
        health_sha=old,
        readiness_sha=old,
        ui_proof_sha=old,
        health_ok=True,
        readiness_ok=True,
        ui_proof_ok=True,
    )
    incomplete = build_deployment_truth(
        github_main_sha=main,
        production_sha=main,
        build_id="",
        deploy_id="deploy-incomplete",
        health_sha=main,
        readiness_sha=main,
        ui_proof_sha=main,
        health_ok=True,
        readiness_ok=True,
        ui_proof_ok=True,
    )
    proof_failed = build_deployment_truth(
        github_main_sha=main,
        production_sha=main,
        build_id="build-proof",
        deploy_id="deploy-proof",
        health_sha=main,
        readiness_sha=main,
        ui_proof_sha=main,
        health_ok=True,
        readiness_ok=True,
        ui_proof_ok=False,
    )

    return {
        "status": "GREEN",
        "version": VERSION,
        "exact_main_sha_parity": parity["state"] == "DEPLOYMENT_PARITY",
        "stale_deployment_classification": stale["state"] == "STALE_DEPLOYMENT",
        "build_deploy_identity_required": incomplete["state"] == "INCOMPLETE",
        "health_ready_ui_chain_required": proof_failed["state"] == "PROOF_FAILED",
        "product_patch_blocked_on_deployment_failure": (
            stale["patch_product_allowed"] is False
            and stale["product_mutation_allowed"] is False
            and stale["owner"] == OWNER
        ),
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
    }


if __name__ == "__main__":
    print("MONSTER_DEPLOYMENT_TRUTH_CONTROL_PLANE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
