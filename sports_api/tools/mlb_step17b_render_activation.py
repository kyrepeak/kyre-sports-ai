#!/usr/bin/env python3
"""Controlled live Render activation for MLB Step 17B.

The operator reuses the existing shared WNBA Render Free service. It first deploys
the exact certified WNBA+MLB revision with Step 17B OFF, proves WNBA continuity,
then atomically stages the bounded Step 17B environment and deploys that same
immutable revision. A second same-revision deploy proves durable restart recovery.

If any post-mutation phase fails, the operator restores the exact original direct
Render environment, original source branch, and original live Git revision before
raising. It never prints secret values.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

from sports_api.wnba_render_provisioning import RenderAPIClient, resolve_owner_id
from sports_api.tools import wnba_step7c_render_free_deploy as step7c

MODEL_VERSION = "mlb_step17b_render_controlled_activation_v1"
CERTIFIED_REVISION = "ece3cd2d15d091728fdbe30be774dd9c15e4fe8e"
CERTIFIED_RUN_ID = 33578176749
CANDIDATE_BRANCH = "mlb-step17b-shared-host-cert"
EXPECTED_SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
SERVICE_URL = "https://kyre-sports-api.onrender.com"

STEP17B_ENV = {
    "MLB_STEP17B_ALWAYS_ON_ENABLED": "true",
    "MLB_STEP17B_LOOP_SECONDS": "60",
    "MLB_STEP17B_EXPECTED_REVISION": CERTIFIED_REVISION,
    "MLB_DEPLOYMENT_MODE": "container",
    "WEB_CONCURRENCY": "1",
    "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED": "true",
    "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED": "true",
    "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
    "MLB_STEP14B_DATABASE_READ_ENABLED": "true",
    "MLB_STEP14B_DATABASE_WRITE_ENABLED": "true",
    "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
    "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
    "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
    "MLB_WAGERING_ENABLED": "false",
    "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED": "false",
    "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED": "false",
    "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED": "false",
}
FROZEN_FALSE = tuple(
    key
    for key, value in STEP17B_ENV.items()
    if key.startswith("MLB_") and value == "false"
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class Step17BRenderActivationError(RuntimeError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _details(service: Mapping[str, Any]) -> Mapping[str, Any]:
    value = service.get("serviceDetails")
    return value if isinstance(value, Mapping) else {}


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


def build_activated_env(original: Mapping[str, str]) -> dict[str, str]:
    values = {str(k): str(v) for k, v in original.items()}
    values.update(STEP17B_ENV)
    return values


def _validate_database(values: Mapping[str, str]) -> None:
    raw = _clean(values.get("KYRE_DATABASE_URL"))
    parsed = urlsplit(raw or "")
    if not (
        raw
        and parsed.scheme.casefold() in {"postgres", "postgresql"}
        and parsed.hostname
        and parsed.path not in {"", "/"}
    ):
        raise Step17BRenderActivationError(
            "Render is missing a valid protected PostgreSQL KYRE_DATABASE_URL."
        )


def _validate_service(service: Mapping[str, Any]) -> None:
    details = _details(service)
    if _clean(service.get("id")) != EXPECTED_SERVICE_ID:
        raise Step17BRenderActivationError("Render service identity drifted.")
    if _clean(service.get("name")) not in {None, step7c.SERVICE_NAME}:
        raise Step17BRenderActivationError("Render service name drifted.")
    if _clean(service.get("repo")) != step7c.SOURCE_REPOSITORY:
        raise Step17BRenderActivationError("Render repository drifted.")
    if (_clean(service.get("autoDeploy")) or "no").casefold() not in {"no", "false", "off"}:
        raise Step17BRenderActivationError("Render auto-deploy must remain OFF.")
    if (_clean(details.get("runtime") or details.get("env")) or "").casefold() != "docker":
        raise Step17BRenderActivationError("Existing Render service is not Docker-backed.")
    if (_clean(details.get("plan")) or "").casefold() != "free":
        raise Step17BRenderActivationError("Step 17B refuses a non-Free Render service.")
    if isinstance(details.get("disk"), Mapping):
        raise Step17BRenderActivationError("Unexpected persistent Render disk attached.")


def _validate_baseline_env(values: Mapping[str, str]) -> None:
    if values.get("WNBA_KYRE_DURABLE_STORAGE_BACKEND") != "supabase":
        raise Step17BRenderActivationError("WNBA durable backend drifted.")
    for name in step7c.OFF_SWITCHES:
        if _truthy(values.get(name)):
            raise Step17BRenderActivationError(
                f"WNBA safety switch unexpectedly enabled: {name}"
            )
    if _truthy(values.get("MLB_STEP17B_ALWAYS_ON_ENABLED")):
        raise Step17BRenderActivationError("Step 17B is already enabled before activation.")
    for name in FROZEN_FALSE:
        if _truthy(values.get(name)):
            raise Step17BRenderActivationError(
                f"Frozen MLB switch unexpectedly enabled: {name}"
            )
    _validate_database(values)


def _validate_activated_env(values: Mapping[str, str]) -> None:
    for key, expected in STEP17B_ENV.items():
        actual = str(values.get(key, "")).strip().casefold()
        if actual != expected.casefold():
            raise Step17BRenderActivationError(
                f"Render did not persist required Step 17B environment key {key}."
            )
    _validate_database(values)
    for name in step7c.OFF_SWITCHES:
        if _truthy(values.get(name)):
            raise Step17BRenderActivationError(
                f"WNBA safety switch changed during activation: {name}"
            )


def _deploy_commit_id(deploy: Mapping[str, Any]) -> str | None:
    direct = _clean(deploy.get("commitId"))
    if direct:
        return direct.casefold()
    commit = deploy.get("commit")
    if isinstance(commit, Mapping):
        value = _clean(commit.get("id") or commit.get("sha"))
        return value.casefold() if value else None
    return None


def _deploy_rows(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, list):
        return []
    out: list[dict[str, Any]] = []
    for row in document:
        if not isinstance(row, Mapping):
            continue
        item = row.get("deploy") if isinstance(row.get("deploy"), Mapping) else row
        if isinstance(item, Mapping):
            out.append(dict(item))
    return out


def _current_live_revision(client: RenderAPIClient, service_id: str) -> str:
    rows = _deploy_rows(
        client.request(
            "GET",
            f"/v1/services/{service_id}/deploys",
            params={"limit": 20},
        )
    )
    for deploy in rows:
        if (_clean(deploy.get("status")) or "").casefold() != "live":
            continue
        revision = _deploy_commit_id(deploy)
        if revision and SHA40.fullmatch(revision):
            return revision
    raise Step17BRenderActivationError(
        "Could not identify exact currently-live Render Git revision for rollback."
    )


def _replace_env(client: RenderAPIClient, service_id: str, values: Mapping[str, str]) -> None:
    rows = [
        {"key": str(key), "value": str(value)}
        for key, value in sorted(values.items())
    ]
    client.request(
        "PUT",
        f"/v1/services/{service_id}/env-vars",
        json_body=rows,
        allowed=(200,),
    )


def _patch_branch(client: RenderAPIClient, service_id: str, branch: str) -> None:
    client.request(
        "PATCH",
        f"/v1/services/{service_id}",
        json_body={"branch": branch, "autoDeploy": "no"},
        allowed=(200,),
    )
    service = client.get_service(service_id)
    _validate_service(service)
    if _clean(service.get("branch")) != branch:
        raise Step17BRenderActivationError("Render did not persist requested source branch.")


def _trigger_exact_deploy(
    client: RenderAPIClient,
    service_id: str,
    revision: str,
    *,
    clear_cache: bool,
) -> str:
    body = {
        "commitId": revision,
        "clearCache": "clear" if clear_cache else "do_not_clear",
    }
    document = client.request(
        "POST",
        f"/v1/services/{service_id}/deploys",
        json_body=body,
        allowed=(201, 202),
    )
    if not isinstance(document, Mapping) or not _clean(document.get("id")):
        raise Step17BRenderActivationError("Render did not return a deploy identity.")
    return str(document["id"])


def _wait_live(
    client: RenderAPIClient,
    service_id: str,
    deploy_id: str,
    expected_revision: str,
    timeout_seconds: float = 900.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    failed = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    while True:
        deploy = client.get_deploy(service_id, deploy_id)
        status = (_clean(deploy.get("status")) or "").casefold()
        if status == "live":
            actual = _deploy_commit_id(deploy)
            if actual is not None and actual != expected_revision:
                raise Step17BRenderActivationError(
                    "Render live deploy revision does not match requested immutable revision."
                )
            return deploy
        if status in failed:
            raise Step17BRenderActivationError(
                f"Render deploy failed with status={status}."
            )
        if time.monotonic() >= deadline:
            raise Step17BRenderActivationError(
                f"Timed out waiting for Render deploy; status={status or 'unknown'}."
            )
        time.sleep(5)


def _get_json(path: str, *, timeout_seconds: float = 240.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = "not attempted"
    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"user-agent": "kyre-mlb-step17b-controlled-activation/1"},
    ) as http:
        while True:
            try:
                response = http.get(SERVICE_URL + path)
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
                raise Step17BRenderActivationError(
                    f"Hosted verification failed for {path}: {last}"
                )
            time.sleep(5)


def _verify_wnba() -> dict[str, Any]:
    health = _get_json("/health")
    if health.get("status") != "ok":
        raise Step17BRenderActivationError("Hosted /health is not ok.")
    schedule = _get_json("/api/v1/wnba/games/today?season=2026")
    if schedule.get("season") != 2026 or not isinstance(schedule.get("games"), list):
        raise Step17BRenderActivationError("Hosted WNBA schedule smoke failed.")
    return {
        "health": "ok",
        "season": 2026,
        "game_count": schedule.get("game_count"),
    }


def _verify_step17b_disabled() -> dict[str, Any]:
    status = _get_json("/api/v1/mlb/runtime/step17b")
    if status.get("enabled") is not False or status.get("running") is not False:
        raise Step17BRenderActivationError(
            "Step 17B did not remain disabled during combined-host deployment."
        )
    return status


def _verify_step17b_running(
    *,
    min_checkpoint_version: int | None = None,
    require_recovery: bool = False,
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while True:
        last = _get_json("/api/v1/mlb/runtime/step17b", timeout_seconds=60.0)
        version = last.get("last_checkpoint_version")
        version_ok = isinstance(version, int) and not isinstance(version, bool)
        if min_checkpoint_version is not None:
            version_ok = version_ok and version > min_checkpoint_version
        safe = (
            last.get("enabled") is True
            and last.get("running") is True
            and last.get("role") == "leader"
            and last.get("leadership_acquired") is True
            and isinstance(last.get("success_count"), int)
            and last.get("success_count", 0) >= 1
            and last.get("provider_calls") == 0
            and last.get("sportsbook_calls") == 0
            and last.get("production_scheduler_started") is False
            and last.get("legacy_production_runtime_started") is False
            and last.get("actionable_output_enabled") is False
            and last.get("wagering_enabled") is False
            and version_ok
        )
        if require_recovery:
            safe = safe and last.get("recovered_from_checkpoint") is True
        if safe:
            return last
        if time.monotonic() >= deadline:
            raise Step17BRenderActivationError(
                "Step 17B did not reach the required safe leader/checkpoint state."
            )
        time.sleep(5)


def _rollback(
    *,
    client: RenderAPIClient,
    service_id: str,
    original_env: Mapping[str, str],
    original_branch: str,
    original_revision: str,
) -> dict[str, Any]:
    _replace_env(client, service_id, original_env)
    _patch_branch(client, service_id, original_branch)
    deploy_id = _trigger_exact_deploy(
        client,
        service_id,
        original_revision,
        clear_cache=False,
    )
    _wait_live(client, service_id, deploy_id, original_revision)
    smoke = _verify_wnba()
    return {
        "performed": True,
        "service_restored": True,
        "original_branch_restored": True,
        "original_revision_restored": True,
        "original_environment_restored": True,
        "wnba_health": smoke["health"],
    }


def activate(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = os.environ if env is None else env
    render_key = _clean(environment.get("RENDER_API_KEY"))
    if not render_key or len(render_key) < 20:
        raise Step17BRenderActivationError("RENDER_API_KEY is required.")
    requested_owner = _clean(environment.get("RENDER_OWNER_ID"))

    mutation_started = False
    original_env: dict[str, str] = {}
    original_branch = ""
    original_revision = ""
    service_id = ""

    with RenderAPIClient(api_key=render_key, timeout_seconds=30.0) as client:
        owner_id = resolve_owner_id(client, requested_owner)
        matches = client.list_services(owner_id, step7c.SERVICE_NAME)
        if len(matches) != 1:
            raise Step17BRenderActivationError(
                f"Expected one Render service named {step7c.SERVICE_NAME}; found {len(matches)}."
            )
        service_id = _clean(matches[0].get("id")) or ""
        if service_id != EXPECTED_SERVICE_ID:
            raise Step17BRenderActivationError("Render service identity drifted.")
        before = client.get_service(service_id)
        _validate_service(before)
        original_branch = _clean(before.get("branch")) or ""
        if not original_branch:
            raise Step17BRenderActivationError("Render source branch is missing.")
        original_env = _env_map(client.list_env_vars(service_id))
        _validate_baseline_env(original_env)
        original_revision = _current_live_revision(client, service_id)

        try:
            mutation_started = True
            _patch_branch(client, service_id, CANDIDATE_BRANCH)
            off_deploy_id = _trigger_exact_deploy(
                client,
                service_id,
                CERTIFIED_REVISION,
                clear_cache=True,
            )
            _wait_live(client, service_id, off_deploy_id, CERTIFIED_REVISION)
            off_wnba = _verify_wnba()
            _verify_step17b_disabled()

            activated_env = build_activated_env(original_env)
            _replace_env(client, service_id, activated_env)
            persisted = _env_map(client.list_env_vars(service_id))
            _validate_activated_env(persisted)

            activation_deploy_id = _trigger_exact_deploy(
                client,
                service_id,
                CERTIFIED_REVISION,
                clear_cache=False,
            )
            _wait_live(client, service_id, activation_deploy_id, CERTIFIED_REVISION)
            active_wnba = _verify_wnba()
            active_status = _verify_step17b_running()
            active_version = int(active_status["last_checkpoint_version"])

            restart_deploy_id = _trigger_exact_deploy(
                client,
                service_id,
                CERTIFIED_REVISION,
                clear_cache=False,
            )
            _wait_live(client, service_id, restart_deploy_id, CERTIFIED_REVISION)
            restart_wnba = _verify_wnba()
            restart_status = _verify_step17b_running(
                min_checkpoint_version=active_version,
                require_recovery=True,
            )

            final_service = client.get_service(service_id)
            _validate_service(final_service)
            final_env = _env_map(client.list_env_vars(service_id))
            _validate_activated_env(final_env)
            if _clean(final_service.get("branch")) != CANDIDATE_BRANCH:
                raise Step17BRenderActivationError("Render source branch drifted after activation.")

            return {
                "source": "Kyre Sports API MLB Step 17B controlled Render activation",
                "model_version": MODEL_VERSION,
                "generated_at_utc": _utc_now(),
                "state": "mlb_step17b_live_restart_recovery_green",
                "activation_complete": True,
                "certified_candidate": {
                    "branch": CANDIDATE_BRANCH,
                    "revision": CERTIFIED_REVISION,
                    "certification_run_id": CERTIFIED_RUN_ID,
                },
                "render": {
                    "service_id": service_id,
                    "service_name": step7c.SERVICE_NAME,
                    "service_url": SERVICE_URL,
                    "plan": "free",
                    "auto_deploy": "no",
                    "source_branch": CANDIDATE_BRANCH,
                    "off_deploy_id": off_deploy_id,
                    "activation_deploy_id": activation_deploy_id,
                    "restart_deploy_id": restart_deploy_id,
                    "deployed_revision": CERTIFIED_REVISION,
                },
                "wnba": {
                    "pre_activation_health": off_wnba["health"],
                    "post_activation_health": active_wnba["health"],
                    "post_restart_health": restart_wnba["health"],
                },
                "mlb_step17b": {
                    "enabled": True,
                    "running": True,
                    "role": restart_status.get("role"),
                    "leadership_acquired": restart_status.get("leadership_acquired"),
                    "success_count_after_restart": restart_status.get("success_count"),
                    "checkpoint_version_before_restart": active_version,
                    "checkpoint_version_after_restart": restart_status.get("last_checkpoint_version"),
                    "recovered_from_checkpoint": restart_status.get("recovered_from_checkpoint"),
                    "provider_calls": restart_status.get("provider_calls"),
                    "sportsbook_calls": restart_status.get("sportsbook_calls"),
                },
                "safety": {
                    "existing_render_service_reused": True,
                    "new_render_service_created": False,
                    "auto_deploy_enabled": False,
                    "wnba_off_switches_preserved": True,
                    "legacy_mlb_production_runtime_started": False,
                    "legacy_mlb_production_scheduler_started": False,
                    "actionable_output_enabled": False,
                    "wagering_enabled": False,
                    "provider_calls": 0,
                    "sportsbook_calls": 0,
                    "render_api_key_returned": False,
                    "database_secret_returned": False,
                },
                "rollback": {
                    "required": False,
                    "performed": False,
                },
            }
        except Exception as exc:
            if not mutation_started:
                raise
            rollback_error: Exception | None = None
            try:
                _rollback(
                    client=client,
                    service_id=service_id,
                    original_env=original_env,
                    original_branch=original_branch,
                    original_revision=original_revision,
                )
            except Exception as rb_exc:
                rollback_error = rb_exc
            if rollback_error is not None:
                raise Step17BRenderActivationError(
                    f"Step 17B activation failed ({type(exc).__name__}); rollback also failed ({type(rollback_error).__name__})."
                ) from exc
            raise Step17BRenderActivationError(
                f"Step 17B activation failed ({type(exc).__name__}); original WNBA Render state was restored."
            ) from exc


def main() -> int:
    print(json.dumps(activate(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
