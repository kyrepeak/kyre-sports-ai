"""Intelligent failure triage for DevSystem CI.

Maps failed/skipped infrastructure lanes and optional failure evidence to a small,
deterministic diagnosis so operators know which layer and failure mode to inspect
first. This module never changes sports projection/model logic; it only interprets
CI outcomes and evidence text.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
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
# "transient-capable" means a one-time retry can distinguish runner/upstream variance;
# it is not a claim that the failure is flaky.
EVIDENCE_SIGNATURES: tuple[dict[str, Any], ...] = (
    {
        "name": "browser-selector-race",
        "patterns": (r"playwright.*timeout", r"locator.*timeout", r"strict mode violation", r"waiting for.*combobox", r"waiting for.*locator"),
        "diagnosis": "browser selector/readiness synchronization failure",
        "confidence": "high",
        "inspect_first": "the first timed-out locator and the preceding Streamlit rerun/readiness barrier",
        "remediation_class": "transient-capable",
        "retry_policy": "retry-once-after-inspection",
        "retry_reason": "browser readiness can vary with runner timing, but a repeated failure should be treated as deterministic until fixed",
    },
    {
        "name": "test-assertion",
        "patterns": (r"assertionerror", r"\bfailed\b.*::", r"short test summary info"),
        "diagnosis": "test assertion or protected contract failure",
        "confidence": "high",
        "inspect_first": "the first failing test assertion and its protected invariant before changing implementation",
        "remediation_class": "deterministic-regression",
        "retry_policy": "do-not-retry",
        "retry_reason": "the test observed a concrete protected-contract mismatch; inspect and fix the cause before rerunning",
    },
    {
        "name": "python-import",
        "patterns": (r"modulenotfounderror", r"importerror", r"cannot import name"),
        "diagnosis": "Python import/dependency surface failure",
        "confidence": "high",
        "inspect_first": "the first missing/imported module, then the lane requirements/cache key that supplies it",
        "remediation_class": "deterministic-regression",
        "retry_policy": "do-not-retry",
        "retry_reason": "a missing or incompatible import normally persists until code, requirements, or cache provisioning is corrected",
    },
    {
        "name": "syntax-compile",
        "patterns": (r"syntaxerror", r"indentationerror", r"taberror"),
        "diagnosis": "Python syntax/compile failure",
        "confidence": "high",
        "inspect_first": "the first syntax traceback location; avoid touching unrelated model/runtime code",
        "remediation_class": "deterministic-regression",
        "retry_policy": "do-not-retry",
        "retry_reason": "syntax and compile errors are deterministic and cannot be repaired by rerunning CI",
    },
    {
        "name": "cache-dependency",
        "patterns": (r"cache (miss|restore|failed)", r"pip.*(error|failed)", r"no matching distribution", r"could not find a version"),
        "diagnosis": "dependency or CI cache provisioning failure",
        "confidence": "medium",
        "inspect_first": "the cache key/restore result and first dependency installation error",
        "remediation_class": "transient-capable",
        "retry_policy": "retry-once-after-inspection",
        "retry_reason": "cache/network provisioning can be transient, but repeated dependency-resolution failures require a real fix",
    },
    {
        "name": "network-upstream",
        "patterns": (r"connectionerror", r"connection reset", r"timed out.*https?", r"429 too many requests", r"rate limit", r"502 bad gateway", r"503 service unavailable"),
        "diagnosis": "network or upstream service failure",
        "confidence": "medium",
        "inspect_first": "the first failing external endpoint and whether retry/freshness policy was engaged",
        "remediation_class": "transient-capable",
        "retry_policy": "retry-once-after-inspection",
        "retry_reason": "rate limits and upstream/network faults can clear without a code change; one controlled retry is safe after confirming the endpoint failure",
    },
    {
        "name": "generic-timeout",
        "patterns": (r"timeout(error)?", r"timed out", r"deadline exceeded"),
        "diagnosis": "timeout without a more specific signature",
        "confidence": "medium",
        "inspect_first": "the operation immediately before the timeout and its readiness/timeout contract",
        "remediation_class": "transient-capable",
        "retry_policy": "retry-once-after-inspection",
        "retry_reason": "a timeout may reflect runner variance, but a second occurrence should be investigated as a deterministic readiness or performance defect",
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
                    "remediation_class": str(signature["remediation_class"]),
                    "retry_policy": str(signature["retry_policy"]),
                    "retry_reason": str(signature["retry_reason"]),
                }
    return {
        "evidence_signal": "unclassified-evidence",
        "diagnosis": "no known deterministic failure signature matched",
        "confidence": "low",
        "evidence_match": "",
        "inspect_first": "the first error/traceback line in the captured job evidence",
        "remediation_class": "unknown",
        "retry_policy": "investigate-first",
        "retry_reason": "the evidence is not specific enough to safely recommend a retry or a code fix",
    }



def _load_wait_state_machine():
    path = Path(__file__).with_name("wait_state_machine_v1.py")
    spec = importlib.util.spec_from_file_location("wait_state_machine_v1_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("API2 WAIT state machine unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _attach_failure_owner(failure: dict[str, str]) -> dict[str, str]:
    """Attach Step-4 ownership before any remediation can be selected."""
    path = Path(__file__).with_name("failure_ownership_engine_v1.py")
    spec = importlib.util.spec_from_file_location("failure_ownership_engine_v1_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("MONSTER Failure Ownership Engine unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    decision = module.classify_failure(failure)
    enriched = dict(failure)
    enriched.update({
        "owner": decision["owner"],
        "owner_failure_class": decision["failure_class"],
        "owner_decision_id": decision["decision_id"],
        "owner_patch_allowed": str(decision["patch_allowed"]).lower(),
        "owner_next_legal_action": decision["next_legal_action"],
        "owner_classification_basis": decision["classification_basis"],
    })
    return enriched


def triage(needs: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    waits: list[dict[str, Any]] = []
    wait_module = _load_wait_state_machine()
    for name, payload in sorted(needs.items()):
        payload = payload or {}
        result = str(payload.get("result") or "unknown")
        if result in {"success", "skipped"}:
            continue
        route = _route_for(name)
        failure: dict[str, str] = {"job": name, "result": result, **route}
        raw_evidence = str(payload.get("evidence") or payload.get("log_excerpt") or "")
        evidence = diagnose_evidence(raw_evidence)
        if evidence:
            # Evidence refines the failure mode and next action; the lane remains the owner.
            failure.update(evidence)
        else:
            failure.update({
                "evidence_signal": "none",
                "diagnosis": route["failure_class"],
                "confidence": "lane-only",
                "evidence_match": "",
                "remediation_class": "unknown",
                "retry_policy": "investigate-first",
                "retry_reason": "lane-level failure alone is not enough evidence to safely recommend a retry",
            })
        wait_decision = wait_module.classify_wait(
            job_name=name,
            layer=route["layer"],
            evidence_signal=failure.get("evidence_signal", "none"),
            evidence_text=raw_evidence,
        )
        if wait_decision is not None:
            waiting = dict(failure)
            waiting.update({
                "disposition": "WAIT",
                "wait_state": wait_decision["state"],
                "wait_owner": wait_decision["owner"],
                "wait_state_token": wait_decision["state_token"],
                "wake_condition": wait_decision["wake_condition"],
                "recheck_policy": wait_decision["recheck_policy"],
                "blind_retry_allowed": wait_decision["blind_retry_allowed"],
                "next_legal_action": wait_decision["next_legal_action"],
            })
            waits.append(waiting)
            continue
        failures.append(_attach_failure_owner(failure))

    primary = failures[0] if failures else None
    status = "FAILURES_FOUND" if failures else ("WAITING" if waits else "GREEN")
    return {
        "status": status,
        "failure_count": len(failures),
        "wait_count": len(waits),
        "primary": primary,
        "failures": failures,
        "waits": waits,
    }


def render_summary(report: dict[str, Any]) -> str:
    if report["status"] == "GREEN":
        return "DEVSYSTEM_FAILURE_TRIAGE_GREEN no failed lanes"
    if report["status"] == "WAITING":
        waiting = (report.get("waits") or [{}])[0]
        return (
            "DEVSYSTEM_FAILURE_TRIAGE_WAITING "
            f"primary={waiting.get('job')} "
            f"state={waiting.get('wait_state')} "
            f"owner={waiting.get('wait_owner')} "
            f"wake={waiting.get('wake_condition')} "
            f"recheck_policy={waiting.get('recheck_policy')} "
            f"blind_retry_allowed={waiting.get('blind_retry_allowed')}"
        )
    primary = report["primary"] or {}
    return (
        "DEVSYSTEM_FAILURE_TRIAGE "
        f"primary={primary.get('job')} "
        f"layer={primary.get('layer')} "
        f"owner={primary.get('owner')} "
        f"signal={primary.get('evidence_signal')} "
        f"confidence={primary.get('confidence')} "
        f"remediation={primary.get('remediation_class')} "
        f"retry_policy={primary.get('retry_policy')} "
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
