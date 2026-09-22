from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import sports_api.tools.wnba_step6v_supabase_canary as step6v
from sports_api.wnba_step6q_durable_storage import STORAGE_BACKEND_ENV, SUPABASE_BACKEND
from sports_api.wnba_step6r_supabase_storage import SUPABASE_SECRET_KEY_ENV, SUPABASE_URL_ENV


class Step6VSupabaseCanaryTests(unittest.TestCase):
    def base_env(self) -> dict[str, str]:
        return {
            STORAGE_BACKEND_ENV: SUPABASE_BACKEND,
            SUPABASE_URL_ENV: "https://example.supabase.co",
            SUPABASE_SECRET_KEY_ENV: "sb_secret_test_placeholder_abcdefghijklmnopqrstuvwxyz",
            step6v.PRODUCTION_RUNTIME_ENV: "false",
            step6v.DIRECT_SYNC_ENABLED_ENV: "false",
            step6v.RECONCILED_SYNC_ENABLED_ENV: "false",
            step6v.CANARY_ENABLED_ENV: "false",
        }

    def canary_result(self) -> dict:
        return {
            "status": "completed",
            "already_completed": False,
            "storage_backend": SUPABASE_BACKEND,
            "activation_id": "step6v-test-1",
            "offer_side_count": 12,
            "pre_write_sha256": None,
            "post_write_sha256": "a" * 64,
            "verified_persistent_feed_sha256": "b" * 64,
            "snapshot_sha256": "c" * 64,
            "reconciliation_fingerprint_sha256": "d" * 64,
            "attestation_sha256": "e" * 64,
            "rollback_available": True,
        }

    def evidence_result(self) -> dict:
        return {
            "evidence_verified": True,
            "scheduler_authorized": False,
            "evidence_sha256": "f" * 64,
            "canary_identity": {
                "storage_backend": SUPABASE_BACKEND,
                "activation_id": "step6v-test-1",
                "post_write_sha256": "a" * 64,
                "verified_persistent_feed_sha256": "b" * 64,
                "rollback_verified": True,
                "rollback_mode": "delete_new_feed",
                "backup_content_sha256": None,
                "marker_content_sha256": "1" * 64,
                "feed_size_bytes": 1234,
            },
        }

    def test_01_rejects_runtime_enabled(self):
        env = self.base_env()
        env[step6v.PRODUCTION_RUNTIME_ENV] = "true"
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._require_base_fail_closed(env)

    def test_02_rejects_pre_enabled_write_switch(self):
        env = self.base_env()
        env[step6v.DIRECT_SYNC_ENABLED_ENV] = "true"
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._require_base_fail_closed(env)

    def test_03_rejects_non_supabase_backend(self):
        env = self.base_env()
        env[STORAGE_BACKEND_ENV] = "filesystem"
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._require_base_fail_closed(env)

    def test_04_requires_supabase_configuration_ready(self):
        env = self.base_env()
        with patch.object(
            step6v,
            "get_step6r_supabase_storage_status",
            return_value={"configuration_ready": False, "configuration_error": "schema/config not ready"},
        ):
            with self.assertRaises(step6v.WNBAStep6VCanaryError):
                step6v._require_base_fail_closed(env)

    def test_05_active_copy_enables_only_required_canary_switches(self):
        env = self.base_env()
        original = copy.deepcopy(env)
        active = step6v._active_canary_environment(env, "step6v-test-1")
        self.assertEqual(env, original)
        self.assertEqual(active[STORAGE_BACKEND_ENV], SUPABASE_BACKEND)
        self.assertEqual(active[step6v.PRODUCTION_RUNTIME_ENV], "false")
        self.assertEqual(active[step6v.DIRECT_SYNC_ENABLED_ENV], "true")
        self.assertEqual(active[step6v.RECONCILED_SYNC_ENABLED_ENV], "true")
        self.assertEqual(active[step6v.CANARY_ENABLED_ENV], "true")
        self.assertEqual(active[step6v.DIRECT_SYNC_PROVIDER_ENV], step6v.SUPPORTED_DIRECT_PROVIDER)
        self.assertEqual(active[step6v.ACTIVATION_ID_ENV], "step6v-test-1")

    def test_06_verification_copy_forces_all_temporary_switches_off(self):
        env = self.base_env()
        verify = step6v._verification_environment(env)
        self.assertEqual(verify[step6v.PRODUCTION_RUNTIME_ENV], "false")
        self.assertEqual(verify[step6v.DIRECT_SYNC_ENABLED_ENV], "false")
        self.assertEqual(verify[step6v.RECONCILED_SYNC_ENABLED_ENV], "false")
        self.assertEqual(verify[step6v.CANARY_ENABLED_ENV], "false")

    def test_07_successful_operator_is_secret_free_and_does_not_mutate_base(self):
        env = self.base_env()
        original = copy.deepcopy(env)
        with patch.object(step6v, "get_step6r_supabase_storage_status", return_value={"configuration_ready": True}), patch.object(
            step6v, "run_storage_aware_step6j_canary", return_value=self.canary_result()
        ) as canary_mock, patch.object(step6v, "verify_step6t_canary_evidence", return_value=self.evidence_result()) as verify_mock:
            result = step6v.run_step6v_supabase_canary(
                date="2026-08-27",
                season=2026,
                activation_id="step6v-test-1",
                env=env,
            )
        self.assertEqual(env, original)
        self.assertTrue(result["step6j_complete_candidate"])
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["safety"]["scheduler_authorized"])
        self.assertNotIn(env[SUPABASE_SECRET_KEY_ENV], json.dumps(result, sort_keys=True))
        active_env = canary_mock.call_args.kwargs["env"]
        verify_env = verify_mock.call_args.args[0]
        self.assertEqual(active_env[step6v.CANARY_ENABLED_ENV], "true")
        self.assertEqual(verify_env[step6v.CANARY_ENABLED_ENV], "false")

    def test_08_activation_identity_drift_is_rejected(self):
        evidence = self.evidence_result()
        evidence["canary_identity"]["activation_id"] = "step6v-other"
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._assert_evidence_matches(self.canary_result(), evidence, "step6v-test-1")

    def test_09_post_write_hash_drift_is_rejected(self):
        evidence = self.evidence_result()
        evidence["canary_identity"]["post_write_sha256"] = "9" * 64
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._assert_evidence_matches(self.canary_result(), evidence, "step6v-test-1")

    def test_10_canonical_hash_drift_is_rejected(self):
        evidence = self.evidence_result()
        evidence["canary_identity"]["verified_persistent_feed_sha256"] = "9" * 64
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._assert_evidence_matches(self.canary_result(), evidence, "step6v-test-1")

    def test_11_scheduler_authorized_evidence_is_rejected(self):
        evidence = self.evidence_result()
        evidence["scheduler_authorized"] = True
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._assert_evidence_matches(self.canary_result(), evidence, "step6v-test-1")

    def test_12_invalid_date_and_activation_id_fail_closed(self):
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._validated_inputs(date="08/27/2026", season=2026, activation_id="step6v-test-1")
        with self.assertRaises(step6v.WNBAStep6VCanaryError):
            step6v._validated_inputs(date="2026-08-27", season=2026, activation_id="bad id")


if __name__ == "__main__":
    unittest.main()
