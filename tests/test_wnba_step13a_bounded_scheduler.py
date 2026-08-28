from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from sports_api import wnba_step12_release_freeze as release
from sports_api import wnba_step12c_live_board_runtime as step12c
from sports_api import wnba_step13a_bounded_scheduler as scheduler


BASE = datetime(2026, 8, 28, 16, 40, tzinfo=timezone.utc)


def safe_env() -> dict[str, str]:
    return {
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


class SequenceClock:
    def __init__(self, values: list[datetime]) -> None:
        self.values = list(values)
        self.last = values[-1]

    def now(self) -> datetime:
        if self.values:
            self.last = self.values.pop(0)
        return self.last


def make_parent_result(
    request: dict,
    *,
    tick: int = 1,
    delay_seconds: int = 60,
    board_available: bool = True,
    circuit_state: str = "closed",
) -> dict:
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
            "circuit_state": circuit_state,
            "consecutive_failures": 0,
            "next_refresh_due_at_utc": next_due.isoformat(),
            "circuit_open_until_utc": next_due.isoformat() if circuit_state == "open" else None,
            "controller_state_content_sha256": state["state_content_sha256"],
        },
        "board": {
            "available": board_available,
            "requested_top_card_count": 5,
            "qualified_prop_count": 1 if board_available else 0,
            "top_card_count": 1 if board_available else 0,
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
    result["board_content_sha256"] = scheduler._canonical_hash(surface)
    return result


class Tests(unittest.TestCase):
    def request(self, **kwargs) -> dict:
        params = {
            "season": 2026,
            "slate_date": "2026-08-28",
            "max_cycles": 1,
            "max_total_sleep_seconds": 3600,
        }
        params.update(kwargs)
        return scheduler.build_step13a_request(**params)

    def test_default_off_and_frozen_parent(self) -> None:
        self.assertFalse(scheduler.DEFAULT_ENABLED)
        self.assertFalse(scheduler.step13a_bounded_scheduler_enabled({}))
        self.assertEqual(
            scheduler.STEP12D_FROZEN_SHA,
            "48517bac86ee3f55aa4c21d6caba06c41a0a7d60",
        )
        self.assertTrue(scheduler.FOREGROUND_BOUNDED_SCHEDULER_ALLOWED)
        self.assertFalse(scheduler.BACKGROUND_DAEMON_ALLOWED)

    def test_requires_step13_gate(self) -> None:
        env = safe_env()
        env.pop("WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED")
        with self.assertRaises(scheduler.WNBAStep13BoundedSchedulerDisabledError):
            scheduler.run_step13a_bounded_scheduler(self.request(), env=env, step12c_runner=lambda *a, **k: {})

    def test_requires_frozen_step12_gates(self) -> None:
        for key in (
            "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
            "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
            "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
        ):
            env = safe_env()
            env[key] = "false"
            with self.subTest(key=key), self.assertRaises(
                scheduler.WNBAStep13BoundedSchedulerDisabledError
            ):
                scheduler.run_step13a_bounded_scheduler(
                    self.request(), env=env, step12c_runner=lambda *a, **k: {}
                )

    def test_refuses_legacy_production_scheduler_persistence_switches(self) -> None:
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
            with self.subTest(key=key), self.assertRaises(
                scheduler.WNBAStep13BoundedSchedulerDisabledError
            ):
                scheduler.run_step13a_bounded_scheduler(
                    self.request(), env=env, step12c_runner=lambda *a, **k: {}
                )

    def test_request_hash_tamper_detected(self) -> None:
        request = self.request()
        request["max_cycles"] = 2
        with self.assertRaises(scheduler.WNBAStep13BoundedSchedulerIntegrityError):
            scheduler.run_step13a_bounded_scheduler(
                request, env=safe_env(), step12c_runner=lambda *a, **k: {}
            )

    def test_unknown_request_field_fails_closed(self) -> None:
        request = self.request()
        request["surprise"] = True
        request["request_content_sha256"] = scheduler._canonical_hash(
            {key: value for key, value in request.items() if key != "request_content_sha256"}
        )
        with self.assertRaises(scheduler.WNBAStep13BoundedSchedulerInputError):
            scheduler.run_step13a_bounded_scheduler(
                request, env=safe_env(), step12c_runner=lambda *a, **k: {}
            )

    def test_one_cycle_calls_parent_once_without_sleep(self) -> None:
        clock = FakeClock()
        calls: list[dict] = []

        def runner(request, **kwargs):
            calls.append(deepcopy(request))
            return make_parent_result(request, tick=1)

        result = scheduler.run_step13a_bounded_scheduler(
            self.request(max_cycles=1),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step12c_runner=runner,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(result["scheduler_summary"]["executed_ticks"], 1)
        self.assertEqual(result["scheduler_summary"]["stop_reason"], "max_cycles_reached")

    def test_three_cycles_chain_state_and_sleep_to_due(self) -> None:
        clock = FakeClock()
        calls: list[dict] = []

        def runner(request, **kwargs):
            calls.append(deepcopy(request))
            tick = len(calls)
            if tick == 1:
                self.assertIsNone(request["previous_state"])
            else:
                self.assertEqual(request["previous_state"]["tick"], tick - 1)
            return make_parent_result(request, tick=tick, delay_seconds=60)

        result = scheduler.run_step13a_bounded_scheduler(
            self.request(max_cycles=3, max_total_sleep_seconds=180),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step12c_runner=runner,
        )
        self.assertEqual(len(calls), 3)
        self.assertEqual(clock.sleeps, [60.0, 60.0])
        self.assertEqual(result["scheduler_summary"]["total_sleep_seconds"], 120.0)
        self.assertEqual(result["final_controller_state_for_next_process"]["tick"], 3)

    def test_sleep_budget_stops_before_second_tick(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            return make_parent_result(request, tick=calls, delay_seconds=60)

        result = scheduler.run_step13a_bounded_scheduler(
            self.request(max_cycles=3, max_total_sleep_seconds=30),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step12c_runner=runner,
        )
        self.assertEqual(calls, 1)
        self.assertEqual(clock.sleeps, [])
        self.assertEqual(result["status"], "bounded_stop")
        self.assertEqual(result["scheduler_summary"]["stop_reason"], "sleep_budget_reached")

    def test_circuit_cooldown_due_time_drives_sleep(self) -> None:
        clock = FakeClock()
        calls = 0

        def runner(request, **kwargs):
            nonlocal calls
            calls += 1
            return make_parent_result(
                request,
                tick=calls,
                delay_seconds=180 if calls == 1 else 60,
                circuit_state="open" if calls == 1 else "closed",
            )

        result = scheduler.run_step13a_bounded_scheduler(
            self.request(max_cycles=2, max_total_sleep_seconds=180),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step12c_runner=runner,
        )
        self.assertEqual(calls, 2)
        self.assertEqual(clock.sleeps, [180.0])
        self.assertEqual(result["tick_history"][0]["circuit_state"], "open")

    def test_parent_hash_tamper_rejected(self) -> None:
        def runner(request, **kwargs):
            result = make_parent_result(request)
            result["board"]["top_card_count"] = 9
            return result

        with self.assertRaises(scheduler.WNBAStep13BoundedSchedulerIntegrityError):
            scheduler.run_step13a_bounded_scheduler(
                self.request(), env=safe_env(), clock=FakeClock().now, step12c_runner=runner
            )

    def test_wrong_parent_slate_or_type_rejected(self) -> None:
        for mutation in ("slate", "type"):
            def runner(request, **kwargs):
                result = make_parent_result(request)
                if mutation == "slate":
                    result["slate_date"] = "2026-08-27"
                else:
                    result["data_type"] = "wrong"
                surface = {
                    key: deepcopy(value)
                    for key, value in result.items()
                    if key not in {"generated_at_utc", "board_content_sha256"}
                }
                result["board_content_sha256"] = scheduler._canonical_hash(surface)
                return result

            with self.subTest(mutation=mutation), self.assertRaises(
                scheduler.WNBAStep13BoundedSchedulerIntegrityError
            ):
                scheduler.run_step13a_bounded_scheduler(
                    self.request(), env=safe_env(), clock=FakeClock().now, step12c_runner=runner
                )

    def test_clock_reversal_rejected(self) -> None:
        clock = SequenceClock([
            BASE,
            BASE,
            BASE - timedelta(seconds=1),
        ])

        def runner(request, **kwargs):
            return make_parent_result(request, delay_seconds=60)

        with self.assertRaises(scheduler.WNBAStep13BoundedSchedulerIntegrityError):
            scheduler.run_step13a_bounded_scheduler(
                self.request(max_cycles=2),
                env=safe_env(),
                clock=clock.now,
                sleeper=lambda seconds: None,
                step12c_runner=runner,
            )

    def test_scheduler_guardrails_keep_persistence_and_background_off(self) -> None:
        clock = FakeClock()
        result = scheduler.run_step13a_bounded_scheduler(
            self.request(),
            env=safe_env(),
            clock=clock.now,
            sleeper=clock.sleep,
            step12c_runner=lambda request, **kwargs: make_parent_result(request),
        )
        guards = result["guardrails"]
        self.assertTrue(guards["bounded_foreground_scheduler_started"])
        self.assertTrue(guards["controller_state_carried_forward_in_memory"])
        self.assertFalse(guards["background_daemon_started"])
        self.assertFalse(guards["state_persisted"])
        self.assertFalse(guards["supabase_mutated"])
        self.assertFalse(guards["production_runtime_enabled"])
        self.assertFalse(guards["wager_action_performed"])
        self.assertTrue(guards["persistence_deferred_to_step14"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
