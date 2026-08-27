"""WNBA Step 6L guarded production refresh authority for the Kyre-owned feed.

Step 6K deliberately requires every temporary Step 6J write switch to remain
OFF. Step 6L preserves that invariant while defining the production-safe way to
refresh the owned WNBA market feed after scheduler activation:

1. the real process environment must keep Step 6J canary/direct/reconciled
   switches OFF;
2. Step 6K must already authorize scheduler work;
3. Step 6C market-provider mode must be explicitly ``kyre`` so no paid odds
   provider can enter the Step 5O failover chain;
4. an additional Step 6L production-refresh switch must be explicitly enabled;
5. only after those checks pass, Step 6L creates a private copy of the
   environment and enables Step 6D + Step 6I inside that copy for exactly one
   reconciled DraftKings -> Kyre durable-feed sync;
6. the caller's environment is never mutated.

This module does not start the scheduler and exposes no public mutation route.
The actual Step 6L refresh function performs network GETs and one Step 6C atomic
feed write only when explicitly invoked after all gates are green. CI tests use
an injected sync function and never contact DraftKings.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_reconciled_direct_sync import sync_reconciled_draftkings_to_kyre_feed
from sports_api.wnba_schedule import ARIZONA_TZ
from sports_api.wnba_step6k_activation_preflight import get_step6k_activation_preflight

MODEL_SOURCE = "Kyre Sports API WNBA Step 6L guarded production feed refresh"
MODEL_VERSION = "wnba_step_6l_guarded_production_feed_refresh_v1"
SCHEMA_VERSION = MODEL_VERSION

PRODUCTION_REFRESH_ENABLED_ENV = "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED"
REFRESH_LOCK_PATH_ENV = "WNBA_STEP6L_REFRESH_LOCK_PATH"
DEFAULT_REFRESH_LOCK_PATH = "/var/lib/kyre-sports-api/.wnba-step6l-refresh.lock"

MARKET_PROVIDER_MODE_ENV = "WNBA_MARKET_PROVIDER_MODE"
KYRE_PROVIDER_MODE = "kyre"
DIRECT_SYNC_ENABLED_ENV = "WNBA_KYRE_DIRECT_SYNC_ENABLED"
DIRECT_SYNC_PROVIDER_ENV = "WNBA_KYRE_DIRECT_SYNC_PROVIDER"
DIRECT_SYNC_PROVIDER = "draftkings"
RECONCILED_SYNC_ENABLED_ENV = "WNBA_KYRE_RECONCILED_SYNC_ENABLED"
CANARY_ENABLED_ENV = "WNBA_STEP6J_CANARY_ENABLED"


class WNBAStep6LRefreshError(RuntimeError):
    pass


class WNBAStep6LRefreshNotReadyError(WNBAStep6LRefreshError):
    pass


class WNBAStep6LRefreshBusyError(WNBAStep6LRefreshNotReadyError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _truthy(environment: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = environment.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_lock_path(environment: Mapping[str, str]) -> Path:
    raw = _clean(environment.get(REFRESH_LOCK_PATH_ENV)) or DEFAULT_REFRESH_LOCK_PATH
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise WNBAStep6LRefreshNotReadyError(f"{REFRESH_LOCK_PATH_ENV} must be an absolute path.")
    return path


def _target_date(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).astimezone(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise WNBAStep6LRefreshNotReadyError("WNBA Step 6L date must use YYYY-MM-DD format.") from exc
    return text


def _positive_season(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise WNBAStep6LRefreshNotReadyError("WNBA Step 6L season must be a positive integer.")
    return value


def _global_temporary_switches_off(environment: Mapping[str, str]) -> bool:
    return (
        not _truthy(environment, CANARY_ENABLED_ENV, False)
        and not _truthy(environment, DIRECT_SYNC_ENABLED_ENV, False)
        and not _truthy(environment, RECONCILED_SYNC_ENABLED_ENV, False)
    )


def get_step6l_production_refresh_status(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the network-free Step 6L production-refresh decision."""
    environment = _environment(env)
    step6k = get_step6k_activation_preflight(env=environment)
    enabled = _truthy(environment, PRODUCTION_REFRESH_ENABLED_ENV, False)
    market_mode = (_clean(environment.get(MARKET_PROVIDER_MODE_ENV)) or "").casefold() or None
    temporary_switches_off = _global_temporary_switches_off(environment)
    step6k_authorized = step6k.get("scheduler_authorized") is True

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str) -> None:
        row = {"name": name, "required": True, "passed": bool(passed), "detail": detail}
        checks.append(row)
        if not passed:
            blockers.append(f"{name}: {detail}")

    add(
        "step_6l_explicit_refresh_enablement",
        enabled,
        f"{PRODUCTION_REFRESH_ENABLED_ENV}=true is present."
        if enabled
        else f"{PRODUCTION_REFRESH_ENABLED_ENV}=true is required before production refreshes.",
    )
    add(
        "step_6k_scheduler_authorized",
        step6k_authorized,
        "Step 6K authorizes scheduler work."
        if step6k_authorized
        else "Step 6K has not authorized scheduler work yet.",
    )
    add(
        "kyre_owned_market_mode_only",
        market_mode == KYRE_PROVIDER_MODE,
        f"{MARKET_PROVIDER_MODE_ENV}=kyre prevents paid-provider failover."
        if market_mode == KYRE_PROVIDER_MODE
        else f"{MARKET_PROVIDER_MODE_ENV}=kyre is required; current mode is {market_mode or 'unset'}.",
    )
    add(
        "global_step_6j_write_switches_off",
        temporary_switches_off,
        "Global Step 6J canary/direct/reconciled switches remain OFF."
        if temporary_switches_off
        else "Global Step 6J canary/direct/reconciled switches must all remain OFF.",
    )
    try:
        lock_path = _resolve_lock_path(environment)
        lock_path_ready = True
        lock_path_error = None
    except WNBAStep6LRefreshNotReadyError as exc:
        lock_path = None
        lock_path_ready = False
        lock_path_error = str(exc)
    add(
        "refresh_lock_path_valid",
        lock_path_ready,
        "Step 6L cross-process refresh lock path is absolute."
        if lock_path_ready
        else lock_path_error or "Step 6L refresh lock path is invalid.",
    )

    ready = not blockers
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6l_production_refresh_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "production_refresh_enabled": enabled,
        "production_refresh_ready": ready,
        "market_provider_mode": market_mode,
        "global_temporary_write_switches_off": temporary_switches_off,
        "refresh_lock_path": str(lock_path) if lock_path is not None else None,
        "step_6k": {
            "phase": step6k.get("phase"),
            "scheduler_authorized": step6k_authorized,
            "activation_checkpoint_sha256": step6k.get("activation_checkpoint_sha256"),
            "step6j_verified": step6k.get("step6j_verified"),
        },
        "checks": checks,
        "blocking_reasons": blockers,
        "semantics": {
            "status_is_network_free": True,
            "status_is_read_only": True,
            "global_environment_mutated": False,
            "global_step_6j_switches_must_remain_off": True,
            "step_6i_is_only_durable_write_authority": True,
            "draftkings_transport_is_get_only": True,
            "paid_odds_vendor_allowed": False,
            "kyre_owned_feed_is_only_step_5o_market_source": True,
            "scheduler_started_by_step_6l": False,
            "monte_carlo_run_by_status": False,
            "wager_action_performed": False,
        },
    }


def _scoped_step6i_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Return a private single-call Step 6I environment without mutating input."""
    scoped = {str(key): str(value) for key, value in environment.items()}
    scoped[MARKET_PROVIDER_MODE_ENV] = KYRE_PROVIDER_MODE
    scoped[CANARY_ENABLED_ENV] = "false"
    scoped[DIRECT_SYNC_ENABLED_ENV] = "true"
    scoped[DIRECT_SYNC_PROVIDER_ENV] = DIRECT_SYNC_PROVIDER
    scoped[RECONCILED_SYNC_ENABLED_ENV] = "true"
    return scoped


def refresh_step6l_owned_market_feed(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    syncer: Callable[..., dict[str, Any]] = sync_reconciled_draftkings_to_kyre_feed,
) -> dict[str, Any]:
    """Perform one Step 6K-authorized, lock-serialized Step 6I durable refresh."""
    environment = _environment(env)
    before = {str(key): str(value) for key, value in environment.items()}
    status = get_step6l_production_refresh_status(env=environment)
    if status.get("production_refresh_ready") is not True:
        raise WNBAStep6LRefreshNotReadyError(
            "WNBA Step 6L production refresh is not ready: "
            + "; ".join(status.get("blocking_reasons") or ["unknown blocker"])
        )

    target_date = _target_date(date)
    target_season = _positive_season(season)
    lock_path = _resolve_lock_path(environment)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WNBAStep6LRefreshBusyError(
                "WNBA Step 6L production refresh is already owned by another process."
            ) from exc
        try:
            # Re-check after acquiring the cross-process lock to close the gap
            # between readiness evaluation and the actual network/write action.
            rechecked = get_step6l_production_refresh_status(env=environment)
            if rechecked.get("production_refresh_ready") is not True:
                raise WNBAStep6LRefreshNotReadyError(
                    "WNBA Step 6L production refresh became blocked before write: "
                    + "; ".join(rechecked.get("blocking_reasons") or ["unknown blocker"])
                )

            scoped_env = _scoped_step6i_environment(environment)
            result = syncer(
                date=target_date,
                season=target_season,
                env=scoped_env,
            )
            if not isinstance(result, dict):
                raise WNBAStep6LRefreshError("Step 6I refresh result must be an object.")
            if result.get("synced") is not True or result.get("feed_write_performed") is not True:
                raise WNBAStep6LRefreshError("Step 6I did not confirm a durable reconciled feed write.")
            storage = result.get("storage") if isinstance(result.get("storage"), Mapping) else {}
            content_sha = _clean(storage.get("content_sha256"))
            if not content_sha:
                raise WNBAStep6LRefreshError("Step 6I durable write did not return a content SHA-256.")
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    after = {str(key): str(value) for key, value in environment.items()}
    if before != after:
        raise WNBAStep6LRefreshError("Step 6L detected mutation of the caller environment.")

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6l_production_refresh_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "outcome": "refreshed",
        "date": target_date,
        "season": target_season,
        "provider_id": result.get("provider_id"),
        "feed_write_performed": True,
        "content_sha256": content_sha,
        "persistent_feed_sha256": result.get("persistent_feed_sha256"),
        "snapshot_sha256": result.get("snapshot_sha256"),
        "reconciliation_fingerprint_sha256": result.get("reconciliation_fingerprint_sha256"),
        "offer_side_count": result.get("offer_side_count"),
        "step6h_ready": result.get("step6h_ready"),
        "step6k_activation_checkpoint_sha256": (status.get("step_6k") or {}).get("activation_checkpoint_sha256"),
        "global_temporary_write_switches_off_after_refresh": _global_temporary_switches_off(environment),
        "global_environment_mutated": False,
        "paid_odds_vendor_used": False,
        "wager_action_performed": False,
    }


def build_step6l_production_refresh_plan(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    status = get_step6l_production_refresh_status(env=env)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6l_production_refresh_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "production_refresh_ready": status.get("production_refresh_ready"),
        "steps": [
            {
                "order": 1,
                "action": "complete_and_verify_step_6j_then_authorize_step_6k",
                "complete": (status.get("step_6k") or {}).get("scheduler_authorized") is True,
            },
            {
                "order": 2,
                "action": "force_step_5o_to_kyre_owned_market_mode",
                "requirement": f"{MARKET_PROVIDER_MODE_ENV}=kyre",
                "complete": status.get("market_provider_mode") == KYRE_PROVIDER_MODE,
            },
            {
                "order": 3,
                "action": "keep_all_step_6j_temporary_write_switches_off_globally",
                "complete": status.get("global_temporary_write_switches_off") is True,
            },
            {
                "order": 4,
                "action": "enable_step_6l_production_refresh_authority",
                "requirement": f"{PRODUCTION_REFRESH_ENABLED_ENV}=true",
                "complete": status.get("production_refresh_enabled") is True,
            },
            {
                "order": 5,
                "action": "run_one_lock_serialized_scoped_step_6i_refresh_before_each_scheduler_collection",
                "complete": False,
                "note": "Scheduler wiring is intentionally deferred to the next step; Step 6L defines and tests the authority only.",
            },
        ],
        "blocking_reasons": status.get("blocking_reasons"),
        "safety": {
            "paid_odds_vendor_allowed": False,
            "sports_game_odds_fallback_allowed": False,
            "global_step_6j_switches_remain_off": True,
            "scheduler_wiring_performed_in_step_6l": False,
            "public_mutation_route_added": False,
        },
    }
