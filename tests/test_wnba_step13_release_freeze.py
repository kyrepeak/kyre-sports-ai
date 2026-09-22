from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from sports_api import wnba_step12_release_freeze as step12_release
from sports_api import wnba_step13a_bounded_scheduler as step13a
from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step13_release_freeze as step13d


_REQUIRED_GATES = (
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
    "WNBA_STEP12_SCHEDULER_ENABLED",
)


def safe_env() -> dict[str, str]:
    env = {name: "true" for name in _REQUIRED_GATES}
    env[step13d.STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV] = "true"
    for name in _FORBIDDEN:
        env[name] = "false"
    return env


class Tests(unittest.TestCase):
    def test_default_off(self) -> None:
        self.assertFalse(step13d.DEFAULT_ENABLED)
        self.assertFalse(step13d.step13d_final_scheduler_freeze_enabled({}))

    def test_frozen_parent_chain_is_exact(self) -> None:
        self.assertEqual(step13d.STEP13C_FROZEN_SHA, "23c1a9d4bb977a38048073ce7937b8efd983b998")
        self.assertEqual(step13d.STEP13B_FROZEN_SHA, "0a0e4381d0a4deac6bbd3741f893214e99afef7b")
        self.assertEqual(step13d.STEP13A_FROZEN_SHA, "eaa744ae097a94d5f54c490ab13ca7d66bb725c2")
        self.assertEqual(step13d.STEP12D_FROZEN_SHA, "48517bac86ee3f55aa4c21d6caba06c41a0a7d60")
        self.assertEqual(step13c.STEP13B_FROZEN_SHA, step13d.STEP13B_FROZEN_SHA)
        self.assertEqual(step13c.STEP13A_FROZEN_SHA, step13d.STEP13A_FROZEN_SHA)
        self.assertEqual(step13b.STEP13A_FROZEN_SHA, step13d.STEP13A_FROZEN_SHA)
        self.assertEqual(step13a.STEP12D_FROZEN_SHA, step13d.STEP12D_FROZEN_SHA)

    def test_release_identity_and_certified_simulations(self) -> None:
        manifest = step13d.build_step13d_release_manifest(env=safe_env())
        self.assertEqual(
            manifest["release_id"],
            "wnba_step13_scheduler_refresh_automation_2026_regular_season_frozen_v1",
        )
        self.assertEqual(manifest["season"], 2026)
        self.assertEqual(manifest["season_type"], "Regular Season")
        self.assertEqual(manifest["analytical_contract"]["certified_simulations_per_projection"], 5_000_000)
        self.assertEqual(manifest["analytical_contract"]["certified_batch_size"], 250_000)

    def test_step12_release_identity_and_hash_are_preserved(self) -> None:
        manifest = step12_release.build_step12d_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T00:00:00+00:00"
        )
        self.assertEqual(manifest["release_id"], step13d.STEP12_RELEASE_ID)
        self.assertEqual(manifest["release_content_sha256"], step13d.STEP12_RELEASE_CONTENT_SHA256)
        self.assertEqual(
            step13d.STEP12_RELEASE_CONTENT_SHA256,
            "b557bcf8a8f585df1d91c6e5a178fd0d87ddfd5dd4a543d323b9d16d848d3c46",
        )

    def test_scheduler_contract_freezes_all_step13_capabilities(self) -> None:
        contract = step13d.build_step13d_release_manifest(env=safe_env())["scheduler_contract"]
        self.assertTrue(contract["foreground_bounded_scheduler"])
        self.assertTrue(contract["foreground_runtime_supervisor"])
        self.assertTrue(contract["foreground_reliability_manager"])
        self.assertTrue(contract["frozen_step11e_owns_refresh_cadence"])
        self.assertTrue(contract["slate_rollover_resets_controller_state"])
        self.assertTrue(contract["process_local_duplicate_run_guard"])
        self.assertTrue(contract["bounded_transport_recovery"])
        self.assertEqual(contract["recoverable_error_types"], ["TimeoutError", "ConnectionError"])
        self.assertEqual(contract["max_recovery_attempts"], 5)
        self.assertTrue(contract["integrity_errors_never_retried"])
        self.assertTrue(contract["unknown_exceptions_fail_closed"])

    def test_safety_contract_keeps_unsafe_capabilities_off(self) -> None:
        safety = step13d.build_step13d_release_manifest(env=safe_env())["safety_contract"]
        self.assertTrue(safety)
        self.assertTrue(all(value is False for value in safety.values()))

    def test_process_local_lease_is_certified_but_durable_lease_is_not(self) -> None:
        manifest = step13d.build_step13d_release_manifest(env=safe_env())
        self.assertTrue(manifest["scheduler_contract"]["process_local_duplicate_run_guard"])
        self.assertFalse(manifest["scheduler_contract"]["cross_process_duplicate_run_guard"])
        self.assertFalse(manifest["safety_contract"]["durable_distributed_lease"])
        self.assertFalse(step13c.DURABLE_DISTRIBUTED_LEASE_ALLOWED)
        self.assertTrue(step13c.PROCESS_LOCAL_ACTIVE_RUN_LEASE_ALLOWED)

    def test_release_hash_is_stable_across_generation_time_only(self) -> None:
        first = step13d.build_step13d_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T17:00:00+00:00"
        )
        second = step13d.build_step13d_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-29T01:00:00+00:00"
        )
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["release_content_sha256"], second["release_content_sha256"])
        self.assertEqual(len(first["release_content_sha256"]), 64)

    def test_step13d_certification_gate_is_required(self) -> None:
        env = safe_env()
        env.pop(step13d.STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV)
        with self.assertRaises(step13d.WNBAStep13FinalFreezeDisabledError):
            step13d.build_step13d_release_manifest(env=env)

    def test_all_frozen_step13_and_step12_runtime_gates_are_required(self) -> None:
        for gate in _REQUIRED_GATES:
            with self.subTest(gate=gate):
                env = safe_env()
                env.pop(gate)
                with self.assertRaises(step13d.WNBAStep13FinalFreezeDisabledError):
                    step13d.build_step13d_release_manifest(env=env)

    def test_unsafe_external_activation_switches_are_refused(self) -> None:
        for key in _FORBIDDEN:
            with self.subTest(key=key):
                env = safe_env()
                env[key] = "true"
                with self.assertRaises(step13d.WNBAStep13FinalFreezeDisabledError):
                    step13d.build_step13d_release_manifest(env=env)

    def test_downstream_safety_constant_drift_fails_closed(self) -> None:
        with patch.object(step13c, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(step13d.WNBAStep13FinalFreezeIntegrityError):
                step13d.build_step13d_release_manifest(env=safe_env())
        with patch.object(step13a, "FOREGROUND_BOUNDED_SCHEDULER_ALLOWED", False):
            with self.assertRaises(step13d.WNBAStep13FinalFreezeIntegrityError):
                step13d.build_step13d_release_manifest(env=safe_env())

    def test_manifest_contains_full_frozen_lineage(self) -> None:
        lineage = step13d.build_step13d_release_manifest(env=safe_env())["lineage"]
        expected = {
            "step13a_frozen_sha": step13d.STEP13A_FROZEN_SHA,
            "step13b_frozen_sha": step13d.STEP13B_FROZEN_SHA,
            "step13c_frozen_sha": step13d.STEP13C_FROZEN_SHA,
            "step12d_frozen_sha": step13d.STEP12D_FROZEN_SHA,
            "step12c_frozen_sha": step12_release.STEP12C_FROZEN_SHA,
            "step12b_frozen_sha": step12_release.STEP12B_FROZEN_SHA,
            "step12a_frozen_sha": step12_release.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": step12_release.STEP11E_FROZEN_SHA,
            "step10_frozen_sha": step12_release.STEP10_FROZEN_SHA,
            "step9_frozen_sha": step12_release.STEP9_FROZEN_SHA,
            "step8_frozen_sha": step12_release.STEP8_FROZEN_SHA,
            "step12_release_id": step13d.STEP12_RELEASE_ID,
            "step12_release_content_sha256": step13d.STEP12_RELEASE_CONTENT_SHA256,
        }
        self.assertEqual(lineage, expected)

    def test_phase_boundary_closes_step13_and_reserves_step14(self) -> None:
        phase = step13d.build_step13d_release_manifest(env=safe_env())["phase_boundary"]
        self.assertTrue(phase["step13_complete"])
        self.assertTrue(phase["step14_persistence_not_started"])
        self.assertTrue(phase["durable_distributed_lease_not_started"])
        self.assertTrue(phase["durable_restart_recovery_not_started"])
        self.assertTrue(phase["production_deployment_not_started"])
        self.assertTrue(phase["wagering_not_started"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
