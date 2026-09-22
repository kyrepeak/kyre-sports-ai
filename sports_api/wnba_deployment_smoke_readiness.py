"""WNBA Step 5S deployment topology and read-only live smoke readiness.

Step 5S is deployment packaging and verification only. It does not modify
frozen WNBA model, sportsbook, Monte Carlo, ranking, archive, publication,
scheduler cadence, Step-5Q locking, or Step-5R activation semantics.

The current SQLite-based runtime is intentionally restricted to ONE service
replica. Multiple Uvicorn worker processes inside that replica are supported by
Step 5Q because they share the same local persistent volume and lock database.
Multiple service replicas/containers are NOT declared safe until the lock is
moved to a true distributed coordination backend.

The live smoke runner is read-only by design: every request is GET. It never
calls the manual refresh endpoint and therefore cannot intentionally trigger a
sportsbook collection or Monte Carlo rebuild.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.wnba_production_runtime_readiness import (
    ACTIVATION_ENV,
    get_production_runtime_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5S deployment + smoke readiness"
MODEL_VERSION = "wnba_step_5s_deployment_smoke_readiness_v1"
SCHEMA_VERSION = "wnba_step_5s_deployment_smoke_readiness_v1"

DEPLOYMENT_MODE_ENV = "WNBA_DEPLOYMENT_MODE"
REPLICA_COUNT_ENV = "WNBA_DEPLOYMENT_REPLICA_COUNT"
PERSISTENT_ROOT_ENV = "WNBA_PERSISTENT_VOLUME_ROOT"
WEB_CONCURRENCY_ENV = "WEB_CONCURRENCY"
PORT_ENV = "PORT"
SMOKE_BASE_URL_ENV = "WNBA_DEPLOYMENT_SMOKE_BASE_URL"
DEPLOYMENT_REVISION_ENV = "WNBA_DEPLOYMENT_REVISION"

DEFAULT_DEPLOYMENT_MODE = "container"
DEFAULT_REPLICA_COUNT = 1
DEFAULT_WEB_CONCURRENCY = 2
DEFAULT_PORT = 8000
MAX_WEB_CONCURRENCY = 8

REQUIRED_OPENAPI_PATHS = (
    "/api/v1/wnba/rankings/player-props/current",
    "/api/v1/wnba/rankings/player-props/current/refresh",
    "/api/v1/wnba/rankings/player-props/current/status",
    "/api/v1/wnba/rankings/player-props/current/history",
    "/api/v1/wnba/runtime/readiness",
    "/api/v1/wnba/runtime/health",
    "/api/v1/wnba/runtime/deployment",
    "/api/v1/wnba/runtime/smoke-plan",
)


class WNBADeploymentReadinessError(RuntimeError):
    pass


class WNBADeploymentNotReadyError(WNBADeploymentReadinessError):
    pass


class WNBALiveSmokeError(WNBADeploymentReadinessError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_env(environment: Mapping[str, str], name: str, default: int) -> tuple[int | None, str | None]:
    raw = _clean(environment.get(name))
    if raw is None:
        return default, None
    try:
        return int(raw), None
    except ValueError:
        return None, f"{name} must be an integer."


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def normalize_smoke_base_url(value: str) -> str:
    text = (_clean(value) or "").rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WNBALiveSmokeError("Smoke base URL must be an absolute http(s) URL.")
    host = (parsed.hostname or "").casefold()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
        raise WNBALiveSmokeError("Remote live smoke URLs must use HTTPS.")
    if parsed.username or parsed.password:
        raise WNBALiveSmokeError("Smoke base URL must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise WNBALiveSmokeError("Smoke base URL must not contain a query string or fragment.")
    return text


def build_live_smoke_plan(
    base_url: str | None = None,
    *,
    expect_scheduler_ready: bool = False,
) -> dict[str, Any]:
    normalized = normalize_smoke_base_url(base_url) if base_url else None
    requests = [
        {"name": "service_root", "method": "GET", "path": "/", "allowed_statuses": [200]},
        {"name": "service_health", "method": "GET", "path": "/health", "allowed_statuses": [200]},
        {"name": "openapi_contract", "method": "GET", "path": "/openapi.json", "allowed_statuses": [200]},
        {
            "name": "step_5r_readiness",
            "method": "GET",
            "path": "/api/v1/wnba/runtime/readiness",
            "allowed_statuses": [200],
        },
        {
            "name": "step_5s_deployment",
            "method": "GET",
            "path": "/api/v1/wnba/runtime/deployment",
            "allowed_statuses": [200],
        },
        {
            "name": "production_runtime_health",
            "method": "GET",
            "path": "/api/v1/wnba/runtime/health",
            "allowed_statuses": [200] if expect_scheduler_ready else [200, 503],
        },
        {
            "name": "current_board_read",
            "method": "GET",
            "path": "/api/v1/wnba/rankings/player-props/current?require_current=true",
            "allowed_statuses": [200, 409],
        },
    ]
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "base_url": normalized,
        "expect_scheduler_ready": bool(expect_scheduler_ready),
        "request_count": len(requests),
        "requests": requests,
        "safety": {
            "read_only": True,
            "all_methods_are_get": all(item["method"] == "GET" for item in requests),
            "manual_refresh_endpoint_is_not_called": True,
            "sportsbook_collection_is_not_intentionally_triggered": True,
            "monte_carlo_rebuild_is_not_intentionally_triggered": True,
        },
    }


def get_deployment_readiness(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    checks: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []

    def add(name: str, passed: bool, detail: str) -> None:
        row = {"name": name, "required": True, "passed": bool(passed), "detail": detail}
        checks.append(row)
        if not passed:
            blocking_reasons.append(f"{name}: {detail}")

    mode = (_clean(environment.get(DEPLOYMENT_MODE_ENV)) or DEFAULT_DEPLOYMENT_MODE).casefold()
    add(
        "supported_deployment_mode",
        mode == "container",
        "Container deployment mode is configured." if mode == "container" else "Step 5S currently supports deployment mode 'container' only.",
    )

    replica_count, replica_error = _int_env(environment, REPLICA_COUNT_ENV, DEFAULT_REPLICA_COUNT)
    add(
        "single_service_replica",
        replica_count == 1,
        (
            "Exactly one service replica is configured; Step 5Q may coordinate multiple worker processes inside it."
            if replica_count == 1
            else replica_error or "SQLite Step 5Q locking is not approved for multiple service replicas. Configure exactly one replica."
        ),
    )

    web_concurrency, worker_error = _int_env(environment, WEB_CONCURRENCY_ENV, DEFAULT_WEB_CONCURRENCY)
    workers_ok = web_concurrency is not None and 1 <= web_concurrency <= MAX_WEB_CONCURRENCY
    add(
        "uvicorn_worker_count_supported",
        workers_ok,
        (
            f"{web_concurrency} Uvicorn worker process(es) configured inside the single replica."
            if workers_ok
            else worker_error or f"{WEB_CONCURRENCY_ENV} must be between 1 and {MAX_WEB_CONCURRENCY}."
        ),
    )

    port, port_error = _int_env(environment, PORT_ENV, DEFAULT_PORT)
    port_ok = port is not None and 1 <= port <= 65535
    add(
        "http_port_valid",
        port_ok,
        f"HTTP port {port} is valid." if port_ok else port_error or f"{PORT_ENV} must be 1 through 65535.",
    )

    root_raw = _clean(environment.get(PERSISTENT_ROOT_ENV))
    root = Path(root_raw).expanduser() if root_raw else None
    root_ok = root is not None and root.is_absolute()
    add(
        "persistent_volume_root_absolute",
        root_ok,
        (
            f"Persistent volume root is {root}."
            if root_ok
            else f"{PERSISTENT_ROOT_ENV} must be explicitly configured as an absolute path."
        ),
    )

    step5r = get_production_runtime_readiness(env=environment)
    paths = step5r.get("paths") or {}
    runtime_paths = {
        "board_store": paths.get("board_store"),
        "feed_store": paths.get("feed_store"),
        "backtest_store": paths.get("backtest_store"),
        "scheduler_lock_store": paths.get("scheduler_lock_store"),
    }
    paths_under_root = root_ok
    if root_ok:
        for raw in runtime_paths.values():
            if not raw or not _within_root(Path(str(raw)), root):
                paths_under_root = False
                break
    add(
        "all_runtime_databases_on_persistent_volume",
        paths_under_root,
        (
            "All Step 5P/5O/5J/5Q SQLite files resolve beneath the configured persistent volume root."
            if paths_under_root
            else "Every runtime SQLite path must resolve beneath the configured persistent volume root."
        ),
    )

    step5r_preflight = step5r.get("preflight_ready") is True
    add(
        "step_5r_preflight_ready",
        step5r_preflight,
        "Frozen Step 5R production preflight is green." if step5r_preflight else "Frozen Step 5R production preflight is not green.",
    )

    smoke_base_raw = _clean(environment.get(SMOKE_BASE_URL_ENV))
    smoke_base: str | None = None
    smoke_base_valid = True
    if smoke_base_raw:
        try:
            smoke_base = normalize_smoke_base_url(smoke_base_raw)
        except WNBALiveSmokeError:
            smoke_base_valid = False
    add(
        "configured_smoke_base_url_is_safe",
        smoke_base_valid,
        "Smoke base URL is absent or safely formatted." if smoke_base_valid else "Configured remote smoke base URL must be HTTPS and contain no credentials/query/fragment.",
    )

    deployment_ready = not blocking_reasons
    live_write_ready = deployment_ready and step5r.get("scheduler_allowed") is True
    revision = _clean(environment.get(DEPLOYMENT_REVISION_ENV))
    startup_command = (
        "uvicorn sports_api.main:app --host 0.0.0.0 "
        f"--port {port if port_ok else DEFAULT_PORT} --workers {web_concurrency if workers_ok else DEFAULT_WEB_CONCURRENCY}"
    )
    fingerprint_payload = {
        "model_version": MODEL_VERSION,
        "mode": mode,
        "replica_count": replica_count,
        "web_concurrency": web_concurrency,
        "port": port,
        "persistent_root": str(root) if root else None,
        "runtime_paths": runtime_paths,
        "step5r_configuration_fingerprint": step5r.get("configuration_fingerprint_sha256"),
        "revision": revision,
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_deployment_and_smoke_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "deployment_ready": deployment_ready,
        "live_write_ready": live_write_ready,
        "activation_requested": step5r.get("activation_requested") is True,
        "deployment": {
            "mode": mode,
            "replica_count": replica_count,
            "web_concurrency": web_concurrency,
            "port": port,
            "persistent_volume_root": str(root) if root else None,
            "revision": revision,
            "startup_command": startup_command,
            "single_replica_required_for_current_sqlite_locking": True,
            "multiple_worker_processes_inside_single_replica_supported": True,
        },
        "runtime_paths": runtime_paths,
        "step_5r": {
            "preflight_ready": step5r.get("preflight_ready") is True,
            "scheduler_allowed": step5r.get("scheduler_allowed") is True,
            "activation_reason": step5r.get("activation_reason"),
            "blocking_reasons": list(step5r.get("blocking_reasons") or []),
            "configuration_fingerprint_sha256": step5r.get("configuration_fingerprint_sha256"),
        },
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "configured_smoke_base_url": smoke_base,
        "configuration_fingerprint_sha256": _hash(fingerprint_payload),
        "semantics": {
            "frozen_step_5r_activation_remains_authoritative": True,
            "frozen_step_5q_cycle_lock_remains_authoritative": True,
            "frozen_model_and_publication_semantics_are_unchanged": True,
            "deployment_gate_does_not_call_sportsbook": True,
            "deployment_gate_does_not_run_monte_carlo": True,
            "live_smoke_is_read_only": True,
            "multi_replica_sqlite_deployment_is_rejected": True,
        },
    }


def require_deployment_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_deployment_readiness(env=env)
    if report.get("deployment_ready") is not True:
        raise WNBADeploymentNotReadyError("WNBA Step 5S deployment gate is not ready: " + "; ".join(report.get("blocking_reasons") or []))
    return report


def _safe_json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def run_live_smoke(
    base_url: str,
    *,
    expect_scheduler_ready: bool = False,
    timeout_seconds: float = 10.0,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run the read-only Step 5S smoke plan against a deployed API."""
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise ValueError("timeout_seconds must be greater than 0 and no more than 60.")
    normalized = normalize_smoke_base_url(base_url)
    plan = build_live_smoke_plan(normalized, expect_scheduler_ready=expect_scheduler_ready)
    owned_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
    results: list[dict[str, Any]] = []
    try:
        for item in plan["requests"]:
            url = normalized + item["path"]
            try:
                response = http_client.get(url, timeout=timeout_seconds)
                status = int(response.status_code)
                body = _safe_json(response)
                passed = status in item["allowed_statuses"]
                detail = f"HTTP {status}"
                if item["name"] == "service_root" and passed:
                    passed = isinstance(body, dict) and body.get("status") == "online"
                    detail += "; root payload valid" if passed else "; root payload invalid"
                elif item["name"] == "service_health" and passed:
                    passed = isinstance(body, dict) and body.get("status") == "ok"
                    detail += "; liveness payload valid" if passed else "; liveness payload invalid"
                elif item["name"] == "openapi_contract" and passed:
                    paths = set((body or {}).get("paths", {})) if isinstance(body, dict) else set()
                    missing = [path for path in REQUIRED_OPENAPI_PATHS if path not in paths]
                    passed = not missing
                    detail += "; required Step 5S routes present" if passed else f"; missing routes: {missing}"
                elif item["name"] == "step_5r_readiness" and passed and expect_scheduler_ready:
                    passed = isinstance(body, dict) and body.get("scheduler_allowed") is True
                    detail += "; scheduler allowed" if passed else "; scheduler not allowed"
                elif item["name"] == "step_5s_deployment" and passed:
                    passed = isinstance(body, dict) and body.get("deployment_ready") is True
                    if expect_scheduler_ready:
                        passed = passed and body.get("live_write_ready") is True
                    detail += "; deployment contract valid" if passed else "; deployment contract not ready"
                results.append({
                    "name": item["name"],
                    "method": "GET",
                    "path": item["path"],
                    "status_code": status,
                    "passed": bool(passed),
                    "detail": detail,
                })
            except Exception as exc:
                results.append({
                    "name": item["name"],
                    "method": "GET",
                    "path": item["path"],
                    "status_code": None,
                    "passed": False,
                    "detail": f"{type(exc).__name__}: {exc}",
                })
    finally:
        if owned_client:
            http_client.close()

    passed = all(row["passed"] for row in results)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_live_deployment_smoke_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "base_url": normalized,
        "expect_scheduler_ready": bool(expect_scheduler_ready),
        "passed": passed,
        "check_count": len(results),
        "passed_count": sum(1 for row in results if row["passed"]),
        "failed_count": sum(1 for row in results if not row["passed"]),
        "results": results,
        "safety": plan["safety"],
    }
