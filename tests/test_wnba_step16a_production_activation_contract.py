from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from sports_api import wnba_step16a_production_activation_contract as s16a


def safe_env() -> dict[str, str]:
    return {
        s16a.STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV: "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


class Tests(unittest.TestCase):
    def test_01_default_off(self) -> None:
        self.assertFalse(s16a.DEFAULT_ENABLED)
        self.assertFalse(s16a.step16a_production_activation_contract_enabled({}))

    def test_02_exact_frozen_step15c_parent(self) -> None:
        self.assertEqual(
            s16a.STEP15C_CERTIFIED_SHA,
            "5e24210d7aef90143ba016e368cd49d3ee1a7f19",
        )

    def test_03_step15_release_identity_and_hash(self) -> None:
        self.assertEqual(
            s16a.STEP15_RELEASE_ID,
            "wnba_step15_live_supabase_persistence_2026_regular_season_frozen_v1",
        )
        self.assertEqual(
            s16a.STEP15_RELEASE_CONTENT_SHA256,
            "537df3ec10999071941597e71f4e6361e246db98b17c13a3a31a944f9b8e9a2b",
        )

    def test_04_readiness_evidence_hash_is_frozen(self) -> None:
        evidence = s16a.load_step16a_readiness_evidence()
        self.assertEqual(evidence["evidence_content_sha256"], s16a.EVIDENCE_CONTENT_SHA256)

    def test_05_deployment_file_identities_are_exact(self) -> None:
        evidence = s16a.load_step16a_readiness_evidence()
        self.assertEqual(evidence["deployment_files"], s16a.EXPECTED_DEPLOYMENT_BLOBS)

    def test_06_existing_container_contract_is_preserved(self) -> None:
        observed = s16a.inspect_current_deployment_surface()
        self.assertTrue(observed["container_runtime"])
        self.assertEqual(observed["uvicorn_entrypoint"], "sports_api.main:app")
        self.assertEqual(observed["default_web_concurrency"], 2)
        self.assertEqual(observed["deployment_replica_count"], 1)
        self.assertEqual(observed["hosted_staging_provider"], "render")

    def test_07_persistence_requirement_is_defined(self) -> None:
        observed = s16a.inspect_current_deployment_surface()
        self.assertTrue(observed["persistence_requirement_defined"])
        self.assertEqual(observed["persistence_requirement"], "psycopg[binary]>=3.2,<4")

    def test_08_docker_currently_misses_persistence_dependency(self) -> None:
        observed = s16a.inspect_current_deployment_surface()
        self.assertTrue(observed["docker_installs_base_requirements"])
        self.assertFalse(observed["docker_installs_persistence_requirements"])

    def test_09_production_env_currently_misses_database_url_contract(self) -> None:
        observed = s16a.inspect_current_deployment_surface()
        self.assertFalse(observed["production_env_declares_kyre_database_url"])
        self.assertTrue(observed["production_runtime_default_off"])

    def test_10_fastapi_startup_does_not_yet_bind_step13_to_step15_runtime(self) -> None:
        observed = s16a.inspect_current_deployment_surface()
        self.assertFalse(observed["fastapi_startup_binds_step13_to_step15_runtime"])

    def test_11_exact_three_blockers_are_certified(self) -> None:
        evidence = s16a.validate_step16a_readiness_evidence(
            s16a.load_step16a_readiness_evidence()
        )
        self.assertEqual(tuple(evidence["blocking_requirements"]), s16a.BLOCKING_REQUIREMENTS)
        self.assertEqual(len(s16a.BLOCKING_REQUIREMENTS), 3)

    def test_12_production_activation_is_not_ready(self) -> None:
        evidence = s16a.load_step16a_readiness_evidence()
        self.assertFalse(evidence["readiness_findings"]["production_activation_ready"])
        self.assertFalse(s16a.PRODUCTION_ACTIVATION_ALLOWED)
        self.assertFalse(s16a.PRODUCTION_CANARY_ALLOWED)

    def test_13_step15_live_certifications_are_preserved(self) -> None:
        findings = s16a.load_step16a_readiness_evidence()["readiness_findings"]
        self.assertTrue(findings["live_step15_schema_certified"])
        self.assertTrue(findings["live_step15_transactions_certified"])

    def test_14_activation_boundary_is_all_false(self) -> None:
        activation = s16a.load_step16a_readiness_evidence()["activation_boundary"]
        self.assertTrue(activation)
        self.assertTrue(all(value is False for value in activation.values()))
        self.assertTrue(all(value is False for value in s16a.SAFETY_CONTRACT.values()))

    def test_15_future_canary_prerequisites_are_explicit(self) -> None:
        manifest = s16a.build_step16a_production_activation_contract(env=safe_env())
        required = manifest["required_before_any_future_production_canary"]
        self.assertTrue(required["install_psycopg_in_production_image"])
        self.assertTrue(required["supply_kyre_database_url_via_deployment_secret_manager"])
        self.assertTrue(required["never_commit_database_secret"])
        self.assertTrue(required["require_durable_lease_before_scheduler_execution"])
        self.assertTrue(required["recover_valid_checkpoint_before_first_scheduler_cycle"])

    def test_16_contract_hash_is_stable_across_generation_time(self) -> None:
        first = s16a.build_step16a_production_activation_contract(
            env=safe_env(), generated_at_utc="2026-08-28T19:50:00+00:00"
        )
        second = s16a.build_step16a_production_activation_contract(
            env=safe_env(), generated_at_utc="2026-08-29T01:50:00+00:00"
        )
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["contract_content_sha256"], second["contract_content_sha256"])

    def test_17_step16a_gate_is_required(self) -> None:
        with self.assertRaises(s16a.WNBAStep16AProductionActivationContractDisabledError):
            s16a.build_step16a_production_activation_contract(env={})

    def test_18_unsafe_runtime_switches_are_refused(self) -> None:
        keys = (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        )
        for key in keys:
            with self.subTest(key=key):
                env = safe_env()
                env[key] = "true"
                with self.assertRaises(s16a.WNBAStep16AProductionActivationContractDisabledError):
                    s16a.build_step16a_production_activation_contract(env=env)

    def test_19_evidence_tamper_fails_closed(self) -> None:
        evidence = deepcopy(s16a.load_step16a_readiness_evidence())
        evidence["readiness_findings"]["production_activation_ready"] = True
        with self.assertRaises(s16a.WNBAStep16AProductionActivationContractIntegrityError):
            s16a.validate_step16a_readiness_evidence(evidence)

    def test_20_safety_constant_drift_fails_closed(self) -> None:
        with patch.object(s16a, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(s16a.WNBAStep16AProductionActivationContractIntegrityError):
                s16a.build_step16a_production_activation_contract(env=safe_env())


if __name__ == "__main__":
    unittest.main(verbosity=2)
