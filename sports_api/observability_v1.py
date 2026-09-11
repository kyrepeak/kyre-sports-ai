"""Production observability primitives for Kyre Sports API.

This module is intentionally additive and model-agnostic. It exposes deployment
identity, deterministic error fingerprints, request correlation, and safe
runtime diagnostics without changing any sports projection/data logic.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

OBSERVABILITY_VERSION = "KYRE_OBSERVABILITY_V1"
EXPECTED_PRODUCTION_BRANCH = "main"
_PROCESS_STARTED_MONOTONIC = time.monotonic()
_LOGGER = logging.getLogger("kyre.observability")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SECRET_RE = re.compile(
    r"(?i)(authorization|password|passwd|secret|api[_-]?key|token)\s*[:=]\s*([^\s,;]+)"
)


def _env_first(*names: str, default: str = "unknown") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def sanitize_error_message(message: str, *, limit: int = 500) -> str:
    """Redact common credential-shaped fragments before writing an error log."""
    cleaned = _SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted>", str(message))
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").strip()
    return cleaned[:limit]


def request_id_from_header(value: str | None) -> str:
    """Reuse a safe caller request ID or generate a fresh correlation ID."""
    if value and _REQUEST_ID_RE.fullmatch(value):
        return value
    return uuid.uuid4().hex


def error_fingerprint(exc: BaseException, *, path: str = "unknown") -> str:
    """Create a stable, non-secret fingerprint for an exception class + route."""
    identity = f"{exc.__class__.__module__}.{exc.__class__.__qualname__}|{path}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
    return f"KYRE-{digest}"


def runtime_metadata() -> dict[str, Any]:
    """Return non-secret deployment/runtime identity for debugging and support."""
    branch = _env_first("RENDER_GIT_BRANCH", "GIT_BRANCH")
    commit = _env_first("RENDER_GIT_COMMIT", "GIT_COMMIT")
    service_name = _env_first("RENDER_SERVICE_NAME", default="kyre-sports-api")
    service_id = _env_first("RENDER_SERVICE_ID")
    external_url = _env_first("RENDER_EXTERNAL_URL")
    instance = _env_first("RENDER_INSTANCE_ID", "HOSTNAME")
    environment = "render" if os.getenv("RENDER") else _env_first("KYRE_ENV", default="local")

    return {
        "observability_version": OBSERVABILITY_VERSION,
        "service": service_name,
        "service_id": service_id,
        "environment": environment,
        "deploy_branch": branch,
        "deploy_commit": commit,
        "expected_production_branch": EXPECTED_PRODUCTION_BRANCH,
        "branch_aligned": branch in {EXPECTED_PRODUCTION_BRANCH, "unknown"},
        "instance": instance,
        "external_url": external_url,
        "python_version": platform.python_version(),
        "process_id": os.getpid(),
        "uptime_seconds": round(max(0.0, time.monotonic() - _PROCESS_STARTED_MONOTONIC), 3),
    }


def readiness_snapshot() -> dict[str, Any]:
    runtime = runtime_metadata()
    return {
        "status": "ready",
        "service": runtime["service"],
        "observability_version": OBSERVABILITY_VERSION,
        "checks": {
            "process_running": True,
            "python_runtime": bool(runtime["python_version"]),
            "deployment_identity_available": runtime["deploy_commit"] != "unknown",
            "production_branch_alignment": runtime["branch_aligned"],
        },
        "deployment": {
            "branch": runtime["deploy_branch"],
            "commit": runtime["deploy_commit"],
            "expected_branch": EXPECTED_PRODUCTION_BRANCH,
            "aligned": runtime["branch_aligned"],
        },
    }


def diagnostics_snapshot() -> dict[str, Any]:
    runtime = runtime_metadata()
    ready = readiness_snapshot()
    return {
        "status": "ok",
        "observability_version": OBSERVABILITY_VERSION,
        "runtime": runtime,
        "readiness": ready["checks"],
        "debug_contract": {
            "request_id_header": "X-Request-ID",
            "error_fingerprint_field": "error_fingerprint",
            "deploy_commit_header": "X-Kyre-Deploy-Commit",
            "deploy_branch_header": "X-Kyre-Deploy-Branch",
            "duration_header": "X-Kyre-Duration-Ms",
        },
    }


def _structured_log(event: str, payload: dict[str, Any], *, level: int = logging.INFO) -> None:
    _LOGGER.log(
        level,
        "%s %s",
        event,
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
    )


def install_observability(app: FastAPI) -> None:
    """Install request correlation and unhandled-error fingerprinting once."""
    if getattr(app.state, "kyre_observability_v1_installed", False):
        return
    app.state.kyre_observability_v1_installed = True

    startup = runtime_metadata()
    _structured_log(
        "KYRE_OBSERVABILITY_BOOT",
        {
            "observability_version": OBSERVABILITY_VERSION,
            "service": startup["service"],
            "environment": startup["environment"],
            "deploy_branch": startup["deploy_branch"],
            "deploy_commit": startup["deploy_commit"],
            "branch_aligned": startup["branch_aligned"],
        },
    )

    @app.middleware("http")
    async def kyre_observability_middleware(request: Request, call_next):
        request_id = request_id_from_header(request.headers.get("x-request-id"))
        request.state.kyre_request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised in runtime/contract tests
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            fingerprint = error_fingerprint(exc, path=request.url.path)
            runtime = runtime_metadata()
            payload = {
                "request_id": request_id,
                "error_fingerprint": fingerprint,
                "error_type": f"{exc.__class__.__module__}.{exc.__class__.__qualname__}",
                "error_message": sanitize_error_message(str(exc)),
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
                "deploy_branch": runtime["deploy_branch"],
                "deploy_commit": runtime["deploy_commit"],
            }
            _structured_log("KYRE_UNHANDLED_ERROR", payload, level=logging.ERROR)
            response = JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Internal server error",
                    "request_id": request_id,
                    "error_fingerprint": fingerprint,
                },
            )

        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        runtime = runtime_metadata()
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Kyre-Deploy-Commit"] = str(runtime["deploy_commit"])[:40]
        response.headers["X-Kyre-Deploy-Branch"] = str(runtime["deploy_branch"])[:128]
        response.headers["X-Kyre-Duration-Ms"] = f"{duration_ms:.2f}"

        if response.status_code >= 400:
            _structured_log(
                "KYRE_HTTP_NON_SUCCESS",
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "deploy_branch": runtime["deploy_branch"],
                    "deploy_commit": runtime["deploy_commit"],
                },
                level=logging.WARNING if response.status_code < 500 else logging.ERROR,
            )

        return response
