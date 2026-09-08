from __future__ import annotations

import pytest

from sports_api import wnba_step21_step20b_production_activation_v1 as step21


def _base_guards():
    return {
        "projection_math_modified": False,
        "readiness_relaxed": False,
        "sportsbook_transport_modified": False,
        "persistence_modified": False,
        "wagering_enabled": False,
    }


def _statuses():
    runtime_guards = {
        **_base_guards(),
        "monte_carlo_simulation_count_modified": False,
        "monte_carlo_batch_size_modified": False,
    }
    workload_guards = {
        **_base_guards(),
        "first_party_not_found_only": True,
    }
    mc_guards = {
        **_base_guards(),
        "same_pcg64_random_stream": True,
        "same_latent_gaussian_draws": True,
        "same_marginal_cdf_tables": True,
        "same_discrete_count_mapping_required": True,
        "simulations_modified": False,
        "batch_size_modified": False,
    }
    cdf_guards = {
        **_base_guards(),
        "simulations_modified": False,
        "batch_size_modified": False,
    }
    cache_guards = {
        **_base_guards(),
        "cache_scope": "single_step12b_call_only",
        "cached_values_returned_by_deepcopy": True,
        "raised_exceptions_cached": False,
        "optional_unavailable_results_cached": False,
    }
    return {
        "runtime_acceleration": {
            "installed": True,
            "all_bindings_active": False,
            "bindings": {
                "rotation_module": True,
                "event_lineup_rotation_alias": True,
                "event_lineup_sources": True,
                "event_reconstruction": True,
                "player_event_lineups": True,
                "player_possessions": True,
                "game_player_event_features": True,
                "recent_rotation_module": True,
                "recent_rotation_opportunity_alias": True,
                "recent_event_feature_module": True,
                "recent_event_feature_opportunity_alias": True,
                "first_party_page_props": True,
                "step12b_wrapper": False,
            },
            "guardrails": runtime_guards,
        },
        "optional_workload": {
            "installed": True,
            "binding_active": True,
            "guardrails": workload_guards,
        },
        "monte_carlo": {
            "installed": True,
            "binding_active": True,
            "guardrails": mc_guards,
        },
        "monte_carlo_cdf": {
            "installed": True,
            "binding_active": True,
            "guardrails": cdf_guards,
        },
        "step4w_cache": {
            "installed": True,
            "all_bindings_active": True,
            "guardrails": cache_guards,
        },
    }


def _runtime():
    return {
        "enabled": True,
        "running": True,
        "role": "leader",
        "leadership_acquired": True,
        "success_count": 2,
        "failure_count": 0,
        "last_status": "cycle_completed",
        "last_cycle_started_at_utc": "2026-09-08T18:00:00+00:00",
        "last_cycle_finished_at_utc": "2026-09-08T18:04:30+00:00",
    }


def _build():
    return {
        "provider_reported_commit": step21.STEP20B_CANDIDATE_SHA,
        "provider_commit_authoritative": False,
    }


def test_step21_constants_lock_step20b_workload():
    assert step21.CERTIFIED_SIMULATIONS == 5_000_000
    assert step21.CERTIFIED_BATCH_SIZE == 250_000
    assert step21.MAX_COMPLETED_CYCLE_SECONDS == 600.0
    assert step21.MIN_SAFE_COMPLETED_CYCLES == 2
    assert len(step21.STEP20B_RUNTIME_BLOBS) >= 9


def test_completed_cycle_seconds():
    assert step21.completed_cycle_seconds(_runtime()) == 270.0
    bad = _runtime()
    bad["last_cycle_started_at_utc"] = None
    assert step21.completed_cycle_seconds(bad) is None


def test_validate_step20b_statuses_accepts_exact_safe_surface():
    out = step21.validate_step20b_statuses(_statuses())
    assert all(out.values())


def test_validate_step20b_statuses_rejects_disabled_cache():
    statuses = _statuses()
    statuses["step4w_cache"]["all_bindings_active"] = False
    with pytest.raises(step21.WNBAStep21ActivationError):
        step21.validate_step20b_statuses(statuses)


def test_validate_step20b_statuses_rejects_semantic_drift():
    statuses = _statuses()
    statuses["monte_carlo"]["guardrails"]["simulations_modified"] = True
    with pytest.raises(step21.WNBAStep21ActivationError):
        step21.validate_step20b_statuses(statuses)

    statuses = _statuses()
    statuses["runtime_acceleration"]["guardrails"]["projection_math_modified"] = True
    with pytest.raises(step21.WNBAStep21ActivationError):
        step21.validate_step20b_statuses(statuses)


def test_validate_live_activation_accepts_safe_two_cycle_leader():
    out = step21.validate_live_activation(
        build=_build(),
        runtime=_runtime(),
        statuses=_statuses(),
        consumer={
            "runtime": {
                "circuit_state": "closed",
                "consecutive_failures": 0,
                "cycle_outcome": "shadow_board_ready",
            }
        },
    )
    assert out["candidate_sha"] == step21.STEP20B_CANDIDATE_SHA
    assert out["production_role"] == "leader"
    assert out["success_count"] == 2
    assert out["failure_count"] == 0
    assert out["latest_completed_cycle_seconds"] == 270.0
    assert out["certified_simulations"] == 5_000_000
    assert out["certified_batch_size"] == 250_000
    assert out["projection_math_modified"] is False
    assert out["readiness_relaxed"] is False
    assert out["wagering_enabled"] is False


@pytest.mark.parametrize(
    "mutator",
    [
        lambda build, runtime, statuses: build.update(provider_reported_commit="0" * 40),
        lambda build, runtime, statuses: runtime.update(enabled=False),
        lambda build, runtime, statuses: runtime.update(running=False),
        lambda build, runtime, statuses: runtime.update(role="standby"),
        lambda build, runtime, statuses: runtime.update(leadership_acquired=False),
        lambda build, runtime, statuses: runtime.update(failure_count=1),
        lambda build, runtime, statuses: runtime.update(success_count=1),
        lambda build, runtime, statuses: runtime.update(last_status="cycle_failed"),
        lambda build, runtime, statuses: runtime.update(
            last_cycle_started_at_utc="2026-09-08T18:00:00+00:00",
            last_cycle_finished_at_utc="2026-09-08T18:10:00+00:00",
        ),
    ],
)
def test_validate_live_activation_fails_closed(mutator):
    build = _build()
    runtime = _runtime()
    statuses = _statuses()
    mutator(build, runtime, statuses)
    with pytest.raises(step21.WNBAStep21ActivationError):
        step21.validate_live_activation(
            build=build,
            runtime=runtime,
            statuses=statuses,
        )


def test_consumer_circuit_failure_is_rejected():
    with pytest.raises(step21.WNBAStep21ActivationError):
        step21.validate_live_activation(
            build=_build(),
            runtime=_runtime(),
            statuses=_statuses(),
            consumer={
                "runtime": {
                    "circuit_state": "open",
                    "consecutive_failures": 3,
                    "cycle_outcome": "provider_failure",
                }
            },
        )
