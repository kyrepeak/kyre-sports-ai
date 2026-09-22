"""WNBA Step19N: classify a verified FanDuel empty prop board as market readiness.

Step19M repaired the intermittent same-market line-move identity bug. During the
subsequent guarded release, FanDuel returned a different bounded state:
Step11C completed its event/schedule/roster path but produced no complete official
identity two-way player-prop records. Frozen Step12B groups all Step11C NotReady
exceptions with connector readiness and therefore marks this as
``provider_transient_not_ready``.

This compatibility layer changes only the structured Step12B response where:
* DraftKings produced a verified non-empty bridge;
* FanDuel produced no bridge;
* every bounded FanDuel retry is exactly
  ``WNBAStep11FanDuelProviderNotReadyError`` with the frozen post-build message
  ``Step 11C produced no complete official-identity two-way FanDuel records.``;
* Step12B consequently returned ``provider_transient_not_ready``.

That exact state means there is no usable FanDuel two-way player-prop market to
build, not that transport or official identity failed. It is converted to the
existing closed-circuit ``market_board_not_ready`` cadence without fabricating a
FanDuel bridge, projection, line, or consensus. Every other provider failure is
returned unchanged by object identity from the upstream wrapper.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
import threading
from typing import Any

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19k_market_not_ready as step19k

SOURCE = "Kyre Sports API WNBA Step19N FanDuel empty-market readiness compatibility"
MODEL_VERSION = "wnba_step19n_fanduel_empty_market_not_ready_v1"
FANDUEL_EMPTY_MARKET_MESSAGE = (
    "Step 11C produced no complete official-identity two-way FanDuel records."
)

_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None
_INSTALLED = False
_LOCK = threading.RLock()
_TRANSFORMED_COUNT = 0
_LAST_TRANSFORM: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_fanduel_empty_market_response(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    if result.get("data_type") != "wnba_step12b_live_runtime_assembly_response":
        return False
    parent = result.get("step12a_result")
    tick = parent.get("step11e_tick") if isinstance(parent, Mapping) else None
    execution = tick.get("execution") if isinstance(tick, Mapping) else None
    if not isinstance(execution, Mapping) or execution.get("cycle_outcome") != "provider_transient_not_ready":
        return False

    discovery = result.get("provider_discovery")
    if not isinstance(discovery, Mapping):
        return False
    dk = discovery.get("draftkings")
    fd = discovery.get("fanduel")
    if not isinstance(dk, Mapping) or not isinstance(fd, Mapping):
        return False

    try:
        dk_records = int(dk.get("record_count") or 0)
        fd_records = int(fd.get("record_count") or 0)
        fd_attempts = int(fd.get("attempts_executed") or 0)
        fd_retryable = int(fd.get("retryable_failures") or 0)
    except (TypeError, ValueError):
        return False
    if dk_records <= 0 or not str(dk.get("bridge_content_sha256") or "").strip():
        return False
    if fd_records != 0 or fd_attempts <= 0 or fd_retryable != fd_attempts:
        return False

    errors = fd.get("errors")
    if not isinstance(errors, list) or len(errors) != fd_attempts:
        return False
    for error in errors:
        if not isinstance(error, Mapping):
            return False
        if error.get("error_type") != fanduel.WNBAStep11FanDuelProviderNotReadyError.__name__:
            return False
        if _clean_text(error.get("error_message")) != FANDUEL_EMPTY_MARKET_MESSAGE:
            return False

    projection = result.get("projection_assembly")
    if not isinstance(projection, Mapping):
        return False
    try:
        if int(projection.get("built_target_count") or 0) != 0:
            return False
    except (TypeError, ValueError):
        return False
    return True


def _market_not_ready_response(
    *,
    original: Mapping[str, Any],
    normalized: Mapping[str, Any],
    env: Mapping[str, str] | None,
) -> dict[str, Any]:
    tick = step19k._market_not_ready_tick(
        normalized=normalized,
        controller_policy=normalized["controller_policy"],
        env=env,
    )
    execution = tick.get("execution") or {}
    state = tick.get("automation_state")
    if not isinstance(state, Mapping):
        raise step12b.WNBAStep12LiveRuntimeIntegrityError(
            "Step19N empty-market compatibility is missing controller state."
        )
    if execution.get("cycle_outcome") not in {"market_board_not_ready", "not_executed"}:
        raise step12b.WNBAStep12LiveRuntimeIntegrityError(
            "Step19N empty-market compatibility produced an unexpected controller outcome."
        )

    original_discovery = original.get("provider_discovery") or {}
    dk_discovery = deepcopy(dict(original_discovery.get("draftkings") or {}))
    fd_discovery = deepcopy(dict(original_discovery.get("fanduel") or {}))
    provider_discovery = {
        "sportsbooks": deepcopy(original_discovery.get("sportsbooks") or []),
        "draftkings": dk_discovery,
        "fanduel": fd_discovery,
        "sportsbook_network_fetches_reused_in_step11_tick": True,
        "duplicate_sportsbook_discovery_performed": False,
        "transient_provider_short_circuit": False,
        "market_not_ready_short_circuit": True,
        "classification": "fanduel_no_complete_two_way_player_props",
    }

    step12a_compat = {
        "data_type": "wnba_step12a_shadow_runner_response",
        "schema_version": step12a.SCHEMA_VERSION,
        "status": tick.get("status"),
        "health": tick.get("health"),
        "automation_state": deepcopy(dict(state)),
        "shadow_board_result": None,
        "step11e_tick": tick,
        "compatibility_short_circuit": "market_not_ready_fanduel_empty_player_prop_board_before_projection",
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
        "provider_discovery": provider_discovery,
        "market_overlap": {
            "draftkings_record_count": int(dk_discovery.get("record_count") or 0),
            "fanduel_record_count": 0,
            "exact_line_multibook_group_count": 0,
            "exact_line_multibook_groups": [],
            "unique_projection_target_count": 0,
            "different_lines_blended": False,
            "classification": "market_not_ready_fanduel_no_complete_two_way_player_props",
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
            "draftkings_bridge_content_sha256": dk_discovery.get("bridge_content_sha256"),
            "fanduel_bridge_content_sha256": None,
            "step8_result_content_sha256": [],
            "draftkings_bridge_verified_before_short_circuit": True,
            "fanduel_bridge_not_built_due_empty_market": True,
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
            "only_exact_fanduel_empty_market_subtype_transformed": True,
            "draftkings_verified_nonempty_required": True,
            "fanduel_bridge_fabricated": False,
            "fake_projection_created": False,
            "true_provider_failure_reclassified": False,
            "identity_failure_reclassified": False,
            "transport_failure_reclassified": False,
            "upstream_failure_reclassified": False,
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


def run_step12b_fanduel_empty_market_compatible(*args: Any, **kwargs: Any) -> Any:
    upstream = _UPSTREAM_RUN_STEP12B
    if upstream is None:
        raise RuntimeError("Step19N FanDuel empty-market compatibility is not installed.")
    request = args[0] if args else kwargs.get("request")
    result = upstream(*args, **kwargs)
    if not _is_fanduel_empty_market_response(result):
        return result

    normalized = step12b._validate_request(request)
    transformed = _market_not_ready_response(
        original=result,
        normalized=normalized,
        env=kwargs.get("env"),
    )
    execution = ((transformed.get("step12a_result") or {}).get("step11e_tick") or {}).get("execution") or {}
    state = ((transformed.get("step12a_result") or {}).get("automation_state") or {})
    with _LOCK:
        global _TRANSFORMED_COUNT, _LAST_TRANSFORM
        _TRANSFORMED_COUNT += 1
        _LAST_TRANSFORM = {
            "transformed_at_utc": _now(),
            "slate_date": normalized["slate_date"],
            "cycle_outcome": execution.get("cycle_outcome"),
            "status": transformed.get("status"),
            "health": transformed.get("health"),
            "circuit_state": state.get("circuit_state"),
            "consecutive_failure_count": state.get("consecutive_failure_count"),
            "draftkings_record_count": transformed["market_overlap"]["draftkings_record_count"],
            "fanduel_record_count": 0,
        }
    return transformed


def install_step19n_fanduel_empty_market() -> dict[str, Any]:
    """Install only after Step19K is already the active Step12B wrapper."""
    global _INSTALLED, _UPSTREAM_RUN_STEP12B
    current = step12b.run_step12b_live_runtime_job
    if current is run_step12b_fanduel_empty_market_compatible:
        _INSTALLED = True
        return installation_status()
    if current is not step19k.run_step12b_market_not_ready_compatible:
        raise RuntimeError("Step19N requires the already-installed Step19K Step12B wrapper.")
    _UPSTREAM_RUN_STEP12B = current
    step12b.run_step12b_live_runtime_job = run_step12b_fanduel_empty_market_compatible
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        count = int(_TRANSFORMED_COUNT)
        latest = deepcopy(_LAST_TRANSFORM)
    return {
        "data_type": "wnba_step19n_fanduel_empty_market_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "step12b_wrapper_active": (
            step12b.run_step12b_live_runtime_job is run_step12b_fanduel_empty_market_compatible
        ),
        "upstream_is_step19k": (
            _UPSTREAM_RUN_STEP12B is step19k.run_step12b_market_not_ready_compatible
        ),
        "transformed_count": count,
        "last_transform": latest,
        "guardrails": {
            "requires_preinstalled_step19k": True,
            "draftkings_verified_nonempty_required": True,
            "exact_fanduel_error_type_required": fanduel.WNBAStep11FanDuelProviderNotReadyError.__name__,
            "exact_fanduel_error_message_required": FANDUEL_EMPTY_MARKET_MESSAGE,
            "all_fanduel_attempts_must_match": True,
            "identity_failure_reclassified": False,
            "transport_failure_reclassified": False,
            "upstream_failure_reclassified": False,
            "landing_page_failure_reclassified": False,
            "fanduel_bridge_fabricated": False,
            "different_lines_blended": False,
            "fake_projection_created": False,
            "monte_carlo_simulation_count_modified": False,
            "projection_math_modified": False,
            "provider_transport_modified": False,
            "readiness_relaxed": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


def _reset_for_test() -> None:
    with _LOCK:
        global _TRANSFORMED_COUNT, _LAST_TRANSFORM
        _TRANSFORMED_COUNT = 0
        _LAST_TRANSFORM = None


__all__ = [
    "FANDUEL_EMPTY_MARKET_MESSAGE",
    "MODEL_VERSION",
    "SOURCE",
    "install_step19n_fanduel_empty_market",
    "installation_status",
    "run_step12b_fanduel_empty_market_compatible",
]
