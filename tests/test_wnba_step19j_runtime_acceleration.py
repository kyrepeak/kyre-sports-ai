from __future__ import annotations

import unittest
from unittest.mock import patch

from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_projection_input_snapshot as snapshot
from sports_api import wnba_step19g_hosted_provider_trace as step19g
from sports_api import wnba_step19j_runtime_acceleration as step19j
from sports_api import wnba_step7g_first_party_team_history as history_base
from sports_api import wnba_step7g_first_party_team_history_cup_safe as cup_safe


class Step19JCycleLocalCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        with step19j._LOCK:
            step19j._TOTAL_REST_HITS = 0
            step19j._TOTAL_REST_MISSES = 0
            step19j._CYCLE_COUNT = 0
            step19j._LAST_CYCLE = None

    def test_same_game_is_loaded_once_per_cycle_and_returned_by_deepcopy(self) -> None:
        calls = []

        def fake(game_id, season, *, include_observed_workload=True):
            calls.append((game_id, season, include_observed_workload))
            return {"game_id": game_id, "season": season, "nested": {"value": 1}}

        token = step19j._ACTIVE_GAME_CACHE.set({})
        try:
            with patch.object(step19j, "_ORIGINAL_GAME_REST", side_effect=fake):
                first = step19j.get_game_rest_travel_context_step19j("1022600001", 2026)
                first["nested"]["value"] = 99
                second = step19j.get_game_rest_travel_context_step19j("1022600001", 2026)
        finally:
            step19j._ACTIVE_GAME_CACHE.reset(token)

        self.assertEqual(len(calls), 1)
        self.assertEqual(second["nested"]["value"], 1)
        self.assertEqual(step19j._TOTAL_REST_MISSES, 1)
        self.assertEqual(step19j._TOTAL_REST_HITS, 1)

    def test_cache_is_fresh_for_every_step12b_call(self) -> None:
        calls = []

        def fake_rest(game_id, season, *, include_observed_workload=True):
            calls.append((game_id, season, include_observed_workload))
            return {"game_id": game_id, "season": season}

        def fake_upstream(*_args, **_kwargs):
            a = step19j.get_game_rest_travel_context_step19j("1022600001", 2026)
            b = step19j.get_game_rest_travel_context_step19j("1022600001", 2026)
            return {"a": a, "b": b}

        old_upstream = step19j._UPSTREAM_RUN_STEP12B
        try:
            step19j._UPSTREAM_RUN_STEP12B = fake_upstream
            with patch.object(step19j, "_ORIGINAL_GAME_REST", side_effect=fake_rest):
                step19j.run_step12b_with_cycle_local_context({})
                self.assertIsNone(step19j._ACTIVE_GAME_CACHE.get())
                step19j.run_step12b_with_cycle_local_context({})
                self.assertIsNone(step19j._ACTIVE_GAME_CACHE.get())
        finally:
            step19j._UPSTREAM_RUN_STEP12B = old_upstream

        self.assertEqual(len(calls), 2)
        self.assertEqual(step19j._TOTAL_REST_MISSES, 2)
        self.assertEqual(step19j._TOTAL_REST_HITS, 2)
        self.assertEqual(step19j._CYCLE_COUNT, 2)

    def test_exception_is_not_cached_and_cycle_context_is_always_cleared(self) -> None:
        def boom(*_args, **_kwargs):
            raise RuntimeError("expected")

        old_upstream = step19j._UPSTREAM_RUN_STEP12B
        try:
            step19j._UPSTREAM_RUN_STEP12B = boom
            with self.assertRaisesRegex(RuntimeError, "expected"):
                step19j.run_step12b_with_cycle_local_context({})
        finally:
            step19j._UPSTREAM_RUN_STEP12B = old_upstream
        self.assertIsNone(step19j._ACTIVE_GAME_CACHE.get())
        self.assertEqual((step19j._LAST_CYCLE or {}).get("status"), "raised")


class Step19JTeamHistoryCacheTests(unittest.TestCase):
    def tearDown(self) -> None:
        cup_safe.restore_base_marker_for_tests()

    def test_idempotent_cup_install_preserves_valid_team_history_cache(self) -> None:
        cup_safe.restore_base_marker_for_tests()
        cup_safe.install_exact_cup_exclusion()
        sentinel = {
            ("phoenix-mercury", 2026, "Regular Season"): {
                "dataset": {"sentinel": True},
                "expires_at": 10**30,
            }
        }
        history_base._CACHE.clear()
        history_base._CACHE.update(sentinel)
        cup_safe.install_exact_cup_exclusion()
        self.assertEqual(history_base._CACHE, sentinel)

    def test_real_overlay_transition_invalidates_old_team_history_cache(self) -> None:
        cup_safe.restore_base_marker_for_tests()
        history_base._CACHE[("phoenix-mercury", 2026, "Regular Season")] = {
            "dataset": {"stale": True},
            "expires_at": 10**30,
        }
        cup_safe.install_exact_cup_exclusion()
        self.assertEqual(history_base._CACHE, {})


class Step19JInstallationTests(unittest.TestCase):
    def test_install_wraps_existing_step19g_chain_and_preserves_guardrails(self) -> None:
        # Run in this isolated test process so process-global compatibility seams
        # cannot contaminate the frozen provider regression process.
        step19g.install_step19g_hosted_provider_trace()
        upstream = step12b.run_step12b_live_runtime_job
        status = step19j.install_step19j_runtime_acceleration()
        self.assertIs(step19j._UPSTREAM_RUN_STEP12B, upstream)
        self.assertIs(step12b.run_step12b_live_runtime_job, step19j.run_step12b_with_cycle_local_context)
        self.assertIs(snapshot.get_game_rest_travel_context, step19j.get_game_rest_travel_context_step19j)
        self.assertTrue(status["installed"])
        self.assertTrue(status["step12b_wrapper_active"])
        self.assertTrue(status["game_rest_cycle_cache_active"])
        guards = status["guardrails"]
        self.assertFalse(guards["monte_carlo_simulation_count_modified"])
        self.assertFalse(guards["monte_carlo_batch_size_modified"])
        self.assertFalse(guards["projection_math_modified"])
        self.assertFalse(guards["readiness_relaxed"])
        self.assertFalse(guards["wagering_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
