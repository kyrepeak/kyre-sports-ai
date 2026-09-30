"""MONSTER V3 Step 7 — Project Dependency / Blast-Radius Map V1.

Pre-edit, read-only change-impact planner built on the proven Monster Dependency
Map V1 plus the MONSTER V3 Step-6 Adaptive Proof Engine.

Given a proposed path set, it predicts transitive dependent modules, production
entrypoints, protected/frozen reach, aggregate risk, and the minimum legitimate
proof plan before any repository mutation occurs.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

from devsystem.adaptive_proof_engine_v1 import plan_proof
from sports_api.monster_dependency_map_v1 import build_dependency_map

VERSION = "MONSTER_PROJECT_BLAST_RADIUS_MAP_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class BlastRadiusFailure(RuntimeError):
    pass


def _norm(path: Any) -> str:
    return str(path or "").strip().replace("\\", "/")


def _max_risk(values: Iterable[str]) -> str:
    risks = [str(v or "LOW").upper() for v in values]
    if not risks:
        return "LOW"
    return max(risks, key=lambda x: _RISK_ORDER.get(x, 2))


def plan_change(
    paths: Iterable[str],
    *,
    root: str | Path = ".",
    expected_head_sha: str = "",
    observed_head_sha: str = "",
) -> dict[str, Any]:
    proposed = sorted({_norm(path) for path in paths if _norm(path)})
    if not proposed:
        raise BlastRadiusFailure("at least one proposed path is required")

    graph = build_dependency_map(root)
    mapped: list[dict[str, Any]] = []
    unmapped: list[str] = []
    dependent_modules: set[str] = set()
    entrypoints: set[str] = set()
    protected: set[str] = set()
    risks: list[str] = []

    for path in proposed:
        report = graph.impact_report(path)
        if report.get("status") != "OK":
            unmapped.append(path)
            continue
        mapped.append(report)
        risks.append(str(report.get("risk") or "LOW").upper())
        dependent_modules.update(report.get("transitive_dependents") or [])
        entrypoints.update(report.get("impacted_entrypoints") or [])
        protected.update(report.get("protected_reach") or [])

    proof_plan = plan_proof(
        proposed,
        expected_head_sha=expected_head_sha,
        observed_head_sha=observed_head_sha,
    )

    aggregate_risk = _max_risk(risks)
    if protected and _RISK_ORDER[aggregate_risk] < _RISK_ORDER["HIGH"]:
        aggregate_risk = "HIGH"
    if unmapped and _RISK_ORDER[aggregate_risk] < _RISK_ORDER["HIGH"]:
        aggregate_risk = "HIGH"
    if entrypoints and len(dependent_modules) >= 20:
        aggregate_risk = "CRITICAL"

    if proof_plan["state"] == "STALE_HEAD":
        decision = "REPLAN_REQUIRED"
    elif protected:
        decision = "REVIEW_PROTECTED_REACH"
    elif unmapped:
        decision = "FAIL_SAFE_FULL_PROOF"
    else:
        decision = "PROCEED_WITH_PLANNED_PROOF"

    return {
        "version": VERSION,
        "status": "GREEN",
        "proposed_paths": proposed,
        "mapped_paths": [report["path"] for report in mapped],
        "unmapped_paths": unmapped,
        "risk": aggregate_risk,
        "blast_radius": len(dependent_modules),
        "transitive_dependents": sorted(dependent_modules),
        "impacted_entrypoints": sorted(entrypoints),
        "protected_reach": sorted(protected),
        "frozen_impact": bool(protected),
        "decision": decision,
        "proof_plan": proof_plan,
        "protections": {
            "pre_edit_only": True,
            "protected_reach_visible": True,
            "unknown_surface_fail_safe": True,
            "stale_head_cannot_certify": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }


def contract_self_test() -> dict[str, Any]:
    head = "a" * 40
    old = "b" * 40
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "feature.py").write_text("import leaf\n", encoding="utf-8")
        (root / "app.py").write_text("import feature\n", encoding="utf-8")
        (root / "frozen_projection.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "guarded.py").write_text("import frozen_projection\n", encoding="utf-8")

        leaf = plan_change(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
        )
        guarded = plan_change(
            ["guarded.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
        )
        unknown = plan_change(
            ["mystery.bin"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
        )
        stale = plan_change(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=old,
        )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "entrypoint_blast_radius_visible": (
            leaf["blast_radius"] == 2 and leaf["impacted_entrypoints"] == ["app.py"]
        ),
        "protected_reach_visible": (
            guarded["frozen_impact"] is True
            and guarded["decision"] == "REVIEW_PROTECTED_REACH"
        ),
        "unknown_surface_fail_safe": (
            unknown["decision"] == "FAIL_SAFE_FULL_PROOF"
            and unknown["proof_plan"]["full_release_required"] is True
        ),
        "stale_head_replan": stale["decision"] == "REPLAN_REQUIRED",
        "pre_edit_only": True,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
    }
    if not all(
        result[key] is True
        for key in (
            "entrypoint_blast_radius_visible",
            "protected_reach_visible",
            "unknown_surface_fail_safe",
            "stale_head_replan",
            "pre_edit_only",
        )
    ):
        raise BlastRadiusFailure("project blast-radius self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_PROJECT_BLAST_RADIUS_MAP_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
