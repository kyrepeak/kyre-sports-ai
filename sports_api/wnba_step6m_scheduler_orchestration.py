"""WNBA Step 6M owned-feed scheduler orchestration.

Step 6M connects the frozen scheduler stack to the Step 6L production refresh
authority without changing Step 5P model semantics or Step 5Q lock semantics.

The production ordering contract is intentionally stricter than the first
Step-6M draft:

    local process mutex
      -> Step 5Q distributed cycle mutex
        -> frozen Step 5P due/slate/provider-spacing guards
          -> Step 6L guarded DraftKings -> Kyre feed refresh
            -> frozen Step 5O Kyre-only provider collection
              -> frozen Step 5P model/publication work

The Step 6L refresh is injected at Step 5P's existing ``failover_collector``
hook.  Therefore a cycle that is not due, has no playable official slate, or is
blocked by Step 5P's provider-spacing guard performs no DraftKings refresh.
A worker that does not own the Step 5Q distributed lock performs no refresh,
provider collection, model work, or publication.

The slate date is resolved exactly once by Step 6M and passed into Step 5P;
Step 5P passes that same date into the injected provider hook, closing the
Arizona-midnight split-date edge case without moving any frozen Step 5P guards.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import os
from typing import Any

import sports_api.api.wnba_pregame_board_scheduler_distributed as step5q
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_prop_feed_failover import collect_failover_line_board
from sports_api.wnba_schedule import ARIZONA_TZ
from sports_api.wnba_step6l_production_feed_refresh import (
    WNBAStep6LRefreshError,
    WNBAStep6LRefreshNotReadyError,
    get_step6l_production_refresh_status,
    refresh_step6l_owned_market_feed,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6M owned-feed scheduler orchestration"
MODEL_VERSION = "wnba_step_6m_owned_feed_scheduler_orchestration_v2"
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


def _provider_sequence(value: Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    return [str(item).strip().casefold() for item in value if str(item).strip()]


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
        "execution_order": [
            "step_5q_local_process_cycle_lock",
            "step_5q_distributed_cycle_lock",
            "frozen_step_5p_due_official_slate_and_provider_spacing_guards",
            "step_6l_owned_market_feed_refresh_at_step_5p_provider_collection",
            "frozen_step_5o_kyre_owned_feed_collection",
            "frozen_step_5p_model_and_publication",
        ],
        "semantics": {
            "status_is_network_free": True,
            "status_is_read_only": True,
            "losing_worker_refreshes_feed": False,
            "losing_worker_runs_model": False,
            "losing_worker_publishes_board": False,
            "not_due_cycle_refreshes_feed": False,
            "empty_or_closed_official_slate_refreshes_feed": False,
            "provider_spacing_guarded_cycle_refreshes_feed": False,
            "refresh_injected_only_at_step_5p_provider_collection": True,
            "one_resolved_arizona_slate_date_per_cycle": True,
            "kyre_owned_provider_only": True,
            "paid_provider_override_allowed": False,
            "step_5q_distributed_lock_remains_authoritative": True,
            "step_5p_pre_provider_guards_remain_authoritative": True,
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


def _refresh_at_provider_collection(
    *,
    target_date: str,
    season: int,
    environment: Mapping[str, str],
    refresher: Callable[..., dict[str, Any]],
    base_failover_collector: Callable[..., dict[str, Any]],
    refresh_evidence: dict[str, Any],
) -> Callable[..., dict[str, Any]]:
    """Return a Step-5P failover hook that refreshes immediately before Step 5O."""

    def refreshing_failover_collector(
        provider_ids: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if _provider_sequence(provider_ids) != [KYRE_PROVIDER_ID]:
            raise WNBAStep6MOrchestrationError(
                "WNBA Step 6M injected provider collection requires provider_ids=['kyre']."
            )

        hook_date = str(kwargs.get("date") or "").strip()
        hook_season = kwargs.get("season")
        if hook_date != target_date or hook_season != season:
            raise WNBAStep6MOrchestrationError(
                "WNBA Step 6M detected a slate date/season mismatch at the Step 5P provider hook."
            )

        try:
            refresh = refresher(date=target_date, season=season, env=environment)
        except WNBAStep6LRefreshNotReadyError as exc:
            raise WNBAStep6MOrchestrationNotReadyError(str(exc)) from exc
        except WNBAStep6LRefreshError as exc:
            raise WNBAStep6MOrchestrationUpstreamError(str(exc)) from exc

        if not isinstance(refresh, dict) or refresh.get("outcome") != "refreshed":
            raise WNBAStep6MOrchestrationUpstreamError(
                "WNBA Step 6M requires a confirmed Step 6L owned-feed refresh before Step 5O collection."
            )

        refresh_evidence.update(
            {
                "attempted": True,
                "outcome": "refreshed",
                "content_sha256": refresh.get("content_sha256"),
                "persistent_feed_sha256": refresh.get("persistent_feed_sha256"),
                "offer_side_count": refresh.get("offer_side_count"),
            }
        )

        forwarded = dict(kwargs)
        forwarded["date"] = target_date
        forwarded["season"] = season
        forwarded["env"] = environment
        return base_failover_collector([KYRE_PROVIDER_ID], **forwarded)

    return refreshing_failover_collector


def _run_frozen_cycle_with_scoped_refresh(
    *,
    target_date: str,
    season: int,
    force: bool,
    environment: Mapping[str, str],
    refresher: Callable[..., dict[str, Any]],
    cycle_runner: Callable[..., dict[str, Any]],
    base_failover_collector: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Run frozen Step 5P and refresh only if Step 5P reaches provider collection."""
    refresh_evidence: dict[str, Any] = {
        "attempted": False,
        "outcome": None,
        "content_sha256": None,
        "persistent_feed_sha256": None,
        "offer_side_count": None,
    }
    refreshing_failover_collector = _refresh_at_provider_collection(
        target_date=target_date,
        season=season,
        environment=environment,
        refresher=refresher,
        base_failover_collector=base_failover_collector,
        refresh_evidence=refresh_evidence,
    )

    result = cycle_runner(
        date=target_date,
        season=season,
        provider_ids=[KYRE_PROVIDER_ID],
        force=force,
        env=environment,
        failover_collector=refreshing_failover_collector,
    )
    if not isinstance(result, dict):
        raise WNBAStep6MOrchestrationError("Frozen Step 5P cycle result must be an object.")

    enriched = dict(result)
    enriched["step_6m"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "resolved_slate_date": target_date,
        "provider_ids": [KYRE_PROVIDER_ID],
        "frozen_step_5p_cycle_entered": True,
        "provider_collection_attempted": result.get("provider_collection_attempted") is True,
        "board_rebuild_attempted": result.get("board_rebuild_attempted") is True,
        "owned_feed_refresh_attempted": refresh_evidence["attempted"],
        "owned_feed_refresh_outcome": refresh_evidence["outcome"],
        "owned_feed_content_sha256": refresh_evidence["content_sha256"],
        "owned_feed_persistent_sha256": refresh_evidence["persistent_feed_sha256"],
        "owned_feed_offer_side_count": refresh_evidence["offer_side_count"],
        "refresh_injected_at_step_5p_provider_collection": True,
        "step_5p_pre_provider_guards_preserved": True,
        "paid_odds_vendor_used": False,
        "distributed_lock_owned_before_provider_refresh": True,
    }
    if not refresh_evidence["attempted"]:
        enriched["step_6m"]["owned_feed_refresh_skip_reason"] = (
            "frozen_step_5p_did_not_enter_provider_collection"
        )
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
    base_failover_collector: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    result = step5q._run_cycle_with_distributed_lock(
        lambda: _run_frozen_cycle_with_scoped_refresh(
            target_date=target_date,
            season=season,
            force=force,
            environment=environment,
            refresher=refresher,
            cycle_runner=cycle_runner,
            base_failover_collector=base_failover_collector,
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
            "provider_collection_attempted": False,
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
    base_failover_collector: Callable[..., dict[str, Any]] = collect_failover_line_board,
) -> dict[str, Any]:
    """Run one background cycle with Step 5Q ownership before any work."""
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
            base_failover_collector=base_failover_collector,
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
    base_failover_collector: Callable[..., dict[str, Any]] = collect_failover_line_board,
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
            base_failover_collector=base_failover_collector,
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
            {
                "order": 4,
                "action": "enter_frozen_step_5p_due_slate_and_provider_spacing_guards",
                "complete": False,
                "note": "Not-due, empty/closed-slate, and provider-spacing outcomes do not refresh DraftKings.",
            },
            {
                "order": 5,
                "action": "refresh_kyre_owned_feed_through_step_6l_only_if_step_5p_requests_provider_collection",
                "complete": False,
            },
            {"order": 6, "action": "collect_frozen_step_5o_with_provider_ids_kyre", "complete": False},
            {"order": 7, "action": "continue_frozen_step_5p_model_and_publication", "complete": False},
            {"order": 8, "action": "release_step_5q_distributed_and_local_locks", "complete": False},
        ],
        "blocking_reasons": status.get("blocking_reasons"),
        "safety": {
            "distributed_lock_precedes_network_refresh": True,
            "distributed_lock_precedes_model_execution": True,
            "step_5p_due_guard_precedes_network_refresh": True,
            "official_slate_guard_precedes_network_refresh": True,
            "provider_spacing_guard_precedes_network_refresh": True,
            "not_due_cycle_refreshes_feed": False,
            "empty_or_closed_official_slate_refreshes_feed": False,
            "provider_spacing_guarded_cycle_refreshes_feed": False,
            "losing_worker_does_no_refresh_or_model_work": True,
            "provider_override_is_kyre_only": True,
            "paid_provider_fallback_allowed": False,
            "same_resolved_date_used_for_step_5p_and_provider_refresh": True,
            "frozen_step_5p_model_semantics_preserved": True,
            "frozen_step_5q_lock_semantics_preserved": True,
        },
    }
