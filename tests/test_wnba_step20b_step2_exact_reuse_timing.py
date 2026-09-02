from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api import wnba_model_input_readiness as step4x
from sports_api import wnba_projection_input_snapshot as step4w
from sports_api import wnba_step20b_step4w_cycle_cache as cache


def test_full_snapshot_exact_reuse_is_deepcopied_and_cycle_local(monkeypatch):
    calls = []

    def upstream(player_id, game_id, season, **kwargs):
        calls.append((player_id, game_id, season, deepcopy(kwargs)))
        return {"player_id": player_id, "game_id": game_id, "season": season, "nested": {"value": 1}}

    monkeypatch.setitem(cache._UPSTREAM_HELPERS, "get_player_game_projection_input_snapshot", upstream)
    with cache.cycle_local_cache_scope() as active:
        first = cache.get_player_game_projection_input_snapshot_step20b(1629483, "1022600297", 2026, season_type="Regular Season", last_n_games=5, include_shot_context=True)
        first["nested"]["value"] = 99
        second = cache.get_player_game_projection_input_snapshot_step20b(1629483, "1022600297", 2026, season_type="Regular Season", last_n_games=5, include_shot_context=True)
        third = cache.get_player_game_projection_input_snapshot_step20b(1629483, "1022600297", 2026, season_type="Regular Season", last_n_games=5, include_shot_context=False)
        stats = cache.cache_stats(active)

    with cache.cycle_local_cache_scope():
        cache.get_player_game_projection_input_snapshot_step20b(1629483, "1022600297", 2026, season_type="Regular Season", last_n_games=5, include_shot_context=True)

    assert second["nested"]["value"] == 1
    assert third["nested"]["value"] == 1
    assert len(calls) == 3
    assert calls[0][3]["include_shot_context"] is True
    assert calls[1][3]["include_shot_context"] is False
    assert calls[2][3]["include_shot_context"] is True
    assert stats["hits"]["projection_snapshot"] == 1
    assert stats["misses"]["projection_snapshot"] == 2
    timing = stats["timing_ms"]["projection_snapshot"]
    assert timing["calls"] == 3
    assert timing["upstream_calls"] == 2
    assert timing["direct_cache_hits"] == 1
    assert timing["raised"] == 0
    assert timing["cumulative_ms"] >= 0.0
    assert timing["max_ms"] >= 0.0


def test_snapshot_key_separates_player_game_and_exact_arguments(monkeypatch):
    calls = []

    def upstream(*args, **kwargs):
        calls.append((deepcopy(args), deepcopy(kwargs)))
        return {"args": deepcopy(args), "kwargs": deepcopy(kwargs)}

    monkeypatch.setitem(cache._UPSTREAM_HELPERS, "get_player_game_projection_input_snapshot", upstream)
    with cache.cycle_local_cache_scope():
        cache.get_player_game_projection_input_snapshot_step20b(1, "1022600001", 2026, last_n_games=5)
        cache.get_player_game_projection_input_snapshot_step20b(2, "1022600001", 2026, last_n_games=5)
        cache.get_player_game_projection_input_snapshot_step20b(1, "1022600002", 2026, last_n_games=5)
        cache.get_player_game_projection_input_snapshot_step20b(1, "1022600001", 2026, last_n_games=6)
    assert len(calls) == 4


def test_snapshot_exceptions_are_never_cached_and_are_timed(monkeypatch):
    calls = 0

    def upstream(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("snapshot boom")

    monkeypatch.setitem(cache._UPSTREAM_HELPERS, "get_player_game_projection_input_snapshot", upstream)
    with cache.cycle_local_cache_scope() as active:
        for _ in range(2):
            with pytest.raises(RuntimeError, match="snapshot boom"):
                cache.get_player_game_projection_input_snapshot_step20b(1, "1022600001", 2026)
        stats = cache.cache_stats(active)

    assert calls == 2
    assert stats["entries"]["projection_snapshot"] == 0
    assert stats["hits"]["projection_snapshot"] == 0
    assert stats["misses"]["projection_snapshot"] == 0
    timing = stats["timing_ms"]["projection_snapshot"]
    assert timing["calls"] == 2
    assert timing["upstream_calls"] == 2
    assert timing["raised"] == 2


def test_optional_unavailable_is_not_cached_and_has_component_ms(monkeypatch):
    calls = 0

    class OptionalUnavailable(RuntimeError):
        pass

    def upstream(name, func, *args, exceptions, **kwargs):
        nonlocal calls
        calls += 1
        return None, {"requested": True, "available": False, "error": "missing", "component": name}

    monkeypatch.setitem(cache._UPSTREAM_HELPERS, "_optional_component", upstream)
    with cache.cycle_local_cache_scope() as active:
        for _ in range(2):
            cache.optional_component_step20b("player_vs_opponent_shot_chart", lambda: None, 1629483, 2026, exceptions=(OptionalUnavailable,), opponent_team_key="NY")
        stats = cache.cache_stats(active)

    assert calls == 2
    assert stats["entries"]["optional_component"] == 0
    assert stats["hits"]["optional_component"] == 0
    assert stats["misses"]["optional_component"] == 0
    timing = stats["timing_ms"]["optional_component:player_vs_opponent_shot_chart"]
    assert timing["calls"] == 2
    assert timing["upstream_calls"] == 2
    assert timing["direct_cache_hits"] == 0


def test_live_cycle_timing_remains_observable_while_step12b_is_running(monkeypatch):
    seen = {}

    def upstream(*args, **kwargs):
        seen["live"] = deepcopy(cache.installation_status()["live_cycles"])
        raise RuntimeError("stop after observation")

    monkeypatch.setattr(cache, "_UPSTREAM_RUN_STEP12B", upstream)
    with pytest.raises(RuntimeError, match="stop after observation"):
        cache.run_step12b_with_step4w_cycle_cache({"request": True})

    assert len(seen["live"]) == 1
    assert seen["live"][0]["status"] == "running"
    assert seen["live"][0]["elapsed_ms_now"] >= 0.0
    status = cache.installation_status()
    assert status["live_cycles"] == []
    assert status["last_cycle"]["status"] == "raised"
    assert status["last_cycle"]["elapsed_seconds"] >= 0.0


def test_installer_wraps_only_unprotected_snapshot_boundary_and_preserves_guards():
    protected = {name: getattr(step4w, name) for name in ("get_player_shot_chart_dataset", "get_opponent_defense_by_shot_zone_dataset", "get_player_advanced_stats_dataset", "get_team_advanced_stats_dataset", "get_game_whistle_context")}
    status = cache.install_step20b_step4w_cycle_cache()

    assert status["installed"] is True
    assert status["all_bindings_active"] is True
    assert status["bindings"]["projection_snapshot"] is True
    assert step4x.get_player_game_projection_input_snapshot is cache.get_player_game_projection_input_snapshot_step20b
    assert {name: getattr(step4w, name) for name in protected} == protected

    guards = status["guardrails"]
    assert guards["cache_scope"] == "single_step12b_call_only"
    assert guards["cached_values_returned_by_deepcopy"] is True
    assert guards["raised_exceptions_cached"] is False
    assert guards["optional_unavailable_results_cached"] is False
    assert guards["exact_call_arguments_are_cache_key"] is True
    assert guards["full_step4w_snapshot_reuse_enabled"] is True
    assert guards["full_snapshot_cache_scope"] == "single_step12b_call_exact_arguments_only"
    assert guards["readiness_result_cached"] is False
    assert guards["step8a_handoff_result_cached"] is False
    assert guards["freshness_recomputed_by_step4x_on_every_readiness_call"] is True
    assert guards["timing_uses_monotonic_clock"] is True
    assert guards["timing_unit"] == "milliseconds"
    assert guards["timing_changes_execution"] is False
    assert guards["step7g_protected_provider_aliases_modified"] is False
    assert guards["projection_math_modified"] is False
    assert guards["readiness_relaxed"] is False
    assert guards["monte_carlo_simulation_count_modified"] is False
    assert guards["monte_carlo_batch_size_modified"] is False
    assert guards["sportsbook_transport_modified"] is False
    assert guards["persistence_modified"] is False
    assert guards["wagering_enabled"] is False
