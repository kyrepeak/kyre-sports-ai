from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    return payload


def audit_repository(root: Path = ROOT) -> dict[str, Any]:
    policy = _policy(root)
    step7 = _read(root / ".github" / "workflows" / "api2-proof-architecture-v1-step7-end-to-end-convergence.yml")
    failure_packet = _read(root / ".github" / "workflows" / "devsystem-failure-packet-v1.yml")
    targeted_ci = _read(root / ".github" / "workflows" / "devsystem-targeted-ci.yml")
    wnba_fast = _read(root / ".github" / "workflows" / "wnba-nav-step6-fast-cert.yml")
    wnba_responsive = _read(root / ".github" / "workflows" / "wnba-nav-step6-responsive-cert.yml")
    workflow_quarantine = _read(root / ".github" / "workflows" / "monster-speed-v3-step1-quarantine-v1.yml")

    checks = {
        "step7_pr_path_scoped": (
            "pull_request:\n    branches: [main]\n    paths:" in step7
            and step7.count("    paths:") >= 2
        ),
        "step7_push_path_scoped": "push:\n    branches: [main]\n    paths:" in step7,
        "step7_cancel_stale_heads": (
            "github.event.pull_request.number" in step7
            and "cancel-in-progress: true" in step7
        ),
        "failure_packet_failure_only": (
            "if: github.event_name != 'workflow_run' || github.event.workflow_run.conclusion == 'failure'"
            in failure_packet
        ),
        "targeted_ci_remains_central_dispatcher": (
            "name: DevSystem targeted CI" in targeted_ci
            and "pull_request:\n    branches: [main]" in targeted_ci
            and "cancel-in-progress: true" in targeted_ci
        ),
        "wnba_nav_fast_cert_path_scoped": (
            "pull_request:\n    branches: [main]\n    paths:" in wnba_fast
            and "devsystem/wnba_nav_step6_fast_cert.py" in wnba_fast
            and "wnba_pra_responsive_v2_step6.py" in wnba_fast
        ),
        "wnba_nav_responsive_cert_path_scoped": (
            "pull_request:\n    branches: [main]\n    paths:" in wnba_responsive
            and "devsystem/wnba_nav_step6_responsive_cert.py" in wnba_responsive
            and "devsystem/wnba_nav_step6_responsive_harness.py" in wnba_responsive
        ),
        "workflow_change_quarantine_preserved": (
            '".github/workflows/**"' in workflow_quarantine
            and "cancel-in-progress: true" in workflow_quarantine
        ),
        "product_runtime_untouched_by_policy": (
            policy["safety"]["product_runtime_mutation_allowed"] is False
            and policy["safety"]["model_projection_mutation_allowed"] is False
        ),
        "blind_reruns_forbidden": policy["safety"]["blind_reruns_allowed"] is False,
        "frozen_change_requires_exact_thaw": policy["safety"]["frozen_artifact_change_requires_exact_thaw"] is True,
    }

    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise WorkflowFanoutGovernorFailure(
            "workflow fan-out governor blocked: " + ", ".join(failed)
        )

    return {
        "status": "GREEN",
        "version": VERSION,
        "central_broad_dispatcher": policy["central_broad_dispatcher"],
        "checks": checks,
        "proof_lanes": {
            "step7": "PATH_SCOPED_AND_STALE_CANCELLED",
            "failure_packet": "SOURCE_FAILURE_ONLY",
            "targeted_ci": "CENTRAL_BROAD_DISPATCHER_PRESERVED",
            "wnba_nav_fast_cert": "WNBA_PATH_SCOPED",
            "wnba_nav_responsive_cert": "WNBA_PATH_SCOPED",
            "workflow_quarantine": "WORKFLOW_CHANGE_SAFETY_PRESERVED",
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
