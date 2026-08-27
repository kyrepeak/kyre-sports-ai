#!/usr/bin/env python3
"""Step 7D: wire the live Render Free API to the frozen Supabase backend.

This operator is intentionally pre-activation. It performs a read-only Supabase
proof using the existing Step 6R storage contract, injects only the server-side
Supabase storage variables plus explicit OFF switches into the existing Render
Free service, redeploys the exact Step 7B release, and verifies the live API
reports Supabase configuration readiness.

It does not write Supabase data, call a sportsbook, start a scheduler, run Monte
Carlo, or place wagers. Secret values are never returned.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

from sports_api.wnba_render_provisioning import RenderAPIClient, resolve_owner_id
from sports_api.wnba_step6q_durable_storage import (
    CANARY_MARKER_OBJECT_KEY,
    FEED_OBJECT_KEY,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
)
from sports_api.wnba_step6r_supabase_storage import (
    SUPABASE_SECRET_KEY_ENV,
    SUPABASE_URL_ENV,
    build_step6r_durable_storage,
)
import sports_api.tools.wnba_step7c_render_free_deploy as step7c
import sports_api.tools.wnba_step7c_render_free_deploy_v3 as step7c_v3

MODEL_VERSION = "wnba_step_7d_render_supabase_wiring_v1"
EXPECTED_SUPABASE_HOST = "jqajcdckalsfizbvngiu.supabase.co"
SERVICE_URL = "https://kyre-sports-api.onrender.com"
OFF_SWITCHES = dict(step7c.OFF_SWITCHES)


class Step7DWiringError(RuntimeError):
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


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
    failures = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    while True:
        deploy = client.get_deploy(service_id, deploy_id)
        status = (_clean(deploy.get("status")) or "").casefold()
        if status == "live":
            return deploy
        if status in failures:
            raise Step7DWiringError(f"Render Step 7D deploy failed with status={status}.")
        if time.monotonic() >= deadline:
            raise Step7DWiringError(f"Timed out waiting for Step 7D deploy; status={status or 'unknown'}.")
        time.sleep(5)


def _get_json_with_retry(url: str, timeout_seconds: float = 180.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = "not attempted"
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        while True:
            try:
                response = client.get(url)
                if response.status_code == 200:
                    body = response.json()
                    if isinstance(body, dict):
                        return body
                    last = "response was not a JSON object"
                else:
                    last = f"HTTP {response.status_code}"
            except Exception as exc:  # pragma: no cover - live retry guard
                last = f"{type(exc).__name__}: {exc}"
            if time.monotonic() >= deadline:
                raise Step7DWiringError(f"Live API verification failed for {url}: {last}")
            time.sleep(5)


def validate_environment(environment: Mapping[str, str]) -> None:
    for key in OFF_SWITCHES:
        if _truthy(environment.get(key)):
            raise Step7DWiringError(f"Step 7D refuses to run while {key} is enabled.")
    render_key = _clean(environment.get("RENDER_API_KEY"))
    supabase_url = _clean(environment.get(SUPABASE_URL_ENV))
    supabase_secret = _clean(environment.get(SUPABASE_SECRET_KEY_ENV))
    if not render_key or len(render_key) < 20:
        raise Step7DWiringError("RENDER_API_KEY is required.")
    if not supabase_url:
        raise Step7DWiringError(f"{SUPABASE_URL_ENV} is required.")
    if not supabase_secret or len(supabase_secret) < 20:
        raise Step7DWiringError(f"{SUPABASE_SECRET_KEY_ENV} is required.")
    parsed = urlsplit(supabase_url)
    if parsed.scheme.casefold() != "https" or parsed.hostname != EXPECTED_SUPABASE_HOST:
        raise Step7DWiringError("Step 7D Supabase URL is not the frozen WNBA project origin.")


def build_render_env_values(environment: Mapping[str, str]) -> dict[str, str]:
    validate_environment(environment)
    return {
        STORAGE_BACKEND_ENV: SUPABASE_BACKEND,
        SUPABASE_URL_ENV: str(environment[SUPABASE_URL_ENV]).strip(),
        SUPABASE_SECRET_KEY_ENV: str(environment[SUPABASE_SECRET_KEY_ENV]).strip(),
        **{key: "false" for key in OFF_SWITCHES},
    }


def wire_render_to_supabase(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = os.environ if env is None else env
    render_env = build_render_env_values(environment)

    # Read-only proof against the frozen Supabase durable objects before Render mutation.
    storage_env = dict(environment)
    storage_env[STORAGE_BACKEND_ENV] = SUPABASE_BACKEND
    storage = build_step6r_durable_storage(env=storage_env)
    if storage.backend_id != SUPABASE_BACKEND:
        raise Step7DWiringError("Step 7D did not resolve the Supabase backend.")
    feed_raw = storage.read_bytes(FEED_OBJECT_KEY)
    marker_raw = storage.read_bytes(CANARY_MARKER_OBJECT_KEY)
    if not feed_raw or not marker_raw:
        raise Step7DWiringError("Step 7D Supabase read proof returned empty durable evidence.")
    read_proof = {
        "backend": SUPABASE_BACKEND,
        "feed_object": FEED_OBJECT_KEY,
        "feed_size_bytes": len(feed_raw),
        "feed_sha256": _sha256(feed_raw),
        "marker_object": CANARY_MARKER_OBJECT_KEY,
        "marker_size_bytes": len(marker_raw),
        "marker_sha256": _sha256(marker_raw),
        "storage_read_performed": True,
        "storage_write_performed": False,
    }

    render_key = str(environment["RENDER_API_KEY"]).strip()
    requested_owner = _clean(environment.get("RENDER_OWNER_ID"))
    with RenderAPIClient(api_key=render_key, timeout_seconds=30.0) as client:
        owner_id = resolve_owner_id(client, requested_owner)
        services = client.list_services(owner_id, step7c.SERVICE_NAME)
        if len(services) != 1:
            raise Step7DWiringError(f"Expected exactly one Render service named {step7c.SERVICE_NAME}; found {len(services)}.")
        service_id = _clean(services[0].get("id"))
        if not service_id:
            raise Step7DWiringError("Render service has no ID.")
        service = client.get_service(service_id)
        step7c_v3._validate_existing_service(service)
        if _clean(service.get("branch")) != step7c.SOURCE_BRANCH:
            raise Step7DWiringError("Render source branch drifted from the frozen Step 7C pin.")

        for key, value in render_env.items():
            client.put_env_var(service_id, key, value)

        observed_rows = client.list_env_vars(service_id)
        observed = {str(row.get("key")): str(row.get("value")) for row in observed_rows if isinstance(row, Mapping)}
        for key, expected in render_env.items():
            if observed.get(key) != expected:
                raise Step7DWiringError(f"Render did not persist required Step 7D variable {key}.")

        deploy_doc = client.request(
            "POST",
            f"/v1/services/{service_id}/deploys",
            json_body={"commitId": step7c.SOURCE_REVISION, "clearCache": "do_not_clear"},
            allowed=(201, 202),
        )
        if not isinstance(deploy_doc, dict) or not _clean(deploy_doc.get("id")):
            raise Step7DWiringError("Render did not return a Step 7D deploy identity.")
        deploy_id = str(deploy_doc["id"])
        final_deploy = _wait_live(client, service_id, deploy_id)
        final_commit = _deploy_commit_id(final_deploy)
        if final_commit is not None and final_commit != step7c.SOURCE_REVISION:
            raise Step7DWiringError(f"Render deployed {final_commit}; expected frozen revision {step7c.SOURCE_REVISION}.")

    health = _get_json_with_retry(SERVICE_URL + "/health")
    if health.get("status") != "ok":
        raise Step7DWiringError("Live Render /health did not report ok after Step 7D wiring.")

    step6r = _get_json_with_retry(SERVICE_URL + "/api/v1/wnba/runtime/step6r-supabase-storage")
    if step6r.get("selected_backend") != SUPABASE_BACKEND or step6r.get("configuration_ready") is not True:
        raise Step7DWiringError("Live Step 6R status did not confirm Supabase configuration readiness.")
    backend = step6r.get("backend") if isinstance(step6r.get("backend"), Mapping) else {}
    if backend.get("project_host") != EXPECTED_SUPABASE_HOST:
        raise Step7DWiringError("Live Step 6R status reported the wrong Supabase project host.")
    if backend.get("secret_configured") is not True or backend.get("secret_value_exposed") is not False:
        raise Step7DWiringError("Live Step 6R secret safety report is invalid.")

    step6t = _get_json_with_retry(SERVICE_URL + "/api/v1/wnba/runtime/step6t-canary-evidence/status")
    if step6t.get("selected_backend") != SUPABASE_BACKEND or step6t.get("configuration_ready") is not True:
        raise Step7DWiringError("Live Step 6T status did not confirm read-only Supabase verification readiness.")
    if step6t.get("scheduler_authorized") is not False:
        raise Step7DWiringError("Step 7D unexpectedly observed scheduler authorization.")

    return {
        "source": "Kyre Sports API WNBA Step 7D Render-Supabase wiring",
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": "wnba_render_supabase_wired_preactivation",
        "wiring_complete": True,
        "render": {
            "service_id": service_id,
            "service_name": step7c.SERVICE_NAME,
            "service_url": SERVICE_URL,
            "deploy_id": deploy_id,
            "deploy_status": "live",
            "deployed_revision": step7c.SOURCE_REVISION,
            "plan": "free",
            "auto_deploy": "no",
        },
        "supabase": {
            "project_host": EXPECTED_SUPABASE_HOST,
            "storage_backend": SUPABASE_BACKEND,
            "render_configuration_ready": True,
            "secret_configured_in_render": True,
            "secret_value_returned": False,
            "read_proof": read_proof,
        },
        "live_api": {
            "health_status": "ok",
            "step6r_configuration_ready": True,
            "step6t_configuration_ready": True,
            "step6t_verification_requires_network": step6t.get("verification_requires_network") is True,
            "step6t_verification_is_read_only": step6t.get("verification_is_read_only") is True,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_authorized": False,
            "scheduler_started": False,
            "direct_sync_enabled": False,
            "reconciled_sync_enabled": False,
            "step6j_canary_enabled": False,
            "supabase_write_performed": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "render_api_key_returned": False,
            "supabase_secret_returned": False,
        },
    }


def main() -> int:
    print(json.dumps(wire_render_to_supabase(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
