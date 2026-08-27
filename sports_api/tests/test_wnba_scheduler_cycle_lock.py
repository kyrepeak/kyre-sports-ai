from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import sports_api.api.wnba_pregame_board_scheduler_distributed as api
import sports_api.database.wnba_current_board_store as board_store
import sports_api.database.wnba_scheduler_cycle_lock as lock_store
import sports_api.wnba_pregame_board_scheduler as step5p
from sports_api.main import app

NOW = datetime(2026, 8, 26, 21, 0, 0, tzinfo=timezone.utc)
DATE = "2026-08-26"
SEASON = 2026


class Step5QTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.board_path = root / "board.sqlite3"
        self.feed_path = root / "feed.sqlite3"
        self.lock_path = root / "board.scheduler_lock.sqlite3"
        self.env = {
            board_store.STORE_PATH_ENV: str(self.board_path),
            "WNBA_PROP_FEED_STORE_PATH": str(self.feed_path),
            "SPORTSGAMEODDS_API_KEY": "demo-key",
        }
        with lock_store._initialized_paths_lock:
            lock_store._initialized_paths.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def acquire(self, owner="worker-a"):
        return lock_store.try_acquire_cycle_lock(owner, env=self.env, now_utc=NOW)

    def test_01_lock_path_derives_beside_board_store(self):
        path = lock_store.resolve_lock_path(env=self.env)
        self.assertEqual(self.lock_path, path)

    def test_02_explicit_lock_path_is_respected(self):
        explicit = Path(self.tmp.name) / "custom.sqlite3"
        env = dict(self.env)
        env[lock_store.LOCK_PATH_ENV] = str(explicit)
        self.assertEqual(explicit, lock_store.resolve_lock_path(env=env))

    def test_03_lock_database_cannot_equal_board_database(self):
        env = dict(self.env)
        env[lock_store.LOCK_PATH_ENV] = str(self.board_path)
        with self.assertRaises(lock_store.WNBASchedulerCycleLockConfigurationError):
            lock_store.resolve_lock_path(env=env)

    def test_04_initialize_creates_dedicated_store(self):
        result = lock_store.initialize_lock_store(env=self.env)
        self.assertTrue(self.lock_path.exists())
        self.assertTrue(result["separate_from_board_store"])

    def test_05_first_worker_acquires(self):
        handle = self.acquire()
        self.assertIsNotNone(handle)
        lock_store.release_cycle_lock(handle, now_utc=NOW)

    def test_06_second_worker_is_blocked(self):
        first = self.acquire("worker-a")
        try:
            second = self.acquire("worker-b")
            self.assertIsNone(second)
        finally:
            lock_store.release_cycle_lock(first, now_utc=NOW)

    def test_07_release_allows_next_worker(self):
        first = self.acquire("worker-a")
        lock_store.release_cycle_lock(first, now_utc=NOW)
        second = self.acquire("worker-b")
        self.assertIsNotNone(second)
        lock_store.release_cycle_lock(second, now_utc=NOW)

    def test_08_schema_fast_path_still_detects_live_lock(self):
        first = self.acquire("worker-a")
        try:
            with lock_store._initialized_paths_lock:
                lock_store._initialized_paths.clear()
            second = self.acquire("worker-b")
            self.assertIsNone(second)
        finally:
            lock_store.release_cycle_lock(first, now_utc=NOW)

    def test_09_probe_true_when_free(self):
        self.assertTrue(lock_store.probe_cycle_lock_available(env=self.env))

    def test_10_probe_false_when_held(self):
        first = self.acquire()
        try:
            self.assertFalse(lock_store.probe_cycle_lock_available(env=self.env))
        finally:
            lock_store.release_cycle_lock(first, now_utc=NOW)

    def test_11_connection_close_releases_crashed_worker_lock(self):
        first = self.acquire("crashed-worker")
        first.connection.close()
        first.released = True
        second = self.acquire("replacement-worker")
        self.assertIsNotNone(second)
        lock_store.release_cycle_lock(second, now_utc=NOW)

    def test_12_release_records_append_only_history(self):
        handle = self.acquire()
        event = lock_store.release_cycle_lock(
            handle,
            outcome="published_new_board",
            detail={"publication_id": "pub-1"},
            now_utc=NOW,
        )
        history = lock_store.list_lock_history(env=self.env)
        self.assertEqual(event["event_id"], history[0]["event_id"])
        self.assertEqual("published_new_board", history[0]["outcome"])
        self.assertEqual("pub-1", history[0]["detail"]["publication_id"])

    def test_13_lock_history_cannot_update(self):
        handle = self.acquire()
        lock_store.release_cycle_lock(handle, now_utc=NOW)
        conn = sqlite3.connect(self.lock_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE wnba_scheduler_lock_history SET outcome='tampered'")
        finally:
            conn.close()

    def test_14_lock_history_cannot_delete(self):
        handle = self.acquire()
        lock_store.release_cycle_lock(handle, now_utc=NOW)
        conn = sqlite3.connect(self.lock_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM wnba_scheduler_lock_history")
        finally:
            conn.close()

    def test_15_history_limit_validates(self):
        with self.assertRaises(ValueError):
            lock_store.list_lock_history(limit=0, env=self.env)

    def test_16_double_release_rejected(self):
        handle = self.acquire()
        lock_store.release_cycle_lock(handle, now_utc=NOW)
        with self.assertRaises(lock_store.WNBASchedulerCycleLockError):
            lock_store.release_cycle_lock(handle, now_utc=NOW)

    def test_17_empty_owner_rejected(self):
        with self.assertRaises(lock_store.WNBASchedulerCycleLockConfigurationError):
            lock_store.try_acquire_cycle_lock(" ", env=self.env)

    def test_18_negative_timeout_rejected(self):
        with self.assertRaises(lock_store.WNBASchedulerCycleLockConfigurationError):
            lock_store.try_acquire_cycle_lock("worker", env=self.env, timeout_seconds=-1)

    def test_19_board_store_remains_writable_while_cycle_lock_held(self):
        handle = self.acquire()
        try:
            result = board_store.initialize_store(self.board_path, env=self.env)
            self.assertEqual(str(self.board_path), result["store_path"])
        finally:
            lock_store.release_cycle_lock(handle, now_utc=NOW)

    def test_20_status_reports_cross_process_semantics(self):
        status = lock_store.get_cycle_lock_status(env=self.env)
        self.assertTrue(status["available_now"])
        self.assertTrue(status["semantics"]["single_cycle_across_worker_processes"])
        self.assertTrue(status["semantics"]["process_crash_does_not_leave_stale_lock"])

    def test_21_main_registers_current_routes(self):
        paths = app.openapi().get("paths", {})
        self.assertIn("/api/v1/wnba/rankings/player-props/current", paths)
        self.assertIn("/api/v1/wnba/rankings/player-props/current/refresh", paths)
        self.assertIn("post", paths["/api/v1/wnba/rankings/player-props/current/refresh"])
        self.assertIn("/api/v1/wnba/rankings/player-props/current/status", paths)
        self.assertIn("/api/v1/wnba/rankings/player-props/current/history", paths)

    def test_22_provider_parser_preserved(self):
        self.assertEqual(["a", "b"], api._provider_ids("a, b"))

    def test_23_manual_refresh_rejects_other_worker_owner(self):
        with patch.dict(os.environ, self.env, clear=False):
            first = lock_store.try_acquire_cycle_lock("other-worker")
            try:
                with patch.object(api, "run_pregame_board_cycle") as run:
                    with self.assertRaises(HTTPException) as ctx:
                        api.refresh_current_wnba_player_prop_board(
                            date=DATE,
                            season=SEASON,
                            provider_ids=None,
                            force=True,
                        )
                self.assertEqual(409, ctx.exception.status_code)
                run.assert_not_called()
            finally:
                lock_store.release_cycle_lock(first, now_utc=NOW)

    def test_24_manual_refresh_runs_when_lock_is_free(self):
        fake = {"outcome": "skipped_not_due"}
        with patch.dict(os.environ, self.env, clear=False), \
             patch.object(api, "run_pregame_board_cycle", return_value=fake) as run:
            result = api.refresh_current_wnba_player_prop_board(
                date=DATE,
                season=SEASON,
                provider_ids="a,b",
                force=False,
            )
        self.assertEqual(fake, result)
        run.assert_called_once()
        history = lock_store.list_lock_history(env=self.env)
        self.assertEqual("skipped_not_due", history[0]["outcome"])

    def test_25_cycle_exception_releases_cross_process_lock(self):
        with patch.dict(os.environ, self.env, clear=False), \
             patch.object(
                 api,
                 "run_pregame_board_cycle",
                 side_effect=step5p.WNBAPregameBoardSchedulerModelInputError("bad"),
             ):
            with self.assertRaises(HTTPException) as ctx:
                api.refresh_current_wnba_player_prop_board(
                    date=DATE,
                    season=SEASON,
                    provider_ids=None,
                    force=True,
                )
        self.assertEqual(422, ctx.exception.status_code)
        replacement = self.acquire("replacement")
        self.assertIsNotNone(replacement)
        lock_store.release_cycle_lock(replacement, now_utc=NOW)

    def test_26_background_worker_skips_without_model_work_on_contention(self):
        with patch.dict(os.environ, self.env, clear=False):
            first = lock_store.try_acquire_cycle_lock("other-worker")
            try:
                with patch.object(api, "run_pregame_board_cycle") as run:
                    result = api._run_one_background_cycle()
                self.assertEqual("skipped_cross_process_lock", result["outcome"])
                self.assertFalse(result["provider_collection_attempted"])
                run.assert_not_called()
            finally:
                lock_store.release_cycle_lock(first, now_utc=NOW)

    def test_27_background_worker_runs_step5p_when_free(self):
        fake = {"outcome": "feed_unchanged_model_refresh_not_due"}
        with patch.dict(os.environ, self.env, clear=False), \
             patch.object(api, "run_pregame_board_cycle", return_value=fake):
            result = api._run_one_background_cycle()
        self.assertEqual(fake, result)
        self.assertEqual(
            "feed_unchanged_model_refresh_not_due",
            lock_store.list_lock_history(env=self.env)[0]["outcome"],
        )

    def test_28_status_includes_step5q_lock(self):
        with patch.dict(os.environ, self.env, clear=False), \
             patch.object(api, "get_scheduler_status", return_value={"configuration": {}}):
            status = api.get_current_wnba_player_prop_scheduler_status(date=DATE, season=SEASON)
        self.assertIn("cross_process_cycle_lock", status)
        self.assertIn("step_5q", status)
        self.assertTrue(status["step_5q"]["frozen_step_5p_semantics_preserved"])


if __name__ == "__main__":
    unittest.main()
