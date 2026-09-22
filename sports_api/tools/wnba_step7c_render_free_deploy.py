#!/usr/bin/env python3
"""Step 7C: deploy the frozen WNBA FastAPI release to a free Render web service.

This operator is intentionally pre-activation only. It creates/reuses a Render
web service on the Free plan, deploys the exact Step 7B merge commit from a
pinned branch, verifies /health, and returns sanitized evidence.

It never enables the WNBA production runtime, scheduler, sportsbook sync,
Supabase writes, Monte Carlo, or wager actions. It never returns Render API
credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Mapping

import httpx

from sports_api.wnba_render_provisioning import RenderAPIClient, resolve_owner_id

MODEL_VERSION = "wnba_step_7c_render_free_deploy_v1"
SOURCE_REPOSITORY = "https://github.com/kyrepeak/kyre-sports-ai"
SOURCE_BRANCH = "wnba-production-7c-20260827"
SOURCE_REVISION = "12b9a0bb21e72f16282f562d848673222d48c7f2"
SERVICE_NAME = "kyre-sports-api"
RELEASE_ID = f"wnba-step7c-{SOURCE_REVISION[:12]}"
RENDER_API_KEY_ENV = "RENDER_API_KEY"
RENDER_OWNER_ID_ENV = "RENDER_OWNER_ID"

OFF_SWITCHES = {
    "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
    "WNBA_STEP6J_CANARY_ENABLED": "false",
}


class Step7CRenderError(RuntimeError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _service_details(service: Mapping[str, Any]) -> Mapping[str, Any]:
    value = service.get("serviceDetails")
    return value if isinstance(value, Mapping) else {}


def _service_url(service: Mapping[str, Any]) -> str | None:
    details = _service_details(service)
    value = _clean(details.get("url")) or _clean(service.get("url"))
    return value.rstrip("/") if value else None


def _unwrap_created_service(document: Any) -> dict[str, Any]:
    if isinstance(document, dict) and isinstance(document.get("service"), dict):
        return document["service"]
    if isinstance(document, dict) and _clean(document.get("id")):
        return document
    raise Step7CRenderError("Render create-service response did not contain a service object.")


def _unwrap_created_deploy(document: Any) -> dict[str, Any] | None:
    if isinstance(document, dict) and isinstance(document.get("deploy"), dict):
        return document["deploy"]
    return None


def _list_deploys(client: RenderAPIClient, service_id: str) -> list[dict[str, Any]]:
    document = client.request("GET", f"/v1/services/{service_id}/deploys", params={"limit": 20})
    if not isinstance(document, list):
        return []
    out: list[dict[str, Any]] = []
    for row in document:
        if not isinstance(row, dict):
            continue
        deploy = row.get("deploy") if isinstance(row.get("deploy"), dict) else row
        if isinstance(deploy, dict):
            out.append(deploy)
    return out


def _deploy_commit_id(deploy: Mapping[str, Any]) -> str | None:
    direct = _clean(deploy.get("commitId"))
    if direct:
        return direct.casefold()
    commit = deploy.get("commit")
    if isinstance(commit, Mapping):
        value = _clean(commit.get("id") or commit.get("sha"))
        return value.casefold() if value else None
    return None


def build_free_service_payload(*, owner_id: str) -> dict[str, Any]:
    payload = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "ownerId": owner_id,
        "repo": SOURCE_REPOSITORY,
        "branch": SOURCE_BRANCH,
        "autoDeploy": "no",
        "envVars": [
            {"key": key, "value": value}
            for key, value in sorted(
                {
                    **OFF_SWITCHES,
                    "WEB_CONCURRENCY": "1",
                    "WNBA_RELEASE_REVISION": SOURCE_REVISION,
                    "WNBA_RELEASE_ID": RELEASE_ID,
                    "WNBA_DEPLOYMENT_MODE": "render_free_preactivation",
                    "WNBA_DEPLOYMENT_REPLICA_COUNT": "1",
                }.items()
            )
        ],
        "serviceDetails": {
            "runtime": "docker",
            "healthCheckPath": "/health",
            "numInstances": 1,
            "plan": "free",
            "region": "oregon",
            "dockerfilePath": "sports_api/Dockerfile",
            "dockerContext": ".",
            "maxShutdownDelaySeconds": 30,
        },
    }
    validate_free_payload(payload)
    return payload


def validate_free_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("type") != "web_service":
        raise Step7CRenderError("Step 7C only permits a Render web service.")
    if payload.get("autoDeploy") != "no":
        raise Step7CRenderError("Step 7C requires Render auto-deploy OFF.")
    if payload.get("repo") != SOURCE_REPOSITORY or payload.get("branch") != SOURCE_BRANCH:
        raise Step7CRenderError("Step 7C source repository/branch drifted from the frozen release pin.")
    details = payload.get("serviceDetails")
    if not isinstance(details, Mapping):
        raise Step7CRenderError("Step 7C serviceDetails are required.")
    if details.get("runtime") != "docker":
        raise Step7CRenderError("Step 7C requires the frozen Docker runtime.")
    if details.get("plan") != "free":
        raise Step7CRenderError("Step 7C refuses every paid Render plan.")
    if "disk" in details:
        raise Step7CRenderError("Step 7C Free service must not attach a persistent disk.")
    if details.get("numInstances") != 1:
        raise Step7CRenderError("Step 7C Free service must use exactly one instance.")
    rows = payload.get("envVars")
    if not isinstance(rows, list):
        raise Step7CRenderError("Step 7C envVars are required.")
    env = {str(row.get("key")): str(row.get("value")) for row in rows if isinstance(row, Mapping)}
    for key in OFF_SWITCHES:
        if env.get(key) != "false":
            raise Step7CRenderError(f"Step 7C requires {key}=false.")
    forbidden_secret_keys = {
        "RENDER_API_KEY",
        "WNBA_KYRE_SUPABASE_SECRET_KEY",
        "SPORTSGAMEODDS_API_KEY",
        "GHCR_RENDER_TOKEN",
    }
    if forbidden_secret_keys.intersection(env):
        raise Step7CRenderError("Operator/service credentials must not be injected during Step 7C.")


def _validate_existing_service(service: Mapping[str, Any]) -> None:
    details = _service_details(service)
    if _clean(service.get("type")) not in {None, "web_service"}:
        raise Step7CRenderError("Existing Render service with Step 7C name is not a web service.")
    runtime = (_clean(details.get("runtime") or details.get("env")) or "").casefold()
    if runtime and runtime != "docker":
        raise Step7CRenderError("Existing Render service with Step 7C name is not Docker-backed.")
    plan = (_clean(details.get("plan")) or "").casefold()
    if plan and plan != "free":
        raise Step7CRenderError("Existing Render service with Step 7C name is not on the Free plan.")
    if isinstance(details.get("disk"), Mapping):
        raise Step7CRenderError("Existing Render service unexpectedly has a persistent disk.")
    branch = _clean(service.get("branch"))
    repo = _clean(service.get("repo"))
    if branch and branch != SOURCE_BRANCH:
        raise Step7CRenderError("Existing Render service is linked to a different branch.")
    if repo and repo.rstrip("/") != SOURCE_REPOSITORY.rstrip("/"):
        raise Step7CRenderError("Existing Render service is linked to a different repository.")
    auto = _clean(service.get("autoDeploy"))
    if auto and auto.casefold() not in {"no", "false", "off"}:
        raise Step7CRenderError("Existing Render service has auto-deploy enabled.")


def _wait_for_live(client: RenderAPIClient, *, service_id: str, deploy_id: str, timeout_seconds: float = 900.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    failure_states = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    while True:
        deploy = client.get_deploy(service_id, deploy_id)
        status = (_clean(deploy.get("status")) or "").casefold()
        if status == "live":
            return deploy
        if status in failure_states:
            raise Step7CRenderError(f"Render deploy failed with status={status}.")
        if time.monotonic() >= deadline:
            raise Step7CRenderError(f"Timed out waiting for Render deploy; last status={status or 'unknown'}.")
        time.sleep(5)


def _verify_health(url: str, timeout_seconds: float = 150.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        while True:
            try:
                response = client.get(url.rstrip("/") + "/health")
                if response.status_code == 200:
                    body = response.json()
                    if isinstance(body, dict) and body.get("status") == "ok":
                        return {"status_code": 200, "body_status": "ok"}
                    last_error = f"unexpected health JSON: {body!r}"
                else:
                    last_error = f"HTTP {response.status_code}"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if time.monotonic() >= deadline:
                raise Step7CRenderError(f"Render /health verification failed: {last_error}")
            time.sleep(5)


def deploy_free_render_service(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = os.environ if env is None else env
    api_key = _clean(environment.get(RENDER_API_KEY_ENV))
    if not api_key:
        raise Step7CRenderError("RENDER_API_KEY is required in the GitHub Actions secret context.")
    for key in OFF_SWITCHES:
        if _truthy(environment.get(key)):
            raise Step7CRenderError(f"Step 7C refuses to run while {key} is enabled.")

    requested_owner = _clean(environment.get(RENDER_OWNER_ID_ENV))
    created = False
    with RenderAPIClient(api_key=api_key, timeout_seconds=30.0) as client:
        owner_id = resolve_owner_id(client, requested_owner)
        payload = build_free_service_payload(owner_id=owner_id)
        existing = client.list_services(owner_id, SERVICE_NAME)
        if len(existing) > 1:
            raise Step7CRenderError(f"Multiple Render services are named {SERVICE_NAME}.")

        initial_deploy: dict[str, Any] | None = None
        if existing:
            service_id = _clean(existing[0].get("id"))
            if not service_id:
                raise Step7CRenderError("Existing Render service has no ID.")
            service = client.get_service(service_id)
            _validate_existing_service(service)
        else:
            document = client.create_service(payload)
            service = _unwrap_created_service(document)
            initial_deploy = _unwrap_created_deploy(document)
            service_id = _clean(service.get("id"))
            if not service_id:
                raise Step7CRenderError("Created Render service has no ID.")
            created = True

        service = client.get_service(service_id)
        _validate_existing_service(service)

        deploy = initial_deploy
        if deploy is None:
            deploys = _list_deploys(client, service_id)
            deploy = deploys[0] if deploys else None

        # Creation from the pinned branch should already deploy the exact release.
        # For an existing service, or if no deploy is discoverable, explicitly
        # request the frozen Step 7B commit with auto-deploy still disabled.
        deploy_commit = _deploy_commit_id(deploy or {})
        if deploy is None or (deploy_commit is not None and deploy_commit != SOURCE_REVISION):
            deploy = client.request(
                "POST",
                f"/v1/services/{service_id}/deploys",
                json_body={"commitId": SOURCE_REVISION, "clearCache": "do_not_clear"},
                allowed=(201, 202),
            )
            if not isinstance(deploy, dict):
                raise Step7CRenderError("Render trigger-deploy response was not an object.")

        deploy_id = _clean(deploy.get("id"))
        if not deploy_id:
            raise Step7CRenderError("Render deploy has no ID.")
        final_deploy = _wait_for_live(client, service_id=service_id, deploy_id=deploy_id)
        final_commit = _deploy_commit_id(final_deploy)
        if final_commit is not None and final_commit != SOURCE_REVISION:
            raise Step7CRenderError(
                f"Render deployed commit {final_commit}, expected frozen revision {SOURCE_REVISION}."
            )

        final_service = client.get_service(service_id)
        _validate_existing_service(final_service)
        service_url = _service_url(final_service)
        if not service_url or not service_url.startswith("https://"):
            raise Step7CRenderError("Render service did not expose a valid HTTPS URL.")

    health = _verify_health(service_url)
    details = _service_details(final_service)
    return {
        "source": "Kyre Sports API WNBA Step 7C free Render deployment",
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": "wnba_render_free_preactivation_live",
        "deployment_complete": True,
        "created_new_service": created,
        "source_release": {
            "repository": SOURCE_REPOSITORY,
            "branch": SOURCE_BRANCH,
            "revision": SOURCE_REVISION,
            "release_id": RELEASE_ID,
            "branch_was_pinned_before_render_call": True,
        },
        "render": {
            "service_id": service_id,
            "service_name": SERVICE_NAME,
            "service_url": service_url,
            "deploy_id": deploy_id,
            "deploy_status": "live",
            "observed_deploy_commit": final_commit,
            "runtime": _clean(details.get("runtime") or details.get("env")) or "docker",
            "plan": _clean(details.get("plan")) or "free",
            "region": _clean(details.get("region")) or "oregon",
            "persistent_disk_attached": isinstance(details.get("disk"), Mapping),
            "auto_deploy": _clean(final_service.get("autoDeploy")) or "no",
        },
        "health": health,
        "safety": {
            "render_plan_is_free": True,
            "paid_render_provisioning_authorized": False,
            "persistent_disk_attached": False,
            "production_runtime_enabled": False,
            "scheduler_authorized": False,
            "scheduler_started": False,
            "direct_sync_enabled": False,
            "reconciled_sync_enabled": False,
            "step6j_canary_enabled": False,
            "supabase_credentials_injected": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "render_api_key_returned": False,
        },
    }


def main() -> int:
    print(json.dumps(deploy_free_render_service(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
