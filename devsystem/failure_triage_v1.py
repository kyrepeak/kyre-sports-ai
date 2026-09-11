"""Intelligent failure triage for DevSystem CI.

Maps failed/skipped infrastructure lanes to a small, deterministic diagnosis so
operators know which layer to inspect first. This module never changes sports
projection/model logic; it only interprets CI job outcomes.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any


ROUTES: dict[str, dict[str, str]] = {
    "classify": {
        "layer": "change-classifier",
        "failure_class": "change-impact classification",
        "inspect_first": "devsystem/change_classifier_v1.py and changed-path inputs",
    },
    "workflow-hygiene": {
        "layer": "workflow-control",
        "failure_class": "legacy workflow fan-out or trigger drift",
        "inspect_first": "devsystem/legacy_broad_pr_workflows_2026-09-09.txt and .github/workflows",
    },
    "permanent-contract": {
        "layer": "devsystem-contract",
        "failure_class": "manifest/protection/permanent contract regression",
        "inspect_first": "devsystem/permanent_gate_v1.py and devsystem/devsystem_manifest_v1.json",
    },
    "regression-shield": {
        "layer": "regression-shield",
        "failure_class": "frozen invariant or protected contract regression",
        "inspect_first": "devsystem/regression_shield_v1.py and the first failing invariant",
    },
    "browser-qa": {
        "layer": "ui-browser",
        "failure_class": "Streamlit routing/rendering/browser behavior",
        "inspect_first": "browser QA artifact, Streamlit log, then devsystem/browser_qa_v1.py",
    },
    "cfb-critical": {
        "layer": "cfb",
        "failure_class": "College Football critical-path regression",
        "inspect_first": "first failing CFB test; preserve frozen projection math and official-ID contracts",
    },
    "mlb-critical": {
        "layer": "mlb",
        "failure_class": "MLB critical-path regression",
        "inspect_first": "first failing MLB critical test before touching shared infrastructure",
    },
    "wnba-critical": {
        "layer": "wnba",
        "failure_class": "WNBA critical-path regression",
        "inspect_first": "first failing WNBA critical test before touching shared infrastructure",
    },
    "core-smoke": {
        "layer": "shared-core",
        "failure_class": "shared entrypoint/import/compile regression",
        "inspect_first": "app.py and the first compile/import traceback",
    },
    "devsystem-final-gate": {
        "layer": "devsystem-final-gate",
        "failure_class": "aggregate gate execution or final-gate contract failure",
        "inspect_first": "the failed final-gate step, then devsystem/final_gate_v1.py",
    },
    "production-verification": {
        "layer": "production",
        "failure_class": "deployment/runtime/identity drift",
        "inspect_first": "production verification evidence, Render health/details, then deploy identity",
    },
}


def _route_for(job_name: str) -> dict[str, str]:
    if job_name in ROUTES:
        return ROUTES[job_name]
    return {
        "layer": "unknown",
        "failure_class": "unclassified CI failure",
        "inspect_first": f"GitHub Actions logs for {job_name}",
    }


def triage(needs: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    for name, payload in sorted(needs.items()):
        result = str((payload or {}).get("result") or "unknown")
        if result in {"success", "skipped"}:
            continue
        route = _route_for(name)
        failures.append({"job": name, "result": result, **route})

    primary = failures[0] if failures else None
    return {
        "status": "FAILURES_FOUND" if failures else "GREEN",
        "failure_count": len(failures),
        "primary": primary,
        "failures": failures,
    }


def render_summary(report: dict[str, Any]) -> str:
    if report["status"] == "GREEN":
        return "DEVSYSTEM_FAILURE_TRIAGE_GREEN no failed lanes"
    primary = report["primary"] or {}
    return (
        "DEVSYSTEM_FAILURE_TRIAGE "
        f"primary={primary.get('job')} "
        f"layer={primary.get('layer')} "
        f"class={primary.get('failure_class')} "
        f"inspect_first={primary.get('inspect_first')}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--needs-json")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    raw = args.needs_json or os.environ.get("DEVSYSTEM_NEEDS_JSON") or "{}"
    report = triage(json.loads(raw))
    print(render_summary(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
