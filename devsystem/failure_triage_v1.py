"""Intelligent failure triage for DevSystem CI.

Maps failed/skipped infrastructure lanes and optional failure evidence to a small,
deterministic diagnosis so operators know which layer and failure mode to inspect
first. This module never changes sports projection/model logic; it only interprets
CI outcomes and evidence text.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
        "inspect_first": "the failed final-gate dependency result",
    },
    "production-verification": {
        "layer": "production",
        "failure_class": "deployment/runtime/identity drift",
        "inspect_first": "production verification evidence, Render health/details, then deploy identity",
    },
}

# Ordered most-specific first. This is intentionally deterministic and conservative.
EVIDENCE_SIGNATURES: tuple[dict[str, Any], ...] = (
    {
        "name": "browser-selector-race",
        "patterns": (r"playwright.*timeout", r"locator.*timeout", r"strict mode violation", r"waiting for.*combobox", r"waiting for.*locator"),
        "diagnosis": "browser selector/readiness synchronization failure",
        "confidence": "high",
        "inspect_first": "the first timed-out locator and the preceding Streamlit rerun/readiness barrier",
    },
    {
        "name": "test-assertion",
        "patterns": (r"assertionerror", r"\bfailed\b.*::", r"short test summary info"),
        "diagnosis": "test assertion or protected contract failure",
        "confidence": "high",
        "inspect_first": "the first failing test assertion and its protected invariant before changing implementation",
    },
    {
        "name": "python-import",
        "patterns": (r"modulenotfounderror", r"importerror", r"cannot import name"),
        "diagnosis": "Python import/dependency surface failure",
        "confidence": "high",
        "inspect_first": "the first missing/imported module, then the lane requirements/cache key that supplies it",
    },
    {
        "name": "syntax-compile",
        "patterns": (r"syntaxerror", r"indentationerror", r"taberror"),
        "diagnosis": "Python syntax/compile failure",
        "confidence": "high",
        "inspect_first": "the first syntax traceback location; avoid touching unrelated model/runtime code",
    },
    {
        "name": "cache-dependency",
        "patterns": (r"cache (miss|restore|failed)", r"pip.*(error|failed)", r"no matching distribution", r"could not find a version"),
        "diagnosis": "dependency or CI cache provisioning failure",
        "confidence": "medium",
        "inspect_first": "the cache key/restore result and first dependency installation error",
    },
    {
        "name": "network-upstream",
        "patterns": (r"connectionerror", r"connection reset", r"timed out.*https?", r"429 too many requests", r"rate limit", r"502 bad gateway", r"503 service unavailable"),
        "diagnosis": "network or upstream service failure",
        "confidence": "medium",
        "inspect_first": "the first failing external endpoint and whether retry/freshness policy was engaged",
    },
    {
        "name": "generic-timeout",
        "patterns": (r"timeout(error)?", r"timed out", r"deadline exceeded"),
        "diagnosis": "timeout without a more specific signature",
        "confidence": "medium",
        "inspect_first": "the operation immediately before the timeout and its readiness/timeout contract",
    },
)


def _route_for(job_name: str) -> dict[str, str]:
    if job_name in ROUTES:
        return ROUTES[job_name]
    return {
        "layer": "unknown",
        "failure_class": "unclassified CI failure",
        "inspect_first": f"GitHub Actions logs for {job_name}",
    }


def diagnose_evidence(text: str | None) -> dict[str, str] | None:
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    for signature in EVIDENCE_SIGNATURES:
        for pattern in signature["patterns"]:
            match = re.search(pattern, normalized, flags=re.DOTALL)
            if match:
                return {
                    "evidence_signal": str(signature["name"]),
                    "diagnosis": str(signature["diagnosis"]),
                    "confidence": str(signature["confidence"]),
                    "evidence_match": match.group(0)[:160],
                    "inspect_first": str(signature["inspect_first"]),
                }
    return {
        "evidence_signal": "unclassified-evidence",
        "diagnosis": "no known deterministic failure signature matched",
        "confidence": "low",
        "evidence_match": "",
        "inspect_first": "the first error/traceback line in the captured job evidence",
    }


def triage(needs: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    for name, payload in sorted(needs.items()):
        payload = payload or {}
        result = str(payload.get("result") or "unknown")
        if result in {"success", "skipped"}:
            continue
        route = _route_for(name)
        failure: dict[str, str] = {"job": name, "result": result, **route}
        evidence = diagnose_evidence(
            str(payload.get("evidence") or payload.get("log_excerpt") or "")
        )
        if evidence:
            # Evidence refines the failure mode and next action; the lane remains the owner.
            failure.update(evidence)
        else:
            failure.update({
                "evidence_signal": "none",
                "diagnosis": route["failure_class"],
                "confidence": "lane-only",
                "evidence_match": "",
            })
        failures.append(failure)

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
        f"signal={primary.get('evidence_signal')} "
        f"confidence={primary.get('confidence')} "
        f"diagnosis={primary.get('diagnosis')} "
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
