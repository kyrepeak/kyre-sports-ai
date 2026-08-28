from __future__ import annotations

from unittest.mock import patch
import unittest

from sports_api import wnba_step14_release_freeze as step14d
from sports_api import wnba_step15a_live_postgres_preflight as s15a


_REQUIRED = (
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
    env = {name: "true" for name in _REQUIRED}
    env[s15a.STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED_ENV] = "true"
    for name in _FORBIDDEN:
        env[name] = "false"
    return env


class Tests(unittest.TestCase):
    def test_01_default_off(self) -> None:
        self.assertFalse(s15a.DEFAULT_ENABLED)
        self.assertFalse(s15a.step15a_live_postgres_preflight_enabled({}))

    def test_02_exact_frozen_step14_head(self) -> None:
        self.assertEqual(
            s15a.STEP14D_FROZEN_SHA,
            "d5a7378d94fb1aa51a6bc5fbf5e5c0384f34a9d6",
        )

    def test_03_step14_release_identity_and_hash(self) -> None:
        self.assertEqual(s15a.STEP14_RELEASE_ID, step14d.RELEASE_ID)
        self.assertEqual(
            s15a.STEP14_RELEASE_CONTENT_SHA256,
            "70082ab06a58ddee4dce567626ff83bc64e67bf89f04e5f402d820a414b25e59",
        )

    def test_04_live_evidence_hash(self) -> None:
        evidence = s15a.load_step15a_live_evidence()
        self.assertEqual(
            evidence["evidence_content_sha256"],
            s15a.LIVE_EVIDENCE_CONTENT_SHA256,
        )

    def test_05_project_is_expected_and_healthy(self) -> None:
        evidence = s15a.validate_step15a_live_evidence(s15a.load_step15a_live_evidence())
        project = evidence["supabase_project"]
        self.assertEqual(project["ref"], s15a.EXPECTED_SUPABASE_PROJECT_REF)
        self.assertEqual(project["name"], s15a.EXPECTED_SUPABASE_PROJECT_NAME)
        self.assertEqual(project["region"], "us-west-1")
        self.assertEqual(project["status"], "ACTIVE_HEALTHY")
        self.assertEqual(project["postgres_engine"], "17")

    def test_06_expected_migration_is_applied(self) -> None:
        evidence = s15a.load_step15a_live_evidence()
        migration = evidence["migration"]
        self.assertTrue(migration["applied"])
        self.assertEqual(migration["version"], s15a.EXPECTED_MIGRATION_VERSION)
        self.assertEqual(migration["name"], s15a.EXPECTED_MIGRATION_NAME)

    def test_07_live_tables_match_frozen_shape_counts(self) -> None:
        tables = s15a.load_step15a_live_evidence()["live_schema"]["tables"]
        self.assertEqual(tables["wnba_runtime_checkpoints"]["column_count"], 15)
        self.assertEqual(tables["wnba_runtime_checkpoint_heads"]["column_count"], 5)
        self.assertEqual(tables["wnba_runtime_leases"]["column_count"], 8)
        self.assertEqual(sum(item["constraint_count"] for item in tables.values()), 20)
        self.assertEqual(sum(item["index_count"] for item in tables.values()), 8)

    def test_08_live_tables_are_empty_at_preflight(self) -> None:
        evidence = s15a.load_step15a_live_evidence()
        self.assertTrue(evidence["live_schema"]["all_tables_empty_at_certification"])
        self.assertTrue(
            all(item["row_count"] == 0 for item in evidence["live_schema"]["tables"].values())
        )

    def test_09_required_relational_guards_present(self) -> None:
        live = s15a.load_step15a_live_evidence()["live_schema"]
        self.assertTrue(live["required_foreign_key_present"])
        self.assertTrue(live["required_unique_constraints_present"])
        self.assertTrue(live["required_check_constraints_present"])
        self.assertTrue(live["required_indexes_present"])

    def test_10_client_roles_cannot_use_runtime_schema(self) -> None:
        access = s15a.load_step15a_live_evidence()["access_boundary"]
        self.assertFalse(access["anon_schema_usage"])
        self.assertFalse(access["authenticated_schema_usage"])
        self.assertFalse(access["service_role_schema_usage"])
        self.assertEqual(access["non_postgres_table_grant_count"], 0)

    def test_11_postgres_owns_runtime_schema_access(self) -> None:
        access = s15a.load_step15a_live_evidence()["access_boundary"]
        self.assertTrue(access["postgres_schema_usage"])
        self.assertTrue(access["postgres_schema_create"])
        self.assertEqual(access["schema_acl_explicit_entries"], 0)

    def test_12_no_kyre_runtime_security_advisor_findings(self) -> None:
        access = s15a.load_step15a_live_evidence()["access_boundary"]
        self.assertEqual(access["kyre_runtime_security_advisor_finding_count"], 0)

    def test_13_activation_boundary_is_all_false(self) -> None:
        activation = s15a.load_step15a_live_evidence()["activation_boundary"]
        self.assertTrue(activation)
        self.assertTrue(all(value is False for value in activation.values()))

    def test_14_manifest_certifies_live_schema_but_not_runtime(self) -> None:
        manifest = s15a.build_step15a_live_preflight_manifest(env=safe_env())
        self.assertTrue(manifest["activation_contract"]["live_schema_installed"])
        self.assertFalse(manifest["activation_contract"]["live_scheduler_started"])
        self.assertFalse(manifest["activation_contract"]["production_runtime_enabled"])
        self.assertFalse(manifest["activation_contract"]["global_persistence_runtime_enabled"])

    def test_15_manifest_hash_stable_across_generation_time(self) -> None:
        first = s15a.build_step15a_live_preflight_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T19:20:00+00:00"
        )
        second = s15a.build_step15a_live_preflight_manifest(
            env=safe_env(), generated_at_utc="2026-08-29T01:20:00+00:00"
        )
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["preflight_content_sha256"], second["preflight_content_sha256"])

    def test_16_step15a_gate_is_required(self) -> None:
        env = safe_env()
        env.pop(s15a.STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED_ENV)
        with self.assertRaises(s15a.WNBAStep15ALivePreflightDisabledError):
            s15a.build_step15a_live_preflight_manifest(env=env)

    def test_17_all_frozen_parent_gates_are_required(self) -> None:
        for gate in _REQUIRED:
            with self.subTest(gate=gate):
                env = safe_env()
                env.pop(gate)
                with self.assertRaises(s15a.WNBAStep15ALivePreflightDisabledError):
                    s15a.build_step15a_live_preflight_manifest(env=env)

    def test_18_unsafe_activation_switches_are_refused(self) -> None:
        for key in _FORBIDDEN:
            with self.subTest(key=key):
                env = safe_env()
                env[key] = "true"
                with self.assertRaises(s15a.WNBAStep15ALivePreflightDisabledError):
                    s15a.build_step15a_live_preflight_manifest(env=env)

    def test_19_evidence_tamper_fails_closed(self) -> None:
        evidence = s15a.load_step15a_live_evidence()
        evidence["supabase_project"]["name"] = "tampered"
        with self.assertRaises(s15a.WNBAStep15ALivePreflightIntegrityError):
            s15a.validate_step15a_live_evidence(evidence)

    def test_20_parent_release_or_safety_drift_fails_closed(self) -> None:
        with patch.object(step14d, "RELEASE_ID", "drifted"):
            with self.assertRaises(s15a.WNBAStep15ALivePreflightIntegrityError):
                s15a.build_step15a_live_preflight_manifest(env=safe_env())
        with patch.object(s15a, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(s15a.WNBAStep15ALivePreflightIntegrityError):
                s15a.build_step15a_live_preflight_manifest(env=safe_env())


if __name__ == "__main__":
    unittest.main(verbosity=2)
