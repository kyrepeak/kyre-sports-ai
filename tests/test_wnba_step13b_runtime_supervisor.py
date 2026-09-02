from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from sports_api import wnba_step12_release_freeze as release
from sports_api import wnba_step12c_live_board_runtime as step12c
from sports_api import wnba_step13a_bounded_scheduler as step13a
from sports_api import wnba_step13b_runtime_supervisor as supervisor


BASE = datetime(2026, 8, 28, 16, 40, tzinfo=timezone.utc)


def safe_env() -> dict[str, str]:
    return {
        "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED": "true",
        "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED": "true",
        "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED": "true",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


class FakeClock:
    def __init__(self, current: datetime = BASE) -> None:
        self.current = current
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)


def make_step13a_result(request: dict, *, now: datetime, session: int, delay_seconds: int = 60) -> dict:
    next_due = now + timedelta(seconds=delay_seconds)
    state = {
        "data_type": "wnba_step11e_controlled_automation_state",
        "state_content_sha256": f"{session:064x}",
        "next_refresh_due_at_utc": next_due.isoformat(),
        "session": session,
    }
    result = {
        "data_type": "wnba_step13a_bounded_scheduler_response",
        "schema_version": step13a.SCHEMA_VERSION,
        "source": "test",
        "model_version": "test",
        "generated_at_utc": now.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "completed",
        "health": "healthy",
        "slate_date": request["slate_date"],
        "scheduler_summary": {
            "requested_cycles": request["max_cycles"],
            "executed_ticks": request["max_cycles"],
            "sleep_calls": 0,
            "total_sleep_seconds": 0.0,
            "sleep_budget_seconds": request["max_total_sleep_seconds"],
            "stop_reason": "max_cycles_reached",
            "started_at_utc": now.isoformat(),
            "ended_at_utc": now.isoformat(),
        },
        "tick_history": [],
        "latest_board": {"available": True, "top_card_count": 1},
        "latest_runtime": {
            "health": "healthy",
            "next_refresh_due_at_utc": next_due.isoformat(),
            "circuit_state": "closed",
        },
        "final_controller_state_for_next_process": state,
        "lineage": {
            "step12d_frozen_sha": supervisor.STEP12D_FROZEN_SHA,
            "step12_release_id": release.RELEASE_ID,
        },
        "guardrails": {
            "shadow_only": True,
            "bounded_foreground_scheduler_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "state_persisted": False,
            "supabase_mutated": False,
            "public_fastapi_route_added": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_ranking_changed": False,
            "step9_qualification_changed": False,
            "step12_presentation_changed": False,
        },
    }
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "scheduler_content_sha256"}
    }
    result["scheduler_content_sha256"] = supervisor._canonical_hash(surface)
    return result


def make_step12c_result(request: dict, *, tick: int, delay_seconds: int = 60) -> dict:
    evaluated = datetime.fromisoformat(request["evaluated_at_utc"])
    next_due = evaluated + timedelta(seconds=delay_seconds)
    state = {
        "data_type": "wnba_step11e_controlled_automation_state",
        "state_content_sha256": f"{tick:064x}",
        "next_refresh_due_at_utc": next_due.isoformat(),
        "tick": tick,
    }
    result = {
        "data_type": "wnba_step12c_live_board_runtime_response",
        "schema_version": step12c.SCHEMA_VERSION,
        "source": "test",
        "model_version": "test",
        "generated_at_utc": evaluated.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "healthy",
        "health": "healthy",
        "slate_date": request["slate_date"],
        "runtime": {
            "status": "healthy",
            "health": "healthy",
            "evaluated_at_utc": evaluated.isoformat(),
            "cycle_due": True,
            "cycle_executed": True,
            "cycle_outcome": "shadow_board_ready",
            "skip_reason": None,
            "circuit_state": "closed",
            "consecutive_failures": 0,
            "next_refresh_due_at_utc": next_due.isoformat(),
            "circuit_open_until_utc": None,
            "controller_state_content_sha256": state["state_content_sha256"],
        },
        "board": {
            "available": True,
            "requested_top_card_count": 5,
            "qualified_prop_count": 1,
            "top_card_count": 1,
            "primary_top_cards": [],
            "value_ranking": [],
        },
        "controller_state_for_next_caller_tick": state,
        "diagnostics": {},
        "lineage": {
            "step12b_frozen_sha": release.STEP12B_FROZEN_SHA,
            "step12b_runtime_content_sha256": "1" * 64,
        },
        "guardrails": {},
    }
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "board_content_sha256"}
    }
    result["board_content_sha256"] = step13a._canonical_hash(surface)
    return result


class Tests(unittest.TestCase):
    def request(self, **kwargs) -> dict:
        params = {
            "season": 2026,
            "initial_slate_date": "2026-08-28",
            "slate_timezone": "America/New_York",
            "rollover_policy": "stop",
            "max_supervisor_sessions": 1,
            "max_supervisor_runtime_seconds": 3600,
            "max_total_intersession_sleep_seconds": 3600,
            "scheduler_cycles_per_session": 1,
            "scheduler_sleep_budget_seconds_per_session": 0,
        }
        params.update(kwargs)
        return supervisor.build_step13b_request(**params)

    def test_default_off_and_frozen_parent(self) -> None:
        self.assertFalse(supervisor.DEFAULT_ENABLED)
        self.assertFalse(supervisor.step13b_runtime_supervisor_enabled({}))
        self.assertEqual(supervisor.STEP13A_FROZEN_SHA, "eaa744ae097a94d5f54c490ab13ca7d66bb725c2")
        self.assertEqual(supervisor.STEP12D_FROZEN_SHA, "48517bac86ee3f55aa4c21d6caba06c41a0a7d60")
        self.assertTrue(supervisor.FOREGROUND_RUNTIME_SUPERVISOR_ALLOWED)
        self.assertFalse(supervisor.BACKGROUND_DAEMON_ALLOWED)
        self.assertFalse(supervisor.BACKGROUND_THREAD_ALLOWED)

    def test_requires_step13b_gate(self) -> None:
        env = safe_env()
        env.pop("WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED")
        with self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorDisabledError):
            supervisor.run_step13b_runtime_supervisor(self.request(), env=env, step13a_runner=lambda *a, **k: {})

    def test_requires_frozen_parent_gates(self) -> None:
        for key in (
            "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
            "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
            "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
            "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
        ):
            env = safe_env()
            env[key] = "false"
            with self.subTest(key=key), self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorDisabledError):
                supervisor.run_step13b_runtime_supervisor(self.request(), env=env, step13a_runner=lambda *a, **k: {})

    def test_refuses_unsafe_external_switches(self) -> None:
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        ):
            env = safe_env()
            env[key] = "true"
            with self.subTest(key=key), self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorDisabledError):
                supervisor.run_step13b_runtime_supervisor(self.request(), env=env, step13a_runner=lambda *a, **k: {})

    def test_request_hash_tamper_detected(self) -> None:
        request = self.request()
        request["max_supervisor_sessions"] = 2
        with self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorIntegrityError):
            supervisor.run_step13b_runtime_supervisor(request, env=safe_env(), step13a_runner=lambda *a, **k: {})

    def test_unknown_request_field_fails_closed(self) -> None:
        request = self.request()
        request["surprise"] = True
        request["request_content_sha256"] = supervisor._canonical_hash(
            {key: value for key, value in request.items() if key != "request_content_sha256"}
        )
        with self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorInputError):
            supervisor.run_step13b_runtime_supervisor(request, env=safe_env(), step13a_runner=lambda *a, **k: {})

    def test_invalid_timezone_and_rollover_policy_rejected(self) -> None:
        with self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorInputError):
            self.request(slate_timezone="Mars/Olympus")
        with self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorInputError):
            self.request(rollover_policy="blend")

    def test_one_session_calls_parent_once_without_intersession_sleep(self) -> None:
        clock = FakeClock()
        calls: list[dict] = []

        def runner(request, **kwargs):
            calls.append(deepcopy(request))
            return make_step13a_result(request, now=clock.current, session=1)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(), env=safe_env(), clock=clock.now, sleeper=clock.sleep, step13a_runner=runner
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(result["supervisor_summary"]["completed_sessions"], 1)
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "max_sessions_reached")

    def test_two_sessions_chain_state_and_wait_to_frozen_due(self) -> None:
        clock = FakeClock()
        calls: list[dict] = []

        def runner(request, **kwargs):
            calls.append(deepcopy(request))
            session = len(calls)
            if session == 1:
                self.assertIsNone(request["initial_previous_state"])
            else:
                self.assertEqual(request["initial_previous_state"]["session"], 1)
            return make_step13a_result(request, now=clock.current, session=session, delay_seconds=60)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=runner,
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(clock.sleeps, [60.0])
        self.assertEqual(result["supervisor_summary"]["total_intersession_sleep_seconds"], 60.0)
        self.assertEqual(result["final_controller_state_for_restart_handoff"]["session"], 2)

    def test_graceful_shutdown_before_first_session(self) -> None:
        clock = FakeClock()
        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            stop_requested=lambda: True,
            step13a_runner=lambda *a, **k: self.fail("scheduler should not run"),
        )
        self.assertEqual(result["supervisor_summary"]["completed_sessions"], 0)
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "graceful_shutdown_requested")
        self.assertEqual(result["health"], "not_started")

    def test_graceful_shutdown_after_one_session(self) -> None:
        clock = FakeClock()
        checks = iter([False, True])
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            return make_step13a_result(request, now=clock.current, session=calls)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=3),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            stop_requested=lambda: next(checks),
            step13a_runner=runner,
        )
        self.assertEqual(calls, 1)
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "graceful_shutdown_requested")

    def test_stop_rollover_policy_never_calls_old_slate_after_midnight(self) -> None:
        clock = FakeClock(datetime(2026, 8, 29, 3, 59, tzinfo=timezone.utc))
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            return make_step13a_result(request, now=clock.current, session=calls, delay_seconds=120)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2, rollover_policy="stop"),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=runner,
        )
        self.assertEqual(calls, 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "slate_rollover_required")

    def test_advance_rollover_resets_state_before_new_slate(self) -> None:
        clock = FakeClock(datetime(2026, 8, 29, 3, 59, tzinfo=timezone.utc))
        calls: list[dict] = []

        def runner(request, **kwargs):
            calls.append(deepcopy(request))
            session = len(calls)
            delay = 120 if session == 1 else 60
            return make_step13a_result(request, now=clock.current, session=session, delay_seconds=delay)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2, rollover_policy="advance_reset"),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=runner,
        )
        self.assertEqual([c["slate_date"] for c in calls], ["2026-08-28", "2026-08-29"])
        self.assertIsNone(calls[1]["initial_previous_state"])
        self.assertEqual(clock.sleeps, [120.0])
        self.assertEqual(result["supervisor_summary"]["rollover_count"], 1)
        self.assertTrue(result["rollover_history"][0]["controller_state_reset"])

    def test_season_boundary_stops_before_sleeping_into_2027(self) -> None:
        clock = FakeClock(datetime(2027, 1, 1, 4, 59, tzinfo=timezone.utc))  # 2026-12-31 23:59 ET

        def runner(request, **kwargs):
            return make_step13a_result(request, now=clock.current, session=1, delay_seconds=120)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(initial_slate_date="2026-12-31", max_supervisor_sessions=2, rollover_policy="advance_reset"),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=runner,
        )
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "season_boundary_reached")
        self.assertEqual(clock.sleeps, [])

    def test_runtime_budget_stops_before_intersession_wait(self) -> None:
        clock = FakeClock()

        def runner(request, **kwargs):
            return make_step13a_result(request, now=clock.current, session=1, delay_seconds=60)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2, max_supervisor_runtime_seconds=30),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=runner,
        )
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "runtime_budget_reached")
        self.assertEqual(clock.sleeps, [])

    def test_intersession_sleep_budget_stops_cleanly(self) -> None:
        clock = FakeClock()

        def runner(request, **kwargs):
            return make_step13a_result(request, now=clock.current, session=1, delay_seconds=60)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2, max_total_intersession_sleep_seconds=30),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=runner,
        )
        self.assertEqual(result["supervisor_summary"]["stop_reason"], "intersession_sleep_budget_reached")
        self.assertEqual(clock.sleeps, [])

    def test_parent_hash_or_lineage_tamper_fails_closed(self) -> None:
        for mutation in ("hash", "lineage"):
            clock = FakeClock()

            def runner(request, **kwargs):
                result = make_step13a_result(request, now=clock.current, session=1)
                if mutation == "hash":
                    result["latest_board"]["available"] = False
                else:
                    result["lineage"]["step12d_frozen_sha"] = "0" * 40
                    surface = {
                        key: deepcopy(value)
                        for key, value in result.items()
                        if key not in {"generated_at_utc", "scheduler_content_sha256"}
                    }
                    result["scheduler_content_sha256"] = supervisor._canonical_hash(surface)
                return result

            with self.subTest(mutation=mutation), self.assertRaises(supervisor.WNBAStep13RuntimeSupervisorIntegrityError):
                supervisor.run_step13b_runtime_supervisor(
                    self.request(), env=safe_env(), clock=clock.now, sleeper=clock.sleep, step13a_runner=runner
                )

    def test_real_frozen_step13a_boundary_preserves_rollover_reset(self) -> None:
        clock = FakeClock(datetime(2026, 8, 29, 3, 59, tzinfo=timezone.utc))
        step12c_calls: list[dict] = []

        def step12c_runner(request, **kwargs):
            step12c_calls.append(deepcopy(request))
            tick = len(step12c_calls)
            return make_step12c_result(request, tick=tick, delay_seconds=120 if tick == 1 else 60)

        result = supervisor.run_step13b_runtime_supervisor(
            self.request(max_supervisor_sessions=2, rollover_policy="advance_reset"),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step12c_runner=step12c_runner,
        )
        self.assertEqual(len(step12c_calls), 2)
        self.assertEqual([c["slate_date"] for c in step12c_calls], ["2026-08-28", "2026-08-29"])
        self.assertIsNone(step12c_calls[0]["previous_state"])
        self.assertIsNone(step12c_calls[1]["previous_state"])
        self.assertEqual(result["session_history"][0]["executed_ticks"], 1)
        self.assertEqual(result["session_history"][1]["executed_ticks"], 1)

    def test_guardrails_keep_runtime_foreground_nonpersistent_and_nonproduction(self) -> None:
        clock = FakeClock()
        result = supervisor.run_step13b_runtime_supervisor(
            self.request(),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13a_runner=lambda request, **kwargs: make_step13a_result(
                request, now=clock.current, session=1
            ),
        )
        guards = result["guardrails"]
        self.assertTrue(guards["foreground_runtime_supervisor_started"])
        self.assertTrue(guards["graceful_shutdown_hook_supported"])
        self.assertTrue(guards["slate_rollover_protected"])
        self.assertFalse(guards["cross_slate_controller_state_reuse"])
        self.assertFalse(guards["background_daemon_started"])
        self.assertFalse(guards["background_thread_spawned"])
        self.assertFalse(guards["state_persisted"])
        self.assertFalse(guards["supabase_mutated"])
        self.assertFalse(guards["production_runtime_enabled"])
        self.assertFalse(guards["wager_action_performed"])
        self.assertTrue(guards["persistence_deferred_to_step14"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
