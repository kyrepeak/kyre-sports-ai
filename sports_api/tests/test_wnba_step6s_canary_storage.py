from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from sports_api.collectors.wnba_kyre_market_feed import (
    KYRE_MARKET_FEED_PATH_ENV,
    write_kyre_market_feed,
)
from sports_api.wnba_step6q_durable_storage import (
    CANARY_LOCK_OBJECT_KEY,
    CANARY_MARKER_OBJECT_KEY,
    FEED_OBJECT_KEY,
    FILESYSTEM_BACKEND,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
    DurableObjectMetadata,
    WNBADurableStorageNotReadyError,
)
from sports_api.wnba_step6r_supabase_storage import (
    SUPABASE_SECRET_KEY_ENV,
    SUPABASE_URL_ENV,
)
import sports_api.wnba_step6j_canary_activation as step6j
import sports_api.wnba_step6s_canary_storage as s


class MemoryDurableStorage:
    backend_id = SUPABASE_BACKEND

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.locked = False
        self.contended = False
        self.lock_entries = 0

    def exists(self, object_key: str) -> bool:
        return object_key in self.objects

    def read_bytes(self, object_key: str, *, max_bytes: int = 5_000_000) -> bytes:
        if object_key not in self.objects:
            raise WNBADurableStorageNotReadyError(f"missing {object_key}")
        payload = self.objects[object_key]
        if len(payload) > max_bytes:
            raise ValueError("test object too large")
        return payload

    def write_bytes_atomic(self, object_key: str, payload: bytes) -> DurableObjectMetadata:
        self.objects[object_key] = bytes(payload)
        return DurableObjectMetadata(
            backend_id=self.backend_id,
            object_key=object_key,
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
        )

    def delete(self, object_key: str) -> bool:
        return self.objects.pop(object_key, None) is not None

    def size_bytes(self, object_key: str) -> int | None:
        payload = self.objects.get(object_key)
        return None if payload is None else len(payload)

    def sha256(self, object_key: str) -> str | None:
        payload = self.objects.get(object_key)
        return None if payload is None else hashlib.sha256(payload).hexdigest()

    def describe(self):
        return {"backend_id": self.backend_id, "implemented": True}

    @contextmanager
    def exclusive_lock(self, lock_key: str):
        if self.contended or self.locked:
            raise WNBADurableStorageNotReadyError(f"contended {lock_key}")
        self.locked = True
        self.lock_entries += 1
        try:
            yield
        finally:
            self.locked = False


class Step6SCanaryStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.host_feed = self.root / "host-feed-must-stay-unused.json"
        self.activation_id = "step6s-test-001"
        self.backend = MemoryDurableStorage()

    def tearDown(self):
        self.tmp.cleanup()

    def feed(self, *, source="test", odds=-110):
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-27",
            "season": 2026,
            "captured_at_utc": "2026-08-27T04:00:00+00:00",
            "feed_source": source,
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": [
                {
                    "sportsbook": "DraftKings",
                    "player_name": "A'ja Wilson",
                    "stat": "points",
                    "side": "over",
                    "line": 24.5,
                    "american_odds": odds,
                }
            ],
        }

    def supabase_env(self):
        return {
            STORAGE_BACKEND_ENV: SUPABASE_BACKEND,
            SUPABASE_URL_ENV: "https://step6s-test.supabase.co",
            SUPABASE_SECRET_KEY_ENV: "sb_secret_step6s_unit_test_placeholder_abcdefghijklmnopqrstuvwxyz",
            KYRE_MARKET_FEED_PATH_ENV: str(self.host_feed),
            step6j.CANARY_ENABLED_ENV: "true",
            step6j.ACTIVATION_ID_ENV: self.activation_id,
            step6j.DIRECT_SYNC_ENABLED_ENV: "true",
            step6j.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
            step6j.RECONCILED_SYNC_ENABLED_ENV: "true",
            step6j.PRODUCTION_RUNTIME_ENV: "false",
        }

    def feed_bytes(self, document):
        path = self.root / "serialize-feed.json"
        write_kyre_market_feed(copy.deepcopy(document), path=path, env={})
        return path.read_bytes()

    def fake_sync(self, document, *, persistent_sha=None):
        def _sync(*, date, season, env, path, **kwargs):
            storage = write_kyre_market_feed(copy.deepcopy(document), path=path, env=env)
            return {
                "synced": True,
                "feed_write_performed": True,
                "storage": storage,
                "persistent_feed_sha256": persistent_sha or s.persistent_feed_sha256(document),
                "snapshot_sha256": "1" * 64,
                "reconciliation_fingerprint_sha256": "2" * 64,
                "attestation_sha256": "3" * 64,
                "offer_side_count": len(document["offers"]),
            }

        return _sync

    def run_supabase(self, new_document):
        env = self.supabase_env()
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
            side_effect=self.fake_sync(new_document),
        ):
            return s.run_storage_aware_step6j_canary(
                date="2026-08-27",
                season=2026,
                activation_id=self.activation_id,
                env=env,
            )

    def test_01_filesystem_dispatch_delegates_to_unchanged_step6j(self):
        env = {STORAGE_BACKEND_ENV: FILESYSTEM_BACKEND}
        expected = {"status": "legacy-filesystem"}
        with patch.object(s, "_legacy_run_step6j_canary", return_value=expected) as legacy:
            result = s.run_storage_aware_step6j_canary(
                date="2026-08-27",
                season=2026,
                activation_id=self.activation_id,
                env=env,
            )
        self.assertEqual(expected, result)
        legacy.assert_called_once()

    def test_02_filesystem_rollback_delegates_to_unchanged_step6j(self):
        env = {STORAGE_BACKEND_ENV: FILESYSTEM_BACKEND}
        expected = {"status": "legacy-rollback"}
        with patch.object(s, "_legacy_rollback_step6j_canary", return_value=expected) as legacy:
            result = s.rollback_storage_aware_step6j_canary(
                activation_id=self.activation_id,
                env=env,
            )
        self.assertEqual(expected, result)
        legacy.assert_called_once()

    def test_03_status_is_network_free_and_filesystem_default(self):
        with patch.object(httpx.Client, "request", side_effect=AssertionError("status must not call network")):
            result = s.get_step6s_canary_storage_status({})
        self.assertEqual(FILESYSTEM_BACKEND, result["selected_backend"])
        self.assertTrue(result["configuration_ready"])
        self.assertTrue(result["filesystem_delegates_to_step6j_unchanged"])
        self.assertFalse(result["safety"]["network_used_by_status"])
        self.assertFalse(result["safety"]["storage_write_performed_by_status"])

    def test_04_supabase_status_is_configuration_only_and_secret_free(self):
        env = self.supabase_env()
        with patch.object(httpx.Client, "request", side_effect=AssertionError("status must not call network")):
            result = s.get_step6s_canary_storage_status(env)
        rendered = json.dumps(result, sort_keys=True)
        self.assertEqual(SUPABASE_BACKEND, result["selected_backend"])
        self.assertTrue(result["configuration_ready"])
        self.assertNotIn(env[SUPABASE_SECRET_KEY_ENV], rendered)
        self.assertFalse(result["migration"]["step6k_remote_canary_preflight_migrated"])
        self.assertTrue(result["migration"]["step6k_remains_fail_closed_for_supabase_until_later_step"])

    def test_05_green_supabase_canary_persists_backup_feed_marker_and_lock(self):
        old = self.feed(source="old", odds=-101)
        new = self.feed(source="new", odds=-125)
        old_bytes = self.feed_bytes(old)
        new_bytes = self.feed_bytes(new)
        self.backend.objects[FEED_OBJECT_KEY] = old_bytes

        result = self.run_supabase(new)

        backup_key = s._backup_key(self.activation_id)
        marker = json.loads(self.backend.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        self.assertEqual("completed", result["status"])
        self.assertEqual(SUPABASE_BACKEND, result["storage_backend"])
        self.assertTrue(result["step6s_storage_migration"])
        self.assertEqual(old_bytes, self.backend.objects[backup_key])
        self.assertEqual(new_bytes, self.backend.objects[FEED_OBJECT_KEY])
        self.assertEqual("completed", marker["status"])
        self.assertEqual(hashlib.sha256(new_bytes).hexdigest(), marker["post_write_sha256"])
        self.assertEqual(1, self.backend.lock_entries)
        self.assertFalse(self.backend.locked)
        self.assertFalse(self.host_feed.exists())

    def test_06_identity_mismatch_restores_exact_preexisting_bytes(self):
        old_bytes = self.feed_bytes(self.feed(source="old"))
        self.backend.objects[FEED_OBJECT_KEY] = old_bytes
        env = self.supabase_env()
        new = self.feed(source="bad-new")
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
            side_effect=self.fake_sync(new, persistent_sha="f" * 64),
        ):
            with self.assertRaises(s.WNBAStep6SCanaryStorageError):
                s.run_storage_aware_step6j_canary(
                    date="2026-08-27",
                    season=2026,
                    activation_id=self.activation_id,
                    env=env,
                )
        marker = json.loads(self.backend.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        self.assertEqual(old_bytes, self.backend.objects[FEED_OBJECT_KEY])
        self.assertEqual("rolled_back", marker["status"])
        self.assertTrue(marker["rollback_verified"])
        self.assertFalse(marker["write_attempted"])

    def test_07_failure_after_remote_write_restores_exact_old_feed(self):
        old_bytes = self.feed_bytes(self.feed(source="old"))
        self.backend.objects[FEED_OBJECT_KEY] = old_bytes
        env = self.supabase_env()
        new = self.feed(source="new")
        real_write_marker = s._write_marker

        def fail_completed(storage, document):
            if document.get("status") == "completed":
                raise s.WNBAStep6SCanaryStorageError("forced completed-marker failure")
            return real_write_marker(storage, document)

        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
            side_effect=self.fake_sync(new),
        ), patch.object(s, "_write_marker", side_effect=fail_completed):
            with self.assertRaises(s.WNBAStep6SCanaryStorageError):
                s.run_storage_aware_step6j_canary(
                    date="2026-08-27",
                    season=2026,
                    activation_id=self.activation_id,
                    env=env,
                )
        marker = json.loads(self.backend.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        self.assertEqual(old_bytes, self.backend.objects[FEED_OBJECT_KEY])
        self.assertEqual("rolled_back", marker["status"])
        self.assertTrue(marker["write_attempted"])
        self.assertTrue(marker["rollback_verified"])

    def test_08_failed_new_feed_canary_removes_remote_feed(self):
        env = self.supabase_env()
        new = self.feed(source="new")
        real_write_marker = s._write_marker

        def fail_completed(storage, document):
            if document.get("status") == "completed":
                raise s.WNBAStep6SCanaryStorageError("forced completed-marker failure")
            return real_write_marker(storage, document)

        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
            side_effect=self.fake_sync(new),
        ), patch.object(s, "_write_marker", side_effect=fail_completed):
            with self.assertRaises(s.WNBAStep6SCanaryStorageError):
                s.run_storage_aware_step6j_canary(
                    date="2026-08-27",
                    season=2026,
                    activation_id=self.activation_id,
                    env=env,
                )
        marker = json.loads(self.backend.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        self.assertNotIn(FEED_OBJECT_KEY, self.backend.objects)
        self.assertEqual("rolled_back", marker["status"])
        self.assertFalse(marker["preexisting_feed"])

    def test_09_completed_supabase_canary_is_idempotent(self):
        new = self.feed(source="new")
        first = self.run_supabase(new)
        env = self.supabase_env()
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
        ) as sync:
            second = s.run_storage_aware_step6j_canary(
                date="2026-08-27",
                season=2026,
                activation_id=self.activation_id,
                env=env,
            )
        sync.assert_not_called()
        self.assertFalse(first["already_completed"])
        self.assertTrue(second["already_completed"])

    def test_10_remote_rolled_back_marker_blocks_replay_before_sync(self):
        marker = {
            "activation_id": self.activation_id,
            "status": "rolled_back",
            "preexisting_feed": False,
            "rollback_verified": True,
        }
        self.backend.objects[CANARY_MARKER_OBJECT_KEY] = s._marker_bytes(marker)
        env = self.supabase_env()
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
        ) as sync:
            with self.assertRaises(s.WNBAStep6SCanaryStorageError):
                s.run_storage_aware_step6j_canary(
                    date="2026-08-27",
                    season=2026,
                    activation_id=self.activation_id,
                    env=env,
                )
        sync.assert_not_called()

    def test_11_manual_supabase_rollback_restores_precanary_bytes_and_blocks_replay(self):
        old_bytes = self.feed_bytes(self.feed(source="old"))
        self.backend.objects[FEED_OBJECT_KEY] = old_bytes
        self.run_supabase(self.feed(source="new"))
        env = self.supabase_env()
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend):
            rollback = s.rollback_storage_aware_step6j_canary(
                activation_id=self.activation_id,
                env=env,
            )
        self.assertTrue(rollback["rollback_verified"])
        self.assertEqual(old_bytes, self.backend.objects[FEED_OBJECT_KEY])
        marker = json.loads(self.backend.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        self.assertEqual("manually_rolled_back", marker["status"])
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
        ) as sync:
            with self.assertRaises(s.WNBAStep6SCanaryStorageError):
                s.run_storage_aware_step6j_canary(
                    date="2026-08-27",
                    season=2026,
                    activation_id=self.activation_id,
                    env=env,
                )
        sync.assert_not_called()

    def test_12_lock_contention_fails_closed_before_step6i_sync(self):
        self.backend.contended = True
        env = self.supabase_env()
        with patch.object(s, "build_step6r_durable_storage", return_value=self.backend), patch.object(
            s,
            "sync_reconciled_draftkings_to_kyre_feed",
        ) as sync:
            with self.assertRaises(s.WNBAStep6SCanaryStorageError):
                s.run_storage_aware_step6j_canary(
                    date="2026-08-27",
                    season=2026,
                    activation_id=self.activation_id,
                    env=env,
                )
        sync.assert_not_called()

    def test_13_existing_step6j_api_post_dispatch_symbol_remains_patchable(self):
        import sports_api.api.wnba_step6j_canary as api

        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "WNBA_KYRE_MARKET_INGEST_TOKEN": "secret-token",
                KYRE_MARKET_FEED_PATH_ENV: str(Path(td) / "feed.json"),
            },
            clear=False,
        ), patch.object(api, "run_step6j_canary", return_value={"status": "completed", "storage_backend": "supabase"}) as run:
            response = client.post(
                "/markets/direct/draftkings/step6j-canary?date=2026-08-27&season=2026",
                headers={
                    "Authorization": "Bearer secret-token",
                    "X-WNBA-Step6J-Activation-ID": self.activation_id,
                },
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual("supabase", response.json()["storage_backend"])
        run.assert_called_once()

    def test_14_storage_status_route_is_get_only_and_network_free(self):
        import sports_api.api.wnba_step6j_canary as api

        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        with patch.dict(os.environ, {STORAGE_BACKEND_ENV: FILESYSTEM_BACKEND}, clear=False), patch.object(
            httpx.Client,
            "request",
            side_effect=AssertionError("status must not call network"),
        ):
            response = client.get("/markets/direct/draftkings/step6j-canary/storage-status")
        self.assertEqual(200, response.status_code)
        self.assertEqual(FILESYSTEM_BACKEND, response.json()["selected_backend"])
        self.assertEqual(405, client.put("/markets/direct/draftkings/step6j-canary/storage-status").status_code)


if __name__ == "__main__":
    unittest.main()
