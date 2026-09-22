from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from sports_api import wnba_step15a_live_postgres_preflight as step15a
from sports_api import wnba_step15b_live_adapter_transaction_smoke as step15b
from sports_api import wnba_step15_live_persistence_release_freeze as s15c


_REQUIRED = (
    "WNBA_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED",
    "WNBA_STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED",
    "WNBA_STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED",
    "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "WNBA_STEP14B_DATABASE_READ_ENABLED",
    "WNBA_STEP14B_DATABASE_WRITE_ENABLED",
    "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED",
    "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED",
    "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED",
    "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
    "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
    "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)
_FORBIDDEN = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)


def safe_env() -> dict[str, str]:
    env = {key: "true" for key in _REQUIRED}
    env[s15c.STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV] = "true"
    for key in _FORBIDDEN:
        env[key] = "false"
    return env


class Tests(unittest.TestCase):
    def test_01_default_off(self) -> None:
        self.assertFalse(s15c.DEFAULT_ENABLED)
        self.assertFalse(s15c.step15c_final_live_persistence_freeze_enabled({}))

    def test_02_exact_step15b_parent_sha(self) -> None:
        self.assertEqual(
            s15c.STEP15B_FROZEN_SHA,
            "df509a78a30bc5f05980407cca07bc4a712bae4b",
        )

    def test_03_exact_step15b_smoke_hash(self) -> None:
        self.assertEqual(
            s15c.STEP15B_SMOKE_CONTENT_SHA256,
            "5b000b68c1b1f5acb569dfa788b94aea538b7895eb71c3e0e91ed34b0defcdbf",
        )

    def test_04_exact_step15a_preflight_hash(self) -> None:
        self.assertEqual(
            s15c.STEP15A_PREFLIGHT_CONTENT_SHA256,
            "33a2c431a202b791180d6cca0aa8ad12f46ca6d561749c5753918f90b145223e",
        )
        self.assertEqual(s15c.STEP15A_PREFLIGHT_CONTENT_SHA256, step15b.STEP15A_PREFLIGHT_CONTENT_SHA256)

    def test_05_final_live_evidence_hash_is_exact(self) -> None:
        evidence = s15c.load_step15c_final_live_evidence()
        self.assertEqual(evidence["evidence_content_sha256"], s15c.FINAL_LIVE_EVIDENCE_CONTENT_SHA256)

    def test_06_live_project_is_expected_and_healthy(self) -> None:
        evidence = s15c.validate_step15c_final_live_evidence(s15c.load_step15c_final_live_evidence())
        project = evidence["supabase_project"]
        self.assertEqual(project["ref"], "jqajcdckalsfizbvngiu")
        self.assertEqual(project["status"], "ACTIVE_HEALTHY")
        self.assertEqual(project["region"], "us-west-1")
        self.assertEqual(project["postgres_engine"], "17")

    def test_07_final_tables_present_and_empty(self) -> None:
        live = s15c.load_step15c_final_live_evidence()["live_final_state"]
        self.assertTrue(all(live["tables_present"].values()))
        self.assertEqual(live["row_counts"], {
            "wnba_runtime_checkpoint_heads": 0,
            "wnba_runtime_checkpoints": 0,
            "wnba_runtime_leases": 0,
        })
        self.assertTrue(live["smoke_cleanup_reverified"])

    def test_08_live_migration_is_present(self) -> None:
        live = s15c.load_step15c_final_live_evidence()["live_final_state"]
        self.assertTrue(live["migration_present"])
        self.assertEqual(live["migration_version"], "20260828191445")
        self.assertEqual(live["migration_name"], "wnba_step15a_install_frozen_step14_persistence_schema")

    def test_09_client_roles_still_cannot_use_runtime_schema(self) -> None:
        access = s15c.load_step15c_final_live_evidence()["access_boundary"]
        self.assertFalse(access["anon_schema_usage"])
        self.assertFalse(access["authenticated_schema_usage"])
        self.assertFalse(access["service_role_schema_usage"])
        self.assertTrue(access["postgres_schema_usage"])

    def test_10_no_kyre_runtime_security_advisor_findings(self) -> None:
        access = s15c.load_step15c_final_live_evidence()["access_boundary"]
        self.assertEqual(access["kyre_runtime_security_advisor_finding_count"], 0)

    def test_11_step15b_frozen_sql_fingerprints_still_match(self) -> None:
        self.assertEqual(step15b.validate_frozen_sql_fingerprints(), step15b.SQL_FINGERPRINTS)
        self.assertEqual(len(step15b.SQL_FINGERPRINTS), 7)

    def test_12_out_of_scope_edge_function_is_recorded_not_released(self) -> None:
        scope = s15c.load_step15c_final_live_evidence()["scope_notes"]
        self.assertTrue(scope["unrelated_connector_probe_edge_function_present"])
        self.assertEqual(scope["unrelated_connector_probe_edge_function_slug"], "noop-do-not-deploy")
        self.assertFalse(scope["edge_function_is_part_of_persistence_release"])
        self.assertFalse(scope["edge_function_has_kyre_runtime_access_certified"])

    def test_13_release_manifest_freezes_parent_chain(self) -> None:
        manifest = s15c.build_step15c_release_manifest(env=safe_env())
        self.assertEqual(manifest["release_id"], s15c.RELEASE_ID)
        self.assertEqual(manifest["lineage"]["step15b_frozen_sha"], s15c.STEP15B_FROZEN_SHA)
        self.assertEqual(manifest["lineage"]["step15b_smoke_content_sha256"], s15c.STEP15B_SMOKE_CONTENT_SHA256)
        self.assertEqual(manifest["lineage"]["step15a_preflight_content_sha256"], s15c.STEP15A_PREFLIGHT_CONTENT_SHA256)

    def test_14_release_activation_boundary_remains_off(self) -> None:
        manifest = s15c.build_step15c_release_manifest(env=safe_env())
        activation = manifest["activation_contract"]
        self.assertTrue(activation["step15_release_frozen"])
        for key, value in activation.items():
            if key != "step15_release_frozen":
                self.assertFalse(value, key)
        self.assertTrue(all(value is False for value in manifest["safety_contract"].values()))

    def test_15_release_hash_stable_across_generation_time(self) -> None:
        a = s15c.build_step15c_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T19:35:00+00:00"
        )
        b = s15c.build_step15c_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-29T00:35:00+00:00"
        )
        self.assertNotEqual(a["generated_at_utc"], b["generated_at_utc"])
        self.assertEqual(a["release_content_sha256"], b["release_content_sha256"])

    def test_16_step15c_gate_is_required(self) -> None:
        env = safe_env()
        env.pop(s15c.STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV)
        with self.assertRaises(s15c.WNBAStep15ReleaseFreezeDisabledError):
            s15c.build_step15c_release_manifest(env=env)

    def test_17_every_frozen_parent_gate_is_required(self) -> None:
        for gate in _REQUIRED:
            with self.subTest(gate=gate):
                env = safe_env()
                env[gate] = "false"
                with self.assertRaises(s15c.WNBAStep15ReleaseFreezeDisabledError):
                    s15c.build_step15c_release_manifest(env=env)

    def test_18_unsafe_activation_switches_are_refused(self) -> None:
        for key in _FORBIDDEN:
            with self.subTest(key=key):
                env = safe_env()
                env[key] = "true"
                with self.assertRaises(s15c.WNBAStep15ReleaseFreezeDisabledError):
                    s15c.build_step15c_release_manifest(env=env)

    def test_19_final_live_evidence_tamper_fails_closed(self) -> None:
        evidence = deepcopy(s15c.load_step15c_final_live_evidence())
        evidence["live_final_state"]["row_counts"]["wnba_runtime_leases"] = 1
        with self.assertRaises(s15c.WNBAStep15ReleaseFreezeIntegrityError):
            s15c.validate_step15c_final_live_evidence(evidence)

    def test_20_parent_or_safety_drift_fails_closed(self) -> None:
        with patch.object(s15c, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(s15c.WNBAStep15ReleaseFreezeIntegrityError):
                s15c.build_step15c_release_manifest(env=safe_env())
        drifted = dict(step15b.SQL_FINGERPRINTS)
        drifted["step14b_insert_head"] = "0" * 64
        with patch.object(step15b, "SQL_FINGERPRINTS", drifted):
            with self.assertRaises(step15b.WNBAStep15BLiveSmokeIntegrityError):
                s15c.build_step15c_release_manifest(env=safe_env())


if __name__ == "__main__":
    unittest.main(verbosity=2)
