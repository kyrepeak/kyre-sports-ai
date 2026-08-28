"""WNBA Step 17A: fail-closed contract for reusing the existing Render host.

This layer does not create Render services and does not start the scheduler. It
binds the exact frozen Step-16E release identity to the existing image-backed
host and requires the protected PostgreSQL URL to be present before startup.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

STEP16E_FROZEN_SHA = "5becd6af4fc8ce20a458c3bcb738dbff8312c8d7"
STEP16E_CONTAINER_SHA256 = "257096c6b5557edf84d442bee1121be410471700186d1083331019eb4d50d24f"
STEP17A_ENABLED_ENV = "WNBA_STEP17A_HOST_CONTRACT_ENABLED"
DATABASE_URL_ENV = "KYRE_DATABASE_URL"
EXPECTED_REVISION_ENV = "WNBA_STEP17A_EXPECTED_REVISION"
EXPECTED_SERVICE_NAMES = ("kyre-sports-api-staging", "wnba-render-staging")

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
        "frozen_container_sha256": STEP16E_CONTAINER_SHA256,
        "database_secret_configured": True,
        "database_secret_exposed": False,
        "scheduler_enabled": False,
        "production_runtime_enabled": False,
        "new_render_service_creation_allowed": False,
    }
