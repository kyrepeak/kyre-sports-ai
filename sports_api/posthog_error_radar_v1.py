"""Monster Error Radar V1.

Optional PostHog-backed exception reporting shared by the Streamlit app and
FastAPI service. This module is deliberately fail-open: telemetry must never
break sports data, projections, routing, or user-facing requests.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Mapping, Sequence

_LOGGER = logging.getLogger("kyre.monster_error_radar")
_CLIENT: Any | None = None
_CLIENT_INITIALIZED = False
_CLIENT_LOCK = threading.Lock()

ERROR_RADAR_VERSION = "MONSTER_ERROR_RADAR_V1"
DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"
STREAMLIT_PROBE_VERSION = "MONSTER_STREAMLIT_TELEMETRY_PROBE_V1"
STREAMLIT_PROBE_FINGERPRINT = "MONSTER-A8-STREAMLIT-PROBE-V1"
STREAMLIT_PROBE_MESSAGE = "Monster Streamlit certification synthetic exception probe"


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


def run_streamlit_activation_probe(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    ping_fn: Callable[[str], bool],
    capture_fn: Callable[..., bool],
    flush_fn: Callable[[], bool],
    marker_factory: Callable[[], str],
) -> dict[str, Any]:
    """Run one fail-open A8 certification probe for a Streamlit process."""
    del environ  # reserved for the production wrapper added after core certification
    eligible = any("streamlit" in str(part).casefold() for part in argv)
    if not eligible:
        return {
            "status": "ineligible",
            "eligible": False,
            "runtime_pinged": False,
            "accepted": False,
            "flushed": False,
            "marker": None,
            "fingerprint": STREAMLIT_PROBE_FINGERPRINT,
        }

    marker = marker_factory()
    runtime_pinged = False
    accepted = False
    flushed = False

    try:
        runtime_pinged = bool(ping_fn(marker))
    except Exception as exc:
        _LOGGER.warning("MONSTER_A8_STREAMLIT_PING_FAILED %s", exc.__class__.__name__)

    probe_error = RuntimeError(STREAMLIT_PROBE_MESSAGE)
    try:
        accepted = bool(
            capture_fn(
                probe_error,
                error_fingerprint=STREAMLIT_PROBE_FINGERPRINT,
                surface="streamlit",
                path="app.py",
                properties={
                    "monster_streamlit_certification_probe": marker,
                    "synthetic_certification_probe": True,
                    "probe_version": STREAMLIT_PROBE_VERSION,
                },
            )
        )
    except Exception as exc:
        _LOGGER.warning("MONSTER_A8_STREAMLIT_CAPTURE_FAILED %s", exc.__class__.__name__)

    if accepted:
        try:
            flushed = bool(flush_fn())
        except Exception as exc:
            _LOGGER.warning("MONSTER_A8_STREAMLIT_FLUSH_FAILED %s", exc.__class__.__name__)

    status = "flushed" if accepted and flushed else "queued" if accepted else "not_accepted"
    return {
        "status": status,
        "eligible": True,
        "runtime_pinged": runtime_pinged,
        "accepted": accepted,
        "flushed": flushed,
        "marker": marker,
        "fingerprint": STREAMLIT_PROBE_FINGERPRINT,
    }
