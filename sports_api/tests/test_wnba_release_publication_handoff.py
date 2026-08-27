from pathlib import Path
import json
import tempfile
import unittest

import sports_api.wnba_release_publication_handoff as s
from sports_api.main import app


class Step5VTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.revision = "a" * 40
        self.digest = "b" * 64
        self.image_repo = "ghcr.io/kyrepeak/kyre-sports-api"
        self.image_ref = f"{self.image_repo}@sha256:{self.digest}"
        self.release_id = "staging-release-5v-001"
        self.service_name = "kyre-sports-api-staging"
        self.external_url = "https://kyre-sports-api-staging.onrender.com"
        self.secret = "step-5v-test-secret-material-12345678901234567890"
        self.env = {
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_CURRENT_BOARD_STORE_PATH": str(root / "board.sqlite3"),
            "WNBA_PROP_FEED_STORE_PATH": str(root / "feed.sqlite3"),
            "WNBA_BACKTEST_STORE_PATH": str(root / "backtest.sqlite3"),
            "WNBA_BOARD_SCHEDULER_LOCK_PATH": str(root / "scheduler_lock.sqlite3"),
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET": self.secret,
            "SPORTSGAMEODDS_API_KEY": "step5v-provider-demo-key",
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
            "RENDER_SERVICE_ID": "srv-step5v123",
            "RENDER_SERVICE_NAME": self.service_name,
            "RENDER_SERVICE_TYPE": "web",
            "RENDER_EXTERNAL_URL": self.external_url,
            "RENDER_EXTERNAL_HOSTNAME": "kyre-sports-api-staging.onrender.com",
            "RENDER_GIT_COMMIT": self.revision,
            "RENDER_GIT_BRANCH": "api-foundation-v1",
            "RENDER_GIT_REPO_SLUG": "kyrepeak/kyre-sports-ai",
            "RENDER_INSTANCE_ID": "instance-step5v-1",
            s.REGISTRY_ENV: "ghcr.io",
            s.IMAGE_REPOSITORY_ENV: self.image_repo,
            s.PUBLISHED_IMAGE_REF_ENV: self.image_ref,
            s.PUBLICATION_VERIFIED_ENV: "true",
            s.PUBLISHER_ENV: "github-actions",
            s.SOURCE_REPOSITORY_ENV: "kyrepeak/kyre-sports-ai",
            s.HANDOFF_FORMAT_ENV: "render-staging-v1",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def readiness(self, env=None):
        return s.get_release_publication_handoff_readiness(env=self.env if env is None else env)

    def test_01_good_handoff_is_ready(self):
        self.assertTrue(self.readiness()["handoff_ready"])

    def test_02_good_handoff_keeps_activation_off(self):
        self.assertFalse(self.readiness()["activation_requested"])

    def test_03_registry_must_be_ghcr(self):
        env = dict(self.env); env[s.REGISTRY_ENV] = "docker.io"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_04_image_repository_must_be_ghcr(self):
        env = dict(self.env); env[s.IMAGE_REPOSITORY_ENV] = "docker.io/kyre/api"; env[s.PUBLISHED_IMAGE_REF_ENV] = "docker.io/kyre/api@sha256:" + self.digest; env["WNBA_DEPLOYMENT_IMAGE_REF"] = env[s.PUBLISHED_IMAGE_REF_ENV]
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_05_published_image_must_be_digest_pinned(self):
        env = dict(self.env); env[s.PUBLISHED_IMAGE_REF_ENV] = self.image_repo + ":latest"; env["WNBA_DEPLOYMENT_IMAGE_REF"] = self.image_repo + ":latest"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_06_published_repository_must_match_configured_repository(self):
        env = dict(self.env); env[s.IMAGE_REPOSITORY_ENV] = "ghcr.io/kyrepeak/other"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_07_published_image_must_match_step5t(self):
        env = dict(self.env); env[s.PUBLISHED_IMAGE_REF_ENV] = self.image_repo + "@sha256:" + ("c" * 64)
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_08_publication_verification_is_required(self):
        env = dict(self.env); env[s.PUBLICATION_VERIFIED_ENV] = "false"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_09_publisher_must_be_github_actions(self):
        env = dict(self.env); env[s.PUBLISHER_ENV] = "manual-shell"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_10_source_repository_must_match_host(self):
        env = dict(self.env); env[s.SOURCE_REPOSITORY_ENV] = "someone/other"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_11_release_revision_must_be_full_sha(self):
        env = dict(self.env); env["WNBA_DEPLOYMENT_REVISION"] = "abc"; env["RENDER_GIT_COMMIT"] = "abc"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_12_release_id_must_be_valid(self):
        env = dict(self.env); env["WNBA_RELEASE_ID"] = "x"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_13_handoff_format_is_versioned(self):
        env = dict(self.env); env[s.HANDOFF_FORMAT_ENV] = "unknown-v9"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_14_host_must_remain_render_staging(self):
        env = dict(self.env); env["WNBA_HOST_ENVIRONMENT"] = "production"
        self.assertFalse(self.readiness(env)["handoff_ready"])

    def test_15_storage_identity_is_present(self):
        self.assertEqual(64, len(self.readiness()["storage_identity_sha256"]))

    def test_16_host_identity_is_present(self):
        self.assertEqual(64, len(self.readiness()["host_identity_sha256"]))

    def test_17_digest_is_extracted_from_image_ref(self):
        self.assertEqual(self.digest, self.readiness()["publication"]["image_digest_sha256"])

    def test_18_publication_fields_are_sanitized(self):
        pub = self.readiness()["publication"]
        self.assertEqual("ghcr.io", pub["registry"])
        self.assertEqual(self.image_repo, pub["image_repository"])

    def test_19_handoff_identity_is_deterministic(self):
        self.assertEqual(self.readiness()["handoff_identity_sha256"], self.readiness()["handoff_identity_sha256"])

    def test_20_handoff_identity_changes_with_image(self):
        first = self.readiness()["handoff_identity_sha256"]
        env = dict(self.env)
        alt = self.image_repo + "@sha256:" + ("c" * 64)
        env[s.PUBLISHED_IMAGE_REF_ENV] = alt
        env["WNBA_DEPLOYMENT_IMAGE_REF"] = alt
        second = self.readiness(env)["handoff_identity_sha256"]
        self.assertNotEqual(first, second)

    def test_21_secrets_are_not_returned_in_readiness(self):
        self.assertNotIn(self.secret, repr(self.readiness()))
        self.assertNotIn("step5v-provider-demo-key", repr(self.readiness()))

    def test_22_manifest_is_ready(self):
        self.assertTrue(s.build_release_handoff_manifest(env=self.env)["handoff_ready"])

    def test_23_manifest_contains_exact_published_image(self):
        self.assertEqual(self.image_ref, s.build_release_handoff_manifest(env=self.env)["published_image_ref"])

    def test_24_manifest_never_activates_runtime(self):
        manifest = s.build_release_handoff_manifest(env=self.env)
        self.assertFalse(manifest["production_runtime_enabled"])
        self.assertFalse(manifest["activation_required"])

    def test_25_manifest_explicitly_says_no_secrets(self):
        self.assertFalse(s.build_release_handoff_manifest(env=self.env)["safety"]["contains_secrets"])

    def test_26_manifest_carries_host_and_storage_identity(self):
        manifest = s.build_release_handoff_manifest(env=self.env)
        self.assertEqual(64, len(manifest["host_identity_sha256"]))
        self.assertEqual(64, len(manifest["storage_identity_sha256"]))

    def test_27_plan_has_twelve_steps(self):
        self.assertEqual(12, s.build_release_handoff_plan(env=self.env)["step_count"])

    def test_28_plan_starts_with_registry_publication(self):
        plan = s.build_release_handoff_plan(env=self.env)
        self.assertEqual("publish_exact_container_to_registry", plan["steps"][0]["action"])

    def test_29_plan_keeps_runtime_disabled(self):
        plan = s.build_release_handoff_plan(env=self.env)
        row = next(x for x in plan["steps"] if x["action"] == "keep_runtime_disabled")
        self.assertIn("=false", row["requirement"])

    def test_30_plan_defers_activation_to_step5w(self):
        self.assertIn("Step 5W", s.build_release_handoff_plan(env=self.env)["steps"][-1]["requirement"])

    def test_31_api_performs_none_of_the_external_write_steps(self):
        plan = s.build_release_handoff_plan(env=self.env)
        self.assertTrue(all(row["performed_by_this_api"] is False for row in plan["steps"]))

    def test_32_plan_safety_blocks_sportsbook_and_monte_carlo(self):
        safety = s.build_release_handoff_plan(env=self.env)["safety"]
        self.assertTrue(safety["api_does_not_call_sportsbook"])
        self.assertTrue(safety["api_does_not_run_monte_carlo"])

    def test_33_require_ready_passes_good_environment(self):
        self.assertTrue(s.require_release_publication_handoff_ready(env=self.env)["handoff_ready"])

    def test_34_require_ready_raises_on_bad_environment(self):
        env = dict(self.env); env[s.PUBLICATION_VERIFIED_ENV] = "false"
        with self.assertRaises(s.WNBAReleasePublicationHandoffNotReadyError):
            s.require_release_publication_handoff_ready(env=env)

    def test_35_bundle_writes_four_files(self):
        out = self.root / "bundle"
        result = s.write_release_handoff_bundle(out, env=self.env)
        self.assertEqual(4, result["file_count"])

    def test_36_bundle_files_exist(self):
        out = self.root / "bundle"
        result = s.write_release_handoff_bundle(out, env=self.env)
        self.assertTrue(all(Path(path).exists() for path in result["files"]))

    def test_37_checksum_file_has_three_payload_entries(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        rows = json.loads((out / "SHA256SUMS.json").read_text())
        self.assertEqual(3, len(rows))
        self.assertTrue(all(len(row["sha256"]) == 64 for row in rows))

    def test_38_bundle_manifest_parses(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        path = next(out.glob("*.manifest.json"))
        self.assertEqual(self.release_id, json.loads(path.read_text())["release_id"])

    def test_39_bundle_plan_parses(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        path = next(out.glob("*.handoff-plan.json"))
        self.assertEqual(12, json.loads(path.read_text())["step_count"])

    def test_40_bundle_env_omits_real_secret_values(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        text = next(out.glob("*.render.env")).read_text()
        self.assertNotIn(self.secret, text)
        self.assertNotIn("step5v-provider-demo-key", text)

    def test_41_bundle_env_keeps_runtime_false(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        self.assertIn("WNBA_PRODUCTION_RUNTIME_ENABLED=false", next(out.glob("*.render.env")).read_text())

    def test_42_bundle_env_carries_published_image(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        self.assertIn(self.image_ref, next(out.glob("*.render.env")).read_text())

    def test_43_bundle_filename_uses_release_id(self):
        out = self.root / "bundle"
        s.write_release_handoff_bundle(out, env=self.env)
        self.assertTrue((out / f"{self.release_id}.manifest.json").exists())

    def test_44_main_registers_handoff_route(self):
        self.assertIn("/api/v1/wnba/runtime/handoff", set(app.openapi().get("paths", {})))

    def test_45_main_registers_handoff_plan_route(self):
        self.assertIn("/api/v1/wnba/runtime/handoff-plan", set(app.openapi().get("paths", {})))

    def test_46_model_and_schema_are_versioned(self):
        report = self.readiness()
        self.assertEqual(s.MODEL_VERSION, report["model_version"])
        self.assertEqual(s.SCHEMA_VERSION, report["schema_version"])

    def test_47_default_registry_is_ghcr(self):
        env = dict(self.env); env.pop(s.REGISTRY_ENV)
        self.assertEqual("ghcr.io", self.readiness(env)["publication"]["registry"])

    def test_48_default_image_repository_is_expected_repo(self):
        env = dict(self.env); env.pop(s.IMAGE_REPOSITORY_ENV)
        self.assertEqual(self.image_repo, self.readiness(env)["publication"]["image_repository"])

    def test_49_default_publisher_is_github_actions(self):
        env = dict(self.env); env.pop(s.PUBLISHER_ENV)
        self.assertEqual("github-actions", self.readiness(env)["publication"]["publisher"])

    def test_50_default_source_repository_matches_project(self):
        env = dict(self.env); env.pop(s.SOURCE_REPOSITORY_ENV)
        self.assertEqual("kyrepeak/kyre-sports-ai", self.readiness(env)["publication"]["source_repository"])

    def test_51_default_handoff_format_is_supported(self):
        env = dict(self.env); env.pop(s.HANDOFF_FORMAT_ENV)
        self.assertEqual("render-staging-v1", self.readiness(env)["publication"]["handoff_format"])

    def test_52_semantics_never_call_sportsbook(self):
        self.assertTrue(self.readiness()["semantics"]["api_does_not_call_sportsbook"])

    def test_53_semantics_never_run_monte_carlo(self):
        self.assertTrue(self.readiness()["semantics"]["api_does_not_run_monte_carlo"])

    def test_54_manifest_handoff_identity_matches_readiness(self):
        self.assertEqual(self.readiness()["handoff_identity_sha256"], s.build_release_handoff_manifest(env=self.env)["handoff_identity_sha256"])

    def test_55_bundle_refuses_unverified_publication(self):
        env = dict(self.env); env[s.PUBLICATION_VERIFIED_ENV] = "false"
        with self.assertRaises(s.WNBAReleasePublicationHandoffNotReadyError):
            s.write_release_handoff_bundle(self.root / "bad-bundle", env=env)


if __name__ == "__main__":
    unittest.main()
