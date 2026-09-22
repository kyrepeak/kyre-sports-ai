from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api.wnba_step6q_durable_storage import router
from sports_api.collectors.wnba_kyre_market_feed import KYRE_MARKET_FEED_PATH_ENV
from sports_api.wnba_step6q_durable_storage import (
    CANARY_LOCK_OBJECT_KEY,
    FEED_OBJECT_KEY,
    FILESYSTEM_BACKEND,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
    FilesystemDurableStorage,
    WNBADurableStorageBackend,
    WNBADurableStorageModelInputError,
    WNBADurableStorageNotReadyError,
    build_durable_storage,
    get_step6q_durable_storage_status,
    resolve_storage_backend_name,
)


class Step6QDurableStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.feed_path = self.root / FEED_OBJECT_KEY
        self.env = {
            STORAGE_BACKEND_ENV: FILESYSTEM_BACKEND,
            KYRE_MARKET_FEED_PATH_ENV: str(self.feed_path),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_default_backend_preserves_filesystem(self):
        self.assertEqual(resolve_storage_backend_name({}), FILESYSTEM_BACKEND)

    def test_02_backend_name_is_case_insensitive(self):
        self.assertEqual(resolve_storage_backend_name({STORAGE_BACKEND_ENV: "FILESYSTEM"}), FILESYSTEM_BACKEND)
        self.assertEqual(resolve_storage_backend_name({STORAGE_BACKEND_ENV: "SUPABASE"}), SUPABASE_BACKEND)

    def test_03_unknown_backend_fails_closed(self):
        with self.assertRaises(WNBADurableStorageModelInputError):
            resolve_storage_backend_name({STORAGE_BACKEND_ENV: "magic-disk"})

    def test_04_supabase_slot_is_reserved_but_not_silently_fallbacked(self):
        env = dict(self.env)
        env[STORAGE_BACKEND_ENV] = SUPABASE_BACKEND
        with self.assertRaises(WNBADurableStorageNotReadyError):
            build_durable_storage(env=env)

    def test_05_filesystem_backend_satisfies_contract(self):
        backend = build_durable_storage(env=self.env)
        self.assertIsInstance(backend, WNBADurableStorageBackend)
        self.assertEqual(backend.backend_id, FILESYSTEM_BACKEND)

    def test_06_relative_filesystem_root_rejected(self):
        with self.assertRaises(WNBADurableStorageModelInputError):
            FilesystemDurableStorage("relative-root")

    def test_07_atomic_write_and_byte_exact_read(self):
        backend = build_durable_storage(env=self.env)
        payload = b'{"hello":"wnba"}\n'
        metadata = backend.write_bytes_atomic(FEED_OBJECT_KEY, payload)
        self.assertEqual(backend.read_bytes(FEED_OBJECT_KEY), payload)
        self.assertEqual(metadata.size_bytes, len(payload))
        self.assertEqual(metadata.content_sha256, hashlib.sha256(payload).hexdigest())

    def test_08_atomic_overwrite_uses_latest_exact_bytes(self):
        backend = build_durable_storage(env=self.env)
        backend.write_bytes_atomic(FEED_OBJECT_KEY, b"first")
        backend.write_bytes_atomic(FEED_OBJECT_KEY, b"second")
        self.assertEqual(backend.read_bytes(FEED_OBJECT_KEY), b"second")

    def test_09_exists_size_hash_and_delete(self):
        backend = build_durable_storage(env=self.env)
        payload = b"durable-proof"
        self.assertFalse(backend.exists(FEED_OBJECT_KEY))
        backend.write_bytes_atomic(FEED_OBJECT_KEY, payload)
        self.assertTrue(backend.exists(FEED_OBJECT_KEY))
        self.assertEqual(backend.size_bytes(FEED_OBJECT_KEY), len(payload))
        self.assertEqual(backend.sha256(FEED_OBJECT_KEY), hashlib.sha256(payload).hexdigest())
        self.assertTrue(backend.delete(FEED_OBJECT_KEY))
        self.assertFalse(backend.delete(FEED_OBJECT_KEY))
        self.assertIsNone(backend.sha256(FEED_OBJECT_KEY))

    def test_10_missing_read_is_not_ready(self):
        backend = build_durable_storage(env=self.env)
        with self.assertRaises(WNBADurableStorageNotReadyError):
            backend.read_bytes(FEED_OBJECT_KEY)

    def test_11_object_key_path_traversal_is_rejected(self):
        backend = build_durable_storage(env=self.env)
        for key in ("../secret", "nested/file", "..", "."):
            with self.subTest(key=key):
                with self.assertRaises(WNBADurableStorageModelInputError):
                    backend.exists(key)

    def test_12_exclusive_lock_contract_works_for_filesystem_backend(self):
        backend = build_durable_storage(env=self.env)
        with backend.exclusive_lock(CANARY_LOCK_OBJECT_KEY):
            self.assertTrue((self.root / CANARY_LOCK_OBJECT_KEY).is_file())

    def test_13_status_is_read_only_and_reports_existing_feed_hash(self):
        backend = build_durable_storage(env=self.env)
        payload = b"status-proof"
        backend.write_bytes_atomic(FEED_OBJECT_KEY, payload)
        before = self.feed_path.read_bytes()
        result = get_step6q_durable_storage_status(self.env)
        after = self.feed_path.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(result["selected_backend"], FILESYSTEM_BACKEND)
        self.assertTrue(result["backend_implemented"])
        self.assertTrue(result["feed_exists"])
        self.assertEqual(result["feed_content_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertFalse(result["safety"]["storage_write_performed_by_status"])
        self.assertFalse(result["safety"]["network_used_by_status"])

    def test_14_supabase_status_is_deferred_without_network_or_fallback(self):
        env = dict(self.env)
        env[STORAGE_BACKEND_ENV] = SUPABASE_BACKEND
        result = get_step6q_durable_storage_status(env)
        self.assertEqual(result["selected_backend"], SUPABASE_BACKEND)
        self.assertFalse(result["backend_implemented"])
        self.assertIn("Step 6R", result["configuration_error"])
        self.assertFalse(result["feed_exists"])
        self.assertFalse(result["safety"]["network_used_by_status"])

    def test_15_invalid_backend_status_stays_fail_closed(self):
        env = dict(self.env)
        env[STORAGE_BACKEND_ENV] = "invalid"
        result = get_step6q_durable_storage_status(env)
        self.assertFalse(result["backend_implemented"])
        self.assertIsNotNone(result["configuration_error"])

    def test_16_api_is_get_only(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        response = client.get("/api/v1/wnba/runtime/step6q-durable-storage")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selected_backend"], FILESYSTEM_BACKEND)
        self.assertEqual(client.post("/api/v1/wnba/runtime/step6q-durable-storage").status_code, 405)


if __name__ == "__main__":
    unittest.main()
