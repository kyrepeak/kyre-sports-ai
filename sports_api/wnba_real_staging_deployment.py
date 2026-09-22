"""WNBA Step 5X real hosted-staging pre-activation deployment verification.

Step 5X sits outside frozen Steps 5U/5V/5W. It does not provision Render,
activate the production scheduler, call a sportsbook, or run Monte Carlo.
Instead it binds the exact immutable release, real hosted Render identity,
persistent storage identity, and Step 5W pre-activation checkpoint into one
deployment attestation and provides a GET-only remote verification routine.

A Step 5X deployment is ready for explicit activation only when the deployed
host is still fail-closed: WNBA_PRODUCTION_RUNTIME_ENABLED=false,
Step 5V is green, and Step 5W reports pre_activation_checkpoint_ready.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

import httpx

from sports_api.wnba_deployment_smoke_readiness import normalize_smoke_base_url
from sports_api.wnba_hosted_staging_readiness import get_hosted_staging_readiness
from sports_api.wnba_release_publication_handoff import (
    get_release_publication_handoff_readiness,
)
from sports_api.wnba_staging_activation_gate import get_staging_activation_gate

MODEL_SOURCE = "Kyre Sports API WNBA Step 5X real hosted staging deployment"
MODEL_VERSION = "wnba_step_5x_real_hosted_staging_deployment_v1"
SCHEMA_VERSION = "wnba_step_5x_real_hosted_staging_deployment_v1"

_IMAGE_REF_RE = re.compile(r"^(?P<repo>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$")


class WNBARealStagingDeploymentError(RuntimeError):
    pass


class WNBARealStagingVerificationError(WNBARealStagingDeploymentError):
    pass


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _immutable_image(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = _IMAGE_REF_RE.fullmatch(value.casefold())
    if not match:
        return None, None
    return match.group("repo"), match.group("digest")


def get_real_staging_deployment_readiness(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Bind frozen hosted/release/activation evidence into a pre-activation attestation."""
    step5u = get_hosted_staging_readiness(env=env)
    step5v = get_release_publication_handoff_readiness(env=env)
    step5w = get_staging_activation_gate(env=env)

    host = step5u.get("host") or {}
    release = step5u.get("release") or {}
    publication = step5v.get("publication") or {}
    checkpoint_payload = step5w.get("checkpoint_payload") or {}
    checkpoint_release = checkpoint_payload.get("release") or {}
    checkpoint_host = checkpoint_payload.get("host") or {}

    external_url = _clean(step5u.get("external_url"))
    service_id = _clean(host.get("service_id"))
    service_name = _clean(host.get("service_name"))
    revision = (_clean(release.get("revision")) or "").casefold() or None
    release_id = _clean(release.get("release_id"))
    release_image = (_clean(release.get("image_ref")) or "").casefold() or None
    published_image = (
        (_clean(publication.get("published_image_ref")) or "").casefold() or None
    )
    image_repo, image_digest = _immutable_image(published_image)
    storage_identity = _clean(step5u.get("storage_identity_sha256"))
    checkpoint_storage = _clean(checkpoint_payload.get("storage_identity_sha256"))
    checkpoint = (
        (_clean(step5w.get("activation_checkpoint_sha256")) or "").casefold() or None
    )

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "required": True,
                "passed": bool(passed),
                "detail": detail,
            }
        )
        if not passed:
            blockers.append(f"{name}: {detail}")

    add(
        "frozen_step_5u_host_contract_ready",
        step5u.get("host_contract_ready") is True,
        "Frozen Step 5U real hosted-staging contract is green."
        if step5u.get("host_contract_ready") is True
        else "Frozen Step 5U hosted-staging contract is not green.",
    )
    add(
        "frozen_step_5v_handoff_ready",
        step5v.get("handoff_ready") is True,
        "Frozen Step 5V immutable publication handoff is green."
        if step5v.get("handoff_ready") is True
        else "Frozen Step 5V immutable publication handoff is not green.",
    )
    add(
        "step_5w_checkpoint_ready",
        step5w.get("checkpoint_ready") is True,
        "Step 5W pre-activation checkpoint is frozen and ready."
        if step5w.get("checkpoint_ready") is True
        else "Step 5W pre-activation checkpoint is not ready.",
    )
    add(
        "step_5w_pre_activation_phase",
        step5w.get("phase") == "pre_activation_checkpoint_ready",
        "Step 5W remains in the required pre-activation phase."
        if step5w.get("phase") == "pre_activation_checkpoint_ready"
        else "Step 5X requires Step 5W phase=pre_activation_checkpoint_ready.",
    )
    add(
        "runtime_activation_not_requested",
        step5w.get("activation_requested") is False,
        "Production runtime activation remains OFF."
        if step5w.get("activation_requested") is False
        else "Production runtime activation must remain OFF during Step 5X.",
    )
    add(
        "live_cycle_remains_blocked",
        step5w.get("live_cycle_allowed") is False,
        "Sportsbook/model live cycles remain blocked."
        if step5w.get("live_cycle_allowed") is False
        else "Step 5X must not run with live_cycle_allowed=true.",
    )
    add(
        "real_render_staging_host",
        step5u.get("provider") == "render"
        and step5u.get("environment") == "staging",
        "Deployment is a Render staging host."
        if step5u.get("provider") == "render"
        and step5u.get("environment") == "staging"
        else "Step 5X currently requires a Render staging host.",
    )
    add(
        "external_https_url_present",
        bool(external_url and external_url.casefold().startswith("https://")),
        "Real staging HTTPS URL is present."
        if external_url and external_url.casefold().startswith("https://")
        else "A real HTTPS staging URL is required.",
    )
    add(
        "render_service_identity_present",
        bool(service_id and service_name),
        "Stable Render service ID and service name are present."
        if service_id and service_name
        else "Render service ID and service name are required.",
    )
    add(
        "immutable_published_image",
        bool(image_repo and image_digest),
        "Published image is pinned by sha256 digest."
        if image_repo and image_digest
        else "Published image must use name@sha256:<64-hex>.",
    )
    add(
        "published_image_matches_release",
        bool(published_image and release_image and published_image == release_image),
        "Registry-published image exactly matches the deployed Step 5T release."
        if published_image and published_image == release_image
        else "Published image does not match the deployed immutable release image.",
    )
    add(
        "checkpoint_release_matches_deployment",
        bool(
            checkpoint_release.get("release_id") == release_id
            and (checkpoint_release.get("revision") or "").casefold() == revision
            and (checkpoint_release.get("image_ref") or "").casefold()
            == (published_image or "")
        ),
        "Step 5W checkpoint release identity matches the deployed immutable release."
        if checkpoint_release.get("release_id") == release_id
        and (checkpoint_release.get("revision") or "").casefold() == revision
        and (checkpoint_release.get("image_ref") or "").casefold()
        == (published_image or "")
        else "Step 5W checkpoint release identity drifted from the deployed release.",
    )
    add(
        "checkpoint_host_matches_deployment",
        bool(
            checkpoint_host.get("service_id") == service_id
            and checkpoint_host.get("service_name") == service_name
            and checkpoint_host.get("external_url") == external_url
        ),
        "Step 5W checkpoint host identity matches the deployed Render service."
        if checkpoint_host.get("service_id") == service_id
        and checkpoint_host.get("service_name") == service_name
        and checkpoint_host.get("external_url") == external_url
        else "Step 5W checkpoint host identity drifted from the deployed Render service.",
    )
    add(
        "persistent_storage_identity_matches_checkpoint",
        bool(
            storage_identity
            and checkpoint_storage
            and storage_identity == checkpoint_storage
            and len(storage_identity) == 64
        ),
        "Persistent storage identity exactly matches the Step 5W checkpoint."
        if storage_identity
        and checkpoint_storage
        and storage_identity == checkpoint_storage
        and len(storage_identity) == 64
        else "Persistent storage identity is missing or drifted from the Step 5W checkpoint.",
    )
    add(
        "activation_checkpoint_is_sha256",
        bool(checkpoint and len(checkpoint) == 64 and re.fullmatch(r"[0-9a-f]{64}", checkpoint)),
        "Activation checkpoint is a valid SHA-256."
        if checkpoint
        and len(checkpoint) == 64
        and re.fullmatch(r"[0-9a-f]{64}", checkpoint)
        else "Activation checkpoint is missing or malformed.",
    )

    deployment_identity_payload = {
        "model_version": MODEL_VERSION,
        "release_id": release_id,
        "revision": revision,
        "published_image_ref": published_image,
        "render_service_id": service_id,
        "render_service_name": service_name,
        "external_url": external_url,
        "storage_identity_sha256": storage_identity,
        "activation_checkpoint_sha256": checkpoint,
    }
    deployment_identity = _hash(deployment_identity_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_real_staging_deployment_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "ready_for_explicit_activation": not blockers,
        "phase": "real_host_preactivation_ready" if not blockers else "real_host_preactivation_blocked",
        "external_url": external_url,
        "release_id": release_id,
        "revision": revision,
        "published_image_ref": published_image,
        "image_repository": image_repo,
        "image_digest_sha256": image_digest,
        "render_service_id": service_id,
        "render_service_name": service_name,
        "storage_identity_sha256": storage_identity,
        "activation_checkpoint_sha256": checkpoint,
        "deployment_identity_sha256": deployment_identity,
        "deployment_identity_payload": deployment_identity_payload,
        "checks": checks,
        "blocking_reasons": blockers,
        "step_5u": {
            "host_contract_ready": step5u.get("host_contract_ready"),
            "host_identity_sha256": step5u.get("host_identity_sha256"),
        },
        "step_5v": {
            "handoff_ready": step5v.get("handoff_ready"),
            "handoff_identity_sha256": step5v.get("handoff_identity_sha256"),
        },
        "step_5w": {
            "phase": step5w.get("phase"),
            "checkpoint_ready": step5w.get("checkpoint_ready"),
            "live_cycle_allowed": step5w.get("live_cycle_allowed"),
        },
        "semantics": {
            "fail_closed": True,
            "real_host_required": True,
            "runtime_must_remain_disabled": True,
            "explicit_step_5w_activation_still_required": True,
            "readiness_makes_no_network_requests": True,
            "readiness_does_not_call_sportsbook": True,
            "readiness_does_not_run_monte_carlo": True,
            "read_path_remains_network_free": True,
            "persistent_storage_identity_is_bound": True,
            "immutable_image_digest_is_bound": True,
        },
    }


def build_real_staging_smoke_plan(base_url: str) -> dict[str, Any]:
    """Return the exact Step 5X GET-only remote pre-activation verification plan."""
    normalized = normalize_smoke_base_url(base_url)
    requests = [
        {"name": "service_health", "method": "GET", "path": "/health", "allowed_statuses": [200]},
        {"name": "step_5s_deployment", "method": "GET", "path": "/api/v1/wnba/runtime/deployment", "allowed_statuses": [200]},
        {"name": "step_5t_release", "method": "GET", "path": "/api/v1/wnba/runtime/release", "allowed_statuses": [200]},
        {"name": "step_5u_hosting", "method": "GET", "path": "/api/v1/wnba/runtime/hosting", "allowed_statuses": [200]},
        {"name": "step_5v_handoff", "method": "GET", "path": "/api/v1/wnba/runtime/handoff", "allowed_statuses": [200]},
        {"name": "step_5w_activation_gate", "method": "GET", "path": "/api/v1/wnba/runtime/activation-gate", "allowed_statuses": [200]},
        {"name": "step_5x_staging_deployment", "method": "GET", "path": "/api/v1/wnba/runtime/staging-deployment", "allowed_statuses": [200]},
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
        "data_type": "wnba_real_staging_smoke_plan",
        "schema_version": SCHEMA_VERSION,
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
            "requires_runtime_health_503": True,
            "requires_step_5w_checkpoint_ready": True,
        },
    }


def _validate_remote_documents(
    documents: Mapping[str, Mapping[str, Any]],
    statuses: Mapping[str, int],
    *,
    expected_revision: str,
    expected_release_id: str,
    expected_image_ref: str,
    expected_service_name: str,
    expected_storage_identity: str,
    expected_checkpoint: str | None = None,
) -> list[str]:
    failures: list[str] = []

    hosting = documents.get("step_5u_hosting") or {}
    handoff = documents.get("step_5v_handoff") or {}
    gate = documents.get("step_5w_activation_gate") or {}
    deployment = documents.get("step_5x_staging_deployment") or {}

    if hosting.get("host_contract_ready") is not True:
        failures.append("step_5u_hosting_not_ready")
    hosted_release = hosting.get("release") or {}
    hosted_host = hosting.get("host") or {}
    if (_clean(hosted_release.get("revision")) or "").casefold() != expected_revision.casefold():
        failures.append("revision_mismatch")
    if _clean(hosted_host.get("service_name")) != expected_service_name:
        failures.append("service_name_mismatch")
    if _clean(hosting.get("storage_identity_sha256")) != expected_storage_identity:
        failures.append("storage_identity_mismatch")

    if handoff.get("handoff_ready") is not True:
        failures.append("step_5v_handoff_not_ready")
    handoff_release = handoff.get("release") or {}
    handoff_publication = handoff.get("publication") or {}
    if _clean(handoff_release.get("release_id")) != expected_release_id:
        failures.append("release_id_mismatch")
    if (_clean(handoff_publication.get("published_image_ref")) or "").casefold() != expected_image_ref.casefold():
        failures.append("image_ref_mismatch")

    if gate.get("checkpoint_ready") is not True:
        failures.append("step_5w_checkpoint_not_ready")
    if gate.get("activation_requested") is not False:
        failures.append("activation_already_requested")
    if gate.get("live_cycle_allowed") is not False:
        failures.append("live_cycle_not_blocked")
    if expected_checkpoint and (
        (_clean(gate.get("activation_checkpoint_sha256")) or "").casefold()
        != expected_checkpoint.casefold()
    ):
        failures.append("activation_checkpoint_mismatch")

    if deployment.get("ready_for_explicit_activation") is not True:
        failures.append("step_5x_deployment_not_ready")
    if (_clean(deployment.get("revision")) or "").casefold() != expected_revision.casefold():
        failures.append("step_5x_revision_mismatch")
    if _clean(deployment.get("release_id")) != expected_release_id:
        failures.append("step_5x_release_id_mismatch")
    if (_clean(deployment.get("published_image_ref")) or "").casefold() != expected_image_ref.casefold():
        failures.append("step_5x_image_ref_mismatch")
    if _clean(deployment.get("render_service_name")) != expected_service_name:
        failures.append("step_5x_service_name_mismatch")
    if _clean(deployment.get("storage_identity_sha256")) != expected_storage_identity:
        failures.append("step_5x_storage_identity_mismatch")
    if expected_checkpoint and (
        (_clean(deployment.get("activation_checkpoint_sha256")) or "").casefold()
        != expected_checkpoint.casefold()
    ):
        failures.append("step_5x_checkpoint_mismatch")

    if statuses.get("runtime_health_pre_activation") != 503:
        failures.append("runtime_health_must_be_503_before_activation")
    if statuses.get("current_board_read") not in {200, 409}:
        failures.append("current_board_read_status_invalid")

    return failures


def run_real_staging_smoke(
    base_url: str,
    *,
    expected_revision: str,
    expected_release_id: str,
    expected_image_ref: str,
    expected_service_name: str,
    expected_storage_identity: str,
    expected_checkpoint: str | None = None,
    timeout_seconds: float = 10.0,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Run the Step 5X GET-only smoke against a real hosted staging URL."""
    if timeout_seconds <= 0:
        raise WNBARealStagingVerificationError("timeout_seconds must be greater than zero")
    plan = build_real_staging_smoke_plan(base_url)
    documents: dict[str, Mapping[str, Any]] = {}
    statuses: dict[str, int] = {}
    request_results: list[dict[str, Any]] = []

    try:
        with httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        ) as client:
            for spec in plan["requests"]:
                url = plan["base_url"] + spec["path"]
                response = client.get(url)
                status = int(response.status_code)
                statuses[spec["name"]] = status
                allowed = status in set(spec["allowed_statuses"])
                payload: Mapping[str, Any] = {}
                if response.content:
                    try:
                        parsed = response.json()
                    except Exception:
                        parsed = None
                    if isinstance(parsed, Mapping):
                        payload = parsed
                documents[spec["name"]] = payload
                request_results.append(
                    {
                        "name": spec["name"],
                        "method": "GET",
                        "path": spec["path"],
                        "status_code": status,
                        "status_allowed": allowed,
                    }
                )
    except httpx.HTTPError as exc:
        raise WNBARealStagingVerificationError(
            f"Step 5X remote verification failed: {type(exc).__name__}: {exc}"
        ) from exc

    failures = [
        f"{row['name']}_unexpected_status_{row['status_code']}"
        for row in request_results
        if not row["status_allowed"]
    ]
    failures.extend(
        _validate_remote_documents(
            documents,
            statuses,
            expected_revision=expected_revision,
            expected_release_id=expected_release_id,
            expected_image_ref=expected_image_ref,
            expected_service_name=expected_service_name,
            expected_storage_identity=expected_storage_identity,
            expected_checkpoint=expected_checkpoint,
        )
    )
    failures = list(dict.fromkeys(failures))
    deployment_doc = documents.get("step_5x_staging_deployment") or {}
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_real_staging_remote_verification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "base_url": plan["base_url"],
        "passed": not failures,
        "request_count": len(request_results),
        "requests": request_results,
        "failures": failures,
        "activation_checkpoint_sha256": deployment_doc.get(
            "activation_checkpoint_sha256"
        ),
        "deployment_identity_sha256": deployment_doc.get(
            "deployment_identity_sha256"
        ),
        "safety": plan["safety"],
    }
