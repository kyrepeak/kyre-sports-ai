from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devsystem.runless_actions_fallback_policy_v1 import (
    AUTO_RE,
    audit_legacy_workflows,
    manifest_paths,
)

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP1_WORKFLOW_FANOUT_GOVERNOR_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

ROOT = Path(__file__).resolve().parents[1]


class WorkflowFanoutGovernorFailure(RuntimeError):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise WorkflowFanoutGovernorFailure(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _policy(root: Path) -> dict[str, Any]:
    path = root / "devsystem" / "workflow_fanout_policy_v1.json"
    payload = json.loads(_read(path))
    if payload.get("version") != VERSION:
        raise WorkflowFanoutGovernorFailure("fan-out policy version drift")
    if payload.get("repository") != "kyrepeak/kyre-sports-ai":
        raise WorkflowFanoutGovernorFailure("fan-out policy repository drift")
    if payload.get("normal_proof_plane") != "runless-proof-plane":
        raise WorkflowFanoutGovernorFailure("normal proof plane drift")
    if payload.get("legacy_actions_mode") != "manual_only":
        raise WorkflowFanoutGovernorFailure("legacy Actions mode drift")
    return payload


def _manual_only(text: str) -> bool:
    return "workflow_dispatch:" in text and AUTO_RE.search(text) is None


def audit_repository(root: Path = ROOT) -> dict[str, Any]:
    policy = _policy(root)
    step7 = _read(
        root
        / ".github"
        / "workflows"
        / "api2-proof-architecture-v1-step7-end-to-end-convergence.yml"
    )
    failure_packet = _read(
        root / ".github" / "workflows" / "devsystem-failure-packet-v1.yml"
    )
    targeted_ci = _read(
        root / ".github" / "workflows" / "devsystem-targeted-ci.yml"
    )
    wnba_fast = _read(
        root / ".github" / "workflows" / "wnba-nav-step6-fast-cert.yml"
    )
    wnba_responsive = _read(
        root / ".github" / "workflows" / "wnba-nav-step6-responsive-cert.yml"
    )
    workflow_quarantine = _read(
        root / ".github" / "workflows" / "monster-speed-v3-step1-quarantine-v1.yml"
    )
    fallback_audit = audit_legacy_workflows(root)

    checks = {
        "legacy_actions_manual_only": fallback_audit["green"],
        "step7_manual_fallback": _manual_only(step7),
        "failure_packet_failure_only": (
            "if: github.event_name != 'workflow_run' || github.event.workflow_run.conclusion == 'failure'"
            in failure_packet
        ),
        "targeted_ci_manual_fallback": _manual_only(targeted_ci),
        "permanent_contract_uses_exact_pr_head": (
            "permanent-contract:" in targeted_ci
            and "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}"
            in targeted_ci
        ),
        "wnba_nav_fast_cert_manual_fallback": _manual_only(wnba_fast),
        "wnba_nav_responsive_cert_manual_fallback": _manual_only(wnba_responsive),
        "workflow_change_quarantine_manual_fallback": _manual_only(
            workflow_quarantine
        ),
        "product_runtime_untouched_by_policy": (
            policy["safety"]["product_runtime_mutation_allowed"] is False
            and policy["safety"]["model_projection_mutation_allowed"] is False
        ),
        "blind_reruns_forbidden": policy["safety"]["blind_reruns_allowed"] is False,
        "frozen_change_requires_exact_thaw": policy["safety"]
        ["frozen_artifact_change_requires_exact_thaw"]
        is True,
    }

    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise WorkflowFanoutGovernorFailure(
            "workflow fan-out governor blocked: " + ", ".join(failed)
        )

    return {
        "status": "GREEN",
        "version": VERSION,
        "normal_proof_plane": policy["normal_proof_plane"],
        "legacy_actions_mode": policy["legacy_actions_mode"],
        "legacy_actions_manifest_count": len(manifest_paths(root)),
        "checks": checks,
        "proof_lanes": {
            "step7": "RUNLESS_MANUAL_FALLBACK",
            "failure_packet": "SOURCE_FAILURE_ONLY",
            "targeted_ci": "RUNLESS_MANUAL_FALLBACK",
            "permanent_contract": "EXACT_PR_HEAD_IDENTITY",
            "wnba_nav_fast_cert": "RUNLESS_MANUAL_FALLBACK",
            "wnba_nav_responsive_cert": "RUNLESS_MANUAL_FALLBACK",
            "workflow_quarantine": "RUNLESS_MANUAL_FALLBACK",
            "legacy_actions": "MANIFEST_MANUAL_ONLY",
        },
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def main() -> int:
    result = audit_repository()
    print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP1_FANOUT_GOVERNOR_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
