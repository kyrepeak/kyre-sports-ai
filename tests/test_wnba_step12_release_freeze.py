from __future__ import annotations

import unittest
from unittest.mock import patch

from sports_api import wnba_step12_release_freeze as freeze
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step12c_live_board_runtime as step12c


def _env() -> dict[str, str]:
    env = {
        freeze.STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV: "true",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
    }
    for key in (
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
    ):
        env[key] = "false"
    return env


class Tests(unittest.TestCase):
    def test_default_off(self) -> None:
        self.assertFalse(freeze.DEFAULT_ENABLED)
        self.assertFalse(freeze.step12d_final_runtime_freeze_enabled({}))

    def test_frozen_parent_chain_is_exact(self) -> None:
        self.assertEqual(
            freeze.STEP12C_FROZEN_SHA,
            "26902667212e670903b19002f7166ea435b238c2",
        )
        self.assertEqual(step12c.STEP12B_FROZEN_SHA, freeze.STEP12B_FROZEN_SHA)
        self.assertEqual(step12b.STEP12A_FROZEN_SHA, freeze.STEP12A_FROZEN_SHA)
        self.assertEqual(step12a.STEP11E_FROZEN_SHA, freeze.STEP11E_FROZEN_SHA)

    def test_release_identity_and_certified_simulations(self) -> None:
        self.assertEqual(freeze.SEASON, 2026)
        self.assertEqual(freeze.SEASON_TYPE, "Regular Season")
        self.assertEqual(
            freeze.RELEASE_ID,
            "wnba_step12_live_board_runtime_2026_regular_season_frozen_v1",
        )
        self.assertEqual(freeze.CERTIFIED_SIMULATIONS, 5_000_000)
        self.assertEqual(freeze.CERTIFIED_SIMULATIONS, step12c.CERTIFIED_SIMULATIONS)

    def test_release_safety_contract_is_all_false(self) -> None:
        self.assertTrue(freeze.SAFETY_CONTRACT)
        self.assertTrue(all(value is False for value in freeze.SAFETY_CONTRACT.values()))
        self.assertFalse(freeze.PRODUCTION_ACTIVATION_ALLOWED)
        self.assertFalse(freeze.BACKGROUND_SCHEDULER_ALLOWED)
        self.assertFalse(freeze.PERSISTENCE_ALLOWED)
        self.assertFalse(freeze.SUPABASE_WRITE_ALLOWED)
        self.assertFalse(freeze.PUBLIC_FASTAPI_ACTIVATION_ALLOWED)
        self.assertFalse(freeze.WAGERING_ALLOWED)
        self.assertFalse(freeze.AUTHENTICATION_ALLOWED)
        self.assertFalse(freeze.COOKIES_ALLOWED)
        self.assertFalse(freeze.RUNTIME_MUTATION_ALLOWED)

    def test_manifest_exposes_final_step12_runtime_contract(self) -> None:
        result = freeze.build_step12d_release_manifest(
            env=_env(), generated_at_utc="2026-08-28T16:20:00+00:00"
        )
        self.assertTrue(result["phase_boundary"]["step12_complete"])
        self.assertTrue(result["phase_boundary"]["step13_scheduler_not_started"])
        self.assertTrue(result["phase_boundary"]["step14_persistence_not_started"])
        self.assertTrue(result["runtime_contract"]["caller_driven"])
        self.assertTrue(result["runtime_contract"]["shadow_only"])
        self.assertTrue(result["runtime_contract"]["read_only"])
        self.assertEqual(result["runtime_contract"]["sportsbooks"], ["DraftKings", "FanDuel"])
        self.assertEqual(result["runtime_contract"]["sportsbook_http_methods"], ["GET"])
        self.assertTrue(result["runtime_contract"]["top_five_never_forced"])

    def test_release_hash_is_stable_across_generation_time_only(self) -> None:
        first = freeze.build_step12d_release_manifest(
            env=_env(), generated_at_utc="2026-08-28T16:20:00+00:00"
        )
        second = freeze.build_step12d_release_manifest(
            env=_env(), generated_at_utc="2026-08-28T16:21:00+00:00"
        )
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["release_content_sha256"], second["release_content_sha256"])
        self.assertEqual(len(first["release_content_sha256"]), 64)

    def test_step12d_certification_gate_is_required(self) -> None:
        env = _env()
        env[freeze.STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV] = "false"
        with self.assertRaises(freeze.WNBAStep12FinalFreezeDisabledError):
            freeze.build_step12d_release_manifest(env=env)

    def test_all_frozen_step12_runtime_gates_are_required(self) -> None:
        for key in (
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
            "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
            "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
        ):
            with self.subTest(key=key):
                env = _env()
                env[key] = "false"
                with self.assertRaises(freeze.WNBAStep12FinalFreezeDisabledError):
                    freeze.build_step12d_release_manifest(env=env)

    def test_unsafe_external_activation_switches_are_refused(self) -> None:
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        ):
            with self.subTest(key=key):
                env = _env()
                env[key] = "true"
                with self.assertRaises(freeze.WNBAStep12FinalFreezeDisabledError):
                    freeze.build_step12d_release_manifest(env=env)

    def test_downstream_safety_constant_drift_fails_closed(self) -> None:
        with patch.object(step12c, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(freeze.WNBAStep12FinalFreezeIntegrityError):
                freeze.build_step12d_release_manifest(env=_env())

    def test_manifest_contains_full_frozen_lineage(self) -> None:
        result = freeze.build_step12d_release_manifest(env=_env())
        lineage = result["lineage"]
        self.assertEqual(lineage["step12a_frozen_sha"], freeze.STEP12A_FROZEN_SHA)
        self.assertEqual(lineage["step12b_frozen_sha"], freeze.STEP12B_FROZEN_SHA)
        self.assertEqual(lineage["step12c_frozen_sha"], freeze.STEP12C_FROZEN_SHA)
        self.assertEqual(lineage["step11e_frozen_sha"], freeze.STEP11E_FROZEN_SHA)
        self.assertEqual(lineage["step10_frozen_sha"], freeze.STEP10_FROZEN_SHA)
        self.assertEqual(lineage["step9_frozen_sha"], freeze.STEP9_FROZEN_SHA)
        self.assertEqual(lineage["step8_frozen_sha"], freeze.STEP8_FROZEN_SHA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
