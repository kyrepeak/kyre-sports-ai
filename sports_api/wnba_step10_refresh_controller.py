"""Step 10D: isolated WNBA live-market refresh-cycle controller.

This layer coordinates caller-supplied provider refresh attempts, applies certified
Step-10B adapters, builds a certified Step-10C reconciled snapshot, reports retry and
refresh-cadence metadata, and can fall back to one verified still-fresh last-good
Step-10C snapshot. It does not fetch providers, sleep, schedule jobs, persist data,
call Step 9, or enable production.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping, Sequence

from sports_api import wnba_step10_live_market_input as step10a
from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_market_snapshot as step10c

SOURCE = "Kyre Sports API WNBA Step 10D isolated market refresh controller"
SCHEMA_VERSION = "wnba_step_10d_refresh_controller_v1"
MODEL_VERSION = "wnba_step10d_isolated_refresh_cycle_2026_regular_v1"
RELEASE_ID = "wnba_step10d_refresh_controller_2026_regular_season_v1"
STEP10D_REFRESH_CONTROLLER_ENABLED_ENV = "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED"
STEP10C_FROZEN_HEAD_SHA = "a5264f40d2fe9f17e5cefa3c20e0d2ad31b73f3e"

DEFAULT_REFRESH_INTERVAL_SECONDS = 60
MAX_REFRESH_INTERVAL_SECONDS = 3_600
DEFAULT_MAX_ATTEMPTS_PER_PROVIDER = 3
MAX_ATTEMPTS_PER_PROVIDER = 5
DEFAULT_RETRY_BASE_SECONDS = 2.0
DEFAULT_RETRY_MULTIPLIER = 2.0
DEFAULT_RETRY_MAX_SECONDS = 30.0
DEFAULT_MAX_LAST_GOOD_AGE_SECONDS = step10c.DEFAULT_MAX_QUOTE_AGE_SECONDS
MAX_PROVIDER_REFRESHES = 50
MAX_ERROR_CODE_LENGTH = 80

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep10RefreshControllerDisabledError(RuntimeError):
    """Raised when Step 10D is not isolated behind all required gates."""


class WNBAStep10RefreshControllerInputError(ValueError):
    """Raised for malformed refresh-cycle input."""


class WNBAStep10RefreshControllerIntegrityError(ValueError):
    """Raised when a last-good Step-10C snapshot fails frozen integrity checks."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step10d_refresh_controller_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP10D_REFRESH_CONTROLLER_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep10RefreshControllerDisabledError(
            "Step 10D refuses to run while production/scheduler switches are enabled: "
            + ", ".join(bad)
        )
    if not _truthy(source.get(STEP10D_REFRESH_CONTROLLER_ENABLED_ENV)):
        raise WNBAStep10RefreshControllerDisabledError(
            f"Step 10D requires {STEP10D_REFRESH_CONTROLLER_ENABLED_ENV}=true."
        )
    if not step10c.step10c_market_snapshot_enabled(source):
        raise WNBAStep10RefreshControllerDisabledError(
            "Step 10D requires the frozen Step-10C snapshot gate to be explicitly enabled."
        )
    if not step10b.step10b_market_adapter_enabled(source):
        raise WNBAStep10RefreshControllerDisabledError(
            "Step 10D requires the frozen Step-10B adapter gate to be explicitly enabled."
        )
    if not step10a.step10a_live_market_input_enabled(source):
        raise WNBAStep10RefreshControllerDisabledError(
            "Step 10D requires the frozen Step-10A input gate to be explicitly enabled."
        )


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _strict_keys(value: Mapping[str, Any], *, allowed: set[str], required: set[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} must be an object.")
    extras = sorted(str(key) for key in value if key not in allowed)
    missing = sorted(key for key in required if key not in value)
    if extras:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D rejects unknown {label} fields: " + ", ".join(extras)
        )
    if missing:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D missing required {label} fields: " + ", ".join(missing)
        )


def _clean_label(value: Any, label: str, *, maximum: int = 100) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or len(text) > maximum:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D {label} must contain 1 through {maximum} characters."
        )
    return text


def _evaluation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep10RefreshControllerInputError("WNBA Step 10D evaluated_at must be timezone-aware.")
    return result.astimezone(timezone.utc)


def _parse_timestamp(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} is required.")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D {label} must be ISO-8601 with timezone."
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D {label} must include a timezone offset."
        )
    return result.astimezone(timezone.utc)


def _positive_number(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} must be numeric.") from exc
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D {label} must be from {minimum:g} through {maximum:g}."
        )
    return result


def _positive_int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} must be an integer.") from exc
    if result != value and not (isinstance(value, str) and str(result) == value.strip()):
        raise WNBAStep10RefreshControllerInputError(f"WNBA Step 10D {label} must be an integer.")
    if not minimum <= result <= maximum:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D {label} must be from {minimum} through {maximum}."
        )
    return result


def _retry_delay(attempt_number: int, *, base: float, multiplier: float, maximum: float) -> float:
    if attempt_number <= 1:
        return 0.0
    return min(maximum, base * (multiplier ** (attempt_number - 2)))


def _verify_last_good_snapshot(snapshot: Mapping[str, Any]) -> None:
    if not isinstance(snapshot, Mapping):
        raise WNBAStep10RefreshControllerIntegrityError("Step 10D last-good snapshot must be an object.")
    if snapshot.get("data_type") != "wnba_reconciled_live_market_snapshot":
        raise WNBAStep10RefreshControllerIntegrityError("Unexpected last-good Step-10C data_type.")
    if snapshot.get("schema_version") != step10c.SCHEMA_VERSION:
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C schema drift.")
    if snapshot.get("model_version") != step10c.MODEL_VERSION:
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C model drift.")
    if snapshot.get("release_id") != step10c.RELEASE_ID:
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C release drift.")
    lineage = snapshot.get("lineage", {})
    if lineage.get("step10b_frozen_head_sha") != step10c.STEP10B_FROZEN_HEAD_SHA:
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C frozen Step-10B lineage drift.")
    surface = {
        key: value for key, value in snapshot.items()
        if key not in {"generated_at_utc", "snapshot_content_sha256"}
    }
    if snapshot.get("snapshot_content_sha256") != _canonical_hash(surface):
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C snapshot content hash mismatch.")
    snap_meta = snapshot.get("snapshot", {})
    if not snap_meta.get("board_synchronized"):
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C board is not synchronized.")
    records = snapshot.get("records")
    if not isinstance(records, list) or not records:
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C snapshot has no eligible records.")


def _last_good_age_seconds(snapshot: Mapping[str, Any], evaluated: datetime) -> float:
    latest = _parse_timestamp(snapshot.get("snapshot", {}).get("board_latest_capture_utc"), "last_good latest capture")
    age = (evaluated - latest).total_seconds()
    if age < -step10a.MARKET_FUTURE_TOLERANCE_SECONDS:
        raise WNBAStep10RefreshControllerIntegrityError("Last-good Step-10C snapshot is too far in the future.")
    return max(0.0, age)


def _cycle_id(started_at: datetime, providers: Sequence[str]) -> str:
    material = {
        "started_at_utc": started_at.isoformat(),
        "providers": sorted((provider.casefold() for provider in providers)),
        "release_id": RELEASE_ID,
    }
    return "s10d-" + started_at.strftime("%Y%m%dT%H%M%SZ") + "-" + _canonical_hash(material)[:16]


def run_step10d_refresh_cycle(
    provider_refreshes: Sequence[Mapping[str, Any]],
    *,
    evaluated_at: datetime | None = None,
    cycle_started_at: datetime | None = None,
    last_good_snapshot: Mapping[str, Any] | None = None,
    expected_sportsbooks: Sequence[str] | None = None,
    refresh_interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
    max_attempts_per_provider: int = DEFAULT_MAX_ATTEMPTS_PER_PROVIDER,
    retry_base_seconds: float = DEFAULT_RETRY_BASE_SECONDS,
    retry_multiplier: float = DEFAULT_RETRY_MULTIPLIER,
    retry_max_seconds: float = DEFAULT_RETRY_MAX_SECONDS,
    allow_last_good_fallback: bool = True,
    max_last_good_age_seconds: float = DEFAULT_MAX_LAST_GOOD_AGE_SECONDS,
    max_quote_age_seconds: float = step10c.DEFAULT_MAX_QUOTE_AGE_SECONDS,
    max_market_sync_seconds: float = step10c.DEFAULT_MAX_MARKET_SYNC_SECONDS,
    max_board_sync_seconds: float = step10c.DEFAULT_MAX_BOARD_SYNC_SECONDS,
    require_board_synchronized: bool = True,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run one explicit refresh cycle without network, sleeping, persistence, or scheduling."""
    _assert_safe_environment(env)
    if isinstance(provider_refreshes, (str, bytes)) or not isinstance(provider_refreshes, Sequence):
        raise WNBAStep10RefreshControllerInputError("WNBA Step 10D provider_refreshes must be a sequence.")
    if not 1 <= len(provider_refreshes) <= MAX_PROVIDER_REFRESHES:
        raise WNBAStep10RefreshControllerInputError(
            f"WNBA Step 10D requires 1 through {MAX_PROVIDER_REFRESHES} provider refreshes."
        )
    if not isinstance(allow_last_good_fallback, bool) or not isinstance(require_board_synchronized, bool):
        raise WNBAStep10RefreshControllerInputError("WNBA Step 10D boolean controls must be boolean.")

    evaluated = _evaluation_time(evaluated_at)
    started = _evaluation_time(cycle_started_at) if cycle_started_at is not None else evaluated
    if started > evaluated + timedelta(seconds=step10a.MARKET_FUTURE_TOLERANCE_SECONDS):
        raise WNBAStep10RefreshControllerInputError("Step 10D cycle_started_at is too far in the future.")

    refresh_interval = _positive_int(
        refresh_interval_seconds, "refresh_interval_seconds", minimum=1, maximum=MAX_REFRESH_INTERVAL_SECONDS
    )
    max_attempts = _positive_int(
        max_attempts_per_provider, "max_attempts_per_provider", minimum=1, maximum=MAX_ATTEMPTS_PER_PROVIDER
    )
    retry_base = _positive_number(retry_base_seconds, "retry_base_seconds", minimum=0.1, maximum=300.0)
    retry_multiplier_value = _positive_number(retry_multiplier, "retry_multiplier", minimum=1.0, maximum=10.0)
    retry_max = _positive_number(retry_max_seconds, "retry_max_seconds", minimum=retry_base, maximum=900.0)
    last_good_limit = _positive_number(
        max_last_good_age_seconds, "max_last_good_age_seconds", minimum=1.0, maximum=86_400.0
    )

    verified_last_good: Mapping[str, Any] | None = None
    last_good_age: float | None = None
    if last_good_snapshot is not None:
        _verify_last_good_snapshot(last_good_snapshot)
        verified_last_good = last_good_snapshot
        last_good_age = _last_good_age_seconds(last_good_snapshot, evaluated)

    providers: list[str] = []
    seen_providers: set[str] = set()
    normalized_refreshes = []
    for entry in provider_refreshes:
        _strict_keys(
            entry,
            allowed={"provider", "adapter_type", "attempts"},
            required={"provider", "adapter_type", "attempts"},
            label="provider refresh",
        )
        provider = _clean_label(entry["provider"], "provider")
        folded = provider.casefold()
        if folded in seen_providers:
            raise WNBAStep10RefreshControllerInputError("Step 10D provider identities must be unique per cycle.")
        seen_providers.add(folded)
        adapter_type = str(entry["adapter_type"] or "").strip().casefold()
        if adapter_type not in step10b.SUPPORTED_ADAPTERS:
            raise WNBAStep10RefreshControllerInputError("Step 10D provider adapter_type is not certified.")
        attempts = entry["attempts"]
        if isinstance(attempts, (str, bytes)) or not isinstance(attempts, Sequence) or not attempts:
            raise WNBAStep10RefreshControllerInputError("Step 10D provider attempts must be a nonempty sequence.")
        providers.append(provider)
        normalized_refreshes.append((provider, adapter_type, attempts))

    successful_adapters: list[dict[str, Any]] = []
    provider_results: list[dict[str, Any]] = []
    total_attempts_consumed = 0

    for provider, adapter_type, attempts in normalized_refreshes:
        attempt_reports = []
        successful_snapshot: dict[str, Any] | None = None
        terminal_reason = "attempts_exhausted"
        attempts_to_consume = list(attempts[:max_attempts])
        for index, attempt in enumerate(attempts_to_consume, start=1):
            delay = _retry_delay(index, base=retry_base, multiplier=retry_multiplier_value, maximum=retry_max)
            _strict_keys(
                attempt,
                allowed={"ok", "payload", "error_code"},
                required={"ok"},
                label="provider attempt",
            )
            ok = attempt["ok"]
            if not isinstance(ok, bool):
                raise WNBAStep10RefreshControllerInputError("Step 10D attempt ok must be boolean.")
            total_attempts_consumed += 1
            if ok:
                if "payload" not in attempt or "error_code" in attempt:
                    raise WNBAStep10RefreshControllerInputError(
                        "Successful Step 10D attempts require payload and forbid error_code."
                    )
                try:
                    adapted = step10b.adapt_step10b_market_payload(
                        adapter_type,
                        attempt["payload"],
                        evaluated_at=evaluated,
                        env=env,
                    )
                    if str(adapted.get("adapter", {}).get("provider", "")).casefold() != provider.casefold():
                        raise WNBAStep10RefreshControllerInputError(
                            "Step 10D declared provider does not match adapted payload provider."
                        )
                except WNBAStep10RefreshControllerInputError:
                    raise
                except Exception as exc:
                    attempt_reports.append({
                        "attempt_number": index,
                        "retry_delay_seconds_before_attempt": round(delay, 3),
                        "result": "adapter_rejected",
                        "error_code": type(exc).__name__,
                    })
                    terminal_reason = "adapter_rejected"
                    continue
                successful_snapshot = adapted
                attempt_reports.append({
                    "attempt_number": index,
                    "retry_delay_seconds_before_attempt": round(delay, 3),
                    "result": "success",
                    "adapter_content_sha256": adapted["adapter_content_sha256"],
                })
                terminal_reason = "success"
                break
            else:
                if "payload" in attempt or "error_code" not in attempt:
                    raise WNBAStep10RefreshControllerInputError(
                        "Failed Step 10D attempts require error_code and forbid payload."
                    )
                error_code = _clean_label(attempt["error_code"], "error_code", maximum=MAX_ERROR_CODE_LENGTH)
                attempt_reports.append({
                    "attempt_number": index,
                    "retry_delay_seconds_before_attempt": round(delay, 3),
                    "result": "provider_error",
                    "error_code": error_code,
                })
                terminal_reason = "provider_error"

        if successful_snapshot is not None:
            successful_adapters.append(successful_snapshot)
        provider_results.append({
            "provider": provider,
            "adapter_type": adapter_type,
            "attempts_available": len(attempts),
            "attempts_consumed": len(attempt_reports),
            "retries_planned": max(0, len(attempt_reports) - 1),
            "succeeded": successful_snapshot is not None,
            "terminal_reason": terminal_reason,
            "attempts": attempt_reports,
        })

    current_snapshot = None
    current_failure_reason = None
    if successful_adapters:
        try:
            current_snapshot = step10c.build_step10c_market_snapshot(
                successful_adapters,
                evaluated_at=evaluated,
                previous_snapshot=verified_last_good,
                expected_sportsbooks=expected_sportsbooks,
                max_quote_age_seconds=max_quote_age_seconds,
                max_market_sync_seconds=max_market_sync_seconds,
                max_board_sync_seconds=max_board_sync_seconds,
                require_board_synchronized=require_board_synchronized,
                env=env,
            )
        except step10c.WNBAStep10MarketSnapshotNotReadyError as exc:
            current_failure_reason = f"{type(exc).__name__}:{exc}"
    else:
        current_failure_reason = "no_provider_refresh_succeeded"

    fallback_eligible = (
        allow_last_good_fallback
        and verified_last_good is not None
        and last_good_age is not None
        and last_good_age <= last_good_limit
    )

    if current_snapshot is not None:
        status = "ready"
        snapshot_source = "current_refresh"
        served_snapshot = current_snapshot
    elif fallback_eligible:
        status = "degraded_last_good"
        snapshot_source = "last_good_snapshot"
        served_snapshot = verified_last_good
    else:
        status = "not_ready"
        snapshot_source = "none"
        served_snapshot = None

    succeeded_count = sum(1 for row in provider_results if row["succeeded"])
    failed_count = len(provider_results) - succeeded_count
    next_due = evaluated + timedelta(seconds=refresh_interval)
    cycle_identifier = _cycle_id(started, providers)

    result = {
        "data_type": "wnba_live_market_refresh_cycle",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "refresh_cycle_id": cycle_identifier,
        "cycle_started_at_utc": started.isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "status": status,
        "snapshot_source": snapshot_source,
        "refresh": {
            "refresh_interval_seconds": refresh_interval,
            "next_refresh_due_at_utc": next_due.isoformat(),
            "provider_count": len(provider_results),
            "successful_provider_count": succeeded_count,
            "failed_provider_count": failed_count,
            "total_attempts_consumed": total_attempts_consumed,
            "providers_retried_count": sum(1 for row in provider_results if row["retries_planned"] > 0),
            "retry_policy": {
                "max_attempts_per_provider": max_attempts,
                "base_seconds": retry_base,
                "multiplier": retry_multiplier_value,
                "max_seconds": retry_max,
                "sleep_executed": False,
                "delays_are_plan_metadata_only": True,
            },
        },
        "providers": provider_results,
        "current_refresh": {
            "step10c_snapshot_created": current_snapshot is not None,
            "failure_reason": current_failure_reason,
            "snapshot_content_sha256": (
                current_snapshot.get("snapshot_content_sha256") if current_snapshot is not None else None
            ),
        },
        "last_good": {
            "supplied": verified_last_good is not None,
            "snapshot_content_sha256": (
                verified_last_good.get("snapshot_content_sha256") if verified_last_good is not None else None
            ),
            "age_seconds_at_evaluation": round(last_good_age, 3) if last_good_age is not None else None,
            "max_age_seconds": last_good_limit,
            "fallback_allowed": allow_last_good_fallback,
            "fallback_eligible": fallback_eligible,
            "used": snapshot_source == "last_good_snapshot",
        },
        "market_snapshot": served_snapshot,
        "lineage": {
            "step10c_release_id": step10c.RELEASE_ID,
            "step10c_model_version": step10c.MODEL_VERSION,
            "step10c_schema_version": step10c.SCHEMA_VERSION,
            "step10c_frozen_head_sha": STEP10C_FROZEN_HEAD_SHA,
            "served_step10c_snapshot_content_sha256": (
                served_snapshot.get("snapshot_content_sha256") if served_snapshot is not None else None
            ),
        },
        "contract": {
            "provider_refresh_attempts_are_caller_supplied": True,
            "provider_network_fetch_allowed": False,
            "controller_sleep_allowed": False,
            "controller_scheduler_allowed": False,
            "refresh_cadence_is_metadata_only": True,
            "successful_payloads_must_pass_frozen_step10b": True,
            "current_snapshot_must_pass_frozen_step10c": True,
            "last_good_snapshot_must_be_content_verified_and_age_bounded": True,
            "step10e_owns_full_live_pipeline_integration": True,
        },
        "guardrails": {
            "provider_refresh_attempts_consumed": True,
            "sportsbook_network_fetch_performed": False,
            "retry_sleep_performed": False,
            "refresh_cycle_coordinated": True,
            "market_snapshot_reconciled": current_snapshot is not None,
            "last_good_fallback_used": snapshot_source == "last_good_snapshot",
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "cross_sportsbook_consensus_calculated": False,
            "cross_prop_ranking_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = {
        key: value for key, value in result.items()
        if key not in {"generated_at_utc", "refresh_cycle_content_sha256"}
    }
    result["refresh_cycle_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
