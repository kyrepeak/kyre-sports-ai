"""WNBA Step 5Y Render attachment + persistent-disk + secret-wiring gate.

Step 5Y sits outside frozen Steps 5U/5V/5W/5X. It does not activate the
production runtime, call a sportsbook, run Monte Carlo, or mutate Render.

The network-free readiness gate requires a green Step 5X deployment plus a
sanitized attachment attestation produced after the real Render service has
successfully pulled the exact immutable GHCR digest, attached one persistent
disk, and received the required runtime secrets. A separate read-only Render
API verifier is provided for operator/CI use. That verifier issues GET requests
only and never returns secret values.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

import httpx

from sports_api.wnba_real_staging_deployment import get_real_staging_deployment_readiness

MODEL_SOURCE = "Kyre Sports API WNBA Step 5Y Render attachment readiness"
MODEL_VERSION = "wnba_step_5y_render_attachment_readiness_v1"
SCHEMA_VERSION = "wnba_step_5y_render_attachment_readiness_v1"

RENDER_API_BASE_URL = "https://api.render.com"
RENDER_API_KEY_ENV = "RENDER_API_KEY"
ATTACHMENT_VERIFIED_ENV = "WNBA_RENDER_ATTACHMENT_VERIFIED"
ATTACHMENT_EVIDENCE_ENV = "WNBA_RENDER_ATTACHMENT_EVIDENCE_SHA256"
DEPLOYED_IMAGE_REF_ENV = "WNBA_RENDER_DEPLOYED_IMAGE_REF"
DISK_ID_ENV = "WNBA_RENDER_DISK_ID"
DISK_NAME_ENV = "WNBA_RENDER_DISK_NAME"
DISK_MOUNT_PATH_ENV = "WNBA_RENDER_DISK_MOUNT_PATH"
DISK_SIZE_GB_ENV = "WNBA_RENDER_DISK_SIZE_GB"
INSTANCE_COUNT_ENV = "WNBA_RENDER_INSTANCE_COUNT"
REGISTRY_ACCESS_VERIFIED_ENV = "WNBA_RENDER_REGISTRY_ACCESS_VERIFIED"
SECRET_WIRING_VERIFIED_ENV = "WNBA_RENDER_SECRET_WIRING_VERIFIED"
REGISTRY_CREDENTIAL_NAME_ENV = "WNBA_RENDER_REGISTRY_CREDENTIAL_NAME"

DEFAULT_DISK_NAME = "kyre-sports-api-staging-data"
DEFAULT_DISK_MOUNT_PATH = "/var/lib/kyre-sports-api"
DEFAULT_DISK_SIZE_GB = 1
DEFAULT_INSTANCE_COUNT = 1
DEFAULT_REGISTRY_CREDENTIAL_NAME = "kyre-sports-ghcr"
DEFAULT_SERVICE_NAME = "kyre-sports-api-staging"

_IMAGE_REF_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DISK_ID_RE = re.compile(r"^dsk-[0-9a-z]{20}$")

SECRET_ENV_KEYS = (
    "SPORTSGAMEODDS_API_KEY",
    "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET",
)


class WNBARenderAttachmentError(RuntimeError):
    pass


class WNBARenderAttachmentNotReadyError(WNBARenderAttachmentError):
    pass


class WNBARenderAPIVerificationError(WNBARenderAttachmentError):
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
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _attachment_identity_payload(
    *,
    step5x_identity: str | None,
    service_id: str | None,
    service_name: str | None,
    deployed_image_ref: str | None,
    disk_id: str | None,
    disk_name: str | None,
    disk_mount_path: str | None,
    disk_size_gb: int | None,
    instance_count: int | None,
    registry_access_verified: bool,
    secret_wiring_verified: bool,
) -> dict[str, Any]:
    return {
        "model_version": MODEL_VERSION,
        "step_5x_deployment_identity_sha256": step5x_identity,
        "render_service_id": service_id,
        "render_service_name": service_name,
        "deployed_image_ref": deployed_image_ref,
        "disk_id": disk_id,
        "disk_name": disk_name,
        "disk_mount_path": disk_mount_path,
        "disk_size_gb": disk_size_gb,
        "instance_count": instance_count,
        "registry_access_verified": bool(registry_access_verified),
        "secret_wiring_verified": bool(secret_wiring_verified),
    }


def expected_render_env_values(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> dict[str, str]:
    """Return non-secret environment values required by the Step 5Y bundle."""
    if not _SHA40_RE.fullmatch(revision.casefold()):
        raise WNBARenderAttachmentError("Step 5Y revision must be a full 40-character Git SHA.")
    if not _IMAGE_REF_RE.fullmatch(image_ref.casefold()):
        raise WNBARenderAttachmentError("Step 5Y image_ref must use name@sha256:<64-hex>.")
    if not _clean(release_id):
        raise WNBARenderAttachmentError("Step 5Y release_id is required.")
    if not _clean(service_name):
        raise WNBARenderAttachmentError("Step 5Y service_name is required.")

    return {
        "WNBA_DEPLOYMENT_MODE": "container",
        "WNBA_DEPLOYMENT_REPLICA_COUNT": "1",
        "WEB_CONCURRENCY": "2",
        "WNBA_PERSISTENT_VOLUME_ROOT": DEFAULT_DISK_MOUNT_PATH,
        "WNBA_CURRENT_BOARD_STORE_PATH": f"{DEFAULT_DISK_MOUNT_PATH}/wnba_current_board.sqlite3",
        "WNBA_PROP_FEED_STORE_PATH": f"{DEFAULT_DISK_MOUNT_PATH}/wnba_prop_feed.sqlite3",
        "WNBA_BACKTEST_STORE_PATH": f"{DEFAULT_DISK_MOUNT_PATH}/wnba_backtest.sqlite3",
        "WNBA_BOARD_SCHEDULER_LOCK_PATH": f"{DEFAULT_DISK_MOUNT_PATH}/wnba_scheduler_lock.sqlite3",
        "WNBA_BOARD_SCHEDULER_ENABLED": "true",
        "WNBA_BOARD_AUTO_ARCHIVE_ENABLED": "true",
        "WNBA_BOARD_SCHEDULER_LOOP_SECONDS": "30",
        "WNBA_BOARD_MIN_PROVIDER_SPACING_SECONDS": "60",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_RELEASE_ID": release_id,
        "WNBA_RELEASE_CHANNEL": "production",
        "WNBA_DEPLOYMENT_REVISION": revision.casefold(),
        "WNBA_DEPLOYMENT_IMAGE_REF": image_ref.casefold(),
        "WNBA_RELEASE_INITIAL_DEPLOYMENT": "true",
        "WNBA_STAGING_HOST_PROVIDER": "render",
        "WNBA_HOST_ENVIRONMENT": "staging",
        "WNBA_STAGING_EXPECTED_SERVICE_NAME": service_name,
        "WNBA_STAGING_EXPECTED_GIT_BRANCH": "api-foundation-v1",
        "WNBA_STAGING_ALLOW_CUSTOM_DOMAIN": "false",
        "WNBA_RELEASE_REGISTRY": "ghcr.io",
        "WNBA_RELEASE_IMAGE_REPOSITORY": "ghcr.io/kyrepeak/kyre-sports-api",
        "WNBA_RELEASE_PUBLISHED_IMAGE_REF": image_ref.casefold(),
        "WNBA_RELEASE_PUBLICATION_VERIFIED": "true",
        "WNBA_RELEASE_PUBLISHER": "github-actions",
        "WNBA_RELEASE_SOURCE_REPOSITORY": "kyrepeak/kyre-sports-ai",
        "WNBA_RELEASE_HANDOFF_FORMAT": "render-staging-v1",
        DEPLOYED_IMAGE_REF_ENV: image_ref.casefold(),
        DISK_NAME_ENV: DEFAULT_DISK_NAME,
        DISK_MOUNT_PATH_ENV: DEFAULT_DISK_MOUNT_PATH,
        DISK_SIZE_GB_ENV: str(DEFAULT_DISK_SIZE_GB),
        INSTANCE_COUNT_ENV: str(DEFAULT_INSTANCE_COUNT),
        REGISTRY_ACCESS_VERIFIED_ENV: "true",
        SECRET_WIRING_VERIFIED_ENV: "true",
        ATTACHMENT_VERIFIED_ENV: "false",
        REGISTRY_CREDENTIAL_NAME_ENV: DEFAULT_REGISTRY_CREDENTIAL_NAME,
    }


def build_render_attachment_spec(
    *,
    release_id: str,
    revision: str,
    image_ref: str,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> dict[str, Any]:
    env_values = expected_render_env_values(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_render_attachment_specification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "service": {
            "provider": "render",
            "type": "web",
            "runtime": "image",
            "name": service_name,
            "plan": "starter",
            "region": "oregon",
            "num_instances": DEFAULT_INSTANCE_COUNT,
            "health_check_path": "/health",
            "image_ref": image_ref.casefold(),
            "registry_credential_name": DEFAULT_REGISTRY_CREDENTIAL_NAME,
        },
        "disk": {
            "name": DEFAULT_DISK_NAME,
            "mount_path": DEFAULT_DISK_MOUNT_PATH,
            "size_gb": DEFAULT_DISK_SIZE_GB,
        },
        "non_secret_environment": env_values,
        "secret_environment_keys": list(SECRET_ENV_KEYS),
        "post_deploy_attestation_environment": [
            ATTACHMENT_VERIFIED_ENV,
            ATTACHMENT_EVIDENCE_ENV,
            DISK_ID_ENV,
        ],
        "safety": {
            "production_runtime_enabled": False,
            "activation_approved": False,
            "single_service_instance": True,
            "persistent_disk_required": True,
            "secret_values_in_specification": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
        },
    }


def get_render_attachment_readiness(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return network-free readiness after a real Render attachment attestation."""
    environment = _environment(env)
    step5x = get_real_staging_deployment_readiness(env=environment)
    service_id = _clean(step5x.get("render_service_id"))
    service_name = _clean(step5x.get("render_service_name"))
    expected_image = (_clean(step5x.get("published_image_ref")) or "").casefold() or None
    deployed_image = (_clean(environment.get(DEPLOYED_IMAGE_REF_ENV)) or "").casefold() or None
    disk_id = (_clean(environment.get(DISK_ID_ENV)) or "").casefold() or None
    disk_name = _clean(environment.get(DISK_NAME_ENV)) or DEFAULT_DISK_NAME
    disk_mount = _clean(environment.get(DISK_MOUNT_PATH_ENV)) or DEFAULT_DISK_MOUNT_PATH
    disk_size = _int(environment.get(DISK_SIZE_GB_ENV))
    instance_count = _int(environment.get(INSTANCE_COUNT_ENV))
    registry_verified = _truthy(environment, REGISTRY_ACCESS_VERIFIED_ENV, False)
    secrets_verified = _truthy(environment, SECRET_WIRING_VERIFIED_ENV, False)
    attachment_verified = _truthy(environment, ATTACHMENT_VERIFIED_ENV, False)
    supplied_evidence = (_clean(environment.get(ATTACHMENT_EVIDENCE_ENV)) or "").casefold() or None
    activation_requested = _truthy(environment, "WNBA_PRODUCTION_RUNTIME_ENABLED", False)

    payload = _attachment_identity_payload(
        step5x_identity=_clean(step5x.get("deployment_identity_sha256")),
        service_id=service_id,
        service_name=service_name,
        deployed_image_ref=deployed_image,
        disk_id=disk_id,
        disk_name=disk_name,
        disk_mount_path=disk_mount,
        disk_size_gb=disk_size,
        instance_count=instance_count,
        registry_access_verified=registry_verified,
        secret_wiring_verified=secrets_verified,
    )
    calculated_evidence = _hash(payload)

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "required": True, "passed": bool(passed), "detail": detail})
        if not passed:
            blockers.append(f"{name}: {detail}")

    add(
        "frozen_step_5x_real_host_ready",
        step5x.get("ready_for_explicit_activation") is True,
        "Frozen Step 5X real hosted deployment is green."
        if step5x.get("ready_for_explicit_activation") is True
        else "Frozen Step 5X real hosted deployment is not green.",
    )
    add(
        "runtime_still_disabled",
        not activation_requested,
        "Production runtime remains fail-closed."
        if not activation_requested
        else "WNBA_PRODUCTION_RUNTIME_ENABLED must remain false during Step 5Y.",
    )
    add(
        "attachment_explicitly_verified",
        attachment_verified,
        "Real Render attachment was explicitly verified."
        if attachment_verified
        else f"{ATTACHMENT_VERIFIED_ENV}=true is required after read-only Render API verification.",
    )
    add(
        "deployed_image_is_immutable",
        bool(deployed_image and _IMAGE_REF_RE.fullmatch(deployed_image)),
        "Attached image is pinned by SHA-256 digest."
        if deployed_image and _IMAGE_REF_RE.fullmatch(deployed_image)
        else f"{DEPLOYED_IMAGE_REF_ENV} must use name@sha256:<64-hex>.",
    )
    add(
        "deployed_image_matches_step_5x",
        bool(deployed_image and expected_image and deployed_image == expected_image),
        "Render attachment uses the exact Step 5X immutable image."
        if deployed_image and deployed_image == expected_image
        else "Render attachment image does not match the Step 5X published digest.",
    )
    add(
        "persistent_disk_id_present",
        bool(disk_id and _DISK_ID_RE.fullmatch(disk_id)),
        "Render persistent disk ID is format-valid."
        if disk_id and _DISK_ID_RE.fullmatch(disk_id)
        else f"{DISK_ID_ENV} must contain the verified Render dsk-... identifier.",
    )
    add(
        "persistent_disk_name_matches",
        disk_name == DEFAULT_DISK_NAME,
        "Persistent disk name matches the frozen staging attachment."
        if disk_name == DEFAULT_DISK_NAME
        else f"{DISK_NAME_ENV} must be {DEFAULT_DISK_NAME}.",
    )
    add(
        "persistent_disk_mount_matches",
        disk_mount == DEFAULT_DISK_MOUNT_PATH,
        "Persistent disk mount matches the Step 5S persistent root."
        if disk_mount == DEFAULT_DISK_MOUNT_PATH
        else f"{DISK_MOUNT_PATH_ENV} must be {DEFAULT_DISK_MOUNT_PATH}.",
    )
    add(
        "persistent_disk_size_supported",
        disk_size is not None and disk_size >= DEFAULT_DISK_SIZE_GB,
        f"Persistent disk is at least {DEFAULT_DISK_SIZE_GB} GB."
        if disk_size is not None and disk_size >= DEFAULT_DISK_SIZE_GB
        else f"{DISK_SIZE_GB_ENV} must be an integer >= {DEFAULT_DISK_SIZE_GB}.",
    )
    add(
        "single_render_instance_verified",
        instance_count == DEFAULT_INSTANCE_COUNT,
        "Exactly one Render service instance is attached."
        if instance_count == DEFAULT_INSTANCE_COUNT
        else f"{INSTANCE_COUNT_ENV} must equal {DEFAULT_INSTANCE_COUNT} while SQLite locking is authoritative.",
    )
    add(
        "registry_access_verified",
        registry_verified,
        "Render successfully authenticated to/pulled from GHCR."
        if registry_verified
        else f"{REGISTRY_ACCESS_VERIFIED_ENV}=true is required after the immutable image pull succeeds.",
    )
    add(
        "required_secret_wiring_verified",
        secrets_verified,
        "Required SportsGameOdds and archive-signing secret keys are wired in Render."
        if secrets_verified
        else f"{SECRET_WIRING_VERIFIED_ENV}=true is required after secret-key presence verification.",
    )
    add(
        "attachment_evidence_is_sha256",
        bool(supplied_evidence and _SHA256_RE.fullmatch(supplied_evidence)),
        "Render attachment evidence is a valid SHA-256."
        if supplied_evidence and _SHA256_RE.fullmatch(supplied_evidence)
        else f"{ATTACHMENT_EVIDENCE_ENV} must contain the verifier-produced SHA-256.",
    )
    add(
        "attachment_evidence_matches_current_identity",
        bool(supplied_evidence and supplied_evidence == calculated_evidence),
        "Attachment evidence exactly matches current release/service/disk identity."
        if supplied_evidence == calculated_evidence
        else "Attachment evidence does not match the current immutable deployment identity.",
    )

    ready = not blockers
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_render_attachment_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "render_attachment_ready": ready,
        "ready_for_activation_checkpoint": ready,
        "phase": "render_attachment_verified" if ready else "render_attachment_blocked",
        "render_service_id": service_id,
        "render_service_name": service_name,
        "deployed_image_ref": deployed_image,
        "disk": {
            "id": disk_id,
            "name": disk_name,
            "mount_path": disk_mount,
            "size_gb": disk_size,
        },
        "instance_count": instance_count,
        "attachment_evidence_sha256": calculated_evidence,
        "supplied_attachment_evidence_sha256": supplied_evidence,
        "attachment_identity_payload": payload,
        "checks": checks,
        "blocking_reasons": blockers,
        "step_5x": {
            "ready_for_explicit_activation": step5x.get("ready_for_explicit_activation"),
            "deployment_identity_sha256": step5x.get("deployment_identity_sha256"),
            "activation_checkpoint_sha256": step5x.get("activation_checkpoint_sha256"),
        },
        "semantics": {
            "fail_closed": True,
            "frozen_step_5x_remains_authoritative": True,
            "runtime_must_remain_disabled": True,
            "readiness_is_network_free": True,
            "readiness_does_not_call_sportsbook": True,
            "readiness_does_not_run_monte_carlo": True,
            "single_render_instance_required": True,
            "persistent_disk_required": True,
            "render_api_verification_is_get_only": True,
            "secret_values_are_never_returned": True,
        },
    }


def require_render_attachment_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_render_attachment_readiness(env=env)
    if report.get("render_attachment_ready") is not True:
        raise WNBARenderAttachmentNotReadyError(
            "WNBA Step 5Y Render attachment is not ready: "
            + "; ".join(report.get("blocking_reasons") or [])
        )
    return report


def _items(document: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(document, list):
        result: list[dict[str, Any]] = []
        for row in document:
            if not isinstance(row, dict):
                continue
            unwrapped = None
            for key in keys:
                if isinstance(row.get(key), dict):
                    unwrapped = row[key]
                    break
            result.append(unwrapped if isinstance(unwrapped, dict) else row)
        return result
    if isinstance(document, dict):
        for key in ("items", "data") + keys:
            if isinstance(document.get(key), list):
                return _items(document[key], keys)
    return []


def _contains_string(document: Any, expected: str) -> bool:
    target = expected.casefold()
    if isinstance(document, str):
        return document.strip().casefold() == target
    if isinstance(document, Mapping):
        return any(_contains_string(value, expected) for value in document.values())
    if isinstance(document, list):
        return any(_contains_string(value, expected) for value in document)
    return False


def _env_mapping(document: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _items(document, ("envVar", "env_var", "environmentVariable")):
        key = _clean(row.get("key") or row.get("name"))
        value = _clean(row.get("value"))
        if key:
            result[key] = value or ""
    return result


def validate_render_api_documents(
    *,
    service_document: Mapping[str, Any],
    disks_document: Any,
    instances_document: Any,
    env_vars_document: Any,
    expected_service_id: str,
    expected_service_name: str,
    expected_image_ref: str,
    expected_env_values: Mapping[str, str],
    step5x_identity: str,
) -> dict[str, Any]:
    """Validate Render API GET responses and return sanitized attachment evidence."""
    failures: list[str] = []
    service_id = _clean(service_document.get("id"))
    service_name = _clean(service_document.get("name"))
    service_type = (_clean(service_document.get("type")) or "").casefold()

    if service_id != expected_service_id:
        failures.append("service_id_mismatch")
    if service_name != expected_service_name:
        failures.append("service_name_mismatch")
    if service_type not in {"web", "web_service"}:
        failures.append("service_type_not_web")
    if not _contains_string(service_document, expected_image_ref):
        failures.append("immutable_image_not_present_in_service_document")

    disks = _items(disks_document, ("disk",))
    matching_disks = []
    for disk in disks:
        mount = _clean(disk.get("mountPath") or disk.get("mount_path"))
        name = _clean(disk.get("name"))
        attached_service = _clean(disk.get("serviceId") or disk.get("service_id"))
        size = _int(disk.get("sizeGB") or disk.get("size_gb") or disk.get("sizeGb"))
        if (
            mount == DEFAULT_DISK_MOUNT_PATH
            and name == DEFAULT_DISK_NAME
            and (attached_service in {None, expected_service_id})
            and size is not None
            and size >= DEFAULT_DISK_SIZE_GB
        ):
            matching_disks.append(disk)
    if len(matching_disks) != 1:
        failures.append("expected_single_persistent_disk_not_found")
        disk_id = None
        disk_size = None
    else:
        disk_id = (_clean(matching_disks[0].get("id")) or "").casefold() or None
        disk_size = _int(
            matching_disks[0].get("sizeGB")
            or matching_disks[0].get("size_gb")
            or matching_disks[0].get("sizeGb")
        )
        if not disk_id or not _DISK_ID_RE.fullmatch(disk_id):
            failures.append("persistent_disk_id_invalid")

    instances = _items(instances_document, ("instance",))
    if len(instances) != DEFAULT_INSTANCE_COUNT:
        failures.append("instance_count_not_one")

    env_map = _env_mapping(env_vars_document)
    missing_env_keys: list[str] = []
    mismatched_env_keys: list[str] = []
    for key, expected in expected_env_values.items():
        if key in {ATTACHMENT_VERIFIED_ENV, ATTACHMENT_EVIDENCE_ENV, DISK_ID_ENV}:
            continue
        if key not in env_map:
            missing_env_keys.append(key)
        elif env_map[key].casefold() != str(expected).casefold():
            mismatched_env_keys.append(key)
    if missing_env_keys:
        failures.append("required_non_secret_env_keys_missing")
    if mismatched_env_keys:
        failures.append("required_non_secret_env_values_mismatch")

    missing_secret_keys = [key for key in SECRET_ENV_KEYS if key not in env_map or not _clean(env_map[key])]
    if missing_secret_keys:
        failures.append("required_secret_keys_missing")

    registry_verified = not any(
        item in failures
        for item in (
            "service_id_mismatch",
            "service_name_mismatch",
            "service_type_not_web",
            "immutable_image_not_present_in_service_document",
        )
    )
    secret_wiring_verified = not missing_secret_keys

    payload = _attachment_identity_payload(
        step5x_identity=step5x_identity,
        service_id=service_id,
        service_name=service_name,
        deployed_image_ref=expected_image_ref.casefold(),
        disk_id=disk_id,
        disk_name=DEFAULT_DISK_NAME,
        disk_mount_path=DEFAULT_DISK_MOUNT_PATH,
        disk_size_gb=disk_size,
        instance_count=len(instances),
        registry_access_verified=registry_verified,
        secret_wiring_verified=secret_wiring_verified,
    )
    evidence = _hash(payload)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_render_api_attachment_verification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "passed": not failures,
        "failures": failures,
        "service": {
            "id": service_id,
            "name": service_name,
            "type": service_type,
            "immutable_image_match": "immutable_image_not_present_in_service_document" not in failures,
        },
        "disk": {
            "id": disk_id,
            "name": DEFAULT_DISK_NAME,
            "mount_path": DEFAULT_DISK_MOUNT_PATH,
            "size_gb": disk_size,
            "matching_disk_count": len(matching_disks),
        },
        "instance_count": len(instances),
        "environment": {
            "missing_non_secret_keys": sorted(missing_env_keys),
            "mismatched_non_secret_keys": sorted(mismatched_env_keys),
            "required_secret_keys_present": not missing_secret_keys,
            "missing_secret_key_names": sorted(missing_secret_keys),
            "secret_values_returned": False,
        },
        "attachment_identity_payload": payload,
        "attachment_evidence_sha256": evidence,
        "attestation_environment": {
            ATTACHMENT_VERIFIED_ENV: "true" if not failures else "false",
            ATTACHMENT_EVIDENCE_ENV: evidence,
            DEPLOYED_IMAGE_REF_ENV: expected_image_ref.casefold(),
            DISK_ID_ENV: disk_id,
            DISK_NAME_ENV: DEFAULT_DISK_NAME,
            DISK_MOUNT_PATH_ENV: DEFAULT_DISK_MOUNT_PATH,
            DISK_SIZE_GB_ENV: str(disk_size) if disk_size is not None else None,
            INSTANCE_COUNT_ENV: str(len(instances)),
            REGISTRY_ACCESS_VERIFIED_ENV: "true" if registry_verified else "false",
            SECRET_WIRING_VERIFIED_ENV: "true" if secret_wiring_verified else "false",
        },
        "safety": {
            "render_api_requests_are_get_only": True,
            "render_api_token_returned": False,
            "secret_values_returned": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "production_runtime_activated": False,
        },
    }


def run_render_api_attachment_verification(
    *,
    service_id: str,
    service_name: str,
    image_ref: str,
    release_id: str,
    revision: str,
    step5x_identity: str,
    api_key: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = 15.0,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Read Render service/disk/instance/env metadata using GET requests only."""
    if timeout_seconds <= 0:
        raise WNBARenderAPIVerificationError("Step 5Y timeout_seconds must be positive.")
    environment = _environment(env)
    token = _clean(api_key) or _clean(environment.get(RENDER_API_KEY_ENV))
    if not token:
        raise WNBARenderAPIVerificationError(
            f"Step 5Y requires {RENDER_API_KEY_ENV} for read-only Render API verification."
        )
    if not _clean(service_id) or not _clean(service_name):
        raise WNBARenderAPIVerificationError("Step 5Y service_id and service_name are required.")
    if not _IMAGE_REF_RE.fullmatch(image_ref.casefold()):
        raise WNBARenderAPIVerificationError("Step 5Y image_ref must be immutable.")
    if not _SHA40_RE.fullmatch(revision.casefold()):
        raise WNBARenderAPIVerificationError("Step 5Y revision must be a full Git SHA.")
    if not _SHA256_RE.fullmatch(step5x_identity.casefold()):
        raise WNBARenderAPIVerificationError("Step 5Y step5x_identity must be a SHA-256.")

    expected_env = expected_render_env_values(
        release_id=release_id,
        revision=revision,
        image_ref=image_ref,
        service_name=service_name,
    )
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "kyre-sports-api-wnba-step5y/1",
    }
    requests = (
        ("service", f"/v1/services/{service_id}", None),
        ("disks", "/v1/disks", {"serviceId": service_id, "limit": "100"}),
        ("instances", f"/v1/services/{service_id}/instances", None),
        ("env_vars", f"/v1/services/{service_id}/env-vars", {"limit": "100"}),
    )
    documents: dict[str, Any] = {}
    statuses: dict[str, int] = {}
    with httpx.Client(
        base_url=RENDER_API_BASE_URL,
        headers=headers,
        timeout=timeout_seconds,
        transport=transport,
        follow_redirects=False,
    ) as client:
        for name, path, params in requests:
            response = client.get(path, params=params)
            statuses[name] = response.status_code
            if response.status_code != 200:
                raise WNBARenderAPIVerificationError(
                    f"Step 5Y Render GET {name} returned HTTP {response.status_code}."
                )
            try:
                documents[name] = response.json()
            except ValueError as exc:
                raise WNBARenderAPIVerificationError(
                    f"Step 5Y Render GET {name} did not return JSON."
                ) from exc

    report = validate_render_api_documents(
        service_document=documents["service"],
        disks_document=documents["disks"],
        instances_document=documents["instances"],
        env_vars_document=documents["env_vars"],
        expected_service_id=service_id,
        expected_service_name=service_name,
        expected_image_ref=image_ref,
        expected_env_values=expected_env,
        step5x_identity=step5x_identity,
    )
    report["render_api"] = {
        "base_url": RENDER_API_BASE_URL,
        "request_count": len(requests),
        "methods": ["GET"] * len(requests),
        "statuses": statuses,
        "api_key_returned": False,
    }
    return report
