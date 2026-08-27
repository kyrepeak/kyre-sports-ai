"""WNBA Step 5V immutable image publication + staging handoff readiness.

Step 5V does not publish infrastructure and does not activate the sportsbook/model
runtime. It validates that a registry-published immutable image is the exact image
recorded by Step 5T, that the frozen Step 5U hosted-staging contract is green,
and that the handoff bundle is safe to use for the first real staging deployment.

All API-facing helpers are read-only. The optional bundle writer only emits
sanitized local files; it never writes credentials, calls a sportsbook provider,
runs Monte Carlo, or provisions a host.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
from typing import Any

from sports_api.wnba_hosted_staging_readiness import get_hosted_staging_readiness
from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV

MODEL_SOURCE = "Kyre Sports API WNBA Step 5V immutable publication + staging handoff"
MODEL_VERSION = "wnba_step_5v_release_publication_handoff_v1"
SCHEMA_VERSION = "wnba_step_5v_release_publication_handoff_v1"

REGISTRY_ENV = "WNBA_RELEASE_REGISTRY"
IMAGE_REPOSITORY_ENV = "WNBA_RELEASE_IMAGE_REPOSITORY"
PUBLISHED_IMAGE_REF_ENV = "WNBA_RELEASE_PUBLISHED_IMAGE_REF"
PUBLICATION_VERIFIED_ENV = "WNBA_RELEASE_PUBLICATION_VERIFIED"
PUBLISHER_ENV = "WNBA_RELEASE_PUBLISHER"
SOURCE_REPOSITORY_ENV = "WNBA_RELEASE_SOURCE_REPOSITORY"
HANDOFF_FORMAT_ENV = "WNBA_RELEASE_HANDOFF_FORMAT"

DEFAULT_REGISTRY = "ghcr.io"
DEFAULT_IMAGE_REPOSITORY = "ghcr.io/kyrepeak/kyre-sports-api"
DEFAULT_PUBLISHER = "github-actions"
DEFAULT_SOURCE_REPOSITORY = "kyrepeak/kyre-sports-ai"
DEFAULT_HANDOFF_FORMAT = "render-staging-v1"

_IMAGE_REF_RE = re.compile(r"^(?P<repo>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


class WNBAReleasePublicationHandoffError(RuntimeError):
    pass


class WNBAReleasePublicationHandoffNotReadyError(WNBAReleasePublicationHandoffError):
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


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _parse_image_ref(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = _IMAGE_REF_RE.fullmatch(value.casefold())
    if not match:
        return None, None
    return match.group("repo"), match.group("digest")


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "wnba-release"


def build_release_handoff_manifest(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build the sanitized immutable-image handoff manifest."""
    report = get_release_publication_handoff_readiness(env=env)
    release = report.get("release") or {}
    host = report.get("host") or {}
    publication = report.get("publication") or {}
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_publication_handoff_manifest",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "handoff_ready": report.get("handoff_ready") is True,
        "release_id": release.get("release_id"),
        "revision": release.get("revision"),
        "published_image_ref": publication.get("published_image_ref"),
        "image_digest_sha256": publication.get("image_digest_sha256"),
        "registry": publication.get("registry"),
        "image_repository": publication.get("image_repository"),
        "publisher": publication.get("publisher"),
        "source_repository": publication.get("source_repository"),
        "host_provider": host.get("provider"),
        "host_environment": host.get("environment"),
        "service_name": host.get("service_name"),
        "external_url": host.get("external_url"),
        "git_branch": host.get("git_branch"),
        "host_identity_sha256": report.get("host_identity_sha256"),
        "storage_identity_sha256": report.get("storage_identity_sha256"),
        "handoff_identity_sha256": report.get("handoff_identity_sha256"),
        "activation_required": False,
        "production_runtime_enabled": False,
        "safety": {
            "pre_activation_only": True,
            "contains_secrets": False,
            "provisions_host": False,
            "publishes_image": False,
            "calls_sportsbook": False,
            "runs_monte_carlo": False,
            "manual_refresh_endpoint_is_not_called": True,
        },
    }


def build_release_handoff_plan(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_release_publication_handoff_readiness(env=env)
    manifest = build_release_handoff_manifest(env=env)
    image_ref = (report.get("publication") or {}).get("published_image_ref")
    external_url = (report.get("host") or {}).get("external_url")
    steps = [
        {"order": 1, "action": "publish_exact_container_to_registry", "requirement": image_ref, "write_capable": True, "performed_by_this_api": False},
        {"order": 2, "action": "record_registry_digest", "requirement": "name@sha256:<64-hex>", "write_capable": False, "performed_by_this_api": False},
        {"order": 3, "action": "render_staging_template", "requirement": "sports_api/hosting/render.staging.yaml.template", "write_capable": False, "performed_by_this_api": False},
        {"order": 4, "action": "attach_persistent_disk", "requirement": "/var/lib/kyre-sports-api", "write_capable": True, "performed_by_this_api": False},
        {"order": 5, "action": "supply_provider_and_hmac_secrets", "requirement": "host secret manager only", "write_capable": True, "performed_by_this_api": False},
        {"order": 6, "action": "keep_runtime_disabled", "requirement": f"{ACTIVATION_ENV}=false", "write_capable": False, "performed_by_this_api": False},
        {"order": 7, "action": "verify_hosting_contract", "requirement": "/api/v1/wnba/runtime/hosting", "write_capable": False, "performed_by_this_api": False},
        {"order": 8, "action": "verify_release_handoff", "requirement": "/api/v1/wnba/runtime/handoff", "write_capable": False, "performed_by_this_api": False},
        {"order": 9, "action": "run_get_only_remote_smoke", "requirement": external_url, "write_capable": False, "performed_by_this_api": False},
        {"order": 10, "action": "restart_host_once_and_reverify_storage_identity", "requirement": manifest.get("storage_identity_sha256"), "write_capable": True, "performed_by_this_api": False},
        {"order": 11, "action": "freeze_pre_activation_staging_checkpoint", "requirement": manifest.get("handoff_identity_sha256"), "write_capable": False, "performed_by_this_api": False},
        {"order": 12, "action": "do_not_activate_until_next_step", "requirement": "Step 5W explicit activation gate", "write_capable": False, "performed_by_this_api": False},
    ]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_publication_handoff_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "handoff_ready": report.get("handoff_ready") is True,
        "step_count": len(steps),
        "steps": steps,
        "manifest": manifest,
        "safety": {
            "runtime_remains_disabled": True,
            "api_does_not_publish_image": True,
            "api_does_not_provision_host": True,
            "api_does_not_call_sportsbook": True,
            "api_does_not_run_monte_carlo": True,
        },
    }


def get_release_publication_handoff_readiness(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Validate immutable registry publication and hosted staging handoff state."""
    environment = _environment(env)
    step5u = get_hosted_staging_readiness(env=environment)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "required": True, "passed": bool(passed), "detail": detail})
        if not passed:
            blockers.append(f"{name}: {detail}")

    registry = (_clean(environment.get(REGISTRY_ENV)) or DEFAULT_REGISTRY).casefold()
    image_repository = (_clean(environment.get(IMAGE_REPOSITORY_ENV)) or DEFAULT_IMAGE_REPOSITORY).casefold()
    published_image_ref = (_clean(environment.get(PUBLISHED_IMAGE_REF_ENV)) or "").casefold() or None
    publication_verified = _truthy(environment, PUBLICATION_VERIFIED_ENV, False)
    publisher = (_clean(environment.get(PUBLISHER_ENV)) or DEFAULT_PUBLISHER).casefold()
    source_repository = (_clean(environment.get(SOURCE_REPOSITORY_ENV)) or DEFAULT_SOURCE_REPOSITORY).casefold()
    handoff_format = (_clean(environment.get(HANDOFF_FORMAT_ENV)) or DEFAULT_HANDOFF_FORMAT).casefold()
    activation_requested = _truthy(environment, ACTIVATION_ENV, False)

    published_repo, published_digest = _parse_image_ref(published_image_ref)
    release = step5u.get("release") or {}
    release_image_ref = (release.get("image_ref") or "").casefold() or None
    release_revision = (release.get("revision") or "").casefold() or None
    release_id = release.get("release_id")
    host = step5u.get("host") or {}

    add("frozen_step_5u_host_contract_ready", step5u.get("host_contract_ready") is True, "Frozen Step 5U hosted-staging contract is green." if step5u.get("host_contract_ready") is True else "Frozen Step 5U hosted-staging contract is not green.")
    add("runtime_remains_disabled", not activation_requested, "Production runtime remains disabled for handoff." if not activation_requested else "WNBA_PRODUCTION_RUNTIME_ENABLED must remain false during Step 5V.")
    add("supported_registry", registry == DEFAULT_REGISTRY, f"Registry is {DEFAULT_REGISTRY}." if registry == DEFAULT_REGISTRY else f"Step 5V currently requires {REGISTRY_ENV}={DEFAULT_REGISTRY}.")
    add("image_repository_is_ghcr", image_repository.startswith(DEFAULT_REGISTRY + "/"), "Image repository is hosted on GHCR." if image_repository.startswith(DEFAULT_REGISTRY + "/") else "Image repository must be under ghcr.io.")
    add("published_image_ref_is_immutable", published_repo is not None and published_digest is not None, "Published image is pinned by sha256 digest." if published_digest else f"{PUBLISHED_IMAGE_REF_ENV} must use name@sha256:<64-hex> form.")
    add("published_repository_matches", published_repo == image_repository, "Published image repository matches the configured repository." if published_repo == image_repository else "Published image repository does not match WNBA_RELEASE_IMAGE_REPOSITORY.")
    add("published_image_matches_step_5t", bool(published_image_ref and release_image_ref and published_image_ref == release_image_ref), "Published image exactly matches the immutable image recorded by Step 5T." if published_image_ref and published_image_ref == release_image_ref else "Published image must exactly match Step 5T WNBA_DEPLOYMENT_IMAGE_REF.")
    add("publication_explicitly_verified", publication_verified, "Registry publication has been explicitly verified." if publication_verified else f"{PUBLICATION_VERIFIED_ENV}=true is required after registry digest verification.")
    add("publisher_is_github_actions", publisher == DEFAULT_PUBLISHER, "Publisher identity is GitHub Actions." if publisher == DEFAULT_PUBLISHER else f"{PUBLISHER_ENV} must be {DEFAULT_PUBLISHER} for Step 5V.")
    add("source_repository_matches_host", bool(source_repository and (host.get("repository") or "").casefold() == source_repository), "Source repository matches the hosted staging repository." if source_repository and (host.get("repository") or "").casefold() == source_repository else "Published image source repository does not match the Step 5U host repository.")
    add("release_revision_is_full_sha", bool(release_revision and _SHA40_RE.fullmatch(release_revision)), "Release revision is a full Git SHA." if release_revision and _SHA40_RE.fullmatch(release_revision) else "Release revision is not a full 40-character SHA.")
    add("release_id_is_valid", bool(release_id and _RELEASE_ID_RE.fullmatch(str(release_id))), "Release ID is format-valid." if release_id and _RELEASE_ID_RE.fullmatch(str(release_id)) else "Release ID is invalid.")
    add("handoff_format_supported", handoff_format == DEFAULT_HANDOFF_FORMAT, f"Handoff format is {DEFAULT_HANDOFF_FORMAT}." if handoff_format == DEFAULT_HANDOFF_FORMAT else f"{HANDOFF_FORMAT_ENV} must be {DEFAULT_HANDOFF_FORMAT}.")
    add("host_is_render_staging", step5u.get("provider") == "render" and step5u.get("environment") == "staging", "Host is Render staging." if step5u.get("provider") == "render" and step5u.get("environment") == "staging" else "Step 5V requires the Render staging adapter.")
    add("storage_identity_present", isinstance(step5u.get("storage_identity_sha256"), str) and len(step5u.get("storage_identity_sha256")) == 64, "Persistent storage identity is present." if isinstance(step5u.get("storage_identity_sha256"), str) and len(step5u.get("storage_identity_sha256")) == 64 else "Persistent storage identity is missing.")
    add("host_identity_present", isinstance(step5u.get("host_identity_sha256"), str) and len(step5u.get("host_identity_sha256")) == 64, "Hosted staging identity is present." if isinstance(step5u.get("host_identity_sha256"), str) and len(step5u.get("host_identity_sha256")) == 64 else "Hosted staging identity is missing.")

    handoff_ready = not blockers
    identity_payload = {
        "release_id": release_id,
        "revision": release_revision,
        "published_image_ref": published_image_ref,
        "registry": registry,
        "image_repository": image_repository,
        "publisher": publisher,
        "source_repository": source_repository,
        "handoff_format": handoff_format,
        "host_identity_sha256": step5u.get("host_identity_sha256"),
        "storage_identity_sha256": step5u.get("storage_identity_sha256"),
    }
    handoff_identity = _hash_json(identity_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_publication_handoff_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "handoff_ready": handoff_ready,
        "activation_requested": activation_requested,
        "publication": {
            "registry": registry,
            "image_repository": image_repository,
            "published_image_ref": published_image_ref,
            "image_digest_sha256": published_digest,
            "publication_verified": publication_verified,
            "publisher": publisher,
            "source_repository": source_repository,
            "handoff_format": handoff_format,
        },
        "release": {
            "release_id": release_id,
            "revision": release_revision,
            "image_ref": release_image_ref,
            "phase": release.get("phase"),
        },
        "host": {
            "provider": step5u.get("provider"),
            "environment": step5u.get("environment"),
            "service_name": host.get("service_name"),
            "repository": host.get("repository"),
            "git_branch": host.get("git_branch"),
            "external_url": step5u.get("external_url"),
        },
        "host_identity_sha256": step5u.get("host_identity_sha256"),
        "storage_identity_sha256": step5u.get("storage_identity_sha256"),
        "handoff_identity_sha256": handoff_identity,
        "checks": checks,
        "blocking_reasons": blockers,
        "semantics": {
            "immutable_registry_digest_required": True,
            "published_image_must_match_step_5t": True,
            "frozen_step_5u_remains_hosting_authority": True,
            "runtime_must_remain_disabled": True,
            "api_does_not_publish_image": True,
            "api_does_not_provision_host": True,
            "api_does_not_call_sportsbook": True,
            "api_does_not_run_monte_carlo": True,
        },
    }


def require_release_publication_handoff_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_release_publication_handoff_readiness(env=env)
    if report.get("handoff_ready") is not True:
        raise WNBAReleasePublicationHandoffNotReadyError(
            "WNBA Step 5V release publication handoff is not ready: " + "; ".join(report.get("blocking_reasons") or [])
        )
    return report


def write_release_handoff_bundle(output_dir: str | Path, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Write a sanitized deployment handoff bundle and checksums."""
    report = require_release_publication_handoff_ready(env=env)
    manifest = build_release_handoff_manifest(env=env)
    plan = build_release_handoff_plan(env=env)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    release_id = str((report.get("release") or {}).get("release_id") or "wnba-release")
    stem = _safe_filename(release_id)
    manifest_path = target / f"{stem}.manifest.json"
    plan_path = target / f"{stem}.handoff-plan.json"
    env_path = target / f"{stem}.render.env"

    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    plan_text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    publication = report.get("publication") or {}
    host = report.get("host") or {}
    release = report.get("release") or {}
    env_text = "\n".join([
        "# Sanitized Step 5V Render staging handoff. Secrets intentionally omitted.",
        f"WNBA_RELEASE_ID={release.get('release_id') or ''}",
        f"WNBA_DEPLOYMENT_REVISION={release.get('revision') or ''}",
        f"WNBA_DEPLOYMENT_IMAGE_REF={publication.get('published_image_ref') or ''}",
        f"WNBA_RELEASE_PUBLISHED_IMAGE_REF={publication.get('published_image_ref') or ''}",
        f"WNBA_RELEASE_PUBLICATION_VERIFIED=true",
        f"WNBA_STAGING_EXTERNAL_URL={host.get('external_url') or ''}",
        f"WNBA_STAGING_EXPECTED_SERVICE_NAME={host.get('service_name') or ''}",
        "WNBA_PRODUCTION_RUNTIME_ENABLED=false",
        "# SPORTSGAMEODDS_API_KEY=<set in host secret manager>",
        "# WNBA_BACKTEST_ARCHIVE_HMAC_SECRET=<set in host secret manager>",
        "",
    ])

    manifest_path.write_text(manifest_text, encoding="utf-8")
    plan_path.write_text(plan_text, encoding="utf-8")
    env_path.write_text(env_text, encoding="utf-8")

    files = [manifest_path, plan_path, env_path]
    checksums = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksums.append({"file": path.name, "sha256": digest})
    checksums_path = target / "SHA256SUMS.json"
    checksums_path.write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_publication_handoff_bundle",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "output_dir": str(target),
        "file_count": 4,
        "files": [str(path) for path in [manifest_path, plan_path, env_path, checksums_path]],
        "handoff_identity_sha256": report.get("handoff_identity_sha256"),
        "contains_secrets": False,
    }
