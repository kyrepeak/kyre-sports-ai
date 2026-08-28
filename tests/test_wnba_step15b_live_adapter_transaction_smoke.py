from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from sports_api import wnba_step14b_database_checkpoint_adapter as step14b
from sports_api import wnba_step15b_live_adapter_transaction_smoke as s15b


_REQUIRED = (
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
    env = {name: "true" for name in _REQUIRED}
    env[s15b.STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV] = "true"
    for name in _FORBIDDEN:
        env[name] = "false"
    return env


class Tests(unittest.TestCase):
    def test_01_default_off_and_exact_parent(self) -> None:
        self.assertFalse(s15b.DEFAULT_ENABLED)
        self.assertFalse(s15b.step15b_live_adapter_smoke_enabled({}))
        self.assertEqual(
            s15b.STEP15A_CERTIFIED_SHA,
            "9cc30b96c4583f6b18306910ca4a7fb70d93c325",
        )

    def test_02_live_evidence_content_hash_is_pinned(self) -> None:
        evidence = s15b.load_step15b_live_evidence()
        self.assertEqual(
            evidence["evidence_content_sha256"],
            s15b.LIVE_EVIDENCE_CONTENT_SHA256,
        )

    def test_03_expected_live_project_and_smoke_scope(self) -> None:
        evidence = s15b.validate_step15b_live_evidence(s15b.load_step15b_live_evidence())
        self.assertEqual(evidence["supabase_project"]["ref"], "jqajcdckalsfizbvngiu")
        self.assertEqual(evidence["supabase_project"]["status"], "ACTIVE_HEALTHY")
        self.assertEqual(evidence["smoke_scope"]["slate_date"], "2026-01-15")
        self.assertEqual(evidence["smoke_scope"]["checkpoint_key"], s15b.EXPECTED_CHECKPOINT_KEY)
        self.assertEqual(evidence["smoke_scope"]["lease_key"], s15b.EXPECTED_LEASE_KEY)

    def test_04_frozen_adapter_sql_fingerprints_match(self) -> None:
        self.assertEqual(s15b.validate_frozen_sql_fingerprints(), s15b.SQL_FINGERPRINTS)

    def test_05_checkpoint_v1_created_and_loaded_exactly(self) -> None:
        c = s15b.load_step15b_live_evidence()["checkpoint_smoke"]
        self.assertTrue(c["version_1_created"])
        self.assertTrue(c["load_round_trip_exact"])
        self.assertEqual(c["version_1_checkpoint_id"], "aff40b6b-8e3d-5982-9746-4bf10ab776c9")
        self.assertEqual(len(c["version_1_envelope_content_sha256"]), 64)
        self.assertEqual(len(c["version_1_controller_state_sha256"]), 64)

    def test_06_checkpoint_idempotency_kept_one_history_row(self) -> None:
        c = s15b.load_step15b_live_evidence()["checkpoint_smoke"]
        self.assertEqual(c["idempotent_repeat_history_rows"], 1)

    def test_07_checkpoint_advance_created_v2_and_append_only_history(self) -> None:
        c = s15b.load_step15b_live_evidence()["checkpoint_smoke"]
        self.assertTrue(c["version_2_advanced"])
        self.assertEqual(c["history_rows_after_advance"], 2)
        self.assertNotEqual(c["version_1_checkpoint_id"], c["version_2_checkpoint_id"])
        self.assertNotEqual(c["version_1_envelope_content_sha256"], c["version_2_envelope_content_sha256"])

    def test_08_stale_cas_rejected_and_transaction_rolled_back(self) -> None:
        c = s15b.load_step15b_live_evidence()["checkpoint_smoke"]
        self.assertEqual(c["stale_expected_version"], 1)
        self.assertEqual(c["current_version_during_stale_attempt"], 2)
        self.assertTrue(c["stale_cas_rejected"])
        self.assertTrue(c["stale_transaction_rolled_back"])
        self.assertFalse(c["stale_history_row_survived"])
        self.assertEqual(c["history_rows_after_stale_attempt"], 2)

    def test_09_initial_lease_generation_and_duplicate_block(self) -> None:
        lease = s15b.load_step15b_live_evidence()["lease_smoke"]
        self.assertEqual(lease["initial_acquire_generation"], 1)
        self.assertEqual(lease["duplicate_active_acquire_rows"], 0)

    def test_10_lease_renew_and_wrong_owner_rejection(self) -> None:
        lease = s15b.load_step15b_live_evidence()["lease_smoke"]
        self.assertTrue(lease["owner_a_renew_succeeded"])
        self.assertEqual(lease["wrong_owner_renew_rows"], 0)

    def test_11_expiry_takeover_increments_fencing_generation(self) -> None:
        lease = s15b.load_step15b_live_evidence()["lease_smoke"]
        self.assertTrue(lease["test_only_expiry_forced"])
        self.assertEqual(lease["takeover_generation"], 2)
        self.assertGreater(lease["takeover_generation"], lease["initial_acquire_generation"])

    def test_12_stale_release_blocked_and_current_owner_release_succeeds(self) -> None:
        lease = s15b.load_step15b_live_evidence()["lease_smoke"]
        self.assertEqual(lease["stale_owner_release_rows"], 0)
        self.assertTrue(lease["current_owner_release_succeeded"])

    def test_13_cleanup_returns_all_step14_tables_to_zero(self) -> None:
        cleanup = s15b.load_step15b_live_evidence()["cleanup"]
        self.assertTrue(cleanup["live_step14_tables_returned_to_empty_state"])
        self.assertEqual(cleanup["checkpoint_heads_rows_after_cleanup"], 0)
        self.assertEqual(cleanup["checkpoint_history_rows_after_cleanup"], 0)
        self.assertEqual(cleanup["lease_rows_after_cleanup"], 0)

    def test_14_direct_psycopg_live_secret_is_not_falsely_certified(self) -> None:
        evidence = s15b.load_step15b_live_evidence()["execution_boundary"]
        self.assertFalse(s15b.DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED)
        self.assertFalse(evidence["python_psycopg_adapter_connected_directly"])
        self.assertTrue(evidence["frozen_adapter_sql_semantics_executed_live"])
        self.assertIn("KYRE_DATABASE_URL", evidence["reason_direct_adapter_not_connected"])

    def test_15_manifest_certifies_transactions_without_runtime_activation(self) -> None:
        manifest = s15b.build_step15b_live_smoke_manifest(env=safe_env())
        self.assertTrue(manifest["activation_contract"]["live_database_transaction_smoke_completed"])
        self.assertFalse(manifest["activation_contract"]["live_scheduler_started"])
        self.assertFalse(manifest["activation_contract"]["global_persistence_runtime_enabled"])
        self.assertFalse(manifest["activation_contract"]["production_runtime_enabled"])
        self.assertTrue(all(value is False for value in manifest["safety_contract"].values()))

    def test_16_manifest_content_hash_is_generation_time_independent(self) -> None:
        a = s15b.build_step15b_live_smoke_manifest(
            env=safe_env(), generated_at_utc="2026-08-28T19:30:00+00:00"
        )
        b = s15b.build_step15b_live_smoke_manifest(
            env=safe_env(), generated_at_utc="2026-08-29T01:30:00+00:00"
        )
        self.assertNotEqual(a["generated_at_utc"], b["generated_at_utc"])
        self.assertEqual(a["smoke_content_sha256"], b["smoke_content_sha256"])

    def test_17_step15b_gate_is_required(self) -> None:
        env = safe_env()
        env.pop(s15b.STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV)
        with self.assertRaises(s15b.WNBAStep15BLiveSmokeDisabledError):
            s15b.build_step15b_live_smoke_manifest(env=env)

    def test_18_all_parent_gates_are_required(self) -> None:
        for gate in _REQUIRED:
            with self.subTest(gate=gate):
                env = safe_env()
                env.pop(gate)
                with self.assertRaises(s15b.WNBAStep15BLiveSmokeDisabledError):
                    s15b.build_step15b_live_smoke_manifest(env=env)

    def test_19_unsafe_global_switches_are_refused(self) -> None:
        for key in _FORBIDDEN:
            with self.subTest(key=key):
                env = safe_env()
                env[key] = "true"
                with self.assertRaises(s15b.WNBAStep15BLiveSmokeDisabledError):
                    s15b.build_step15b_live_smoke_manifest(env=env)

    def test_20_evidence_or_frozen_sql_tamper_fails_closed(self) -> None:
        evidence = s15b.load_step15b_live_evidence()
        tampered = deepcopy(evidence)
        tampered["checkpoint_smoke"]["stale_cas_rejected"] = False
        with self.assertRaises(s15b.WNBAStep15BLiveSmokeIntegrityError):
            s15b.validate_step15b_live_evidence(tampered)
        with patch.object(step14b, "_UPDATE_HEAD_SQL", step14b._UPDATE_HEAD_SQL + "\n-- drift"):
            with self.assertRaises(s15b.WNBAStep15BLiveSmokeIntegrityError):
                s15b.validate_frozen_sql_fingerprints()


if __name__ == "__main__":
    unittest.main(verbosity=2)
