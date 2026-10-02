"""API2 Proof Architecture V1 Step 5 — Failure Domain Separation.

This adapter reuses the frozen MONSTER Failure Ownership Engine V1 and adds the
API2 repair-domain boundary. A failed proof must resolve to exactly one domain
before any mutation or retry is legal.

The adapter is dependency-light, performs no network calls, and never mutates
the repository itself.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from devsystem.failure_ownership_engine_v1 import (
    OwnershipFailure,
    classify_failure,
    classify_path,
)

VERSION = "API2_PROOF_ARCHITECTURE_V1_STEP5_FAILURE_DOMAIN_SEPARATION_V1"
DOMAINS = frozenset({
    "PRODUCT",
    "CONTROL_PLANE",
    "DEPLOYMENT",
    "UPSTREAM_DEPENDENCY",
    "PROOF_VERIFIER",
    "EXTERNAL",
})
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_CONTROL_PLANE_SIGNALS = {
    "frozen-registry-mismatch",
    "action-ledger-contract",
    "scope-lease-conflict",
    "branch-protection",
    "workflow-contract",
    "synthetic-merge-identity",
    "control-plane-state",
}
_CONTROL_PLANE_JOBS = {
    "classify",
    "workflow-hygiene",
    "permanent-contract",
    "devsystem-final-gate",
    "terminal-proof-receipt",
}
_PROOF_VERIFIER_SIGNALS = {
    "browser-selector-race",
    "verifier-entrypoint",
    "proof-contract",
    "assertion-shape",
}


class FailureDomainError(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return "API2-DOMAIN-" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()


def _upstream_blocked(upstream_gate: Mapping[str, Any] | None) -> bool:
    if not isinstance(upstream_gate, Mapping):
        return False
    decision = str(upstream_gate.get("decision") or "").strip().upper()
    status = str(upstream_gate.get("status") or "").strip().upper()
    allowed = upstream_gate.get("downstream_proof_allowed")
    return decision == "UPSTREAM_BLOCKED" or status == "UPSTREAM_BLOCKED" or allowed is False


def _domain_from_core(
    *,
    failure: Mapping[str, Any],
    core: Mapping[str, Any],
) -> tuple[str, str]:
    owner = str(core.get("owner") or "").upper()
    layer = str(failure.get("layer") or "").strip().lower()
    signal = str(failure.get("evidence_signal") or "").strip().lower()
    job = str(failure.get("job") or "").strip().lower()

    if owner == "PRODUCT":
        return "PRODUCT", "MONSTER_PRODUCT_OWNER"
    if owner == "DEPLOYMENT":
        return "DEPLOYMENT", "MONSTER_DEPLOYMENT_OWNER"
    if owner == "EXTERNAL":
        return "EXTERNAL", "MONSTER_EXTERNAL_OWNER"
    if owner == "STALE":
        return "CONTROL_PLANE", "STALE_EVIDENCE_CONTROL_PLANE"
    if owner == "CI":
        return "CONTROL_PLANE", "MONSTER_CI_CONTROL_PLANE_OWNER"
    if owner == "VERIFIER":
        if (
            layer == "control-plane"
            or signal in _CONTROL_PLANE_SIGNALS
            or (job in _CONTROL_PLANE_JOBS and signal not in _PROOF_VERIFIER_SIGNALS)
        ):
            return "CONTROL_PLANE", "CONTROL_PLANE_SIGNATURE"
        return "PROOF_VERIFIER", "MONSTER_VERIFIER_OWNER"
    raise FailureDomainError(f"unsupported MONSTER owner: {owner!r}")


def classify_api2_failure(
    failure: Mapping[str, Any],
    *,
    evidence_freshness: str = "CURRENT",
    upstream_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(failure, Mapping):
        raise FailureDomainError("failure evidence must be an object")

    if _upstream_blocked(upstream_gate):
        owner = str((upstream_gate or {}).get("upstream_owner") or "UNKNOWN_UPSTREAM")
        body: dict[str, Any] = {
            "version": VERSION,
            "domain": "UPSTREAM_DEPENDENCY",
            "raw_owner": "UPSTREAM_DEPENDENCY",
            "classification_basis": "UPSTREAM_BLOCKER_SHORT_CIRCUIT",
            "patch_allowed": False,
            "product_mutation_allowed": False,
            "next_legal_action": "ROUTE_TO_UPSTREAM_OWNER",
            "patch_scope_classes": [],
            "upstream_owner": owner,
            "source": {
                "job": str(failure.get("job") or ""),
                "layer": str(failure.get("layer") or ""),
                "evidence_signal": str(failure.get("evidence_signal") or ""),
                "diagnosis": str(failure.get("diagnosis") or ""),
                "evidence_freshness": str(evidence_freshness or "CURRENT").upper(),
            },
            "protections": {
                "classify_before_patch": True,
                "single_failure_domain": True,
                "owner_scope_enforcement": True,
                "downstream_patch_for_upstream_blocked": False,
                "network_calls": NETWORK_CALLS,
                "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            },
        }
        body["decision_id"] = _fingerprint(body)
        return validate_domain_decision(body)

    core = classify_failure(failure, evidence_freshness=evidence_freshness)
    domain, basis = _domain_from_core(failure=failure, core=core)

    if domain == "PRODUCT":
        patch_allowed = bool(core["patch_allowed"])
        product_mutation_allowed = bool(core["product_mutation_allowed"])
        action = "PATCH_PRODUCT_OWNER"
        scope = ["PRODUCT"]
    elif domain == "CONTROL_PLANE":
        patch_allowed = bool(core["patch_allowed"]) and str(core["owner"]) != "STALE"
        product_mutation_allowed = False
        action = "REFRESH_EVIDENCE" if str(core["owner"]) == "STALE" else "PATCH_CONTROL_PLANE_OWNER"
        scope = ["CI", "VERIFIER"] if patch_allowed else []
    elif domain == "DEPLOYMENT":
        patch_allowed = bool(core["patch_allowed"])
        product_mutation_allowed = False
        action = "PATCH_OR_REFRESH_DEPLOYMENT_OWNER"
        scope = ["DEPLOYMENT"] if patch_allowed else []
    elif domain == "PROOF_VERIFIER":
        patch_allowed = bool(core["patch_allowed"])
        product_mutation_allowed = False
        action = "PATCH_PROOF_VERIFIER_OWNER"
        scope = ["VERIFIER"] if patch_allowed else []
    elif domain == "EXTERNAL":
        patch_allowed = False
        product_mutation_allowed = False
        action = "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY"
        scope = []
    else:
        raise FailureDomainError(f"unhandled API2 domain: {domain}")

    body = {
        "version": VERSION,
        "domain": domain,
        "raw_owner": str(core["owner"]),
        "classification_basis": basis,
        "patch_allowed": patch_allowed,
        "product_mutation_allowed": product_mutation_allowed,
        "next_legal_action": action,
        "patch_scope_classes": scope,
        "upstream_owner": None,
        "source": deepcopy(dict(core["source"])),
        "protections": {
            "classify_before_patch": True,
            "single_failure_domain": True,
            "owner_scope_enforcement": True,
            "downstream_patch_for_upstream_blocked": False,
            "network_calls": NETWORK_CALLS,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    body["decision_id"] = _fingerprint(body)
    return validate_domain_decision(body)


def validate_domain_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise FailureDomainError("domain decision must be an object")
    value = deepcopy(dict(payload))
    supplied = str(value.pop("decision_id", ""))
    if not supplied:
        raise FailureDomainError("domain decision requires decision_id")
    expected = _fingerprint(value)
    if supplied != expected:
        raise FailureDomainError("domain decision fingerprint mismatch")
    if value.get("version") != VERSION:
        raise FailureDomainError("unsupported domain decision version")

    domain = str(value.get("domain") or "")
    if domain not in DOMAINS:
        raise FailureDomainError(f"invalid failure domain: {domain!r}")
    if bool(value.get("product_mutation_allowed")) is not (domain == "PRODUCT"):
        raise FailureDomainError("product mutation permission drift")
    if domain in {"UPSTREAM_DEPENDENCY", "EXTERNAL"} and value.get("patch_allowed") is not False:
        raise FailureDomainError(f"{domain} may not authorize mutation")
    if domain == "UPSTREAM_DEPENDENCY" and value.get("next_legal_action") != "ROUTE_TO_UPSTREAM_OWNER":
        raise FailureDomainError("upstream blocker must route to upstream owner")

    protections = value.get("protections")
    expected_protections = {
        "classify_before_patch": True,
        "single_failure_domain": True,
        "owner_scope_enforcement": True,
        "downstream_patch_for_upstream_blocked": False,
        "network_calls": False,
        "may_modify_product_runtime": False,
    }
    if protections != expected_protections:
        raise FailureDomainError("domain protections drift")

    value["decision_id"] = supplied
    return value


def authorize_domain_mutation(
    decision: Mapping[str, Any],
    paths: Sequence[str],
) -> dict[str, Any]:
    verified = validate_domain_decision(decision)
    domain = str(verified["domain"])
    if not verified["patch_allowed"]:
        raise FailureDomainError(f"domain {domain} does not permit repository mutation")
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)) or not paths:
        raise FailureDomainError("mutation authorization requires paths")

    normalized = [str(path).strip() for path in paths]
    classes = [classify_path(path) for path in normalized]
    allowed = set(str(x) for x in verified.get("patch_scope_classes") or [])
    for path, path_class in zip(normalized, classes):
        if path_class not in allowed:
            raise FailureDomainError(
                f"domain {domain} cannot mutate {path_class} path: {path}"
            )
    return {
        "status": "GREEN",
        "authorized": True,
        "domain": domain,
        "decision_id": verified["decision_id"],
        "paths": normalized,
        "path_classes": classes,
    }


def contract_self_test() -> dict[str, Any]:
    product = classify_api2_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "test-assertion",
        "diagnosis": "product invariant mismatch",
    })
    control = classify_api2_failure({
        "job": "permanent-contract",
        "layer": "control-plane",
        "evidence_signal": "frozen-registry-mismatch",
        "diagnosis": "authoritative registry snapshot did not contain exact thaw",
    })
    deployment = classify_api2_failure({
        "job": "production-verification",
        "layer": "production",
        "evidence_signal": "deployment-identity",
        "diagnosis": "deployed SHA differs from merged main",
    })
    verifier = classify_api2_failure({
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
        "diagnosis": "selector readiness mismatch",
    })
    external = classify_api2_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "network-upstream",
        "diagnosis": "provider unavailable",
    })
    stale = classify_api2_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "test-assertion",
    }, evidence_freshness="STALE_HEAD")
    upstream = classify_api2_failure(
        {
            "job": "wnba-step3-public",
            "layer": "wnba",
            "evidence_signal": "no-tappable-players",
            "diagnosis": "downstream cannot traverse Page 2",
        },
        upstream_gate={
            "status": "UPSTREAM_BLOCKED",
            "decision": "UPSTREAM_BLOCKED",
            "downstream_proof_allowed": False,
            "upstream_owner": "wnba-pra-repair-v1-step2-team-identity",
        },
    )

    observed = {x["domain"] for x in (product, control, deployment, verifier, external, upstream)}
    if observed != DOMAINS:
        raise FailureDomainError(
            f"failure-domain coverage drift: expected={sorted(DOMAINS)} actual={sorted(observed)}"
        )
    if stale["domain"] != "CONTROL_PLANE" or stale["patch_allowed"] is not False:
        raise FailureDomainError("stale evidence must be non-mutating control-plane work")

    authorize_domain_mutation(control, ["devsystem/example_control_plane.py"])
    authorize_domain_mutation(verifier, ["tests/test_devsystem_browser_qa_v1.py"])
    authorize_domain_mutation(product, ["app.py"])

    wrong_scope_blocked = False
    try:
        authorize_domain_mutation(control, ["app.py"])
    except FailureDomainError:
        wrong_scope_blocked = True
    if not wrong_scope_blocked:
        raise FailureDomainError("control-plane owner was able to mutate product code")

    upstream_patch_blocked = False
    try:
        authorize_domain_mutation(upstream, ["devsystem/example_control_plane.py"])
    except FailureDomainError:
        upstream_patch_blocked = True
    if not upstream_patch_blocked:
        raise FailureDomainError("upstream blocker was able to mutate downstream code")

    return {
        "status": "GREEN",
        "version": VERSION,
        "domains": sorted(DOMAINS),
        "classify_before_patch": True,
        "single_failure_domain": True,
        "control_plane_product_mutation_blocked": wrong_scope_blocked,
        "upstream_downstream_mutation_blocked": upstream_patch_blocked,
        "stale_patch_blocked": stale["patch_allowed"] is False,
        "network_calls": NETWORK_CALLS,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


if __name__ == "__main__":
    print("API2_PROOF_ARCHITECTURE_V1_STEP5_FAILURE_DOMAIN_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
