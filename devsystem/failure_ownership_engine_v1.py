"""MONSTER V3 Step 4 — Failure Ownership Engine V1.

Dependency-light fail-closed control-plane classification. Every failure is
assigned to exactly one owner before repository mutation is considered:
PRODUCT, VERIFIER, CI, DEPLOYMENT, EXTERNAL, or STALE.

This module performs no network calls and never mutates the repository itself.
It only classifies evidence and authorizes a proposed path set.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_FAILURE_OWNERSHIP_ENGINE_V1"
OWNERS = frozenset({"PRODUCT", "VERIFIER", "CI", "DEPLOYMENT", "EXTERNAL", "STALE"})
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_STALE_FRESHNESS = {"STALE", "STALE_HEAD", "STALE_MAIN", "STALE_DEPLOYMENT", "STALE_EVIDENCE"}
_PRODUCT_LAYERS = {
    "cfb", "mlb", "wnba", "nfl", "nba", "nhl", "soccer", "shared-core", "product"
}
_VERIFIER_LAYERS = {
    "ui-browser", "devsystem-contract", "regression-shield",
    "devsystem-final-gate", "verifier", "control-plane"
}
_CI_LAYERS = {"workflow-control", "change-classifier", "ci", "ci-infra"}
_DEPLOYMENT_LAYERS = {"production", "deployment", "hosting"}

class OwnershipFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return "OWNER-" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()


def _decision(
    owner: str,
    *,
    failure: Mapping[str, Any],
    evidence_freshness: str,
    classification_basis: str,
) -> dict[str, Any]:
    owner = str(owner).upper()
    if owner not in OWNERS:
        raise OwnershipFailure(f"unsupported failure owner: {owner!r}")

    if owner == "STALE":
        patch_allowed = False
        next_action = "REFRESH_EVIDENCE"
    elif owner == "EXTERNAL":
        patch_allowed = False
        next_action = "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY"
    else:
        patch_allowed = True
        next_action = "PATCH_OWNER_SCOPE"

    body: dict[str, Any] = {
        "version": VERSION,
        "owner": owner,
        "failure_class": owner,
        "classification_basis": classification_basis,
        "patch_allowed": patch_allowed,
        "product_mutation_allowed": owner == "PRODUCT",
        "next_legal_action": next_action,
        "source": {
            "job": str(failure.get("job") or ""),
            "layer": str(failure.get("layer") or ""),
            "evidence_signal": str(failure.get("evidence_signal") or ""),
            "diagnosis": str(failure.get("diagnosis") or ""),
            "confidence": str(failure.get("confidence") or ""),
            "evidence_freshness": str(evidence_freshness or "CURRENT").upper(),
        },
        "protections": {
            "classify_before_patch": True,
            "owner_scope_enforcement": True,
            "fail_closed_on_ambiguity": True,
            "network_calls": NETWORK_CALLS,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    body["decision_id"] = _fingerprint(body)
    return validate_decision(body)


def classify_failure(
    failure: Mapping[str, Any],
    *,
    evidence_freshness: str = "CURRENT",
) -> dict[str, Any]:
    if not isinstance(failure, Mapping):
        raise OwnershipFailure("failure evidence must be an object")

    freshness = str(evidence_freshness or "CURRENT").upper()
    layer = str(failure.get("layer") or "").strip().lower()
    signal = str(failure.get("evidence_signal") or "").strip().lower()
    job = str(failure.get("job") or "").strip().lower()

    # Step 3 truth has absolute precedence. Stale proof can never authorize a patch.
    if freshness in _STALE_FRESHNESS or freshness.startswith("STALE_"):
        return _decision(
            "STALE",
            failure=failure,
            evidence_freshness=freshness,
            classification_basis="STALE_EVIDENCE_PRECEDENCE",
        )

    # External/upstream evidence outranks the lane in which it surfaced.
    if signal == "network-upstream":
        return _decision(
            "EXTERNAL",
            failure=failure,
            evidence_freshness=freshness,
            classification_basis="EXTERNAL_EVIDENCE_SIGNATURE",
        )

    if (
        layer in _DEPLOYMENT_LAYERS
        or signal in {"deployment-identity", "deployment-drift", "hosting-drift"}
        or "production-verification" in job
        or job.startswith("deploy")
    ):
        return _decision(
            "DEPLOYMENT",
            failure=failure,
            evidence_freshness=freshness,
            classification_basis="DEPLOYMENT_SURFACE",
        )

    if (
        layer in _CI_LAYERS
        or signal == "cache-dependency"
        or job in {"classify", "workflow-hygiene"}
    ):
        return _decision(
            "CI",
            failure=failure,
            evidence_freshness=freshness,
            classification_basis="CI_CONTROL_SURFACE",
        )

    if (
        layer in _VERIFIER_LAYERS
        or signal == "browser-selector-race"
        or job in {"permanent-contract", "regression-shield", "devsystem-final-gate", "browser-qa"}
    ):
        return _decision(
            "VERIFIER",
            failure=failure,
            evidence_freshness=freshness,
            classification_basis="VERIFIER_CONTROL_SURFACE",
        )

    if layer in _PRODUCT_LAYERS:
        return _decision(
            "PRODUCT",
            failure=failure,
            evidence_freshness=freshness,
            classification_basis="PRODUCT_DOMAIN_SURFACE",
        )

    # Incomplete/ambiguous evidence may never grant product mutation.
    return _decision(
        "VERIFIER",
        failure=failure,
        evidence_freshness=freshness,
        classification_basis="INSUFFICIENT_EVIDENCE_FAIL_SAFE",
    )


def validate_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise OwnershipFailure("ownership decision must be an object")
    value = deepcopy(dict(payload))
    supplied = str(value.pop("decision_id", ""))
    if not supplied:
        raise OwnershipFailure("ownership decision requires decision_id")
    if value.get("version") != VERSION:
        raise OwnershipFailure("unsupported ownership decision version")

    owner = str(value.get("owner") or "").upper()
    if owner not in OWNERS:
        raise OwnershipFailure("ownership decision has invalid owner")
    if str(value.get("failure_class") or "").upper() != owner:
        raise OwnershipFailure("failure_class must equal owner")

    expected_patch = owner not in {"EXTERNAL", "STALE"}
    if bool(value.get("patch_allowed")) is not expected_patch:
        raise OwnershipFailure("patch permission drift")
    if bool(value.get("product_mutation_allowed")) is not (owner == "PRODUCT"):
        raise OwnershipFailure("product mutation permission drift")

    expected_action = (
        "REFRESH_EVIDENCE" if owner == "STALE"
        else "OBSERVE_EXTERNAL_OR_CONTROLLED_RETRY" if owner == "EXTERNAL"
        else "PATCH_OWNER_SCOPE"
    )
    if value.get("next_legal_action") != expected_action:
        raise OwnershipFailure("next legal action drift")

    protections = value.get("protections")
    expected_protections = {
        "classify_before_patch": True,
        "owner_scope_enforcement": True,
        "fail_closed_on_ambiguity": True,
        "network_calls": False,
        "may_modify_product_runtime": False,
    }
    if protections != expected_protections:
        raise OwnershipFailure("ownership protections drift")

    expected = _fingerprint(value)
    if supplied != expected:
        raise OwnershipFailure("ownership decision fingerprint mismatch")
    value["decision_id"] = supplied
    return value


def classify_path(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/")
    lower = value.lower()
    if not value:
        return "UNKNOWN"

    if lower.startswith("tests/"):
        name = lower.rsplit("/", 1)[-1]
        if name.startswith((
            "test_cfb_", "test_nfl_", "test_wnba_", "test_mlb_",
            "test_nba_", "test_nhl_", "test_soccer_", "test_sports_api_",
        )):
            return "PRODUCT"
        return "VERIFIER"

    if lower == "app.py" or lower.startswith("sports_api/") or lower.startswith((
        "cfb_", "nfl_", "wnba_", "mlb_", "nba_", "nhl_", "soccer_",
    )):
        return "PRODUCT"

    if lower.startswith("devsystem/deployment_markers/") or lower.startswith("devsystem/production_"):
        return "DEPLOYMENT"
    if lower in {"render.yaml", "render.yml", "procfile"}:
        return "DEPLOYMENT"

    if lower.startswith(".github/workflows/"):
        if any(token in lower for token in ("production", "deploy", "render", "streamlit")):
            return "DEPLOYMENT"
        return "CI"

    if lower in {"requirements.txt", "pyproject.toml", "requirements.lock"}:
        return "CI"
    if lower.startswith("devsystem/") and any(
        token in lower
        for token in ("action_ledger", "workflow_", "change_classifier", "root_requirements")
    ):
        return "CI"
    if lower.startswith("devsystem/"):
        return "VERIFIER"

    return "UNKNOWN"


def authorize_mutation(
    decision: Mapping[str, Any],
    paths: Sequence[str],
) -> dict[str, Any]:
    verified = validate_decision(decision)
    owner = verified["owner"]
    if not verified["patch_allowed"]:
        raise OwnershipFailure(f"owner {owner} does not permit repository mutation")
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)) or not paths:
        raise OwnershipFailure("mutation authorization requires at least one path")

    normalized = [str(path).strip() for path in paths]
    classes = [classify_path(path) for path in normalized]
    for path, path_class in zip(normalized, classes):
        if path_class != owner:
            raise OwnershipFailure(f"owner {owner} cannot mutate {path_class} path: {path}")

    return {
        "status": "GREEN",
        "authorized": True,
        "owner": owner,
        "decision_id": verified["decision_id"],
        "paths": normalized,
        "path_classes": classes,
    }


def contract_self_test() -> dict[str, Any]:
    product = classify_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "test-assertion",
        "diagnosis": "product invariant mismatch",
    })
    verifier = classify_failure({
        "job": "browser-qa",
        "layer": "ui-browser",
        "evidence_signal": "browser-selector-race",
    })
    ci = classify_failure({
        "job": "workflow-hygiene",
        "layer": "workflow-control",
        "evidence_signal": "cache-dependency",
    })
    deployment = classify_failure({
        "job": "production-verification",
        "layer": "production",
        "evidence_signal": "deployment-identity",
    })
    external = classify_failure({
        "job": "wnba-critical",
        "layer": "wnba",
        "evidence_signal": "network-upstream",
    })
    stale = classify_failure(
        {"job": "wnba-critical", "layer": "wnba", "evidence_signal": "test-assertion"},
        evidence_freshness="STALE_HEAD",
    )

    observed = {x["owner"] for x in (product, verifier, ci, deployment, external, stale)}
    if observed != set(OWNERS):
        raise OwnershipFailure("six-owner coverage self-test failed")

    authorize_mutation(
        verifier,
        ["tests/test_devsystem_browser_qa_v1.py", "devsystem/browser_qa_v1.py"],
    )

    verifier_blocked = False
    try:
        authorize_mutation(verifier, ["app.py"])
    except OwnershipFailure:
        verifier_blocked = True
    if not verifier_blocked:
        raise OwnershipFailure("verifier product-mutation guard self-test failed")

    stale_blocked = False
    try:
        authorize_mutation(stale, ["devsystem/evidence_truth_ledger_v1.py"])
    except OwnershipFailure:
        stale_blocked = True
    if not stale_blocked:
        raise OwnershipFailure("stale mutation guard self-test failed")

    external_blocked = False
    try:
        authorize_mutation(external, ["tests/test_devsystem_browser_qa_v1.py"])
    except OwnershipFailure:
        external_blocked = True
    if not external_blocked:
        raise OwnershipFailure("external mutation guard self-test failed")

    return {
        "status": "GREEN",
        "version": VERSION,
        "owners": sorted(OWNERS),
        "classify_before_patch": True,
        "owner_scope_enforcement": True,
        "verifier_product_mutation_blocked": verifier_blocked,
        "stale_patch_blocked": stale_blocked,
        "external_patch_blocked": external_blocked,
        "fail_closed_on_ambiguity": True,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
    }


if __name__ == "__main__":
    print("MONSTER_FAILURE_OWNERSHIP_ENGINE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
