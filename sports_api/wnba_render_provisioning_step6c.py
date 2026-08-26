"""Step 6C Render provisioning for the Kyre-owned WNBA market architecture.

This is the active provisioning path after SportsGameOdds was retired as a
required dependency. It reuses the hardened Step 5Z Render client but builds a
new service contract that contains no SportsGameOdds secret or runtime binding.
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

from sports_api.collectors.wnba_kyre_market_feed import (
    DEFAULT_KYRE_MARKET_FEED_PATH,
    KYRE_MARKET_FEED_PATH_ENV,
    MARKET_PROVIDER_MODE_ENV,
)
from sports_api.wnba_render_attachment_readiness import (
    ATTACHMENT_EVIDENCE_ENV,
    ATTACHMENT_VERIFIED_ENV,
    DEFAULT_DISK_MOUNT_PATH,
    DEFAULT_DISK_NAME,
    DEFAULT_DISK_SIZE_GB,
    DEFAULT_INSTANCE_COUNT,
    DEFAULT_REGISTRY_CREDENTIAL_NAME,
    DEFAULT_SERVICE_NAME,
    DEPLOYED_IMAGE_REF_ENV,
    DISK_ID_ENV,
    DISK_MOUNT_PATH_ENV,
    DISK_NAME_ENV,
    DISK_SIZE_GB_ENV,
    INSTANCE_COUNT_ENV,
    REGISTRY_ACCESS_VERIFIED_ENV,
    SECRET_WIRING_VERIFIED_ENV,
    expected_render_env_values,
)
from sports_api.wnba_render_provisioning import (
    ALLOW_PAID_PROVISIONING_ENV,
    DEFAULT_DEPLOY_TIMEOUT_SECONDS,
    DEFAULT_HEALTH_PATH,
    DEFAULT_PLAN,
    DEFAULT_POLL_SECONDS,
    DEFAULT_REGION,
    GHCR_TOKEN_ENV,
    GHCR_USERNAME_ENV,
    RENDER_API_KEY_ENV,
    RENDER_OWNER_ID_ENV,
    RenderAPIClient,
    WNBARenderProvisioningAPIError,
    WNBARenderProvisioningConfigurationError,
    WNBARenderProvisioningConflictError,
    WNBARenderProvisioningPaymentConfirmationError,
    _deploy_from_create,
    _service_from_create,
    _service_image_ref,
    _service_runtime,
    _service_type,
    _service_url,
    ensure_registry_credential,
    resolve_owner_id,
    wait_for_deploy,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6C owned-market Render provisioner"
MODEL_VERSION = "wnba_step_6c_owned_market_render_provisioner_v1"
SCHEMA_VERSION = MODEL_VERSION

PROVISIONED_ENV = "WNBA_RENDER_PROVISIONED"
PROVISION_EVIDENCE_ENV = "WNBA_RENDER_PROVISION_EVIDENCE_SHA256"
SERVICE_ID_ENV = "WNBA_RENDER_SERVICE_ID"
SERVICE_URL_ENV = "WNBA_RENDER_SERVICE_URL"
DEPLOY_ID_ENV = "WNBA_RENDER_DEPLOY_ID"
ARCHIVE_HMAC_ENV = "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"
LEGACY_SGO_ENV = "SPORTSGAMEODDS_API_KEY"
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_SERVICE_RE = re.compile(r"^srv-[0-9a-z]{20}$")
_DISK_RE = re.compile(r"^dsk-[0-9a-z]{20}$")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def step6c_non_secret_environment(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> dict[str, str]:
    revision = revision.casefold()
    image_ref = image_ref.casefold()
    if not _clean(release_id):
        raise WNBARenderProvisioningConfigurationError("Step 6C release_id is required.")
    if not _SHA40_RE.fullmatch(revision):
        raise WNBARenderProvisioningConfigurationError("Step 6C revision must be a full 40-character Git SHA.")
    if not _IMAGE_RE.fullmatch(image_ref):
        raise WNBARenderProvisioningConfigurationError("Step 6C image_ref must be immutable name@sha256:<64hex>.")
    values = expected_render_env_values(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    values.update(
        {
            "PORT": "8000",
            MARKET_PROVIDER_MODE_ENV: "kyre",
            KYRE_MARKET_FEED_PATH_ENV: DEFAULT_KYRE_MARKET_FEED_PATH,
            "WNBA_PROP_FEED_FAILOVER_ORDER": "kyre",
            PROVISIONED_ENV: "false",
            SERVICE_ID_ENV: "pending",
            SERVICE_URL_ENV: "pending",
            DEPLOY_ID_ENV: "pending",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        }
    )
    return values


def build_step6c_render_plan(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str = DEFAULT_SERVICE_NAME,
    owner_id: str | None = None,
) -> dict[str, Any]:
    env_values = step6c_non_secret_environment(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6c_render_provisioning_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "release_id": release_id,
        "revision": revision.casefold(),
        "image_ref": image_ref.casefold(),
        "service_name": service_name,
        "owner_id": owner_id,
        "required_operator_secrets": [RENDER_API_KEY_ENV, GHCR_USERNAME_ENV, GHCR_TOKEN_ENV],
        "runtime_generated_secret_keys": [ARCHIVE_HMAC_ENV],
        "removed_required_dependencies": [LEGACY_SGO_ENV],
        "service": {
            "type": "web_service",
            "runtime": "image",
            "plan": DEFAULT_PLAN,
            "region": DEFAULT_REGION,
            "num_instances": DEFAULT_INSTANCE_COUNT,
            "health_check_path": DEFAULT_HEALTH_PATH,
            "persistent_disk": {
                "name": DEFAULT_DISK_NAME,
                "mount_path": DEFAULT_DISK_MOUNT_PATH,
                "size_gb": DEFAULT_DISK_SIZE_GB,
            },
            "market_provider_mode": "kyre",
            "market_feed_path": DEFAULT_KYRE_MARKET_FEED_PATH,
        },
        "non_secret_environment": env_values,
        "safety": {
            "production_runtime_enabled": False,
            "activation_approved": False,
            "sportsbook_vendor_secret_required": False,
            "sportsgameodds_injected": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
        },
    }


def _service_payload(
    *,
    owner_id: str,
    registry_credential_id: str,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str,
) -> dict[str, Any]:
    env_values = step6c_non_secret_environment(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    env_rows = [{"key": key, "value": value} for key, value in sorted(env_values.items())]
    env_rows.append({"key": ARCHIVE_HMAC_ENV, "generateValue": True})
    return {
        "type": "web_service",
        "name": service_name,
        "ownerId": owner_id,
        "autoDeploy": "no",
        "image": {
            "ownerId": owner_id,
            "registryCredentialId": registry_credential_id,
            "imagePath": image_ref.casefold(),
        },
        "envVars": env_rows,
        "serviceDetails": {
            "runtime": "image",
            "healthCheckPath": DEFAULT_HEALTH_PATH,
            "numInstances": DEFAULT_INSTANCE_COUNT,
            "plan": DEFAULT_PLAN,
            "region": DEFAULT_REGION,
            "maxShutdownDelaySeconds": 60,
            "disk": {
                "name": DEFAULT_DISK_NAME,
                "mountPath": DEFAULT_DISK_MOUNT_PATH,
                "sizeGB": DEFAULT_DISK_SIZE_GB,
            },
        },
    }


def _ensure_service(
    client: RenderAPIClient,
    *,
    owner_id: str,
    registry_credential_id: str,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    existing = client.list_services(owner_id, service_name)
    if len(existing) > 1:
        raise WNBARenderProvisioningConflictError(f"Multiple Render services are named {service_name}.")
    if existing:
        service = existing[0]
        if _service_type(service) != "web_service":
            raise WNBARenderProvisioningConflictError("Existing Step 6C service is not a web service.")
        if _service_runtime(service) not in {None, "image"}:
            raise WNBARenderProvisioningConflictError("Existing Step 6C service is not image-backed.")
        existing_image = _service_image_ref(service)
        if existing_image and existing_image != image_ref.casefold():
            raise WNBARenderProvisioningConflictError(
                "Existing Step 6C service points at another immutable image; refusing mutation."
            )
        return service, None, False
    document = client.create_service(
        _service_payload(
            owner_id=owner_id,
            registry_credential_id=registry_credential_id,
            release_id=release_id,
            revision=revision,
            image_ref=image_ref,
            service_name=service_name,
        )
    )
    return _service_from_create(document), _deploy_from_create(document), True


def _env_map(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        key = _clean(row.get("key") or row.get("name"))
        if key:
            result[key] = _clean(row.get("value")) or ""
    return result


def validate_step6c_render_state(
    *,
    service: Mapping[str, Any],
    disks: list[Mapping[str, Any]],
    instances: list[Mapping[str, Any]],
    env_vars: list[Mapping[str, Any]],
    expected_owner_id: str,
    expected_image_ref: str,
    expected_service_name: str,
) -> dict[str, Any]:
    failures: list[str] = []
    service_id = _clean(service.get("id"))
    owner = _clean(service.get("ownerId") or service.get("owner_id"))
    url = _service_url(service)
    image = _service_image_ref(service)
    if not service_id or not _SERVICE_RE.fullmatch(service_id): failures.append("service_id_invalid")
    if _clean(service.get("name")) != expected_service_name: failures.append("service_name_mismatch")
    if owner not in {None, expected_owner_id}: failures.append("owner_mismatch")
    if _service_type(service) != "web_service": failures.append("service_type_not_web")
    if _service_runtime(service) != "image": failures.append("runtime_not_image")
    if image != expected_image_ref.casefold(): failures.append("immutable_image_mismatch")
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".onrender.com"): failures.append("service_url_invalid")

    matching = []
    for disk in disks:
        name = _clean(disk.get("name"))
        mount = _clean(disk.get("mountPath") or disk.get("mount_path"))
        try: size = int(disk.get("sizeGB") or disk.get("size_gb") or 0)
        except (TypeError, ValueError): size = 0
        if name == DEFAULT_DISK_NAME and mount == DEFAULT_DISK_MOUNT_PATH and size >= DEFAULT_DISK_SIZE_GB:
            matching.append((disk, size))
    disk_id = None
    disk_size = None
    if len(matching) != 1:
        failures.append("persistent_disk_mismatch")
    else:
        disk_id = _clean(matching[0][0].get("id"))
        disk_size = matching[0][1]
        if not disk_id or not _DISK_RE.fullmatch(disk_id): failures.append("persistent_disk_id_invalid")
    if len(instances) != 1: failures.append("instance_count_not_one")

    env = _env_map(env_vars)
    if env.get("WNBA_PRODUCTION_RUNTIME_ENABLED", "").casefold() != "false": failures.append("runtime_not_fail_closed")
    if env.get(MARKET_PROVIDER_MODE_ENV, "").casefold() != "kyre": failures.append("market_mode_not_kyre")
    if env.get(KYRE_MARKET_FEED_PATH_ENV) != DEFAULT_KYRE_MARKET_FEED_PATH: failures.append("kyre_market_path_mismatch")
    if env.get("WNBA_PROP_FEED_FAILOVER_ORDER", "").casefold() != "kyre": failures.append("failover_order_not_kyre")
    if not _clean(env.get(ARCHIVE_HMAC_ENV)): failures.append("archive_hmac_missing")

    identity = {
        "model_version": MODEL_VERSION,
        "service_id": service_id,
        "service_name": expected_service_name,
        "owner_id": expected_owner_id,
        "service_url": url,
        "image_ref": expected_image_ref.casefold(),
        "disk_id": disk_id,
        "disk_size_gb": disk_size,
        "instance_count": len(instances),
        "market_provider_mode": "kyre",
        "market_feed_path": DEFAULT_KYRE_MARKET_FEED_PATH,
    }
    return {
        "passed": not failures,
        "failures": failures,
        "identity": identity,
        "evidence_sha256": _hash(identity),
        "service_id": service_id,
        "service_url": url,
        "disk_id": disk_id,
        "disk_size_gb": disk_size,
        "instance_count": len(instances),
        "sportsgameodds_required": False,
        "secret_values_returned": False,
    }


def _remote_pre_activation(base_url: str, *, timeout_seconds: float, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    requests = (
        ("health", "/health", {200}),
        ("runtime_readiness", "/api/v1/wnba/runtime/readiness", {200}),
        ("runtime_health", "/api/v1/wnba/runtime/health", {503}),
        ("current_board", "/api/v1/wnba/rankings/player-props/current?require_current=true", {200, 409}),
    )
    statuses: dict[str, int] = {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport, follow_redirects=False) as client:
        for name, path, allowed in requests:
            response = client.get(path)
            statuses[name] = response.status_code
            if response.status_code not in allowed:
                raise WNBARenderProvisioningAPIError(f"Step 6C preactivation GET {path} returned HTTP {response.status_code}.")
    return {"passed": True, "statuses": statuses, "request_count": len(requests), "all_methods_get": True}


def provision_step6c_render_staging(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    api_key: str,
    ghcr_username: str,
    ghcr_token: str,
    owner_id: str | None = None,
    service_name: str = DEFAULT_SERVICE_NAME,
    confirm_paid_provisioning: bool = False,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = 20.0,
    deploy_timeout_seconds: float = DEFAULT_DEPLOY_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    transport: httpx.BaseTransport | None = None,
    remote_transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    environment = os.environ if env is None else env
    if not (confirm_paid_provisioning and _truthy(environment, ALLOW_PAID_PROVISIONING_ENV, False)):
        raise WNBARenderProvisioningPaymentConfirmationError(
            "Step 6C paid Render provisioning requires explicit confirmation and WNBA_RENDER_ALLOW_PAID_PROVISIONING=true."
        )
    if _truthy(environment, "WNBA_PRODUCTION_RUNTIME_ENABLED", False):
        raise WNBARenderProvisioningConfigurationError("Step 6C refuses provisioning while production runtime is enabled.")
    if not all(_clean(v) for v in (api_key, ghcr_username, ghcr_token)):
        raise WNBARenderProvisioningConfigurationError("Step 6C requires Render API key and GHCR username/token only.")
    build_step6c_render_plan(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
        owner_id=owner_id,
    )

    actions: list[str] = []
    with RenderAPIClient(api_key=api_key, timeout_seconds=timeout_seconds, transport=transport) as client:
        resolved_owner = resolve_owner_id(client, owner_id)
        actions.append("workspace_verified")
        credential = ensure_registry_credential(client, owner_id=resolved_owner, username=ghcr_username, token=ghcr_token)
        credential_id = _clean(credential.get("id"))
        if not credential_id:
            raise WNBARenderProvisioningAPIError("Step 6C registry credential has no ID.")
        actions.append("registry_credential_ready")
        service, initial_deploy, created = _ensure_service(
            client,
            owner_id=resolved_owner,
            registry_credential_id=credential_id,
            release_id=release_id,
            revision=revision,
            image_ref=image_ref,
            service_name=service_name,
        )
        service_id = _clean(service.get("id"))
        if not service_id:
            raise WNBARenderProvisioningAPIError("Step 6C Render service has no ID.")
        actions.append("service_created" if created else "service_reused")
        initial_deploy_id = _clean(initial_deploy.get("id")) if initial_deploy else None
        if initial_deploy_id:
            wait_for_deploy(client, service_id=service_id, deploy_id=initial_deploy_id, timeout_seconds=deploy_timeout_seconds, poll_seconds=poll_seconds)
            actions.append("initial_deploy_live")
        service = client.get_service(service_id)
        state = validate_step6c_render_state(
            service=service,
            disks=client.list_disks(service_id),
            instances=client.list_instances(service_id),
            env_vars=client.list_env_vars(service_id),
            expected_owner_id=resolved_owner,
            expected_image_ref=image_ref,
            expected_service_name=service_name,
        )
        if not state["passed"]:
            raise WNBARenderProvisioningConflictError("Step 6C Render verification failed: " + ", ".join(state["failures"]))
        actions.append("owned_market_render_state_verified")
        service_url = state["service_url"]
        disk_id = state["disk_id"]
        evidence = state["evidence_sha256"]
        for key, value in {
            "WNBA_STAGING_EXTERNAL_URL": service_url,
            PROVISIONED_ENV: "true",
            PROVISION_EVIDENCE_ENV: evidence,
            SERVICE_ID_ENV: service_id,
            SERVICE_URL_ENV: service_url,
            DEPLOYED_IMAGE_REF_ENV: image_ref.casefold(),
            DISK_ID_ENV: disk_id,
            DISK_NAME_ENV: DEFAULT_DISK_NAME,
            DISK_MOUNT_PATH_ENV: DEFAULT_DISK_MOUNT_PATH,
            DISK_SIZE_GB_ENV: str(state["disk_size_gb"]),
            INSTANCE_COUNT_ENV: str(state["instance_count"]),
            REGISTRY_ACCESS_VERIFIED_ENV: "true",
            SECRET_WIRING_VERIFIED_ENV: "true",
            ATTACHMENT_VERIFIED_ENV: "true",
            ATTACHMENT_EVIDENCE_ENV: evidence,
        }.items():
            client.put_env_var(service_id, key, str(value))
        actions.append("sanitized_attestation_written")
        deploy = client.trigger_deploy(service_id, image_ref.casefold())
        deploy_id = _clean(deploy.get("id"))
        if not deploy_id:
            raise WNBARenderProvisioningAPIError("Step 6C attestation deploy has no ID.")
        client.put_env_var(service_id, DEPLOY_ID_ENV, deploy_id)
        wait_for_deploy(client, service_id=service_id, deploy_id=deploy_id, timeout_seconds=deploy_timeout_seconds, poll_seconds=poll_seconds)
        actions.append("attested_deploy_live")

    remote = _remote_pre_activation(service_url, timeout_seconds=timeout_seconds, transport=remote_transport)
    actions.append("remote_pre_activation_smoke_green")
    identity = {
        "release_id": release_id,
        "revision": revision.casefold(),
        "image_ref": image_ref.casefold(),
        "owner_id": resolved_owner,
        "service_id": service_id,
        "service_url": service_url,
        "disk_id": disk_id,
        "deploy_id": deploy_id,
        "market_provider_mode": "kyre",
        "market_feed_path": DEFAULT_KYRE_MARKET_FEED_PATH,
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6c_render_provisioning_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "provisioning_complete": True,
        "phase": "owned_market_render_staging_provisioned_pre_activation",
        "identity": identity,
        "result_sha256": _hash(identity),
        "actions": actions,
        "remote_smoke": remote,
        "safety": {
            "production_runtime_enabled": False,
            "activation_approved": False,
            "sportsgameodds_required": False,
            "sportsgameodds_injected": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "operator_secret_values_returned": False,
            "paid_provisioning_was_explicitly_confirmed": True,
        },
    }
