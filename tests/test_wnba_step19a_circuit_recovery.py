from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e


BASE = datetime(2026, 8, 29, 3, 0, tzinfo=timezone.utc)


def safe_env() -> dict[str, str]:
    return {
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED": "true",
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED": "true",
        "WNBA_STEP11B_NETWORK_REFRESH_ENABLED": "true",
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
        "WNBA_STEP10_FASTAPI_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
        "WNBA_STEP9_FASTAPI_ENABLED": "true",
        "WNBA_STEP9_THRESHOLD_PRICING_ENABLED": "true",
        "WNBA_STEP9B_MARKET_COMPARISON_ENABLED": "true",
        "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED": "true",
        "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    }


def policy() -> dict[str, int]:
    return {
        "refresh_interval_seconds": step11e.DEFAULT_REFRESH_INTERVAL_SECONDS,
        "failure_threshold": step11e.DEFAULT_FAILURE_THRESHOLD,
        "circuit_cooldown_seconds": step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS,
    }


def state_with_57_failures() -> dict:
    opened_until = BASE + timedelta(seconds=step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS)
    return step11e._make_state(
        policy=policy(),
        circuit_state="open",
        consecutive_failure_count=57,
        last_tick_at=BASE,
        last_cycle_started_at=BASE,
        last_success_at=None,
        last_failure_at=BASE,
        next_refresh_due_at=opened_until,
        circuit_open_until=opened_until,
        last_shadow_hash=None,
        last_step10_hash=None,
        last_step9_hash=None,
    )


def run_tick(at: datetime, previous_state: dict) -> dict:
    return step11e.run_step11e_controlled_automation_tick(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=[],
        previous_state=previous_state,
        evaluated_at=at,
        env=safe_env(),
    )


def healthy_shadow() -> dict:
    return {
        "shadow_board_content_sha256": "a" * 64,
        "lineage": {
            "step10_pipeline_content_sha256": "b" * 64,
            "step9_ranking_content_sha256": "c" * 64,
        },
    }


class Step19ACircuitRecoveryCertification(unittest.TestCase):
    def test_57_failures_are_preserved_during_active_cooldown(self) -> None:
        state = state_with_57_failures()
        original_open_until = state["circuit_open_until_utc"]

        with patch.object(step11e.step11d, "run_step11d_multibook_shadow_board") as provider:
            result = run_tick(BASE + timedelta(seconds=60), state)

        provider.assert_not_called()
        self.assertEqual(result["status"], "circuit_open")
        self.assertFalse(result["execution"]["cycle_executed"])
        self.assertFalse(result["execution"]["half_open_probe"])
        self.assertEqual(result["automation_state"]["consecutive_failure_count"], 57)
        self.assertEqual(result["automation_state"]["circuit_state"], "open")
        self.assertEqual(result["automation_state"]["circuit_open_until_utc"], original_open_until)

    def test_expired_cooldown_allows_exactly_one_probe_and_recovers_naturally(self) -> None:
        state = state_with_57_failures()
        probe_at = BASE + timedelta(seconds=step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS)

        with patch.object(
            step11e.step11d,
            "run_step11d_multibook_shadow_board",
            return_value=healthy_shadow(),
        ) as provider:
            result = run_tick(probe_at, state)

        provider.assert_called_once()
        self.assertTrue(result["execution"]["half_open_probe"])
        self.assertEqual(result["status"], "half_open_recovered")
        self.assertEqual(result["health"], "healthy")
        self.assertEqual(result["automation_state"]["consecutive_failure_count"], 0)
        self.assertEqual(result["automation_state"]["circuit_state"], "closed")
        self.assertIsNone(result["automation_state"]["circuit_open_until_utc"])

    def test_failed_recovery_probe_increments_to_58_and_reopens_without_reset(self) -> None:
        state = state_with_57_failures()
        probe_at = BASE + timedelta(seconds=step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS)
        error = step11e.step11d.WNBAStep11MultiBookShadowNotReadyError("synthetic provider outage")

        with patch.object(
            step11e.step11d,
            "run_step11d_multibook_shadow_board",
            side_effect=error,
        ) as provider:
            result = run_tick(probe_at, state)

        provider.assert_called_once()
        self.assertTrue(result["execution"]["half_open_probe"])
        self.assertEqual(result["status"], "half_open_failed")
        self.assertEqual(result["health"], "blocked")
        self.assertEqual(result["automation_state"]["consecutive_failure_count"], 58)
        self.assertEqual(result["automation_state"]["circuit_state"], "open")
        self.assertEqual(
            result["automation_state"]["circuit_open_until_utc"],
            (probe_at + timedelta(seconds=step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS)).isoformat(),
        )

    def test_certification_environment_keeps_production_off(self) -> None:
        environment = safe_env()
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_KYRE_DIRECT_SYNC_ENABLED",
            "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
            "WNBA_STEP6J_CANARY_ENABLED",
            "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
        ):
            self.assertEqual(environment[key], "false", key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
