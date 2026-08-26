from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

import sports_api.wnba_deployment_smoke_readiness as s
from sports_api.main import app


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, timeout=None):
        parsed = urlsplit(url)
        key = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.calls.append(("GET", key, timeout))
        value = self.mapping.get(key)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return FakeResponse(404, {"detail": "missing fake route"})
        return value


class Step5STests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.secret = "step-5s-test-secret-material-1234567890"
        self.env = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "true",
            "WNBA_CURRENT_BOARD_STORE_PATH": str(root / "board.sqlite3"),
            "WNBA_PROP_FEED_STORE_PATH": str(root / "feed.sqlite3"),
            "WNBA_BACKTEST_STORE_PATH": str(root / "backtest.sqlite3"),
            "WNBA_BOARD_SCHEDULER_LOCK_PATH": str(root / "scheduler_lock.sqlite3"),
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET": self.secret,
            "SPORTSGAMEODDS_API_KEY": "demo-key",
            "WNBA_BOARD_SCHEDULER_ENABLED": "true",
            "WNBA_BOARD_AUTO_ARCHIVE_ENABLED": "true",
            s.DEPLOYMENT_MODE_ENV: "container",
            s.REPLICA_COUNT_ENV: "1",
            s.PERSISTENT_ROOT_ENV: str(root),
            s.WEB_CONCURRENCY_ENV: "2",
            s.PORT_ENV: "8000",
            s.DEPLOYMENT_REVISION_ENV: "test-revision",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def readiness(self, env=None):
        return s.get_deployment_readiness(env=self.env if env is None else env)

    def fake_mapping(self, *, scheduler_ready=True, health_status=200, current_status=200):
        openapi_paths = {path: {} for path in s.REQUIRED_OPENAPI_PATHS}
        return {
            "/": FakeResponse(200, {"status": "online"}),
            "/health": FakeResponse(200, {"status": "ok"}),
            "/openapi.json": FakeResponse(200, {"paths": openapi_paths}),
            "/api/v1/wnba/runtime/readiness": FakeResponse(200, {"scheduler_allowed": scheduler_ready}),
            "/api/v1/wnba/runtime/deployment": FakeResponse(
                200,
                {"deployment_ready": True, "live_write_ready": scheduler_ready},
            ),
            "/api/v1/wnba/runtime/health": FakeResponse(health_status, {"status": "ready"}),
            "/api/v1/wnba/rankings/player-props/current?require_current=true": FakeResponse(current_status, {}),
        }

    def test_01_good_single_replica_configuration_is_deployment_ready(self):
        report = self.readiness()
        self.assertTrue(report["deployment_ready"])
        self.assertTrue(report["live_write_ready"])

    def test_02_activation_off_keeps_deployment_ready_but_blocks_live_writes(self):
        env = dict(self.env)
        env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "false"
        report = self.readiness(env)
        self.assertTrue(report["deployment_ready"])
        self.assertFalse(report["live_write_ready"])

    def test_03_only_container_mode_is_approved(self):
        env = dict(self.env)
        env[s.DEPLOYMENT_MODE_ENV] = "serverless"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_04_two_service_replicas_are_rejected(self):
        env = dict(self.env)
        env[s.REPLICA_COUNT_ENV] = "2"
        report = self.readiness(env)
        self.assertFalse(report["deployment_ready"])
        self.assertIn("single_service_replica", repr(report["blocking_reasons"]))

    def test_05_zero_replicas_are_rejected(self):
        env = dict(self.env)
        env[s.REPLICA_COUNT_ENV] = "0"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_06_non_integer_replica_count_is_rejected(self):
        env = dict(self.env)
        env[s.REPLICA_COUNT_ENV] = "many"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_07_one_uvicorn_worker_is_supported(self):
        env = dict(self.env)
        env[s.WEB_CONCURRENCY_ENV] = "1"
        self.assertTrue(self.readiness(env)["deployment_ready"])

    def test_08_eight_uvicorn_workers_are_supported(self):
        env = dict(self.env)
        env[s.WEB_CONCURRENCY_ENV] = "8"
        self.assertTrue(self.readiness(env)["deployment_ready"])

    def test_09_zero_uvicorn_workers_are_rejected(self):
        env = dict(self.env)
        env[s.WEB_CONCURRENCY_ENV] = "0"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_10_more_than_eight_uvicorn_workers_are_rejected(self):
        env = dict(self.env)
        env[s.WEB_CONCURRENCY_ENV] = "9"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_11_non_integer_worker_count_is_rejected(self):
        env = dict(self.env)
        env[s.WEB_CONCURRENCY_ENV] = "two"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_12_invalid_port_is_rejected(self):
        env = dict(self.env)
        env[s.PORT_ENV] = "0"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_13_non_integer_port_is_rejected(self):
        env = dict(self.env)
        env[s.PORT_ENV] = "http"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_14_missing_persistent_root_is_rejected(self):
        env = dict(self.env)
        env.pop(s.PERSISTENT_ROOT_ENV)
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_15_relative_persistent_root_is_rejected(self):
        env = dict(self.env)
        env[s.PERSISTENT_ROOT_ENV] = "relative/storage"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_16_runtime_database_outside_persistent_root_is_rejected(self):
        env = dict(self.env)
        env["WNBA_PROP_FEED_STORE_PATH"] = "/tmp/outside-feed.sqlite3"
        self.assertFalse(self.readiness(env)["deployment_ready"])

    def test_17_configuration_fingerprint_is_deterministic(self):
        one = self.readiness()["configuration_fingerprint_sha256"]
        two = self.readiness()["configuration_fingerprint_sha256"]
        self.assertEqual(one, two)
        self.assertEqual(64, len(one))

    def test_18_secret_values_are_not_returned(self):
        self.assertNotIn(self.secret, repr(self.readiness()))

    def test_19_report_declares_single_replica_sqlite_constraint(self):
        report = self.readiness()
        self.assertTrue(report["deployment"]["single_replica_required_for_current_sqlite_locking"])
        self.assertTrue(report["semantics"]["multi_replica_sqlite_deployment_is_rejected"])

    def test_20_smoke_plan_is_get_only(self):
        plan = s.build_live_smoke_plan("https://api.example.com")
        self.assertTrue(plan["safety"]["all_methods_are_get"])
        self.assertTrue(all(row["method"] == "GET" for row in plan["requests"]))

    def test_21_smoke_plan_never_calls_manual_refresh(self):
        plan = s.build_live_smoke_plan("https://api.example.com")
        self.assertNotIn("/refresh", " ".join(row["path"] for row in plan["requests"]))
        self.assertTrue(plan["safety"]["manual_refresh_endpoint_is_not_called"])

    def test_22_inactive_smoke_allows_runtime_health_503(self):
        plan = s.build_live_smoke_plan("https://api.example.com", expect_scheduler_ready=False)
        row = next(x for x in plan["requests"] if x["name"] == "production_runtime_health")
        self.assertEqual([200, 503], row["allowed_statuses"])

    def test_23_active_smoke_requires_runtime_health_200(self):
        plan = s.build_live_smoke_plan("https://api.example.com", expect_scheduler_ready=True)
        row = next(x for x in plan["requests"] if x["name"] == "production_runtime_health")
        self.assertEqual([200], row["allowed_statuses"])

    def test_24_https_base_url_is_normalized(self):
        self.assertEqual("https://api.example.com", s.normalize_smoke_base_url("https://api.example.com/"))

    def test_25_remote_http_base_url_is_rejected(self):
        with self.assertRaises(s.WNBALiveSmokeError):
            s.normalize_smoke_base_url("http://api.example.com")

    def test_26_localhost_http_base_url_is_allowed(self):
        self.assertEqual("http://127.0.0.1:8000", s.normalize_smoke_base_url("http://127.0.0.1:8000"))

    def test_27_credentials_in_base_url_are_rejected(self):
        with self.assertRaises(s.WNBALiveSmokeError):
            s.normalize_smoke_base_url("https://user:pass@api.example.com")

    def test_28_query_in_base_url_is_rejected(self):
        with self.assertRaises(s.WNBALiveSmokeError):
            s.normalize_smoke_base_url("https://api.example.com?token=x")

    def test_29_live_smoke_passes_when_scheduler_is_ready(self):
        client = FakeClient(self.fake_mapping(scheduler_ready=True, health_status=200, current_status=200))
        result = s.run_live_smoke("https://api.example.com", expect_scheduler_ready=True, client=client)
        self.assertTrue(result["passed"])
        self.assertEqual(result["check_count"], result["passed_count"])

    def test_30_live_smoke_passes_in_pre_activation_mode_with_health_503(self):
        client = FakeClient(self.fake_mapping(scheduler_ready=False, health_status=503, current_status=409))
        result = s.run_live_smoke("https://api.example.com", expect_scheduler_ready=False, client=client)
        self.assertTrue(result["passed"])

    def test_31_active_live_smoke_fails_when_runtime_health_is_503(self):
        client = FakeClient(self.fake_mapping(scheduler_ready=True, health_status=503, current_status=200))
        result = s.run_live_smoke("https://api.example.com", expect_scheduler_ready=True, client=client)
        self.assertFalse(result["passed"])

    def test_32_live_smoke_fails_when_openapi_contract_is_missing_route(self):
        mapping = self.fake_mapping()
        mapping["/openapi.json"] = FakeResponse(200, {"paths": {"/health": {}}})
        result = s.run_live_smoke("https://api.example.com", client=FakeClient(mapping))
        self.assertFalse(result["passed"])

    def test_33_empty_current_board_409_is_valid_smoke_result(self):
        client = FakeClient(self.fake_mapping(scheduler_ready=False, health_status=503, current_status=409))
        result = s.run_live_smoke("https://api.example.com", client=client)
        current = next(x for x in result["results"] if x["name"] == "current_board_read")
        self.assertTrue(current["passed"])

    def test_34_current_board_500_fails_smoke(self):
        client = FakeClient(self.fake_mapping(current_status=500))
        result = s.run_live_smoke("https://api.example.com", client=client)
        self.assertFalse(result["passed"])

    def test_35_invalid_timeout_is_rejected(self):
        with self.assertRaises(ValueError):
            s.run_live_smoke("https://api.example.com", timeout_seconds=0, client=FakeClient({}))

    def test_36_live_smoke_issues_only_get_requests(self):
        client = FakeClient(self.fake_mapping())
        s.run_live_smoke("https://api.example.com", client=client)
        self.assertTrue(client.calls)
        self.assertTrue(all(method == "GET" for method, _, _ in client.calls))

    def test_37_main_registers_step5s_endpoints(self):
        paths = set(app.openapi().get("paths", {}))
        self.assertIn("/api/v1/wnba/runtime/deployment", paths)
        self.assertIn("/api/v1/wnba/runtime/smoke-plan", paths)

    def test_38_frozen_current_routes_remain_registered(self):
        paths = set(app.openapi().get("paths", {}))
        for path in s.REQUIRED_OPENAPI_PATHS[:6]:
            self.assertIn(path, paths)

    def test_39_require_deployment_ready_returns_report(self):
        report = s.require_deployment_ready(env=self.env)
        self.assertTrue(report["deployment_ready"])

    def test_40_require_deployment_ready_rejects_multi_replica(self):
        env = dict(self.env)
        env[s.REPLICA_COUNT_ENV] = "2"
        with self.assertRaises(s.WNBADeploymentNotReadyError):
            s.require_deployment_ready(env=env)


if __name__ == "__main__":
    unittest.main()
