from __future__ import annotations

import unittest
from unittest.mock import patch

from sports_api import wnba_player_event_features as event_features
from sports_api import wnba_projection_input_snapshot as projection_snapshot
from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19n_fanduel_empty_market as step19n
from sports_api import wnba_step20b_shared_input_cache as step20b
from sports_api import wnba_step7g_first_party_history as first_history
from sports_api import wnba_step7g_first_party_integration as step7g


class Step20BSharedInputCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        with step20b._LOCK:
            step20b._CYCLE_COUNT = 0
            step20b._LAST_CYCLE = None
            for name in step20b._TOTAL_HITS:
                step20b._TOTAL_HITS[name] = 0
                step20b._TOTAL_MISSES[name] = 0

    def _active(self):
        return step20b._ACTIVE_CACHE.set(
            {
                "page_props": {},
                "game_rotation": {},
                "game_sources": {},
                "game_availability": {},
            }
        )

    def test_page_props_loaded_once_per_cycle_and_returned_by_deepcopy(self) -> None:
        calls = []

        def fake(url, *, ttl_seconds):
            calls.append((url, ttl_seconds))
            return {"nested": {"value": 1}}, "2026-08-30T00:00:00+00:00", False, ttl_seconds

        token = self._active()
        try:
            with patch.object(step20b, "_ORIGINAL_REQUEST_PAGE_PROPS", side_effect=fake):
                first = step20b.request_page_props_step20b("https://www.wnba.com/game/1022600001", ttl_seconds=30)
                first[0]["nested"]["value"] = 99
                second = step20b.request_page_props_step20b("https://www.wnba.com/game/1022600001", ttl_seconds=4)
        finally:
            step20b._ACTIVE_CACHE.reset(token)

        self.assertEqual(len(calls), 1)
        self.assertEqual(second[0]["nested"]["value"], 1)
        self.assertTrue(second[2])
        self.assertEqual(second[3], 4)
        self.assertEqual(step20b._TOTAL_MISSES["page_props"], 1)
        self.assertEqual(step20b._TOTAL_HITS["page_props"], 1)

    def test_full_game_rotation_loaded_once_and_deepcopied(self) -> None:
        calls = []

        def fake(game_id, season, *, rotation_stat="PLAYER_PTS"):
            calls.append((game_id, season, rotation_stat))
            return {"game_id": game_id, "away": {"players": [1]}}

        token = self._active()
        try:
            with patch.object(step20b, "_ORIGINAL_GAME_ROTATION", side_effect=fake):
                first = step20b.get_game_rotation_step20b("1022600001", 2026)
                first["away"]["players"].append(2)
                second = step20b.get_game_rotation_step20b("1022600001", 2026)
        finally:
            step20b._ACTIVE_CACHE.reset(token)

        self.assertEqual(len(calls), 1)
        self.assertEqual(second["away"]["players"], [1])
        self.assertEqual(step20b._TOTAL_MISSES["game_rotation"], 1)
        self.assertEqual(step20b._TOTAL_HITS["game_rotation"], 1)

    def test_step4u_game_sources_loaded_once_and_both_objects_deepcopied(self) -> None:
        calls = []

        def fake(game_id, season):
            calls.append((game_id, season))
            return ({"events": [{"id": 1}]}, {"possessions": [{"id": 2}]})

        token = self._active()
        try:
            with patch.object(step20b, "_ORIGINAL_GAME_SOURCES", side_effect=fake):
                first = step20b.game_sources_step20b("1022600001", 2026)
                first[0]["events"][0]["id"] = 99
                first[1]["possessions"][0]["id"] = 99
                second = step20b.game_sources_step20b("1022600001", 2026)
        finally:
            step20b._ACTIVE_CACHE.reset(token)

        self.assertEqual(len(calls), 1)
        self.assertEqual(second[0]["events"][0]["id"], 1)
        self.assertEqual(second[1]["possessions"][0]["id"], 2)
        self.assertEqual(step20b._TOTAL_MISSES["game_sources"], 1)
        self.assertEqual(step20b._TOTAL_HITS["game_sources"], 1)

    def test_full_game_availability_loaded_once_and_deepcopied(self) -> None:
        calls = []

        def fake(game_id, target_date, season, *, last_n_games=5, report_url=None, lookback_hours=36):
            calls.append((game_id, target_date, season, last_n_games, report_url, lookback_hours))
            return {"game_id": game_id, "away": {"players": [{"player_id": 1}]}}

        token = self._active()
        try:
            with patch.object(step20b, "_ORIGINAL_GAME_AVAILABILITY", side_effect=fake):
                first = step20b.get_game_availability_context_dataset_step20b(
                    "1022600001", "2026-08-30", 2026, last_n_games=5
                )
                first["away"]["players"][0]["player_id"] = 99
                second = step20b.get_game_availability_context_dataset_step20b(
                    "1022600001", "2026-08-30", 2026, last_n_games=5
                )
        finally:
            step20b._ACTIVE_CACHE.reset(token)

        self.assertEqual(len(calls), 1)
        self.assertEqual(second["away"]["players"][0]["player_id"], 1)
        self.assertEqual(step20b._TOTAL_MISSES["game_availability"], 1)
        self.assertEqual(step20b._TOTAL_HITS["game_availability"], 1)

    def test_exceptions_are_not_cached(self) -> None:
        calls = []

        def boom(game_id, season, *, rotation_stat="PLAYER_PTS"):
            calls.append((game_id, season, rotation_stat))
            raise RuntimeError("expected")

        token = self._active()
        try:
            with patch.object(step20b, "_ORIGINAL_GAME_ROTATION", side_effect=boom):
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError, "expected"):
                        step20b.get_game_rotation_step20b("1022600001", 2026)
        finally:
            step20b._ACTIVE_CACHE.reset(token)

        self.assertEqual(len(calls), 2)
        self.assertEqual(step20b._TOTAL_HITS["game_rotation"], 0)
        self.assertEqual(step20b._TOTAL_MISSES["game_rotation"], 0)

    def test_cache_is_fresh_for_every_step12b_call_and_always_cleared(self) -> None:
        calls = []

        def fake_page(url, *, ttl_seconds):
            calls.append(url)
            return {"value": len(calls)}, "2026-08-30T00:00:00+00:00", False, ttl_seconds

        def fake_upstream(*_args, **_kwargs):
            a = step20b.request_page_props_step20b("https://www.wnba.com/game/1022600001", ttl_seconds=4)
            b = step20b.request_page_props_step20b("https://www.wnba.com/game/1022600001", ttl_seconds=4)
            return a, b

        old_upstream = step20b._UPSTREAM_RUN_STEP12B
        try:
            step20b._UPSTREAM_RUN_STEP12B = fake_upstream
            with patch.object(step20b, "_ORIGINAL_REQUEST_PAGE_PROPS", side_effect=fake_page):
                step20b.run_step12b_with_shared_input_cache({})
                self.assertIsNone(step20b._ACTIVE_CACHE.get())
                step20b.run_step12b_with_shared_input_cache({})
                self.assertIsNone(step20b._ACTIVE_CACHE.get())
        finally:
            step20b._UPSTREAM_RUN_STEP12B = old_upstream

        self.assertEqual(len(calls), 2)
        self.assertEqual(step20b._TOTAL_MISSES["page_props"], 2)
        self.assertEqual(step20b._TOTAL_HITS["page_props"], 2)
        self.assertEqual(step20b._CYCLE_COUNT, 2)
        self.assertEqual((step20b._LAST_CYCLE or {}).get("status"), "returned")

    def test_raised_step12b_always_clears_cycle_cache(self) -> None:
        def boom(*_args, **_kwargs):
            raise RuntimeError("expected")

        old_upstream = step20b._UPSTREAM_RUN_STEP12B
        try:
            step20b._UPSTREAM_RUN_STEP12B = boom
            with self.assertRaisesRegex(RuntimeError, "expected"):
                step20b.run_step12b_with_shared_input_cache({})
        finally:
            step20b._UPSTREAM_RUN_STEP12B = old_upstream

        self.assertIsNone(step20b._ACTIVE_CACHE.get())
        self.assertEqual((step20b._LAST_CYCLE or {}).get("status"), "raised")
        self.assertEqual((step20b._LAST_CYCLE or {}).get("error_type"), "RuntimeError")


class Step20BInstallationSafetyTests(unittest.TestCase):
    def test_installer_wraps_step19n_without_touching_guarded_step7g_seams(self) -> None:
        env = {"WNBA_STEP7G_FIRST_PARTY_ENABLED": "true"}
        before = step7g.install_step7g_first_party_integration(env)
        self.assertTrue(before["all_core_seams_installed"])

        saved = {
            "run": step12b.run_step12b_live_runtime_job,
            "page": first_history._request_page_props,
            "rotation": rotation.get_game_rotation,
            "sources": event_features._game_sources,
            "availability": projection_snapshot.get_game_availability_context_dataset,
            "upstream": step20b._UPSTREAM_RUN_STEP12B,
            "installed": step20b._INSTALLED,
        }
        try:
            # Present the exact certified Step19N outer wrapper to the installer.
            step12b.run_step12b_live_runtime_job = step19n.run_step12b_fanduel_empty_market_compatible
            first_history._request_page_props = step20b._ORIGINAL_REQUEST_PAGE_PROPS
            rotation.get_game_rotation = step20b._ORIGINAL_GAME_ROTATION
            event_features._game_sources = step20b._ORIGINAL_GAME_SOURCES
            projection_snapshot.get_game_availability_context_dataset = step20b._ORIGINAL_GAME_AVAILABILITY
            step20b._UPSTREAM_RUN_STEP12B = None
            step20b._INSTALLED = False

            status = step20b.install_step20b_shared_input_cache()
            self.assertTrue(status["installed"])
            self.assertTrue(status["step12b_wrapper_active"])
            self.assertTrue(status["upstream_step19n_preserved"])
            self.assertTrue(all(status["helper_seams"].values()))

            # Re-running the Step7G integrity installer must still accept every
            # exact guarded public seam. Step20B patches only lower-level helpers.
            after = step7g.install_step7g_first_party_integration(env)
            self.assertTrue(after["all_core_seams_installed"])

            guards = status["guardrails"]
            self.assertEqual(guards["cache_scope"], "single_step12b_call_only")
            self.assertTrue(guards["cache_cleared_after_every_cycle"])
            self.assertTrue(guards["cached_values_returned_by_deepcopy"])
            self.assertFalse(guards["exceptions_cached"])
            for key in (
                "frozen_step7g_public_provider_seams_modified",
                "player_coverage_modified",
                "exact_line_matching_modified",
                "different_lines_blended",
                "monte_carlo_simulation_count_modified",
                "monte_carlo_batch_size_modified",
                "projection_math_modified",
                "readiness_relaxed",
                "sportsbook_transport_modified",
                "controller_state_modified",
                "durable_lease_policy_modified",
                "persistence_modified",
                "wagering_enabled",
            ):
                self.assertFalse(guards[key], key)
            self.assertEqual(step12b.CERTIFIED_SIMULATIONS, 5_000_000)
            self.assertEqual(step12b.CERTIFIED_BATCH_SIZE, 250_000)
        finally:
            step12b.run_step12b_live_runtime_job = saved["run"]
            first_history._request_page_props = saved["page"]
            rotation.get_game_rotation = saved["rotation"]
            event_features._game_sources = saved["sources"]
            projection_snapshot.get_game_availability_context_dataset = saved["availability"]
            step20b._UPSTREAM_RUN_STEP12B = saved["upstream"]
            step20b._INSTALLED = saved["installed"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
