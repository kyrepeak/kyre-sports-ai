from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

import sports_api.wnba_release_activation_readiness as t
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


class Step5TTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.current_revision = "a" * 40
        self.previous_revision = "c" * 40
        self.current_image = "ghcr.io/kyre/api@sha256:" + ("b" * 64)
        self.previous_image = "ghcr.io/kyre/api@sha256:" + ("d" * 64)
        self.env = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_CURRENT_BOARD_STORE_PATH": str(root / "board.sqlite3"),
            "WNBA_PROP_FEED_STORE_PATH": str(root / "feed.sqlite3"),
            "WNBA_BACKTEST_STORE_PATH": str(root / "backtest.sqlite3"),
            "WNBA_BOARD_SCHEDULER_LOCK_PATH": str(root / "scheduler_lock.sqlite3"),
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET": "step-5t-test-secret-material-1234567890",
            "SPORTSGAMEODDS_API_KEY": "demo-key",
            "WNBA_BOARD_SCHEDULER_ENABLED": "true",
            "WNBA_BOARD_AUTO_ARCHIVE_ENABLED": "true",
            "WNBA_DEPLOYMENT_MODE": "container",
            "WNBA_DEPLOYMENT_REPLICA_COUNT": "1",
            "WNBA_PERSISTENT_VOLUME_ROOT": str(root),
            "WEB_CONCURRENCY": "2",
            "PORT": "8000",
            "WNBA_DEPLOYMENT_REVISION": self.current_revision,
            t.RELEASE_ID_ENV: "wnba-api-2026.08.26.1",
            t.RELEASE_CHANNEL_ENV: "production",
            t.DEPLOYMENT_IMAGE_REF_ENV: self.current_image,
            t.PREVIOUS_REVISION_ENV: self.previous_revision,
            t.PREVIOUS_IMAGE_REF_ENV: self.previous_image,
            t.INITIAL_RELEASE_ENV: "false",
            t.RELEASE_CREATED_AT_ENV: "2026-08-26T21:15:00Z",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def readiness(self, env=None):
        return t.get_release_readiness(env=self.env if env is None else env)

    def fake_mapping(self, *, revision=None, image_ref=None, release_id=None, storage_identity=None):
        report = self.readiness()
        return {
            "/health": FakeResponse(200, {"status": "ok"}),
            "/api/v1/wnba/runtime/deployment": FakeResponse(200, {"deployment_ready": True}),
            "/api/v1/wnba/runtime/release": FakeResponse(
                200,
                {
                    "release": {
                        "release_id": release_id or report["release"]["release_id"],
                        "revision": revision or report["release"]["revision"],
                        "image_ref": image_ref or report["release"]["image_ref"],
                    },
                    "storage_identity_sha256": storage_identity or report["storage_identity_sha256"],
                    "phase": report["phase"],
                },
            ),
        }

    def test_01_complete_release_is_ready(self):
        report = self.readiness()
        self.assertTrue(report["release_ready"])
        self.assertTrue(report["rollback_ready"])

    def test_02_preactivation_release_is_safe_to_activate(self):
        report = self.readiness()
        self.assertTrue(report["safe_to_activate"])
        self.assertEqual("pre_activation_ready", report["phase"])

    def test_03_activation_enabled_yields_active_release(self):
        env = dict(self.env)
        env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        report = self.readiness(env)
        self.assertTrue(report["release_ready"])
        self.assertTrue(report["active_release_healthy"])
        self.assertEqual("active", report["phase"])

    def test_04_missing_release_id_is_rejected(self):
        env = dict(self.env)
        env.pop(t.RELEASE_ID_ENV)
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_05_short_release_id_is_rejected(self):
        env = dict(self.env)
        env[t.RELEASE_ID_ENV] = "x"
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_06_release_id_with_spaces_is_rejected(self):
        env = dict(self.env)
        env[t.RELEASE_ID_ENV] = "bad release id"
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_07_nonproduction_channel_is_rejected(self):
        env = dict(self.env)
        env[t.RELEASE_CHANNEL_ENV] = "staging"
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_08_missing_revision_is_rejected(self):
        env = dict(self.env)
        env.pop("WNBA_DEPLOYMENT_REVISION")
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_09_short_revision_is_rejected(self):
        env = dict(self.env)
        env["WNBA_DEPLOYMENT_REVISION"] = "abcdef"
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_10_nonhex_revision_is_rejected(self):
        env = dict(self.env)
        env["WNBA_DEPLOYMENT_REVISION"] = "z" * 40
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_11_missing_image_digest_is_rejected(self):
        env = dict(self.env)
        env.pop(t.DEPLOYMENT_IMAGE_REF_ENV)
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_12_mutable_image_tag_is_rejected(self):
        env = dict(self.env)
        env[t.DEPLOYMENT_IMAGE_REF_ENV] = "ghcr.io/kyre/api:latest"
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_13_bad_image_digest_length_is_rejected(self):
        env = dict(self.env)
        env[t.DEPLOYMENT_IMAGE_REF_ENV] = "ghcr.io/kyre/api@sha256:" + ("a" * 10)
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_14_previous_revision_is_required_for_noninitial_release(self):
        env = dict(self.env)
        env.pop(t.PREVIOUS_REVISION_ENV)
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_15_previous_image_is_required_for_noninitial_release(self):
        env = dict(self.env)
        env.pop(t.PREVIOUS_IMAGE_REF_ENV)
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_16_same_previous_revision_is_rejected(self):
        env = dict(self.env)
        env[t.PREVIOUS_REVISION_ENV] = self.current_revision
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_17_same_previous_image_is_rejected(self):
        env = dict(self.env)
        env[t.PREVIOUS_IMAGE_REF_ENV] = self.current_image
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_18_initial_release_can_have_no_previous_target(self):
        env = dict(self.env)
        env[t.INITIAL_RELEASE_ENV] = "true"
        env.pop(t.PREVIOUS_REVISION_ENV)
        env.pop(t.PREVIOUS_IMAGE_REF_ENV)
        report = self.readiness(env)
        self.assertTrue(report["release_ready"])
        self.assertTrue(report["rollback_ready"])
        self.assertEqual("disable_runtime_only", report["rollback_target"]["mode"])

    def test_19_noninitial_release_uses_previous_image_rollback(self):
        report = self.readiness()
        self.assertEqual("redeploy_previous_immutable_image", report["rollback_target"]["mode"])
        self.assertEqual(self.previous_image, report["rollback_target"]["image_ref"])

    def test_20_optional_created_at_accepts_timezone_aware_iso(self):
        report = self.readiness()
        self.assertTrue(report["release_ready"])
        self.assertTrue(report["release"]["created_at_utc"].endswith("+00:00"))

    def test_21_invalid_created_at_is_rejected_when_supplied(self):
        env = dict(self.env)
        env[t.RELEASE_CREATED_AT_ENV] = "yesterday-ish"
        self.assertFalse(self.readiness(env)["release_ready"])

    def test_22_storage_identity_is_deterministic(self):
        one = self.readiness()["storage_identity_sha256"]
        two = self.readiness()["storage_identity_sha256"]
        self.assertEqual(one, two)
        self.assertEqual(64, len(one))

    def test_23_manifest_fingerprint_is_deterministic(self):
        one = self.readiness()["release"]["manifest_fingerprint_sha256"]
        two = self.readiness()["release"]["manifest_fingerprint_sha256"]
        self.assertEqual(one, two)
        self.assertEqual(64, len(one))

    def test_24_changing_image_changes_manifest_fingerprint(self):
        one = self.readiness()["release"]["manifest_fingerprint_sha256"]
        env = dict(self.env)
        env[t.DEPLOYMENT_IMAGE_REF_ENV] = "ghcr.io/kyre/api@sha256:" + ("e" * 64)
        two = self.readiness(env)["release"]["manifest_fingerprint_sha256"]
        self.assertNotEqual(one, two)

    def test_25_activation_plan_starts_read_only(self):
        plan = t.build_activation_plan(env=self.env, base_url="https://api.example.com")
        self.assertTrue(plan["safety"]["steps_before_activation_are_read_only"])
        self.assertTrue(all(not row["write_capable"] for row in plan["steps"][:5]))

    def test_26_activation_plan_first_write_is_explicit_activation(self):
        plan = t.build_activation_plan(env=self.env)
        writes = [row for row in plan["steps"] if row["write_capable"]]
        self.assertEqual("enable_frozen_step_5r_runtime_switch", writes[0]["action"])

    def test_27_activation_plan_never_requires_manual_refresh(self):
        plan = t.build_activation_plan(env=self.env)
        self.assertTrue(plan["safety"]["manual_refresh_endpoint_is_never_required"])
        self.assertNotIn("/refresh", repr(plan["steps"]))

    def test_28_rollback_plan_disables_runtime_first(self):
        plan = t.build_rollback_plan(env=self.env)
        self.assertEqual("disable_production_runtime", plan["steps"][0]["action"])

    def test_29_rollback_plan_preserves_volume(self):
        plan = t.build_rollback_plan(env=self.env)
        self.assertTrue(plan["invariants"]["persistent_volume_is_never_deleted"])
        self.assertTrue(plan["target"]["preserve_persistent_volume"])

    def test_30_rollback_plan_never_reverses_schema(self):
        plan = t.build_rollback_plan(env=self.env)
        self.assertTrue(plan["invariants"]["schema_is_never_migrated_backward"])
        self.assertFalse(plan["target"]["reverse_schema_migrations"])

    def test_31_require_release_ready_returns_report(self):
        self.assertTrue(t.require_release_ready(env=self.env)["release_ready"])

    def test_32_require_release_ready_rejects_bad_image(self):
        env = dict(self.env)
        env[t.DEPLOYMENT_IMAGE_REF_ENV] = "kyre/api:latest"
        with self.assertRaises(t.WNBAReleaseNotReadyError):
            t.require_release_ready(env=env)

    def test_33_remote_verification_passes_for_exact_identity(self):
        report = self.readiness()
        client = FakeClient(self.fake_mapping())
        result = t.run_release_verification(
            "https://api.example.com",
            expected_revision=self.current_revision,
            expected_image_ref=self.current_image,
            expected_release_id=report["release"]["release_id"],
            expected_storage_identity=report["storage_identity_sha256"],
            client=client,
        )
        self.assertTrue(result["passed"])

    def test_34_remote_verification_fails_revision_mismatch(self):
        client = FakeClient(self.fake_mapping(revision="e" * 40))
        result = t.run_release_verification(
            "https://api.example.com",
            expected_revision=self.current_revision,
            expected_image_ref=self.current_image,
            client=client,
        )
        self.assertFalse(result["passed"])

    def test_35_remote_verification_fails_image_mismatch(self):
        client = FakeClient(self.fake_mapping(image_ref="ghcr.io/kyre/api@sha256:" + ("e" * 64)))
        result = t.run_release_verification(
            "https://api.example.com",
            expected_revision=self.current_revision,
            expected_image_ref=self.current_image,
            client=client,
        )
        self.assertFalse(result["passed"])

    def test_36_remote_verification_fails_storage_mismatch(self):
        report = self.readiness()
        client = FakeClient(self.fake_mapping(storage_identity="f" * 64))
        result = t.run_release_verification(
            "https://api.example.com",
            expected_revision=self.current_revision,
            expected_image_ref=self.current_image,
            expected_storage_identity=report["storage_identity_sha256"],
            client=client,
        )
        self.assertFalse(result["passed"])

    def test_37_remote_verification_is_get_only(self):
        client = FakeClient(self.fake_mapping())
        t.run_release_verification(
            "https://api.example.com",
            expected_revision=self.current_revision,
            expected_image_ref=self.current_image,
            client=client,
        )
        self.assertTrue(client.calls)
        self.assertTrue(all(method == "GET" for method, _, _ in client.calls))

    def test_38_remote_http_url_is_rejected(self):
        with self.assertRaises(Exception):
            t.run_release_verification(
                "http://api.example.com",
                expected_revision=self.current_revision,
                expected_image_ref=self.current_image,
                client=FakeClient({}),
            )

    def test_39_invalid_expected_revision_is_rejected(self):
        with self.assertRaises(t.WNBAReleaseVerificationError):
            t.run_release_verification(
                "https://api.example.com",
                expected_revision="bad",
                expected_image_ref=self.current_image,
                client=FakeClient({}),
            )

    def test_40_invalid_expected_image_is_rejected(self):
        with self.assertRaises(t.WNBAReleaseVerificationError):
            t.run_release_verification(
                "https://api.example.com",
                expected_revision=self.current_revision,
                expected_image_ref="latest",
                client=FakeClient({}),
            )

    def test_41_invalid_expected_storage_identity_is_rejected(self):
        with self.assertRaises(t.WNBAReleaseVerificationError):
            t.run_release_verification(
                "https://api.example.com",
                expected_revision=self.current_revision,
                expected_image_ref=self.current_image,
                expected_storage_identity="short",
                client=FakeClient({}),
            )

    def test_42_main_registers_step5t_release_route(self):
        paths = set(app.openapi().get("paths", {}))
        self.assertIn("/api/v1/wnba/runtime/release", paths)

    def test_43_main_registers_activation_plan_route(self):
        paths = set(app.openapi().get("paths", {}))
        self.assertIn("/api/v1/wnba/runtime/activation-plan", paths)

    def test_44_main_registers_rollback_plan_route(self):
        paths = set(app.openapi().get("paths", {}))
        self.assertIn("/api/v1/wnba/runtime/rollback-plan", paths)

    def test_45_report_declares_frozen_authority_and_no_model_work(self):
        semantics = self.readiness()["semantics"]
        self.assertTrue(semantics["frozen_step_5r_remains_activation_authority"])
        self.assertTrue(semantics["frozen_step_5s_remains_deployment_authority"])
        self.assertTrue(semantics["release_gate_does_not_call_sportsbook"])
        self.assertTrue(semantics["release_gate_does_not_run_monte_carlo"])


if __name__ == "__main__":
    unittest.main()
