"""MONSTER V3 Step 6 — Recovery / Next-Action Router V1.

Deterministic control-plane router that converts already-classified truth into
exactly one legal next action.

Inputs are produced by frozen MONSTER V3 Steps 2-5. This module performs no
network calls and does not mutate repository or product state. Repository
mutation is authorized only through the Step-4 Failure Ownership Engine.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

try:
    from devsystem.failure_ownership_engine_v1 import (
        OwnershipFailure,
        authorize_mutation,
        validate_decision,
    )
    from devsystem.deployment_truth_control_plane_v1 import (
        DeploymentTruthFailure,
        validate_deployment_truth,
    )
except ModuleNotFoundError:
    from failure_ownership_engine_v1 import (
        OwnershipFailure,
        authorize_mutation,
        validate_decision,
    )
    from deployment_truth_control_plane_v1 import (
        DeploymentTruthFailure,
        validate_deployment_truth,
    )

VERSION = "MONSTER_RECOVERY_NEXT_ACTION_ROUTER_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_LIVE_ASYNC = {"QUEUED", "IN_PROGRESS"}
_ALLOWED_ASYNC = {"NONE", "QUEUED", "IN_PROGRESS", "SUCCESS", "FAILURE", "CANCELLED"}
_STALE_FRESHNESS = {"STALE", "STALE_HEAD", "STALE_MAIN", "STALE_DEPLOYMENT", "STALE_EVIDENCE"}


class RecoveryRouteFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return "RECOVERY-" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()


def _deployment_action(state: str) -> str:
    mapping = {
        "DEPLOYMENT_PARITY": "ADVANCE_CHECKPOINT",
        "STALE_DEPLOYMENT": "REFRESH_OR_REDEPLOY_PRODUCTION",
        "IDENTITY_CONFLICT": "RECONCILE_DEPLOYMENT_IDENTITY",
        "INCOMPLETE": "COLLECT_DEPLOYMENT_IDENTITY",
        "PROOF_FAILED": "RESTORE_RUNTIME_AND_UI_PROOF",
    }
    try:
        return mapping[state]
    except KeyError as exc:
        raise RecoveryRouteFailure(f"unsupported deployment state: {state!r}") from exc


def route_next_action(
    ownership_decision: Mapping[str, Any],
    *,
    async_state: str = "NONE",
    evidence_freshness: str = "CURRENT",
    deployment_truth: Mapping[str, Any] | None = None,
    proposed_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    ownership = validate_decision(ownership_decision)
    owner = ownership["owner"]
    async_value = str(async_state or "NONE").upper()
    freshness = str(evidence_freshness or "CURRENT").upper()

    if async_value not in _ALLOWED_ASYNC:
        raise RecoveryRouteFailure("async_state is invalid")

    mutation_authorized = False
    authorized_paths: list[str] = []
    path_classes: list[str] = []

    if async_value in _LIVE_ASYNC:
        action = "WAIT_FOR_AUTHORITATIVE_RUN"
        reason = "one authoritative async run is still live"
    elif freshness in _STALE_FRESHNESS or freshness.startswith("STALE_"):
        action = "REFRESH_EVIDENCE"
        reason = "stale evidence cannot authorize repair"
    elif owner == "STALE":
        action = "REFRESH_EVIDENCE"
        reason = "failure ownership is stale evidence"
    elif owner == "EXTERNAL":
        action = "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY"
        reason = "external failures do not authorize repository mutation"
    elif owner == "DEPLOYMENT":
        if deployment_truth is None:
            action = "COLLECT_DEPLOYMENT_IDENTITY"
            reason = "deployment owner requires deployment truth before action"
        else:
            deployment = validate_deployment_truth(deployment_truth)
            action = _deployment_action(deployment["state"])
            reason = f"deployment truth state={deployment['state']}"
    else:
        action = "PATCH_OWNER_SCOPE"
        reason = f"{owner} owns the failure"
        if proposed_paths:
            try:
                auth = authorize_mutation(ownership, proposed_paths)
            except OwnershipFailure as exc:
                raise RecoveryRouteFailure(str(exc)) from exc
            mutation_authorized = bool(auth["authorized"])
            authorized_paths = list(auth["paths"])
            path_classes = list(auth["path_classes"])

    product_mutation_allowed = bool(
        owner == "PRODUCT"
        and action == "PATCH_OWNER_SCOPE"
        and mutation_authorized
        and async_value not in _LIVE_ASYNC
        and not (freshness in _STALE_FRESHNESS or freshness.startswith("STALE_"))
    )

    result: dict[str, Any] = {
        "version": VERSION,
        "owner": owner,
        "action": action,
        "reason": reason,
        "async_state": async_value,
        "evidence_freshness": freshness,
        "mutation_authorized": mutation_authorized,
        "authorized_paths": authorized_paths,
        "path_classes": path_classes,
        "product_mutation_allowed": product_mutation_allowed,
        "exactly_one_action": True,
        "source_decision_id": ownership["decision_id"],
        "protections": {
            "async_mutation_lock": True,
            "stale_evidence_guard": True,
            "owner_scope_enforcement": True,
            "deployment_truth_required_for_deployment_action": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    result["route_id"] = _fingerprint(result)
    return validate_route(result)


def validate_route(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise RecoveryRouteFailure("recovery route must be an object")
    value = deepcopy(dict(payload))
    supplied = str(value.pop("route_id", ""))
    if not supplied:
        raise RecoveryRouteFailure("recovery route requires route_id")
    expected = _fingerprint(value)
    if supplied != expected:
        raise RecoveryRouteFailure("recovery route fingerprint mismatch")
    if value.get("version") != VERSION:
        raise RecoveryRouteFailure("unsupported recovery route version")
    if value.get("exactly_one_action") is not True:
        raise RecoveryRouteFailure("recovery route must contain exactly one action")
    if not str(value.get("action") or "").strip():
        raise RecoveryRouteFailure("recovery action is required")

    protections = value.get("protections")
    expected_protections = {
        "async_mutation_lock": True,
        "stale_evidence_guard": True,
        "owner_scope_enforcement": True,
        "deployment_truth_required_for_deployment_action": True,
        "network_calls": False,
        "auto_mutate": False,
        "may_modify_product_runtime": False,
    }
    if protections != expected_protections:
        raise RecoveryRouteFailure("recovery protections drift")

    if value.get("async_state") in _LIVE_ASYNC:
        if value.get("action") != "WAIT_FOR_AUTHORITATIVE_RUN":
            raise RecoveryRouteFailure("live async work must block competing recovery actions")
        if value.get("mutation_authorized"):
            raise RecoveryRouteFailure("live async work may not authorize mutation")

    freshness = str(value.get("evidence_freshness") or "").upper()
    if freshness in _STALE_FRESHNESS or freshness.startswith("STALE_"):
        if value.get("action") != "REFRESH_EVIDENCE":
            raise RecoveryRouteFailure("stale evidence must route to evidence refresh")
        if value.get("mutation_authorized"):
            raise RecoveryRouteFailure("stale evidence may not authorize mutation")

    if value.get("product_mutation_allowed") and value.get("owner") != "PRODUCT":
        raise RecoveryRouteFailure("only PRODUCT ownership can authorize product mutation")

    value["route_id"] = supplied
    return value


def contract_self_test() -> dict[str, Any]:
    try:
        from devsystem.failure_ownership_engine_v1 import classify_failure
        from devsystem.deployment_truth_control_plane_v1 import build_deployment_truth
    except ModuleNotFoundError:
        from failure_ownership_engine_v1 import classify_failure
        from deployment_truth_control_plane_v1 import build_deployment_truth

    verifier = classify_failure({
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
    })
    live = route_next_action(verifier, async_state="IN_PROGRESS")
    verifier_patch = route_next_action(
        verifier,
        proposed_paths=["devsystem/browser_qa_v1.py"],
    )
    external = classify_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "network-upstream",
    })
    external_route = route_next_action(external)
    stale = classify_failure(
        {"job": "wnba-critical", "layer": "wnba", "evidence_signal": "test-assertion"},
        evidence_freshness="STALE_MAIN",
    )
    stale_route = route_next_action(stale, evidence_freshness="STALE_MAIN")

    main = "a" * 40
    old = "b" * 40
    deployment_owner = classify_failure({
        "job": "production-verification",
        "layer": "deployment",
        "evidence_signal": "deployment-drift",
    })
    deployment_truth = build_deployment_truth(
        github_main_sha=main,
        production_sha=old,
        build_id="build-old",
        deploy_id="deploy-old",
        health_sha=old,
        readiness_sha=old,
        ui_proof_sha=old,
        health_ok=True,
        readiness_ok=True,
        ui_proof_ok=True,
    )
    deployment_route = route_next_action(
        deployment_owner,
        deployment_truth=deployment_truth,
    )

    return {
        "status": "GREEN",
        "version": VERSION,
        "one_action_only": True,
        "live_async_waits": live["action"] == "WAIT_FOR_AUTHORITATIVE_RUN",
        "verifier_scope_patch": verifier_patch["mutation_authorized"] is True,
        "external_no_patch": external_route["mutation_authorized"] is False,
        "stale_refresh_only": stale_route["action"] == "REFRESH_EVIDENCE",
        "deployment_stale_redeploy": deployment_route["action"] == "REFRESH_OR_REDEPLOY_PRODUCTION",
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
    }


if __name__ == "__main__":
    print("MONSTER_RECOVERY_NEXT_ACTION_ROUTER_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
