from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from sports_api import wnba_step16_release_freeze as s16
from sports_api import wnba_step16d_controlled_production_activation as s16d


def safe_env():
    return {
        "WNBA_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str).encode()).hexdigest()


class Tests(unittest.TestCase):
    def test_01_default_off(self):
        self.assertFalse(s16.step16e_freeze_enabled({}))
        self.assertFalse(s16.DEFAULT_ENABLED)

    def test_02_exact_step16d_parent(self):
        self.assertEqual(s16.STEP16D_CERTIFIED_SHA, "b13307e6a89a456edfd0fc4f4ddbb5244ae91a60")
        self.assertEqual(s16d.CONTRACT_ID, s16.STEP16D_CONTRACT_ID)

    def test_03_final_release_identity(self):
        self.assertEqual(s16.RELEASE_ID, "wnba_step16_controlled_production_activation_2026_regular_season_frozen_v1")
        self.assertEqual(s16.SCHEMA_VERSION, "wnba_step_16e_final_production_freeze_v1")

    def test_04_final_evidence_hash_is_exact(self):
        evidence = s16.load_step16e_final_evidence()
        surface = deepcopy(evidence)
        surface.pop("observed_at_utc", None)
        surface.pop("evidence_content_sha256", None)
        self.assertEqual(canonical(surface), s16.FINAL_EVIDENCE_CONTENT_SHA256)

    def test_05_supabase_project_is_expected_and_healthy(self):
        e = s16.validate_step16e_final_evidence(s16.load_step16e_final_evidence())
        self.assertEqual(e["supabase_project"]["ref"], "jqajcdckalsfizbvngiu")
        self.assertEqual(e["supabase_project"]["status"], "ACTIVE_HEALTHY")
        self.assertEqual(e["supabase_project"]["postgres_engine"], "17")

    def test_06_final_live_tables_are_zero_residue(self):
        live = s16.load_step16e_final_evidence()["final_live_state"]
        self.assertEqual((live["checkpoint_rows"], live["checkpoint_head_rows"], live["lease_rows"]), (0, 0, 0))

    def test_07_runtime_tables_and_postgres_access_remain_present(self):
        live = s16.load_step16e_final_evidence()["final_live_state"]
        for key in ("checkpoints_present", "heads_present", "leases_present", "postgres_schema_usage"):
            self.assertTrue(live[key])

    def test_08_client_roles_still_cannot_use_runtime_schema(self):
        live = s16.load_step16e_final_evidence()["final_live_state"]
        for key in ("anon_schema_usage", "authenticated_schema_usage", "service_role_schema_usage"):
            self.assertFalse(live[key])

    def test_09_migration_and_security_boundary_are_frozen(self):
        live = s16.load_step16e_final_evidence()["final_live_state"]
        self.assertEqual(live["migration_version"], s16.EXPECTED_MIGRATION_VERSION)
        self.assertEqual(live["migration_name"], s16.EXPECTED_MIGRATION_NAME)
        self.assertEqual(live["kyre_runtime_security_advisor_findings"], 0)

    def test_10_step16d_direct_psycopg_is_certified(self):
        parent = s16.load_step16e_final_evidence()["step16d_certification"]
        self.assertTrue(parent["direct_psycopg_live_connection_certified"])
        self.assertTrue(parent["production_docker_image_execution_certified"])

    def test_11_step16d_two_cycle_restart_is_certified(self):
        parent = s16.load_step16e_final_evidence()["step16d_certification"]
        self.assertTrue(parent["two_cycle_durable_restart_certified"])
        self.assertTrue(parent["canary_cleanup_zero_residue_certified"])

    def test_12_step16d_artifact_and_live_hash_are_exact(self):
        parent = s16.load_step16e_final_evidence()["step16d_certification"]
        self.assertEqual(parent["contract_content_sha256"], s16.STEP16D_CONTRACT_CONTENT_SHA256)
        self.assertEqual(parent["live_result_content_sha256"], s16.STEP16D_LIVE_RESULT_CONTENT_SHA256)
        self.assertEqual(parent["artifact_digest_sha256"], s16.STEP16D_ARTIFACT_DIGEST_SHA256)

    def test_13_out_of_release_edge_function_is_disclosed_not_certified(self):
        cleanup = s16.load_step16e_final_evidence()["out_of_release_cleanup"]
        self.assertEqual(cleanup["slug"], "noop-do-not-deploy")
        self.assertTrue(cleanup["verify_jwt"])
        self.assertTrue(cleanup["excluded_from_step16_release"])
        self.assertTrue(cleanup["cleanup_pending"])
        self.assertFalse(cleanup["persistence_access_certified"])

    def test_14_release_safety_contract_is_all_false(self):
        self.assertTrue(s16.SAFETY_CONTRACT)
        self.assertTrue(all(value is False for value in s16.SAFETY_CONTRACT.values()))

    def test_15_manifest_freezes_full_step16_lineage(self):
        manifest = s16.build_step16_release_manifest(env=safe_env(), generated_at_utc="2026-08-28T21:00:00+00:00")
        lineage = manifest["lineage"]
        self.assertEqual(lineage["step16d_certified_sha"], s16.STEP16D_CERTIFIED_SHA)
        self.assertEqual(lineage["step16c_certified_sha"], s16.STEP16C_CERTIFIED_SHA)
        self.assertEqual(lineage["step16b_certified_sha"], s16.STEP16B_CERTIFIED_SHA)
        self.assertEqual(lineage["step16a_certified_sha"], s16.STEP16A_CERTIFIED_SHA)
        self.assertEqual(lineage["step15c_certified_sha"], s16.STEP15C_CERTIFIED_SHA)

    def test_16_manifest_certifies_controlled_activation_not_continuous_host(self):
        manifest = s16.validate_step16_release_manifest(s16.build_step16_release_manifest(env=safe_env()))
        self.assertTrue(manifest["certification"]["controlled_production_activation"])
        self.assertTrue(manifest["certification"]["direct_psycopg_live_connection"])
        self.assertFalse(manifest["scope_boundary"]["continuous_production_runtime_started"])
        self.assertFalse(manifest["scope_boundary"]["render_hosted_service_activation_certified"])
        self.assertTrue(manifest["phase_boundary"]["continuous_hosted_runtime_intentionally_not_activated"])

    def test_17_release_hash_is_stable_across_generation_time(self):
        a = s16.build_step16_release_manifest(env=safe_env(), generated_at_utc="2026-08-28T21:00:00+00:00")
        b = s16.build_step16_release_manifest(env=safe_env(), generated_at_utc="2026-08-29T01:00:00+00:00")
        self.assertNotEqual(a["generated_at_utc"], b["generated_at_utc"])
        self.assertEqual(a["release_content_sha256"], b["release_content_sha256"])

    def test_18_step16e_gate_is_required(self):
        env = safe_env(); env["WNBA_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED"] = "false"
        with self.assertRaises(s16.WNBAStep16ReleaseDisabledError):
            s16.build_step16_release_manifest(env=env)

    def test_19_unsafe_runtime_switches_are_refused(self):
        for key in ("WNBA_PRODUCTION_RUNTIME_ENABLED", "WNBA_BOARD_SCHEDULER_ENABLED", "WNBA_PERSISTENCE_ENABLED", "WNBA_SUPABASE_WRITE_ENABLED", "WNBA_WAGERING_ENABLED", "WNBA_STEP12_SCHEDULER_ENABLED"):
            env = safe_env(); env[key] = "true"
            with self.assertRaises(s16.WNBAStep16ReleaseDisabledError):
                s16.build_step16_release_manifest(env=env)

    def test_20_evidence_or_safety_tamper_fails_closed(self):
        evidence = s16.load_step16e_final_evidence()
        tampered = deepcopy(evidence); tampered["final_live_state"]["lease_rows"] = 1
        with self.assertRaises(s16.WNBAStep16ReleaseIntegrityError):
            s16.validate_step16e_final_evidence(tampered)
        with patch.object(s16, "DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED", False):
            with self.assertRaises(s16.WNBAStep16ReleaseIntegrityError):
                s16.build_step16_release_manifest(env=safe_env())


if __name__ == "__main__":
    unittest.main()
