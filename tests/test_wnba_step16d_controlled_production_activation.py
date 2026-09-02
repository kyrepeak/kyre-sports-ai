from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step16d_controlled_production_activation as s16d


FAKE_SHA = "1" * 40
FAKE_DSN = "postgresql://user:secret@db.example.invalid:5432/postgres"


def fake_env():
    return {
        s16d.STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED_ENV: "true",
        s16d.DATABASE_URL_ENV: FAKE_DSN,
        s16d.EXPECTED_REVISION_ENV: FAKE_SHA,
        "WNBA_RELEASE_BUILD_REVISION": FAKE_SHA,
        "WNBA_DEPLOYMENT_MODE": "container",
    }


def sample_result():
    result = {
        "data_type": "wnba_step16d_controlled_production_activation_result",
        "schema_version": s16d.SCHEMA_VERSION,
        "integration_version": s16d.INTEGRATION_VERSION,
        "contract_id": s16d.CONTRACT_ID,
        "status": "completed",
        "lineage": {
            "step16c_certified_sha": s16d.STEP16C_CERTIFIED_SHA,
            "step16c_contract_id": s16d.STEP16C_CONTRACT_ID,
            "step16c_manifest_content_sha256": s16d.STEP16C_MANIFEST_CONTENT_SHA256,
            "step16c_live_evidence_content_sha256": s16d.STEP16C_LIVE_EVIDENCE_CONTENT_SHA256,
            "step16b_certified_sha": s16d.STEP16B_CERTIFIED_SHA,
            "step15c_certified_sha": s16d.STEP15C_CERTIFIED_SHA,
        },
        "activation": {
            "production_docker_image": True,
            "direct_psycopg_live_connection": True,
            "protected_database_secret_used": True,
            "credential_value_exposed_false": True,
            "database_secret_scheme": "postgresql",
            "container_build_revision": FAKE_SHA,
            "expected_revision": FAKE_SHA,
            "exact_step16b_bound_runner": True,
            "controlled_one_shot_activation": True,
            "slate_date": s16d.EXPECTED_CANARY_SLATE_DATE,
            "checkpoint_key": s16d.EXPECTED_CHECKPOINT_KEY,
            "lease_key": s16d.EXPECTED_LEASE_KEY,
            "database_role": "postgres",
            "postgres_version": "17.6",
            "database_name": "postgres",
            "baseline_checkpoint_rows": 0,
            "baseline_checkpoint_head_rows": 0,
            "baseline_lease_rows": 0,
        },
        "cycles": {
            "cycle_1_status": "completed",
            "cycle_1_recovered_from_checkpoint": False,
            "cycle_1_loaded_checkpoint_version": None,
            "cycle_1_saved_checkpoint_version": 1,
            "cycle_1_lease_fencing_generation": 1,
            "cycle_2_status": "completed",
            "cycle_2_recovered_from_checkpoint": True,
            "cycle_2_loaded_checkpoint_version": 1,
            "cycle_2_saved_checkpoint_version": 2,
            "cycle_2_lease_fencing_generation": 1,
            "cycle_2_injected_previous_cycle_index": 1,
            "checkpoint_rows_after_two_cycles": 2,
            "checkpoint_head_rows_after_two_cycles": 1,
            "lease_rows_after_two_cycles": 0,
        },
        "cleanup": {
            "checkpoint_rows": 0,
            "checkpoint_head_rows": 0,
            "lease_rows": 0,
            "canary_residue_zero": True,
        },
        "safety": {
            "continuous_production_runtime_started": False,
            "global_persistence_autostart_started": False,
            "automatic_restart_autostart_started": False,
            "background_daemon_started": False,
            "background_thread_started": False,
            "background_task_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_enabled": False,
            "wagering_enabled": False,
            "authentication_enabled": False,
            "cookies_enabled": False,
            "basketball_model_mutated": False,
            "ranking_mutated": False,
            "credential_value_exposed": False,
        },
        "phase_boundary": {
            "step16d_controlled_activation_complete": True,
            "step16e_final_production_freeze_ready": True,
            "continuous_production_runtime_not_started": True,
            "render_hosted_service_activation_not_certified": True,
        },
        "observed_at_utc": "2026-08-28T20:30:00+00:00",
    }
    result["result_content_sha256"] = s16d._canonical_hash(s16d._result_hash_surface(result))
    return result


class Tests(unittest.TestCase):
    def test_01_default_off(self):
        self.assertFalse(s16d.DEFAULT_ENABLED)
        self.assertFalse(s16d.step16d_enabled({}))

    def test_02_exact_step16c_parent(self):
        self.assertEqual(s16d.STEP16C_CERTIFIED_SHA, "1de22beb83cad2f0c3bae3bc6ab845b5f3d2a4e3")
        self.assertEqual(s16d.STEP16C_MANIFEST_CONTENT_SHA256, "1efa8f82298297cc32f8c826d16332f9dddfee2e9c501422f5706704a98bf51b")

    def test_03_controlled_activation_capabilities(self):
        self.assertTrue(s16d.CONTROLLED_ONE_SHOT_PRODUCTION_ACTIVATION_ALLOWED)
        self.assertTrue(s16d.PRODUCTION_DOCKER_IMAGE_EXECUTION_REQUIRED)
        self.assertTrue(s16d.DIRECT_PSYCOG_LIVE_CONNECTION_REQUIRED)
        self.assertTrue(s16d.TWO_CYCLE_RESTART_RECOVERY_REQUIRED)

    def test_04_continuous_runtime_stays_off(self):
        self.assertFalse(s16d.CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED)
        self.assertFalse(s16d.GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED)
        self.assertFalse(s16d.AUTOMATIC_RESTART_AUTOSTART_ALLOWED)
        self.assertFalse(s16d.BACKGROUND_TASK_ALLOWED)

    def test_05_database_secret_required(self):
        env = fake_env()
        del env[s16d.DATABASE_URL_ENV]
        with self.assertRaises(s16d.WNBAStep16DDisabledError):
            s16d.validate_activation_prerequisites(env)

    def test_06_non_postgres_database_url_rejected(self):
        env = fake_env()
        env[s16d.DATABASE_URL_ENV] = "https://example.invalid/db"
        with self.assertRaises(s16d.WNBAStep16DIntegrityError):
            s16d.validate_activation_prerequisites(env)

    def test_07_container_execution_required(self):
        env = fake_env()
        env["WNBA_DEPLOYMENT_MODE"] = "local"
        with self.assertRaises(s16d.WNBAStep16DDisabledError):
            s16d.validate_activation_prerequisites(env)

    def test_08_exact_container_revision_required(self):
        env = fake_env()
        env["WNBA_RELEASE_BUILD_REVISION"] = "2" * 40
        with self.assertRaises(s16d.WNBAStep16DIntegrityError):
            s16d.validate_activation_prerequisites(env)

    def test_09_activation_env_enables_only_frozen_required_gates(self):
        env = s16d.build_activation_env(fake_env())
        for key in s16d._REQUIRED_TRUE_GATES:
            self.assertEqual(env[key], "true")
        for key in s16d._FORBIDDEN_TRUE_GATES:
            self.assertEqual(env[key], "false")

    def test_10_bound_runner_is_exact_step14c(self):
        with patch.object(s16d.step16b, "persistence_driver_available", return_value=True):
            pre = s16d.validate_activation_prerequisites(fake_env())
        self.assertIs(pre["bound_runner"], step14c.run_step14c_durable_restart_lease)

    def test_11_canary_slate_is_isolated(self):
        self.assertEqual(s16d.EXPECTED_CANARY_SLATE_DATE, "2026-01-17")
        self.assertEqual(s16d.EXPECTED_CHECKPOINT_KEY, "wnba:runtime:2026:regular-season:2026-01-17")
        self.assertTrue(s16d.EXPECTED_LEASE_KEY.endswith(":scheduler-lease"))

    def test_12_canary_request_is_frozen_step13c_shape(self):
        request = s16d.build_canary_request()
        self.assertEqual(request["data_type"], "wnba_step13c_reliability_recovery_request")
        self.assertEqual(request["supervisor_request"]["initial_slate_date"], s16d.EXPECTED_CANARY_SLATE_DATE)

    def test_13_controlled_response_hash_is_valid(self):
        response = s16d.build_controlled_step13c_response(cycle_index=1)
        surface = {k: deepcopy(v) for k, v in response.items() if k not in {"generated_at_utc", "reliability_content_sha256"}}
        self.assertEqual(response["reliability_content_sha256"], s16d._canonical_hash(surface))
        self.assertEqual(response["status"], "completed")

    def test_14_live_result_validates(self):
        validated = s16d.validate_live_activation_result(sample_result())
        self.assertEqual(validated["cycles"]["cycle_2_saved_checkpoint_version"], 2)

    def test_15_live_result_requires_direct_psycopg(self):
        result = sample_result()
        result["activation"]["direct_psycopg_live_connection"] = False
        result["result_content_sha256"] = s16d._canonical_hash(s16d._result_hash_surface(result))
        with self.assertRaises(s16d.WNBAStep16DIntegrityError):
            s16d.validate_live_activation_result(result)

    def test_16_live_result_requires_restart_recovery(self):
        result = sample_result()
        result["cycles"]["cycle_2_recovered_from_checkpoint"] = False
        result["result_content_sha256"] = s16d._canonical_hash(s16d._result_hash_surface(result))
        with self.assertRaises(s16d.WNBAStep16DIntegrityError):
            s16d.validate_live_activation_result(result)

    def test_17_live_result_requires_zero_residue(self):
        result = sample_result()
        result["cleanup"]["checkpoint_rows"] = 1
        result["cleanup"]["canary_residue_zero"] = False
        result["result_content_sha256"] = s16d._canonical_hash(s16d._result_hash_surface(result))
        with self.assertRaises(s16d.WNBAStep16DIntegrityError):
            s16d.validate_live_activation_result(result)

    def test_18_secret_never_appears_in_result_contract(self):
        result = sample_result()
        self.assertNotIn(FAKE_DSN, str(result))
        self.assertFalse(result["safety"]["credential_value_exposed"])

    def test_19_contract_hash_stable_across_generation_time(self):
        first = s16d.build_contract_manifest(generated_at_utc="2026-08-28T20:00:00+00:00")
        second = s16d.build_contract_manifest(generated_at_utc="2026-08-29T20:00:00+00:00")
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["contract_content_sha256"], second["contract_content_sha256"])
        self.assertTrue(first["phase_boundary"]["step16e_final_freeze_required"])

    def test_20_tamper_fails_closed(self):
        result = sample_result()
        result["cycles"]["cycle_2_saved_checkpoint_version"] = 99
        with self.assertRaises(s16d.WNBAStep16DIntegrityError):
            s16d.validate_live_activation_result(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
