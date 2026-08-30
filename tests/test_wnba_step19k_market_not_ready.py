from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step12c_live_board_runtime as step12c
from sports_api import wnba_step19j_runtime_acceleration as step19j
from sports_api import wnba_step19k_market_not_ready as step19k


EVALUATED = datetime(2026, 8, 30, 2, 30, tzinfo=timezone.utc)
SLATE = "2026-08-29"


def request(*, previous_state=None, evaluated=EVALUATED, policy=None):
    return step12b.build_step12b_request(
        season=2026,
        slate_date=SLATE,
        evaluated_at=evaluated,
        previous_state=previous_state,
        controller_policy=policy or {
            "refresh_interval_seconds": 60,
            "failure_threshold": 3,
            "circuit_cooldown_seconds": 180,
            "provider_attempts": 3,
        },
    )


def previous_state(
    *,
    circuit="closed",
    failures=0,
    next_due=None,
    open_until=None,
    last_success=None,
    last_failure=None,
):
    policy = step11e._policy(60, 3, 180)
    return step11e._make_state(
        policy=policy,
        circuit_state=circuit,
        consecutive_failure_count=failures,
        last_tick_at=EVALUATED - timedelta(minutes=2),
        last_cycle_started_at=EVALUATED - timedelta(minutes=2),
        last_success_at=last_success,
        last_failure_at=last_failure,
        next_refresh_due_at=next_due or (EVALUATED - timedelta(seconds=1)),
        circuit_open_until=open_until,
        last_shadow_hash="a" * 64 if last_success else None,
        last_step10_hash="b" * 64 if last_success else None,
        last_step9_hash="c" * 64 if last_success else None,
    )


class Step19KClassificationTests(unittest.TestCase):
    def setUp(self):
        with step19k._LOCK:
            step19k._TRANSFORMED_COUNT = 0
            step19k._LAST_TRANSFORM = None

    def _run_exact_line_exception(self, req):
        def upstream(*_args, **_kwargs):
            raise step12b.WNBAStep12LiveRuntimeNotReadyError(
                step19k.NO_EXACT_LINE_MESSAGE
            )

        old = step19k._UPSTREAM_RUN_STEP12B
        try:
            step19k._UPSTREAM_RUN_STEP12B = upstream
            with patch.object(step11e, "_assert_safe_environment", return_value=None):
                return step19k.run_step12b_market_not_ready_compatible(req, env={})
        finally:
            step19k._UPSTREAM_RUN_STEP12B = old

    def test_no_exact_line_becomes_closed_circuit_market_not_ready(self):
        result = self._run_exact_line_exception(request())
        tick = result["step12a_result"]["step11e_tick"]
        state = tick["automation_state"]

        self.assertEqual(result["status"], "market_not_ready")
        self.assertEqual(result["health"], "market_not_ready")
        self.assertEqual(tick["execution"]["cycle_outcome"], "market_board_not_ready")
        self.assertEqual(tick["execution"]["error"]["error_type"], "WNBAStep10LivePipelineNotReadyError")
        self.assertEqual(state["circuit_state"], "closed")
        self.assertEqual(state["consecutive_failure_count"], 0)
        self.assertIsNone(state["circuit_open_until_utc"])
        self.assertEqual(
            state["next_refresh_due_at_utc"],
            (EVALUATED + timedelta(seconds=60)).isoformat(),
        )
        self.assertEqual(result["market_overlap"]["exact_line_multibook_group_count"], 0)
        self.assertFalse(result["market_overlap"]["different_lines_blended"])
        self.assertEqual(result["projection_assembly"]["built_target_count"], 0)
        self.assertTrue(result["projection_assembly"]["short_circuited_before_projection"])
        self.assertTrue(result["guardrails"]["exact_line_multibook_overlap_required"])
        self.assertFalse(result["guardrails"]["readiness_relaxed"])

        parent_hash = step12c._verify_step12b_result(result, SLATE)
        self.assertEqual(parent_hash, result["runtime_content_sha256"])
        nested_tick, shadow, pipeline = step12c._nested_runtime(result)
        self.assertEqual(nested_tick["execution"]["cycle_outcome"], "market_board_not_ready")
        self.assertIsNone(shadow)
        self.assertIsNone(pipeline)

    def test_market_not_ready_resets_prior_provider_failure_count_without_faking_success(self):
        last_failure = EVALUATED - timedelta(minutes=1)
        state0 = previous_state(failures=2, last_failure=last_failure)
        result = self._run_exact_line_exception(request(previous_state=state0))
        tick = result["step12a_result"]["step11e_tick"]
        state = tick["automation_state"]
        self.assertEqual(tick["circuit_breaker"]["consecutive_failures_before"], 2)
        self.assertEqual(tick["circuit_breaker"]["consecutive_failures_after"], 0)
        self.assertEqual(state["circuit_state"], "closed")
        self.assertEqual(state["consecutive_failure_count"], 0)
        self.assertEqual(state["last_failure_at_utc"], last_failure.isoformat())
        self.assertIsNone(state["last_success_at_utc"])

    def test_expired_open_circuit_closes_when_providers_are_healthy_but_market_has_no_overlap(self):
        state0 = previous_state(
            circuit="open",
            failures=3,
            next_due=EVALUATED - timedelta(seconds=1),
            open_until=EVALUATED - timedelta(seconds=1),
            last_failure=EVALUATED - timedelta(minutes=3),
        )
        result = self._run_exact_line_exception(request(previous_state=state0))
        tick = result["step12a_result"]["step11e_tick"]
        self.assertTrue(tick["execution"]["half_open_probe"])
        self.assertEqual(tick["execution"]["cycle_outcome"], "market_board_not_ready")
        self.assertEqual(tick["circuit_breaker"]["state_before"], "open")
        self.assertEqual(tick["circuit_breaker"]["state_after"], "closed")
        self.assertEqual(tick["automation_state"]["consecutive_failure_count"], 0)

    def test_not_due_controller_stays_not_executed(self):
        future = EVALUATED + timedelta(seconds=40)
        state0 = previous_state(next_due=future)
        result = self._run_exact_line_exception(request(previous_state=state0))
        tick = result["step12a_result"]["step11e_tick"]
        self.assertEqual(tick["status"], "not_due")
        self.assertEqual(tick["execution"]["cycle_outcome"], "not_executed")
        self.assertFalse(tick["execution"]["cycle_executed"])
        self.assertEqual(tick["automation_state"]["next_refresh_due_at_utc"], future.isoformat())

    def test_unrelated_step12b_not_ready_is_not_reclassified(self):
        def upstream(*_args, **_kwargs):
            raise step12b.WNBAStep12LiveRuntimeNotReadyError(
                "Step 12B could not build any certified converged Step-8 distribution."
            )

        old = step19k._UPSTREAM_RUN_STEP12B
        try:
            step19k._UPSTREAM_RUN_STEP12B = upstream
            with self.assertRaisesRegex(
                step12b.WNBAStep12LiveRuntimeNotReadyError,
                "certified converged",
            ):
                step19k.run_step12b_market_not_ready_compatible(request(), env={})
        finally:
            step19k._UPSTREAM_RUN_STEP12B = old

    def test_exact_line_message_must_match_exactly(self):
        self.assertTrue(
            step19k._is_no_exact_line_condition(
                step12b.WNBAStep12LiveRuntimeNotReadyError(
                    step19k.NO_EXACT_LINE_MESSAGE
                )
            )
        )
        self.assertFalse(
            step19k._is_no_exact_line_condition(
                step12b.WNBAStep12LiveRuntimeNotReadyError(
                    step19k.NO_EXACT_LINE_MESSAGE + " changed"
                )
            )
        )


class Step19KInstallationTests(unittest.TestCase):
    def test_install_wraps_step19j_only_and_keeps_safety_guards_strict(self):
        with patch.object(step19j, "install_step19j_runtime_acceleration", return_value={}):
            old_run = step12b.run_step12b_live_runtime_job
            old_upstream = step19k._UPSTREAM_RUN_STEP12B
            old_installed = step19k._INSTALLED
            try:
                step12b.run_step12b_live_runtime_job = step19j.run_step12b_with_cycle_local_context
                step19k._UPSTREAM_RUN_STEP12B = None
                step19k._INSTALLED = False
                status = step19k.install_step19k_market_not_ready()
                self.assertIs(
                    step12b.run_step12b_live_runtime_job,
                    step19k.run_step12b_market_not_ready_compatible,
                )
                self.assertIs(
                    step19k._UPSTREAM_RUN_STEP12B,
                    step19j.run_step12b_with_cycle_local_context,
                )
                guards = status["guardrails"]
                self.assertTrue(guards["exact_line_overlap_required"])
                self.assertFalse(guards["different_lines_blended"])
                self.assertFalse(guards["fake_projection_created"])
                self.assertFalse(guards["readiness_relaxed"])
                self.assertFalse(guards["wagering_enabled"])
            finally:
                step12b.run_step12b_live_runtime_job = old_run
                step19k._UPSTREAM_RUN_STEP12B = old_upstream
                step19k._INSTALLED = old_installed


if __name__ == "__main__":
    unittest.main(verbosity=2)
