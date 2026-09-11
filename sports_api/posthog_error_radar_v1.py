"""Monster Error Radar V1.

Optional PostHog-backed exception reporting shared by the Streamlit app and
FastAPI service. This module is deliberately fail-open: telemetry must never
break sports data, projections, routing, or user-facing requests.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

_LOGGER = logging.getLogger("kyre.monster_error_radar")
_CLIENT: Any | None = None
_CLIENT_INITIALIZED = False
_CLIENT_LOCK = threading.Lock()

ERROR_RADAR_VERSION = "MONSTER_ERROR_RADAR_V1"
DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _posthog_client() -> Any | None:
    """Create one reusable PostHog client when the project token is configured."""
    global _CLIENT, _CLIENT_INITIALIZED
    if _CLIENT_INITIALIZED:
        return _CLIENT

    with _CLIENT_LOCK:
        if _CLIENT_INITIALIZED:
            return _CLIENT

        project_key = _env_first("POSTHOG_PROJECT_API_KEY", "POSTHOG_API_KEY")
        if not project_key:
            _CLIENT_INITIALIZED = True
            return None

        try:
            from posthog import Posthog

            _CLIENT = Posthog(
                project_api_key=project_key,
                host=_env_first("POSTHOG_HOST", default=DEFAULT_POSTHOG_HOST),
                enable_exception_autocapture=True,
                capture_exception_code_variables=False,
            )
        except Exception as exc:  # telemetry may never become an application dependency
            _LOGGER.warning("MONSTER_ERROR_RADAR_INIT_FAILED %s", exc.__class__.__name__)
            _CLIENT = None
        finally:
            _CLIENT_INITIALIZED = True

    return _CLIENT


def radar_status() -> dict[str, Any]:
    """Return non-secret configuration state for diagnostics and CI."""
    configured = bool(_env_first("POSTHOG_PROJECT_API_KEY", "POSTHOG_API_KEY"))
    return {
        "version": ERROR_RADAR_VERSION,
        "configured": configured,
        "host": _env_first("POSTHOG_HOST", default=DEFAULT_POSTHOG_HOST),
    }


def capture_runtime_exception(
    exc: BaseException,
    *,
    error_fingerprint: str,
    surface: str,
    request_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
    properties: dict[str, Any] | None = None,
) -> bool:
    """Capture an exception with stable Kyre debugging metadata.

    Returns True when the event was accepted by the local PostHog client queue.
    Any telemetry failure is swallowed so application behavior stays unchanged.
    """
    client = _posthog_client()
    if client is None:
        return False

    payload: dict[str, Any] = {
        "monster_error_radar_version": ERROR_RADAR_VERSION,
        "error_fingerprint": error_fingerprint,
        "$exception_fingerprint": error_fingerprint,
        "$issue_name": f"{surface}: {exc.__class__.__name__}",
        "$exception_level": "error",
        "surface": surface,
        "request_id": request_id,
        "path": path,
        "method": method,
        "deploy_commit": _env_first("RENDER_GIT_COMMIT", "GIT_COMMIT", default="unknown"),
        "deploy_branch": _env_first("RENDER_GIT_BRANCH", "GIT_BRANCH", default="unknown"),
        "service": _env_first("RENDER_SERVICE_NAME", default="kyre-sports-ai"),
        "environment": "render" if os.getenv("RENDER") else _env_first("KYRE_ENV", default="unknown"),
    }
    if properties:
        payload.update(properties)

    try:
        client.capture_exception(exc, properties=payload)
        return True
    except Exception as capture_error:
        _LOGGER.warning(
            "MONSTER_ERROR_RADAR_CAPTURE_FAILED %s",
            capture_error.__class__.__name__,
        )
        return False
