#!/usr/bin/env python3
"""Step 7E: deploy the certified WNBA schedule transport hotfix to Render.

This operator mutates only the existing Render Free service's source branch and
triggers an explicit deploy of the exact certified hotfix SHA. It verifies the
existing Supabase wiring and all production/scheduler/write switches before
mutation, then performs only read-only HTTP checks against the hosted API.

It does not change Supabase data, enable runtime/sync/scheduler switches, call a
sportsbook, run Monte Carlo, or expose any secret value.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Mapping

import httpx

from sports_api.wnba_render_provisioning import RenderAPIClient, resolve_owner_id
import sports_api.tools.wnba_step7c_render_free_deploy as step7c

MODEL_VERSION = "wnba_step_7e_schedule_hotfix_deploy_v1"
PATCH_BRANCH = "wnba-production-7e-schedule-fix-20260827"
PATCH_REVISION = "9a45b11704bb95ec5ace275b5dd941e27e32f745"
PATCH_PARENT_REVISION = "12b9a0bb21e72f16282f562d848673222d48c7f2"
SERVICE_URL = "https://kyre-sports-api.onrender.com"
EXPECTED_SUPABASE_URL = "https://jqajcdckalsfizbvngiu.supabase.co"
EXPECTED_SUPABASE_HOST = "jqajcdckalsfizbvngiu.supabase.co"
EXPECTED_SCHEDULE_SOURCE_URL = "https://www.wnba.com/api/schedule"
EXPECTED_SCHEDULE_SOURCE_VARIANT = "wnba_public_schedule_api"
LEGACY_STEP6U_BLOCKER = "Step 5W pre-activation checkpoint is not ready."
OFF_SWITCHES = dict(step7c.OFF_SWITCHES)


class Step7EHotfixDeployError(RuntimeError):
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


def _deploy_commit_id(deploy: Mapping[str, Any]) -> str | None:
    direct = _clean(deploy.get("commitId"))
    if direct:
        return direct.casefold()
    commit = deploy.get("commit")
    if isinstance(commit, Mapping):
        value = _clean(commit.get("id") or commit.get("sha"))
        return value.casefold() if value else None
    return None


def _wait_live(client: RenderAPIClient, service_id: str, deploy_id: str, timeout_seconds: float = 900.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    failed = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    while True:
        deploy = client.get_deploy(service_id, deploy_id)
        status = (_clean(deploy.get("status")) or "").casefold()
        if status == "live":
            return deploy
        if status in failed:
            raise Step7EHotfixDeployError(f"Render hotfix deploy failed with status={status}.")
        if time.monotonic() >= deadline:
            raise Step7EHotfixDeployError(f"Timed out waiting for hotfix deploy; status={status or 'unknown'}.")
        time.sleep(5)


def _get_json(path: str, *, timeout_seconds: float = 180.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = "not attempted"
    with httpx.Client(timeout=25.0, follow_redirects=True, headers={"user-agent": "kyre-sports-api-step7e-hotfix/1"}) as client:
        while True:
            try:
                response = client.get(SERVICE_URL + path)
                if response.status_code == 200:
                    body = response.json()
                    if isinstance(body, dict):
                        return body
                    last = "non-object JSON"
                else:
                    last = f"HTTP {response.status_code}"
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
            if time.monotonic() >= deadline:
                raise Step7EHotfixDeployError(f"Hosted verification failed for {path}: {last}")
            time.sleep(5)


def _validate_existing_service(service: Mapping[str, Any]) -> None:
    details = _details(service)
    if _clean(service.get("type")) not in {None, "web_service"}:
        raise Step7EHotfixDeployError("Existing Render service is not a web service.")
    if (_clean(details.get("runtime") or details.get("env")) or "").casefold() != "docker":
        raise Step7EHotfixDeployError("Existing Render service is not Docker-backed.")
    if (_clean(details.get("plan")) or "").casefold() != "free":
        raise Step7EHotfixDeployError("Step 7E refuses to alter a non-Free Render service.")
    if isinstance(details.get("disk"), Mapping):
        raise Step7EHotfixDeployError("Existing Render service unexpectedly has a persistent disk.")
    if _clean(service.get("repo")) != step7c.SOURCE_REPOSITORY:
        raise Step7EHotfixDeployError("Render repository drifted.")
    if (_clean(service.get("autoDeploy")) or "no").casefold() not in {"no", "false", "off"}:
        raise Step7EHotfixDeployError("Render auto-deploy must remain OFF.")


def _env_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = _clean(row.get("key"))
        value = row.get("value")
        if key and value is not None:
            out[key] = str(value)
    return out


def _validate_render_environment(values: Mapping[str, str]) -> None:
    if values.get("WNBA_KYRE_DURABLE_STORAGE_BACKEND") != "supabase":
        raise Step7EHotfixDeployError("Render is no longer configured for the Supabase durable backend.")
    if values.get("WNBA_KYRE_SUPABASE_URL") != EXPECTED_SUPABASE_URL:
        raise Step7EHotfixDeployError("Render Supabase project URL drifted.")
    secret = _clean(values.get("WNBA_KYRE_SUPABASE_SECRET_KEY"))
    if not secret or len(secret) < 20:
        raise Step7EHotfixDeployError("Render Supabase server secret is missing.")
    for name in OFF_SWITCHES:
        if _truthy(values.get(name)):
            raise Step7EHotfixDeployError(f"Step 7E refuses deployment while {name} is enabled.")


def deploy_schedule_hotfix(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = os.environ if env is None else env
    render_key = _clean(environment.get("RENDER_API_KEY"))
    if not render_key or len(render_key) < 20:
        raise Step7EHotfixDeployError("RENDER_API_KEY is required.")
    requested_owner = _clean(environment.get("RENDER_OWNER_ID"))

    with RenderAPIClient(api_key=render_key, timeout_seconds=30.0) as client:
        owner_id = resolve_owner_id(client, requested_owner)
        matches = client.list_services(owner_id, step7c.SERVICE_NAME)
        if len(matches) != 1:
            raise Step7EHotfixDeployError(f"Expected one Render service named {step7c.SERVICE_NAME}; found {len(matches)}.")
        service_id = _clean(matches[0].get("id"))
        if not service_id:
            raise Step7EHotfixDeployError("Render service has no ID.")

        before = client.get_service(service_id)
        _validate_existing_service(before)
        before_branch = _clean(before.get("branch"))
        if before_branch not in {step7c.SOURCE_BRANCH, PATCH_BRANCH}:
            raise Step7EHotfixDeployError(f"Unexpected pre-hotfix Render branch {before_branch!r}.")

        env_rows = client.list_env_vars(service_id)
        env_values = _env_map(env_rows)
        _validate_render_environment(env_values)

        client.request(
            "PATCH",
            f"/v1/services/{service_id}",
            json_body={"branch": PATCH_BRANCH, "autoDeploy": "no"},
            allowed=(200,),
        )
        after_patch = client.get_service(service_id)
        _validate_existing_service(after_patch)
        if _clean(after_patch.get("branch")) != PATCH_BRANCH:
            raise Step7EHotfixDeployError("Render did not persist the certified hotfix branch.")

        # Re-verify environment after service metadata mutation. No env values are changed.
        after_env = _env_map(client.list_env_vars(service_id))
        _validate_render_environment(after_env)

        deploy_doc = client.request(
            "POST",
            f"/v1/services/{service_id}/deploys",
            json_body={"commitId": PATCH_REVISION, "clearCache": "clear"},
            allowed=(201, 202),
        )
        if not isinstance(deploy_doc, Mapping) or not _clean(deploy_doc.get("id")):
            raise Step7EHotfixDeployError("Render did not return a hotfix deploy identity.")
        deploy_id = str(deploy_doc["id"])
        final_deploy = _wait_live(client, service_id, deploy_id)
        final_commit = _deploy_commit_id(final_deploy)
        if final_commit is not None and final_commit != PATCH_REVISION:
            raise Step7EHotfixDeployError(f"Render deployed {final_commit}; expected {PATCH_REVISION}.")

        final_service = client.get_service(service_id)
        _validate_existing_service(final_service)
        if _clean(final_service.get("branch")) != PATCH_BRANCH:
            raise Step7EHotfixDeployError("Render source branch drifted after hotfix deployment.")

    health = _get_json("/health")
    if health.get("status") != "ok":
        raise Step7EHotfixDeployError("Hosted /health is not ok after schedule hotfix.")

    schedule = _get_json("/api/v1/wnba/games/today?season=2026")
    if schedule.get("season") != 2026 or not isinstance(schedule.get("games"), list):
        raise Step7EHotfixDeployError("Hosted WNBA games/today response is invalid after hotfix.")
    if schedule.get("source_variant") != EXPECTED_SCHEDULE_SOURCE_VARIANT:
        raise Step7EHotfixDeployError(f"Hosted schedule used unexpected source variant {schedule.get('source_variant')!r}.")
    if schedule.get("source_url") != EXPECTED_SCHEDULE_SOURCE_URL:
        raise Step7EHotfixDeployError("Hosted schedule did not use the official WNBA.com schedule API.")

    step6r = _get_json("/api/v1/wnba/runtime/step6r-supabase-storage")
    backend = step6r.get("backend") if isinstance(step6r.get("backend"), Mapping) else {}
    if step6r.get("selected_backend") != "supabase" or step6r.get("configuration_ready") is not True:
        raise Step7EHotfixDeployError("Step 6R Supabase readiness regressed after hotfix.")
    if backend.get("project_host") != EXPECTED_SUPABASE_HOST:
        raise Step7EHotfixDeployError("Step 6R Supabase host drifted after hotfix.")

    step6t = _get_json("/api/v1/wnba/runtime/step6t-canary-evidence/status")
    if step6t.get("selected_backend") != "supabase" or step6t.get("configuration_ready") is not True:
        raise Step7EHotfixDeployError("Step 6T Supabase readiness regressed after hotfix.")
    if step6t.get("verification_is_read_only") is not True or step6t.get("scheduler_authorized") is not False:
        raise Step7EHotfixDeployError("Step 6T safety state regressed after hotfix.")

    step6u = _get_json("/api/v1/wnba/runtime/step6u-activation-bridge/status")
    if step6u.get("blocking_reasons") != [LEGACY_STEP6U_BLOCKER]:
        raise Step7EHotfixDeployError(f"Legacy Step 6U blockers changed: {step6u.get('blocking_reasons')!r}")
    if step6u.get("bridge_ready") is not False or step6u.get("scheduler_authorized") is not False:
        raise Step7EHotfixDeployError("Legacy Step 6U fail-closed state regressed after hotfix.")
    safety6u = step6u.get("safety") if isinstance(step6u.get("safety"), Mapping) else {}
    if safety6u.get("production_runtime_enabled") is not False or safety6u.get("scheduler_started") is not False:
        raise Step7EHotfixDeployError("Production/scheduler state changed during hotfix.")

    return {
        "source": "Kyre Sports API WNBA Step 7E certified schedule hotfix deployment",
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": "wnba_step7e_schedule_hotfix_live",
        "deployment_complete": True,
        "patch": {
            "branch": PATCH_BRANCH,
            "revision": PATCH_REVISION,
            "parent_revision": PATCH_PARENT_REVISION,
            "scope": ["sports_api/wnba_schedule.py", "sports_api/tests/test_wnba_schedule.py"],
        },
        "render": {
            "service_id": service_id,
            "service_name": step7c.SERVICE_NAME,
            "service_url": SERVICE_URL,
            "plan": "free",
            "auto_deploy": "no",
            "source_branch": PATCH_BRANCH,
            "deploy_id": deploy_id,
            "deploy_status": "live",
            "deployed_revision": PATCH_REVISION,
        },
        "schedule": {
            "status_code": 200,
            "season": 2026,
            "game_count": schedule.get("game_count"),
            "source_variant": schedule.get("source_variant"),
            "source_url": schedule.get("source_url"),
        },
        "runtime_readiness": {
            "health": "ok",
            "step6r_supabase_ready": True,
            "step6t_supabase_ready": True,
            "legacy_step6u_expected_block_preserved": True,
        },
        "safety": {
            "render_plan_is_free": True,
            "persistent_disk_attached": False,
            "auto_deploy_enabled": False,
            "supabase_environment_changed": False,
            "supabase_write_performed": False,
            "production_runtime_enabled": False,
            "scheduler_authorized": False,
            "scheduler_started": False,
            "direct_sync_enabled": False,
            "reconciled_sync_enabled": False,
            "step6j_canary_enabled": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "render_api_key_returned": False,
            "supabase_secret_returned": False,
        },
    }


def main() -> int:
    print(json.dumps(deploy_schedule_hotfix(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
