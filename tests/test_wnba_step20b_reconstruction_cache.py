from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import threading
import time

import pytest

from sports_api import wnba_event_lineup_context as event_lineup
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step20b_runtime_acceleration as accel


def _pbp(*, marker: int = 1) -> dict:
    return {
        "game_id": "1022600001",
        "season": 2026,
        "source_url": "https://www.wnba.com/game/test/play-by-play",
        "retrieved_at_utc": "2026-08-30T20:00:00+00:00",
        "events": [{"event_id": 1, "marker": marker}],
    }


def _rotation(*, marker: int = 1) -> dict:
    return {
        "game_id": "1022600001",
        "season": 2026,
        "source_url": "https://stats.wnba.com/stats/gamerotation",
        "retrieved_at_utc": "2026-08-30T20:00:00+00:00",
        "away": {"stints": [{"player_id": 1, "marker": marker}]},
        "home": {"stints": [{"player_id": 2, "marker": marker}]},
    }


def test_reconstruction_cache_reuses_exact_sources_and_returns_deepcopy(monkeypatch):
    calls = []

    def upstream(play_by_play, rotation_context):
        calls.append((deepcopy(play_by_play), deepcopy(rotation_context)))
        return {
            "rows": [{"marker": play_by_play["events"][0]["marker"]}],
            "teams": {"away": [1], "home": [2]},
        }

    monkeypatch.setattr(accel, "_ORIGINAL_EVENT_JOIN", upstream)

    with accel.cycle_local_cache_scope() as cache:
        first = accel.reconstruct_event_context_step20b(_pbp(), _rotation())
        first["rows"][0]["marker"] = 999
        second = accel.reconstruct_event_context_step20b(_pbp(), _rotation())
        changed = accel.reconstruct_event_context_step20b(_pbp(marker=2), _rotation())
        stats = accel.cache_stats(cache)

    assert second["rows"][0]["marker"] == 1
    assert changed["rows"][0]["marker"] == 2
    assert len(calls) == 2
    assert stats["entries"]["event_reconstruction"] == 2
    assert stats["stats"]["event_reconstruction"] == {"hits": 1, "misses": 2}
    timing = stats["event_reconstruction_timing_ms"]
    assert timing["build_count"] == 2
    assert timing["reuse_count"] == 1
    assert timing["build_ms"] >= 0.0
    assert timing["reuse_ms"] >= 0.0


def test_reconstruction_cache_coalesces_same_key_concurrent_consumers(monkeypatch):
    calls = 0
    calls_lock = threading.Lock()
    upstream_started = threading.Event()

    def upstream(play_by_play, rotation_context):
        nonlocal calls
        with calls_lock:
            calls += 1
        upstream_started.set()
        time.sleep(0.08)
        return ({"rows": [{"value": 7}]}, {"away": [1], "home": [2]})

    monkeypatch.setattr(accel, "_ORIGINAL_EVENT_JOIN", upstream)

    with accel.cycle_local_cache_scope() as cache:
        ctx1 = copy_context()
        ctx2 = copy_context()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(ctx1.run, accel.reconstruct_event_context_step20b, _pbp(), _rotation())
            assert upstream_started.wait(timeout=1.0)
            second = pool.submit(ctx2.run, accel.reconstruct_event_context_step20b, _pbp(), _rotation())
            result1 = first.result(timeout=2.0)
            result2 = second.result(timeout=2.0)
        stats = accel.cache_stats(cache)

    assert result1 == result2
    assert calls == 1
    assert stats["entries"]["event_reconstruction"] == 1
    assert stats["stats"]["event_reconstruction"] == {"hits": 1, "misses": 1}
    timing = stats["event_reconstruction_timing_ms"]
    assert timing["build_count"] == 1
    assert timing["reuse_count"] == 1
    assert timing["wait_count"] >= 1
    assert timing["wait_ms"] > 0.0
    assert stats["event_reconstruction_inflight"] == 0


def test_reconstruction_exceptions_are_not_cached(monkeypatch):
    calls = 0

    def upstream(play_by_play, rotation_context):
        nonlocal calls
        calls += 1
        raise RuntimeError("join failed")

    monkeypatch.setattr(accel, "_ORIGINAL_EVENT_JOIN", upstream)

    with accel.cycle_local_cache_scope() as cache:
        with pytest.raises(RuntimeError, match="join failed"):
            accel.reconstruct_event_context_step20b(_pbp(), _rotation())
        with pytest.raises(RuntimeError, match="join failed"):
            accel.reconstruct_event_context_step20b(_pbp(), _rotation())
        stats = accel.cache_stats(cache)

    assert calls == 2
    assert stats["entries"]["event_reconstruction"] == 0
    assert stats["stats"]["event_reconstruction"] == {"hits": 0, "misses": 0}
    assert stats["event_reconstruction_inflight"] == 0


def test_installer_binds_lower_level_join_and_preserves_frozen_settings():
    status = accel.install_step20b_runtime_acceleration()

    assert status["installed"] is True
    assert status["all_bindings_active"] is True
    assert status["bindings"]["event_reconstruction"] is True
    assert event_lineup._join is accel.reconstruct_event_context_step20b

    guards = status["guardrails"]
    assert guards["cache_scope"] == "single_step12b_call_only"
    assert guards["cached_values_returned_by_deepcopy"] is True
    assert guards["exceptions_cached"] is False
    assert guards["lower_level_event_lineup_possession_reconstruction_reuse"] is True
    assert guards["event_reconstruction_exact_source_content_fingerprint"] is True
    assert guards["event_reconstruction_one_builder_waiters"] is True
    assert guards["event_reconstruction_timing_uses_monotonic_clock"] is True
    assert guards["event_reconstruction_timing_unit"] == "milliseconds"
    assert guards["projection_math_modified"] is False
    assert guards["readiness_relaxed"] is False
    assert guards["monte_carlo_simulation_count_modified"] is False
    assert guards["monte_carlo_batch_size_modified"] is False
    assert guards["sportsbook_transport_modified"] is False
    assert guards["persistence_modified"] is False
    assert guards["wagering_enabled"] is False

    assert step12b.CERTIFIED_SIMULATIONS == 5_000_000
    assert step12b.CERTIFIED_BATCH_SIZE == 250_000
