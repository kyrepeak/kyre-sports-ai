"""WNBA Step 5Z authenticated Render image-backed staging provisioner.

Step 5Z is the first layer that is *capable* of mutating Render. It is designed
for explicit operator/CI invocation only. Importing this module, calling the
plan/status helpers, or serving the read-only API route never touches Render.

Safety invariants:
- production runtime stays OFF throughout provisioning;
- sportsbook collection and Monte Carlo are never triggered by this module;
- the Render API key, GHCR token, SportsGameOdds key, and generated archive
  signing secret are never returned or logged;
- paid Render resource creation requires an explicit double-confirmation flag;
- existing resources are reused only when their immutable identity matches;
- an image-backed Render service is verified from Render's service/deploy API,
  rather than relying on RENDER_GIT_* variables that are meaningful to
  Git-backed services.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

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

MODEL_SOURCE = "Kyre Sports API WNBA Step 5Z authenticated Render provisioner"
MODEL_VERSION = "wnba_step_5z_authenticated_render_provisioner_v1"
SCHEMA_VERSION = "wnba_step_5z_authenticated_render_provisioner_v1"

RENDER_API_BASE_URL = "https://api.render.com"
RENDER_API_KEY_ENV = "RENDER_API_KEY"
RENDER_OWNER_ID_ENV = "RENDER_OWNER_ID"
GHCR_USERNAME_ENV = "GHCR_RENDER_USERNAME"
GHCR_TOKEN_ENV = "GHCR_RENDER_TOKEN"
SPORTSGAMEODDS_API_KEY_ENV = "SPORTSGAMEODDS_API_KEY"
ALLOW_PAID_PROVISIONING_ENV = "WNBA_RENDER_ALLOW_PAID_PROVISIONING"
PROVISIONED_ENV = "WNBA_RENDER_PROVISIONED"
PROVISION_EVIDENCE_ENV = "WNBA_RENDER_PROVISION_EVIDENCE_SHA256"
SERVICE_ID_ENV = "WNBA_RENDER_SERVICE_ID"
SERVICE_URL_ENV = "WNBA_RENDER_SERVICE_URL"
DEPLOY_ID_ENV = "WNBA_RENDER_DEPLOY_ID"

DEFAULT_PLAN = "starter"
DEFAULT_REGION = "oregon"
DEFAULT_HEALTH_PATH = "/health"
DEFAULT_DEPLOY_TIMEOUT_SECONDS = 420.0
DEFAULT_POLL_SECONDS = 3.0

_IMAGE_REF_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SERVICE_ID_RE = re.compile(r"^srv-[0-9a-z]{20}$")
_DISK_ID_RE = re.compile(r"^dsk-[0-9a-z]{20}$")


class WNBARenderProvisioningError(RuntimeError):
    pass


class WNBARenderProvisioningConfigurationError(WNBARenderProvisioningError):
    pass


class WNBARenderProvisioningConflictError(WNBARenderProvisioningError):
    pass


class WNBARenderProvisioningPaymentConfirmationError(WNBARenderProvisioningError):
    pass


class WNBARenderProvisioningAPIError(WNBARenderProvisioningError):
    pass


class WNBARenderProvisioningTimeoutError(WNBARenderProvisioningError):
    pass


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


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _items(document: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(document, list):
        out: list[dict[str, Any]] = []
        for row in document:
            if not isinstance(row, dict):
                continue
            unwrapped = None
            for key in keys:
                if isinstance(row.get(key), dict):
                    unwrapped = row[key]
                    break
            out.append(unwrapped if isinstance(unwrapped, dict) else row)
        return out
    if isinstance(document, dict):
        for key in ("items", "data") + keys:
            if isinstance(document.get(key), list):
                return _items(document[key], keys)
    return []


def _service_from_create(document: Any) -> dict[str, Any]:
    if isinstance(document, dict):
        service = document.get("service")
        if isinstance(service, dict):
            return service
        if _clean(document.get("id")) and _clean(document.get("name")):
            return document
    raise WNBARenderProvisioningAPIError("Render create-service response did not contain a service object.")


def _deploy_from_create(document: Any) -> dict[str, Any] | None:
    if isinstance(document, dict) and isinstance(document.get("deploy"), dict):
        return document["deploy"]
    return None


def _service_url(service: Mapping[str, Any]) -> str | None:
    details = service.get("serviceDetails")
    if isinstance(details, Mapping):
        value = _clean(details.get("url"))
        if value:
            return value.rstrip("/")
    value = _clean(service.get("url"))
    return value.rstrip("/") if value else None


def _service_image_ref(service: Mapping[str, Any]) -> str | None:
    image = service.get("image")
    if isinstance(image, Mapping):
        value = _clean(image.get("imagePath") or image.get("imageUrl") or image.get("ref"))
        return value.casefold() if value else None
    return None


def _service_type(service: Mapping[str, Any]) -> str | None:
    value = _clean(service.get("type"))
    return value.casefold() if value else None


def _service_runtime(service: Mapping[str, Any]) -> str | None:
    details = service.get("serviceDetails")
    if isinstance(details, Mapping):
        value = _clean(details.get("runtime") or details.get("env"))
        return value.casefold() if value else None
    return None


def _disk_from_service(service: Mapping[str, Any]) -> dict[str, Any] | None:
    details = service.get("serviceDetails")
    if isinstance(details, Mapping) and isinstance(details.get("disk"), dict):
        return details["disk"]
    return None


def _env_rows(env_values: Mapping[str, str], sportsbook_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"key": key, "value": str(value)} for key, value in sorted(env_values.items())
    ]
    rows.append({"key": SPORTSGAMEODDS_API_KEY_ENV, "value": sportsbook_key})
    rows.append({"key": "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", "generateValue": True})
    return rows


def build_render_provisioning_plan(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str = DEFAULT_SERVICE_NAME,
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Build a sanitized, mutation-free plan for the exact Step 5Z service."""
    if not _clean(release_id):
        raise WNBARenderProvisioningConfigurationError("Step 5Z release_id is required.")
    revision = revision.casefold()
    image_ref = image_ref.casefold()
    if not _SHA40_RE.fullmatch(revision):
        raise WNBARenderProvisioningConfigurationError("Step 5Z revision must be a full 40-character Git SHA.")
    if not _IMAGE_REF_RE.fullmatch(image_ref):
        raise WNBARenderProvisioningConfigurationError("Step 5Z image_ref must use name@sha256:<64-hex>.")
    if not _clean(service_name):
        raise WNBARenderProvisioningConfigurationError("Step 5Z service_name is required.")

    base_env = expected_render_env_values(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    base_env.update(
        {
            PROVISIONED_ENV: "false",
            SERVICE_ID_ENV: "pending",
            SERVICE_URL_ENV: "pending",
            DEPLOY_ID_ENV: "pending",
        }
    )
    service_payload = {
        "type": "web_service",
        "name": service_name,
        "ownerId": owner_id or "<resolved-from-render-api>",
        "autoDeploy": "no",
        "image": {
            "ownerId": owner_id or "<resolved-from-render-api>",
            "registryCredentialId": "<resolved-or-created>",
            "imagePath": image_ref,
        },
        "envVars": [
            {"key": key, "value": value} for key, value in sorted(base_env.items())
        ]
        + [
            {"key": SPORTSGAMEODDS_API_KEY_ENV, "value": "<secret>"},
            {"key": "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", "generateValue": True},
        ],
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
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_render_provisioning_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "release_id": release_id,
        "revision": revision,
        "image_ref": image_ref,
        "service_name": service_name,
        "owner_id": owner_id,
        "registry_credential_name": DEFAULT_REGISTRY_CREDENTIAL_NAME,
        "service_payload": service_payload,
        "required_operator_secrets": [
            RENDER_API_KEY_ENV,
            GHCR_USERNAME_ENV,
            GHCR_TOKEN_ENV,
            SPORTSGAMEODDS_API_KEY_ENV,
        ],
        "paid_resources": {
            "service_plan": DEFAULT_PLAN,
            "persistent_disk_size_gb": DEFAULT_DISK_SIZE_GB,
            "explicit_confirmation_required": True,
        },
        "safety": {
            "mutation_free_plan": True,
            "production_runtime_enabled": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "secret_values_in_plan": False,
            "image_backed_render_contract": True,
            "render_git_metadata_not_required": True,
        },
    }


def get_render_provisioning_status(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return a fully sanitized local status. This function is network-free."""
    environment = os.environ if env is None else env
    api_key_present = bool(_clean(environment.get(RENDER_API_KEY_ENV)))
    ghcr_user_present = bool(_clean(environment.get(GHCR_USERNAME_ENV)))
    ghcr_token_present = bool(_clean(environment.get(GHCR_TOKEN_ENV)))
    provider_key_present = bool(_clean(environment.get(SPORTSGAMEODDS_API_KEY_ENV)))
    owner_id = _clean(environment.get(RENDER_OWNER_ID_ENV))
    service_id = _clean(environment.get(SERVICE_ID_ENV))
    service_url = _clean(environment.get(SERVICE_URL_ENV))
    evidence = (_clean(environment.get(PROVISION_EVIDENCE_ENV)) or "").casefold() or None
    runtime_activation = _truthy(environment, "WNBA_PRODUCTION_RUNTIME_ENABLED", False)
    paid_confirmation = _truthy(environment, ALLOW_PAID_PROVISIONING_ENV, False)
    provisioned = _truthy(environment, PROVISIONED_ENV, False)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_render_provisioning_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "provisioned": provisioned,
        "service_id": service_id,
        "service_url": service_url,
        "provision_evidence_sha256": evidence,
        "operator_credentials": {
            "render_api_key_configured": api_key_present,
            "render_owner_id_configured": bool(owner_id),
            "ghcr_username_configured": ghcr_user_present,
            "ghcr_token_configured": ghcr_token_present,
            "sportsgameodds_key_configured": provider_key_present,
            "secret_values_returned": False,
        },
        "paid_provisioning_confirmed": paid_confirmation,
        "production_runtime_enabled": runtime_activation,
        "ready_to_attempt_authenticated_provisioning": bool(
            api_key_present
            and ghcr_user_present
            and ghcr_token_present
            and provider_key_present
            and paid_confirmation
            and not runtime_activation
        ),
        "semantics": {
            "network_free": True,
            "read_only": True,
            "operator_credentials_should_live_in_ci_not_service": True,
            "render_api_key_returned": False,
            "ghcr_token_returned": False,
            "sportsbook_key_returned": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
        },
    }


class RenderAPIClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        token = _clean(api_key)
        if not token:
            raise WNBARenderProvisioningConfigurationError("Render API key is required.")
        if timeout_seconds <= 0:
            raise WNBARenderProvisioningConfigurationError("Render API timeout must be positive.")
        self._client = httpx.Client(
            base_url=RENDER_API_BASE_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "kyre-sports-api-wnba-step5z/1",
            },
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    def __enter__(self) -> "RenderAPIClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, json_body: Any = None, allowed: tuple[int, ...] = (200,)) -> Any:
        response = self._client.request(method, path, params=params, json=json_body)
        if response.status_code not in allowed:
            message = None
            try:
                body = response.json()
                if isinstance(body, dict):
                    message = _clean(body.get("message")) or _clean((body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else body.get("error"))
            except ValueError:
                message = None
            detail = f"Render API {method.upper()} {path} returned HTTP {response.status_code}"
            if message:
                detail += f": {message}"
            raise WNBARenderProvisioningAPIError(detail)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise WNBARenderProvisioningAPIError(
                f"Render API {method.upper()} {path} did not return JSON."
            ) from exc

    def list_owners(self) -> list[dict[str, Any]]:
        return _items(self.request("GET", "/v1/owners", params={"limit": 100}), ("owner",))

    def list_registry_credentials(self, owner_id: str, name: str) -> list[dict[str, Any]]:
        return _items(
            self.request(
                "GET",
                "/v1/registrycredentials",
                params={"ownerId": owner_id, "name": name, "limit": 100},
            ),
            ("registryCredential", "registry_credential"),
        )

    def create_registry_credential(self, *, owner_id: str, username: str, token: str) -> dict[str, Any]:
        document = self.request(
            "POST",
            "/v1/registrycredentials",
            json_body={
                "registry": "GITHUB",
                "name": DEFAULT_REGISTRY_CREDENTIAL_NAME,
                "username": username,
                "authToken": token,
                "ownerId": owner_id,
            },
            allowed=(200,),
        )
        if not isinstance(document, dict):
            raise WNBARenderProvisioningAPIError("Render registry credential response was not an object.")
        return document

    def list_services(self, owner_id: str, name: str) -> list[dict[str, Any]]:
        return _items(
            self.request(
                "GET",
                "/v1/services",
                params={"ownerId": owner_id, "name": name, "limit": 100},
            ),
            ("service",),
        )

    def create_service(self, payload: Mapping[str, Any]) -> Any:
        return self.request("POST", "/v1/services", json_body=dict(payload), allowed=(201,))

    def get_service(self, service_id: str) -> dict[str, Any]:
        document = self.request("GET", f"/v1/services/{service_id}")
        if not isinstance(document, dict):
            raise WNBARenderProvisioningAPIError("Render service response was not an object.")
        return document

    def list_disks(self, service_id: str) -> list[dict[str, Any]]:
        return _items(
            self.request("GET", "/v1/disks", params={"serviceId": service_id, "limit": 100}),
            ("disk",),
        )

    def list_instances(self, service_id: str) -> list[dict[str, Any]]:
        return _items(
            self.request("GET", f"/v1/services/{service_id}/instances"),
            ("instance",),
        )

    def list_env_vars(self, service_id: str) -> list[dict[str, Any]]:
        return _items(
            self.request("GET", f"/v1/services/{service_id}/env-vars", params={"limit": 100}),
            ("envVar", "env_var"),
        )

    def put_env_var(self, service_id: str, key: str, value: str | None = None, *, generate_value: bool = False) -> Any:
        body: dict[str, Any]
        if generate_value:
            body = {"generateValue": True}
        else:
            if value is None:
                raise WNBARenderProvisioningConfigurationError(f"A value is required for {key}.")
            body = {"value": value}
        return self.request("PUT", f"/v1/services/{service_id}/env-vars/{key}", json_body=body)

    def trigger_deploy(self, service_id: str, image_ref: str) -> dict[str, Any]:
        document = self.request(
            "POST",
            f"/v1/services/{service_id}/deploys",
            json_body={"imageUrl": image_ref},
            allowed=(201, 202),
        )
        if not isinstance(document, dict):
            raise WNBARenderProvisioningAPIError("Render deploy response was not an object.")
        return document

    def get_deploy(self, service_id: str, deploy_id: str) -> dict[str, Any]:
        document = self.request("GET", f"/v1/services/{service_id}/deploys/{deploy_id}")
        if not isinstance(document, dict):
            raise WNBARenderProvisioningAPIError("Render deploy status response was not an object.")
        return document


def resolve_owner_id(client: RenderAPIClient, requested_owner_id: str | None = None) -> str:
    owners = client.list_owners()
    if requested_owner_id:
        matches = [owner for owner in owners if _clean(owner.get("id")) == requested_owner_id]
        if len(matches) != 1:
            raise WNBARenderProvisioningConfigurationError(
                "Configured RENDER_OWNER_ID is not accessible to the supplied Render API key."
            )
        return requested_owner_id
    if len(owners) != 1:
        raise WNBARenderProvisioningConfigurationError(
            "Render API key can access multiple/no workspaces; set RENDER_OWNER_ID explicitly."
        )
    owner_id = _clean(owners[0].get("id"))
    if not owner_id:
        raise WNBARenderProvisioningAPIError("Render owner response did not contain an ID.")
    return owner_id


def ensure_registry_credential(
    client: RenderAPIClient,
    *,
    owner_id: str,
    username: str,
    token: str,
) -> dict[str, Any]:
    credentials = client.list_registry_credentials(owner_id, DEFAULT_REGISTRY_CREDENTIAL_NAME)
    if len(credentials) > 1:
        raise WNBARenderProvisioningConflictError(
            f"Multiple Render registry credentials are named {DEFAULT_REGISTRY_CREDENTIAL_NAME}."
        )
    if credentials:
        credential = credentials[0]
        if (_clean(credential.get("registry")) or "").casefold() != "github":
            raise WNBARenderProvisioningConflictError(
                "Existing Step 5Z registry credential is not a GitHub registry credential."
            )
        if _clean(credential.get("username")) not in {None, username}:
            raise WNBARenderProvisioningConflictError(
                "Existing Step 5Z registry credential belongs to a different username."
            )
        if not _clean(credential.get("id")):
            raise WNBARenderProvisioningAPIError("Existing Render registry credential has no ID.")
        return credential
    return client.create_registry_credential(owner_id=owner_id, username=username, token=token)


def _build_service_payload(
    *,
    owner_id: str,
    registry_credential_id: str,
    release_id: str,
    revision: str,
    image_ref: str,
    sportsbook_key: str,
    service_name: str,
) -> dict[str, Any]:
    env_values = expected_render_env_values(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    env_values.update(
        {
            PROVISIONED_ENV: "false",
            SERVICE_ID_ENV: "pending",
            SERVICE_URL_ENV: "pending",
            DEPLOY_ID_ENV: "pending",
        }
    )
    return {
        "type": "web_service",
        "name": service_name,
        "ownerId": owner_id,
        "autoDeploy": "no",
        "image": {
            "ownerId": owner_id,
            "registryCredentialId": registry_credential_id,
            "imagePath": image_ref,
        },
        "envVars": _env_rows(env_values, sportsbook_key),
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


def ensure_service(
    client: RenderAPIClient,
    *,
    owner_id: str,
    registry_credential_id: str,
    release_id: str,
    revision: str,
    image_ref: str,
    sportsbook_key: str,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    existing = client.list_services(owner_id, service_name)
    if len(existing) > 1:
        raise WNBARenderProvisioningConflictError(
            f"Multiple Render services are named {service_name}."
        )
    if existing:
        service = existing[0]
        if _service_type(service) != "web_service":
            raise WNBARenderProvisioningConflictError("Existing Step 5Z service is not a web service.")
        if _service_runtime(service) not in {None, "image"}:
            raise WNBARenderProvisioningConflictError("Existing Step 5Z service is not image-backed.")
        existing_image = _service_image_ref(service)
        if existing_image and existing_image != image_ref.casefold():
            raise WNBARenderProvisioningConflictError(
                "Existing Step 5Z service points at a different immutable image; refusing to mutate it."
            )
        return service, None, False

    payload = _build_service_payload(
        owner_id=owner_id,
        registry_credential_id=registry_credential_id,
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        sportsbook_key=sportsbook_key,
        service_name=service_name,
    )
    document = client.create_service(payload)
    return _service_from_create(document), _deploy_from_create(document), True


def wait_for_deploy(
    client: RenderAPIClient,
    *,
    service_id: str,
    deploy_id: str,
    timeout_seconds: float = DEFAULT_DEPLOY_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> dict[str, Any]:
    if timeout_seconds <= 0 or poll_seconds <= 0:
        raise WNBARenderProvisioningConfigurationError("Deploy timeout and poll interval must be positive.")
    deadline = time.monotonic() + timeout_seconds
    terminal_failures = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
    while True:
        deploy = client.get_deploy(service_id, deploy_id)
        status = (_clean(deploy.get("status")) or "").casefold()
        if status == "live":
            return deploy
        if status in terminal_failures:
            raise WNBARenderProvisioningAPIError(
                f"Render deploy {deploy_id} ended with status={status}."
            )
        if time.monotonic() >= deadline:
            raise WNBARenderProvisioningTimeoutError(
                f"Timed out waiting for Render deploy {deploy_id}; last status={status or 'unknown'}."
            )
        time.sleep(poll_seconds)


def validate_image_backed_service(
    *,
    service: Mapping[str, Any],
    disks: list[Mapping[str, Any]],
    instances: list[Mapping[str, Any]],
    env_vars: list[Mapping[str, Any]],
    expected_owner_id: str,
    expected_image_ref: str,
    expected_service_name: str,
) -> dict[str, Any]:
    """Validate real Render state without requiring Git-backed metadata."""
    failures: list[str] = []
    service_id = _clean(service.get("id"))
    service_name = _clean(service.get("name"))
    owner_id = _clean(service.get("ownerId") or service.get("owner_id"))
    service_type = _service_type(service)
    runtime = _service_runtime(service)
    image_ref = _service_image_ref(service)
    service_url = _service_url(service)

    if not service_id or not _SERVICE_ID_RE.fullmatch(service_id):
        failures.append("service_id_invalid")
    if service_name != expected_service_name:
        failures.append("service_name_mismatch")
    if owner_id not in {None, expected_owner_id}:
        failures.append("owner_id_mismatch")
    if service_type != "web_service":
        failures.append("service_type_not_web_service")
    if runtime != "image":
        failures.append("service_runtime_not_image")
    if image_ref != expected_image_ref.casefold():
        failures.append("immutable_image_mismatch")
    if not service_url or urlparse(service_url).scheme != "https" or not (urlparse(service_url).hostname or "").endswith(".onrender.com"):
        failures.append("service_url_not_render_https")

    matching_disks = []
    for disk in disks:
        name = _clean(disk.get("name"))
        mount = _clean(disk.get("mountPath") or disk.get("mount_path"))
        try:
            size = int(disk.get("sizeGB") or disk.get("size_gb") or 0)
        except (TypeError, ValueError):
            size = 0
        if name == DEFAULT_DISK_NAME and mount == DEFAULT_DISK_MOUNT_PATH and size >= DEFAULT_DISK_SIZE_GB:
            matching_disks.append(disk)
    if len(matching_disks) != 1:
        failures.append("persistent_disk_mismatch")
        disk_id = None
        disk_size = None
    else:
        disk_id = _clean(matching_disks[0].get("id"))
        try:
            disk_size = int(matching_disks[0].get("sizeGB") or matching_disks[0].get("size_gb"))
        except (TypeError, ValueError):
            disk_size = None
        if not disk_id or not _DISK_ID_RE.fullmatch(disk_id):
            failures.append("persistent_disk_id_invalid")

    if len(instances) != DEFAULT_INSTANCE_COUNT:
        failures.append("instance_count_not_one")

    env_map: dict[str, str] = {}
    for row in env_vars:
        key = _clean(row.get("key") or row.get("name"))
        value = _clean(row.get("value"))
        if key:
            env_map[key] = value or ""
    if env_map.get("WNBA_PRODUCTION_RUNTIME_ENABLED", "").casefold() != "false":
        failures.append("production_runtime_not_disabled")
    for key in (SPORTSGAMEODDS_API_KEY_ENV, "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"):
        if not _clean(env_map.get(key)):
            failures.append(f"required_secret_missing:{key}")

    identity = {
        "model_version": MODEL_VERSION,
        "service_id": service_id,
        "service_name": service_name,
        "owner_id": expected_owner_id,
        "service_url": service_url,
        "image_ref": expected_image_ref.casefold(),
        "disk_id": disk_id,
        "disk_name": DEFAULT_DISK_NAME,
        "disk_mount_path": DEFAULT_DISK_MOUNT_PATH,
        "disk_size_gb": disk_size,
        "instance_count": len(instances),
        "runtime_activation": False,
    }
    evidence = _hash(identity)
    return {
        "passed": not failures,
        "failures": failures,
        "service": {
            "id": service_id,
            "name": service_name,
            "url": service_url,
            "type": service_type,
            "runtime": runtime,
            "image_ref": image_ref,
        },
        "disk": {
            "id": disk_id,
            "name": DEFAULT_DISK_NAME,
            "mount_path": DEFAULT_DISK_MOUNT_PATH,
            "size_gb": disk_size,
        },
        "instance_count": len(instances),
        "provision_identity": identity,
        "provision_evidence_sha256": evidence,
        "secret_values_returned": False,
        "render_git_metadata_required": False,
    }


def _verify_remote_pre_activation(base_url: str, *, timeout_seconds: float, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    requests = (
        ("health", "/health", {200}),
        ("runtime_readiness", "/api/v1/wnba/runtime/readiness", {200}),
        ("runtime_health", "/api/v1/wnba/runtime/health", {503}),
        ("current_board", "/api/v1/wnba/rankings/player-props/current?require_current=true", {200, 409}),
        ("step5z_status", "/api/v1/wnba/runtime/render-provisioning", {200}),
    )
    statuses: dict[str, int] = {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport, follow_redirects=False) as client:
        for name, path, allowed in requests:
            response = client.get(path)
            statuses[name] = response.status_code
            if response.status_code not in allowed:
                raise WNBARenderProvisioningAPIError(
                    f"Hosted pre-activation GET {path} returned HTTP {response.status_code}."
                )
    return {
        "passed": True,
        "statuses": statuses,
        "request_count": len(requests),
        "all_methods_get": True,
        "manual_refresh_called": False,
        "sportsbook_called": False,
        "monte_carlo_run": False,
    }


def provision_render_staging(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    api_key: str,
    ghcr_username: str,
    ghcr_token: str,
    sportsbook_key: str,
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
    """Provision and verify the exact image-backed Render staging service.

    This is intentionally not called by FastAPI startup or any public endpoint.
    """
    environment = os.environ if env is None else env
    paid_confirmed = confirm_paid_provisioning and _truthy(
        environment, ALLOW_PAID_PROVISIONING_ENV, False
    )
    if not paid_confirmed:
        raise WNBARenderProvisioningPaymentConfirmationError(
            f"Step 5Z creates a {DEFAULT_PLAN} Render web service with a persistent disk. "
            f"Pass confirm_paid_provisioning=True and set {ALLOW_PAID_PROVISIONING_ENV}=true."
        )
    if _truthy(environment, "WNBA_PRODUCTION_RUNTIME_ENABLED", False):
        raise WNBARenderProvisioningConfigurationError(
            "Step 5Z refuses to provision while WNBA_PRODUCTION_RUNTIME_ENABLED=true."
        )
    if not all(_clean(value) for value in (api_key, ghcr_username, ghcr_token, sportsbook_key)):
        raise WNBARenderProvisioningConfigurationError(
            "Step 5Z requires Render API, GHCR username/token, and SportsGameOdds credentials."
        )
    build_render_provisioning_plan(
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
        credential = ensure_registry_credential(
            client,
            owner_id=resolved_owner,
            username=ghcr_username,
            token=ghcr_token,
        )
        credential_id = _clean(credential.get("id"))
        if not credential_id:
            raise WNBARenderProvisioningAPIError("Resolved Render registry credential has no ID.")
        actions.append("registry_credential_ready")

        service, initial_deploy, created = ensure_service(
            client,
            owner_id=resolved_owner,
            registry_credential_id=credential_id,
            release_id=release_id,
            revision=revision,
            image_ref=image_ref.casefold(),
            sportsbook_key=sportsbook_key,
            service_name=service_name,
        )
        service_id = _clean(service.get("id"))
        if not service_id:
            raise WNBARenderProvisioningAPIError("Resolved Render service has no ID.")
        actions.append("service_created" if created else "service_reused")

        initial_deploy_id = _clean(initial_deploy.get("id")) if initial_deploy else None
        if initial_deploy_id:
            wait_for_deploy(
                client,
                service_id=service_id,
                deploy_id=initial_deploy_id,
                timeout_seconds=deploy_timeout_seconds,
                poll_seconds=poll_seconds,
            )
            actions.append("initial_deploy_live")

        service = client.get_service(service_id)
        disks = client.list_disks(service_id)
        instances = client.list_instances(service_id)
        env_vars = client.list_env_vars(service_id)
        verification = validate_image_backed_service(
            service=service,
            disks=disks,
            instances=instances,
            env_vars=env_vars,
            expected_owner_id=resolved_owner,
            expected_image_ref=image_ref,
            expected_service_name=service_name,
        )
        if not verification["passed"]:
            raise WNBARenderProvisioningConflictError(
                "Step 5Z Render attachment verification failed: "
                + ", ".join(verification["failures"])
            )
        actions.append("render_attachment_verified")

        service_url = verification["service"]["url"]
        disk_id = verification["disk"]["id"]
        evidence = verification["provision_evidence_sha256"]
        if not service_url or not disk_id:
            raise WNBARenderProvisioningAPIError("Verified Render service URL/disk ID is missing.")

        attestation_updates = {
            "WNBA_STAGING_EXTERNAL_URL": service_url,
            PROVISIONED_ENV: "true",
            PROVISION_EVIDENCE_ENV: evidence,
            SERVICE_ID_ENV: service_id,
            SERVICE_URL_ENV: service_url,
            DEPLOYED_IMAGE_REF_ENV: image_ref.casefold(),
            DISK_ID_ENV: disk_id,
            DISK_NAME_ENV: DEFAULT_DISK_NAME,
            DISK_MOUNT_PATH_ENV: DEFAULT_DISK_MOUNT_PATH,
            DISK_SIZE_GB_ENV: str(verification["disk"]["size_gb"]),
            INSTANCE_COUNT_ENV: str(verification["instance_count"]),
            REGISTRY_ACCESS_VERIFIED_ENV: "true",
            SECRET_WIRING_VERIFIED_ENV: "true",
            ATTACHMENT_VERIFIED_ENV: "true",
            ATTACHMENT_EVIDENCE_ENV: evidence,
        }
        for key, value in attestation_updates.items():
            client.put_env_var(service_id, key, str(value))
        actions.append("sanitized_attestation_written")

        deploy = client.trigger_deploy(service_id, image_ref.casefold())
        deploy_id = _clean(deploy.get("id"))
        if not deploy_id:
            raise WNBARenderProvisioningAPIError("Render attestation deploy response has no ID.")
        client.put_env_var(service_id, DEPLOY_ID_ENV, deploy_id)
        wait_for_deploy(
            client,
            service_id=service_id,
            deploy_id=deploy_id,
            timeout_seconds=deploy_timeout_seconds,
            poll_seconds=poll_seconds,
        )
        actions.append("attested_deploy_live")

    remote = _verify_remote_pre_activation(
        service_url,
        timeout_seconds=timeout_seconds,
        transport=remote_transport,
    )
    actions.append("remote_pre_activation_smoke_green")

    result_identity = {
        "model_version": MODEL_VERSION,
        "release_id": release_id,
        "revision": revision.casefold(),
        "image_ref": image_ref.casefold(),
        "owner_id": resolved_owner,
        "service_id": service_id,
        "service_url": service_url,
        "disk_id": disk_id,
        "deploy_id": deploy_id,
        "provision_evidence_sha256": evidence,
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_render_provisioning_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "provisioning_complete": True,
        "phase": "real_render_staging_provisioned_pre_activation",
        "identity": result_identity,
        "result_sha256": _hash(result_identity),
        "actions": actions,
        "remote_smoke": remote,
        "safety": {
            "production_runtime_enabled": False,
            "activation_approved": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "operator_secret_values_returned": False,
            "render_api_key_returned": False,
            "ghcr_token_returned": False,
            "sportsbook_key_returned": False,
            "paid_provisioning_was_explicitly_confirmed": True,
            "image_backed_render_contract": True,
            "render_git_metadata_not_required": True,
        },
    }
