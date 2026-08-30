"""WNBA Step 19K: safe no-exact-line market readiness classification.

The frozen Step12B caller-driven job raises when DraftKings and FanDuel both
return verified current records but no exact same-line player-prop identity is
shared by both books. That was safe for a manual caller, but in the always-on
Step17B host it incorrectly turns a normal moving-market condition into a failed
scheduler cycle.

This compatibility layer changes only that one boundary condition. It preserves
strict exact-line requirements and never fabricates a projection or market. When
both verified providers reached Step12B's exact-overlap check and the intersection
is empty, the wrapper returns a Step12B-compatible market_not_ready response using
the same closed-circuit cadence/state semantics as Step11E's native
WNBAStep10LivePipelineNotReadyError branch. Every other exception is re-raised
unchanged.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import threading
from typing import Any

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19j_runtime_acceleration as step19j
from sports_api.wnba_step10_live_pipeline import WNBAStep10LivePipelineNotReadyError

SOURCE = "Kyre Sports API WNBA Step19K exact-line market readiness compatibility"
MODEL_VERSION = "wnba_step19k_no_exact_line_market_not_ready_v1"
NO_EXACT_LINE_MESSAGE = (
    "Step 12B found no exact same-line DraftKings/FanDuel player-prop group."
)

_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None
_INSTALLED = False
_LOCK = threading.RLock()
_TRANSFORMED_COUNT = 0
_LAST_TRANSFORM: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_no_exact_line_condition(exc: Exception) -> bool:
    return (
        isinstance(exc, step12b.WNBAStep12LiveRuntimeNotReadyError)
        and " ".join(str(exc).split()) == NO_EXACT_LINE_MESSAGE
    )


def _market_not_ready_tick(
    *,
    normalized: Mapping[str, Any],
    controller_policy: Mapping[str, Any],
    env: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Build the exact Step11E controller semantics for healthy-market not-ready.

    This does not call a sportsbook or Step8. It is used only after the frozen
    Step12B path has already proven both provider bridges and non-empty records
    and then raised solely because the exact-line intersection was empty.
    """
    step11e._assert_safe_environment(env)
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
    attempts = step11e._strict_int(
        controller_policy.get("provider_attempts", step11d.DEFAULT_PROVIDER_ATTEMPTS),
        "provider_attempts",
        1,
        step11d.MAX_PROVIDER_ATTEMPTS,
    )

    previous_state = normalized.get("previous_state")
    previous = None
    if previous_state is not None:
        previous = step11e._verify_previous_state(
            previous_state,
            current_policy=policy,
            evaluated_at=evaluated,
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

    probe_mode = (
        prior_circuit == "open"
        and open_until is not None
        and evaluated >= open_until
    )
    if prior_circuit == "open" and open_until is not None and evaluated < open_until:
        cycle_due = False
        skip_reason = "circuit_open_cooldown"
    elif prior_circuit == "closed" and evaluated < next_due:
        cycle_due = False
        skip_reason = "refresh_not_due"
    else:
        cycle_due = True
        skip_reason = None

    cycle_outcome = "not_executed"
    cycle_error: dict[str, str] | None = None
    health = "waiting"
    status = "not_due"
    circuit = prior_circuit
    failures = prior_failures
    new_open_until = open_until
    new_next_due = next_due
    cycle_started = last_cycle

    if not cycle_due:
        if skip_reason == "circuit_open_cooldown":
            status = "circuit_open"
            health = "blocked"
            new_next_due = open_until or next_due
    else:
        cycle_started = evaluated
        condition = WNBAStep10LivePipelineNotReadyError(
            "Verified DraftKings and FanDuel records have no exact same-line "
            "player-prop group for the current slate."
        )
        cycle_error = step11e._error_detail(condition)
        cycle_outcome = "market_board_not_ready"
        failures = 0
        circuit = "closed"
        new_open_until = None
        new_next_due = evaluated + timedelta(seconds=policy["refresh_interval_seconds"])
        status = "market_not_ready"
        health = "market_not_ready"

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

    result = {
        "data_type": "wnba_step11e_controlled_automation_tick",
        "schema_version": step11e.SCHEMA_VERSION,
        "source": step11e.SOURCE,
        "model_version": step11e.MODEL_VERSION,
        "release_id": step11e.RELEASE_ID,
        "generated_at_utc": _now(),
        "evaluated_at_utc": evaluated.isoformat(),
        "status": status,
        "health": health,
        "execution": {
            "cycle_due": cycle_due,
            "cycle_executed": cycle_due,
            "cycle_outcome": cycle_outcome,
            "skip_reason": skip_reason,
            "half_open_probe": probe_mode,
            "provider_attempt_limit": attempts,
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
            "step11_release_id": release.RELEASE_ID,
            "step11a_frozen_sha": release.STEP11A_FROZEN_SHA,
            "step11b_frozen_sha": release.STEP11B_FROZEN_SHA,
            "step11c_frozen_sha": release.STEP11C_FROZEN_SHA,
            "step11d_frozen_sha": release.STEP11D_FROZEN_SHA,
            "step10_frozen_sha": release.STEP10_FROZEN_SHA,
            "step9_frozen_sha": release.STEP9_FROZEN_SHA,
            "step8_frozen_sha": release.STEP8_FROZEN_SHA,
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
        for key, value in result.items()
        if key
        not in {
            "generated_at_utc",
            "shadow_board_result",
            "controller_content_sha256",
        }
    }
    result["controller_content_sha256"] = step11e._canonical_hash(hash_surface)
    step11e._assert_safe_environment(env)
    return result


def _step12b_market_not_ready_response(
    *,
    normalized: Mapping[str, Any],
    controller_policy: Mapping[str, Any],
    env: Mapping[str, str] | None,
) -> dict[str, Any]:
    tick = _market_not_ready_tick(
        normalized=normalized,
        controller_policy=controller_policy,
        env=env,
    )
    execution = tick.get("execution") or {}
    state = tick.get("automation_state")
    if not isinstance(state, Mapping):
        raise step12b.WNBAStep12LiveRuntimeIntegrityError(
            "Step19K market-not-ready compatibility is missing controller state."
        )
    if execution.get("cycle_outcome") not in {"market_board_not_ready", "not_executed"}:
        raise step12b.WNBAStep12LiveRuntimeIntegrityError(
            "Step19K market-not-ready compatibility produced an unexpected outcome."
        )

    step12a_compat = {
        "data_type": "wnba_step12a_shadow_runner_response",
        "schema_version": step12a.SCHEMA_VERSION,
        "status": tick.get("status"),
        "health": tick.get("health"),
        "automation_state": deepcopy(dict(state)),
        "shadow_board_result": None,
        "step11e_tick": tick,
        "compatibility_short_circuit": "market_not_ready_no_exact_same_line_before_projection",
    }

    response = {
        "data_type": "wnba_step12b_live_runtime_assembly_response",
        "schema_version": step12b.SCHEMA_VERSION,
        "source": step12b.SOURCE,
        "model_version": step12b.MODEL_VERSION,
        "generated_at_utc": _now(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": tick.get("status"),
        "health": tick.get("health"),
        "slate_date": normalized["slate_date"],
        "provider_discovery": {
            "sportsbooks": [draftkings.PROVIDER, fanduel.PROVIDER],
            "draftkings": {
                "bridge_verified_before_exact_overlap_check": True,
                "nonempty_records_verified": True,
            },
            "fanduel": {
                "bridge_verified_before_exact_overlap_check": True,
                "nonempty_records_verified": True,
            },
            "duplicate_sportsbook_discovery_performed": False,
            "transient_provider_short_circuit": False,
            "market_not_ready_short_circuit": True,
        },
        "market_overlap": {
            "draftkings_record_count": None,
            "fanduel_record_count": None,
            "exact_line_multibook_group_count": 0,
            "exact_line_multibook_groups": [],
            "unique_projection_target_count": 0,
            "different_lines_blended": False,
            "classification": "market_not_ready_no_exact_same_line",
        },
        "projection_assembly": {
            "requested_target_count": 0,
            "built_target_count": 0,
            "skipped_target_count": 0,
            "simulations_per_built_target": step12b.CERTIFIED_SIMULATIONS,
            "batch_size": step12b.CERTIFIED_BATCH_SIZE,
            "targets": [],
            "skipped_targets": [],
            "all_built_distributions_converged": True,
            "short_circuited_before_projection": True,
        },
        "runtime_summary": {
            "step8_distribution_count": 0,
            "step11_cycle_executed": execution.get("cycle_executed"),
            "qualified_prop_count": None,
            "top_card_count": None,
        },
        "step12a_result": step12a_compat,
        "lineage": {
            "step12a_frozen_sha": step12b.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": step12b.STEP11E_FROZEN_SHA,
            "step8_frozen_sha": step12b.STEP8_FROZEN_SHA,
            "step12a_runner_content_sha256": None,
            "draftkings_bridge_content_sha256": None,
            "fanduel_bridge_content_sha256": None,
            "step8_result_content_sha256": [],
            "provider_bridges_verified_before_short_circuit": True,
        },
        "guardrails": {
            "shadow_only": True,
            "caller_driven_job_only": True,
            "market_driven_projection_target_discovery": True,
            "official_wnba_identity_reconciliation_required": True,
            "exact_line_multibook_overlap_required": True,
            "different_lines_blended": False,
            "frozen_step8_projection_generated": False,
            "five_million_simulations_required": True,
            "market_not_ready_short_circuit_before_projection": True,
            "frozen_step11e_market_controller_semantics_reused": True,
            "readiness_relaxed": False,
            "sportsbook_network_fetch_performed": True,
            "sportsbook_http_methods": ["GET"],
            "duplicate_sportsbook_discovery_performed": False,
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


def run_step12b_market_not_ready_compatible(*args: Any, **kwargs: Any) -> Any:
    upstream = _UPSTREAM_RUN_STEP12B
    if upstream is None:
        raise RuntimeError("Step19K market readiness compatibility is not installed.")
    request = args[0] if args else kwargs.get("request")
    try:
        return upstream(*args, **kwargs)
    except Exception as exc:
        if not _is_no_exact_line_condition(exc):
            raise
        normalized = step12b._validate_request(request)
        response = _step12b_market_not_ready_response(
            normalized=normalized,
            controller_policy=normalized["controller_policy"],
            env=kwargs.get("env"),
        )
        execution = ((response.get("step12a_result") or {}).get("step11e_tick") or {}).get(
            "execution"
        ) or {}
        with _LOCK:
            global _TRANSFORMED_COUNT, _LAST_TRANSFORM
            _TRANSFORMED_COUNT += 1
            _LAST_TRANSFORM = {
                "transformed_at_utc": _now(),
                "slate_date": normalized["slate_date"],
                "cycle_outcome": execution.get("cycle_outcome"),
                "status": response.get("status"),
                "health": response.get("health"),
                "circuit_state": ((response.get("step12a_result") or {}).get("automation_state") or {}).get(
                    "circuit_state"
                ),
                "consecutive_failure_count": ((response.get("step12a_result") or {}).get("automation_state") or {}).get(
                    "consecutive_failure_count"
                ),
            }
        return response


def install_step19k_market_not_ready() -> dict[str, Any]:
    global _INSTALLED, _UPSTREAM_RUN_STEP12B
    step19j.install_step19j_runtime_acceleration()
    current = step12b.run_step12b_live_runtime_job
    if current is run_step12b_market_not_ready_compatible:
        _INSTALLED = True
        return installation_status()
    if current is not step19j.run_step12b_with_cycle_local_context:
        raise RuntimeError("Step19K refuses to replace an unknown Step12B override.")
    _UPSTREAM_RUN_STEP12B = current
    step12b.run_step12b_live_runtime_job = run_step12b_market_not_ready_compatible
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        count = int(_TRANSFORMED_COUNT)
        latest = deepcopy(_LAST_TRANSFORM)
    return {
        "data_type": "wnba_step19k_market_not_ready_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "step12b_wrapper_active": (
            step12b.run_step12b_live_runtime_job
            is run_step12b_market_not_ready_compatible
        ),
        "upstream_is_step19j": (
            _UPSTREAM_RUN_STEP12B is step19j.run_step12b_with_cycle_local_context
        ),
        "transformed_count": count,
        "last_transform": latest,
        "guardrails": {
            "exact_line_overlap_required": True,
            "different_lines_blended": False,
            "fake_projection_created": False,
            "monte_carlo_simulation_count_modified": False,
            "projection_math_modified": False,
            "provider_transport_modified": False,
            "provider_failure_reclassified": False,
            "only_no_exact_line_condition_transformed": True,
            "market_condition_counts_as_provider_failure": False,
            "market_condition_opens_circuit": False,
            "readiness_relaxed": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "NO_EXACT_LINE_MESSAGE",
    "SOURCE",
    "install_step19k_market_not_ready",
    "installation_status",
    "run_step12b_market_not_ready_compatible",
]
