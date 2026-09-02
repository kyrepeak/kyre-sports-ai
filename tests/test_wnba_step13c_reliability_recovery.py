from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from sports_api import wnba_step13a_bounded_scheduler as step13a
from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as recovery


BASE = datetime(2026, 8, 28, 16, 55, tzinfo=timezone.utc)


def safe_env() -> dict[str, str]:
    return {
        "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED": "true",
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


def supervisor_request(**kwargs) -> dict:
    params = {
        "season": 2026,
        "initial_slate_date": "2026-08-28",
        "rollover_policy": "stop",
        "max_supervisor_sessions": 1,
        "max_supervisor_runtime_seconds": 600,
        "max_total_intersession_sleep_seconds": 0,
        "scheduler_cycles_per_session": 1,
        "scheduler_sleep_budget_seconds_per_session": 0,
    }
    params.update(kwargs)
    return step13b.build_step13b_request(**params)


def step13c_request(**kwargs) -> dict:
    parent = kwargs.pop("supervisor_request", supervisor_request())
    params = {
        "supervisor_request": parent,
        "max_recovery_attempts": 3,
        "base_recovery_backoff_seconds": 2,
        "max_total_recovery_sleep_seconds": 30,
    }
    params.update(kwargs)
    return recovery.build_step13c_request(**params)


def make_supervisor_result(request: dict, *, health: str = "healthy") -> dict:
    state = {
        "data_type": "wnba_step11e_controlled_automation_state",
        "state_content_sha256": "7" * 64,
        "next_refresh_due_at_utc": (BASE + timedelta(seconds=60)).isoformat(),
    }
    result = {
        "data_type": "wnba_step13b_runtime_supervisor_response",
        "schema_version": step13b.SCHEMA_VERSION,
        "source": "test",
        "model_version": step13b.MODEL_VERSION,
        "generated_at_utc": BASE.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "stopped",
        "health": health,
        "active_slate_date": request["initial_slate_date"],
        "supervisor_summary": {
            "requested_max_sessions": 1,
            "completed_sessions": 1,
            "stop_reason": "max_sessions_reached",
            "started_at_utc": BASE.isoformat(),
            "ended_at_utc": BASE.isoformat(),
        },
        "lifecycle": [],
        "session_history": [],
        "rollover_history": [],
        "latest_scheduler": None,
        "final_controller_state_for_restart_handoff": state,
        "lineage": {
            "step13a_frozen_sha": recovery.STEP13A_FROZEN_SHA,
            "latest_step13a_scheduler_content_sha256": "6" * 64,
            "step12d_frozen_sha": recovery.STEP12D_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "foreground_runtime_supervisor_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "step13a_scheduler_reused_without_modification": True,
            "frozen_controller_owns_refresh_cadence": True,
            "intersession_wait_uses_frozen_next_refresh_due": True,
            "graceful_shutdown_hook_supported": True,
            "slate_rollover_protected": True,
            "cross_slate_controller_state_reuse": False,
            "advance_rollover_resets_controller_state": True,
            "state_carried_forward_in_memory": True,
            "state_persisted": False,
            "process_restart_state_recovery_available": False,
            "persistence_deferred_to_step14": True,
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
        if key not in {"generated_at_utc", "supervisor_content_sha256"}
    }
    result["supervisor_content_sha256"] = recovery._canonical_hash(surface)
    return result


def make_step13a_result(request: dict) -> dict:
    now = BASE
    next_due = now + timedelta(seconds=60)
    state = {
        "data_type": "wnba_step11e_controlled_automation_state",
        "state_content_sha256": "8" * 64,
        "next_refresh_due_at_utc": next_due.isoformat(),
    }
    result = {
        "data_type": "wnba_step13a_bounded_scheduler_response",
        "schema_version": step13a.SCHEMA_VERSION,
        "source": "test frozen Step13A fixture",
        "model_version": step13a.MODEL_VERSION,
        "generated_at_utc": now.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "completed",
        "health": "healthy",
        "slate_date": request["slate_date"],
        "scheduler_summary": {
            "requested_cycles": 1,
            "executed_ticks": 1,
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
            "next_refresh_due_at_utc": next_due.isoformat(),
            "circuit_state": "closed",
        },
        "final_controller_state_for_next_process": state,
        "lineage": {
            "step12d_frozen_sha": recovery.STEP12D_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "bounded_foreground_scheduler_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "one_step12c_call_per_scheduler_tick": True,
            "frozen_controller_owns_refresh_cadence": True,
            "sleep_until_frozen_next_refresh_due": True,
            "controller_state_carried_forward_in_memory": True,
            "state_persisted": False,
            "process_restart_state_recovery_available": False,
            "persistence_deferred_to_step14": True,
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
    result["scheduler_content_sha256"] = recovery._canonical_hash(surface)
    return result


class Tests(unittest.TestCase):
    def test_default_off_and_frozen_parent(self) -> None:
        self.assertFalse(recovery.DEFAULT_ENABLED)
        self.assertFalse(recovery.step13c_reliability_recovery_enabled({}))
        self.assertEqual(
            recovery.STEP13B_FROZEN_SHA,
            "0a0e4381d0a4deac6bbd3741f893214e99afef7b",
        )
        self.assertEqual(
            recovery.STEP13A_FROZEN_SHA,
            "eaa744ae097a94d5f54c490ab13ca7d66bb725c2",
        )
        self.assertTrue(recovery.PROCESS_LOCAL_ACTIVE_RUN_LEASE_ALLOWED)
        self.assertFalse(recovery.DURABLE_DISTRIBUTED_LEASE_ALLOWED)

    def test_requires_step13c_gate(self) -> None:
        env = safe_env()
        env["WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED"] = "false"
        with self.assertRaises(recovery.WNBAStep13ReliabilityDisabledError):
            recovery.run_step13c_reliability_recovery(step13c_request(), env=env)

    def test_requires_frozen_parent_gates(self) -> None:
        for key in (
            "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
            "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
            "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
            "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
            "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
        ):
            env = safe_env()
            env[key] = "false"
            with self.subTest(key=key), self.assertRaises(
                recovery.WNBAStep13ReliabilityDisabledError
            ):
                recovery.run_step13c_reliability_recovery(step13c_request(), env=env)

    def test_refuses_unsafe_external_switches(self) -> None:
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        ):
            env = safe_env()
            env[key] = "true"
            with self.subTest(key=key), self.assertRaises(
                recovery.WNBAStep13ReliabilityDisabledError
            ):
                recovery.run_step13c_reliability_recovery(step13c_request(), env=env)

    def test_request_hash_tamper_detected(self) -> None:
        request = step13c_request()
        request["max_recovery_attempts"] = 2
        with self.assertRaises(recovery.WNBAStep13ReliabilityIntegrityError):
            recovery.run_step13c_reliability_recovery(request, env=safe_env())

    def test_nested_supervisor_request_hash_tamper_detected(self) -> None:
        request = step13c_request()
        request["supervisor_request"]["max_supervisor_sessions"] = 2
        request["request_content_sha256"] = recovery._canonical_hash(
            {k: v for k, v in request.items() if k != "request_content_sha256"}
        )
        with self.assertRaises(recovery.WNBAStep13ReliabilityIntegrityError):
            recovery.run_step13c_reliability_recovery(request, env=safe_env())

    def test_run_identity_tamper_detected(self) -> None:
        request = step13c_request()
        request["run_identity_sha256"] = "0" * 64
        request["request_content_sha256"] = recovery._canonical_hash(
            {k: v for k, v in request.items() if k != "request_content_sha256"}
        )
        with self.assertRaises(recovery.WNBAStep13ReliabilityIntegrityError):
            recovery.run_step13c_reliability_recovery(request, env=safe_env())

    def test_unknown_request_field_fails_closed(self) -> None:
        request = step13c_request()
        request["surprise"] = True
        request["request_content_sha256"] = recovery._canonical_hash(
            {k: v for k, v in request.items() if k != "request_content_sha256"}
        )
        with self.assertRaises(recovery.WNBAStep13ReliabilityInputError):
            recovery.run_step13c_reliability_recovery(request, env=safe_env())

    def test_success_calls_parent_once_without_recovery_sleep(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            return make_supervisor_result(request)

        result = recovery.run_step13c_reliability_recovery(
            step13c_request(),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13b_runner=runner,
            active_run_registry=set(),
        )
        self.assertEqual(calls, 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recovery_summary"]["successful_attempt"], 1)

    def test_timeout_then_success_uses_exponential_recovery_backoff(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("synthetic timeout")
            return make_supervisor_result(request)

        result = recovery.run_step13c_reliability_recovery(
            step13c_request(base_recovery_backoff_seconds=2),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13b_runner=runner,
            active_run_registry=set(),
        )
        self.assertEqual(calls, 2)
        self.assertEqual(clock.sleeps, [2.0])
        self.assertEqual(result["recovery_summary"]["recoverable_failures"], 1)
        self.assertEqual(result["recovery_summary"]["successful_attempt"], 2)

    def test_connection_error_then_success_is_recoverable(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("synthetic disconnect")
            return make_supervisor_result(request)

        result = recovery.run_step13c_reliability_recovery(
            step13c_request(base_recovery_backoff_seconds=1),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13b_runner=runner,
            active_run_registry=set(),
        )
        self.assertEqual(calls, 2)
        self.assertEqual(clock.sleeps, [1.0])
        self.assertEqual(result["attempt_history"][0]["error_type"], "ConnectionError")

    def test_transport_failure_exhaustion_returns_no_fake_supervisor(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            raise TimeoutError("still down")

        result = recovery.run_step13c_reliability_recovery(
            step13c_request(max_recovery_attempts=3, base_recovery_backoff_seconds=1),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13b_runner=runner,
            active_run_registry=set(),
        )
        self.assertEqual(calls, 3)
        self.assertEqual(clock.sleeps, [1.0, 2.0])
        self.assertEqual(result["status"], "recovery_exhausted")
        self.assertEqual(result["health"], "failed")
        self.assertIsNone(result["latest_supervisor"])
        self.assertEqual(result["recovery_summary"]["recoverable_failures"], 3)

    def test_recovery_sleep_budget_stops_before_next_attempt(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            raise TimeoutError("down")

        result = recovery.run_step13c_reliability_recovery(
            step13c_request(
                max_recovery_attempts=5,
                base_recovery_backoff_seconds=4,
                max_total_recovery_sleep_seconds=3,
            ),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13b_runner=runner,
            active_run_registry=set(),
        )
        self.assertEqual(calls, 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(
            result["recovery_summary"]["stop_reason"],
            "recovery_sleep_budget_reached",
        )

    def test_frozen_parent_errors_are_never_retried(self) -> None:
        for error in (
            step13b.WNBAStep13RuntimeSupervisorIntegrityError("integrity"),
            step13b.WNBAStep13RuntimeSupervisorInputError("input"),
            step13b.WNBAStep13RuntimeSupervisorDisabledError("disabled"),
        ):
            calls = 0

            def runner(request, **kwargs):
                nonlocal calls
                calls += 1
                raise error

            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                recovery.run_step13c_reliability_recovery(
                    step13c_request(),
                    env=safe_env(),
                    clock=FakeClock().now,
                    step13b_runner=runner,
                    active_run_registry=set(),
                )
            self.assertEqual(calls, 1)

    def test_unknown_runtime_error_fails_closed_without_retry(self) -> None:
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            raise RuntimeError("unknown")

        with self.assertRaises(recovery.WNBAStep13ReliabilityFatalError):
            recovery.run_step13c_reliability_recovery(
                step13c_request(),
                env=safe_env(),
                clock=FakeClock().now,
                step13b_runner=runner,
                active_run_registry=set(),
            )
        self.assertEqual(calls, 1)

    def test_duplicate_active_run_is_rejected_process_locally(self) -> None:
        request = step13c_request()
        registry = {request["run_identity_sha256"]}
        with self.assertRaises(recovery.WNBAStep13DuplicateRunError):
            recovery.run_step13c_reliability_recovery(
                request,
                env=safe_env(),
                clock=FakeClock().now,
                step13b_runner=lambda request, **kwargs: make_supervisor_result(request),
                active_run_registry=registry,
            )
        self.assertIn(request["run_identity_sha256"], registry)

    def test_active_run_lease_is_released_after_fatal_failure(self) -> None:
        request = step13c_request()
        registry: set[str] = set()
        with self.assertRaises(recovery.WNBAStep13ReliabilityFatalError):
            recovery.run_step13c_reliability_recovery(
                request,
                env=safe_env(),
                clock=FakeClock().now,
                step13b_runner=lambda request, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
                active_run_registry=registry,
            )
        self.assertNotIn(request["run_identity_sha256"], registry)

    def test_parent_result_hash_or_lineage_tamper_is_rejected(self) -> None:
        for mutation in ("hash", "lineage"):
            def runner(request, **kwargs):
                result = make_supervisor_result(request)
                if mutation == "hash":
                    result["health"] = "tampered"
                else:
                    result["lineage"]["step13a_frozen_sha"] = "0" * 40
                    surface = {
                        key: deepcopy(value)
                        for key, value in result.items()
                        if key not in {"generated_at_utc", "supervisor_content_sha256"}
                    }
                    result["supervisor_content_sha256"] = recovery._canonical_hash(surface)
                return result

            with self.subTest(mutation=mutation), self.assertRaises(
                recovery.WNBAStep13ReliabilityIntegrityError
            ):
                recovery.run_step13c_reliability_recovery(
                    step13c_request(),
                    env=safe_env(),
                    clock=FakeClock().now,
                    step13b_runner=runner,
                    active_run_registry=set(),
                )

    def test_real_frozen_step13b_boundary_is_preserved(self) -> None:
        clock = FakeClock()
        calls = 0

        def fake_step13a(request, **kwargs):
            nonlocal calls
            calls += 1
            return make_step13a_result(request)

        result = recovery.run_step13c_reliability_recovery(
            step13c_request(supervisor_request=supervisor_request()),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step13b_runner=step13b.run_step13b_runtime_supervisor,
            step13a_runner=fake_step13a,
            active_run_registry=set(),
        )
        self.assertEqual(calls, 1)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["latest_supervisor"]["lineage"]["step13a_frozen_sha"],
            recovery.STEP13A_FROZEN_SHA,
        )

    def test_guardrails_keep_recovery_read_only_nonpersistent_and_nonproduction(self) -> None:
        result = recovery.run_step13c_reliability_recovery(
            step13c_request(),
            env=safe_env(),
            clock=FakeClock().now,
            step13b_runner=lambda request, **kwargs: make_supervisor_result(request),
            active_run_registry=set(),
        )
        guards = result["guardrails"]
        self.assertTrue(guards["process_local_duplicate_run_guard"])
        self.assertTrue(guards["bounded_recovery_attempts"])
        self.assertTrue(guards["recovery_only_for_timeout_or_connection_error"])
        self.assertTrue(guards["frozen_refresh_cadence_unchanged"])
        self.assertFalse(guards["cross_process_duplicate_run_guard"])
        self.assertFalse(guards["durable_distributed_lease_used"])
        self.assertFalse(guards["state_persisted"])
        self.assertFalse(guards["durable_restart_recovery_available"])
        self.assertFalse(guards["supabase_mutated"])
        self.assertFalse(guards["production_runtime_enabled"])
        self.assertFalse(guards["wager_action_performed"])
        self.assertTrue(guards["persistence_deferred_to_step14"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
