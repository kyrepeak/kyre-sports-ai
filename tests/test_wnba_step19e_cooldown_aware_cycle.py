from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sports_api import wnba_step17b_always_on_runtime as step17b
from sports_api import wnba_step19e_cooldown_aware_cycle as step19e


class Step19ECooldownAwareCycleTests(unittest.TestCase):
    def test_future_open_circuit_waits_past_open_until(self):
        now = datetime(2026, 8, 29, 19, 33, 35, tzinfo=timezone.utc)
        checkpoint = {
            "circuit_state": "open",
            "circuit_open_until_utc": (now + timedelta(seconds=2)).isoformat(),
        }
        wait = step19e._cooldown_wait_seconds(checkpoint, now=now)
        self.assertAlmostEqual(wait, 3.0, places=6)

    def test_expired_open_circuit_does_not_wait(self):
        now = datetime(2026, 8, 29, 19, 33, 40, tzinfo=timezone.utc)
        checkpoint = {
            "circuit_state": "open",
            "circuit_open_until_utc": (now - timedelta(seconds=1)).isoformat(),
        }
        self.assertEqual(step19e._cooldown_wait_seconds(checkpoint, now=now), 0.0)

    def test_closed_circuit_does_not_wait(self):
        now = datetime(2026, 8, 29, 19, 33, 35, tzinfo=timezone.utc)
        checkpoint = {
            "circuit_state": "closed",
            "circuit_open_until_utc": (now + timedelta(seconds=30)).isoformat(),
        }
        self.assertEqual(step19e._cooldown_wait_seconds(checkpoint, now=now), 0.0)

    def test_stop_request_interrupts_wait(self):
        stop_calls = [False, True]

        def stop_requested():
            return stop_calls.pop(0) if stop_calls else True

        sleeps = []
        completed = step19e._wait_interruptibly(
            5.0,
            stop_requested=stop_requested,
            sleeper=lambda seconds: sleeps.append(seconds),
        )
        self.assertFalse(completed)
        self.assertEqual(len(sleeps), 1)
        self.assertLessEqual(sleeps[0], step19e.WAIT_POLL_SECONDS)

    def test_wrapper_waits_then_calls_original_once(self):
        checkpoint = {
            "circuit_state": "open",
            "circuit_open_until_utc": "2099-01-01T00:00:00+00:00",
        }
        original_result = {"status": "completed", "saved_checkpoint_version": 99}
        calls = []

        def original(**kwargs):
            calls.append(kwargs)
            return original_result

        with patch.object(step19e, "_load_controller_checkpoint", return_value=checkpoint), \
             patch.object(step19e, "_cooldown_wait_seconds", return_value=2.5), \
             patch.object(step19e, "_wait_interruptibly", return_value=True) as wait_mock, \
             patch.object(step19e, "_ORIGINAL_RUN_ONE_CYCLE", side_effect=original):
            result = step19e.run_one_cycle_step19e(
                env={"WNBA_STEP17B_ALWAYS_ON_ENABLED": "true"},
                owner_id="test-owner",
                slate_date="2026-08-29",
                stop_requested=lambda: False,
            )

        self.assertEqual(result, original_result)
        wait_mock.assert_called_once()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["owner_id"], "test-owner")
        self.assertEqual(calls[0]["slate_date"], "2026-08-29")

    def test_wrapper_does_not_wait_when_checkpoint_closed(self):
        checkpoint = {"circuit_state": "closed", "circuit_open_until_utc": None}
        original_result = {"status": "completed"}
        with patch.object(step19e, "_load_controller_checkpoint", return_value=checkpoint), \
             patch.object(step19e, "_cooldown_wait_seconds", return_value=0.0), \
             patch.object(step19e, "_wait_interruptibly") as wait_mock, \
             patch.object(step19e, "_ORIGINAL_RUN_ONE_CYCLE", return_value=original_result) as original_mock:
            result = step19e.run_one_cycle_step19e(
                env={}, owner_id="test-owner", slate_date="2026-08-29"
            )
        self.assertEqual(result, original_result)
        wait_mock.assert_not_called()
        original_mock.assert_called_once()

    def test_bootstrap_installs_wrapper_without_changing_frozen_controller(self):
        step19e.install_step19e_cooldown_aware_cycle()
        self.assertIs(step17b.run_one_cycle, step19e.run_one_cycle_step19e)
        self.assertFalse(step19e.INSTALLATION["controller_state_mutated_by_preflight"])
        self.assertFalse(step19e.INSTALLATION["circuit_force_closed"])
        self.assertFalse(step19e.INSTALLATION["readiness_gates_relaxed"])
        self.assertFalse(step19e.INSTALLATION["projection_fabrication_allowed"])
        self.assertFalse(step19e.INSTALLATION["provider_logic_modified"])
        self.assertFalse(step19e.INSTALLATION["durable_lease_ownership_modified"])


if __name__ == "__main__":
    unittest.main()
