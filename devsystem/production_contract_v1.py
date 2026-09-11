"""Permanent production deployment contract for Kyre Sports AI.

This file contains no credentials. It separates two different questions:
1) Is Render configured the way we intentionally deploy it?
2) Is the Render release branch actually carrying the same certified code as main?

That separation keeps production drift diagnosable instead of collapsing every
problem into a vague red/green hosting state.
"""
from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "KYRE_PRODUCTION_CONTRACT_V1"
PROVIDER = "render"
REPOSITORY = "https://github.com/kyrepeak/kyre-sports-ai"
SERVICE_NAME = "kyre-sports-api"
SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
PUBLIC_URL = "https://kyre-sports-api.onrender.com"
CANONICAL_SOURCE_BRANCH = "main"
RENDER_RELEASE_BRANCH = "mlb-step17b-shared-host-cert"
EXPECTED_AUTO_DEPLOY = "no"
EXPECTED_HEALTH_PATH = "/health"
DEPLOY_POLICY = "manual_release_pointer_after_devsystem_final_gate"
REQUIRE_RELEASE_PARITY_WITH_MAIN = True
REQUIRED_DIAGNOSTIC_PATHS = (
    "/health",
    "/health/ready",
    "/health/details",
)


def evaluate_render_service(service: dict[str, Any]) -> dict[str, Any]:
    """Validate hosting configuration without pretending it proves code freshness."""
    details = service.get("serviceDetails") or {}
    repo = str(service.get("repo") or "")
    observed = {
        "name": service.get("name"),
        "id": service.get("id"),
        "repo": repo,
        "branch": service.get("branch"),
        "auto_deploy": service.get("autoDeploy"),
        "health_path": details.get("healthCheckPath"),
        "url": details.get("url"),
        "suspended": service.get("suspended"),
    }

    violations: list[str] = []
    if observed["name"] != SERVICE_NAME:
        violations.append("service_name_mismatch")
    if observed["id"] != SERVICE_ID:
        violations.append("service_id_mismatch")
    if repo.rstrip("/") != REPOSITORY.rstrip("/"):
        violations.append("repository_mismatch")
    if observed["branch"] != RENDER_RELEASE_BRANCH:
        violations.append("release_branch_config_mismatch")
    if observed["auto_deploy"] != EXPECTED_AUTO_DEPLOY:
        violations.append("auto_deploy_policy_mismatch")
    if observed["health_path"] != EXPECTED_HEALTH_PATH:
        violations.append("health_path_mismatch")
    if observed["url"] != PUBLIC_URL:
        violations.append("public_url_mismatch")
    if observed["suspended"] not in {None, "not_suspended"}:
        violations.append("service_suspended")

    return {
        "contract_version": CONTRACT_VERSION,
        "status": "GREEN" if not violations else "RED",
        "provider": PROVIDER,
        "deploy_policy": DEPLOY_POLICY,
        "observed": observed,
        "expected": {
            "name": SERVICE_NAME,
            "id": SERVICE_ID,
            "repo": REPOSITORY,
            "branch": RENDER_RELEASE_BRANCH,
            "auto_deploy": EXPECTED_AUTO_DEPLOY,
            "health_path": EXPECTED_HEALTH_PATH,
            "url": PUBLIC_URL,
        },
        "violations": violations,
    }


def evaluate_release_parity(compare_payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate GitHub compare metadata for release-branch parity with main."""
    status = str(compare_payload.get("status") or "unknown")
    ahead_by = int(compare_payload.get("ahead_by") or 0)
    behind_by = int(compare_payload.get("behind_by") or 0)

    # compare(base=release, head=main):
    # ahead_by => commits main has that release does not.
    # behind_by => commits release has that main does not.
    parity = status == "identical" and ahead_by == 0 and behind_by == 0

    violations: list[str] = []
    if REQUIRE_RELEASE_PARITY_WITH_MAIN and not parity:
        if ahead_by:
            violations.append(f"release_missing_main_commits:{ahead_by}")
        if behind_by:
            violations.append(f"release_has_unmerged_commits:{behind_by}")
        if not violations:
            violations.append(f"release_compare_status:{status}")

    return {
        "contract_version": CONTRACT_VERSION,
        "status": "GREEN" if not violations else "RED",
        "canonical_branch": CANONICAL_SOURCE_BRANCH,
        "release_branch": RENDER_RELEASE_BRANCH,
        "compare_status": status,
        "main_only_commits": ahead_by,
        "release_only_commits": behind_by,
        "parity": parity,
        "violations": violations,
    }
