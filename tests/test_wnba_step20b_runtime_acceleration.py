from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api import wnba_projection_input_snapshot as projection_snapshot
from sports_api import wnba_step20b_runtime_acceleration as accel


def test_rotation_cache_is_exact_deepcopy_and_scope_local(monkeypatch):
    calls = []

    def upstream(game_id, season, *, rotation_stat="PLAYER_PTS"):
        calls.append((game_id, season, rotation_stat))
        return {"game_id": game_id, "nested": {"value": 1}}

    monkeypatch.setattr(accel, "_ORIGINAL_GAME_ROTATION", upstream)
    with accel.cycle_local_cache_scope() as cache:
        first = accel.get_game_rotation_step20b("1022600001", 2026)
        first["nested"]["value"] = 99
        second = accel.get_game_rotation_step20b("1022600001", 2026)
        assert second == {"game_id": "1022600001", "nested": {"value": 1}}
        assert calls == [("1022600001", 2026, "PLAYER_PTS")]
        stats = accel.cache_stats(cache)
        assert stats["stats"]["rotation"] == {"hits": 1, "misses": 1}

    with accel.cycle_local_cache_scope():
        accel.get_game_rotation_step20b("1022600001", 2026)
    assert len(calls) == 2


def test_exceptions_are_not_cached(monkeypatch):
    calls = 0

    def upstream(game_id, season, *, rotation_stat="PLAYER_PTS"):
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(accel, "_ORIGINAL_GAME_ROTATION", upstream)
    with accel.cycle_local_cache_scope() as cache:
        with pytest.raises(RuntimeError, match="boom"):
            accel.get_game_rotation_step20b("1022600002", 2026)
        with pytest.raises(RuntimeError, match="boom"):
            accel.get_game_rotation_step20b("1022600002", 2026)
        assert calls == 2
        stats = accel.cache_stats(cache)
        assert stats["entries"]["rotation"] == 0
        assert stats["stats"]["rotation"] == {"hits": 0, "misses": 0}


def test_event_and_possession_cache_keys_preserve_arguments(monkeypatch):
    event_calls = []
    possession_calls = []

    def events(game_id, season, *, event_category="All", limit=0):
        event_calls.append((game_id, season, event_category, limit))
        return {"events": [event_category, limit]}

    def possessions(game_id, season, *, limit=0):
        possession_calls.append((game_id, season, limit))
        return {"possessions": [limit]}

    monkeypatch.setattr(accel, "_ORIGINAL_PLAYER_EVENT_LINEUPS", events)
    monkeypatch.setattr(accel, "_ORIGINAL_PLAYER_POSSESSIONS", possessions)

    with accel.cycle_local_cache_scope():
        assert accel.get_game_event_lineups_step20b("1022600003", 2026, event_category="All", limit=0) == {"events": ["All", 0]}
        assert accel.get_game_event_lineups_step20b("1022600003", 2026, event_category="All", limit=0) == {"events": ["All", 0]}
        assert accel.get_game_event_lineups_step20b("1022600003", 2026, event_category="Shot", limit=5) == {"events": ["Shot", 5]}
        assert accel.get_game_possession_event_context_step20b("1022600003", 2026, limit=0) == {"possessions": [0]}
        assert accel.get_game_possession_event_context_step20b("1022600003", 2026, limit=0) == {"possessions": [0]}
        assert accel.get_game_possession_event_context_step20b("1022600003", 2026, limit=5) == {"possessions": [5]}

    assert event_calls == [
        ("1022600003", 2026, "All", 0),
        ("1022600003", 2026, "Shot", 5),
    ]
    assert possession_calls == [
        ("1022600003", 2026, 0),
        ("1022600003", 2026, 5),
    ]


def test_source_tuple_is_deepcopied(monkeypatch):
    calls = 0

    def sources(game_id, season):
        nonlocal calls
        calls += 1
        return ({"game_id": game_id, "actions": [1]}, {"game_id": game_id, "players": [2]})

    monkeypatch.setattr(accel, "_ORIGINAL_EVENT_SOURCES", sources)
    with accel.cycle_local_cache_scope():
        first = accel.get_event_sources_step20b("1022600004", 2026)
        first[0]["actions"].append(99)
        second = accel.get_event_sources_step20b("1022600004", 2026)
    assert calls == 1
    assert second == ({"game_id": "1022600004", "actions": [1]}, {"game_id": "1022600004", "players": [2]})


def test_installer_does_not_touch_step7g_protected_projection_aliases():
    protected = {
        "get_player_shot_chart_dataset": projection_snapshot.get_player_shot_chart_dataset,
        "get_opponent_defense_by_shot_zone_dataset": projection_snapshot.get_opponent_defense_by_shot_zone_dataset,
        "get_player_advanced_stats_dataset": projection_snapshot.get_player_advanced_stats_dataset,
        "get_team_advanced_stats_dataset": projection_snapshot.get_team_advanced_stats_dataset,
        "get_game_whistle_context": projection_snapshot.get_game_whistle_context,
    }

    status = accel.install_step20b_runtime_acceleration()

    assert status["installed"] is True
    assert status["all_bindings_active"] is True
    assert status["guardrails"]["cache_scope"] == "single_step12b_call_only"
    assert status["guardrails"]["exceptions_cached"] is False
    assert status["guardrails"]["provider_identity_protected_step7g_aliases_modified"] is False
    assert {
        name: getattr(projection_snapshot, name)
        for name in protected
    } == protected


def test_step12b_wrapper_uses_fresh_cache_each_call(monkeypatch):
    seen = []

    def upstream(*args, **kwargs):
        current = accel.cache_stats()
        seen.append(deepcopy(current))
        return {"ok": True}

    monkeypatch.setattr(accel, "_UPSTREAM_RUN_STEP12B", upstream)
    assert accel.run_step12b_with_observed_context_cache() == {"ok": True}
    assert accel.run_step12b_with_observed_context_cache() == {"ok": True}
    assert len(seen) == 2
    assert all(item["active"] is True for item in seen)
    assert all(all(value == 0 for value in item["entries"].values()) for item in seen)
    assert accel.cache_stats()["active"] is False
