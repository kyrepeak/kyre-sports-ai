"""WNBA Step 6M owned-feed scheduler orchestration.

Step 6M connects the frozen scheduler stack to the Step 6L production refresh
authority without changing Step 5P model semantics or Step 5Q lock semantics.
The lock/order contract is:

    local process mutex
      -> Step 5Q distributed cycle mutex
        -> Step 6L guarded DraftKings -> Kyre feed refresh
          -> frozen Step 5P pregame board cycle using provider_ids=["kyre"]

A worker that does not own the Step 5Q distributed lock never refreshes the
market feed, never runs the model, and never publishes a board.  The slate date
is resolved exactly once and is passed to both refresh and model operations so
an Arizona midnight boundary cannot split one cycle across two dates.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import os
from typing import Any

import sports_api.api.wnba_pregame_board_scheduler_distributed as step5q
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_schedule import ARIZONA_TZ
from sports_api.wnba_step6l_production_feed_refresh import (
    WNBAStep6LRefreshError,
    WNBAStep6LRefreshNotReadyError,
    get_step6l_production_refresh_status,
    refresh_step6l_owned_market_feed,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6M owned-feed scheduler orchestration"
MODEL_VERSION = "wnba_step_6m_owned_feed_scheduler_orchestration_v1"
SCHEMA_VERSION = MODEL_VERSION
KYRE_PROVIDER_ID = "kyre"


class WNBAStep6MOrchestrationError(RuntimeError):
    pass


class WNBAStep6MOrchestrationNotReadyError(WNBAStep6MOrchestrationError):
    pass


class WNBAStep6MOrchestrationUpstreamError(WNBAStep6MOrchestrationError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _target_date(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).astimezone(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("WNBA Step 6M date must use YYYY-MM-DD format.") from exc
    return text


def _positive_season(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA Step 6M season must be a positive integer.")
    return value


def _kyre_only_provider_ids(value: str | None) -> list[str]:
    if value is None:
        return [KYRE_PROVIDER_ID]
    items = [item.strip().casefold() for item in str(value).split(",") if item.strip()]
    if items != [KYRE_PROVIDER_ID]:
        raise ValueError(
            "WNBA Step 6M production orchestration permits only provider_ids=kyre; "
            "paid-provider and multi-provider overrides are disabled."
        )
    return [KYRE_PROVIDER_ID]


def get_step6m_scheduler_orchestration_status(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the network-free Step 6M scheduler-orchestration decision."""
    environment = _environment(env)
    step6l = get_step6l_production_refresh_status(env=environment)
    refresh_ready = step6l.get("production_refresh_ready") is True
    blockers = [] if refresh_ready else list(step6l.get("blocking_reasons") or [])
    if not refresh_ready and not blockers:
        blockers = ["step_6l_production_refresh_ready: Step 6L is not ready."]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6m_scheduler_orchestration_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "scheduler_cycle_ready": refresh_ready,
        "step_6l": {
            "production_refresh_ready": refresh_ready,
            "production_refresh_enabled": step6l.get("production_refresh_enabled"),
            "market_provider_mode": step6l.get("market_provider_mode"),
            "global_temporary_write_switches_off": step6l.get("global_temporary_write_switches_off"),
            "step_6k": step6l.get("step_6k"),
        },
        "blocking_reasons": blockers,
        "lock_order": [
            "step_5q_local_process_cycle_lock",
            "step_5q_distributed_cycle_lock",
            "step_6l_owned_market_feed_refresh",
            "step_5p_pregame_board_cycle",
        ],
        "semantics": {
            "status_is_network_free": True,
            "status_is_read_only": True,
            "losing_worker_refreshes_feed": False,
            "losing_worker_runs_model": False,
            "losing_worker_publishes_board": False,
            "one_resolved_arizona_slate_date_per_cycle": True,
            "kyre_owned_provider_only": True,
            "paid_provider_override_allowed": False,
            "step_5q_distributed_lock_remains_authoritative": True,
            "step_5p_model_semantics_unchanged": True,
            "new_public_mutation_route_added": False,
        },
    }


def require_step6m_scheduler_ready(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    report = get_step6m_scheduler_orchestration_status(env=env)
    if report.get("scheduler_cycle_ready") is not True:
        raise WNBAStep6MOrchestrationNotReadyError(
            "WNBA Step 6M scheduler orchestration is not ready: "
            + "; ".join(report.get("blocking_reasons") or ["unknown blocker"])
        )
    return report


def _refresh_then_run_frozen_cycle(
    *,
    target_date: str,
    season: int,
    force: bool,
    environment: Mapping[str, str],
    refresher: Callable[..., dict[str, Any]],
    cycle_runner: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Run only after Step 5Q has granted distributed ownership."""
    try:
        refresh = refresher(date=target_date, season=season, env=environment)
    except WNBAStep6LRefreshNotReadyError as exc:
        raise WNBAStep6MOrchestrationNotReadyError(str(exc)) from exc
    except WNBAStep6LRefreshError as exc:
        raise WNBAStep6MOrchestrationUpstreamError(str(exc)) from exc

    if not isinstance(refresh, dict) or refresh.get("outcome") != "refreshed":
        raise WNBAStep6MOrchestrationUpstreamError(
            "WNBA Step 6M requires a confirmed Step 6L owned-feed refresh before model execution."
        )

    result = cycle_runner(
        date=target_date,
        season=season,
        provider_ids=[KYRE_PROVIDER_ID],
        force=force,
        env=environment,
    )
    if not isinstance(result, dict):
        raise WNBAStep6MOrchestrationError("Frozen Step 5P cycle result must be an object.")
    enriched = dict(result)
    enriched["step_6m"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "resolved_slate_date": target_date,
        "provider_ids": [KYRE_PROVIDER_ID],
        "owned_feed_refresh_attempted": True,
        "owned_feed_refresh_outcome": "refreshed",
        "owned_feed_content_sha256": refresh.get("content_sha256"),
        "owned_feed_persistent_sha256": refresh.get("persistent_feed_sha256"),
        "owned_feed_offer_side_count": refresh.get("offer_side_count"),
        "paid_odds_vendor_used": False,
        "distributed_lock_owned_before_refresh": True,
    }
    return enriched


def _run_under_step5q_distributed_lock(
    *,
    target_date: str,
    season: int,
    force: bool,
    environment: Mapping[str, str],
    contention_is_error: bool,
    refresher: Callable[..., dict[str, Any]],
    cycle_runner: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    result = step5q._run_cycle_with_distributed_lock(
        lambda: _refresh_then_run_frozen_cycle(
            target_date=target_date,
            season=season,
            force=force,
            environment=environment,
            refresher=refresher,
            cycle_runner=cycle_runner,
        ),
        contention_is_error=contention_is_error,
    )
    if result.get("outcome") == "skipped_cross_process_lock":
        skipped = dict(result)
        skipped["step_6m"] = {
            "source": MODEL_SOURCE,
            "model_version": MODEL_VERSION,
            "resolved_slate_date": target_date,
            "provider_ids": [KYRE_PROVIDER_ID],
            "owned_feed_refresh_attempted": False,
            "model_cycle_attempted": False,
            "paid_odds_vendor_used": False,
            "reason": "step_5q_distributed_lock_not_owned",
        }
        return skipped
    return result


def run_step6m_background_cycle(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    refresher: Callable[..., dict[str, Any]] = refresh_step6l_owned_market_feed,
    cycle_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one background cycle with Step 5Q ownership before any refresh."""
    environment = _environment(env)
    require_step6m_scheduler_ready(env=environment)
    target_date = _target_date(date)
    target_season = _positive_season(season)
    runner = cycle_runner or step5q.run_pregame_board_cycle

    if not step5q._cycle_lock.acquire(blocking=False):
        raise step5q.WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 6M scheduler cycle is already running in this process."
        )
    started = step5q._utc_now_iso()
    with step5q._worker_lock:
        step5q._worker_state["last_cycle_started_at_utc"] = started
        step5q._worker_state["last_error"] = None
    try:
        result = _run_under_step5q_distributed_lock(
            target_date=target_date,
            season=target_season,
            force=False,
            environment=environment,
            contention_is_error=False,
            refresher=refresher,
            cycle_runner=runner,
        )
        with step5q._worker_lock:
            step5q._worker_state["last_cycle_outcome"] = result.get("outcome")
            publication = result.get("publication") or result.get("current_publication") or {}
            step5q._worker_state["last_publication_id"] = publication.get("publication_id")
        return result
    except Exception as exc:
        with step5q._worker_lock:
            step5q._worker_state["last_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        with step5q._worker_lock:
            step5q._worker_state["last_cycle_completed_at_utc"] = step5q._utc_now_iso()
        step5q._cycle_lock.release()


def run_step6m_manual_cycle(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    provider_ids: str | None = None,
    force: bool = True,
    env: Mapping[str, str] | None = None,
    refresher: Callable[..., dict[str, Any]] = refresh_step6l_owned_market_feed,
    cycle_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the existing manual refresh contract through the Step 6M pipeline."""
    environment = _environment(env)
    require_step6m_scheduler_ready(env=environment)
    _kyre_only_provider_ids(provider_ids)
    if not isinstance(force, bool):
        raise ValueError("WNBA Step 6M force must be boolean.")
    target_date = _target_date(date)
    target_season = _positive_season(season)
    runner = cycle_runner or step5q.run_pregame_board_cycle

    if not step5q._cycle_lock.acquire(blocking=False):
        raise step5q.WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 6M scheduler cycle is already running in this process."
        )
    try:
        return _run_under_step5q_distributed_lock(
            target_date=target_date,
            season=target_season,
            force=force,
            environment=environment,
            contention_is_error=True,
            refresher=refresher,
            cycle_runner=runner,
        )
    finally:
        step5q._cycle_lock.release()


def build_step6m_scheduler_orchestration_plan(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    status = get_step6m_scheduler_orchestration_status(env=env)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6m_scheduler_orchestration_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "scheduler_cycle_ready": status.get("scheduler_cycle_ready"),
        "steps": [
            {"order": 1, "action": "require_step_6m_readiness", "complete": status.get("scheduler_cycle_ready") is True},
            {"order": 2, "action": "acquire_step_5q_local_process_cycle_lock", "complete": False},
            {"order": 3, "action": "acquire_step_5q_distributed_cycle_lock", "complete": False},
            {"order": 4, "action": "refresh_kyre_owned_feed_through_step_6l", "complete": False},
            {"order": 5, "action": "run_frozen_step_5p_cycle_with_provider_ids_kyre", "complete": False},
            {"order": 6, "action": "release_step_5q_distributed_and_local_locks", "complete": False},
        ],
        "blocking_reasons": status.get("blocking_reasons"),
        "safety": {
            "distributed_lock_precedes_network_refresh": True,
            "distributed_lock_precedes_model_execution": True,
            "losing_worker_does_no_refresh_or_model_work": True,
            "provider_override_is_kyre_only": True,
            "paid_provider_fallback_allowed": False,
            "same_resolved_date_used_for_refresh_and_model": True,
            "frozen_step_5p_model_semantics_preserved": True,
            "frozen_step_5q_lock_semantics_preserved": True,
        },
    }
