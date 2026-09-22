from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step12c_live_board_runtime as step12c
from sports_api import wnba_step19k_market_not_ready as step19k
from sports_api import wnba_step19n_fanduel_empty_market as step19n

EVALUATED = datetime(2026, 8, 30, 3, 30, tzinfo=timezone.utc)
SLATE = "2026-08-29"


def request(*, previous_state=None, evaluated=EVALUATED):
    return step12b.build_step12b_request(
        season=2026,
        slate_date=SLATE,
        evaluated_at=evaluated,
        previous_state=previous_state,
        controller_policy={
            "refresh_interval_seconds": 60,
            "failure_threshold": 3,
            "circuit_cooldown_seconds": 180,
            "provider_attempts": 3,
        },
    )


def previous_state(*, circuit="closed", failures=0, open_until=None, last_failure=None):
    policy = step11e._policy(60, 3, 180)
    return step11e._make_state(
        policy=policy,
        circuit_state=circuit,
        consecutive_failure_count=failures,
        last_tick_at=EVALUATED - timedelta(minutes=2),
        last_cycle_started_at=EVALUATED - timedelta(minutes=2),
        last_success_at=None,
        last_failure_at=last_failure,
        next_refresh_due_at=EVALUATED - timedelta(seconds=1),
        circuit_open_until=open_until,
        last_shadow_hash=None,
        last_step10_hash=None,
        last_step9_hash=None,
    )


def provider_transient_result(*, fd_message=None, fd_type=None, dk_records=12, fd_attempts=3):
    message = fd_message or step19n.FANDUEL_EMPTY_MARKET_MESSAGE
    error_type = fd_type or fanduel.WNBAStep11FanDuelProviderNotReadyError.__name__
    errors = [
        {"attempt": n, "error_type": error_type, "error_message": message}
        for n in range(1, fd_attempts + 1)
    ]
    state = previous_state(failures=1, last_failure=EVALUATED)
    tick = {
        "execution": {"cycle_outcome": "provider_transient_not_ready", "cycle_executed": True},
        "automation_state": state,
    }
    return {
        "data_type": "wnba_step12b_live_runtime_assembly_response",
        "schema_version": step12b.SCHEMA_VERSION,
        "status": "transient_failure",
        "health": "degraded",
        "slate_date": SLATE,
        "provider_discovery": {
            "sportsbooks": ["DraftKings", "FanDuel"],
            "draftkings": {
                "provider": "DraftKings",
                "attempt_limit": 3,
                "attempts_executed": 1,
                "retryable_failures": 0,
                "record_count": dk_records,
                "bridge_content_sha256": "d" * 64 if dk_records else None,
                "errors": [],
            },
            "fanduel": {
                "provider": "FanDuel",
                "attempt_limit": fd_attempts,
                "attempts_executed": fd_attempts,
                "retryable_failures": fd_attempts,
                "record_count": 0,
                "bridge_content_sha256": None,
                "errors": errors,
            },
            "sportsbook_network_fetches_reused_in_step11_tick": True,
            "duplicate_sportsbook_discovery_performed": False,
            "transient_provider_short_circuit": True,
        },
        "projection_assembly": {"built_target_count": 0},
        "step12a_result": {"step11e_tick": tick},
    }


class Step19NClassificationTests(unittest.TestCase):
    def setUp(self):
        step19n._reset_for_test()

    def _run(self, parent, req=None):
        original_upstream = step19n._UPSTREAM_RUN_STEP12B
        try:
            step19n._UPSTREAM_RUN_STEP12B = lambda *_args, **_kwargs: parent
            with patch.object(step11e, "_assert_safe_environment", return_value=None):
                return step19n.run_step12b_fanduel_empty_market_compatible(
                    req or request(), env={}
                )
        finally:
            step19n._UPSTREAM_RUN_STEP12B = original_upstream

    def test_exact_empty_market_becomes_closed_circuit_market_not_ready(self):
        parent = provider_transient_result()
        result = self._run(parent)
        tick = result["step12a_result"]["step11e_tick"]
        state = tick["automation_state"]
        self.assertEqual(result["status"], "market_not_ready")
        self.assertEqual(result["health"], "market_not_ready")
        self.assertEqual(tick["execution"]["cycle_outcome"], "market_board_not_ready")
        self.assertEqual(state["circuit_state"], "closed")
        self.assertEqual(state["consecutive_failure_count"], 0)
        self.assertEqual(result["market_overlap"]["draftkings_record_count"], 12)
        self.assertEqual(result["market_overlap"]["fanduel_record_count"], 0)
        self.assertEqual(result["projection_assembly"]["built_target_count"], 0)
        self.assertFalse(result["guardrails"]["fanduel_bridge_fabricated"])
        self.assertFalse(result["guardrails"]["transport_failure_reclassified"])
        self.assertFalse(result["guardrails"]["identity_failure_reclassified"])
        self.assertFalse(result["guardrails"]["readiness_relaxed"])
        self.assertFalse(result["guardrails"]["wager_action_performed"])
        self.assertEqual(step19n.installation_status()["transformed_count"], 1)

        verified_hash = step12c._verify_step12b_result(result, SLATE)
        self.assertEqual(verified_hash, result["runtime_content_sha256"])
        nested, shadow, pipeline = step12c._nested_runtime(result)
        self.assertEqual(nested["execution"]["cycle_outcome"], "market_board_not_ready")
        self.assertIsNone(shadow)
        self.assertIsNone(pipeline)

    def test_exact_message_and_error_class_are_required(self):
        wrong_message = provider_transient_result(
            fd_message="FanDuel WNBA landing page exposed no target-slate events."
        )
        wrong_type = provider_transient_result(
            fd_type=fanduel.WNBAStep11FanDuelProviderUpstreamError.__name__
        )
        self.assertFalse(step19n._is_fanduel_empty_market_response(wrong_message))
        self.assertFalse(step19n._is_fanduel_empty_market_response(wrong_type))

    def test_landing_or_upstream_failure_is_returned_unchanged(self):
        parent = provider_transient_result(
            fd_message="FanDuel WNBA landing page exposed no target-slate events."
        )
        result = self._run(parent)
        self.assertIs(result, parent)
        self.assertEqual(step19n.installation_status()["transformed_count"], 0)

    def test_draftkings_must_be_verified_nonempty(self):
        parent = provider_transient_result(dk_records=0)
        result = self._run(parent)
        self.assertIs(result, parent)
        self.assertFalse(step19n._is_fanduel_empty_market_response(parent))

    def test_all_fanduel_attempts_must_be_exact_empty_market_subtype(self):
        parent = provider_transient_result()
        parent["provider_discovery"]["fanduel"]["errors"][1]["error_message"] = (
            "Step 11C endpoint returned invalid JSON."
        )
        result = self._run(parent)
        self.assertIs(result, parent)

    def test_expired_provider_circuit_recovers_to_closed_market_not_ready(self):
        state0 = previous_state(
            circuit="open",
            failures=3,
            open_until=EVALUATED - timedelta(seconds=1),
            last_failure=EVALUATED - timedelta(minutes=3),
        )
        result = self._run(provider_transient_result(), request(previous_state=state0))
        tick = result["step12a_result"]["step11e_tick"]
        self.assertTrue(tick["execution"]["half_open_probe"])
        self.assertEqual(tick["circuit_breaker"]["state_before"], "open")
        self.assertEqual(tick["circuit_breaker"]["state_after"], "closed")
        self.assertEqual(tick["automation_state"]["consecutive_failure_count"], 0)

    def test_non_provider_transient_parent_is_never_transformed(self):
        parent = provider_transient_result()
        parent["step12a_result"]["step11e_tick"]["execution"]["cycle_outcome"] = "shadow_board_ready"
        result = self._run(parent)
        self.assertIs(result, parent)


class Step19NInstallationTests(unittest.TestCase):
    def test_install_requires_step19k_and_keeps_guardrails_strict(self):
        old_run = step12b.run_step12b_live_runtime_job
        old_upstream = step19n._UPSTREAM_RUN_STEP12B
        old_installed = step19n._INSTALLED
        try:
            with patch.object(step19k, "install_step19k_market_not_ready", return_value={}):
                step12b.run_step12b_live_runtime_job = step19k.run_step12b_market_not_ready_compatible
                step19n._UPSTREAM_RUN_STEP12B = None
                step19n._INSTALLED = False
                status = step19n.install_step19n_fanduel_empty_market()
                self.assertIs(
                    step12b.run_step12b_live_runtime_job,
                    step19n.run_step12b_fanduel_empty_market_compatible,
                )
                self.assertIs(
                    step19n._UPSTREAM_RUN_STEP12B,
                    step19k.run_step12b_market_not_ready_compatible,
                )
                guards = status["guardrails"]
                self.assertTrue(guards["draftkings_verified_nonempty_required"])
                self.assertTrue(guards["all_fanduel_attempts_must_match"])
                self.assertFalse(guards["identity_failure_reclassified"])
                self.assertFalse(guards["transport_failure_reclassified"])
                self.assertFalse(guards["upstream_failure_reclassified"])
                self.assertFalse(guards["landing_page_failure_reclassified"])
                self.assertFalse(guards["fanduel_bridge_fabricated"])
                self.assertFalse(guards["different_lines_blended"])
                self.assertFalse(guards["fake_projection_created"])
                self.assertFalse(guards["readiness_relaxed"])
                self.assertFalse(guards["wagering_enabled"])
        finally:
            step12b.run_step12b_live_runtime_job = old_run
            step19n._UPSTREAM_RUN_STEP12B = old_upstream
            step19n._INSTALLED = old_installed


if __name__ == "__main__":
    unittest.main(verbosity=2)
