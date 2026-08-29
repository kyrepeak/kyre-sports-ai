"""Step 19C compatibility for legitimate pregame Step-8 readiness holds.

The frozen Step-12B assembly correctly refuses to fabricate a projection when all
current exact-line targets fail a certified Step-8 readiness gate.  Its legacy
behavior, however, raises a terminal-looking NotReady exception before Step-11E
can classify the condition as market/data readiness.

This additive bridge preserves every underlying Step-8 blocker.  It only converts
that one all-target-not-ready outcome into the same caller-visible
``market_not_ready`` semantics used elsewhere by the frozen controller.  No
projection is synthesized, no availability gate is relaxed, and no write/wager
switch is enabled.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step12b_live_runtime_assembly as step12b

MODEL_VERSION = "wnba_step19c_market_not_ready_compat_v1"
_ALL_STEP8_NOT_READY_MESSAGE = (
    "Step 12B could not build any certified converged Step-8 distribution "
    "for current exact-line markets."
)
_ORIGINAL_RUN = step12b.run_step12b_live_runtime_job


def _error_detail(exc: Exception) -> dict[str, str]:
    return {
        "error_type": type(exc).__name__,
        "error_message": " ".join(str(exc).split())[:500],
    }


def _recording_fetcher(
    fetcher: Callable[..., Mapping[str, Any]],
    calls: list[dict[str, Any]],
    successes: list[dict[str, Any]],
) -> Callable[..., Mapping[str, Any]]:
    def wrapped(**kwargs: Any) -> Mapping[str, Any]:
        row: dict[str, Any] = {"ok": False}
        calls.append(row)
        try:
            result = fetcher(**kwargs)
        except Exception as exc:
            row["error"] = _error_detail(exc)
            raise
        row["ok"] = True
        successes.append(deepcopy(dict(result)))
        return result

    return wrapped


def _discovery_audit(
    *,
    provider: str,
    bridge: Mapping[str, Any],
    calls: list[dict[str, Any]],
    attempt_limit: int,
) -> dict[str, Any]:
    records = step12b._payload_records(bridge, provider)
    return {
        "provider": provider,
        "attempt_limit": attempt_limit,
        "attempts_executed": len(calls),
        "retryable_failures": sum(1 for row in calls if row.get("ok") is not True),
        "record_count": len(records),
        "bridge_content_sha256": bridge.get("provider_bridge_content_sha256"),
        "errors": [deepcopy(row["error"]) for row in calls if isinstance(row.get("error"), Mapping)],
    }


def _controlled_tick(
    *,
    normalized: Mapping[str, Any],
    controller_policy: Mapping[str, Any],
) -> dict[str, Any]:
    evaluated = normalized["evaluated_at"]
    policy = step11e._policy(
        controller_policy.get(
            "refresh_interval_seconds", step11e.DEFAULT_REFRESH_INTERVAL_SECONDS
        ),
        controller_policy.get("failure_threshold", step11e.DEFAULT_FAILURE_THRESHOLD),
        controller_policy.get(
            "circuit_cooldown_seconds", step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS
        ),
    )
    previous_state = normalized["previous_state"]
    previous = (
        None
        if previous_state is None
        else step11e._verify_previous_state(
            previous_state,
            current_policy=policy,
            evaluated_at=evaluated,
        )
    )

    if previous is None:
        prior_failures = 0
        prior_circuit = "closed"
        next_due = evaluated
        open_until = None
        last_cycle = None
        last_success = None
        last_failure = None
        last_shadow_hash = None
        last_step10_hash = None
        last_step9_hash = None
    else:
        prior_failures = int(previous["consecutive_failure_count"])
        prior_circuit = str(previous["circuit_state"])
        next_due = previous["_next_due"]
        open_until = previous["_open_until"]
        last_cycle = previous["_last_cycle"]
        last_success = previous["_last_success"]
        last_failure = previous["_last_failure"]
        last_shadow_hash = previous.get("last_shadow_board_content_sha256")
        last_step10_hash = previous.get("last_step10_pipeline_content_sha256")
        last_step9_hash = previous.get("last_step9_ranking_content_sha256")

    probe_mode = prior_circuit == "open" and open_until is not None and evaluated >= open_until
    if prior_circuit == "open" and open_until is not None and evaluated < open_until:
        cycle_due = False
        skip_reason = "circuit_open_cooldown"
    elif prior_circuit == "closed" and evaluated < next_due:
        cycle_due = False
        skip_reason = "refresh_not_due"
    else:
        cycle_due = True
        skip_reason = None

    cycle_started = last_cycle
    cycle_error: dict[str, str] | None = None
    if not cycle_due:
        if skip_reason == "circuit_open_cooldown":
            status = "circuit_open"
            health = "blocked"
            circuit = "open"
            failures = prior_failures
            new_open_until = open_until
            new_next_due = open_until or next_due
        else:
            status = "not_due"
            health = "waiting"
            circuit = prior_circuit
            failures = prior_failures
            new_open_until = open_until
            new_next_due = next_due
        cycle_outcome = "not_executed"
    else:
        cycle_started = evaluated
        status = "market_not_ready"
        health = "market_not_ready"
        cycle_outcome = "market_board_not_ready"
        cycle_error = {
            "error_type": "WNBAStep8ProjectionHandoffNotReadyError",
            "error_message": (
                "All current exact-line projection targets are held by certified "
                "Step-8 pregame readiness gates; no projection was fabricated."
            ),
        }
        circuit = "closed"
        failures = 0
        new_open_until = None
        new_next_due = evaluated + timedelta(seconds=policy["refresh_interval_seconds"])

    state = step11e._make_state(
        policy=policy,
        circuit_state=circuit,
        consecutive_failure_count=failures,
        last_tick_at=evaluated,
        last_cycle_started_at=cycle_started,
        last_success_at=last_success,
        last_failure_at=last_failure,
        next_refresh_due_at=new_next_due,
        circuit_open_until=new_open_until,
        last_shadow_hash=last_shadow_hash,
        last_step10_hash=last_step10_hash,
        last_step9_hash=last_step9_hash,
    )
    tick = {
        "data_type": "wnba_step11e_controlled_automation_tick",
        "schema_version": step11e.SCHEMA_VERSION,
        "source": step11e.SOURCE,
        "model_version": step11e.MODEL_VERSION,
        "release_id": step11e.RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "status": status,
        "health": health,
        "execution": {
            "cycle_due": cycle_due,
            "cycle_executed": cycle_due,
            "cycle_outcome": cycle_outcome,
            "skip_reason": skip_reason,
            "half_open_probe": probe_mode,
            "provider_attempt_limit": int(
                controller_policy.get("provider_attempts", step11d.DEFAULT_PROVIDER_ATTEMPTS)
            ),
            "error": cycle_error,
            "shadow_board_content_sha256": None,
            "step10_pipeline_content_sha256": None,
            "step9_ranking_content_sha256": None,
        },
        "circuit_breaker": {
            "state_before": prior_circuit,
            "state_after": circuit,
            "consecutive_failures_before": prior_failures,
            "consecutive_failures_after": failures,
            "failure_threshold": policy["failure_threshold"],
            "cooldown_seconds": policy["circuit_cooldown_seconds"],
            "open_until_utc": new_open_until.isoformat() if new_open_until else None,
        },
        "automation_state": state,
        "shadow_board_result": None,
        "lineage": {
            "step11_release_id": step11e.release.RELEASE_ID,
            "step11a_frozen_sha": step11e.release.STEP11A_FROZEN_SHA,
            "step11b_frozen_sha": step11e.release.STEP11B_FROZEN_SHA,
            "step11c_frozen_sha": step11e.release.STEP11C_FROZEN_SHA,
            "step11d_frozen_sha": step11e.release.STEP11D_FROZEN_SHA,
            "step10_frozen_sha": step11e.release.STEP10_FROZEN_SHA,
            "step9_frozen_sha": step11e.release.STEP9_FROZEN_SHA,
            "step8_frozen_sha": step11e.release.STEP8_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "caller_driven_tick_only": True,
            "external_scheduler_required_for_repeated_ticks": True,
            "background_scheduler_started": False,
            "sleep_performed": False,
            "sportsbook_network_fetch_attempted": cycle_due,
            "sportsbook_http_methods": ["GET"] if cycle_due else [],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "state_persisted": False,
            "caller_must_resupply_state": True,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
        },
    }
    hash_surface = {
        key: value
        for key, value in tick.items()
        if key not in {"generated_at_utc", "shadow_board_result", "controller_content_sha256"}
    }
    tick["controller_content_sha256"] = step11e._canonical_hash(hash_surface)
    return tick


def _market_not_ready_response(
    *,
    normalized: Mapping[str, Any],
    controller_policy: Mapping[str, Any],
    dk_bridge: Mapping[str, Any],
    fd_bridge: Mapping[str, Any],
    dk_calls: list[dict[str, Any]],
    fd_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    provider_attempts = int(
        controller_policy.get("provider_attempts", step11d.DEFAULT_PROVIDER_ATTEMPTS)
    )
    dk_records = step12b._payload_records(dk_bridge, draftkings.PROVIDER)
    fd_records = step12b._payload_records(fd_bridge, fanduel.PROVIDER)
    targets, exact_groups = step12b._exact_multibook_targets(dk_records, fd_records)
    tick = _controlled_tick(normalized=normalized, controller_policy=controller_policy)
    state = tick["automation_state"]
    skipped_targets = [
        {
            "game_id": game_id,
            "player_id": player_id,
            "reason": "certified_step8_candidate_not_ready",
            "error_type": "WNBAStep8ProjectionHandoffNotReadyError",
        }
        for game_id, player_id in targets
    ]
    step12a_compat = {
        "data_type": "wnba_step12a_shadow_runner_response",
        "schema_version": step12b.step12a.SCHEMA_VERSION,
        "status": tick["status"],
        "health": tick["health"],
        "automation_state": deepcopy(state),
        "shadow_board_result": None,
        "step11e_tick": tick,
        "compatibility_short_circuit": "all_certified_step8_targets_not_ready",
    }
    response = {
        "data_type": "wnba_step12b_live_runtime_assembly_response",
        "schema_version": step12b.SCHEMA_VERSION,
        "source": step12b.SOURCE,
        "model_version": step12b.MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": tick["status"],
        "health": tick["health"],
        "slate_date": normalized["slate_date"],
        "provider_discovery": {
            "sportsbooks": [draftkings.PROVIDER, fanduel.PROVIDER],
            "draftkings": _discovery_audit(
                provider=draftkings.PROVIDER,
                bridge=dk_bridge,
                calls=dk_calls,
                attempt_limit=provider_attempts,
            ),
            "fanduel": _discovery_audit(
                provider=fanduel.PROVIDER,
                bridge=fd_bridge,
                calls=fd_calls,
                attempt_limit=provider_attempts,
            ),
            "sportsbook_network_fetches_reused_in_step11_tick": True,
            "duplicate_sportsbook_discovery_performed": False,
            "market_readiness_short_circuit": True,
        },
        "market_overlap": {
            "draftkings_record_count": len(dk_records),
            "fanduel_record_count": len(fd_records),
            "exact_line_multibook_group_count": len(exact_groups),
            "exact_line_multibook_groups": exact_groups,
            "unique_projection_target_count": len(targets),
            "different_lines_blended": False,
        },
        "projection_assembly": {
            "requested_target_count": len(targets),
            "built_target_count": 0,
            "skipped_target_count": len(skipped_targets),
            "simulations_per_built_target": step12b.CERTIFIED_SIMULATIONS,
            "batch_size": step12b.CERTIFIED_BATCH_SIZE,
            "targets": [],
            "skipped_targets": skipped_targets,
            "all_built_distributions_converged": True,
            "market_readiness_short_circuit": True,
        },
        "runtime_summary": {
            "step8_distribution_count": 0,
            "step11_cycle_executed": tick["execution"]["cycle_executed"],
            "qualified_prop_count": 0,
            "top_card_count": 0,
        },
        "step12a_result": step12a_compat,
        "lineage": {
            "step12a_frozen_sha": step12b.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": step12b.STEP11E_FROZEN_SHA,
            "step8_frozen_sha": step12b.STEP8_FROZEN_SHA,
            "step12a_runner_content_sha256": None,
            "draftkings_bridge_content_sha256": dk_bridge.get("provider_bridge_content_sha256"),
            "fanduel_bridge_content_sha256": fd_bridge.get("provider_bridge_content_sha256"),
            "step8_result_content_sha256": [],
            "step19c_market_not_ready_compat": MODEL_VERSION,
        },
        "guardrails": {
            "shadow_only": True,
            "caller_driven_job_only": True,
            "market_driven_projection_target_discovery": True,
            "official_wnba_identity_reconciliation_required": True,
            "exact_line_multibook_overlap_required": True,
            "frozen_step8_projection_generated": False,
            "five_million_simulations_required": True,
            "sportsbook_network_fetch_performed": True,
            "sportsbook_http_methods": ["GET"],
            "sportsbook_discovery_reused_without_second_network_fetch": True,
            "scheduler_started": False,
            "background_worker_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "caller_resupplies_state": True,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_model_modified": False,
            "step8_distribution_modified_after_generation": False,
        },
    }
    hash_surface = {
        key: response[key]
        for key in (
            "data_type",
            "schema_version",
            "request_content_sha256",
            "status",
            "health",
            "slate_date",
            "provider_discovery",
            "market_overlap",
            "projection_assembly",
            "runtime_summary",
            "lineage",
            "guardrails",
        )
    }
    response["runtime_content_sha256"] = step12b._canonical_hash(hash_surface)
    return response


def run_step12b_live_runtime_job_step19c(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    draftkings_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_requester: Callable[..., Any] | None = None,
    fanduel_requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    projection_loader: Callable[..., Mapping[str, Any]] | None = None,
    step12a_runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = step12b._validate_request(request)
    controller_policy = normalized["controller_policy"]
    dk_calls: list[dict[str, Any]] = []
    fd_calls: list[dict[str, Any]] = []
    dk_successes: list[dict[str, Any]] = []
    fd_successes: list[dict[str, Any]] = []
    dk_actual = draftkings_fetcher or draftkings.fetch_step11a_draftkings_provider_bridge
    fd_actual = fanduel_fetcher or fanduel.fetch_step11c_fanduel_provider_bridge
    dk_recording = _recording_fetcher(dk_actual, dk_calls, dk_successes)
    fd_recording = _recording_fetcher(fd_actual, fd_calls, fd_successes)
    try:
        return _ORIGINAL_RUN(
            request,
            env=env,
            draftkings_fetcher=dk_recording,
            fanduel_fetcher=fd_recording,
            draftkings_requester=draftkings_requester,
            fanduel_requester=fanduel_requester,
            roster_loader=roster_loader,
            projection_loader=projection_loader,
            step12a_runner=step12a_runner,
        )
    except step12b.WNBAStep12LiveRuntimeNotReadyError as exc:
        if str(exc) != _ALL_STEP8_NOT_READY_MESSAGE:
            raise
        if not dk_successes or not fd_successes:
            raise step12b.WNBAStep12LiveRuntimeIntegrityError(
                "Step 19C market-readiness conversion requires both verified provider bridges."
            ) from exc
        return _market_not_ready_response(
            normalized=normalized,
            controller_policy=controller_policy,
            dk_bridge=dk_successes[-1],
            fd_bridge=fd_successes[-1],
            dk_calls=dk_calls,
            fd_calls=fd_calls,
        )


def install_step19c_market_not_ready_compat() -> dict[str, Any]:
    if step12b.run_step12b_live_runtime_job is not run_step12b_live_runtime_job_step19c:
        step12b.run_step12b_live_runtime_job = run_step12b_live_runtime_job_step19c
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "underlying_step8_readiness_gates_relaxed": False,
        "projection_fabrication_allowed": False,
        "market_not_ready_conversion_enabled": True,
    }


INSTALLATION = install_step19c_market_not_ready_compat()

__all__ = [
    "INSTALLATION",
    "MODEL_VERSION",
    "install_step19c_market_not_ready_compat",
    "run_step12b_live_runtime_job_step19c",
]
