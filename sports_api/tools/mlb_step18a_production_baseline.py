"""MLB Step 18A — read-only production provenance and rollback baseline.

This module validates a sanitized snapshot of the already-running Step 17B
production host. It never mutates Render, starts a scheduler, calls a provider or
sportsbook, runs a model, writes a database, or changes wagering/actionability.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from urllib.parse import urlsplit

STEP18A_SCHEMA_VERSION = "mlb_step18a_production_baseline_v1"
STEP18A_FINAL_MARKER = "MLB_STEP18A_PRODUCTION_BASELINE_GREEN"
STEP17B_MERGED_MAIN_SHA = "911e917d9d1552289bab5f8c74604103c056982f"
STEP17B_CERTIFIED_DEPLOYED_SHA = "ece3cd2d15d091728fdbe30be774dd9c15e4fe8e"
EXPECTED_RENDER_SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
EXPECTED_RENDER_SERVICE_NAME = "kyre-sports-api"
EXPECTED_SERVICE_URL = "https://kyre-sports-api.onrender.com"
EXPECTED_WNBA_DATA_TYPE = "wnba_deployment_and_smoke_readiness"
EXPECTED_MLB_DATA_TYPE = "mlb_step17b_runtime_status_v1"

REQUIRED_TRUE_GATES = (
    "MLB_STEP17B_ALWAYS_ON_ENABLED",
    "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED",
    "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "MLB_STEP14B_DATABASE_READ_ENABLED",
    "MLB_STEP14B_DATABASE_WRITE_ENABLED",
)

FROZEN_FALSE_GATES = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
    "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
    "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED",
)

SAFE_CONFIG_KEYS = (
    "MLB_STEP17B_ALWAYS_ON_ENABLED",
    "MLB_STEP17B_LOOP_SECONDS",
    "MLB_STEP17B_EXPECTED_REVISION",
    "MLB_DEPLOYMENT_MODE",
    "WEB_CONCURRENCY",
    *REQUIRED_TRUE_GATES[1:],
    *FROZEN_FALSE_GATES,
)


class MLBStep18ABaselineError(RuntimeError):
    """Raised when the live production baseline is not the certified Step 17B state."""


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise MLBStep18ABaselineError(message)


def _validate_database_url(value: object) -> None:
    raw = _clean(value)
    parsed = urlsplit(raw or "")
    _assert(
        bool(
            raw
            and parsed.scheme.casefold() in {"postgres", "postgresql"}
            and parsed.hostname
            and parsed.path not in {"", "/"}
        ),
        "protected PostgreSQL KYRE_DATABASE_URL is missing or invalid",
    )


def _sanitize_config(env: Mapping[str, str]) -> dict[str, Any]:
    return {
        "MLB_STEP17B_ALWAYS_ON_ENABLED": _truthy(env.get("MLB_STEP17B_ALWAYS_ON_ENABLED")),
        "MLB_STEP17B_LOOP_SECONDS": _clean(env.get("MLB_STEP17B_LOOP_SECONDS")),
        "MLB_STEP17B_EXPECTED_REVISION": _clean(env.get("MLB_STEP17B_EXPECTED_REVISION")),
        "MLB_DEPLOYMENT_MODE": _clean(env.get("MLB_DEPLOYMENT_MODE")),
        "WEB_CONCURRENCY": _clean(env.get("WEB_CONCURRENCY")),
        "required_true_gates": {name: _truthy(env.get(name)) for name in REQUIRED_TRUE_GATES},
        "frozen_false_gates": {name: _truthy(env.get(name)) for name in FROZEN_FALSE_GATES},
        "database_url_configured": bool(_clean(env.get("KYRE_DATABASE_URL"))),
        "database_url_exposed": False,
    }


def validate_production_baseline(
    *,
    service: Mapping[str, Any],
    env: Mapping[str, str],
    health: Mapping[str, Any],
    wnba: Mapping[str, Any],
    mlb: Mapping[str, Any],
    captured_at_utc: str | None = None,
) -> dict[str, Any]:
    """Validate and return a sanitized, immutable rollback/provenance baseline."""
    details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), Mapping) else {}
    _assert(_clean(service.get("id")) == EXPECTED_RENDER_SERVICE_ID, "Render service identity drift")
    _assert(_clean(service.get("name")) == EXPECTED_RENDER_SERVICE_NAME, "Render service name drift")
    _assert((_clean(service.get("autoDeploy")) or "no").casefold() in {"no", "false", "off"}, "Render auto-deploy must remain off")
    _assert((_clean(details.get("runtime") or details.get("env")) or "").casefold() == "docker", "Render runtime must remain Docker")
    _assert((_clean(details.get("plan")) or "").casefold() == "free", "Render plan drift")
    _assert(not isinstance(details.get("disk"), Mapping), "unexpected persistent Render disk")

    for name in REQUIRED_TRUE_GATES:
        _assert(_truthy(env.get(name)), f"required production gate is not enabled: {name}")
    for name in FROZEN_FALSE_GATES:
        _assert(not _truthy(env.get(name)), f"frozen safety gate unexpectedly enabled: {name}")
    _assert((_clean(env.get("MLB_DEPLOYMENT_MODE")) or "").casefold() == "container", "MLB_DEPLOYMENT_MODE drift")
    _assert(_clean(env.get("WEB_CONCURRENCY")) == "1", "WEB_CONCURRENCY must remain 1")
    _assert(_clean(env.get("MLB_STEP17B_EXPECTED_REVISION")) == STEP17B_CERTIFIED_DEPLOYED_SHA, "deployed immutable revision drift")
    _validate_database_url(env.get("KYRE_DATABASE_URL"))

    _assert(health.get("status") == "ok", "hosted /health is not ok")
    _assert(wnba.get("data_type") == EXPECTED_WNBA_DATA_TYPE, "WNBA production contract drift")
    wnba_semantics = wnba.get("semantics") if isinstance(wnba.get("semantics"), Mapping) else {}
    _assert(wnba_semantics.get("deployment_gate_does_not_call_sportsbook") is True, "WNBA sportsbook safety drift")
    _assert(wnba_semantics.get("deployment_gate_does_not_run_monte_carlo") is True, "WNBA Monte Carlo safety drift")
    _assert(wnba_semantics.get("live_smoke_is_read_only") is True, "WNBA read-only safety drift")

    _assert(mlb.get("data_type") == EXPECTED_MLB_DATA_TYPE, "MLB Step 17B status contract drift")
    _assert(mlb.get("enabled") is True, "MLB Step 17B is not enabled")
    _assert(mlb.get("running") is True, "MLB Step 17B is not running")
    _assert(mlb.get("role") == "leader", "MLB Step 17B is not the active leader")
    _assert(mlb.get("leadership_acquired") is True, "MLB Step 17B leadership is not acquired")
    _assert(mlb.get("provider_calls") == 0, "MLB provider-call boundary was crossed")
    _assert(mlb.get("sportsbook_calls") == 0, "MLB sportsbook-call boundary was crossed")
    _assert(mlb.get("provider_workload_cycle_count") == 0, "MLB provider workload unexpectedly ran")
    _assert(mlb.get("sportsbook_workload_cycle_count") == 0, "MLB sportsbook workload unexpectedly ran")
    _assert(mlb.get("production_scheduler_started") is False, "legacy MLB scheduler unexpectedly started")
    _assert(mlb.get("legacy_production_runtime_started") is False, "legacy MLB runtime unexpectedly started")
    _assert(mlb.get("actionable_output_enabled") is False, "MLB actionable output unexpectedly enabled")
    _assert(mlb.get("wagering_enabled") is False, "MLB wagering unexpectedly enabled")
    _assert(mlb.get("database_secret_exposed") is False, "database secret exposure drift")
    _assert(mlb.get("new_render_service_created") is False, "unexpected Render service creation")
    _assert(mlb.get("last_error_class") in {None, ""}, "MLB Step 17B has a live runtime error")
    _assert(isinstance(mlb.get("success_count"), int) and mlb.get("success_count", 0) >= 1, "MLB Step 17B has no successful durable control cycle")
    _assert(isinstance(mlb.get("last_checkpoint_version"), int) and mlb.get("last_checkpoint_version", 0) >= 1, "MLB durable checkpoint is unavailable")
    _assert(mlb.get("recovered_from_checkpoint") is True, "MLB restart recovery is not proven in the live process")

    captured = captured_at_utc or datetime.now(timezone.utc).isoformat()
    safe_config = _sanitize_config(env)
    rollback_target = {
        "render_service_id": EXPECTED_RENDER_SERVICE_ID,
        "render_service_name": EXPECTED_RENDER_SERVICE_NAME,
        "render_service_url": EXPECTED_SERVICE_URL,
        "render_branch": _clean(service.get("branch")),
        "deployed_revision": STEP17B_CERTIFIED_DEPLOYED_SHA,
        "merged_main_sha": STEP17B_MERGED_MAIN_SHA,
        "auto_deploy": _clean(service.get("autoDeploy")),
        "runtime": _clean(details.get("runtime") or details.get("env")),
        "plan": _clean(details.get("plan")),
        "safe_config": safe_config,
        "safe_config_sha256": _canonical_hash(safe_config),
    }
    evidence = {
        "data_type": "mlb_step18a_production_baseline_evidence",
        "schema_version": STEP18A_SCHEMA_VERSION,
        "state": "green",
        "captured_at_utc": captured,
        "final_marker": STEP18A_FINAL_MARKER,
        "mutation_performed": False,
        "rollback_target": rollback_target,
        "live_health": {
            "host": "ok",
            "wnba_continuity": "ok",
            "mlb_step17b_enabled": True,
            "mlb_step17b_running": True,
            "mlb_role": "leader",
            "mlb_success_count": mlb.get("success_count"),
            "mlb_failure_count": mlb.get("failure_count"),
            "mlb_last_checkpoint_version": mlb.get("last_checkpoint_version"),
            "mlb_recovered_from_checkpoint": True,
        },
        "safety": {
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "legacy_runtime_started": False,
            "legacy_scheduler_started": False,
            "actionable_output_enabled": False,
            "wagering_enabled": False,
            "database_secret_exposed": False,
            "render_secret_exposed": False,
            "render_mutation_performed": False,
        },
    }
    evidence["evidence_sha256"] = _canonical_hash(
        {key: deepcopy(value) for key, value in evidence.items() if key != "captured_at_utc"}
    )
    return evidence


__all__ = [
    "EXPECTED_RENDER_SERVICE_ID",
    "EXPECTED_RENDER_SERVICE_NAME",
    "EXPECTED_SERVICE_URL",
    "FROZEN_FALSE_GATES",
    "MLBStep18ABaselineError",
    "REQUIRED_TRUE_GATES",
    "STEP17B_CERTIFIED_DEPLOYED_SHA",
    "STEP17B_MERGED_MAIN_SHA",
    "STEP18A_FINAL_MARKER",
    "STEP18A_SCHEMA_VERSION",
    "validate_production_baseline",
]
