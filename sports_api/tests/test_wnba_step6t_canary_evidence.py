from __future__ import annotations

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

from sports_api.collectors.wnba_kyre_market_feed import KYRE_MARKET_FEED_PATH_ENV
from sports_api.wnba_reconciled_direct_sync import persistent_feed_sha256
from sports_api.wnba_step6q_durable_storage import (
    CANARY_MARKER_OBJECT_KEY,
    FEED_OBJECT_KEY,
    FILESYSTEM_BACKEND,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
    DurableObjectMetadata,
    WNBADurableStorageNotReadyError,
)
from sports_api.wnba_step6r_supabase_storage import SUPABASE_SECRET_KEY_ENV, SUPABASE_URL_ENV
import sports_api.wnba_step6t_canary_evidence as s


class MemoryStorage:
    backend_id = SUPABASE_BACKEND

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.read_count = 0
        self.write_count = 0

    def exists(self, object_key: str) -> bool:
        self.read_count += 1
        return object_key in self.objects

    def read_bytes(self, object_key: str, *, max_bytes: int = 5_000_000) -> bytes:
        self.read_count += 1
        if object_key not in self.objects:
            raise WNBADurableStorageNotReadyError(f"missing {object_key}")
        payload = self.objects[object_key]
        if len(payload) > max_bytes:
            raise ValueError("test object too large")
        return payload

    def write_bytes_atomic(self, object_key: str, payload: bytes) -> DurableObjectMetadata:
        self.write_count += 1
        self.objects[object_key] = bytes(payload)
        return DurableObjectMetadata(
            backend_id=self.backend_id,
            object_key=object_key,
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
        )

    def delete(self, object_key: str) -> bool:
        self.write_count += 1
        return self.objects.pop(object_key, None) is not None

    def size_bytes(self, object_key: str):
        self.read_count += 1
        value = self.objects.get(object_key)
        return None if value is None else len(value)

    def sha256(self, object_key: str):
        self.read_count += 1
        value = self.objects.get(object_key)
        return None if value is None else hashlib.sha256(value).hexdigest()

    def describe(self):
        return {"backend_id": self.backend_id, "implemented": True}

    def exclusive_lock(self, lock_key: str):
        raise AssertionError("Step 6T verification must never acquire a mutation lock")


class Step6TCanaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.activation_id = "step6t-test-001"
        self.storage = MemoryStorage()

    def tearDown(self):
        self.tmp.cleanup()

    def feed(self):
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-27",
            "season": 2026,
            "captured_at_utc": "2026-08-27T05:00:00+00:00",
            "feed_source": "step6t-test",
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": [
                {
                    "sportsbook": "DraftKings",
                    "player_name": "A'ja Wilson",
                    "stat": "points",
                    "side": "over",
                    "line": 24.5,
                    "american_odds": -110,
                }
            ],
        }

    def feed_bytes(self):
        return (json.dumps(self.feed(), indent=2, sort_keys=True) + "\n").encode("utf-8")

    def marker(self, *, preexisting=False, pre_write_sha=None):
        feed_raw = self.feed_bytes()
        return {
            "source": "test",
            "schema_version": "test",
            "model_version": "test",
            "activation_id": self.activation_id,
            "status": "completed",
            "started_at_utc": "2026-08-27T05:00:00+00:00",
            "completed_at_utc": "2026-08-27T05:01:00+00:00",
            "date": "2026-08-27",
            "season": 2026,
            "preexisting_feed": bool(preexisting),
            "pre_write_sha256": pre_write_sha,
            "backup_present": bool(preexisting),
            "rollback_verified": True,
            "post_write_sha256": hashlib.sha256(feed_raw).hexdigest(),
            "verified_persistent_feed_sha256": persistent_feed_sha256(self.feed()),
            "offer_side_count": 1,
            "storage_backend": SUPABASE_BACKEND,
            "step6s_storage_migration": True,
        }

    def supabase_env(self):
        return {
            STORAGE_BACKEND_ENV: SUPABASE_BACKEND,
            SUPABASE_URL_ENV: "https://step6t-test.supabase.co",
            SUPABASE_SECRET_KEY_ENV: "sb_secret_step6t_unit_test_placeholder_abcdefghijklmnopqrstuvwxyz",
            s.CANARY_ENABLED_ENV: "false",
            s.DIRECT_SYNC_ENABLED_ENV: "false",
            s.RECONCILED_SYNC_ENABLED_ENV: "false",
            s.PRODUCTION_RUNTIME_ENV: "false",
        }

    def load_remote(self, *, preexisting=False, old_bytes=b"old-feed-bytes"):
        feed_raw = self.feed_bytes()
        pre_sha = hashlib.sha256(old_bytes).hexdigest() if preexisting else None
        marker = self.marker(preexisting=preexisting, pre_write_sha=pre_sha)
        self.storage.objects[FEED_OBJECT_KEY] = feed_raw
        self.storage.objects[CANARY_MARKER_OBJECT_KEY] = (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if preexisting:
            self.storage.objects[s._backup_key(self.activation_id)] = old_bytes
        self.storage.read_count = 0
        self.storage.write_count = 0

    def verify_remote(self):
        with patch.object(s, "build_step6r_durable_storage", return_value=self.storage):
            return s.verify_step6t_canary_evidence(self.supabase_env())

    def test_01_default_status_is_filesystem_network_free_and_not_authorized(self):
        with patch.object(httpx.Client, "request", side_effect=AssertionError("status must not call network")):
            result = s.get_step6t_canary_evidence_status({})
        self.assertEqual(FILESYSTEM_BACKEND, result["selected_backend"])
        self.assertTrue(result["configuration_ready"])
        self.assertFalse(result["verification_requires_network"])
        self.assertFalse(result["scheduler_authorized"])
        self.assertFalse(result["safety"]["network_used_by_status"])

    def test_02_supabase_status_is_configuration_only_network_free_and_secret_free(self):
        env = self.supabase_env()
        with patch.object(httpx.Client, "request", side_effect=AssertionError("status must not call network")):
            result = s.get_step6t_canary_evidence_status(env)
        rendered = json.dumps(result, sort_keys=True)
        self.assertTrue(result["configuration_ready"])
        self.assertTrue(result["verification_requires_network"])
        self.assertNotIn(env[SUPABASE_SECRET_KEY_ENV], rendered)
        self.assertFalse(result["scheduler_authorized"])

    def test_03_green_supabase_evidence_verifies_exact_feed_identity_read_only(self):
        self.load_remote(preexisting=False)
        result = self.verify_remote()
        self.assertTrue(result["evidence_verified"])
        self.assertEqual(SUPABASE_BACKEND, result["canary_identity"]["storage_backend"])
        self.assertEqual(hashlib.sha256(self.feed_bytes()).hexdigest(), result["canary_identity"]["post_write_sha256"])
        self.assertEqual(persistent_feed_sha256(self.feed()), result["canary_identity"]["verified_persistent_feed_sha256"])
        self.assertGreater(self.storage.read_count, 0)
        self.assertEqual(0, self.storage.write_count)
        self.assertFalse(result["scheduler_authorized"])
        self.assertFalse(result["safety"]["storage_write_performed"])

    def test_04_preexisting_feed_requires_exact_backup_bytes(self):
        old = b"exact-old-feed"
        self.load_remote(preexisting=True, old_bytes=old)
        result = self.verify_remote()
        self.assertEqual("restore_exact_backup_bytes", result["canary_identity"]["rollback_mode"])
        self.assertEqual(hashlib.sha256(old).hexdigest(), result["canary_identity"]["backup_content_sha256"])

    def test_05_missing_preexisting_backup_fails_closed(self):
        self.load_remote(preexisting=True)
        self.storage.objects.pop(s._backup_key(self.activation_id))
        with self.assertRaises(s.WNBAStep6TEvidenceError):
            self.verify_remote()

    def test_06_backup_hash_mismatch_fails_closed(self):
        self.load_remote(preexisting=True)
        self.storage.objects[s._backup_key(self.activation_id)] = b"tampered-backup"
        with self.assertRaises(s.WNBAStep6TEvidenceError):
            self.verify_remote()

    def test_07_feed_byte_hash_mismatch_fails_closed(self):
        self.load_remote()
        self.storage.objects[FEED_OBJECT_KEY] += b"tamper"
        with self.assertRaises(s.WNBAStep6TEvidenceError):
            self.verify_remote()

    def test_08_canonical_identity_mismatch_fails_closed(self):
        self.load_remote()
        marker = json.loads(self.storage.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        marker["verified_persistent_feed_sha256"] = "f" * 64
        self.storage.objects[CANARY_MARKER_OBJECT_KEY] = (json.dumps(marker, sort_keys=True) + "\n").encode("utf-8")
        with self.assertRaises(s.WNBAStep6TEvidenceError):
            self.verify_remote()

    def test_09_noncompleted_marker_fails_closed(self):
        self.load_remote()
        marker = json.loads(self.storage.objects[CANARY_MARKER_OBJECT_KEY].decode("utf-8"))
        marker["status"] = "rolled_back"
        self.storage.objects[CANARY_MARKER_OBJECT_KEY] = (json.dumps(marker, sort_keys=True) + "\n").encode("utf-8")
        with self.assertRaises(s.WNBAStep6TEvidenceError):
            self.verify_remote()

    def test_10_temporary_write_switch_blocks_before_storage_read(self):
        self.load_remote()
        env = self.supabase_env()
        env[s.DIRECT_SYNC_ENABLED_ENV] = "true"
        before = self.storage.read_count
        with patch.object(s, "build_step6r_durable_storage", return_value=self.storage):
            with self.assertRaises(s.WNBAStep6TEvidenceError):
                s.verify_step6t_canary_evidence(env)
        self.assertEqual(before, self.storage.read_count)

    def test_11_production_runtime_on_blocks_before_storage_read(self):
        self.load_remote()
        env = self.supabase_env()
        env[s.PRODUCTION_RUNTIME_ENV] = "true"
        before = self.storage.read_count
        with patch.object(s, "build_step6r_durable_storage", return_value=self.storage):
            with self.assertRaises(s.WNBAStep6TEvidenceError):
                s.verify_step6t_canary_evidence(env)
        self.assertEqual(before, self.storage.read_count)

    def test_12_evidence_hash_is_deterministic_across_verifications(self):
        self.load_remote(preexisting=True)
        first = self.verify_remote()
        second = self.verify_remote()
        self.assertEqual(first["evidence_sha256"], second["evidence_sha256"])
        self.assertNotEqual(first["generated_at_utc"], "")

    def test_13_filesystem_verifier_supports_legacy_custom_feed_filename(self):
        target = self.root / "custom-legacy-feed.json"
        feed_raw = self.feed_bytes()
        target.write_bytes(feed_raw)
        marker = self.marker(preexisting=False)
        marker.pop("storage_backend")
        marker_path = target.parent / s.MARKER_FILENAME
        marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        env = {
            STORAGE_BACKEND_ENV: FILESYSTEM_BACKEND,
            KYRE_MARKET_FEED_PATH_ENV: str(target),
            s.CANARY_ENABLED_ENV: "false",
            s.DIRECT_SYNC_ENABLED_ENV: "false",
            s.RECONCILED_SYNC_ENABLED_ENV: "false",
            s.PRODUCTION_RUNTIME_ENV: "false",
        }
        result = s.verify_step6t_canary_evidence(env)
        self.assertTrue(result["evidence_verified"])
        self.assertEqual(FILESYSTEM_BACKEND, result["canary_identity"]["storage_backend"])
        self.assertFalse(result["safety"]["remote_storage_read_performed"])

    def test_14_api_status_is_get_only_and_verify_requires_auth(self):
        import sports_api.api.wnba_step6t_canary_evidence as api

        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        status = client.get("/api/v1/wnba/runtime/step6t-canary-evidence/status")
        self.assertEqual(200, status.status_code)
        self.assertFalse(status.json()["scheduler_authorized"])
        self.assertEqual(405, client.put("/api/v1/wnba/runtime/step6t-canary-evidence/status").status_code)
        response = client.post("/api/v1/wnba/runtime/step6t-canary-evidence/verify")
        self.assertIn(response.status_code, {401, 503})

    def test_15_authenticated_verify_transport_returns_evidence_without_authority(self):
        import sports_api.api.wnba_step6t_canary_evidence as api

        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        expected = {"evidence_verified": True, "scheduler_authorized": False}
        with patch.dict(os.environ, {"WNBA_KYRE_MARKET_INGEST_TOKEN": "step6t-secret"}, clear=False), patch.object(
            api,
            "verify_step6t_canary_evidence",
            return_value=expected,
        ) as verify:
            response = client.post(
                "/api/v1/wnba/runtime/step6t-canary-evidence/verify",
                headers={"Authorization": "Bearer step6t-secret"},
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, response.json())
        verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
