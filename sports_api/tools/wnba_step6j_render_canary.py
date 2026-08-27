"""Execute the Step 6J canary against the existing Render persistent service.

This operator/CI tool never provisions paid resources. It reuses the existing
Step 6C Render service and disk, deploys the exact immutable Step 6J image,
enables only the two Step 6I write switches plus the one-shot Step 6J gate,
invokes one authenticated canary write, then immediately disables all three
write switches and verifies the final fail-closed state.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

import httpx

from sports_api.wnba_render_attachment_readiness import (
    DEFAULT_DISK_MOUNT_PATH,
    DEFAULT_DISK_NAME,
    DEFAULT_DISK_SIZE_GB,
    DEFAULT_SERVICE_NAME,
    DEPLOYED_IMAGE_REF_ENV,
)
from sports_api.wnba_render_provisioning import (
    RenderAPIClient,
    RENDER_API_KEY_ENV,
    RENDER_OWNER_ID_ENV,
    _service_image_ref,
    _service_url,
    resolve_owner_id,
    wait_for_deploy,
)
from sports_api.wnba_render_provisioning_step6c import INGEST_TOKEN_ENV
from sports_api.wnba_reconciled_direct_sync import RECONCILED_SYNC_ENABLED_ENV, RECONCILED_SYNC_MAX_AGE_ENV
from sports_api.wnba_step6d_direct_integration import (
    DIRECT_SYNC_ENABLED_ENV,
    DIRECT_SYNC_PROVIDER_ENV,
    SUPPORTED_DIRECT_PROVIDER,
)
from sports_api.wnba_step6j_canary_activation import ACTIVATION_ID_ENV, CANARY_ENABLED_ENV

MODEL_SOURCE = "Kyre Sports API WNBA Step 6J Render canary operator"
MODEL_VERSION = "wnba_step_6j_render_canary_operator_v1"
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")


class Step6JRenderCanaryError(RuntimeError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _env_map(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        key = _clean(row.get("key") or row.get("name"))
        if key:
            result[key] = _clean(row.get("value")) or ""
    return result


def _put_many(client: RenderAPIClient, service_id: str, values: Mapping[str, str]) -> None:
    for key, value in values.items():
        client.put_env_var(service_id, key, str(value))


def _matching_disk(disks: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    matches = []
    for disk in disks:
        name = _clean(disk.get("name"))
        mount = _clean(disk.get("mountPath") or disk.get("mount_path"))
        try:
            size = int(disk.get("sizeGB") or disk.get("size_gb") or 0)
        except (TypeError, ValueError):
            size = 0
        if name == DEFAULT_DISK_NAME and mount == DEFAULT_DISK_MOUNT_PATH and size >= DEFAULT_DISK_SIZE_GB:
            matches.append(disk)
    return matches[0] if len(matches) == 1 else None


def _deploy(client: RenderAPIClient, *, service_id: str, image_ref: str) -> str:
    deploy = client.trigger_deploy(service_id, image_ref)
    deploy_id = _clean(deploy.get("id"))
    if not deploy_id:
        raise Step6JRenderCanaryError("Render did not return a deploy id.")
    wait_for_deploy(client, service_id=service_id, deploy_id=deploy_id, timeout_seconds=480, poll_seconds=3)
    return deploy_id


def _get_json(remote: httpx.Client, path: str, *, allowed: tuple[int, ...] = (200,)) -> dict[str, Any]:
    response = remote.get(path)
    if response.status_code not in allowed:
        raise Step6JRenderCanaryError(f"Remote GET {path} returned HTTP {response.status_code}.")
    try:
        document = response.json()
    except ValueError as exc:
        raise Step6JRenderCanaryError(f"Remote GET {path} did not return JSON.") from exc
    if not isinstance(document, dict):
        raise Step6JRenderCanaryError(f"Remote GET {path} did not return an object.")
    return document


def _post_canary(remote: httpx.Client, *, date: str, season: int, token: str, activation_id: str) -> dict[str, Any]:
    response = remote.post(
        "/api/v1/wnba/markets/direct/draftkings/step6j-canary",
        params={"date": date, "season": int(season)},
        headers={"Authorization": f"Bearer {token}", "X-WNBA-Step6J-Activation-ID": activation_id},
    )
    if response.status_code != 200:
        detail = None
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail")
        except ValueError:
            pass
        suffix = f": {detail}" if isinstance(detail, str) else ""
        raise Step6JRenderCanaryError(f"Remote Step 6J canary returned HTTP {response.status_code}{suffix}")
    document = response.json()
    if not isinstance(document, dict):
        raise Step6JRenderCanaryError("Remote Step 6J canary response was not an object.")
    return document


def _post_rollback(remote: httpx.Client, *, token: str, activation_id: str) -> dict[str, Any]:
    response = remote.post(
        "/api/v1/wnba/markets/direct/draftkings/step6j-canary/rollback",
        headers={"Authorization": f"Bearer {token}", "X-WNBA-Step6J-Activation-ID": activation_id},
    )
    if response.status_code != 200:
        raise Step6JRenderCanaryError(f"Remote Step 6J rollback returned HTTP {response.status_code}.")
    document = response.json()
    if not isinstance(document, dict) or document.get("rollback_verified") is not True:
        raise Step6JRenderCanaryError("Remote Step 6J rollback did not verify restoration.")
    return document


def run_render_canary(*, revision: str, release_id: str, image_ref: str, activation_id: str, date: str, season: int, api_key: str, owner_id: str | None) -> dict[str, Any]:
    revision = revision.casefold()
    image_ref = image_ref.casefold()
    if not _SHA40_RE.fullmatch(revision):
        raise Step6JRenderCanaryError("Step 6J revision must be a full 40-character Git SHA.")
    if not _IMAGE_RE.fullmatch(image_ref):
        raise Step6JRenderCanaryError("Step 6J image must be immutable name@sha256:<64hex>.")
    if not _clean(release_id) or not _clean(activation_id):
        raise Step6JRenderCanaryError("Step 6J release id and activation id are required.")

    canary_result: dict[str, Any] | None = None
    final_status: dict[str, Any] | None = None
    initial_deploy_id: str | None = None
    closing_deploy_id: str | None = None
    service_url: str | None = None
    service_id: str | None = None
    previous_image: str | None = None
    flags_touched = False
    canary_completed = False
    primary_error: Exception | None = None

    with RenderAPIClient(api_key=api_key, timeout_seconds=25) as client:
        resolved_owner = resolve_owner_id(client, owner_id)
        services = client.list_services(resolved_owner, DEFAULT_SERVICE_NAME)
        if len(services) != 1:
            raise Step6JRenderCanaryError(f"Expected exactly one Render service named {DEFAULT_SERVICE_NAME}.")
        service = services[0]
        service_id = _clean(service.get("id"))
        service_url = _service_url(service)
        previous_image = _service_image_ref(service)
        if not service_id or not service_url or not previous_image:
            raise Step6JRenderCanaryError("Existing Render service identity is incomplete.")
        if _matching_disk(client.list_disks(service_id)) is None:
            raise Step6JRenderCanaryError("Existing Render persistent disk does not match the frozen Step 6C contract.")
        environment = _env_map(client.list_env_vars(service_id))
        ingest_token = _clean(environment.get(INGEST_TOKEN_ENV))
        if not ingest_token:
            raise Step6JRenderCanaryError("Existing Render service has no WNBA market ingest token.")
        if _truthy(environment.get("WNBA_PRODUCTION_RUNTIME_ENABLED")):
            raise Step6JRenderCanaryError("Refusing Step 6J because the WNBA production runtime is currently enabled.")
        if _truthy(environment.get(DIRECT_SYNC_ENABLED_ENV)) or _truthy(environment.get(RECONCILED_SYNC_ENABLED_ENV)):
            raise Step6JRenderCanaryError("Refusing Step 6J because a Step 6I write switch was already enabled before the canary.")

        active_values = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            DIRECT_SYNC_ENABLED_ENV: "true",
            DIRECT_SYNC_PROVIDER_ENV: SUPPORTED_DIRECT_PROVIDER,
            RECONCILED_SYNC_ENABLED_ENV: "true",
            RECONCILED_SYNC_MAX_AGE_ENV: "180",
            CANARY_ENABLED_ENV: "true",
            ACTIVATION_ID_ENV: activation_id,
            "WNBA_RELEASE_ID": release_id,
            "WNBA_DEPLOYMENT_REVISION": revision,
            "WNBA_DEPLOYMENT_IMAGE_REF": image_ref,
            "WNBA_RELEASE_PUBLISHED_IMAGE_REF": image_ref,
            "WNBA_RELEASE_PUBLICATION_VERIFIED": "true",
            DEPLOYED_IMAGE_REF_ENV: image_ref,
        }
        disabled_values = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            DIRECT_SYNC_ENABLED_ENV: "false",
            RECONCILED_SYNC_ENABLED_ENV: "false",
            CANARY_ENABLED_ENV: "false",
        }

        try:
            _put_many(client, service_id, active_values)
            flags_touched = True
            initial_deploy_id = _deploy(client, service_id=service_id, image_ref=image_ref)
            service_after = client.get_service(service_id)
            if _service_image_ref(service_after) != image_ref:
                raise Step6JRenderCanaryError("Render did not activate the exact Step 6J immutable image.")

            with httpx.Client(base_url=service_url.rstrip("/"), timeout=210, follow_redirects=False) as remote:
                health = _get_json(remote, "/health")
                if health.get("status") != "ok":
                    raise Step6JRenderCanaryError("Render health endpoint was not green before canary.")
                gate = _get_json(remote, "/api/v1/wnba/runtime/activation-gate")
                if gate.get("activation_requested") is True or gate.get("live_cycle_allowed") is True:
                    raise Step6JRenderCanaryError("Production scheduler activation gate was not fail-closed before canary.")
                before = _get_json(remote, "/api/v1/wnba/markets/direct/draftkings/step6j-canary/status")
                if before.get("canary_enabled") is not True:
                    raise Step6JRenderCanaryError("Step 6J canary flag did not reach the live Render service.")
                if before.get("production_runtime_enabled") is not False:
                    raise Step6JRenderCanaryError("Production runtime unexpectedly enabled before canary.")
                try:
                    canary_result = _post_canary(remote, date=date, season=season, token=ingest_token, activation_id=activation_id)
                except Exception as exc:
                    status_after_error = _get_json(remote, "/api/v1/wnba/markets/direct/draftkings/step6j-canary/status")
                    state = status_after_error.get("canary_state") or {}
                    if state.get("activation_id") == activation_id and state.get("status") == "completed":
                        canary_result = {
                            "status": "completed",
                            "activation_id": activation_id,
                            "date": state.get("date"),
                            "season": state.get("season"),
                            "offer_side_count": state.get("offer_side_count"),
                            "post_write_sha256": state.get("post_write_sha256"),
                            "verified_persistent_feed_sha256": state.get("verified_persistent_feed_sha256"),
                            "response_recovered_from_status": True,
                        }
                    else:
                        if state.get("activation_id") == activation_id and state.get("status") == "started":
                            _post_rollback(remote, token=ingest_token, activation_id=activation_id)
                        raise exc
                if not canary_result or canary_result.get("status") != "completed":
                    raise Step6JRenderCanaryError("Step 6J did not return a completed canary result.")
                canary_completed = True
                after = _get_json(remote, "/api/v1/wnba/markets/direct/draftkings/step6j-canary/status")
                state = after.get("canary_state") or {}
                if state.get("activation_id") != activation_id or state.get("status") != "completed":
                    raise Step6JRenderCanaryError("Step 6J durable state did not record a completed canary.")
                if state.get("post_write_sha256") != after.get("feed_content_sha256"):
                    raise Step6JRenderCanaryError("Step 6J durable status hash does not match the live feed bytes.")
        except Exception as exc:
            primary_error = exc
        finally:
            if flags_touched:
                try:
                    _put_many(client, service_id, disabled_values)
                    closing_image = image_ref if canary_completed else previous_image
                    closing_deploy_id = _deploy(client, service_id=service_id, image_ref=closing_image)
                except Exception as cleanup_exc:
                    if primary_error is None:
                        primary_error = cleanup_exc
                    else:
                        primary_error = Step6JRenderCanaryError(
                            f"Step 6J failed ({type(primary_error).__name__}) and fail-closed Render cleanup also failed ({type(cleanup_exc).__name__})."
                        )

        if primary_error is not None:
            raise Step6JRenderCanaryError(f"Step 6J Render canary failed: {primary_error}") from primary_error

        with httpx.Client(base_url=service_url.rstrip("/"), timeout=45, follow_redirects=False) as remote:
            final_status = _get_json(remote, "/api/v1/wnba/markets/direct/draftkings/step6j-canary/status")
            if final_status.get("canary_enabled") is not False:
                raise Step6JRenderCanaryError("Step 6J canary flag remained enabled after closing deploy.")
            if final_status.get("direct_sync_enabled") is not False:
                raise Step6JRenderCanaryError("Direct sync flag remained enabled after closing deploy.")
            if final_status.get("reconciled_sync_enabled") is not False:
                raise Step6JRenderCanaryError("Reconciled sync flag remained enabled after closing deploy.")
            if final_status.get("production_runtime_enabled") is not False:
                raise Step6JRenderCanaryError("Production runtime became enabled during Step 6J.")
            state = final_status.get("canary_state") or {}
            if state.get("activation_id") != activation_id or state.get("status") != "completed":
                raise Step6JRenderCanaryError("Completed Step 6J marker did not survive the closing deploy.")
            if state.get("post_write_sha256") != final_status.get("feed_content_sha256"):
                raise Step6JRenderCanaryError("Final durable feed hash does not match the completed Step 6J marker.")

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6j_render_canary_result",
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "completed": True,
        "activation_id": activation_id,
        "date": date,
        "season": int(season),
        "revision": revision,
        "image_ref": image_ref,
        "service_id": service_id,
        "service_url": service_url,
        "initial_deploy_id": initial_deploy_id,
        "closing_deploy_id": closing_deploy_id,
        "canary": {
            "status": canary_result.get("status") if canary_result else None,
            "offer_side_count": canary_result.get("offer_side_count") if canary_result else None,
            "snapshot_sha256": canary_result.get("snapshot_sha256") if canary_result else None,
            "post_write_sha256": canary_result.get("post_write_sha256") if canary_result else None,
            "verified_persistent_feed_sha256": canary_result.get("verified_persistent_feed_sha256") if canary_result else None,
            "reconciliation_fingerprint_sha256": canary_result.get("reconciliation_fingerprint_sha256") if canary_result else None,
            "attestation_sha256": canary_result.get("attestation_sha256") if canary_result else None,
        },
        "final": {
            "canary_enabled": final_status.get("canary_enabled") if final_status else None,
            "direct_sync_enabled": final_status.get("direct_sync_enabled") if final_status else None,
            "reconciled_sync_enabled": final_status.get("reconciled_sync_enabled") if final_status else None,
            "production_runtime_enabled": final_status.get("production_runtime_enabled") if final_status else None,
            "feed_content_sha256": final_status.get("feed_content_sha256") if final_status else None,
            "canary_state": final_status.get("canary_state") if final_status else None,
        },
        "safety": {
            "paid_render_resources_created": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "write_switches_disabled_after_canary": True,
            "ingest_token_returned": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the WNBA Step 6J one-shot Render canary.")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--activation-id", required=True)
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = _clean(os.environ.get(RENDER_API_KEY_ENV))
    owner_id = _clean(os.environ.get(RENDER_OWNER_ID_ENV))
    if not api_key:
        raise SystemExit(f"{RENDER_API_KEY_ENV} is required.")
    result = run_render_canary(
        revision=args.revision,
        release_id=args.release_id,
        image_ref=args.image_ref,
        activation_id=args.activation_id,
        date=args.date,
        season=args.season,
        api_key=api_key,
        owner_id=owner_id,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
