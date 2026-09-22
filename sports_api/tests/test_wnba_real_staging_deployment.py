import unittest
from unittest.mock import patch

import httpx

import sports_api.wnba_real_staging_deployment as s


class Step5XTests(unittest.TestCase):
    def setUp(self):
        self.revision = "a" * 40
        self.digest = "b" * 64
        self.image = f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{self.digest}"
        self.storage = "c" * 64
        self.checkpoint = "d" * 64
        self.release_id = "wnba-step5x-test"
        self.service_name = "kyre-sports-api-staging"
        self.service_id = "srv-step5x"
        self.url = "https://kyre-sports-api-staging.onrender.com"

    def hosted(self):
        return {
            "host_contract_ready": True,
            "provider": "render",
            "environment": "staging",
            "external_url": self.url,
            "host_identity_sha256": "e" * 64,
            "storage_identity_sha256": self.storage,
            "host": {
                "service_id": self.service_id,
                "service_name": self.service_name,
                "repository": "kyrepeak/kyre-sports-ai",
                "git_branch": "api-foundation-v1",
                "git_commit": self.revision,
            },
            "release": {
                "release_id": self.release_id,
                "revision": self.revision,
                "image_ref": self.image,
            },
        }

    def handoff(self):
        return {
            "handoff_ready": True,
            "handoff_identity_sha256": "f" * 64,
            "publication": {
                "published_image_ref": self.image,
                "image_digest_sha256": self.digest,
            },
            "release": {
                "release_id": self.release_id,
                "revision": self.revision,
                "image_ref": self.image,
            },
        }

    def gate(self):
        return {
            "phase": "pre_activation_checkpoint_ready",
            "checkpoint_ready": True,
            "activation_requested": False,
            "live_cycle_allowed": False,
            "activation_checkpoint_sha256": self.checkpoint,
            "checkpoint_payload": {
                "release": {
                    "release_id": self.release_id,
                    "revision": self.revision,
                    "image_ref": self.image,
                },
                "host": {
                    "service_id": self.service_id,
                    "service_name": self.service_name,
                    "external_url": self.url,
                },
                "storage_identity_sha256": self.storage,
            },
        }

    def readiness(self, hosted=None, handoff=None, gate=None):
        with patch.object(s, "get_hosted_staging_readiness", return_value=self.hosted() if hosted is None else hosted), \
             patch.object(s, "get_release_publication_handoff_readiness", return_value=self.handoff() if handoff is None else handoff), \
             patch.object(s, "get_staging_activation_gate", return_value=self.gate() if gate is None else gate):
            return s.get_real_staging_deployment_readiness(env={})

    def docs(self):
        return {
            "step_5u_hosting": self.hosted(),
            "step_5v_handoff": self.handoff(),
            "step_5w_activation_gate": self.gate(),
            "step_5x_staging_deployment": {
                "ready_for_explicit_activation": True,
                "revision": self.revision,
                "release_id": self.release_id,
                "published_image_ref": self.image,
                "render_service_name": self.service_name,
                "storage_identity_sha256": self.storage,
                "activation_checkpoint_sha256": self.checkpoint,
                "deployment_identity_sha256": "9" * 64,
            },
        }

    def statuses(self):
        return {"runtime_health_pre_activation": 503, "current_board_read": 409}

    def validate(self, docs=None, statuses=None, checkpoint=True):
        return s._validate_remote_documents(
            self.docs() if docs is None else docs,
            self.statuses() if statuses is None else statuses,
            expected_revision=self.revision,
            expected_release_id=self.release_id,
            expected_image_ref=self.image,
            expected_service_name=self.service_name,
            expected_storage_identity=self.storage,
            expected_checkpoint=self.checkpoint if checkpoint else None,
        )

    def test_01_green_real_host_is_ready(self):
        self.assertTrue(self.readiness()["ready_for_explicit_activation"])

    def test_02_green_phase_is_explicit(self):
        self.assertEqual("real_host_preactivation_ready", self.readiness()["phase"])

    def test_03_deployment_identity_is_sha256(self):
        self.assertEqual(64, len(self.readiness()["deployment_identity_sha256"]))

    def test_04_deployment_identity_is_deterministic(self):
        self.assertEqual(self.readiness()["deployment_identity_sha256"], self.readiness()["deployment_identity_sha256"])

    def test_05_step5u_failure_blocks(self):
        hosted = self.hosted(); hosted["host_contract_ready"] = False
        self.assertFalse(self.readiness(hosted=hosted)["ready_for_explicit_activation"])

    def test_06_step5v_failure_blocks(self):
        handoff = self.handoff(); handoff["handoff_ready"] = False
        self.assertFalse(self.readiness(handoff=handoff)["ready_for_explicit_activation"])

    def test_07_step5w_checkpoint_failure_blocks(self):
        gate = self.gate(); gate["checkpoint_ready"] = False
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_08_wrong_step5w_phase_blocks(self):
        gate = self.gate(); gate["phase"] = "activation_blocked"
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_09_activation_requested_blocks(self):
        gate = self.gate(); gate["activation_requested"] = True
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_10_live_cycle_allowed_blocks(self):
        gate = self.gate(); gate["live_cycle_allowed"] = True
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_11_non_render_host_blocks(self):
        hosted = self.hosted(); hosted["provider"] = "other"
        self.assertFalse(self.readiness(hosted=hosted)["ready_for_explicit_activation"])

    def test_12_non_staging_host_blocks(self):
        hosted = self.hosted(); hosted["environment"] = "production"
        self.assertFalse(self.readiness(hosted=hosted)["ready_for_explicit_activation"])

    def test_13_non_https_url_blocks(self):
        hosted = self.hosted(); hosted["external_url"] = "http://example.com"
        gate = self.gate(); gate["checkpoint_payload"]["host"]["external_url"] = "http://example.com"
        self.assertFalse(self.readiness(hosted=hosted, gate=gate)["ready_for_explicit_activation"])

    def test_14_missing_service_identity_blocks(self):
        hosted = self.hosted(); hosted["host"]["service_id"] = None
        self.assertFalse(self.readiness(hosted=hosted)["ready_for_explicit_activation"])

    def test_15_mutable_image_blocks(self):
        hosted = self.hosted(); hosted["release"]["image_ref"] = "ghcr.io/kyrepeak/kyre-sports-api:latest"
        handoff = self.handoff(); handoff["publication"]["published_image_ref"] = "ghcr.io/kyrepeak/kyre-sports-api:latest"
        gate = self.gate(); gate["checkpoint_payload"]["release"]["image_ref"] = "ghcr.io/kyrepeak/kyre-sports-api:latest"
        self.assertFalse(self.readiness(hosted=hosted, handoff=handoff, gate=gate)["ready_for_explicit_activation"])

    def test_16_published_image_mismatch_blocks(self):
        handoff = self.handoff(); handoff["publication"]["published_image_ref"] = f"ghcr.io/kyrepeak/kyre-sports-api@sha256:{'1'*64}"
        self.assertFalse(self.readiness(handoff=handoff)["ready_for_explicit_activation"])

    def test_17_checkpoint_release_drift_blocks(self):
        gate = self.gate(); gate["checkpoint_payload"]["release"]["release_id"] = "other"
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_18_checkpoint_host_drift_blocks(self):
        gate = self.gate(); gate["checkpoint_payload"]["host"]["service_id"] = "srv-other"
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_19_storage_drift_blocks(self):
        gate = self.gate(); gate["checkpoint_payload"]["storage_identity_sha256"] = "1" * 64
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_20_bad_checkpoint_blocks(self):
        gate = self.gate(); gate["activation_checkpoint_sha256"] = "abc"
        self.assertFalse(self.readiness(gate=gate)["ready_for_explicit_activation"])

    def test_21_semantics_are_fail_closed(self):
        self.assertTrue(self.readiness()["semantics"]["fail_closed"])

    def test_22_readiness_is_network_free(self):
        self.assertTrue(self.readiness()["semantics"]["readiness_makes_no_network_requests"])

    def test_23_readiness_does_not_call_sportsbook(self):
        self.assertTrue(self.readiness()["semantics"]["readiness_does_not_call_sportsbook"])

    def test_24_readiness_does_not_run_monte_carlo(self):
        self.assertTrue(self.readiness()["semantics"]["readiness_does_not_run_monte_carlo"])

    def test_25_smoke_plan_has_nine_gets(self):
        plan = s.build_real_staging_smoke_plan(self.url)
        self.assertEqual(9, plan["request_count"])
        self.assertTrue(all(row["method"] == "GET" for row in plan["requests"]))

    def test_26_smoke_plan_never_calls_manual_refresh(self):
        paths = [row["path"] for row in s.build_real_staging_smoke_plan(self.url)["requests"]]
        self.assertNotIn("/api/v1/wnba/rankings/player-props/current/refresh", paths)

    def test_27_smoke_plan_requires_runtime_503(self):
        rows = {row["name"]: row for row in s.build_real_staging_smoke_plan(self.url)["requests"]}
        self.assertEqual([503], rows["runtime_health_pre_activation"]["allowed_statuses"])

    def test_28_remote_documents_green(self):
        self.assertEqual([], self.validate())

    def test_29_remote_revision_mismatch_fails(self):
        docs = self.docs(); docs["step_5u_hosting"]["release"]["revision"] = "1" * 40
        self.assertIn("revision_mismatch", self.validate(docs=docs))

    def test_30_remote_release_id_mismatch_fails(self):
        docs = self.docs(); docs["step_5v_handoff"]["release"]["release_id"] = "other"
        self.assertIn("release_id_mismatch", self.validate(docs=docs))

    def test_31_remote_image_mismatch_fails(self):
        docs = self.docs(); docs["step_5v_handoff"]["publication"]["published_image_ref"] = f"ghcr.io/other/kyre-sports-api@sha256:{'1'*64}"
        self.assertIn("image_ref_mismatch", self.validate(docs=docs))

    def test_32_remote_service_mismatch_fails(self):
        docs = self.docs(); docs["step_5u_hosting"]["host"]["service_name"] = "other"
        self.assertIn("service_name_mismatch", self.validate(docs=docs))

    def test_33_remote_storage_mismatch_fails(self):
        docs = self.docs(); docs["step_5u_hosting"]["storage_identity_sha256"] = "1" * 64
        self.assertIn("storage_identity_mismatch", self.validate(docs=docs))

    def test_34_remote_checkpoint_mismatch_fails(self):
        docs = self.docs(); docs["step_5w_activation_gate"]["activation_checkpoint_sha256"] = "1" * 64
        self.assertIn("activation_checkpoint_mismatch", self.validate(docs=docs))

    def test_35_runtime_health_200_fails_preactivation(self):
        statuses = self.statuses(); statuses["runtime_health_pre_activation"] = 200
        self.assertIn("runtime_health_must_be_503_before_activation", self.validate(statuses=statuses))

    def test_36_timeout_must_be_positive(self):
        with self.assertRaises(s.WNBARealStagingVerificationError):
            s.run_real_staging_smoke(
                self.url,
                expected_revision=self.revision,
                expected_release_id=self.release_id,
                expected_image_ref=self.image,
                expected_service_name=self.service_name,
                expected_storage_identity=self.storage,
                timeout_seconds=0,
            )

    def test_37_full_mock_transport_smoke_passes(self):
        docs = self.docs()
        payloads = {
            "/health": {"status": "ok"},
            "/api/v1/wnba/runtime/deployment": {"deployment_ready": True},
            "/api/v1/wnba/runtime/release": {"release_ready": True},
            "/api/v1/wnba/runtime/hosting": docs["step_5u_hosting"],
            "/api/v1/wnba/runtime/handoff": docs["step_5v_handoff"],
            "/api/v1/wnba/runtime/activation-gate": docs["step_5w_activation_gate"],
            "/api/v1/wnba/runtime/staging-deployment": docs["step_5x_staging_deployment"],
            "/api/v1/wnba/runtime/health": {"detail": "disabled"},
            "/api/v1/wnba/rankings/player-props/current": {"detail": "no current board"},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/wnba/runtime/health":
                return httpx.Response(503, json=payloads[path])
            if path == "/api/v1/wnba/rankings/player-props/current":
                return httpx.Response(409, json=payloads[path])
            return httpx.Response(200, json=payloads[path])

        result = s.run_real_staging_smoke(
            self.url,
            expected_revision=self.revision,
            expected_release_id=self.release_id,
            expected_image_ref=self.image,
            expected_service_name=self.service_name,
            expected_storage_identity=self.storage,
            expected_checkpoint=self.checkpoint,
            transport=httpx.MockTransport(handler),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(9, result["request_count"])


if __name__ == "__main__":
    unittest.main()
