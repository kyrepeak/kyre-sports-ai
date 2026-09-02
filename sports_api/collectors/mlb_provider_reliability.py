"""MLB Step 19D — bounded provider reliability for the live market feed.

This layer wraps the certified Step 19B provider reads with bounded retries,
provider cooldowns, and source-snapshot freshness checks. It is deliberately
read-only and returns its reliability state to the caller; it does not persist
state, mutate production runtime wiring, create fallback prices, or synthesize
identities.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import re
import time
from typing import Any

from sports_api.collectors.mlb_draftkings_provider import (
    MLBDraftKingsProviderNotReadyError,
    MLBDraftKingsProviderUpstreamError,
    collect_draftkings_provider_snapshots,
)
from sports_api.collectors.mlb_fanduel_direct import collect_live_mlb_game_odds
from sports_api.collectors.mlb_fanduel_player_props import collect_live_mlb_player_props
from sports_api.collectors.mlb_live_market_feed import collect_live_mlb_market_feed

DATA_TYPE = "mlb_step19d_provider_reliability_v1"
SCHEMA_VERSION = 1
STEP19D_BASE_MAIN_SHA = "0bac36999388db14b0b1e40d5e77cbf55823df88"
RELIABILITY_STATUS = "STEP19D_PROVIDER_RELIABILITY_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP19D_PROVIDER_RELIABILITY_GREEN"

FANDUEL_PROVIDER_KEY = "fanduel"
DRAFTKINGS_PROVIDER_KEY = "draftkings"
SUPPORTED_PROVIDERS = (FANDUEL_PROVIDER_KEY, DRAFTKINGS_PROVIDER_KEY)

DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_BASE_BACKOFF_SECONDS = 0.25
DEFAULT_MAX_BACKOFF_SECONDS = 2.0
DEFAULT_COOLDOWN_SECONDS = 60.0
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 120.0
DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS = 5.0

_HTTP_STATUS = re.compile(r"\b([45]\d{2})\b")


class MLBProviderReliabilityError(RuntimeError):
    """Raised when the Step 19D reliability boundary fails closed."""

    def __init__(self, category: str, detail: str):
        self.category = str(category)
        self.detail = str(detail)
        super().__init__(self.detail)


class MLBProviderCooldownError(MLBProviderReliabilityError):
    """Raised internally when a provider read is suppressed by cooldown."""

    def __init__(self, provider_key: str, cooldown_until_utc: str):
        super().__init__(
            "cooldown_active",
            f"{provider_key} is in cooldown until {cooldown_until_utc}",
        )
        self.provider_key = provider_key
        self.cooldown_until_utc = cooldown_until_utc


def reliability_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step19d_base_main_sha": STEP19D_BASE_MAIN_SHA,
        "reliability_status": RELIABILITY_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "providers_supported": list(SUPPORTED_PROVIDERS),
        "bounded_retry_enabled": True,
        "exponential_backoff_enabled": True,
        "provider_cooldown_enabled": True,
        "rate_limit_cooldown_enabled": True,
        "stale_snapshot_detection_enabled": True,
        "retry_non_retryable_configuration_errors": False,
        "retry_malformed_local_data": False,
        "fallback_price_fabrication_allowed": False,
        "synthetic_game_id_allowed": False,
        "synthetic_player_id_allowed": False,
        "fuzzy_matching_allowed": False,
        "reliability_state_persisted_by_step19d": False,
        "production_runtime_wiring_added_by_step19d": False,
        "production_database_writes_enabled": False,
        "model_probability_mutation_enabled": False,
        "projection_mutation_enabled": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
    }


def _utc(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(
                text[:-1] + "+00:00" if text.endswith("Z") else text
            )
        except ValueError as exc:
            raise MLBProviderReliabilityError(
                "malformed_timestamp", f"{field} is not valid ISO-8601"
            ) from exc
    else:
        raise MLBProviderReliabilityError(
            "missing_timestamp", f"{field} is required"
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBProviderReliabilityError(
            "malformed_timestamp", f"{field} must be timezone-aware"
        )
    return parsed.astimezone(timezone.utc)


def _utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(
    value: Any,
    field: str,
    *,
    minimum: float,
    maximum: float,
    integer: bool = False,
) -> float | int:
    if isinstance(value, bool):
        raise MLBProviderReliabilityError("invalid_policy", f"{field} is invalid")
    if integer and not isinstance(value, int):
        raise MLBProviderReliabilityError(
            "invalid_policy", f"{field} must be an integer"
        )
    try:
        result = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise MLBProviderReliabilityError(
            "invalid_policy", f"{field} must be numeric"
        ) from exc
    if not math.isfinite(float(result)) or not minimum <= float(result) <= maximum:
        raise MLBProviderReliabilityError(
            "invalid_policy",
            f"{field} must be between {minimum} and {maximum}",
        )
    return result


def _blank_provider_state() -> dict[str, Any]:
    return {
        "cooldown_until_utc": None,
        "cooldown_reason": None,
        "last_failure_kind": None,
        "last_failure_at_utc": None,
        "last_success_at_utc": None,
    }


def _normalize_state(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "providers": {key: _blank_provider_state() for key in SUPPORTED_PROVIDERS},
        }
    if not isinstance(value, Mapping):
        raise MLBProviderReliabilityError(
            "invalid_state", "reliability_state must be a mapping"
        )
    raw_version = value.get("schema_version", SCHEMA_VERSION)
    if raw_version != SCHEMA_VERSION:
        raise MLBProviderReliabilityError(
            "invalid_state", "reliability_state schema_version is unsupported"
        )
    raw_providers = value.get("providers", {})
    if not isinstance(raw_providers, Mapping):
        raise MLBProviderReliabilityError(
            "invalid_state", "reliability_state.providers must be a mapping"
        )
    unknown = sorted(set(raw_providers) - set(SUPPORTED_PROVIDERS))
    if unknown:
        raise MLBProviderReliabilityError(
            "invalid_state", f"unsupported provider state keys: {unknown}"
        )
    state = {
        "schema_version": SCHEMA_VERSION,
        "providers": {key: _blank_provider_state() for key in SUPPORTED_PROVIDERS},
    }
    for provider_key in SUPPORTED_PROVIDERS:
        raw = raw_providers.get(provider_key, {})
        if raw is None:
            raw = {}
        if not isinstance(raw, Mapping):
            raise MLBProviderReliabilityError(
                "invalid_state", f"{provider_key} state must be a mapping"
            )
        row = state["providers"][provider_key]
        for field in row:
            value_at_field = raw.get(field)
            if value_at_field is not None and not isinstance(value_at_field, str):
                raise MLBProviderReliabilityError(
                    "invalid_state", f"{provider_key}.{field} must be string or null"
                )
            row[field] = value_at_field
        if row["cooldown_until_utc"] is not None:
            _utc(row["cooldown_until_utc"], f"{provider_key}.cooldown_until_utc")
        for field in ("last_failure_at_utc", "last_success_at_utc"):
            if row[field] is not None:
                _utc(row[field], f"{provider_key}.{field}")
    return deepcopy(state)


def _cooldown_active(
    state: dict[str, Any], provider_key: str, now: datetime
) -> bool:
    row = state["providers"][provider_key]
    cooldown = row.get("cooldown_until_utc")
    if cooldown is None:
        return False
    until = _utc(cooldown, f"{provider_key}.cooldown_until_utc")
    if until <= now:
        row["cooldown_until_utc"] = None
        row["cooldown_reason"] = None
        return False
    return True


def _enter_cooldown(
    state: dict[str, Any],
    provider_key: str,
    *,
    now: datetime,
    cooldown_seconds: float,
    reason: str,
) -> None:
    row = state["providers"][provider_key]
    row["cooldown_until_utc"] = _utc_z(
        now + timedelta(seconds=float(cooldown_seconds))
    )
    row["cooldown_reason"] = reason
    row["last_failure_kind"] = reason
    row["last_failure_at_utc"] = _utc_z(now)


def _mark_failure(
    state: dict[str, Any], provider_key: str, *, now: datetime, kind: str
) -> None:
    row = state["providers"][provider_key]
    row["last_failure_kind"] = kind
    row["last_failure_at_utc"] = _utc_z(now)


def _mark_success(
    state: dict[str, Any], provider_key: str, *, now: datetime
) -> None:
    row = state["providers"][provider_key]
    row["last_success_at_utc"] = _utc_z(now)


def _clear_failure_if_fully_healthy(
    state: dict[str, Any],
    provider_key: str,
    *,
    terminals: list[dict[str, Any]],
) -> None:
    if terminals and all(row["outcome"] == "success" for row in terminals):
        state_row = state["providers"][provider_key]
        state_row["cooldown_until_utc"] = None
        state_row["cooldown_reason"] = None
        state_row["last_failure_kind"] = None
        state_row["last_failure_at_utc"] = None


def _http_status_from_exception(exc: BaseException) -> int | None:
    match = _HTTP_STATUS.search(str(exc))
    return int(match.group(1)) if match else None


def _classify_failure(exc: BaseException) -> tuple[str, bool, bool]:
    """Return (kind, retryable, immediate_cooldown)."""
    if isinstance(exc, MLBProviderCooldownError):
        return "cooldown_active", False, False
    if isinstance(exc, MLBProviderReliabilityError):
        if exc.category == "stale_data":
            return "stale_data", False, True
        return exc.category, False, False
    if isinstance(exc, MLBDraftKingsProviderNotReadyError):
        return "not_ready", False, False

    status = _http_status_from_exception(exc)
    if status == 429:
        return "rate_limited", False, True
    if status in {408, 425} or (status is not None and 500 <= status <= 599):
        return "transient_upstream", True, False
    if status is not None and 400 <= status <= 499:
        return "provider_rejected", False, False

    if isinstance(exc, MLBDraftKingsProviderUpstreamError):
        return "transient_upstream", True, False
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "transient_transport", True, False

    name = type(exc).__name__.casefold()
    if any(token in name for token in ("timeout", "connection", "urlerror", "requesterror")):
        return "transient_transport", True, False
    return "non_retryable_error", False, False


def _snapshot_age_seconds(
    snapshot: Mapping[str, Any],
    *,
    now: datetime,
    max_snapshot_age_seconds: float,
    clock_skew_tolerance_seconds: float,
) -> float:
    collected = _utc(snapshot.get("collected_at_utc"), "provider collected_at_utc")
    age = (now - collected).total_seconds()
    if age < -float(clock_skew_tolerance_seconds):
        raise MLBProviderReliabilityError(
            "future_timestamp",
            "provider collected_at_utc exceeds allowed clock skew",
        )
    if age > float(max_snapshot_age_seconds):
        raise MLBProviderReliabilityError(
            "stale_data",
            f"provider snapshot age {age:.3f}s exceeds {max_snapshot_age_seconds:.3f}s",
        )
    return max(0.0, age)


def _terminal_attempts(telemetry: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in telemetry:
        result[(str(row["provider_key"]), str(row["surface"]))] = row
    return result


def _provider_rows(
    *,
    requested_surfaces: dict[str, list[str]],
    telemetry: list[dict[str, Any]],
    state: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    terminals = _terminal_attempts(telemetry)
    rows: list[dict[str, Any]] = []
    for provider_key in SUPPORTED_PROVIDERS:
        surfaces = requested_surfaces.get(provider_key, [])
        if not surfaces:
            continue
        provider_terminals = [
            terminals[(provider_key, surface)]
            for surface in surfaces
            if (provider_key, surface) in terminals
        ]
        outcomes = [row["outcome"] for row in provider_terminals]
        failure_kinds = sorted(
            {
                str(row["failure_kind"])
                for row in provider_terminals
                if row.get("failure_kind")
            }
        )
        active_cooldown = _cooldown_active(state, provider_key, now)
        if active_cooldown:
            status = "cooldown"
        elif outcomes and all(value == "success" for value in outcomes):
            status = "healthy"
        elif "success" in outcomes:
            status = "degraded"
        elif outcomes and all(
            row.get("failure_kind") == "not_ready" for row in provider_terminals
        ):
            status = "not_ready"
        else:
            status = "error"

        network_attempts = sum(
            1
            for row in telemetry
            if row["provider_key"] == provider_key and int(row.get("attempt", 0)) > 0
        )
        retries = sum(
            1
            for row in telemetry
            if row["provider_key"] == provider_key and int(row.get("attempt", 0)) > 1
        )
        rows.append(
            {
                "provider_key": provider_key,
                "status": status,
                "surfaces_requested": list(surfaces),
                "network_attempt_count": network_attempts,
                "retry_count": retries,
                "failure_kinds": failure_kinds,
                "cooldown_until_utc": state["providers"][provider_key].get(
                    "cooldown_until_utc"
                ),
            }
        )
    return rows


def _overall_status(
    *,
    live_data_present: bool,
    provider_rows: list[dict[str, Any]],
) -> str:
    statuses = [str(row["status"]) for row in provider_rows]
    retry_count = sum(int(row["retry_count"]) for row in provider_rows)
    if live_data_present:
        if statuses and all(status == "healthy" for status in statuses):
            return "recovered" if retry_count else "ok"
        return "fallback"
    if statuses and any(status == "healthy" for status in statuses):
        return "empty"
    if statuses and all(status == "cooldown" for status in statuses):
        return "cooldown"
    if any(status in {"error", "cooldown", "degraded"} for status in statuses):
        return "unavailable"
    if statuses and all(status == "not_ready" for status in statuses):
        return "not_ready"
    if any(status == "not_ready" for status in statuses):
        return "not_ready"
    return "empty"


def collect_reliable_mlb_market_feed(
    *,
    now_utc: datetime | None = None,
    reliability_state: Mapping[str, Any] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_backoff_seconds: float = DEFAULT_BASE_BACKOFF_SECONDS,
    max_backoff_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS,
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    max_snapshot_age_seconds: float = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    clock_skew_tolerance_seconds: float = DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS,
    sleeper: Callable[[float], Any] = time.sleep,
    max_events: int = 30,
    include_fanduel_game_odds: bool = True,
    include_fanduel_player_props: bool = True,
    include_draftkings: bool = True,
    fanduel_game_collector: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_prop_collector: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_collector: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect a Step 19B feed with bounded provider retries and cooldown state.

    ``reliability_state`` is caller-owned. Step 19D returns a new state object but
    never persists it. A provider in active cooldown is not read. A retry is
    attempted only for failures classified as transient transport/upstream
    failures. Rate limits and stale snapshots enter cooldown immediately.
    """
    now = _utc(now_utc or datetime.now(timezone.utc), "now_utc")
    attempts = int(
        _number(max_attempts, "max_attempts", minimum=1, maximum=5, integer=True)
    )
    base_backoff = float(
        _number(
            base_backoff_seconds,
            "base_backoff_seconds",
            minimum=0.0,
            maximum=30.0,
        )
    )
    max_backoff = float(
        _number(
            max_backoff_seconds,
            "max_backoff_seconds",
            minimum=0.0,
            maximum=60.0,
        )
    )
    if max_backoff < base_backoff:
        raise MLBProviderReliabilityError(
            "invalid_policy",
            "max_backoff_seconds must be greater than or equal to base_backoff_seconds",
        )
    cooldown = float(
        _number(cooldown_seconds, "cooldown_seconds", minimum=1.0, maximum=3600.0)
    )
    max_age = float(
        _number(
            max_snapshot_age_seconds,
            "max_snapshot_age_seconds",
            minimum=1.0,
            maximum=3600.0,
        )
    )
    skew = float(
        _number(
            clock_skew_tolerance_seconds,
            "clock_skew_tolerance_seconds",
            minimum=0.0,
            maximum=60.0,
        )
    )
    if not callable(sleeper):
        raise MLBProviderReliabilityError(
            "invalid_policy", "sleeper must be callable"
        )
    for value, field in (
        (include_fanduel_game_odds, "include_fanduel_game_odds"),
        (include_fanduel_player_props, "include_fanduel_player_props"),
        (include_draftkings, "include_draftkings"),
    ):
        if not isinstance(value, bool):
            raise MLBProviderReliabilityError(
                "invalid_policy", f"{field} must be boolean"
            )

    state = _normalize_state(reliability_state)
    telemetry: list[dict[str, Any]] = []
    requested_surfaces = {
        FANDUEL_PROVIDER_KEY: [
            surface
            for enabled, surface in (
                (include_fanduel_game_odds, "fanduel_game_odds"),
                (include_fanduel_player_props, "fanduel_player_props"),
            )
            if enabled
        ],
        DRAFTKINGS_PROVIDER_KEY: [
            "draftkings_game_odds"
        ]
        if include_draftkings
        else [],
    }

    start_cooldown = {
        provider_key: _cooldown_active(state, provider_key, now)
        for provider_key in SUPPORTED_PROVIDERS
    }

    for provider_key, surfaces in requested_surfaces.items():
        if not start_cooldown[provider_key]:
            continue
        for surface in surfaces:
            telemetry.append(
                {
                    "provider_key": provider_key,
                    "surface": surface,
                    "attempt": 0,
                    "outcome": "cooldown_skip",
                    "failure_kind": "cooldown_active",
                    "retryable": False,
                    "backoff_seconds": 0.0,
                    "snapshot_age_seconds": None,
                }
            )

    def reliable_wrapper(
        *,
        provider_key: str,
        surface: str,
        collector: Callable[..., Mapping[str, Any]],
    ) -> Callable[..., Mapping[str, Any]]:
        def wrapped(**kwargs: Any) -> Mapping[str, Any]:
            if _cooldown_active(state, provider_key, now):
                until = str(state["providers"][provider_key]["cooldown_until_utc"])
                telemetry.append(
                    {
                        "provider_key": provider_key,
                        "surface": surface,
                        "attempt": 0,
                        "outcome": "cooldown_skip",
                        "failure_kind": "cooldown_active",
                        "retryable": False,
                        "backoff_seconds": 0.0,
                        "snapshot_age_seconds": None,
                    }
                )
                raise MLBProviderCooldownError(provider_key, until)

            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    snapshot = collector(**kwargs)
                    if not isinstance(snapshot, Mapping):
                        raise MLBProviderReliabilityError(
                            "malformed_snapshot",
                            f"{surface} collector must return a mapping",
                        )
                    age = _snapshot_age_seconds(
                        snapshot,
                        now=now,
                        max_snapshot_age_seconds=max_age,
                        clock_skew_tolerance_seconds=skew,
                    )
                    telemetry.append(
                        {
                            "provider_key": provider_key,
                            "surface": surface,
                            "attempt": attempt,
                            "outcome": "success",
                            "failure_kind": None,
                            "retryable": False,
                            "backoff_seconds": 0.0,
                            "snapshot_age_seconds": round(age, 6),
                        }
                    )
                    _mark_success(state, provider_key, now=now)
                    return snapshot
                except Exception as exc:
                    last_exc = exc
                    kind, retryable, immediate_cooldown = _classify_failure(exc)
                    backoff = 0.0
                    if retryable and attempt < attempts:
                        backoff = min(
                            max_backoff,
                            base_backoff * (2 ** (attempt - 1)),
                        )
                    telemetry.append(
                        {
                            "provider_key": provider_key,
                            "surface": surface,
                            "attempt": attempt,
                            "outcome": "error",
                            "failure_kind": kind,
                            "retryable": retryable,
                            "backoff_seconds": round(backoff, 6),
                            "snapshot_age_seconds": None,
                        }
                    )
                    _mark_failure(state, provider_key, now=now, kind=kind)
                    if immediate_cooldown:
                        _enter_cooldown(
                            state,
                            provider_key,
                            now=now,
                            cooldown_seconds=cooldown,
                            reason=kind,
                        )
                        raise
                    if retryable and attempt < attempts:
                        sleeper(backoff)
                        continue
                    if retryable:
                        _enter_cooldown(
                            state,
                            provider_key,
                            now=now,
                            cooldown_seconds=cooldown,
                            reason="transient_retries_exhausted",
                        )
                    raise
            assert last_exc is not None
            raise last_exc

        return wrapped

    fd_game_base = fanduel_game_collector or collect_live_mlb_game_odds
    fd_prop_base = fanduel_prop_collector or collect_live_mlb_player_props
    dk_base = draftkings_collector or collect_draftkings_provider_snapshots

    effective_fd_game = include_fanduel_game_odds and not start_cooldown[FANDUEL_PROVIDER_KEY]
    effective_fd_props = include_fanduel_player_props and not start_cooldown[FANDUEL_PROVIDER_KEY]
    effective_dk = include_draftkings and not start_cooldown[DRAFTKINGS_PROVIDER_KEY]

    try:
        feed = collect_live_mlb_market_feed(
            now_utc=now,
            max_events=max_events,
            include_fanduel_game_odds=effective_fd_game,
            include_fanduel_player_props=effective_fd_props,
            include_draftkings=effective_dk,
            fanduel_game_collector=reliable_wrapper(
                provider_key=FANDUEL_PROVIDER_KEY,
                surface="fanduel_game_odds",
                collector=fd_game_base,
            ),
            fanduel_prop_collector=reliable_wrapper(
                provider_key=FANDUEL_PROVIDER_KEY,
                surface="fanduel_player_props",
                collector=fd_prop_base,
            ),
            draftkings_collector=reliable_wrapper(
                provider_key=DRAFTKINGS_PROVIDER_KEY,
                surface="draftkings_game_odds",
                collector=dk_base,
            ),
            draftkings_kwargs=draftkings_kwargs,
        )
    except Exception as exc:
        raise MLBProviderReliabilityError(
            "feed_error",
            f"Step19B feed assembly failed closed: {type(exc).__name__}",
        ) from exc

    terminals_by_key = _terminal_attempts(telemetry)
    for provider_key, surfaces in requested_surfaces.items():
        terminals = [
            terminals_by_key[(provider_key, surface)]
            for surface in surfaces
            if (provider_key, surface) in terminals_by_key
        ]
        _clear_failure_if_fully_healthy(
            state, provider_key, terminals=terminals
        )

    provider_rows = _provider_rows(
        requested_surfaces=requested_surfaces,
        telemetry=telemetry,
        state=state,
        now=now,
    )
    overall = _overall_status(
        live_data_present=bool(feed.get("live_market_data_present")),
        provider_rows=provider_rows,
    )
    total_retry_count = sum(int(row["retry_count"]) for row in provider_rows)
    cooldown_enforced = any(row["status"] == "cooldown" for row in provider_rows)

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "reliability_status": RELIABILITY_STATUS,
        "collection_status": overall,
        "collected_at_utc": _utc_z(now),
        "market_feed": feed,
        "provider_reliability": provider_rows,
        "attempt_telemetry": telemetry,
        "reliability_state": deepcopy(state),
        "retry_policy": {
            "max_attempts": attempts,
            "base_backoff_seconds": base_backoff,
            "max_backoff_seconds": max_backoff,
            "cooldown_seconds": cooldown,
            "max_snapshot_age_seconds": max_age,
            "clock_skew_tolerance_seconds": skew,
        },
        "retry_count": total_retry_count,
        "retry_used": total_retry_count > 0,
        "fallback_used": overall == "fallback",
        "cooldown_enforced": cooldown_enforced,
        "stale_data_fail_closed": True,
        "network_reads_only": True,
        "http_methods": ["GET"],
        "price_fabrication_used": False,
        "synthetic_game_id_used": False,
        "synthetic_player_id_used": False,
        "fuzzy_matching_used": False,
        "reliability_state_persisted_by_step19d": False,
        "production_runtime_wiring": False,
        "production_database_writes": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP19D_BASE_MAIN_SHA",
    "RELIABILITY_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "FANDUEL_PROVIDER_KEY",
    "DRAFTKINGS_PROVIDER_KEY",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_BASE_BACKOFF_SECONDS",
    "DEFAULT_MAX_BACKOFF_SECONDS",
    "DEFAULT_COOLDOWN_SECONDS",
    "DEFAULT_MAX_SNAPSHOT_AGE_SECONDS",
    "DEFAULT_CLOCK_SKEW_TOLERANCE_SECONDS",
    "MLBProviderReliabilityError",
    "MLBProviderCooldownError",
    "reliability_manifest",
    "collect_reliable_mlb_market_feed",
]
