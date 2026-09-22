"""Monster Error Radar V1.

Optional PostHog-backed exception reporting shared by the Streamlit app and
FastAPI service. This module is deliberately fail-open: telemetry must never
break sports data, projections, routing, or user-facing requests.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sys
import threading
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

_LOGGER = logging.getLogger("kyre.monster_error_radar")
_CLIENT: Any | None = None
_CLIENT_INITIALIZED = False
_CLIENT_LOCK = threading.Lock()
_STREAMLIT_PROBE_RAN = False
_STREAMLIT_PROBE_LOCK = threading.Lock()

ERROR_RADAR_VERSION = "MONSTER_ERROR_RADAR_V1"
DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"
DEFAULT_STREAMLIT_PROBE_HEALTH_URL = "https://kyre-sports-api.onrender.com/health"
STREAMLIT_PROBE_VERSION = "MONSTER_STREAMLIT_TELEMETRY_PROBE_V1"
STREAMLIT_PROBE_FINGERPRINT = "MONSTER-A8-STREAMLIT-PROBE-V1"
STREAMLIT_PROBE_MESSAGE = "Monster Streamlit certification synthetic exception probe"
STREAMLIT_PROBE_SESSION_KEY = "monster_a9_streamlit_probe_v1"
_STREAMLIT_RUNTIME_SECRET_NAMES = (
    "POSTHOG_PROJECT_API_KEY",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
)


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _streamlit_secret_mapping() -> dict[str, str]:
    """Return only telemetry-related Streamlit secrets, never the whole store."""
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return {}

    values: dict[str, str] = {}
    for name in _STREAMLIT_RUNTIME_SECRET_NAMES:
        try:
            value = secrets.get(name)
        except Exception:
            continue
        if value is not None and str(value).strip():
            values[name] = str(value).strip()
    return values


def _runtime_first(
    *names: str,
    environ: Mapping[str, str] | None = None,
    default: str = "",
) -> str:
    runtime_environ = os.environ if environ is None else environ
    for name in names:
        value = runtime_environ.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()

    secrets = _streamlit_secret_mapping()
    for name in names:
        value = secrets.get(name)
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

        project_key = _runtime_first("POSTHOG_PROJECT_API_KEY", "POSTHOG_API_KEY")
        if not project_key:
            _CLIENT_INITIALIZED = True
            return None

        try:
            from posthog import Posthog

            _CLIENT = Posthog(
                project_api_key=project_key,
                host=_runtime_first("POSTHOG_HOST", default=DEFAULT_POSTHOG_HOST),
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
    configured = bool(_runtime_first("POSTHOG_PROJECT_API_KEY", "POSTHOG_API_KEY"))
    return {
        "version": ERROR_RADAR_VERSION,
        "configured": configured,
        "host": _runtime_first("POSTHOG_HOST", default=DEFAULT_POSTHOG_HOST),
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


def _streamlit_probe_marker() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"monster-a8-{stamp}-{uuid4().hex[:8]}"


def _streamlit_probe_ping(marker: str, environ: Mapping[str, str]) -> bool:
    """Ping the healthy Render API with a unique marker; failures stay fail-open."""
    base_url = str(
        environ.get("MONSTER_A8_RENDER_HEALTH_URL")
        or environ.get("KYRE_API_HEALTH_URL")
        or DEFAULT_STREAMLIT_PROBE_HEALTH_URL
    ).strip()
    posthog_configured = "1" if _runtime_first(
        "POSTHOG_PROJECT_API_KEY",
        "POSTHOG_API_KEY",
        environ=environ,
    ) else "0"
    separator = "&" if "?" in base_url else "?"
    target = f"{base_url}{separator}{urlencode({'monster_a8_marker': marker, 'posthog_configured': posthog_configured})}"
    request = Request(target, headers={"User-Agent": "monster-a8-streamlit-cert/1"})
    try:
        with urlopen(request, timeout=3.0) as response:
            return 200 <= int(getattr(response, "status", 0)) < 300
    except Exception as exc:
        _LOGGER.warning("MONSTER_A8_STREAMLIT_PING_FAILED %s", exc.__class__.__name__)
        return False


def _flush_posthog_client() -> bool:
    client = _posthog_client()
    if client is None:
        return False
    try:
        client.flush()
        return True
    except Exception as exc:
        _LOGGER.warning("MONSTER_A8_STREAMLIT_FLUSH_FAILED %s", exc.__class__.__name__)
        return False


def _is_streamlit_runtime(argv: Sequence[str]) -> bool:
    try:
        import streamlit.runtime as streamlit_runtime

        if streamlit_runtime.exists():
            return True
    except Exception:
        pass

    if not argv:
        return False
    launcher = os.path.basename(str(argv[0])).casefold()
    if launcher == "streamlit" or launcher.startswith("streamlit."):
        return True
    if len(argv) >= 3:
        return (
            launcher.startswith("python")
            and str(argv[1]).casefold() == "-m"
            and str(argv[2]).casefold() == "streamlit"
        )
    return False


def _record_streamlit_probe_state(
    result: Mapping[str, Any],
    environ: Mapping[str, str],
) -> None:
    """Store non-secret A9 probe evidence in Streamlit session state."""
    try:
        import streamlit as st

        safe_result = dict(result)
        safe_result["posthog_configured"] = bool(
            _runtime_first(
                "POSTHOG_PROJECT_API_KEY",
                "POSTHOG_API_KEY",
                environ=environ,
            )
        )
        st.session_state[STREAMLIT_PROBE_SESSION_KEY] = safe_result
    except Exception as exc:
        _LOGGER.debug("MONSTER_A9_STREAMLIT_STATE_UNAVAILABLE %s", exc.__class__.__name__)


def _probe_result(
    *,
    status: str,
    eligible: bool,
    runtime_pinged: bool,
    accepted: bool,
    flushed: bool,
    marker: str | None,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    result = {
        "status": status,
        "eligible": eligible,
        "runtime_pinged": runtime_pinged,
        "accepted": accepted,
        "flushed": flushed,
        "marker": marker,
        "fingerprint": STREAMLIT_PROBE_FINGERPRINT,
    }
    _record_streamlit_probe_state(result, environ)
    return result


def run_streamlit_activation_probe(
    *,
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    ping_fn: Callable[[str], bool] | None = None,
    capture_fn: Callable[..., bool] | None = None,
    flush_fn: Callable[[], bool] | None = None,
    marker_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Run one fail-open A8 certification probe for a Streamlit process."""
    global _STREAMLIT_PROBE_RAN

    runtime_argv = tuple(sys.argv if argv is None else argv)
    runtime_environ = os.environ if environ is None else environ
    eligible = _is_streamlit_runtime(runtime_argv)
    if not eligible:
        return _probe_result(
            status="ineligible",
            eligible=False,
            runtime_pinged=False,
            accepted=False,
            flushed=False,
            marker=None,
            environ=runtime_environ,
        )

    with _STREAMLIT_PROBE_LOCK:
        if _STREAMLIT_PROBE_RAN:
            return _probe_result(
                status="already_ran",
                eligible=True,
                runtime_pinged=False,
                accepted=False,
                flushed=False,
                marker=None,
                environ=runtime_environ,
            )
        _STREAMLIT_PROBE_RAN = True

    marker_builder = marker_factory or _streamlit_probe_marker
    actual_capture = capture_fn or capture_runtime_exception
    actual_flush = flush_fn or _flush_posthog_client

    try:
        marker = marker_builder()
    except Exception as exc:
        _LOGGER.warning("MONSTER_A8_STREAMLIT_MARKER_FAILED %s", exc.__class__.__name__)
        return _probe_result(
            status="marker_failed",
            eligible=True,
            runtime_pinged=False,
            accepted=False,
            flushed=False,
            marker=None,
            environ=runtime_environ,
        )

    actual_ping = ping_fn or (lambda value: _streamlit_probe_ping(value, runtime_environ))
    runtime_pinged = False
    accepted = False
    flushed = False

    try:
        runtime_pinged = bool(actual_ping(marker))
    except Exception as exc:
        _LOGGER.warning("MONSTER_A8_STREAMLIT_PING_FAILED %s", exc.__class__.__name__)

    probe_error = RuntimeError(STREAMLIT_PROBE_MESSAGE)
    try:
        accepted = bool(
            actual_capture(
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
            flushed = bool(actual_flush())
        except Exception as exc:
            _LOGGER.warning("MONSTER_A8_STREAMLIT_FLUSH_FAILED %s", exc.__class__.__name__)

    status = "flushed" if accepted and flushed else "queued" if accepted else "not_accepted"
    return _probe_result(
        status=status,
        eligible=True,
        runtime_pinged=runtime_pinged,
        accepted=accepted,
        flushed=flushed,
        marker=marker,
        environ=runtime_environ,
    )
