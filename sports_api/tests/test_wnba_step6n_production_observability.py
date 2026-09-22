from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.wnba_step6n_production_observability as s


NOW = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)


def step6m(authorized=True, ready=True):
    return {"scheduler_cycle_ready": ready, "step_6l": {"step_6k": {"scheduler_authorized": authorized}}}


def feed(ready=True):
    return {"ready": ready, "mode": "kyre", "feed_exists": ready, "feed_valid": ready, "offer_count": 10, "configuration_error": None if ready else "missing"}


def run(outcome="published_new_board", due_seconds=60, provider="kyre", attempted=True):
    return {
        "run_id": "run-1", "outcome": outcome,
        "completed_at_utc": NOW.isoformat(),
        "next_due_at_utc": (NOW + timedelta(seconds=due_seconds)).isoformat(),
        "provider_collection_attempted": attempted,
        "board_rebuild_attempted": attempted,
        "selected_provider_id": provider,
        "publication_id": "pub-1",
    }


def store(runs=None, ready=True):
    rows = list(runs or [])
    return {"ready": ready, "store_exists": ready, "read_only": True, "error": None if ready else "missing store", "latest_scheduler_run": rows[0] if rows else None, "recent_scheduler_runs": rows, "latest_publication": None}


class Step6NTests(unittest.TestCase):
    def report(self, m=None, f=None, st=None):
        return s.build_step6n_production_observability(
            date="2026-08-26", season=2026, now_utc=NOW, env={},
            step6m_getter=lambda **_: m if m is not None else step6m(),
            feed_getter=lambda **_: f if f is not None else feed(),
            store_reader=lambda **_: st if st is not None else store([run()]),
        )

    def test_01_deferred_is_safe(self):
        report = self.report(step6m(False, False), feed(False), store(ready=False))
        self.assertEqual("safe_deferred", report["state"])
        self.assertTrue(report["healthy"])
        self.assertFalse(report["incident_active"])

    def test_02_active_on_time_is_healthy(self):
        self.assertEqual("healthy", self.report()["state"])

    def test_03_missing_store_is_critical(self):
        self.assertEqual("critical", self.report(st=store(ready=False))["state"])

    def test_04_missing_feed_is_critical_for_playable_cycle(self):
        self.assertEqual("critical", self.report(f=feed(False))["state"])

    def test_05_closed_slate_does_not_require_feed(self):
        closed = run(outcome="pregame_closed", provider=None, attempted=False)
        self.assertEqual("healthy", self.report(f=feed(False), st=store([closed]))["state"])

    def test_06_overdue_changes_health(self):
        self.assertEqual("degraded", self.report(st=store([run(due_seconds=-180)]))["state"])
        self.assertEqual("critical", self.report(st=store([run(due_seconds=-900)]))["state"])

    def test_07_repeated_failures_are_critical(self):
        rows = [run(outcome="provider_cycle_failed") for _ in range(3)]
        self.assertEqual("critical", self.report(st=store(rows))["state"])

    def test_08_unexpected_provider_is_critical(self):
        self.assertEqual("critical", self.report(st=store([run(provider="unexpected")]))["state"])

    def test_09_store_reader_uses_existing_database_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "board.sqlite3"
            conn = sqlite3.connect(path)
            conn.executescript("CREATE TABLE wnba_board_scheduler_runs(run_id TEXT,run_json TEXT,completed_at_utc TEXT,date TEXT,season INTEGER); CREATE TABLE wnba_board_publications(publication_id TEXT,publication_json TEXT,published_at_utc TEXT,date TEXT,season INTEGER);")
            conn.execute("INSERT INTO wnba_board_scheduler_runs VALUES(?,?,?,?,?)", ("run-1", json.dumps(run()), NOW.isoformat(), "2026-08-26", 2026))
            conn.commit(); conn.close()
            before = path.read_bytes()
            snapshot = s.read_scheduler_store_snapshot(date="2026-08-26", season=2026, board_store_path=path, env={})
            self.assertTrue(snapshot["ready"])
            self.assertEqual(before, path.read_bytes())

    def test_10_api_is_get_only(self):
        import sports_api.api.wnba_step6n_production_observability as api
        app = FastAPI(); app.include_router(api.router); client = TestClient(app)
        with patch.object(api, "build_step6n_production_observability", return_value={"state": "safe_deferred"}), patch.object(api, "build_step6n_health", return_value={"status": "safe_deferred", "healthy": True}):
            self.assertEqual(200, client.get("/api/v1/wnba/runtime/step6n-health").status_code)
            self.assertEqual(405, client.post("/api/v1/wnba/runtime/step6n-health").status_code)


if __name__ == "__main__":
    unittest.main()
