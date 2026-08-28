from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step16b_packaging_lifecycle_contract as contract
from sports_api import wnba_step16b_production_lifecycle as lifecycle


class Tests(unittest.TestCase):
    def test_01_default_off(self) -> None:
        self.assertFalse(lifecycle.DEFAULT_ENABLED)
        self.assertFalse(lifecycle.step16b_durable_lifecycle_enabled({}))
        self.assertIsNone(lifecycle.get_step16b_runtime_binding({}))

    def test_02_exact_step16a_parent_identity(self) -> None:
        self.assertEqual(contract.STEP16A_CERTIFIED_SHA, "4ea88aa9a54f5110a03e9e4374219ed15ab30def")
        self.assertEqual(contract.STEP16A_CONTRACT_ID, "wnba_step16a_production_activation_readiness_2026_regular_v1")
        self.assertEqual(contract.STEP16A_CONTRACT_CONTENT_SHA256, "2d8c373dded7eb971d6d6bf6b4a5c9bdfc7bd19de5ddcf1ef83158a0b7d2000e")

    def test_03_evidence_hash_valid(self) -> None:
        evidence = contract.load_step16b_evidence()
        self.assertEqual(evidence["evidence_content_sha256"], contract.EVIDENCE_CONTENT_SHA256)

    def test_04_docker_installs_persistence_requirements(self) -> None:
        text = Path(contract.DOCKERFILE_PATH).read_text(encoding="utf-8")
        self.assertIn("COPY sports_api/requirements-persistence.txt", text)
        self.assertIn("-r /app/sports_api/requirements-persistence.txt", text)

    def test_05_persistence_requirement_is_exact_psycopg3_contract(self) -> None:
        text = Path(contract.PERSISTENCE_REQUIREMENTS_PATH).read_text(encoding="utf-8").strip()
        self.assertEqual(text, "psycopg[binary]>=3.2,<4")

    def test_06_env_declares_secret_manager_key_without_value(self) -> None:
        text = Path(contract.ENV_EXAMPLE_PATH).read_text(encoding="utf-8")
        self.assertIn("Required secret-manager key: KYRE_DATABASE_URL", text)
        self.assertFalse(contract._noncomment_assignment_exists(text, "KYRE_DATABASE_URL"))
        self.assertIn("WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED=false", text)

    def test_07_main_binds_step16b_lifespan(self) -> None:
        text = Path(contract.MAIN_PATH).read_text(encoding="utf-8")
        self.assertIn("from sports_api.wnba_step16b_production_lifecycle import step16b_lifespan", text)
        self.assertIn("lifespan=step16b_lifespan", text)

    def test_08_current_git_blob_shas_match_evidence(self) -> None:
        observed = contract.validate_step16b_packaging_files()
        self.assertEqual(observed, contract.EXPECTED_BLOB_SHAS)

    def test_09_all_step16a_packaging_blockers_closed(self) -> None:
        evidence = contract.validate_step16b_evidence(contract.load_step16b_evidence())
        blockers = evidence["blocker_resolution"]
        self.assertTrue(blockers["all_step16a_packaging_lifecycle_blockers_closed"])
        self.assertTrue(blockers["docker_installs_persistence_requirements"])
        self.assertTrue(blockers["deployment_secret_manager_contract_declares_kyre_database_url"])
        self.assertTrue(blockers["fastapi_lifespan_binds_frozen_step14c_runner"])
        self.assertFalse(blockers["kyre_database_url_value_committed"])

    def test_10_safety_contract_all_false(self) -> None:
        self.assertTrue(contract.SAFETY_CONTRACT)
        self.assertTrue(all(value is False for value in contract.SAFETY_CONTRACT.values()))
        self.assertFalse(lifecycle.PRODUCTION_ACTIVATION_ALLOWED)
        self.assertFalse(lifecycle.PRODUCTION_CANARY_ALLOWED)
        self.assertFalse(lifecycle.DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED)

    def test_11_disabled_lifecycle_status_never_connects_or_executes(self) -> None:
        status = lifecycle.build_step16b_lifecycle_status({})
        self.assertFalse(status["enabled"])
        self.assertFalse(status["database_connected"])
        self.assertFalse(status["runtime_runner_bound"])
        self.assertFalse(status["runtime_executed"])
        self.assertFalse(status["background_task_started"])
        self.assertFalse(status["production_activation"])

    def test_12_enablement_requires_database_secret(self) -> None:
        env = {lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true"}
        with patch.object(lifecycle, "persistence_driver_available", return_value=True):
            with self.assertRaises(lifecycle.WNBAStep16BLifecycleDisabledError):
                lifecycle.validate_step16b_enablement(env)

    def test_13_non_postgres_database_url_is_rejected(self) -> None:
        env = {
            lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true",
            lifecycle.DATABASE_URL_ENV: "https://example.invalid/database",
        }
        with patch.object(lifecycle, "persistence_driver_available", return_value=True):
            with self.assertRaises(lifecycle.WNBAStep16BLifecycleIntegrityError):
                lifecycle.validate_step16b_enablement(env)

    def test_14_unsafe_activation_switches_are_rejected(self) -> None:
        base = {
            lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true",
            lifecycle.DATABASE_URL_ENV: "postgresql://user:secret@db.example.invalid:5432/kyre",
        }
        for key in lifecycle._FORBIDDEN_TRUE_ENV_KEYS:
            with self.subTest(key=key):
                env = dict(base)
                env[key] = "true"
                with patch.object(lifecycle, "persistence_driver_available", return_value=True):
                    with self.assertRaises(lifecycle.WNBAStep16BLifecycleDisabledError):
                        lifecycle.validate_step16b_enablement(env)

    def test_15_enabled_binding_returns_exact_frozen_step14c_runner(self) -> None:
        env = {
            lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true",
            lifecycle.DATABASE_URL_ENV: "postgresql://user:secret@db.example.invalid:5432/kyre",
        }
        with patch.object(lifecycle, "persistence_driver_available", return_value=True):
            runner = lifecycle.get_step16b_runtime_binding(env)
        self.assertIs(runner, step14c.run_step14c_durable_restart_lease)

    def test_16_disabled_lifespan_start_and_shutdown_are_inert(self) -> None:
        async def exercise() -> None:
            app = SimpleNamespace(state=SimpleNamespace())
            with patch.dict(os.environ, {}, clear=True):
                async with lifecycle.step16b_lifespan(app):
                    self.assertEqual(app.state.wnba_step16b_lifecycle["status"], "disabled_default_off")
                    self.assertIsNone(app.state.wnba_step16b_runtime_runner)
                    self.assertFalse(app.state.wnba_step16b_lifecycle["database_connected"])
                self.assertEqual(app.state.wnba_step16b_lifecycle["status"], "shutdown_disabled")
                self.assertIsNone(app.state.wnba_step16b_runtime_runner)
        asyncio.run(exercise())

    def test_17_enabled_lifespan_binds_but_never_runs_or_connects(self) -> None:
        async def exercise() -> None:
            app = SimpleNamespace(state=SimpleNamespace())
            env = {
                lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV: "true",
                lifecycle.DATABASE_URL_ENV: "postgresql://user:secret@db.example.invalid:5432/kyre",
            }
            with patch.dict(os.environ, env, clear=True), patch.object(
                lifecycle, "persistence_driver_available", return_value=True
            ):
                async with lifecycle.step16b_lifespan(app):
                    status = app.state.wnba_step16b_lifecycle
                    self.assertEqual(status["status"], "bound_not_executed")
                    self.assertIs(app.state.wnba_step16b_runtime_runner, step14c.run_step14c_durable_restart_lease)
                    self.assertFalse(status["database_connected"])
                    self.assertFalse(status["runtime_executed"])
                    self.assertFalse(status["background_task_started"])
                    self.assertNotIn("secret", str(status))
                self.assertEqual(app.state.wnba_step16b_lifecycle["status"], "shutdown_bound_never_executed")
                self.assertIsNone(app.state.wnba_step16b_runtime_runner)
        asyncio.run(exercise())

    def test_18_contract_hash_stable_across_generation_time(self) -> None:
        first = contract.build_step16b_contract_manifest(generated_at_utc="2026-08-28T20:00:00+00:00")
        second = contract.build_step16b_contract_manifest(generated_at_utc="2026-08-29T02:00:00+00:00")
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["contract_content_sha256"], second["contract_content_sha256"])

    def test_19_phase_requires_step16c_before_production_ready(self) -> None:
        manifest = contract.build_step16b_contract_manifest(generated_at_utc="2026-08-28T20:00:00+00:00")
        self.assertFalse(manifest["runtime_contract"]["production_activation_ready"])
        self.assertTrue(manifest["runtime_contract"]["step16c_live_canary_required"])
        self.assertTrue(manifest["phase_boundary"]["step16c_live_canary_not_started"])
        self.assertTrue(manifest["phase_boundary"]["controlled_production_activation_not_authorized"])

    def test_20_tamper_or_safety_drift_fails_closed(self) -> None:
        evidence = contract.load_step16b_evidence()
        evidence["blocker_resolution"]["docker_installs_persistence_requirements"] = False
        with self.assertRaises(contract.WNBAStep16BContractIntegrityError):
            contract.validate_step16b_evidence(evidence)
        with patch.object(lifecycle, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(contract.WNBAStep16BContractIntegrityError):
                contract.assert_step16b_integrity()


if __name__ == "__main__":
    unittest.main(verbosity=2)
