"""WNBA Step 17A: fail-closed contract for the existing Render production host.

Step 17A reuses the one already-provisioned Render web service. The service is
Git-backed with Docker runtime, so the certified deployment method is Render's
specific-commit deploy: the exact frozen Step-16E Git SHA is built with the
frozen Dockerfile on that existing service. No second service is created and no
scheduler/runtime/write switch is enabled in this step.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

STEP16E_FROZEN_SHA = "5becd6af4fc8ce20a458c3bcb738dbff8312c8d7"
STEP16E_DOCKERFILE_BLOB_SHA = "324defd214f334c372f3b0b2dcafd958c962a6aa"
STEP16E_PUBLISHED_IMAGE_REF = (
    "ghcr.io/kyrepeak/kyre-sports-api@"
    "sha256:e9c0512a82efd044b142ce1486d9d3c9809f8815dd5d96f45cdff43cf54bf177"
)

STEP17A_ENABLED_ENV = "WNBA_STEP17A_HOST_CONTRACT_ENABLED"
DATABASE_URL_ENV = "KYRE_DATABASE_URL"
EXPECTED_REVISION_ENV = "WNBA_STEP17A_EXPECTED_REVISION"

# Resolved by the read-only Step-17A inventory on 2026-08-28.
EXPECTED_RENDER_SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
EXPECTED_RENDER_SERVICE_NAME = "kyre-sports-api"
EXPECTED_RENDER_SERVICE_TYPE = "web_service"
EXPECTED_RENDER_RUNTIME = "docker"
EXPECTED_RENDER_REPOSITORY = "https://github.com/kyrepeak/kyre-sports-ai"
EXPECTED_RENDER_URL = "https://kyre-sports-api.onrender.com"

FALSE_SWITCHES = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)


class Step17AHostContractError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def expected_host_env() -> dict[str, str]:
    out = {
        STEP17A_ENABLED_ENV: "true",
        EXPECTED_REVISION_ENV: STEP16E_FROZEN_SHA,
        "WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED": "true",
    }
    out.update({key: "false" for key in FALSE_SWITCHES})
    return out


def validate_render_service_identity(service: Mapping[str, Any]) -> dict[str, str]:
    details = service.get("serviceDetails")
    details = details if isinstance(details, Mapping) else {}
    observed = {
        "id": str(service.get("id") or "").strip(),
        "name": str(service.get("name") or "").strip(),
        "type": str(service.get("type") or "").strip().casefold(),
        "runtime": str(details.get("runtime") or details.get("env") or "").strip().casefold(),
        "repo": str(service.get("repo") or "").strip().rstrip("/"),
        "url": str(details.get("url") or service.get("url") or "").strip().rstrip("/"),
    }
    expected = {
        "id": EXPECTED_RENDER_SERVICE_ID,
        "name": EXPECTED_RENDER_SERVICE_NAME,
        "type": EXPECTED_RENDER_SERVICE_TYPE,
        "runtime": EXPECTED_RENDER_RUNTIME,
        "repo": EXPECTED_RENDER_REPOSITORY,
        "url": EXPECTED_RENDER_URL,
    }
    if observed != expected:
        raise Step17AHostContractError(
            "existing Render host identity drift; Step 17A refuses to mutate an unverified service"
        )
    return observed


def validate_host_contract(env: Mapping[str, str], *, build_revision: str | None = None) -> dict[str, object]:
    if not _truthy(env.get(STEP17A_ENABLED_ENV)):
        raise Step17AHostContractError(f"{STEP17A_ENABLED_ENV}=true is required")
    if any(_truthy(env.get(key)) for key in FALSE_SWITCHES):
        raise Step17AHostContractError("Step 17A refuses scheduler/runtime/write activation")
    expected = str(env.get(EXPECTED_REVISION_ENV) or "").strip().lower()
    if expected != STEP16E_FROZEN_SHA:
        raise Step17AHostContractError("Step 17A frozen revision mismatch")
    if build_revision is not None and str(build_revision).strip().lower() != STEP16E_FROZEN_SHA:
        raise Step17AHostContractError("running container is not the frozen Step-16E revision")
    raw = str(env.get(DATABASE_URL_ENV) or "").strip()
    if not raw:
        raise Step17AHostContractError(f"protected {DATABASE_URL_ENV} is required")
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"postgres", "postgresql"} or not parsed.hostname or parsed.path in {"", "/"}:
        raise Step17AHostContractError("database URL must identify PostgreSQL host/database")
    return {
        "step": "17A",
        "status": "host_contract_ready_scheduler_off",
        "frozen_revision": STEP16E_FROZEN_SHA,
        "dockerfile_blob_sha": STEP16E_DOCKERFILE_BLOB_SHA,
        "render_service_id": EXPECTED_RENDER_SERVICE_ID,
        "render_service_name": EXPECTED_RENDER_SERVICE_NAME,
        "render_runtime": EXPECTED_RENDER_RUNTIME,
        "database_secret_configured": True,
        "database_secret_exposed": False,
        "scheduler_enabled": False,
        "production_runtime_enabled": False,
        "new_render_service_creation_allowed": False,
    }
