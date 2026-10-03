"""API2 Control-Plane Efficiency V1 Step 2 — Root-Cause Collapse Engine.

Collapse CI failure cascades into the smallest truthful repair queue:
- exact duplicate signatures become one root;
- known aggregate/terminal lanes become consequences when a direct upstream root exists;
- independent failures remain independent rather than being falsely merged;
- only one primary root is active for repair at a time.

This module is dependency-light, performs no network calls, and grants no
repository or product mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP2_ROOT_CAUSE_COLLAPSE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

CASCADE_LANES = frozenset({
    "devsystem-final-gate",
    "terminal-proof-receipt",
    "full-merge-certification",
})


class RootCauseCollapseFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _root_id(item: Mapping[str, Any]) -> str:
    basis = {
        "job": str(item.get("job") or ""),
        "layer": str(item.get("layer") or ""),
        "failure_class": str(item.get("failure_class") or ""),
        "failure_fingerprint": str(item.get("failure_fingerprint") or ""),
        "evidence_signal": str(item.get("evidence_signal") or ""),
        "diagnosis": str(item.get("diagnosis") or ""),
    }
    return "ROOT-" + hashlib.sha256(_canonical(basis).encode("utf-8")).hexdigest()[:24].upper()


def _signature(item: Mapping[str, Any]) -> str:
    fingerprint = str(item.get("failure_fingerprint") or "").strip()
    if fingerprint:
        return "fingerprint:" + fingerprint
    return "semantic:" + _canonical({
        "layer": str(item.get("layer") or ""),
        "failure_class": str(item.get("failure_class") or ""),
        "evidence_signal": str(item.get("evidence_signal") or ""),
        "diagnosis": str(item.get("diagnosis") or ""),
        "inspect_first": str(item.get("inspect_first") or ""),
    })


def _copy_failure(item: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise RootCauseCollapseFailure("failure item must be an object")
    value = deepcopy(dict(item))
    value["job"] = str(value.get("job") or "unknown")
    value["root_cause_id"] = _root_id(value)
    return value


def collapse_failures(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise RootCauseCollapseFailure("triage report must be an object")

    failures = report.get("failures") or []
    if not isinstance(failures, list):
        raise RootCauseCollapseFailure("triage failures must be a list")

    if not failures:
        return {
            "version": VERSION,
            "status": "GREEN",
            "decision": "NO_FAILURES",
            "root_count": 0,
            "primary_root": None,
            "independent_roots": [],
            "collapsed_failures": [],
            "repair_queue": [],
            "next_legal_action": "NONE",
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        }

    copied = [_copy_failure(item) for item in failures]
    primary = report.get("primary") or {}
    primary_job = str(primary.get("job") or "")
    primary_fingerprint = str(primary.get("failure_fingerprint") or "")

    unique: list[dict[str, Any]] = []
    collapsed: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    for item in copied:
        sig = _signature(item)
        prior = seen.get(sig)
        if prior is None:
            seen[sig] = item
            unique.append(item)
            continue
        consequence = deepcopy(item)
        consequence["collapse_reason"] = "DUPLICATE_FAILURE_SIGNATURE"
        consequence["collapsed_into_root_cause_id"] = prior["root_cause_id"]
        collapsed.append(consequence)

    direct = [item for item in unique if item["job"] not in CASCADE_LANES]
    if direct:
        roots: list[dict[str, Any]] = []
        for item in unique:
            if item["job"] in CASCADE_LANES:
                consequence = deepcopy(item)
                consequence["collapse_reason"] = "DOWNSTREAM_AGGREGATE_CONSEQUENCE"
                consequence["collapsed_into_root_cause_id"] = ""
                collapsed.append(consequence)
            else:
                roots.append(item)
    else:
        roots = unique

    if not roots:
        raise RootCauseCollapseFailure("collapse removed every failure root")

    def primary_rank(item: Mapping[str, Any]) -> tuple[int, int, str]:
        fp_match = bool(primary_fingerprint) and str(item.get("failure_fingerprint") or "") == primary_fingerprint
        job_match = bool(primary_job) and str(item.get("job") or "") == primary_job
        return (0 if fp_match else 1, 0 if job_match else 1, str(item.get("job") or ""))

    roots = sorted(roots, key=primary_rank)
    primary_root = deepcopy(roots[0])

    for item in collapsed:
        if (
            item.get("collapse_reason") == "DOWNSTREAM_AGGREGATE_CONSEQUENCE"
            and not item.get("collapsed_into_root_cause_id")
        ):
            item["collapsed_into_root_cause_id"] = primary_root["root_cause_id"]

    repair_queue = [
        {
            "job": item["job"],
            "root_cause_id": item["root_cause_id"],
            "layer": str(item.get("layer") or ""),
            "inspect_first": str(item.get("inspect_first") or ""),
            "remediation_class": str(item.get("remediation_class") or ""),
            "retry_policy": str(item.get("retry_policy") or ""),
        }
        for item in roots
    ]

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "SINGLE_ROOT_COLLAPSED" if len(roots) == 1 else "MULTIPLE_INDEPENDENT_ROOTS_PRESERVED",
        "root_count": len(roots),
        "primary_root": primary_root,
        "independent_roots": roots,
        "collapsed_failures": sorted(collapsed, key=lambda item: (str(item.get("job") or ""), str(item.get("collapse_reason") or ""))),
        "collapsed_failure_count": len(collapsed),
        "repair_queue": repair_queue,
        "next_legal_action": "PATCH_PRIMARY_ROOT_ONLY",
        "protections": {
            "false_multi_root_collapse_forbidden": True,
            "downstream_aggregate_not_repaired_directly": True,
            "one_active_root_at_a_time": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }


def self_test() -> dict[str, Any]:
    root = {
        "job": "permanent-contract",
        "layer": "control-plane",
        "failure_class": "test-assertion",
        "failure_fingerprint": "KYRE-CI-ROOT",
        "evidence_signal": "frozen-registry-mismatch",
        "diagnosis": "exact head mismatch",
        "inspect_first": "registry verifier identity",
        "remediation_class": "control-plane",
        "retry_policy": "patch-first",
    }
    final_gate = {
        "job": "devsystem-final-gate",
        "layer": "devsystem-final-gate",
        "failure_class": "aggregate",
        "failure_fingerprint": "KYRE-CI-FINAL",
        "evidence_signal": "required-lane-blocked",
        "diagnosis": "upstream lane failed",
        "inspect_first": "upstream failed lane",
    }
    result = collapse_failures({"primary": root, "failures": [root, final_gate]})
    if result["decision"] != "SINGLE_ROOT_COLLAPSED":
        raise RootCauseCollapseFailure("self-test did not collapse aggregate lane")
    if result["primary_root"]["job"] != "permanent-contract":
        raise RootCauseCollapseFailure("self-test selected wrong root")
    if [item["job"] for item in result["collapsed_failures"]] != ["devsystem-final-gate"]:
        raise RootCauseCollapseFailure("self-test did not record collapsed lane")
    print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP2_ROOT_CAUSE_COLLAPSE_GREEN")
    return result


def main() -> int:
    print(json.dumps(self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
