from __future__ import annotations

import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from sports_api import wnba_step13_release_freeze as step13_release
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14b_database_checkpoint_adapter as step14b
from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step14_release_freeze as step14d


_REQUIRED_GATES = (
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
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)


def safe_env() -> dict[str, str]:
    env = {name: "true" for name in _REQUIRED_GATES}
    env[step14d.STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED_ENV] = "true"
    for name in _FORBIDDEN:
        env[name] = "false"
    return env


class Tests(unittest.TestCase):
    def test_01_default_off(self) -> None:
        self.assertFalse(step14d.DEFAULT_ENABLED)
        self.assertFalse(step14d.step14d_final_persistence_freeze_enabled({}))

    def test_02_exact_step14_parent_chain(self) -> None:
        self.assertEqual(step14d.STEP14A_FROZEN_SHA, "aa1d770cd9840dac7e31139ab177fa4aa3ac9020")
        self.assertEqual(step14d.STEP14B_FROZEN_SHA, "dfea123c0702331ecccf3ca285baf1d69b8f3c2e")
        self.assertEqual(step14d.STEP14C_FROZEN_SHA, "e2ff1f8c3729b1dd80189501cd64ddd7393cf077")
        self.assertEqual(step14b.STEP14A_FROZEN_SHA, step14d.STEP14A_FROZEN_SHA)
        self.assertEqual(step14c.STEP14B_FROZEN_SHA, step14d.STEP14B_FROZEN_SHA)

    def test_03_release_identity(self) -> None:
        manifest = step14d.build_step14d_release_manifest(env=safe_env())
        self.assertEqual(
            manifest["release_id"],
            "wnba_step14_durable_persistence_restart_lease_2026_regular_season_frozen_v1",
        )
        self.assertEqual(manifest["season"], 2026)
        self.assertEqual(manifest["season_type"], "Regular Season")
        self.assertEqual(manifest["branch"], "wnba-step14d-final-persistence-freeze-20260828")

    def test_04_step13_release_is_preserved(self) -> None:
        parent = step13_release.build_step13d_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T00:00:00+00:00"
        )
        self.assertEqual(parent["release_id"], step14d.STEP13_RELEASE_ID)
        self.assertEqual(parent["release_content_sha256"], step14d.STEP13_RELEASE_CONTENT_SHA256)
        self.assertEqual(
            step14d.STEP13_RELEASE_CONTENT_SHA256,
            "7857651813d8114de58d21163fdb8f3eceb695a43834c3eb48b55bb5c01c9046",
        )

    def test_05_step14a_manifest_and_sql_hash_are_frozen(self) -> None:
        manifest = step14a.build_step14a_schema_manifest(env=safe_env())
        self.assertEqual(
            manifest["manifest_content_sha256"], step14d.STEP14A_MANIFEST_CONTENT_SHA256
        )
        observed = hashlib.sha256(Path(step14a.SQL_SCHEMA_PATH).read_bytes()).hexdigest()
        self.assertEqual(observed, step14d.STEP14A_SQL_SCHEMA_SHA256)
        self.assertEqual(
            observed,
            "308042f8196607a477158d348ba6e03e090267910cba749491534131b490a2eb",
        )

    def test_06_step14c_lease_sql_hash_is_frozen(self) -> None:
        observed = hashlib.sha256(Path(step14c.LEASE_SQL_SCHEMA_PATH).read_bytes()).hexdigest()
        self.assertEqual(observed, step14d.STEP14C_LEASE_SQL_SCHEMA_SHA256)
        self.assertEqual(
            observed,
            "49376bd4de581606819dc70ace6d462aadb77e641b0344bcde61c69f5a03b5bb",
        )

    def test_07_checkpoint_adapter_contract_is_certified(self) -> None:
        persistence = step14d.build_step14d_release_manifest(env=safe_env())["persistence_contract"]
        self.assertTrue(persistence["postgresql_checkpoint_adapter"])
        self.assertTrue(persistence["append_only_checkpoint_history"])
        self.assertTrue(persistence["checkpoint_head_compare_and_swap"])
        self.assertTrue(persistence["deterministic_checkpoint_identity"])
        self.assertTrue(step14b.POSTGRESQL_DATABASE_READ_ALLOWED)
        self.assertTrue(step14b.POSTGRESQL_DATABASE_WRITE_ALLOWED)
        self.assertTrue(step14b.ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED)
        self.assertTrue(step14b.APPEND_ONLY_HISTORY_REQUIRED)

    def test_08_restart_recovery_contract_is_certified(self) -> None:
        persistence = step14d.build_step14d_release_manifest(env=safe_env())["persistence_contract"]
        self.assertTrue(persistence["exact_controller_state_restart_handoff"])
        self.assertTrue(persistence["durable_restart_recovery"])
        self.assertTrue(persistence["checkpoint_persist_after_success"])
        self.assertTrue(step14c.DURABLE_RESTART_RECOVERY_ALLOWED)
        self.assertTrue(step14c.CHECKPOINT_PERSIST_AFTER_SUCCESS_ALLOWED)

    def test_09_lease_fencing_contract_is_certified(self) -> None:
        persistence = step14d.build_step14d_release_manifest(env=safe_env())["persistence_contract"]
        self.assertTrue(persistence["cross_process_duplicate_run_guard"])
        self.assertTrue(persistence["durable_distributed_lease"])
        self.assertTrue(persistence["uuid_lease_token"])
        self.assertTrue(persistence["monotonic_fencing_generation"])
        self.assertTrue(persistence["lease_expiry_and_takeover"])
        self.assertTrue(persistence["stale_owner_blocked_from_renew_release_or_persist"])
        self.assertTrue(persistence["lease_revalidated_before_checkpoint_persist"])

    def test_10_safety_contract_keeps_unsafe_capabilities_off(self) -> None:
        safety = step14d.build_step14d_release_manifest(env=safe_env())["safety_contract"]
        self.assertTrue(safety)
        self.assertTrue(all(value is False for value in safety.values()))

    def test_11_activation_remains_explicit_foreground_and_nonproduction(self) -> None:
        activation = step14d.build_step14d_release_manifest(env=safe_env())["activation_contract"]
        self.assertTrue(activation["explicit_foreground_invocation_required"])
        self.assertTrue(activation["foreground_only"])
        self.assertFalse(activation["global_persistence_runtime_enabled"])
        self.assertFalse(activation["automatic_production_restart_activation"])
        self.assertFalse(activation["background_lease_renewal_thread"])
        self.assertFalse(activation["production_runtime_enabled"])

    def test_12_release_hash_is_stable_across_generation_time_only(self) -> None:
        first = step14d.build_step14d_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T18:55:00+00:00"
        )
        second = step14d.build_step14d_release_manifest(
            env=safe_env(), generated_at_utc="2026-08-29T03:00:00+00:00"
        )
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["release_content_sha256"], second["release_content_sha256"])
        self.assertEqual(len(first["release_content_sha256"]), 64)

    def test_13_step14d_gate_is_required(self) -> None:
        env = safe_env()
        env.pop(step14d.STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED_ENV)
        with self.assertRaises(step14d.WNBAStep14FinalFreezeDisabledError):
            step14d.build_step14d_release_manifest(env=env)

    def test_14_every_frozen_parent_gate_is_required(self) -> None:
        for gate in _REQUIRED_GATES:
            with self.subTest(gate=gate):
                env = safe_env()
                env.pop(gate)
                with self.assertRaises(step14d.WNBAStep14FinalFreezeDisabledError):
                    step14d.build_step14d_release_manifest(env=env)

    def test_15_unsafe_external_activation_switches_are_refused(self) -> None:
        for key in _FORBIDDEN:
            with self.subTest(key=key):
                env = safe_env()
                env[key] = "true"
                with self.assertRaises(step14d.WNBAStep14FinalFreezeDisabledError):
                    step14d.build_step14d_release_manifest(env=env)

    def test_16_parent_capability_drift_fails_closed(self) -> None:
        with patch.object(step14c, "DURABLE_RESTART_RECOVERY_ALLOWED", False):
            with self.assertRaises(step14d.WNBAStep14FinalFreezeIntegrityError):
                step14d.build_step14d_release_manifest(env=safe_env())
        with patch.object(step14b, "ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED", False):
            with self.assertRaises(step14d.WNBAStep14FinalFreezeIntegrityError):
                step14d.build_step14d_release_manifest(env=safe_env())

    def test_17_parent_safety_drift_fails_closed(self) -> None:
        with patch.object(step14c, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(step14d.WNBAStep14FinalFreezeIntegrityError):
                step14d.build_step14d_release_manifest(env=safe_env())
        with patch.object(step14b, "PERSISTENCE_RUNTIME_ENABLED", True):
            with self.assertRaises(step14d.WNBAStep14FinalFreezeIntegrityError):
                step14d.build_step14d_release_manifest(env=safe_env())

    def test_18_manifest_contains_full_frozen_lineage(self) -> None:
        lineage = step14d.build_step14d_release_manifest(env=safe_env())["lineage"]
        expected = {
            "step14a_frozen_sha": step14d.STEP14A_FROZEN_SHA,
            "step14b_frozen_sha": step14d.STEP14B_FROZEN_SHA,
            "step14c_frozen_sha": step14d.STEP14C_FROZEN_SHA,
            "step13d_frozen_sha": step14d.STEP13D_FROZEN_SHA,
            "step13_release_id": step14d.STEP13_RELEASE_ID,
            "step13_release_content_sha256": step14d.STEP13_RELEASE_CONTENT_SHA256,
            "step14a_contract_id": step14d.STEP14A_CONTRACT_ID,
            "step14a_manifest_content_sha256": step14d.STEP14A_MANIFEST_CONTENT_SHA256,
            "step14a_sql_schema_sha256": step14d.STEP14A_SQL_SCHEMA_SHA256,
            "step14c_lease_sql_schema_sha256": step14d.STEP14C_LEASE_SQL_SCHEMA_SHA256,
        }
        self.assertEqual(lineage, expected)

    def test_19_manifest_build_never_requires_live_database(self) -> None:
        with patch.object(step14b, "_open_connection", side_effect=AssertionError("database opened")):
            with patch.object(step14c, "_open_connection", side_effect=AssertionError("database opened")):
                manifest = step14d.build_step14d_release_manifest(env=safe_env())
        self.assertFalse(manifest["persistence_contract"]["live_database_required_for_release_manifest"])

    def test_20_phase_boundary_closes_step14_without_activation(self) -> None:
        phase = step14d.build_step14d_release_manifest(env=safe_env())["phase_boundary"]
        self.assertTrue(phase["step14_complete"])
        self.assertTrue(phase["step14a_checkpoint_contract_frozen"])
        self.assertTrue(phase["step14b_database_adapter_frozen"])
        self.assertTrue(phase["step14c_restart_and_lease_frozen"])
        self.assertTrue(phase["production_activation_not_started"])
        self.assertTrue(phase["global_persistence_autostart_not_started"])
        self.assertTrue(phase["public_persistence_api_not_started"])
        self.assertTrue(phase["supabase_rest_write_not_started"])
        self.assertTrue(phase["wagering_not_started"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
