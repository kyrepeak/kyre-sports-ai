from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import sports_api.wnba_staging_activation_gate as s
import sports_api.api.wnba_pregame_board_scheduler_staging_activation as api5w
from sports_api.main import app


class Step5WTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.revision = "a" * 40
        self.digest = "b" * 64
        self.image_repo = "ghcr.io/kyrepeak/kyre-sports-api"
        self.image_ref = f"{self.image_repo}@sha256:{self.digest}"
        self.release_id = "staging-release-5w-001"
        self.service_name = "kyre-sports-api-staging"
        self.external_url = "https://kyre-sports-api-staging.onrender.com"
        self.secret = "step-5w-test-secret-material-12345678901234567890"
        self.provider_key = "step5w-provider-demo-key"
        self.env = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_CURRENT_BOARD_STORE_PATH": str(root / "board.sqlite3"),
            "WNBA_PROP_FEED_STORE_PATH": str(root / "feed.sqlite3"),
            "WNBA_BACKTEST_STORE_PATH": str(root / "backtest.sqlite3"),
            "WNBA_BOARD_SCHEDULER_LOCK_PATH": str(root / "scheduler_lock.sqlite3"),
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET": self.secret,
            "SPORTSGAMEODDS_API_KEY": self.provider_key,
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
            "WNBA_STAGING_HOST_PROVIDER": "render",
            "WNBA_HOST_ENVIRONMENT": "staging",
            "WNBA_STAGING_EXTERNAL_URL": self.external_url,
            "WNBA_STAGING_EXPECTED_SERVICE_NAME": self.service_name,
            "WNBA_STAGING_EXPECTED_GIT_BRANCH": "api-foundation-v1",
            "RENDER": "true",
            "RENDER_SERVICE_ID": "srv-step5w123",
            "RENDER_SERVICE_NAME": self.service_name,
            "RENDER_SERVICE_TYPE": "web",
            "RENDER_EXTERNAL_URL": self.external_url,
            "RENDER_EXTERNAL_HOSTNAME": "kyre-sports-api-staging.onrender.com",
            "RENDER_GIT_COMMIT": self.revision,
            "RENDER_GIT_BRANCH": "api-foundation-v1",
            "RENDER_GIT_REPO_SLUG": "kyrepeak/kyre-sports-ai",
            "RENDER_INSTANCE_ID": "instance-step5w-1",
            "WNBA_RELEASE_REGISTRY": "ghcr.io",
            "WNBA_RELEASE_IMAGE_REPOSITORY": self.image_repo,
            "WNBA_RELEASE_PUBLISHED_IMAGE_REF": self.image_ref,
            "WNBA_RELEASE_PUBLICATION_VERIFIED": "true",
            "WNBA_RELEASE_PUBLISHER": "github-actions",
            "WNBA_RELEASE_SOURCE_REPOSITORY": "kyrepeak/kyre-sports-ai",
            "WNBA_RELEASE_HANDOFF_FORMAT": "render-staging-v1",
        }

    def tearDown(self):
        api5w._stop_worker()
        self.tmp.cleanup()

    def gate(self, env=None):
        return s.get_staging_activation_gate(env=self.env if env is None else env)

    def activated_env(self):
        checkpoint = self.gate()["activation_checkpoint_sha256"]
        env = dict(self.env)
        env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        env[s.APPROVAL_ENV] = "true"
        env[s.CHECKPOINT_ENV] = checkpoint
        env[s.ACTIVATED_AT_ENV] = "2020-01-01T00:00:00Z"
        return env

    def test_01_preactivation_checkpoint_is_ready(self):
        self.assertTrue(self.gate()["checkpoint_ready"])

    def test_02_preactivation_never_allows_live_cycle(self):
        self.assertFalse(self.gate()["live_cycle_allowed"])

    def test_03_preactivation_phase_is_explicit(self):
        self.assertEqual("pre_activation_checkpoint_ready", self.gate()["phase"])

    def test_04_checkpoint_is_sha256(self):
        self.assertEqual(64, len(self.gate()["activation_checkpoint_sha256"]))

    def test_05_checkpoint_is_deterministic(self):
        self.assertEqual(self.gate()["activation_checkpoint_sha256"], self.gate()["activation_checkpoint_sha256"])

    def test_06_checkpoint_ignores_render_instance_id(self):
        first = self.gate()["activation_checkpoint_sha256"]
        env = dict(self.env); env["RENDER_INSTANCE_ID"] = "replacement-instance"
        self.assertEqual(first, self.gate(env)["activation_checkpoint_sha256"])

    def test_07_checkpoint_changes_with_service_id(self):
        first = self.gate()["activation_checkpoint_sha256"]
        env = dict(self.env); env["RENDER_SERVICE_ID"] = "srv-other"
        self.assertNotEqual(first, self.gate(env)["activation_checkpoint_sha256"])

    def test_08_checkpoint_changes_with_image(self):
        first = self.gate()["activation_checkpoint_sha256"]
        env = dict(self.env)
        alt = self.image_repo + "@sha256:" + ("c" * 64)
        env["WNBA_DEPLOYMENT_IMAGE_REF"] = alt
        env["WNBA_RELEASE_PUBLISHED_IMAGE_REF"] = alt
        self.assertNotEqual(first, self.gate(env)["activation_checkpoint_sha256"])

    def test_09_checkpoint_changes_with_storage_identity(self):
        first = self.gate()["activation_checkpoint_sha256"]
        env = dict(self.env); env["WNBA_CURRENT_BOARD_STORE_PATH"] = str(self.root / "board2.sqlite3")
        self.assertNotEqual(first, self.gate(env)["activation_checkpoint_sha256"])

    def test_10_unverified_step5v_blocks_checkpoint(self):
        env = dict(self.env); env["WNBA_RELEASE_PUBLICATION_VERIFIED"] = "false"
        self.assertFalse(self.gate(env)["checkpoint_ready"])

    def test_11_missing_stable_host_field_blocks_checkpoint(self):
        env = dict(self.env); env.pop("RENDER_SERVICE_ID")
        self.assertFalse(self.gate(env)["checkpoint_ready"])

    def test_12_semantics_are_fail_closed(self):
        self.assertTrue(self.gate()["semantics"]["fail_closed"])

    def test_13_plan_has_eleven_steps(self):
        self.assertEqual(11, s.build_staging_activation_plan(env=self.env)["step_count"])

    def test_14_plan_does_not_require_manual_refresh(self):
        self.assertTrue(s.build_staging_activation_plan(env=self.env)["safety"]["manual_refresh_not_required"])

    def test_15_checkpoint_survives_activation_flag_transition(self):
        pre = self.gate()["activation_checkpoint_sha256"]
        env = self.activated_env()
        self.assertEqual(pre, self.gate(env)["activation_checkpoint_sha256"])

    def test_16_good_activated_environment_allows_live_cycle(self):
        self.assertTrue(self.gate(self.activated_env())["live_cycle_allowed"])

    def test_17_good_activated_phase_is_ready(self):
        self.assertEqual("active_gate_ready", self.gate(self.activated_env())["phase"])

    def test_18_good_activation_requires_frozen_step5r(self):
        self.assertTrue(self.gate(self.activated_env())["step_5r"]["scheduler_allowed"])

    def test_19_missing_explicit_approval_blocks(self):
        env = self.activated_env(); env.pop(s.APPROVAL_ENV)
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_20_wrong_checkpoint_blocks(self):
        env = self.activated_env(); env[s.CHECKPOINT_ENV] = "f" * 64
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_21_malformed_checkpoint_blocks(self):
        env = self.activated_env(); env[s.CHECKPOINT_ENV] = "abc"
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_22_missing_activation_timestamp_blocks(self):
        env = self.activated_env(); env.pop(s.ACTIVATED_AT_ENV)
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_23_naive_activation_timestamp_blocks(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2026-08-26T12:00:00"
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_24_materially_future_activation_timestamp_blocks(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2999-01-01T00:00:00Z"
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_25_host_identity_change_blocks_old_checkpoint(self):
        env = self.activated_env(); env["RENDER_SERVICE_ID"] = "srv-different"
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_26_release_change_blocks_old_checkpoint(self):
        env = self.activated_env(); env["WNBA_RELEASE_ID"] = "staging-release-5w-002"
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_27_provider_not_ready_blocks_through_step5r(self):
        env = self.activated_env(); env.pop("SPORTSGAMEODDS_API_KEY")
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_28_runtime_disabled_never_allows_live_cycle_even_with_approval(self):
        env = dict(self.env)
        env[s.APPROVAL_ENV] = "true"
        env[s.CHECKPOINT_ENV] = self.gate()["activation_checkpoint_sha256"]
        env[s.ACTIVATED_AT_ENV] = "2020-01-01T00:00:00Z"
        self.assertFalse(self.gate(env)["live_cycle_allowed"])

    def test_29_require_ready_raises_before_activation(self):
        with self.assertRaises(s.WNBAStagingActivationNotReadyError):
            s.require_staging_activation_ready(env=self.env)

    def test_30_require_ready_passes_good_activation(self):
        self.assertTrue(s.require_staging_activation_ready(env=self.activated_env())["live_cycle_allowed"])

    def test_31_first_live_cycle_blocked_gate_does_not_read_stores(self):
        with patch.object(s, "list_scheduler_runs") as runs:
            report = s.get_first_live_cycle_verification(env=self.env)
            self.assertFalse(report["first_live_cycle_verified"])
            runs.assert_not_called()

    def _live_gate_mock(self):
        return {
            "live_cycle_allowed": True,
            "blocking_reasons": [],
        }

    def test_32_first_live_cycle_without_run_is_not_verified(self):
        env = self.activated_env()
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), \
             patch.object(s, "list_scheduler_runs", return_value=[]), \
             patch.object(s, "list_publications", return_value=[]), \
             patch.object(s, "get_latest_publication", return_value=None):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_33_preactivation_run_is_ignored(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2026-01-02T00:00:00Z"
        run = {"completed_at_utc": "2026-01-01T23:59:00Z", "provider_collection_attempted": True, "publication_id": "pub1"}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[]), patch.object(s, "get_latest_publication", return_value=None):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_34_run_without_provider_attempt_is_ignored(self):
        env = self.activated_env()
        run = {"completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": False, "publication_id": "pub1"}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[]), patch.object(s, "get_latest_publication", return_value=None):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_35_run_without_publication_id_is_ignored(self):
        env = self.activated_env()
        run = {"completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": True, "publication_id": None}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[]), patch.object(s, "get_latest_publication", return_value=None):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_36_matching_postactivation_provider_publication_verifies(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2026-01-02T00:00:00Z"
        run = {"completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": True, "publication_id": "pub1"}
        pub = {"publication_id": "pub1", "content": {"published_at_utc": "2026-01-02T00:01:01Z"}}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[pub]), patch.object(s, "get_latest_publication", return_value=pub):
            self.assertTrue(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_37_publication_before_activation_does_not_verify(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2026-01-02T00:00:00Z"
        run = {"completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": True, "publication_id": "pub1"}
        pub = {"publication_id": "pub1", "content": {"published_at_utc": "2026-01-01T23:59:59Z"}}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[pub]), patch.object(s, "get_latest_publication", return_value=pub):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_38_missing_matching_publication_does_not_verify(self):
        env = self.activated_env()
        run = {"completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": True, "publication_id": "pub1"}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[]), patch.object(s, "get_latest_publication", return_value=None):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_39_latest_publication_must_exist(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2026-01-02T00:00:00Z"
        run = {"completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": True, "publication_id": "pub1"}
        pub = {"publication_id": "pub1", "content": {"published_at_utc": "2026-01-02T00:01:01Z"}}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[run]), patch.object(s, "list_publications", return_value=[pub]), patch.object(s, "get_latest_publication", return_value=None):
            self.assertFalse(s.get_first_live_cycle_verification(env=env)["first_live_cycle_verified"])

    def test_40_first_qualifying_provider_run_is_selected(self):
        env = self.activated_env(); env[s.ACTIVATED_AT_ENV] = "2026-01-02T00:00:00Z"
        early = {"run_id": "early", "completed_at_utc": "2026-01-02T00:01:00Z", "provider_collection_attempted": True, "publication_id": "pub1"}
        late = {"run_id": "late", "completed_at_utc": "2026-01-02T00:02:00Z", "provider_collection_attempted": True, "publication_id": "pub2"}
        pub1 = {"publication_id": "pub1", "content": {"published_at_utc": "2026-01-02T00:01:01Z"}}
        pub2 = {"publication_id": "pub2", "content": {"published_at_utc": "2026-01-02T00:02:01Z"}}
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[late, early]), patch.object(s, "list_publications", return_value=[pub2, pub1]), patch.object(s, "get_latest_publication", return_value=pub2):
            report = s.get_first_live_cycle_verification(env=env)
            self.assertEqual("early", report["provider_cycle"]["run_id"])

    def test_41_first_live_verification_is_read_only(self):
        env = self.activated_env()
        with patch.object(s, "get_staging_activation_gate", return_value=self._live_gate_mock()), patch.object(s, "list_scheduler_runs", return_value=[]), patch.object(s, "list_publications", return_value=[]), patch.object(s, "get_latest_publication", return_value=None):
            report = s.get_first_live_cycle_verification(env=env)
            self.assertTrue(report["semantics"]["does_not_trigger_scheduler"])

    def test_42_main_registers_activation_gate(self):
        self.assertIn("/api/v1/wnba/runtime/activation-gate", app.openapi()["paths"])

    def test_43_main_registers_activation_plan(self):
        self.assertIn("/api/v1/wnba/runtime/activation-plan", app.openapi()["paths"])

    def test_44_main_registers_first_live_cycle(self):
        self.assertIn("/api/v1/wnba/runtime/first-live-cycle", app.openapi()["paths"])

    def test_45_refresh_route_remains_post(self):
        methods = app.openapi()["paths"]["/api/v1/wnba/rankings/player-props/current/refresh"]
        self.assertIn("post", methods)

    def test_46_current_read_route_remains_get(self):
        methods = app.openapi()["paths"]["/api/v1/wnba/rankings/player-props/current"]
        self.assertIn("get", methods)

    def test_47_manual_refresh_blocks_before_step5w(self):
        with patch.object(api5w, "require_staging_activation_ready", side_effect=s.WNBAStagingActivationNotReadyError("blocked")), patch.object(api5w.step5q, "refresh_current_wnba_player_prop_board") as refresh:
            with self.assertRaises(HTTPException) as ctx:
                api5w.refresh_current_wnba_player_prop_board()
            self.assertEqual(503, ctx.exception.status_code)
            refresh.assert_not_called()

    def test_48_manual_refresh_delegates_after_step5w(self):
        with patch.object(api5w, "require_staging_activation_ready", return_value={"live_cycle_allowed": True}), patch.object(api5w.step5q, "refresh_current_wnba_player_prop_board", return_value={"outcome": "ok"}) as refresh:
            self.assertEqual("ok", api5w.refresh_current_wnba_player_prop_board()["outcome"])
            refresh.assert_called_once()

    def test_49_runtime_health_503_when_gate_blocked(self):
        with patch.object(api5w, "get_staging_activation_gate", return_value={"live_cycle_allowed": False, "phase": "activation_blocked", "blocking_reasons": ["x"]}):
            with self.assertRaises(HTTPException) as ctx:
                api5w.get_wnba_production_runtime_health()
            self.assertEqual(503, ctx.exception.status_code)

    def test_50_runtime_health_ready_when_gate_green(self):
        gate = {"live_cycle_allowed": True, "activation_checkpoint_sha256": "a" * 64, "activated_at_utc": "2020-01-01T00:00:00+00:00", "step_5r": {"scheduler_allowed": True}}
        with patch.object(api5w, "get_staging_activation_gate", return_value=gate):
            self.assertTrue(api5w.get_wnba_production_runtime_health()["live_cycle_allowed"])

    def test_51_runtime_readiness_includes_step5w(self):
        with patch.object(api5w, "get_production_runtime_readiness", return_value={"preflight_ready": True}), patch.object(api5w, "get_staging_activation_gate", return_value={"phase": "x"}):
            self.assertIn("step_5w_activation_gate", api5w.get_wnba_production_runtime_readiness())

    def test_52_scheduler_status_includes_step5w(self):
        with patch.object(api5w.step5q, "get_current_wnba_player_prop_scheduler_status", return_value={}), patch.object(api5w, "get_production_runtime_readiness", return_value={}), patch.object(api5w, "get_staging_activation_gate", return_value={"phase": "x"}):
            status = api5w.get_current_wnba_player_prop_scheduler_status()
            self.assertIn("step_5w", status["production_runtime"])

    def test_53_worker_blocked_gate_never_calls_step5q_cycle(self):
        stop = MagicMock(); stop.is_set.return_value = False; stop.wait.return_value = True
        with patch.object(api5w, "_worker_stop", stop), patch.object(api5w, "require_staging_activation_ready", side_effect=s.WNBAStagingActivationNotReadyError("blocked")), patch.object(api5w.step5q, "_run_one_background_cycle") as cycle:
            api5w._worker_loop(30)
            cycle.assert_not_called()

    def test_54_worker_green_gate_calls_step5q_cycle(self):
        stop = MagicMock(); stop.is_set.return_value = False; stop.wait.return_value = True
        with patch.object(api5w, "_worker_stop", stop), patch.object(api5w, "require_staging_activation_ready", return_value={"live_cycle_allowed": True}), patch.object(api5w.step5q, "_run_one_background_cycle", return_value={"outcome": "published"}) as cycle:
            api5w._worker_loop(30)
            cycle.assert_called_once()

    def test_55_start_worker_does_not_start_when_activation_not_requested(self):
        with patch.object(api5w, "get_staging_activation_gate", return_value={"activation_requested": False, "live_cycle_allowed": False, "phase": "pre", "blocking_reasons": []}), patch.object(api5w.threading, "Thread") as thread:
            api5w._start_worker()
            thread.assert_not_called()

    def test_56_model_and_schema_versions_are_explicit(self):
        report = self.gate()
        self.assertEqual(s.MODEL_VERSION, report["model_version"])
        self.assertEqual(s.SCHEMA_VERSION, report["schema_version"])

    def test_57_expected_step5u_active_failures_are_declared(self):
        self.assertEqual(sorted(["pre_activation_phase_required", "runtime_remains_disabled"]), self.gate()["expected_active_only_step_5u_failures"])

    def test_58_expected_step5v_active_failures_are_declared(self):
        self.assertEqual(sorted(["frozen_step_5u_host_contract_ready", "runtime_remains_disabled"]), self.gate()["expected_active_only_step_5v_failures"])

    def test_59_gate_never_returns_secret_values(self):
        text = repr(self.gate())
        self.assertNotIn(self.secret, text)
        self.assertNotIn(self.provider_key, text)

    def test_60_checkpoint_payload_excludes_ephemeral_instance_id(self):
        self.assertNotIn("instance_id", repr(self.gate()["checkpoint_payload"]))


if __name__ == "__main__":
    unittest.main()
