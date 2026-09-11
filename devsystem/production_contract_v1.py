"""Permanent production deployment contract for Kyre Sports AI.

This file contains no credentials. It exists so humans, CI, and ChatGPT can
compare the actual hosting configuration against a single expected contract.
"""
from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "KYRE_PRODUCTION_CONTRACT_V1"
PROVIDER = "render"
REPOSITORY = "https://github.com/kyrepeak/kyre-sports-ai"
SERVICE_NAME = "kyre-sports-api"
SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
PUBLIC_URL = "https://kyre-sports-api.onrender.com"
EXPECTED_SOURCE_BRANCH = "main"
EXPECTED_AUTO_DEPLOY = "no"
EXPECTED_HEALTH_PATH = "/health"
DEPLOY_POLICY = "manual_after_devsystem_final_gate"
REQUIRED_DIAGNOSTIC_PATHS = (
    "/health",
    "/health/ready",
    "/health/details",
)


def evaluate_render_service(service: dict[str, Any]) -> dict[str, Any]:
    """Fail closed when Render drifts from the permanent production contract."""
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
    if observed["branch"] != EXPECTED_SOURCE_BRANCH:
        violations.append("source_branch_mismatch")
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
            "branch": EXPECTED_SOURCE_BRANCH,
            "auto_deploy": EXPECTED_AUTO_DEPLOY,
            "health_path": EXPECTED_HEALTH_PATH,
            "url": PUBLIC_URL,
        },
        "violations": violations,
    }
