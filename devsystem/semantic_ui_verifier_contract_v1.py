"""MONSTER V6 Step 5 - Semantic UI Verifier Contract V1.

Dependency-light UI verification semantics.

The contract verifies user-visible meaning and behavior instead of framework
implementation details. It performs no browser/network work itself; browser
adapters may normalize observations into this stable contract.

Key rule: internal DOM shape is diagnostic context, never acceptance truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_V6_SEMANTIC_UI_VERIFIER_CONTRACT_V1"
CASES_VERSION = "MONSTER_V6_SEMANTIC_UI_VERIFIER_CASES_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_ALLOWED_KINDS = {"interactive", "text", "route"}


class SemanticUIVerificationFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, prefix: str) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24].upper()


def selector_fragility(selector: str) -> list[str]:
    value = str(selector or "").strip()
    reasons: list[str] = []
    if not value:
        return ["EMPTY_SELECTOR"]
    if "data-baseweb" in value.casefold():
        reasons.append("FRAMEWORK_INTERNAL_ATTRIBUTE")
    if re.search(r":nth-(?:child|of-type)\s*\(", value, re.IGNORECASE):
        reasons.append("POSITIONAL_DESCENDANT")
    if re.search(r"(?:^|[\s>+~])\.[a-z0-9_-]*css-[a-z0-9_-]+", value, re.IGNORECASE):
        reasons.append("GENERATED_STYLE_CLASS")
    if re.search(r"(?:^|[\s>+~])\.[a-z][a-z0-9_-]*\.[a-z][a-z0-9_-]*\s*>", value, re.IGNORECASE):
        reasons.append("DEEP_CLASS_DESCENDANT_CHAIN")
    return sorted(set(reasons))


def validate_locator_strategy(strategy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(strategy, Mapping):
        raise SemanticUIVerificationFailure("locator strategy must be an object")
    kind = str(strategy.get("kind") or "").strip().lower()
    if kind not in {"role_name", "label", "visible_text", "stable_wrapper"}:
        raise SemanticUIVerificationFailure("locator strategy must use durable semantics")
    selector = str(strategy.get("selector") or "").strip()
    if selector:
        reasons = selector_fragility(selector)
        if reasons:
            raise SemanticUIVerificationFailure(
                "brittle selector is forbidden: " + ",".join(reasons)
            )
    if kind == "role_name":
        if not str(strategy.get("role") or "").strip() or not str(strategy.get("accessible_name") or "").strip():
            raise SemanticUIVerificationFailure("role_name locator requires role and accessible_name")
    elif kind == "label":
        if not str(strategy.get("label") or "").strip():
            raise SemanticUIVerificationFailure("label locator requires label")
    elif kind == "visible_text":
        if not str(strategy.get("text") or "").strip():
            raise SemanticUIVerificationFailure("visible_text locator requires text")
    elif kind == "stable_wrapper":
        if not str(strategy.get("semantic_key") or "").strip():
            raise SemanticUIVerificationFailure("stable_wrapper locator requires semantic_key")
    return deepcopy(dict(strategy))


def _normalize_requirement(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise SemanticUIVerificationFailure("requirement must be an object")
    req = deepcopy(dict(raw))
    capability_id = str(req.get("capability_id") or "").strip()
    kind = str(req.get("kind") or "").strip().lower()
    if not capability_id:
        raise SemanticUIVerificationFailure("requirement capability_id is required")
    if kind not in _ALLOWED_KINDS:
        raise SemanticUIVerificationFailure(f"unsupported requirement kind: {kind!r}")
    req["capability_id"] = capability_id
    req["kind"] = kind

    if kind == "interactive":
        role = str(req.get("role") or "").strip().lower()
        name = str(req.get("accessible_name") or "").strip()
        label = str(req.get("label") or "").strip()
        if not role:
            raise SemanticUIVerificationFailure("interactive requirement requires role")
        if not name and not label:
            raise SemanticUIVerificationFailure("interactive requirement requires accessible_name or label")
        req["role"] = role
        if name:
            req["accessible_name"] = name
        if label:
            req["label"] = label
        if "min_wrapper_height" in req:
            height = float(req["min_wrapper_height"])
            if height <= 0:
                raise SemanticUIVerificationFailure("min_wrapper_height must be positive")
            req["min_wrapper_height"] = height

    elif kind == "text":
        text = str(req.get("text") or "").strip()
        if not text:
            raise SemanticUIVerificationFailure("text requirement requires visible text")
        req["text"] = text

    elif kind == "route":
        route = str(req.get("route") or "").strip()
        if not route:
            raise SemanticUIVerificationFailure("route requirement requires route")
        req["route"] = route

    return req


def _is_positive(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _matches(req: Mapping[str, Any], obs: Mapping[str, Any]) -> bool:
    kind = req["kind"]
    if kind == "interactive":
        if str(obs.get("role") or "").strip().lower() != req["role"]:
            return False
        expected_name = str(req.get("accessible_name") or "")
        expected_label = str(req.get("label") or "")
        actual_name = str(obs.get("accessible_name") or "")
        actual_label = str(obs.get("label") or "")
        if expected_name and actual_name.casefold() != expected_name.casefold():
            return False
        if expected_label and actual_label.casefold() != expected_label.casefold():
            return False
        return True
    if kind == "text":
        return (
            str(obs.get("kind") or "").strip().lower() == "text"
            and str(req["text"]).casefold() in str(obs.get("text") or "").casefold()
        )
    if kind == "route":
        return (
            str(obs.get("kind") or "").strip().lower() == "route"
            and str(obs.get("route") or "").strip().casefold() == str(req["route"]).casefold()
        )
    return False


def _validate_match(req: Mapping[str, Any], obs: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if obs.get("hidden") is True or obs.get("visible") is not True:
        issues.append("NOT_VISIBLE")

    if req["kind"] == "interactive":
        if obs.get("interactive") is not True:
            issues.append("NOT_INTERACTIVE")
        for field in ("wrapper_width", "wrapper_height", "interactive_width", "interactive_height"):
            if not _is_positive(obs.get(field)):
                issues.append(f"NONPOSITIVE_{field.upper()}")
        min_height = req.get("min_wrapper_height")
        if min_height is not None and _is_positive(obs.get("wrapper_height")):
            if float(obs["wrapper_height"]) < float(min_height):
                issues.append("WRAPPER_HEIGHT_BELOW_CONTRACT")
        # No arbitrary minimum is imposed on an internal interactive child.
        # Positive rendered dimensions are enough unless explicitly contracted.
    return sorted(set(issues))


def certify_semantic_contract(
    contract: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise SemanticUIVerificationFailure("semantic UI contract must be an object")
    contract_id = str(contract.get("contract_id") or "").strip()
    if not contract_id:
        raise SemanticUIVerificationFailure("contract_id is required")
    requirements_raw = contract.get("requirements")
    if not isinstance(requirements_raw, list) or not requirements_raw:
        raise SemanticUIVerificationFailure("contract requires at least one requirement")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise SemanticUIVerificationFailure("observations must be a sequence")

    requirements = [_normalize_requirement(item) for item in requirements_raw]
    capability_ids = [item["capability_id"] for item in requirements]
    if len(capability_ids) != len(set(capability_ids)):
        raise SemanticUIVerificationFailure("capability IDs must be unique")

    normalized_obs = [deepcopy(dict(item)) for item in observations if isinstance(item, Mapping)]
    results: list[dict[str, Any]] = []
    blocked = False

    for req in requirements:
        matches = [obs for obs in normalized_obs if _matches(req, obs)]
        issues: list[str] = []
        if not matches:
            issues = ["SEMANTIC_CAPABILITY_MISSING"]
        elif len(matches) > 1:
            issues = ["AMBIGUOUS_SEMANTIC_MATCH"]
        else:
            issues = _validate_match(req, matches[0])
        if issues:
            blocked = True
        results.append({
            "capability_id": req["capability_id"],
            "kind": req["kind"],
            "match_count": len(matches),
            "issues": issues,
            "green": not issues,
        })

    result = {
        "schema_version": 1,
        "version": VERSION,
        "contract_id": contract_id,
        "status": "BLOCKED" if blocked else "GREEN",
        "requirements": requirements,
        "results": results,
        "protections": {
            "semantic_truth_over_dom_shape": True,
            "hidden_marker_not_interactive_proof": True,
            "unique_match_required": True,
            "visible_surface_required": True,
            "interactive_behavior_required": True,
            "wrapper_owns_style_acceptance": True,
            "positive_child_dimensions_only_by_default": True,
            "framework_internal_selectors_forbidden": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        },
    }
    result["certificate_id"] = _fingerprint(result, "SEMUI-")
    return result


def validate_cases(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise SemanticUIVerificationFailure("cases payload must be an object")
    raw = deepcopy(dict(payload))
    supplied = str(raw.pop("cases_id", "") or "").strip().upper()
    if raw.get("version") != CASES_VERSION or int(raw.get("schema_version", 0)) != 1:
        raise SemanticUIVerificationFailure("cases version/schema mismatch")
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SemanticUIVerificationFailure("semantic verifier cases are required")
    basis = raw.get("historical_basis")
    if not isinstance(basis, list) or len(basis) < 2:
        raise SemanticUIVerificationFailure("historical verifier-failure basis is required")
    forbidden = raw.get("forbidden_brittle_examples")
    if not isinstance(forbidden, list) or not forbidden:
        raise SemanticUIVerificationFailure("forbidden brittle examples are required")
    for selector in forbidden:
        if not selector_fragility(str(selector)):
            raise SemanticUIVerificationFailure("brittle example was not detected")

    for case in cases:
        if not isinstance(case, Mapping):
            raise SemanticUIVerificationFailure("case must be an object")
        expected = str(case.get("expected") or "").upper()
        if expected not in {"GREEN", "BLOCKED"}:
            raise SemanticUIVerificationFailure("case expected status is invalid")
        result = certify_semantic_contract(case.get("contract") or {}, case.get("observations") or [])
        if result["status"] != expected:
            raise SemanticUIVerificationFailure(
                f"case {case.get('case_id')!r} expected {expected} got {result['status']}"
            )

    expected_id = _fingerprint(raw, "SEMCASES-")
    if supplied != expected_id:
        raise SemanticUIVerificationFailure("semantic verifier cases fingerprint mismatch")
    raw["cases_id"] = supplied
    return raw


def load_cases(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SemanticUIVerificationFailure(f"unable to load cases: {path}") from exc
    return validate_cases(payload)


def contract_self_test() -> dict[str, Any]:
    durable = certify_semantic_contract(
        {
            "contract_id": "durable-control",
            "requirements": [
                {
                    "capability_id": "date",
                    "kind": "interactive",
                    "role": "combobox",
                    "accessible_name": "Slate Date",
                    "min_wrapper_height": 40,
                }
            ],
        },
        [
            {
                "role": "combobox",
                "accessible_name": "Slate Date",
                "visible": True,
                "interactive": True,
                "wrapper_width": 195.171875,
                "wrapper_height": 68,
                "interactive_width": 123,
                "interactive_height": 25.59375,
            }
        ],
    )
    hidden = certify_semantic_contract(
        {
            "contract_id": "hidden-negative",
            "requirements": [
                {"capability_id": "sport", "kind": "interactive", "role": "combobox", "accessible_name": "Sport"}
            ],
        },
        [{"kind": "diagnostic_marker", "text": "SPORT_READY", "visible": False, "hidden": True}],
    )
    ambiguous = certify_semantic_contract(
        {
            "contract_id": "ambiguous-negative",
            "requirements": [
                {"capability_id": "market", "kind": "interactive", "role": "combobox", "accessible_name": "Market"}
            ],
        },
        [
            {"role": "combobox", "accessible_name": "Market", "visible": True, "interactive": True, "wrapper_width": 100, "wrapper_height": 50, "interactive_width": 80, "interactive_height": 20},
            {"role": "combobox", "accessible_name": "Market", "visible": True, "interactive": True, "wrapper_width": 100, "wrapper_height": 50, "interactive_width": 80, "interactive_height": 20},
        ],
    )
    brittle_blocked = False
    try:
        validate_locator_strategy({"kind": "stable_wrapper", "semantic_key": "date", "selector": "[data-baseweb='input']"})
    except SemanticUIVerificationFailure:
        brittle_blocked = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "dom_reshuffle_semantics_green": durable["status"] == "GREEN",
        "positive_child_dimensions_accept_real_control": durable["status"] == "GREEN",
        "hidden_marker_blocked": hidden["status"] == "BLOCKED",
        "ambiguous_match_blocked": ambiguous["status"] == "BLOCKED",
        "framework_internal_selector_blocked": brittle_blocked,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "dom_reshuffle_semantics_green",
        "positive_child_dimensions_accept_real_control",
        "hidden_marker_blocked",
        "ambiguous_match_blocked",
        "framework_internal_selector_blocked",
    ]
    if not all(result[name] is True for name in required):
        raise SemanticUIVerificationFailure("semantic UI verifier self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"] or result["mutation_authority_granted"]:
        raise SemanticUIVerificationFailure("semantic verifier read-only invariant failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="MONSTER V6 semantic UI verifier contract")
    parser.add_argument("--cases", default="")
    args = parser.parse_args()
    result = contract_self_test()
    if args.cases:
        cases = load_cases(args.cases)
        print(f"MONSTER_V6_SEMANTIC_UI_CASES_GREEN id={cases['cases_id']} cases={len(cases['cases'])}")
    print("MONSTER_V6_SEMANTIC_UI_VERIFIER_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SemanticUIVerificationFailure as exc:
        print(f"MONSTER_V6_SEMANTIC_UI_VERIFIER_BLOCKED: {exc}")
        raise SystemExit(1)
