from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

import sports_api.wnba_hosted_staging_readiness as s
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


class Step5UTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.revision = "a" * 40
        self.storage_identity = "c" * 64
        self.image_ref = "ghcr.io/kyrepeak/kyre-sports-api@sha256:" + "b" * 64
        self.release_id = "staging-release-001"
        self.service_name = "kyre-sports-api-staging"
        self.external_url = "https://kyre-sports-api-staging.onrender.com"
        self.env = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_CURRENT_BOARD_STORE_PATH": str(root / "board.sqlite3"),
            "WNBA_PROP_FEED_STORE_PATH": str(root / "feed.sqlite3"),
            "WNBA_BACKTEST_STORE_PATH": str(root / "backtest.sqlite3"),
            "WNBA_BOARD_SCHEDULER_LOCK_PATH": str(root / "scheduler_lock.sqlite3"),
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET": "step-5u-test-secret-material-12345678901234567890",
            "SPORTSGAMEODDS_API_KEY": "demo-key",
            "WNBA_BOARD_SCHEDULER_ENABLED": "true",
            "WNBA_BOARD_AUTO_ARCHIVE_ENABLED": "true",
            "WNBA_DEPLOYMENT_MODE": "container",
            "WNBA_DEPLOYMENT_REPLICA_COUNT": "1",
            "WNBA_PERSISTENT_VOLUME_ROOT": str(root),
            "WEB_CONCURRENCY": "2",
            "PORT": "8000",
            "WNBA_DEPLOYMENT_REVISION": self.revision,
            "WNBA_RELEASE_ID": self.release_id,
            "WNBA_RELEASE_CHANNEL": "production",
            "WNBA_DEPLOYMENT_IMAGE_REF": self.image_ref,
            "WNBA_RELEASE_INITIAL_DEPLOYMENT": "true",
            s.HOST_PROVIDER_ENV: "render",
            s.HOST_ENVIRONMENT_ENV: "staging",
            s.STAGING_EXTERNAL_URL_ENV: self.external_url,
            s.EXPECTED_SERVICE_NAME_ENV: self.service_name,
            s.EXPECTED_GIT_BRANCH_ENV: "api-foundation-v1",
            s.RENDER_FLAG_ENV: "true",
            s.RENDER_SERVICE_ID_ENV: "srv-step5u123",
            s.RENDER_SERVICE_NAME_ENV: self.service_name,
            s.RENDER_SERVICE_TYPE_ENV: "web",
            s.RENDER_EXTERNAL_URL_ENV: self.external_url,
            s.RENDER_EXTERNAL_HOSTNAME_ENV: "kyre-sports-api-staging.onrender.com",
            s.RENDER_GIT_COMMIT_ENV: self.revision,
            s.RENDER_GIT_BRANCH_ENV: "api-foundation-v1",
            s.RENDER_GIT_REPO_SLUG_ENV: "kyrepeak/kyre-sports-ai",
            s.RENDER_INSTANCE_ID_ENV: "instance-step5u-1",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def readiness(self, env=None):
        return s.get_hosted_staging_readiness(env=self.env if env is None else env)

    def fake_mapping(self, *, health=503, current=409, hosting_ready=True, activation=False):
        return {
            "/health": FakeResponse(200, {"status": "ok"}),
            "/api/v1/wnba/runtime/readiness": FakeResponse(200, {"activation_requested": activation}),
            "/api/v1/wnba/runtime/deployment": FakeResponse(200, {"deployment_ready": True}),
            "/api/v1/wnba/runtime/release": FakeResponse(200, {
                "phase": "pre_activation_ready",
                "release": {"revision": self.revision, "release_id": self.release_id},
                "storage_identity_sha256": self.storage_identity,
            }),
            "/api/v1/wnba/runtime/hosting": FakeResponse(200, {
                "provider": "render",
                "activation_requested": activation,
                "host_contract_ready": hosting_ready,
                "host_identity_sha256": "d" * 64,
                "host": {"service_name": self.service_name},
            }),
            "/api/v1/wnba/runtime/health": FakeResponse(health, {"status": "disabled"}),
            "/api/v1/wnba/rankings/player-props/current?require_current=true": FakeResponse(current, {}),
        }

    def run_fake(self, mapping=None, **kwargs):
        return s.run_hosted_staging_smoke(
            self.external_url,
            expected_revision=self.revision,
            expected_release_id=self.release_id,
            expected_storage_identity=self.storage_identity,
            expected_service_name=self.service_name,
            client=FakeClient(mapping or self.fake_mapping()),
            **kwargs,
        )

    def test_01_good_render_staging_contract_is_ready(self):
        self.assertTrue(self.readiness()["host_contract_ready"])

    def test_02_good_contract_allows_remote_smoke(self):
        self.assertTrue(self.readiness()["remote_smoke_allowed"])

    def test_03_provider_must_be_render(self):
        env = dict(self.env); env[s.HOST_PROVIDER_ENV] = "other"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_04_environment_must_be_staging(self):
        env = dict(self.env); env[s.HOST_ENVIRONMENT_ENV] = "production"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_05_render_marker_is_required(self):
        env = dict(self.env); env[s.RENDER_FLAG_ENV] = "false"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_06_render_service_type_must_be_web(self):
        env = dict(self.env); env[s.RENDER_SERVICE_TYPE_ENV] = "worker"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_07_render_service_id_is_required(self):
        env = dict(self.env); env.pop(s.RENDER_SERVICE_ID_ENV)
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_08_render_service_name_is_required(self):
        env = dict(self.env); env.pop(s.RENDER_SERVICE_NAME_ENV)
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_09_expected_service_name_must_match(self):
        env = dict(self.env); env[s.RENDER_SERVICE_NAME_ENV] = "wrong-service"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_10_expected_service_name_is_optional(self):
        env = dict(self.env); env.pop(s.EXPECTED_SERVICE_NAME_ENV)
        self.assertTrue(self.readiness(env)["host_contract_ready"])

    def test_11_staging_external_url_is_required(self):
        env = dict(self.env); env.pop(s.STAGING_EXTERNAL_URL_ENV)
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_12_remote_http_url_is_rejected(self):
        env = dict(self.env); env[s.STAGING_EXTERNAL_URL_ENV] = "http://kyre.example.com"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_13_render_external_url_is_required(self):
        env = dict(self.env); env.pop(s.RENDER_EXTERNAL_URL_ENV)
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_14_configured_url_must_match_render_url(self):
        env = dict(self.env); env[s.RENDER_EXTERNAL_URL_ENV] = "https://other.onrender.com"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_15_onrender_hostname_is_accepted(self):
        self.assertTrue(self.readiness()["host_contract_ready"])

    def test_16_custom_hostname_rejected_by_default(self):
        env = dict(self.env); env[s.STAGING_EXTERNAL_URL_ENV] = "https://staging.example.com"; env[s.RENDER_EXTERNAL_URL_ENV] = "https://staging.example.com"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_17_custom_hostname_can_be_explicitly_allowed(self):
        env = dict(self.env); env[s.STAGING_EXTERNAL_URL_ENV] = "https://staging.example.com"; env[s.RENDER_EXTERNAL_URL_ENV] = "https://staging.example.com"; env[s.ALLOW_CUSTOM_DOMAIN_ENV] = "true"
        self.assertTrue(self.readiness(env)["host_contract_ready"])

    def test_18_render_commit_must_be_full_sha(self):
        env = dict(self.env); env[s.RENDER_GIT_COMMIT_ENV] = "abc123"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_19_render_commit_must_match_release_revision(self):
        env = dict(self.env); env[s.RENDER_GIT_COMMIT_ENV] = "f" * 40
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_20_render_branch_must_match_expected(self):
        env = dict(self.env); env[s.RENDER_GIT_BRANCH_ENV] = "main"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_21_expected_branch_can_be_overridden(self):
        env = dict(self.env); env[s.EXPECTED_GIT_BRANCH_ENV] = "main"; env[s.RENDER_GIT_BRANCH_ENV] = "main"
        self.assertTrue(self.readiness(env)["host_contract_ready"])

    def test_22_render_repo_slug_is_required(self):
        env = dict(self.env); env.pop(s.RENDER_GIT_REPO_SLUG_ENV)
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_23_render_instance_id_is_required(self):
        env = dict(self.env); env.pop(s.RENDER_INSTANCE_ID_ENV)
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_24_step5t_release_must_be_ready(self):
        env = dict(self.env); env["WNBA_DEPLOYMENT_IMAGE_REF"] = "latest"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_25_runtime_activation_must_remain_off(self):
        env = dict(self.env); env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_26_step5s_single_replica_rule_remains_authoritative(self):
        env = dict(self.env); env["WNBA_DEPLOYMENT_REPLICA_COUNT"] = "2"
        self.assertFalse(self.readiness(env)["host_contract_ready"])

    def test_27_storage_identity_is_returned(self):
        value = self.readiness()["storage_identity_sha256"]
        self.assertEqual(64, len(value))

    def test_28_host_identity_is_deterministic(self):
        self.assertEqual(self.readiness()["host_identity_sha256"], self.readiness()["host_identity_sha256"])

    def test_29_host_identity_is_sha256_length(self):
        self.assertEqual(64, len(self.readiness()["host_identity_sha256"]))

    def test_30_secret_values_are_not_returned(self):
        secret = self.env["WNBA_BACKTEST_ARCHIVE_HMAC_SECRET"]
        self.assertNotIn(secret, repr(self.readiness()))

    def test_31_smoke_plan_contains_seven_gets(self):
        plan = s.build_hosted_staging_smoke_plan(self.external_url)
        self.assertEqual(7, plan["request_count"])
        self.assertTrue(all(row["method"] == "GET" for row in plan["requests"]))

    def test_32_smoke_plan_never_calls_refresh(self):
        plan = s.build_hosted_staging_smoke_plan(self.external_url)
        self.assertNotIn("/refresh", " ".join(row["path"] for row in plan["requests"]))

    def test_33_smoke_plan_requires_runtime_503(self):
        plan = s.build_hosted_staging_smoke_plan(self.external_url)
        row = next(x for x in plan["requests"] if x["name"] == "runtime_health_pre_activation")
        self.assertEqual([503], row["allowed_statuses"])

    def test_34_smoke_plan_allows_empty_current_board(self):
        plan = s.build_hosted_staging_smoke_plan(self.external_url)
        row = next(x for x in plan["requests"] if x["name"] == "current_board_read")
        self.assertEqual([200, 409], row["allowed_statuses"])

    def test_35_remote_smoke_passes_for_valid_pre_activation_host(self):
        self.assertTrue(self.run_fake()["passed"])

    def test_36_remote_smoke_fails_if_runtime_health_is_200(self):
        self.assertFalse(self.run_fake(self.fake_mapping(health=200))["passed"])

    def test_37_remote_smoke_fails_if_host_contract_is_false(self):
        self.assertFalse(self.run_fake(self.fake_mapping(hosting_ready=False))["passed"])

    def test_38_remote_smoke_fails_if_activation_is_on(self):
        self.assertFalse(self.run_fake(self.fake_mapping(activation=True))["passed"])

    def test_39_remote_smoke_accepts_current_board_200(self):
        self.assertTrue(self.run_fake(self.fake_mapping(current=200))["passed"])

    def test_40_remote_smoke_rejects_current_board_500(self):
        self.assertFalse(self.run_fake(self.fake_mapping(current=500))["passed"])

    def test_41_remote_smoke_fails_on_revision_mismatch(self):
        mapping = self.fake_mapping(); mapping["/api/v1/wnba/runtime/release"] = FakeResponse(200, {"phase": "pre_activation_ready", "release": {"revision": "f" * 40, "release_id": self.release_id}, "storage_identity_sha256": self.storage_identity})
        self.assertFalse(self.run_fake(mapping)["passed"])

    def test_42_remote_smoke_fails_on_release_id_mismatch(self):
        mapping = self.fake_mapping(); mapping["/api/v1/wnba/runtime/release"] = FakeResponse(200, {"phase": "pre_activation_ready", "release": {"revision": self.revision, "release_id": "wrong"}, "storage_identity_sha256": self.storage_identity})
        self.assertFalse(self.run_fake(mapping)["passed"])

    def test_43_remote_smoke_fails_on_storage_identity_mismatch(self):
        mapping = self.fake_mapping(); mapping["/api/v1/wnba/runtime/release"] = FakeResponse(200, {"phase": "pre_activation_ready", "release": {"revision": self.revision, "release_id": self.release_id}, "storage_identity_sha256": "e" * 64})
        self.assertFalse(self.run_fake(mapping)["passed"])

    def test_44_remote_smoke_fails_on_service_name_mismatch(self):
        mapping = self.fake_mapping(); mapping["/api/v1/wnba/runtime/hosting"] = FakeResponse(200, {"provider": "render", "activation_requested": False, "host_contract_ready": True, "host_identity_sha256": "d" * 64, "host": {"service_name": "wrong"}})
        self.assertFalse(self.run_fake(mapping)["passed"])

    def test_45_remote_smoke_fails_on_wrong_provider(self):
        mapping = self.fake_mapping(); mapping["/api/v1/wnba/runtime/hosting"] = FakeResponse(200, {"provider": "other", "activation_requested": False, "host_contract_ready": True, "host_identity_sha256": "d" * 64, "host": {"service_name": self.service_name}})
        self.assertFalse(self.run_fake(mapping)["passed"])

    def test_46_invalid_timeout_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_fake(timeout_seconds=0)

    def test_47_invalid_expected_revision_is_rejected(self):
        with self.assertRaises(ValueError):
            s.run_hosted_staging_smoke(self.external_url, expected_revision="bad", expected_release_id=self.release_id, expected_storage_identity=self.storage_identity, client=FakeClient({}))

    def test_48_invalid_storage_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            s.run_hosted_staging_smoke(self.external_url, expected_revision=self.revision, expected_release_id=self.release_id, expected_storage_identity="bad", client=FakeClient({}))

    def test_49_main_registers_step5u_routes(self):
        paths = set(app.openapi().get("paths", {}))
        self.assertIn("/api/v1/wnba/runtime/hosting", paths)
        self.assertIn("/api/v1/wnba/runtime/hosting-smoke-plan", paths)

    def test_50_require_hosted_staging_ready_enforces_gate(self):
        self.assertTrue(s.require_hosted_staging_ready(env=self.env)["host_contract_ready"])
        env = dict(self.env); env[s.RENDER_FLAG_ENV] = "false"
        with self.assertRaises(s.WNBAHostedStagingNotReadyError):
            s.require_hosted_staging_ready(env=env)


if __name__ == "__main__":
    unittest.main()
