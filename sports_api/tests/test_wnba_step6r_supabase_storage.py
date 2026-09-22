from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from sports_api.api.wnba_step6r_supabase_storage import router
from sports_api.collectors.wnba_kyre_market_feed import KYRE_MARKET_FEED_PATH_ENV
from sports_api.wnba_step6q_durable_storage import (
    CANARY_LOCK_OBJECT_KEY,
    FEED_OBJECT_KEY,
    FILESYSTEM_BACKEND,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
    WNBADurableStorageBackend,
    WNBADurableStorageError,
    WNBADurableStorageModelInputError,
    WNBADurableStorageNotReadyError,
)
from sports_api.wnba_step6r_supabase_storage import (
    DEFAULT_LOCK_ACQUIRE_RPC,
    DEFAULT_LOCK_RELEASE_RPC,
    DEFAULT_OBJECT_TABLE,
    SCHEMA_FILE,
    SUPABASE_LOCK_LEASE_SECONDS_ENV,
    SUPABASE_SECRET_KEY_ENV,
    SUPABASE_URL_ENV,
    SupabaseDurableStorage,
    build_step6r_durable_storage,
    get_step6r_supabase_storage_status,
)


SECRET = "sb_secret_unit_test_abcdefghijklmnopqrstuvwxyz"
BASE_URL = "https://unit-test.supabase.co"


class FakeSupabase:
    def __init__(self):
        self.objects: dict[str, dict] = {}
        self.lock_owner: dict[str, str] = {}
        self.requests: list[httpx.Request] = []

    @staticmethod
    def _body(request: httpx.Request):
        if not request.content:
            return None
        return json.loads(request.content.decode("utf-8"))

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        params = request.url.params

        if path.endswith(f"/{DEFAULT_OBJECT_TABLE}"):
            if request.method == "GET":
                raw = params.get("object_key", "")
                key = raw[3:] if raw.startswith("eq.") else raw
                row = self.objects.get(key)
                if row is None:
                    return httpx.Response(200, json=[])
                columns = [part.strip() for part in params.get("select", "").split(",") if part.strip()]
                projected = {column: row[column] for column in columns}
                return httpx.Response(200, json=[projected])

            if request.method == "POST":
                body = self._body(request)
                key = body["object_key"]
                previous = self.objects.get(key, {})
                row = {
                    "created_at": previous.get("created_at", "2026-08-27T00:00:00Z"),
                    **body,
                }
                self.objects[key] = row
                return httpx.Response(201, json=[row])

            if request.method == "DELETE":
                raw = params.get("object_key", "")
                key = raw[3:] if raw.startswith("eq.") else raw
                row = self.objects.pop(key, None)
                return httpx.Response(200, json=[] if row is None else [{"object_key": key}])

        if path.endswith(f"/rpc/{DEFAULT_LOCK_ACQUIRE_RPC}") and request.method == "POST":
            body = self._body(request)
            key = body["p_lock_key"]
            owner = body["p_owner_token"]
            current = self.lock_owner.get(key)
            if current is None or current == owner:
                self.lock_owner[key] = owner
                return httpx.Response(200, json=True)
            return httpx.Response(200, json=False)

        if path.endswith(f"/rpc/{DEFAULT_LOCK_RELEASE_RPC}") and request.method == "POST":
            body = self._body(request)
            key = body["p_lock_key"]
            owner = body["p_owner_token"]
            if self.lock_owner.get(key) == owner:
                del self.lock_owner[key]
                return httpx.Response(200, json=True)
            return httpx.Response(200, json=False)

        return httpx.Response(404, json={"error": "unexpected fake request"})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


class Step6RSupabaseStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.feed_path = self.root / FEED_OBJECT_KEY
        self.filesystem_env = {
            STORAGE_BACKEND_ENV: FILESYSTEM_BACKEND,
            KYRE_MARKET_FEED_PATH_ENV: str(self.feed_path),
        }
        self.supabase_env = {
            STORAGE_BACKEND_ENV: SUPABASE_BACKEND,
            SUPABASE_URL_ENV: BASE_URL,
            SUPABASE_SECRET_KEY_ENV: SECRET,
        }
        self.fake = FakeSupabase()

    def tearDown(self):
        self.tmp.cleanup()

    def backend(self) -> SupabaseDurableStorage:
        return build_step6r_durable_storage(env=self.supabase_env, client=self.fake.client())

    def test_01_filesystem_selector_remains_backward_compatible(self):
        backend = build_step6r_durable_storage(env=self.filesystem_env)
        self.assertEqual(backend.backend_id, FILESYSTEM_BACKEND)
        backend.write_bytes_atomic(FEED_OBJECT_KEY, b"filesystem-still-works")
        self.assertEqual(backend.read_bytes(FEED_OBJECT_KEY), b"filesystem-still-works")

    def test_02_supabase_requires_https_project_url(self):
        env = dict(self.supabase_env)
        env[SUPABASE_URL_ENV] = "http://unit-test.supabase.co"
        with self.assertRaises(WNBADurableStorageModelInputError):
            build_step6r_durable_storage(env=env)

    def test_03_supabase_missing_url_fails_closed(self):
        env = dict(self.supabase_env)
        env.pop(SUPABASE_URL_ENV)
        with self.assertRaises(WNBADurableStorageNotReadyError):
            build_step6r_durable_storage(env=env)

    def test_04_supabase_missing_secret_fails_closed(self):
        env = dict(self.supabase_env)
        env.pop(SUPABASE_SECRET_KEY_ENV)
        with self.assertRaises(WNBADurableStorageNotReadyError):
            build_step6r_durable_storage(env=env)

    def test_05_supabase_backend_satisfies_step6q_protocol(self):
        backend = self.backend()
        self.assertIsInstance(backend, WNBADurableStorageBackend)
        self.assertEqual(backend.backend_id, SUPABASE_BACKEND)

    def test_06_description_never_exposes_secret_value(self):
        backend = self.backend()
        description = backend.describe()
        rendered = json.dumps(description, sort_keys=True)
        self.assertNotIn(SECRET, rendered)
        self.assertEqual(description["project_host"], "unit-test.supabase.co")
        self.assertTrue(description["secret_configured"])
        self.assertFalse(description["secret_value_exposed"])

    def test_07_byte_exact_atomic_write_and_read(self):
        backend = self.backend()
        payload = b"\x00wnba\xff\nexact-bytes"
        metadata = backend.write_bytes_atomic(FEED_OBJECT_KEY, payload)
        self.assertEqual(metadata.backend_id, SUPABASE_BACKEND)
        self.assertEqual(metadata.size_bytes, len(payload))
        self.assertEqual(metadata.content_sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(backend.read_bytes(FEED_OBJECT_KEY), payload)

    def test_08_atomic_overwrite_returns_latest_bytes(self):
        backend = self.backend()
        backend.write_bytes_atomic(FEED_OBJECT_KEY, b"first")
        backend.write_bytes_atomic(FEED_OBJECT_KEY, b"second")
        self.assertEqual(backend.read_bytes(FEED_OBJECT_KEY), b"second")

    def test_09_exists_size_hash_and_delete_contract(self):
        backend = self.backend()
        payload = b"remote-durable-proof"
        self.assertFalse(backend.exists(FEED_OBJECT_KEY))
        backend.write_bytes_atomic(FEED_OBJECT_KEY, payload)
        self.assertTrue(backend.exists(FEED_OBJECT_KEY))
        self.assertEqual(backend.size_bytes(FEED_OBJECT_KEY), len(payload))
        self.assertEqual(backend.sha256(FEED_OBJECT_KEY), hashlib.sha256(payload).hexdigest())
        self.assertTrue(backend.delete(FEED_OBJECT_KEY))
        self.assertFalse(backend.delete(FEED_OBJECT_KEY))
        self.assertIsNone(backend.sha256(FEED_OBJECT_KEY))

    def test_10_missing_remote_object_is_not_ready(self):
        backend = self.backend()
        with self.assertRaises(WNBADurableStorageNotReadyError):
            backend.read_bytes(FEED_OBJECT_KEY)

    def test_11_read_verifies_database_sha_and_size(self):
        backend = self.backend()
        payload = b"integrity-proof"
        backend.write_bytes_atomic(FEED_OBJECT_KEY, payload)
        self.fake.objects[FEED_OBJECT_KEY]["content_sha256"] = "0" * 64
        with self.assertRaises(WNBADurableStorageError):
            backend.read_bytes(FEED_OBJECT_KEY)

    def test_12_read_rejects_invalid_base64(self):
        backend = self.backend()
        payload = b"abc"
        self.fake.objects[FEED_OBJECT_KEY] = {
            "object_key": FEED_OBJECT_KEY,
            "payload_base64": "not***base64",
            "size_bytes": len(payload),
            "content_sha256": hashlib.sha256(payload).hexdigest(),
        }
        with self.assertRaises(WNBADurableStorageError):
            backend.read_bytes(FEED_OBJECT_KEY)

    def test_13_object_key_traversal_is_rejected_before_network(self):
        backend = self.backend()
        before = len(self.fake.requests)
        for key in ("../secret", "nested/file", "..", "."):
            with self.subTest(key=key):
                with self.assertRaises(WNBADurableStorageModelInputError):
                    backend.exists(key)
        self.assertEqual(len(self.fake.requests), before)

    def test_14_exclusive_lock_uses_acquire_and_release_rpc(self):
        backend = self.backend()
        with backend.exclusive_lock(CANARY_LOCK_OBJECT_KEY):
            self.assertIn(CANARY_LOCK_OBJECT_KEY, self.fake.lock_owner)
        self.assertNotIn(CANARY_LOCK_OBJECT_KEY, self.fake.lock_owner)
        paths = [request.url.path for request in self.fake.requests]
        self.assertTrue(any(path.endswith(f"/rpc/{DEFAULT_LOCK_ACQUIRE_RPC}") for path in paths))
        self.assertTrue(any(path.endswith(f"/rpc/{DEFAULT_LOCK_RELEASE_RPC}") for path in paths))

    def test_15_lock_contention_fails_closed(self):
        backend = self.backend()
        self.fake.lock_owner[CANARY_LOCK_OBJECT_KEY] = "some-other-owner"
        with self.assertRaises(WNBADurableStorageNotReadyError):
            with backend.exclusive_lock(CANARY_LOCK_OBJECT_KEY):
                self.fail("contended lock must not enter")

    def test_16_secret_key_uses_server_apikey_header_without_echo(self):
        backend = self.backend()
        backend.exists(FEED_OBJECT_KEY)
        request = self.fake.requests[-1]
        self.assertEqual(request.headers.get("apikey"), SECRET)
        self.assertIsNone(request.headers.get("authorization"))
        self.assertNotIn(SECRET, str(request.url))

    def test_17_http_failure_does_not_leak_secret(self):
        def fail(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"message": "down"})

        client = httpx.Client(transport=httpx.MockTransport(fail))
        backend = build_step6r_durable_storage(env=self.supabase_env, client=client)
        with self.assertRaises(WNBADurableStorageError) as caught:
            backend.exists(FEED_OBJECT_KEY)
        self.assertNotIn(SECRET, str(caught.exception))

    def test_18_configuration_status_is_network_free_and_secret_free(self):
        result = get_step6r_supabase_storage_status(self.supabase_env)
        rendered = json.dumps(result, sort_keys=True)
        self.assertTrue(result["supabase_selected"])
        self.assertTrue(result["backend_implemented"])
        self.assertTrue(result["configuration_ready"])
        self.assertFalse(result["safety"]["network_used_by_status"])
        self.assertFalse(result["safety"]["storage_write_performed_by_status"])
        self.assertFalse(result["safety"]["secret_value_returned"])
        self.assertNotIn(SECRET, rendered)
        self.assertEqual(result["schema_contract"]["sql_file"], SCHEMA_FILE)

    def test_19_status_fails_closed_when_supabase_config_missing(self):
        result = get_step6r_supabase_storage_status({STORAGE_BACKEND_ENV: SUPABASE_BACKEND})
        self.assertTrue(result["supabase_selected"])
        self.assertFalse(result["configuration_ready"])
        self.assertIsNotNone(result["configuration_error"])

    def test_20_lock_lease_bounds_are_enforced(self):
        for value in ("29", "901", "not-an-int"):
            env = dict(self.supabase_env)
            env[SUPABASE_LOCK_LEASE_SECONDS_ENV] = value
            with self.subTest(value=value):
                with self.assertRaises(WNBADurableStorageModelInputError):
                    build_step6r_durable_storage(env=env)

    def test_21_api_is_get_only(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch.dict("os.environ", self.supabase_env, clear=True):
            response = client.get("/api/v1/wnba/runtime/step6r-supabase-storage")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["configuration_ready"])
        self.assertEqual(client.post("/api/v1/wnba/runtime/step6r-supabase-storage").status_code, 405)

    def test_22_schema_contract_is_rls_locked_and_security_invoker(self):
        sql = Path(SCHEMA_FILE).read_text(encoding="utf-8").casefold()
        self.assertIn("enable row level security", sql)
        self.assertIn("from public, anon, authenticated", sql)
        self.assertIn("to service_role", sql)
        self.assertIn("security invoker", sql)
        self.assertNotIn("security definer", sql)
        self.assertIn(DEFAULT_OBJECT_TABLE, sql)
        self.assertIn(DEFAULT_LOCK_ACQUIRE_RPC, sql)
        self.assertIn(DEFAULT_LOCK_RELEASE_RPC, sql)


if __name__ == "__main__":
    unittest.main()
