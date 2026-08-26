from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import sports_api.api.wnba_pregame_board_scheduler_runtime as api
import sports_api.database.wnba_current_board_store as board_store
import sports_api.wnba_pregame_board_scheduler as step5p
import sports_api.wnba_production_runtime_readiness as r
from sports_api.main import app

NOW = datetime(2026, 8, 26, 21, 0, 0, tzinfo=timezone.utc)
DATE = "2026-08-26"
SEASON = 2026


class Step5RTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.board_path = root / "board.sqlite3"
        self.feed_path = root / "feed.sqlite3"
        self.backtest_path = root / "backtest.sqlite3"
        self.lock_path = root / "scheduler_lock.sqlite3"
        self.secret = "step-5r-test-secret-material-1234567890"
        self.env = {
            r.ACTIVATION_ENV: "true",
            "WNBA_CURRENT_BOARD_STORE_PATH": str(self.board_path),
            "WNBA_PROP_FEED_STORE_PATH": str(self.feed_path),
            "WNBA_BACKTEST_STORE_PATH": str(self.backtest_path),
            "WNBA_BOARD_SCHEDULER_LOCK_PATH": str(self.lock_path),
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET": self.secret,
            "SPORTSGAMEODDS_API_KEY": "demo-key",
            "WNBA_BOARD_SCHEDULER_ENABLED": "true",
            "WNBA_BOARD_AUTO_ARCHIVE_ENABLED": "true",
        }

    def tearDown(self):
        api._stop_runtime_worker()
        self.tmp.cleanup()

    def readiness(self, env=None):
        return r.get_production_runtime_readiness(env=self.env if env is None else env, now_utc=NOW)

    def test_01_good_production_configuration_is_ready(self):
        report = self.readiness()
        self.assertTrue(report["preflight_ready"])
        self.assertTrue(report["scheduler_allowed"])

    def test_02_activation_is_explicit_fail_closed_switch(self):
        env = dict(self.env)
        env.pop(r.ACTIVATION_ENV)
        report = self.readiness(env)
        self.assertTrue(report["preflight_ready"])
        self.assertFalse(report["scheduler_allowed"])
        self.assertFalse(report["activation_requested"])

    def test_03_missing_board_path_blocks(self):
        env = dict(self.env)
        env.pop("WNBA_CURRENT_BOARD_STORE_PATH")
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_04_missing_feed_path_blocks(self):
        env = dict(self.env)
        env.pop("WNBA_PROP_FEED_STORE_PATH")
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_05_missing_backtest_path_blocks(self):
        env = dict(self.env)
        env.pop("WNBA_BACKTEST_STORE_PATH")
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_06_relative_board_path_blocks(self):
        env = dict(self.env)
        env["WNBA_CURRENT_BOARD_STORE_PATH"] = "relative/board.sqlite3"
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_07_relative_feed_path_blocks(self):
        env = dict(self.env)
        env["WNBA_PROP_FEED_STORE_PATH"] = "relative/feed.sqlite3"
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_08_relative_backtest_path_blocks(self):
        env = dict(self.env)
        env["WNBA_BACKTEST_STORE_PATH"] = "relative/backtest.sqlite3"
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_09_weak_signing_secret_blocks(self):
        env = dict(self.env)
        env["WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"] = "too-short"
        report = self.readiness(env)
        self.assertFalse(report["preflight_ready"])
        self.assertFalse(report["archive_signing"]["minimum_32_bytes_pass"])

    def test_10_missing_provider_blocks(self):
        env = dict(self.env)
        env.pop("SPORTSGAMEODDS_API_KEY")
        report = self.readiness(env)
        self.assertFalse(report["preflight_ready"])
        self.assertFalse(report["provider"]["ready"])

    def test_11_disabled_step5p_scheduler_blocks(self):
        env = dict(self.env)
        env["WNBA_BOARD_SCHEDULER_ENABLED"] = "false"
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_12_disabled_auto_archive_blocks(self):
        env = dict(self.env)
        env["WNBA_BOARD_AUTO_ARCHIVE_ENABLED"] = "false"
        self.assertFalse(self.readiness(env)["preflight_ready"])

    def test_13_lock_path_can_be_derived_beside_board_store(self):
        env = dict(self.env)
        env.pop("WNBA_BOARD_SCHEDULER_LOCK_PATH")
        report = self.readiness(env)
        self.assertTrue(report["preflight_ready"])
        self.assertFalse(report["paths"]["scheduler_lock_path_explicit"])
        self.assertTrue(report["warnings"])

    def test_14_explicit_lock_path_has_no_derivation_warning(self):
        report = self.readiness()
        self.assertTrue(report["paths"]["scheduler_lock_path_explicit"])
        self.assertEqual([], report["warnings"])

    def test_15_lock_path_cannot_equal_board_store(self):
        env = dict(self.env)
        env["WNBA_BOARD_SCHEDULER_LOCK_PATH"] = str(self.board_path)
        report = self.readiness(env)
        self.assertFalse(report["preflight_ready"])

    def test_16_runtime_stores_are_initialized(self):
        self.readiness()
        self.assertTrue(self.board_path.exists())
        self.assertTrue(self.feed_path.exists())
        self.assertTrue(self.backtest_path.exists())
        self.assertTrue(self.lock_path.exists())

    def test_17_secret_value_is_never_returned(self):
        report = self.readiness()
        self.assertNotIn(self.secret, repr(report))

    def test_18_restart_without_state_runs_immediate_recovery_cycle(self):
        report = self.readiness()
        self.assertEqual("run_immediate_recovery_cycle", report["restart_recovery"]["strategy"])

    def test_19_restart_uses_persisted_next_due(self):
        board_store.initialize_store(self.board_path, env=self.env)
        run = step5p._build_scheduler_run(
            target_date=DATE,
            season=SEASON,
            started_at_utc=NOW - timedelta(minutes=1),
            completed_at_utc=NOW - timedelta(minutes=1),
            outcome="prior_cycle",
            provider_collection_attempted=True,
            board_rebuild_attempted=False,
            next_due_at_utc=NOW + timedelta(minutes=5),
        )
        board_store.append_scheduler_run(run, path=self.board_path, env=self.env)
        report = self.readiness()
        self.assertEqual("resume_from_persisted_next_due", report["restart_recovery"]["strategy"])

    def test_20_configuration_fingerprint_is_deterministic(self):
        one = self.readiness()["configuration_fingerprint_sha256"]
        two = self.readiness()["configuration_fingerprint_sha256"]
        self.assertEqual(one, two)
        self.assertEqual(64, len(one))

    def test_21_require_runtime_ready_returns_report(self):
        report = r.require_production_runtime_ready(env=self.env, now_utc=NOW)
        self.assertTrue(report["scheduler_allowed"])

    def test_22_require_runtime_ready_rejects_disabled_activation(self):
        env = dict(self.env)
        env[r.ACTIVATION_ENV] = "false"
        with self.assertRaises(r.WNBAProductionRuntimeNotReadyError):
            r.require_production_runtime_ready(env=env, now_utc=NOW)

    def test_23_preflight_is_network_free_by_contract(self):
        report = self.readiness()
        self.assertTrue(report["semantics"]["preflight_is_network_free"])
        self.assertTrue(report["semantics"]["failed_preflight_blocks_sportsbook_collection"])
        self.assertTrue(report["semantics"]["failed_preflight_blocks_monte_carlo_rebuild"])

    def test_24_main_registers_current_routes(self):
        paths = set(app.openapi().get("paths", {}))
        for path in {
            "/api/v1/wnba/rankings/player-props/current",
            "/api/v1/wnba/rankings/player-props/current/refresh",
            "/api/v1/wnba/rankings/player-props/current/status",
            "/api/v1/wnba/rankings/player-props/current/history",
        }:
            self.assertIn(path, paths)

    def test_25_main_registers_runtime_routes(self):
        paths = set(app.openapi().get("paths", {}))
        self.assertIn("/api/v1/wnba/runtime/readiness", paths)
        self.assertIn("/api/v1/wnba/runtime/health", paths)

    def test_26_manual_refresh_blocks_before_step5q_when_gate_red(self):
        env = dict(self.env)
        env[r.ACTIVATION_ENV] = "false"
        with patch.dict(os.environ, env, clear=True), \
             patch.object(api.step5q, "refresh_current_wnba_player_prop_board") as delegated:
            with self.assertRaises(HTTPException) as ctx:
                api.refresh_current_wnba_player_prop_board(date=DATE, season=SEASON, provider_ids=None, force=True)
        self.assertEqual(503, ctx.exception.status_code)
        delegated.assert_not_called()

    def test_27_manual_refresh_delegates_after_green_gate(self):
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(api.step5q, "refresh_current_wnba_player_prop_board", return_value={"outcome": "ok"}) as delegated:
            result = api.refresh_current_wnba_player_prop_board(date=DATE, season=SEASON, provider_ids="x", force=True)
        self.assertEqual("ok", result["outcome"])
        delegated.assert_called_once()

    def test_28_runtime_health_is_503_when_not_activated(self):
        env = dict(self.env)
        env[r.ACTIVATION_ENV] = "false"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                api.get_wnba_production_runtime_health()
        self.assertEqual(503, ctx.exception.status_code)

    def test_29_runtime_health_is_200_shape_when_ready(self):
        with patch.dict(os.environ, self.env, clear=True):
            result = api.get_wnba_production_runtime_health()
        self.assertEqual("ready", result["status"])
        self.assertTrue(result["scheduler_allowed"])

    def test_30_read_path_remains_available_when_activation_is_off(self):
        env = dict(self.env)
        env[r.ACTIVATION_ENV] = "false"
        with patch.dict(os.environ, env, clear=True), \
             patch.object(api.step5q, "get_current_wnba_player_prop_board", return_value={"publication_id": "p"}) as delegated:
            result = api.get_current_wnba_player_prop_board(date=DATE, season=SEASON, require_current=True)
        self.assertEqual("p", result["publication_id"])
        delegated.assert_called_once()

    def test_31_status_adds_step5r_runtime_section(self):
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(api.step5q, "get_current_wnba_player_prop_scheduler_status", return_value={"ok": True}):
            result = api.get_current_wnba_player_prop_scheduler_status(date=DATE, season=SEASON)
        self.assertIn("production_runtime", result)
        self.assertTrue(result["production_runtime"]["readiness"]["scheduler_allowed"])

    def test_32_startup_does_not_start_worker_when_activation_is_off(self):
        env = dict(self.env)
        env[r.ACTIVATION_ENV] = "false"
        with patch.dict(os.environ, env, clear=True):
            api._start_runtime_worker()
        self.assertIsNone(api._runtime_worker_thread)
        self.assertFalse(api._runtime_worker_state["startup_scheduler_allowed"])
        self.assertFalse(api._runtime_worker_state["startup_activation_requested"])

    def test_33_history_delegates_to_frozen_step5q(self):
        with patch.object(api.step5q, "get_current_wnba_player_prop_publication_history", return_value={"publication_count": 1}) as delegated:
            result = api.get_current_wnba_player_prop_publication_history(date=DATE, season=SEASON, publication_limit=5, run_limit=5)
        self.assertEqual(1, result["publication_count"])
        delegated.assert_called_once()

    def test_34_step5r_declares_frozen_step5q_authority(self):
        report = self.readiness()
        self.assertTrue(report["semantics"]["step_5q_distributed_lock_remains_authoritative"])
        self.assertTrue(report["semantics"]["frozen_step_5p_model_and_publication_semantics_are_unchanged"])

    def test_35_activated_worker_starts_fail_closed_supervisor_even_if_preflight_red(self):
        env = dict(self.env)
        env["WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"] = "short"
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = False
        with patch.dict(os.environ, env, clear=True), \
             patch.object(api.threading, "Thread", return_value=fake_thread), \
             patch.object(api.step5q, "get_scheduler_configuration", return_value={"loop_seconds": 30}):
            api._start_runtime_worker()
        self.assertTrue(api._runtime_worker_state["startup_activation_requested"])
        self.assertFalse(api._runtime_worker_state["startup_scheduler_allowed"])
        fake_thread.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
