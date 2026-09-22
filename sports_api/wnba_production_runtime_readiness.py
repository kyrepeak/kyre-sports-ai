"""WNBA Step 5R production runtime activation and restart-readiness gate.

Step 5R does not alter any frozen WNBA model, market, Monte Carlo, ranking,
archive, publication, cadence, or Step-5Q locking semantics.  It is a local,
network-free preflight that decides whether production scheduler work is
allowed to begin.

The scheduler fails closed unless:
- production activation is explicitly requested;
- the Step-5P scheduler/provider configuration is ready;
- board, feed, and backtest SQLite paths are explicitly configured as absolute
  paths and their schemas can be opened/initialized;
- the Step-5Q lock database is absolute, separate, and usable;
- automatic signed pregame archiving is ready; and
- restart state can be read from durable storage.

No secret value is ever returned by this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api.database.wnba_current_board_store import (
    STORE_PATH_ENV as BOARD_STORE_PATH_ENV,
    get_latest_publication,
    get_latest_scheduler_run,
    initialize_store as initialize_board_store,
)
from sports_api.database.wnba_pregame_prediction_store import (
    STORE_PATH_ENV as BACKTEST_STORE_PATH_ENV,
    initialize_store as initialize_backtest_store,
)
from sports_api.database.wnba_prop_feed_store import (
    STORE_PATH_ENV as FEED_STORE_PATH_ENV,
    initialize_store as initialize_feed_store,
)
from sports_api.database.wnba_scheduler_cycle_lock import (
    LOCK_PATH_ENV,
    get_cycle_lock_status,
    initialize_lock_store,
    resolve_lock_path,
)
from sports_api.wnba_historical_backtest_calibration import ARCHIVE_SIGNING_ENV
from sports_api.wnba_pregame_board_scheduler import get_scheduler_configuration
from sports_api.wnba_prop_feed_failover import describe_provider_onboarding

MODEL_SOURCE = "Kyre Sports API WNBA Step 5R production runtime readiness"
MODEL_VERSION = "wnba_step_5r_production_runtime_readiness_v1"
SCHEMA_VERSION = "wnba_step_5r_production_runtime_readiness_v1"
ACTIVATION_ENV = "WNBA_PRODUCTION_RUNTIME_ENABLED"


class WNBAProductionRuntimeError(RuntimeError):
    pass


class WNBAProductionRuntimeNotReadyError(WNBAProductionRuntimeError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime:
    result = value or _now()
    if result.tzinfo is None or result.utcoffset() is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return _aware(value).isoformat()


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


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_from_env(environment: Mapping[str, str], name: str) -> Path | None:
    raw = _clean(environment.get(name))
    return Path(raw).expanduser() if raw else None


def _check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    detail: str,
    *,
    required: bool = True,
) -> None:
    checks.append(
        {
            "name": name,
            "required": required,
            "passed": bool(passed),
            "detail": detail,
        }
    )


def _parse_iso(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _restart_recovery(
    *,
    now_utc: datetime,
    board_path: Path,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    latest_publication = get_latest_publication(
        now_utc=now_utc,
        require_current=False,
        path=board_path,
        env=environment,
    )
    latest_run = get_latest_scheduler_run(
        path=board_path,
        env=environment,
    )
    publication_id = None
    publication_current = False
    publication_valid_until = None
    if isinstance(latest_publication, dict):
        publication_id = latest_publication.get("publication_id")
        publication_current = bool((latest_publication.get("serving") or {}).get("is_current"))
        publication_valid_until = (latest_publication.get("content") or {}).get("valid_until_utc")

    next_due_raw = latest_run.get("next_due_at_utc") if isinstance(latest_run, dict) else None
    next_due = _parse_iso(next_due_raw)
    if next_due is not None and next_due > now_utc:
        strategy = "resume_from_persisted_next_due"
    elif publication_current:
        strategy = "revalidate_current_publication_on_immediate_worker_cycle"
    else:
        strategy = "run_immediate_recovery_cycle"

    return {
        "strategy": strategy,
        "latest_publication_id": publication_id,
        "latest_publication_is_current": publication_current,
        "latest_publication_valid_until_utc": publication_valid_until,
        "latest_scheduler_run_id": latest_run.get("run_id") if isinstance(latest_run, dict) else None,
        "latest_scheduler_run_outcome": latest_run.get("outcome") if isinstance(latest_run, dict) else None,
        "persisted_next_due_at_utc": next_due_raw,
        "durable_state_is_authoritative_after_restart": True,
        "no_network_call_needed_to_choose_recovery_strategy": True,
    }


def get_production_runtime_readiness(
    *,
    env: Mapping[str, str] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Return a sanitized, network-free production preflight report."""
    environment = _environment(env)
    now = _aware(now_utc)
    activation_requested = _truthy(environment, ACTIVATION_ENV, False)
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    board_path = _path_from_env(environment, BOARD_STORE_PATH_ENV)
    feed_path = _path_from_env(environment, FEED_STORE_PATH_ENV)
    backtest_path = _path_from_env(environment, BACKTEST_STORE_PATH_ENV)

    for check_name, env_name, path in (
        ("board_store_absolute_persistent_path", BOARD_STORE_PATH_ENV, board_path),
        ("feed_store_absolute_persistent_path", FEED_STORE_PATH_ENV, feed_path),
        ("backtest_store_absolute_persistent_path", BACKTEST_STORE_PATH_ENV, backtest_path),
    ):
        if path is None:
            _check(checks, check_name, False, f"{env_name} is not configured.")
        elif not path.is_absolute():
            _check(checks, check_name, False, f"{env_name} must be an absolute production path.")
        else:
            _check(checks, check_name, True, f"{env_name} is explicitly configured as an absolute path.")

    provider_status: dict[str, Any]
    try:
        provider_status = describe_provider_onboarding(environment)
        provider_ready = provider_status.get("ready") is True
        provider_detail = (
            "Step 5O has a resolved ready provider failover chain."
            if provider_ready
            else str(provider_status.get("order_error") or "Step 5O has no ready provider.")
        )
    except Exception as exc:
        provider_status = {"ready": False, "error_type": type(exc).__name__, "detail": str(exc)}
        provider_ready = False
        provider_detail = str(exc)
    _check(checks, "step_5o_provider_ready", provider_ready, provider_detail)

    try:
        scheduler_config = get_scheduler_configuration(environment)
    except Exception as exc:
        scheduler_config = {
            "enabled": False,
            "disabled_reason": str(exc),
            "automatic_archive": {"enabled": False, "disabled_reason": str(exc)},
        }
    _check(
        checks,
        "step_5p_scheduler_configuration_ready",
        scheduler_config.get("enabled") is True,
        (
            "Frozen Step 5P scheduler configuration is enabled."
            if scheduler_config.get("enabled") is True
            else str(scheduler_config.get("disabled_reason") or "Step 5P scheduler is not ready.")
        ),
    )
    automatic_archive = scheduler_config.get("automatic_archive") or {}
    _check(
        checks,
        "signed_automatic_archive_ready",
        automatic_archive.get("enabled") is True,
        (
            "Step 5J signed automatic pregame archive is enabled."
            if automatic_archive.get("enabled") is True
            else str(automatic_archive.get("disabled_reason") or "Signed automatic archive is not ready.")
        ),
    )

    signing_secret = environment.get(ARCHIVE_SIGNING_ENV)
    signing_bytes = len(str(signing_secret).encode("utf-8")) if signing_secret is not None else 0
    _check(
        checks,
        "archive_signing_secret_strength",
        signing_bytes >= 32,
        (
            f"{ARCHIVE_SIGNING_ENV} is configured with at least 32 bytes."
            if signing_bytes >= 32
            else f"{ARCHIVE_SIGNING_ENV} must contain at least 32 bytes."
        ),
    )

    lock_path: Path | None = None
    lock_explicit = bool(_clean(environment.get(LOCK_PATH_ENV)))
    if board_path is not None and board_path.is_absolute():
        try:
            lock_path = resolve_lock_path(board_store_path=board_path, env=environment)
            _check(
                checks,
                "step_5q_lock_absolute_path",
                lock_path.is_absolute(),
                (
                    "Step 5Q lock path is absolute and separately resolved."
                    if lock_path.is_absolute()
                    else f"{LOCK_PATH_ENV} must resolve to an absolute production path."
                ),
            )
            if not lock_explicit:
                warnings.append(
                    f"{LOCK_PATH_ENV} is not explicit; Step 5Q derives a sibling lock database beside the board store."
                )
        except Exception as exc:
            _check(checks, "step_5q_lock_absolute_path", False, str(exc))
    else:
        _check(
            checks,
            "step_5q_lock_absolute_path",
            False,
            "Step 5Q lock path cannot be validated until the board store has an absolute path.",
        )

    configured_paths = [path for path in (board_path, feed_path, backtest_path, lock_path) if path is not None]
    distinct = len({str(path.resolve()) for path in configured_paths}) == len(configured_paths) if configured_paths else False
    _check(
        checks,
        "all_runtime_databases_are_distinct",
        len(configured_paths) == 4 and distinct,
        (
            "Board, feed, backtest, and scheduler-lock databases resolve to distinct files."
            if len(configured_paths) == 4 and distinct
            else "Board, feed, backtest, and scheduler-lock databases must resolve to four distinct files."
        ),
    )

    storage_results: dict[str, Any] = {}
    storage_ready = bool(
        board_path is not None
        and feed_path is not None
        and backtest_path is not None
        and lock_path is not None
        and board_path.is_absolute()
        and feed_path.is_absolute()
        and backtest_path.is_absolute()
        and lock_path.is_absolute()
        and distinct
    )
    if storage_ready:
        try:
            storage_results["board"] = initialize_board_store(board_path, env=environment)
            storage_results["feed"] = initialize_feed_store(feed_path, environment)
            storage_results["backtest"] = initialize_backtest_store(backtest_path)
            storage_results["lock"] = initialize_lock_store(
                lock_path,
                board_store_path=board_path,
                env=environment,
            )
            storage_detail = "All four runtime SQLite stores opened and their schema versions validated."
        except Exception as exc:
            storage_ready = False
            storage_detail = f"{type(exc).__name__}: {exc}"
    else:
        storage_detail = "Storage schema checks are blocked until all four absolute database paths are valid and distinct."
    _check(checks, "runtime_storage_schema_ready", storage_ready, storage_detail)

    lock_probe_ready = False
    lock_status: dict[str, Any] | None = None
    if storage_ready and lock_path is not None and board_path is not None:
        try:
            lock_status = get_cycle_lock_status(
                path=lock_path,
                board_store_path=board_path,
                env=environment,
            )
            lock_probe_ready = lock_status.get("available_now") is True
            lock_probe_detail = (
                "Step 5Q cross-process mutex is available now."
                if lock_probe_ready
                else "Step 5Q cross-process mutex is currently owned by another process."
            )
        except Exception as exc:
            lock_probe_detail = f"{type(exc).__name__}: {exc}"
    else:
        lock_probe_detail = "Cross-process mutex probe is blocked until runtime storage is ready."
    _check(checks, "step_5q_cross_process_lock_probe", lock_probe_ready, lock_probe_detail)

    restart_ready = False
    restart_state: dict[str, Any] | None = None
    if storage_ready and board_path is not None:
        try:
            restart_state = _restart_recovery(
                now_utc=now,
                board_path=board_path,
                environment=environment,
            )
            restart_ready = True
            restart_detail = "Durable Step 5P publication/run state is readable for restart recovery."
        except Exception as exc:
            restart_detail = f"{type(exc).__name__}: {exc}"
    else:
        restart_detail = "Restart recovery is blocked until runtime storage is ready."
    _check(checks, "restart_recovery_state_readable", restart_ready, restart_detail)

    required_failures = [check for check in checks if check["required"] and not check["passed"]]
    preflight_ready = not required_failures
    scheduler_allowed = activation_requested and preflight_ready
    blocking_reasons = [f"{check['name']}: {check['detail']}" for check in required_failures]
    if not activation_requested:
        activation_reason = f"{ACTIVATION_ENV} is not enabled."
    elif preflight_ready:
        activation_reason = None
    else:
        activation_reason = "Production activation requested, but one or more required preflight checks failed."

    sanitized_provider = {
        "ready": provider_ready,
        "resolved_failover_order": provider_status.get("resolved_failover_order") if isinstance(provider_status, dict) else None,
        "order_error": provider_status.get("order_error") if isinstance(provider_status, dict) else None,
    }
    paths = {
        "board_store": str(board_path) if board_path is not None else None,
        "feed_store": str(feed_path) if feed_path is not None else None,
        "backtest_store": str(backtest_path) if backtest_path is not None else None,
        "scheduler_lock_store": str(lock_path) if lock_path is not None else None,
        "scheduler_lock_path_explicit": lock_explicit,
    }
    fingerprint_payload = {
        "model_version": MODEL_VERSION,
        "activation_requested": activation_requested,
        "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
        "paths": paths,
        "provider": sanitized_provider,
        "scheduler_enabled": scheduler_config.get("enabled") is True,
        "automatic_archive_enabled": automatic_archive.get("enabled") is True,
        "signing_secret_minimum_length_pass": signing_bytes >= 32,
    }

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_production_runtime_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso(now),
        "activation_env": ACTIVATION_ENV,
        "activation_requested": activation_requested,
        "preflight_ready": preflight_ready,
        "scheduler_allowed": scheduler_allowed,
        "activation_reason": activation_reason,
        "blocking_reason_count": len(blocking_reasons),
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "checks": checks,
        "paths": paths,
        "provider": sanitized_provider,
        "scheduler_configuration": {
            "requested": scheduler_config.get("requested"),
            "enabled": scheduler_config.get("enabled"),
            "disabled_reason": scheduler_config.get("disabled_reason"),
            "loop_seconds": scheduler_config.get("loop_seconds"),
            "minimum_provider_spacing_seconds": scheduler_config.get("minimum_provider_spacing_seconds"),
            "automatic_archive": automatic_archive,
        },
        "archive_signing": {
            "environment_variable": ARCHIVE_SIGNING_ENV,
            "configured": signing_secret is not None,
            "minimum_32_bytes_pass": signing_bytes >= 32,
        },
        "storage": storage_results,
        "cross_process_lock": lock_status,
        "restart_recovery": restart_state,
        "configuration_fingerprint_sha256": _hash(fingerprint_payload),
        "semantics": {
            "preflight_is_network_free": True,
            "failed_preflight_blocks_sportsbook_collection": True,
            "failed_preflight_blocks_monte_carlo_rebuild": True,
            "read_only_current_board_serving_can_remain_available": True,
            "step_5q_distributed_lock_remains_authoritative": True,
            "frozen_step_5p_model_and_publication_semantics_are_unchanged": True,
            "secret_values_are_never_returned": True,
        },
    }


def require_production_runtime_ready(
    *,
    env: Mapping[str, str] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    report = get_production_runtime_readiness(env=env, now_utc=now_utc)
    if report["scheduler_allowed"] is not True:
        reasons = list(report.get("blocking_reasons") or [])
        if not report.get("activation_requested"):
            reasons.insert(0, f"{ACTIVATION_ENV} is not enabled.")
        detail = "; ".join(reasons) if reasons else "WNBA Step 5R production runtime is not ready."
        raise WNBAProductionRuntimeNotReadyError(detail)
    return report
