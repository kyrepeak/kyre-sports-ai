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

    proof_plan = plan_proof(
        proposed,
        expected_head_sha=expected_head_sha,
        observed_head_sha=observed_head_sha,
    )

    if proof_plan["state"] == "STALE_HEAD":
        return {
            "version": VERSION,
            "status": "BLOCKED",
            "state": "STALE_HEAD",
            "proposed_paths": proposed,
            "mapped_paths": [],
            "unknown_targets": [],
            "risk": "UNKNOWN",
            "blast_radius": 0,
            "direct_dependencies": [],
            "direct_dependents": [],
            "transitive_dependencies": [],
            "transitive_dependents": [],
            "impacted_entrypoints": [],
            "protected_reach": [],
            "frozen_impact": False,
            "reports": [],
            "edit_allowed": False,
            "requires_narrowing": False,
            "requires_replan": True,
            "certifiable": False,
            "next_legal_action": "REFRESH_HEAD_AND_REPLAN",
            "proof_plan": proof_plan,
            "protections": {
                "pre_edit_only": True,
                "protected_reach_visible": True,
                "protected_high_risk_blocks_edit": True,
                "unknown_surface_fail_safe": True,
                "stale_head_cannot_certify": True,
                "network_calls": NETWORK_CALLS,
                "auto_mutate": AUTO_MUTATE,
                "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
            },
        }

    graph = build_dependency_map(root)
    mapped: list[dict[str, Any]] = []
    unknown_targets: list[str] = []
    direct_dependencies: set[str] = set()
    direct_dependents: set[str] = set()
    transitive_dependencies: set[str] = set()
    transitive_dependents: set[str] = set()
    entrypoints: set[str] = set()
    protected: set[str] = set()
    risks: list[str] = []

    protected_path_markers = (
        "frozen",
        "freeze_manifest",
        "projection_v14",
        "over_under_projection_v14",
        "devsystem/persistent_execution_brain_v1.py",
        "devsystem/automatic_loop_kill_v1.py",
        "devsystem/evidence_truth_ledger_v1.py",
        "devsystem/failure_ownership_engine_v1.py",
        "devsystem/deployment_truth_control_plane_v1.py",
        "devsystem/adaptive_proof_engine_v1.py",
        "devsystem/permanent_gate_v1.py",
        "devsystem/final_gate_v1.py",
    )

    for path in proposed:
        report = graph.impact_report(path)
        if report.get("status") != "OK":
            unknown_targets.append(path)
            continue

        mapped.append(report)
        risks.append(str(report.get("risk") or "LOW").upper())
        direct_dependencies.update(report.get("direct_dependencies") or [])
        direct_dependents.update(report.get("direct_dependents") or [])
        transitive_dependencies.update(report.get("transitive_dependencies") or [])
        transitive_dependents.update(report.get("transitive_dependents") or [])
        entrypoints.update(report.get("impacted_entrypoints") or [])
        protected.update(report.get("protected_reach") or [])

        related_modules = (
            set(report.get("direct_dependencies") or [])
            | set(report.get("direct_dependents") or [])
            | set(report.get("transitive_dependencies") or [])
            | set(report.get("transitive_dependents") or [])
            | {str(report.get("module") or "")}
        )
        for module in related_modules:
            related_path = graph.module_to_path.get(module, "")
            lowered = related_path.lower()
            if related_path and any(marker in lowered for marker in protected_path_markers):
                protected.add(related_path)

    aggregate_risk = _max_risk(risks)
    if protected and _RISK_ORDER.get(aggregate_risk, 0) < _RISK_ORDER["HIGH"]:
        aggregate_risk = "HIGH"
    if unknown_targets and _RISK_ORDER.get(aggregate_risk, 0) < _RISK_ORDER["HIGH"]:
        aggregate_risk = "HIGH"
    if entrypoints and len(transitive_dependents) >= 20:
        aggregate_risk = "CRITICAL"

    protected_high_risk = bool(
        protected and aggregate_risk in {"HIGH", "CRITICAL"}
    )

    if protected_high_risk:
        state = "BLOCKED_PROTECTED_REACH"
        next_action = "NARROW_EDIT_SCOPE"
    elif unknown_targets:
        state = "FAIL_SAFE"
        next_action = "RESOLVE_UNKNOWN_TARGETS"
    else:
        state = "READY"
        next_action = "APPLY_SMALLEST_SAFE_CHANGE"

    return {
        "version": VERSION,
        "status": "GREEN" if state == "READY" else "BLOCKED",
        "state": state,
        "proposed_paths": proposed,
        "mapped_paths": [report["path"] for report in mapped],
        "unknown_targets": sorted(unknown_targets),
        "risk": aggregate_risk,
        "blast_radius": len(transitive_dependents),
        "direct_dependencies": sorted(direct_dependencies),
        "direct_dependents": sorted(direct_dependents),
        "transitive_dependencies": sorted(transitive_dependencies),
        "transitive_dependents": sorted(transitive_dependents),
        "impacted_entrypoints": sorted(entrypoints),
        "protected_reach": sorted(protected),
        "frozen_impact": bool(protected),
        "reports": mapped,
        "edit_allowed": state == "READY",
        "requires_narrowing": protected_high_risk,
        "requires_replan": False,
        "certifiable": bool(proof_plan.get("certifiable")),
        "next_legal_action": next_action,
        "proof_plan": proof_plan,
        "protections": {
            "pre_edit_only": True,
            "protected_reach_visible": True,
            "protected_high_risk_blocks_edit": True,
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
        (root / "frozen_projection.py").write_text("import leaf\n", encoding="utf-8")
        (root / "streamlit_router.py").write_text("VALUE = 1\n", encoding="utf-8")

        leaf = plan_change(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
        )
        router = plan_change(
            ["streamlit_router.py"],
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
        "direct_transitive_map": (
            leaf["direct_dependents"] == ["feature", "frozen_projection"]
            and leaf["transitive_dependents"] == ["app", "feature", "frozen_projection"]
        ),
        "protected_reach_guard": (
            leaf["state"] == "BLOCKED_PROTECTED_REACH"
            and leaf["edit_allowed"] is False
            and leaf["requires_narrowing"] is True
            and "frozen_projection.py" in leaf["protected_reach"]
        ),
        "blast_radius_risk": (
            leaf["blast_radius"] == 3 and leaf["risk"] in {"HIGH", "CRITICAL"}
        ),
        "adaptive_proof_handoff": router["proof_plan"]["proofs"] == [
            "ROUTE_CONTRACT",
            "FRESH_SESSION_NAVIGATION",
        ],
        "unknown_fail_safe": (
            unknown["state"] == "FAIL_SAFE"
            and unknown["edit_allowed"] is False
            and unknown["proof_plan"]["full_release_required"] is True
        ),
        "stale_head_blocked": (
            stale["state"] == "STALE_HEAD"
            and stale["certifiable"] is False
            and stale["requires_replan"] is True
            and stale["reports"] == []
        ),
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
    }
    if not all(
        result[key] is True
        for key in (
            "direct_transitive_map",
            "protected_reach_guard",
            "blast_radius_risk",
            "adaptive_proof_handoff",
            "unknown_fail_safe",
            "stale_head_blocked",
        )
    ):
        raise BlastRadiusFailure("project blast-radius self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_PROJECT_BLAST_RADIUS_MAP_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
