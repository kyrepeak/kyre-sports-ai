import unittest
from unittest.mock import patch

import httpx

import sports_api.wnba_render_attachment_readiness as s


class Step5YTests(unittest.TestCase):
    def setUp(self):
        self.revision = "a" * 40
        self.digest = "b" * 64
        self.image = f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{self.digest}"
        self.release_id = "wnba-step5y-test"
        self.service_id = "srv-step5y"
        self.service_name = "kyre-sports-api-staging"
        self.step5x_identity = "c" * 64
        self.disk_id = "dsk-" + "d" * 20

    def step5x(self):
        return {
            "ready_for_explicit_activation": True,
            "deployment_identity_sha256": self.step5x_identity,
            "activation_checkpoint_sha256": "e" * 64,
            "render_service_id": self.service_id,
            "render_service_name": self.service_name,
            "published_image_ref": self.image,
            "release_id": self.release_id,
            "revision": self.revision,
        }

    def ready_env(self):
        env = {
            s.ATTACHMENT_VERIFIED_ENV: "true",
            s.DEPLOYED_IMAGE_REF_ENV: self.image,
            s.DISK_ID_ENV: self.disk_id,
            s.DISK_NAME_ENV: s.DEFAULT_DISK_NAME,
            s.DISK_MOUNT_PATH_ENV: s.DEFAULT_DISK_MOUNT_PATH,
            s.DISK_SIZE_GB_ENV: "1",
            s.INSTANCE_COUNT_ENV: "1",
            s.REGISTRY_ACCESS_VERIFIED_ENV: "true",
            s.SECRET_WIRING_VERIFIED_ENV: "true",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        }
        with patch.object(s, "get_real_staging_deployment_readiness", return_value=self.step5x()):
            draft = s.get_render_attachment_readiness(env=env)
        env[s.ATTACHMENT_EVIDENCE_ENV] = draft["attachment_evidence_sha256"]
        return env

    def readiness(self, env=None, step5x=None):
        with patch.object(
            s,
            "get_real_staging_deployment_readiness",
            return_value=self.step5x() if step5x is None else step5x,
        ):
            return s.get_render_attachment_readiness(env=self.ready_env() if env is None else env)

    def api_docs(self):
        expected = s.expected_render_env_values(
            release_id=self.release_id,
            revision=self.revision,
            image_ref=self.image,
            service_name=self.service_name,
        )
        env_rows = [{"envVar": {"key": key, "value": value}} for key, value in expected.items()]
        env_rows.extend(
            [
                {"envVar": {"key": "SPORTSGAMEODDS_API_KEY", "value": "secret-provider-value"}},
                {"envVar": {"key": "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET", "value": "x" * 40}},
            ]
        )
        return {
            "service": {
                "id": self.service_id,
                "name": self.service_name,
                "type": "web_service",
                "image": {"imagePath": self.image},
            },
            "disks": [
                {
                    "disk": {
                        "id": self.disk_id,
                        "name": s.DEFAULT_DISK_NAME,
                        "mountPath": s.DEFAULT_DISK_MOUNT_PATH,
                        "sizeGB": 1,
                        "serviceId": self.service_id,
                    }
                }
            ],
            "instances": [{"instance": {"id": "ins-one"}}],
            "env_vars": env_rows,
            "expected_env": expected,
        }

    def validate(self, docs=None):
        docs = self.api_docs() if docs is None else docs
        return s.validate_render_api_documents(
            service_document=docs["service"],
            disks_document=docs["disks"],
            instances_document=docs["instances"],
            env_vars_document=docs["env_vars"],
            expected_service_id=self.service_id,
            expected_service_name=self.service_name,
            expected_image_ref=self.image,
            expected_env_values=docs["expected_env"],
            step5x_identity=self.step5x_identity,
        )

    def test_01_expected_env_requires_full_revision(self):
        with self.assertRaises(s.WNBARenderAttachmentError):
            s.expected_render_env_values(release_id="rel", revision="abc", image_ref=self.image)

    def test_02_expected_env_requires_immutable_image(self):
        with self.assertRaises(s.WNBARenderAttachmentError):
            s.expected_render_env_values(release_id="rel", revision=self.revision, image_ref="ghcr.io/x:latest")

    def test_03_expected_env_runtime_is_disabled(self):
        env = s.expected_render_env_values(release_id=self.release_id, revision=self.revision, image_ref=self.image)
        self.assertEqual("false", env["WNBA_PRODUCTION_RUNTIME_ENABLED"])

    def test_04_expected_env_has_four_persistent_databases(self):
        env = s.expected_render_env_values(release_id=self.release_id, revision=self.revision, image_ref=self.image)
        keys = [
            "WNBA_CURRENT_BOARD_STORE_PATH",
            "WNBA_PROP_FEED_STORE_PATH",
            "WNBA_BACKTEST_STORE_PATH",
            "WNBA_BOARD_SCHEDULER_LOCK_PATH",
        ]
        self.assertTrue(all(env[key].startswith(s.DEFAULT_DISK_MOUNT_PATH + "/") for key in keys))

    def test_05_spec_contains_no_secret_values(self):
        spec = s.build_render_attachment_spec(release_id=self.release_id, revision=self.revision, image_ref=self.image)
        self.assertFalse(spec["safety"]["secret_values_in_specification"])
        self.assertEqual(list(s.SECRET_ENV_KEYS), spec["secret_environment_keys"])

    def test_06_spec_is_single_instance(self):
        spec = s.build_render_attachment_spec(release_id=self.release_id, revision=self.revision, image_ref=self.image)
        self.assertEqual(1, spec["service"]["num_instances"])

    def test_07_spec_uses_persistent_disk(self):
        spec = s.build_render_attachment_spec(release_id=self.release_id, revision=self.revision, image_ref=self.image)
        self.assertEqual(s.DEFAULT_DISK_MOUNT_PATH, spec["disk"]["mount_path"])

    def test_08_green_readiness_passes(self):
        self.assertTrue(self.readiness()["render_attachment_ready"])

    def test_09_green_phase_is_explicit(self):
        self.assertEqual("render_attachment_verified", self.readiness()["phase"])

    def test_10_step5x_failure_blocks(self):
        step5x = self.step5x(); step5x["ready_for_explicit_activation"] = False
        self.assertFalse(self.readiness(step5x=step5x)["render_attachment_ready"])

    def test_11_activation_requested_blocks(self):
        env = self.ready_env(); env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_12_attachment_marker_required(self):
        env = self.ready_env(); env[s.ATTACHMENT_VERIFIED_ENV] = "false"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_13_mutable_deployed_image_blocks(self):
        env = self.ready_env(); env[s.DEPLOYED_IMAGE_REF_ENV] = "ghcr.io/kyrepeak/kyre-sports-api:latest"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_14_image_drift_blocks(self):
        env = self.ready_env(); env[s.DEPLOYED_IMAGE_REF_ENV] = f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'1'*64}"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_15_disk_id_required(self):
        env = self.ready_env(); env[s.DISK_ID_ENV] = "disk"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_16_disk_name_drift_blocks(self):
        env = self.ready_env(); env[s.DISK_NAME_ENV] = "wrong"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_17_disk_mount_drift_blocks(self):
        env = self.ready_env(); env[s.DISK_MOUNT_PATH_ENV] = "/tmp"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_18_disk_size_too_small_blocks(self):
        env = self.ready_env(); env[s.DISK_SIZE_GB_ENV] = "0"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_19_instance_count_must_be_one(self):
        env = self.ready_env(); env[s.INSTANCE_COUNT_ENV] = "2"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_20_registry_verification_required(self):
        env = self.ready_env(); env[s.REGISTRY_ACCESS_VERIFIED_ENV] = "false"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_21_secret_wiring_verification_required(self):
        env = self.ready_env(); env[s.SECRET_WIRING_VERIFIED_ENV] = "false"
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_22_evidence_hash_required(self):
        env = self.ready_env(); env.pop(s.ATTACHMENT_EVIDENCE_ENV)
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_23_evidence_hash_drift_blocks(self):
        env = self.ready_env(); env[s.ATTACHMENT_EVIDENCE_ENV] = "1" * 64
        self.assertFalse(self.readiness(env=env)["render_attachment_ready"])

    def test_24_readiness_is_network_free(self):
        self.assertTrue(self.readiness()["semantics"]["readiness_is_network_free"])

    def test_25_readiness_does_not_call_sportsbook(self):
        self.assertTrue(self.readiness()["semantics"]["readiness_does_not_call_sportsbook"])

    def test_26_readiness_does_not_run_monte_carlo(self):
        self.assertTrue(self.readiness()["semantics"]["readiness_does_not_run_monte_carlo"])

    def test_27_api_documents_green(self):
        self.assertTrue(self.validate()["passed"])

    def test_28_service_id_mismatch_fails(self):
        docs = self.api_docs(); docs["service"]["id"] = "srv-other"
        self.assertIn("service_id_mismatch", self.validate(docs)["failures"])

    def test_29_service_name_mismatch_fails(self):
        docs = self.api_docs(); docs["service"]["name"] = "other"
        self.assertIn("service_name_mismatch", self.validate(docs)["failures"])

    def test_30_service_type_must_be_web(self):
        docs = self.api_docs(); docs["service"]["type"] = "background_worker"
        self.assertIn("service_type_not_web", self.validate(docs)["failures"])

    def test_31_service_document_must_contain_exact_image(self):
        docs = self.api_docs(); docs["service"]["image"]["imagePath"] = "ghcr.io/kyrepeak/kyre-sports-api:latest"
        self.assertIn("immutable_image_not_present_in_service_document", self.validate(docs)["failures"])

    def test_32_missing_disk_fails(self):
        docs = self.api_docs(); docs["disks"] = []
        self.assertIn("expected_single_persistent_disk_not_found", self.validate(docs)["failures"])

    def test_33_two_matching_disks_fail(self):
        docs = self.api_docs(); docs["disks"] = docs["disks"] * 2
        self.assertIn("expected_single_persistent_disk_not_found", self.validate(docs)["failures"])

    def test_34_bad_disk_id_fails(self):
        docs = self.api_docs(); docs["disks"][0]["disk"]["id"] = "bad"
        self.assertIn("persistent_disk_id_invalid", self.validate(docs)["failures"])

    def test_35_two_instances_fail(self):
        docs = self.api_docs(); docs["instances"].append({"instance": {"id": "ins-two"}})
        self.assertIn("instance_count_not_one", self.validate(docs)["failures"])

    def test_36_missing_non_secret_env_fails(self):
        docs = self.api_docs(); docs["env_vars"] = [row for row in docs["env_vars"] if (row.get("envVar") or {}).get("key") != "WNBA_DEPLOYMENT_MODE"]
        self.assertIn("required_non_secret_env_keys_missing", self.validate(docs)["failures"])

    def test_37_mismatched_non_secret_env_fails(self):
        docs = self.api_docs()
        for row in docs["env_vars"]:
            if (row.get("envVar") or {}).get("key") == "WNBA_DEPLOYMENT_REPLICA_COUNT":
                row["envVar"]["value"] = "2"
        self.assertIn("required_non_secret_env_values_mismatch", self.validate(docs)["failures"])

    def test_38_missing_provider_secret_fails_without_returning_values(self):
        docs = self.api_docs(); docs["env_vars"] = [row for row in docs["env_vars"] if (row.get("envVar") or {}).get("key") != "SPORTSGAMEODDS_API_KEY"]
        result = self.validate(docs)
        self.assertIn("required_secret_keys_missing", result["failures"])
        self.assertFalse(result["environment"]["secret_values_returned"])
        self.assertNotIn("secret-provider-value", str(result))

    def test_39_evidence_is_sha256(self):
        self.assertEqual(64, len(self.validate()["attachment_evidence_sha256"]))

    def test_40_attestation_env_marks_green(self):
        result = self.validate()
        self.assertEqual("true", result["attestation_environment"][s.ATTACHMENT_VERIFIED_ENV])
        self.assertEqual(self.disk_id, result["attestation_environment"][s.DISK_ID_ENV])

    def test_41_run_verifier_requires_api_key(self):
        with self.assertRaises(s.WNBARenderAPIVerificationError):
            s.run_render_api_attachment_verification(
                service_id=self.service_id,
                service_name=self.service_name,
                image_ref=self.image,
                release_id=self.release_id,
                revision=self.revision,
                step5x_identity=self.step5x_identity,
                env={},
            )

    def test_42_run_verifier_rejects_zero_timeout(self):
        with self.assertRaises(s.WNBARenderAPIVerificationError):
            s.run_render_api_attachment_verification(
                service_id=self.service_id,
                service_name=self.service_name,
                image_ref=self.image,
                release_id=self.release_id,
                revision=self.revision,
                step5x_identity=self.step5x_identity,
                api_key="token",
                timeout_seconds=0,
            )

    def test_43_mock_render_api_uses_four_gets_and_passes(self):
        docs = self.api_docs()

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual("GET", request.method)
            if request.url.path == f"/v1/services/{self.service_id}":
                return httpx.Response(200, json=docs["service"])
            if request.url.path == "/v1/disks":
                return httpx.Response(200, json=docs["disks"])
            if request.url.path == f"/v1/services/{self.service_id}/instances":
                return httpx.Response(200, json=docs["instances"])
            if request.url.path == f"/v1/services/{self.service_id}/env-vars":
                return httpx.Response(200, json=docs["env_vars"])
            return httpx.Response(404, json={})

        result = s.run_render_api_attachment_verification(
            service_id=self.service_id,
            service_name=self.service_name,
            image_ref=self.image,
            release_id=self.release_id,
            revision=self.revision,
            step5x_identity=self.step5x_identity,
            api_key="token",
            transport=httpx.MockTransport(handler),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(4, result["render_api"]["request_count"])
        self.assertEqual(["GET"] * 4, result["render_api"]["methods"])

    def test_44_mock_render_api_http_error_is_fail_closed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": "denied"})

        with self.assertRaises(s.WNBARenderAPIVerificationError):
            s.run_render_api_attachment_verification(
                service_id=self.service_id,
                service_name=self.service_name,
                image_ref=self.image,
                release_id=self.release_id,
                revision=self.revision,
                step5x_identity=self.step5x_identity,
                api_key="token",
                transport=httpx.MockTransport(handler),
            )

    def test_45_mock_render_api_never_returns_api_key(self):
        docs = self.api_docs()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == f"/v1/services/{self.service_id}":
                return httpx.Response(200, json=docs["service"])
            if request.url.path == "/v1/disks":
                return httpx.Response(200, json=docs["disks"])
            if request.url.path == f"/v1/services/{self.service_id}/instances":
                return httpx.Response(200, json=docs["instances"])
            return httpx.Response(200, json=docs["env_vars"])

        result = s.run_render_api_attachment_verification(
            service_id=self.service_id,
            service_name=self.service_name,
            image_ref=self.image,
            release_id=self.release_id,
            revision=self.revision,
            step5x_identity=self.step5x_identity,
            api_key="super-secret-render-token",
            transport=httpx.MockTransport(handler),
        )
        self.assertFalse(result["render_api"]["api_key_returned"])
        self.assertNotIn("super-secret-render-token", str(result))


if __name__ == "__main__":
    unittest.main()
