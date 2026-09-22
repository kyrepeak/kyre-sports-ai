"""WNBA Step 5U hosted-staging integration and remote verification.

Step 5U sits outside frozen Steps 5R/5S/5T. It proves that a real single-instance
HTTPS host presents the same immutable release, persistent-storage identity,
and fail-closed pre-activation state that we validated locally.

The first supported host adapter is Render because it supports Docker web
services, an HTTPS endpoint, a single service instance, and an attached
persistent disk. The core contract stays provider-neutral so a later host can
be added without changing the WNBA model or scheduler.

This module never calls a sportsbook provider and never runs Monte Carlo.
Remote verification is GET-only and never calls the manual refresh endpoint.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.wnba_deployment_smoke_readiness import normalize_smoke_base_url
from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV
from sports_api.wnba_release_activation_readiness import get_release_readiness

MODEL_SOURCE = "Kyre Sports API WNBA Step 5U hosted staging readiness"
MODEL_VERSION = "wnba_step_5u_hosted_staging_readiness_v1"
SCHEMA_VERSION = "wnba_step_5u_hosted_staging_readiness_v1"

HOST_PROVIDER_ENV = "WNBA_STAGING_HOST_PROVIDER"
HOST_ENVIRONMENT_ENV = "WNBA_HOST_ENVIRONMENT"
STAGING_EXTERNAL_URL_ENV = "WNBA_STAGING_EXTERNAL_URL"
EXPECTED_SERVICE_NAME_ENV = "WNBA_STAGING_EXPECTED_SERVICE_NAME"
EXPECTED_GIT_BRANCH_ENV = "WNBA_STAGING_EXPECTED_GIT_BRANCH"
ALLOW_CUSTOM_DOMAIN_ENV = "WNBA_STAGING_ALLOW_CUSTOM_DOMAIN"

RENDER_FLAG_ENV = "RENDER"
RENDER_SERVICE_ID_ENV = "RENDER_SERVICE_ID"
RENDER_SERVICE_NAME_ENV = "RENDER_SERVICE_NAME"
RENDER_SERVICE_TYPE_ENV = "RENDER_SERVICE_TYPE"
RENDER_EXTERNAL_URL_ENV = "RENDER_EXTERNAL_URL"
RENDER_EXTERNAL_HOSTNAME_ENV = "RENDER_EXTERNAL_HOSTNAME"
RENDER_GIT_COMMIT_ENV = "RENDER_GIT_COMMIT"
RENDER_GIT_BRANCH_ENV = "RENDER_GIT_BRANCH"
RENDER_GIT_REPO_SLUG_ENV = "RENDER_GIT_REPO_SLUG"
RENDER_INSTANCE_ID_ENV = "RENDER_INSTANCE_ID"

DEFAULT_PROVIDER = "render"
DEFAULT_HOST_ENVIRONMENT = "staging"
DEFAULT_EXPECTED_BRANCH = "api-foundation-v1"
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


class WNBAHostedStagingError(RuntimeError):
    pass


class WNBAHostedStagingNotReadyError(WNBAHostedStagingError):
    pass


class WNBAHostedStagingVerificationError(WNBAHostedStagingError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(environment: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = environment.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _valid_sha40(value: str | None) -> bool:
    return bool(value and _SHA40_RE.fullmatch(value.casefold()))


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    return normalize_smoke_base_url(value)


def _host(value: str | None) -> str | None:
    if not value:
        return None
    return (urlparse(value).hostname or "").casefold() or None


def build_hosted_staging_smoke_plan(base_url: str) -> dict[str, Any]:
    """Return the exact GET-only verification plan for a hosted staging API."""
    normalized = normalize_smoke_base_url(base_url)
    requests = [
        {"name": "service_health", "method": "GET", "path": "/health", "allowed_statuses": [200]},
        {"name": "step_5r_readiness", "method": "GET", "path": "/api/v1/wnba/runtime/readiness", "allowed_statuses": [200]},
        {"name": "step_5s_deployment", "method": "GET", "path": "/api/v1/wnba/runtime/deployment", "allowed_statuses": [200]},
        {"name": "step_5t_release", "method": "GET", "path": "/api/v1/wnba/runtime/release", "allowed_statuses": [200]},
        {"name": "step_5u_hosting", "method": "GET", "path": "/api/v1/wnba/runtime/hosting", "allowed_statuses": [200]},
        {"name": "runtime_health_pre_activation", "method": "GET", "path": "/api/v1/wnba/runtime/health", "allowed_statuses": [503]},
        {
            "name": "current_board_read",
            "method": "GET",
            "path": "/api/v1/wnba/rankings/player-props/current?require_current=true",
            "allowed_statuses": [200, 409],
        },
    ]
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "base_url": normalized,
        "request_count": len(requests),
        "requests": requests,
        "safety": {
            "read_only": True,
            "all_methods_are_get": True,
            "manual_refresh_endpoint_is_not_called": True,
            "sportsbook_collection_is_not_intentionally_triggered": True,
            "monte_carlo_rebuild_is_not_intentionally_triggered": True,
            "requires_pre_activation_runtime_503": True,
        },
    }


def get_hosted_staging_readiness(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return sanitized hosting readiness for the deployed staging instance."""
    environment = _environment(env)
    step5t = get_release_readiness(env=environment)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str, *, required: bool = True) -> None:
        checks.append({"name": name, "required": required, "passed": bool(passed), "detail": detail})
        if required and not passed:
            blockers.append(f"{name}: {detail}")

    provider = (_clean(environment.get(HOST_PROVIDER_ENV)) or DEFAULT_PROVIDER).casefold()
    host_environment = (_clean(environment.get(HOST_ENVIRONMENT_ENV)) or DEFAULT_HOST_ENVIRONMENT).casefold()
    expected_service = _clean(environment.get(EXPECTED_SERVICE_NAME_ENV))
    expected_branch = _clean(environment.get(EXPECTED_GIT_BRANCH_ENV)) or DEFAULT_EXPECTED_BRANCH
    allow_custom_domain = _truthy(environment, ALLOW_CUSTOM_DOMAIN_ENV, False)
    activation_requested = _truthy(environment, ACTIVATION_ENV, False)

    configured_url_raw = _clean(environment.get(STAGING_EXTERNAL_URL_ENV))
    render_url_raw = _clean(environment.get(RENDER_EXTERNAL_URL_ENV))
    configured_url: str | None = None
    render_url: str | None = None
    url_error: str | None = None
    try:
        configured_url = _safe_url(configured_url_raw)
        render_url = _safe_url(render_url_raw)
    except Exception as exc:
        url_error = str(exc)

    render_commit = (_clean(environment.get(RENDER_GIT_COMMIT_ENV)) or "").casefold() or None
    render_branch = _clean(environment.get(RENDER_GIT_BRANCH_ENV))
    render_service_id = _clean(environment.get(RENDER_SERVICE_ID_ENV))
    render_service_name = _clean(environment.get(RENDER_SERVICE_NAME_ENV))
    render_service_type = (_clean(environment.get(RENDER_SERVICE_TYPE_ENV)) or "").casefold() or None
    render_repo_slug = _clean(environment.get(RENDER_GIT_REPO_SLUG_ENV))
    render_instance_id = _clean(environment.get(RENDER_INSTANCE_ID_ENV))
    release = step5t.get("release") or {}
    release_revision = (release.get("revision") or "").casefold() or None

    add("supported_host_provider", provider == DEFAULT_PROVIDER, "Render is the Step 5U staging adapter." if provider == DEFAULT_PROVIDER else "Step 5U currently supports WNBA_STAGING_HOST_PROVIDER=render only.")
    add("staging_environment_only", host_environment == DEFAULT_HOST_ENVIRONMENT, "Hosted environment is staging." if host_environment == DEFAULT_HOST_ENVIRONMENT else "Step 5U must run with WNBA_HOST_ENVIRONMENT=staging.")
    add("render_runtime_detected", _truthy(environment, RENDER_FLAG_ENV, False), "Render runtime marker is present." if _truthy(environment, RENDER_FLAG_ENV, False) else "RENDER=true was not detected.")
    add("render_web_service", render_service_type == "web", "Render service type is web." if render_service_type == "web" else "RENDER_SERVICE_TYPE must be web.")
    add("render_service_id_present", bool(render_service_id), "Render service ID is present." if render_service_id else "RENDER_SERVICE_ID is missing.")
    add("render_service_name_present", bool(render_service_name), "Render service name is present." if render_service_name else "RENDER_SERVICE_NAME is missing.")
    if expected_service:
        add("expected_service_name_matches", render_service_name == expected_service, "Render service name matches the expected staging service." if render_service_name == expected_service else "Render service name does not match WNBA_STAGING_EXPECTED_SERVICE_NAME.")

    add("staging_external_url_configured", bool(configured_url_raw), "Explicit staging HTTPS URL is configured." if configured_url_raw else f"{STAGING_EXTERNAL_URL_ENV} is missing.")
    add("staging_external_url_valid", bool(configured_url) and url_error is None, "Staging external URL is valid." if configured_url and not url_error else url_error or "Staging external URL is invalid.")
    add("render_external_url_valid", bool(render_url) and url_error is None, "Render external URL is valid." if render_url and not url_error else url_error or "RENDER_EXTERNAL_URL is missing or invalid.")
    add("configured_url_matches_render", bool(configured_url and render_url and configured_url == render_url), "Configured staging URL matches Render's external URL." if configured_url and render_url and configured_url == render_url else "Configured staging URL does not match RENDER_EXTERNAL_URL.")

    hostname = _host(configured_url)
    render_domain_ok = bool(hostname and hostname.endswith(".onrender.com"))
    add(
        "render_hostname_policy",
        render_domain_ok or allow_custom_domain,
        "Render onrender.com hostname verified." if render_domain_ok else "Custom HTTPS hostname explicitly allowed." if allow_custom_domain and hostname else "Staging hostname must be an onrender.com host unless custom domains are explicitly allowed.",
    )

    add("render_git_commit_valid", _valid_sha40(render_commit), "Render exposes a full Git commit SHA." if _valid_sha40(render_commit) else "RENDER_GIT_COMMIT must be a full 40-character SHA.")
    add("render_commit_matches_release", bool(render_commit and release_revision and render_commit == release_revision), "Render Git commit matches Step 5T release revision." if render_commit and release_revision and render_commit == release_revision else "Render Git commit does not match the Step 5T release revision.")
    add("render_git_branch_matches", render_branch == expected_branch, f"Render branch matches {expected_branch}." if render_branch == expected_branch else f"RENDER_GIT_BRANCH must match {expected_branch}.")
    add("render_repo_slug_present", bool(render_repo_slug), "Render repository slug is present." if render_repo_slug else "RENDER_GIT_REPO_SLUG is missing.")
    add("render_instance_id_present", bool(render_instance_id), "Render instance identity is present." if render_instance_id else "RENDER_INSTANCE_ID is missing.")

    add("frozen_step_5t_release_ready", step5t.get("release_ready") is True, "Frozen Step 5T release gate is green." if step5t.get("release_ready") is True else "Frozen Step 5T release gate is not green.")
    add("pre_activation_phase_required", step5t.get("phase") == "pre_activation_ready", "Release is in the required pre-activation phase." if step5t.get("phase") == "pre_activation_ready" else "Hosted staging must be deployed in Step 5T pre_activation_ready phase.")
    add("runtime_remains_disabled", not activation_requested, "Production runtime remains disabled during first hosted staging verification." if not activation_requested else "WNBA_PRODUCTION_RUNTIME_ENABLED must remain false during Step 5U initial hosted verification.")

    step5s = step5t.get("step_5s") or {}
    add("step_5s_deployment_ready", step5s.get("deployment_ready") is True, "Frozen Step 5S deployment gate is green." if step5s.get("deployment_ready") is True else "Frozen Step 5S deployment gate is not green.")
    storage_identity = step5t.get("storage_identity_sha256")
    add("storage_identity_present", isinstance(storage_identity, str) and len(storage_identity) == 64, "Persistent storage identity is available." if isinstance(storage_identity, str) and len(storage_identity) == 64 else "Step 5T storage identity is unavailable.")

    host_contract_ready = not blockers
    identity_payload = {
        "provider": provider,
        "environment": host_environment,
        "external_url": configured_url,
        "service_id": render_service_id,
        "service_name": render_service_name,
        "service_type": render_service_type,
        "instance_id": render_instance_id,
        "repo_slug": render_repo_slug,
        "git_branch": render_branch,
        "git_commit": render_commit,
        "release_manifest": release.get("manifest_fingerprint_sha256"),
        "storage_identity": storage_identity,
    }
    host_identity = _hash(identity_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_hosted_staging_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "host_contract_ready": host_contract_ready,
        "remote_smoke_allowed": host_contract_ready and not activation_requested,
        "activation_requested": activation_requested,
        "provider": provider,
        "environment": host_environment,
        "external_url": configured_url,
        "host": {
            "provider": provider,
            "service_id": render_service_id,
            "service_name": render_service_name,
            "service_type": render_service_type,
            "instance_id": render_instance_id,
            "repository": render_repo_slug,
            "git_branch": render_branch,
            "git_commit": render_commit,
            "external_hostname": _clean(environment.get(RENDER_EXTERNAL_HOSTNAME_ENV)),
            "custom_domain_allowed": allow_custom_domain,
        },
        "release": {
            "release_id": release.get("release_id"),
            "revision": release_revision,
            "image_ref": release.get("image_ref"),
            "manifest_fingerprint_sha256": release.get("manifest_fingerprint_sha256"),
            "phase": step5t.get("phase"),
        },
        "storage_identity_sha256": storage_identity,
        "host_identity_sha256": host_identity,
        "checks": checks,
        "blocking_reasons": blockers,
        "semantics": {
            "single_host_adapter": "render",
            "https_required": True,
            "one_service_instance_required_by_step_5s": True,
            "persistent_disk_required_by_step_5s": True,
            "runtime_must_remain_disabled_for_initial_remote_verification": True,
            "remote_verification_is_get_only": True,
            "manual_refresh_endpoint_is_not_called": True,
            "sportsbook_collection_is_not_intentionally_triggered": True,
            "monte_carlo_rebuild_is_not_intentionally_triggered": True,
            "frozen_step_5t_release_identity_remains_authoritative": True,
        },
    }


def require_hosted_staging_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_hosted_staging_readiness(env=env)
    if report.get("host_contract_ready") is not True:
        raise WNBAHostedStagingNotReadyError("WNBA Step 5U hosted staging gate is not ready: " + "; ".join(report.get("blocking_reasons") or []))
    return report


def _safe_json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def run_hosted_staging_smoke(
    base_url: str,
    *,
    expected_revision: str,
    expected_release_id: str,
    expected_storage_identity: str,
    expected_service_name: str | None = None,
    timeout_seconds: float = 10.0,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run GET-only hosted staging verification against a real HTTPS API."""
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise ValueError("timeout_seconds must be greater than 0 and no more than 60.")
    if not _valid_sha40(expected_revision):
        raise ValueError("expected_revision must be a full 40-character Git SHA.")
    if not expected_release_id.strip():
        raise ValueError("expected_release_id is required.")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_storage_identity.casefold()):
        raise ValueError("expected_storage_identity must be a 64-character sha256 hex value.")

    normalized = normalize_smoke_base_url(base_url)
    plan = build_hosted_staging_smoke_plan(normalized)
    owned_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
    results: list[dict[str, Any]] = []
    observed: dict[str, Any] = {}
    try:
        for item in plan["requests"]:
            url = normalized + item["path"]
            try:
                response = http_client.get(url, timeout=timeout_seconds)
                status = int(response.status_code)
                body = _safe_json(response)
                passed = status in item["allowed_statuses"]
                detail = f"HTTP {status}"

                if item["name"] == "step_5t_release" and status == 200 and isinstance(body, Mapping):
                    release = body.get("release") or {}
                    observed["revision"] = release.get("revision")
                    observed["release_id"] = release.get("release_id")
                    observed["storage_identity_sha256"] = body.get("storage_identity_sha256")
                    observed["phase"] = body.get("phase")
                    passed = passed and observed["phase"] == "pre_activation_ready"
                    detail += "; pre-activation release observed"

                if item["name"] == "step_5u_hosting" and status == 200 and isinstance(body, Mapping):
                    host = body.get("host") or {}
                    observed["provider"] = body.get("provider")
                    observed["service_name"] = host.get("service_name")
                    observed["host_contract_ready"] = body.get("host_contract_ready")
                    observed["host_identity_sha256"] = body.get("host_identity_sha256")
                    passed = passed and body.get("host_contract_ready") is True and body.get("activation_requested") is False
                    detail += "; hosted contract observed"

                if item["name"] == "step_5r_readiness" and status == 200 and isinstance(body, Mapping):
                    passed = passed and body.get("activation_requested") is False
                    detail += "; runtime activation remains off"

                results.append({
                    "name": item["name"],
                    "method": "GET",
                    "path": item["path"],
                    "status_code": status,
                    "passed": bool(passed),
                    "detail": detail,
                })
            except Exception as exc:
                results.append({
                    "name": item["name"],
                    "method": "GET",
                    "path": item["path"],
                    "status_code": None,
                    "passed": False,
                    "detail": f"request failed: {type(exc).__name__}: {exc}",
                })
    finally:
        if owned_client:
            http_client.close()

    identity_checks = [
        {"name": "revision_matches", "passed": observed.get("revision") == expected_revision.casefold()},
        {"name": "release_id_matches", "passed": observed.get("release_id") == expected_release_id},
        {"name": "storage_identity_matches", "passed": observed.get("storage_identity_sha256") == expected_storage_identity.casefold()},
        {"name": "provider_is_render", "passed": observed.get("provider") == DEFAULT_PROVIDER},
    ]
    if expected_service_name:
        identity_checks.append({"name": "service_name_matches", "passed": observed.get("service_name") == expected_service_name})

    passed_count = sum(1 for row in results if row["passed"])
    all_identity = all(row["passed"] for row in identity_checks)
    passed = passed_count == len(results) and all_identity
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_hosted_staging_smoke_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "base_url": normalized,
        "passed": passed,
        "check_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "results": results,
        "identity_checks": identity_checks,
        "observed": observed,
        "safety": plan["safety"],
    }
