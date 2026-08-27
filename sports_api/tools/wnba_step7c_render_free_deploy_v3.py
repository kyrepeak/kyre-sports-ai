#!/usr/bin/env python3
"""Step 7C v3: repair Render Free Docker settings and deploy frozen release.

Render's current API nests Docker configuration under
serviceDetails.envSpecificDetails. This operator repairs only that configuration
on the already free, diskless, auto-deploy-disabled Step 7C service, then
explicitly deploys the exact frozen Step 7B commit and verifies /health.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Mapping

import httpx

from sports_api.wnba_render_provisioning import RenderAPIClient, resolve_owner_id
import sports_api.tools.wnba_step7c_render_free_deploy as base

MODEL_VERSION = "wnba_step_7c_render_free_deploy_v3"
DOCKERFILE_PATH = "sports_api/Dockerfile"
DOCKER_CONTEXT = "."


class Step7CV3Error(RuntimeError):
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


def _details(service: Mapping[str, Any]) -> Mapping[str, Any]:
    value = service.get("serviceDetails")
    return value if isinstance(value, Mapping) else {}


def _docker_details(service: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _details(service).get("envSpecificDetails")
    return value if isinstance(value, Mapping) else {}


def build_free_service_payload(*, owner_id: str) -> dict[str, Any]:
    payload = {
        "type": "web_service",
        "name": base.SERVICE_NAME,
        "ownerId": owner_id,
        "repo": base.SOURCE_REPOSITORY,
        "branch": base.SOURCE_BRANCH,
        "autoDeploy": "no",
        "envVars": [
            {"key": key, "value": value}
            for key, value in sorted(
                {
                    **base.OFF_SWITCHES,
                    "WEB_CONCURRENCY": "1",
                    "WNBA_RELEASE_REVISION": base.SOURCE_REVISION,
                    "WNBA_RELEASE_ID": base.RELEASE_ID,
                    "WNBA_DEPLOYMENT_MODE": "render_free_preactivation",
                    "WNBA_DEPLOYMENT_REPLICA_COUNT": "1",
                }.items()
            )
        ],
        "serviceDetails": {
            "runtime": "docker",
            "envSpecificDetails": {
                "dockerfilePath": DOCKERFILE_PATH,
                "dockerContext": DOCKER_CONTEXT,
            },
            "healthCheckPath": "/health",
            "numInstances": 1,
            "plan": "free",
            "region": "oregon",
        },
    }
    validate_free_payload(payload)
    return payload


def validate_free_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("type") != "web_service":
        raise Step7CV3Error("Step 7C only permits a Render web service.")
    if payload.get("autoDeploy") != "no":
        raise Step7CV3Error("Step 7C requires auto-deploy OFF.")
    if payload.get("repo") != base.SOURCE_REPOSITORY or payload.get("branch") != base.SOURCE_BRANCH:
        raise Step7CV3Error("Step 7C source pin drifted.")
    details = payload.get("serviceDetails")
    if not isinstance(details, Mapping):
        raise Step7CV3Error("serviceDetails are required.")
    if details.get("runtime") != "docker":
        raise Step7CV3Error("Docker runtime is required.")
    if details.get("plan") != "free":
        raise Step7CV3Error("Step 7C refuses paid Render plans.")
    if "disk" in details:
        raise Step7CV3Error("Step 7C Free service must remain diskless.")
    if "maxShutdownDelaySeconds" in details:
        raise Step7CV3Error("Free service must omit maxShutdownDelaySeconds.")
    docker = details.get("envSpecificDetails")
    if not isinstance(docker, Mapping):
        raise Step7CV3Error("Docker-specific service details are required.")
    if docker.get("dockerfilePath") != DOCKERFILE_PATH:
        raise Step7CV3Error("Dockerfile path must target sports_api/Dockerfile.")
    if docker.get("dockerContext") != DOCKER_CONTEXT:
        raise Step7CV3Error("Docker context must remain repository root.")
    env_rows = payload.get("envVars")
    if not isinstance(env_rows, list):
        raise Step7CV3Error("Service env vars are required.")
    service_env = {str(r.get("key")): str(r.get("value")) for r in env_rows if isinstance(r, Mapping)}
    for key in base.OFF_SWITCHES:
        if service_env.get(key) != "false":
            raise Step7CV3Error(f"{key} must remain false.")
    forbidden = {"RENDER_API_KEY", "WNBA_KYRE_SUPABASE_SECRET_KEY", "SPORTSGAMEODDS_API_KEY", "GHCR_RENDER_TOKEN"}
    if forbidden.intersection(service_env):
        raise Step7CV3Error("Operator/database/provider credentials must not be injected into Render.")


def _validate_existing_service(service: Mapping[str, Any]) -> None:
    details = _details(service)
    if _clean(service.get("type")) not in {None, "web_service"}:
        raise Step7CV3Error("Existing service is not a web service.")
    if (_clean(details.get("runtime") or details.get("env")) or "").casefold() != "docker":
        raise Step7CV3Error("Existing service is not Docker-backed.")
    if (_clean(details.get("plan")) or "").casefold() != "free":
        raise Step7CV3Error("Existing service is not on Render Free.")
    if isinstance(details.get("disk"), Mapping):
        raise Step7CV3Error("Existing service unexpectedly has a persistent disk.")
    if _clean(service.get("repo")) not in {None, base.SOURCE_REPOSITORY}:
        raise Step7CV3Error("Existing service repo drifted.")
    if _clean(service.get("branch")) not in {None, base.SOURCE_BRANCH}:
        raise Step7CV3Error("Existing service branch drifted.")
    if (_clean(service.get("autoDeploy")) or "no").casefold() not in {"no", "false", "off"}:
        raise Step7CV3Error("Existing service has auto-deploy enabled.")


def _deploy_commit_id(deploy: Mapping[str, Any]) -> str | None:
    direct = _clean(deploy.get("commitId"))
    if direct:
        return direct.casefold()
    commit = deploy.get("commit")
    if isinstance(commit, Mapping):
        value = _clean(commit.get("id") or commit.get("sha"))
        return value.casefold() if value else None
    return None


def _list_deploys(client: RenderAPIClient, service_id: str) -> list[dict[str, Any]]:
    doc = client.request("GET", f"/v1/services/{service_id}/deploys", params={"limit": 20})
    if not isinstance(doc, list):
        return []
    out: list[dict[str, Any]] = []
    for row in doc:
        if not isinstance(row, dict):
            continue
        item = row.get("deploy") if isinstance(row.get("deploy"), dict) else row
        if isinstance(item, dict):
            out.append(item)
    return out


def _wait_for_new_deploy(client: RenderAPIClient, service_id: str, prior_ids: set[str], timeout_seconds: float = 60.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        for deploy in _list_deploys(client, service_id):
            did = _clean(deploy.get("id"))
            if did and did not in prior_ids and _deploy_commit_id(deploy) in {None, base.SOURCE_REVISION}:
                return deploy
        if time.monotonic() >= deadline:
            raise Step7CV3Error("Render accepted deploy request but no new deploy became observable.")
        time.sleep(2)


def _wait_live(client: RenderAPIClient, service_id: str, deploy_id: str, timeout_seconds: float = 900.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    failed = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    while True:
        deploy = client.get_deploy(service_id, deploy_id)
        status = (_clean(deploy.get("status")) or "").casefold()
        if status == "live":
            return deploy
        if status in failed:
            raise Step7CV3Error(f"Render deploy failed with status={status}.")
        if time.monotonic() >= deadline:
            raise Step7CV3Error(f"Timed out waiting for Render deploy; status={status or 'unknown'}.")
        time.sleep(5)


def _health(url: str, timeout_seconds: float = 180.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = "not attempted"
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        while True:
            try:
                r = client.get(url.rstrip("/") + "/health")
                if r.status_code == 200:
                    body = r.json()
                    if isinstance(body, dict) and body.get("status") == "ok":
                        return {"status_code": 200, "body_status": "ok"}
                    last = f"unexpected JSON: {body!r}"
                else:
                    last = f"HTTP {r.status_code}"
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
            if time.monotonic() >= deadline:
                raise Step7CV3Error(f"Render health verification failed: {last}")
            time.sleep(5)


def deploy_free_render_service(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = os.environ if env is None else env
    api_key = _clean(environment.get("RENDER_API_KEY"))
    if not api_key:
        raise Step7CV3Error("RENDER_API_KEY is required.")
    for key in base.OFF_SWITCHES:
        if _truthy(environment.get(key)):
            raise Step7CV3Error(f"Step 7C refuses to run while {key} is enabled.")

    requested_owner = _clean(environment.get("RENDER_OWNER_ID"))
    created = False
    patched = False
    with RenderAPIClient(api_key=api_key, timeout_seconds=30.0) as client:
        owner_id = resolve_owner_id(client, requested_owner)
        matches = client.list_services(owner_id, base.SERVICE_NAME)
        if len(matches) > 1:
            raise Step7CV3Error(f"Multiple Render services are named {base.SERVICE_NAME}.")

        if not matches:
            doc = client.create_service(build_free_service_payload(owner_id=owner_id))
            service = doc.get("service") if isinstance(doc, dict) and isinstance(doc.get("service"), dict) else doc
            if not isinstance(service, dict):
                raise Step7CV3Error("Render create-service response did not contain a service.")
            service_id = _clean(service.get("id"))
            if not service_id:
                raise Step7CV3Error("Created Render service has no ID.")
            created = True
        else:
            service_id = _clean(matches[0].get("id"))
            if not service_id:
                raise Step7CV3Error("Existing Render service has no ID.")
            service = client.get_service(service_id)
            _validate_existing_service(service)

            patch = {
                "autoDeploy": "no",
                "serviceDetails": {
                    "envSpecificDetails": {
                        "dockerfilePath": DOCKERFILE_PATH,
                        "dockerContext": DOCKER_CONTEXT,
                    },
                    "healthCheckPath": "/health",
                },
            }
            client.request("PATCH", f"/v1/services/{service_id}", json_body=patch, allowed=(200,))
            patched = True

        service = client.get_service(service_id)
        _validate_existing_service(service)
        docker = _docker_details(service)
        observed_path = _clean(docker.get("dockerfilePath"))
        observed_context = _clean(docker.get("dockerContext"))
        if observed_path not in {DOCKERFILE_PATH, "./" + DOCKERFILE_PATH}:
            raise Step7CV3Error(f"Render stored unexpected Dockerfile path: {observed_path!r}")
        if observed_context != DOCKER_CONTEXT:
            raise Step7CV3Error(f"Render stored unexpected Docker context: {observed_context!r}")

        prior = _list_deploys(client, service_id)
        prior_ids = {_clean(x.get("id")) for x in prior if _clean(x.get("id"))}
        deploy_doc = client.request(
            "POST",
            f"/v1/services/{service_id}/deploys",
            json_body={"commitId": base.SOURCE_REVISION, "clearCache": "clear"},
            allowed=(201, 202),
        )
        if isinstance(deploy_doc, dict) and _clean(deploy_doc.get("id")):
            deploy = deploy_doc
        else:
            deploy = _wait_for_new_deploy(client, service_id, prior_ids)

        deploy_id = _clean(deploy.get("id"))
        if not deploy_id:
            raise Step7CV3Error("Triggered Render deploy has no ID.")
        final_deploy = _wait_live(client, service_id, deploy_id)
        final_commit = _deploy_commit_id(final_deploy)
        if final_commit is not None and final_commit != base.SOURCE_REVISION:
            raise Step7CV3Error(f"Render deployed {final_commit}; expected {base.SOURCE_REVISION}.")

        final_service = client.get_service(service_id)
        _validate_existing_service(final_service)
        final_docker = _docker_details(final_service)
        final_path = _clean(final_docker.get("dockerfilePath"))
        if final_path not in {DOCKERFILE_PATH, "./" + DOCKERFILE_PATH}:
            raise Step7CV3Error("Dockerfile path drifted after deploy.")
        details = _details(final_service)
        service_url = _clean(details.get("url")) or _clean(final_service.get("url"))
        if not service_url or not service_url.startswith("https://"):
            raise Step7CV3Error("Render did not expose a valid HTTPS service URL.")

    health = _health(service_url)
    return {
        "source": "Kyre Sports API WNBA Step 7C Render Free v3 deployment",
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": "wnba_render_free_preactivation_live",
        "deployment_complete": True,
        "created_new_service": created,
        "patched_existing_service": patched,
        "source_release": {
            "repository": base.SOURCE_REPOSITORY,
            "branch": base.SOURCE_BRANCH,
            "revision": base.SOURCE_REVISION,
            "release_id": base.RELEASE_ID,
            "branch_was_pinned_before_render_call": True,
        },
        "render": {
            "service_id": service_id,
            "service_name": base.SERVICE_NAME,
            "service_url": service_url,
            "deploy_id": deploy_id,
            "deploy_status": "live",
            "observed_deploy_commit": final_commit,
            "runtime": _clean(details.get("runtime") or details.get("env")) or "docker",
            "plan": _clean(details.get("plan")) or "free",
            "region": _clean(details.get("region")) or "oregon",
            "dockerfile_path": final_path,
            "docker_context": _clean(_docker_details(final_service).get("dockerContext")),
            "persistent_disk_attached": isinstance(details.get("disk"), Mapping),
            "auto_deploy": _clean(final_service.get("autoDeploy")) or "no",
        },
        "health": health,
        "safety": {
            "render_plan_is_free": (_clean(details.get("plan")) or "").casefold() == "free",
            "paid_render_provisioning_authorized": False,
            "persistent_disk_attached": isinstance(details.get("disk"), Mapping),
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
        "compatibility": {
            "render_free_max_shutdown_delay_omitted": True,
            "docker_settings_nested_under_env_specific_details": True,
            "clean_build_cache_requested": True,
        },
    }


def main() -> int:
    print(json.dumps(deploy_free_render_service(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
