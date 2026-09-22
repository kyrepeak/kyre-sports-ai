import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.wnba_step6k_activation_preflight as s


class Step6KActivationPreflightTests(unittest.TestCase):
    def canary_status(
        self,
        *,
        completed=True,
        feed_sha="a" * 64,
        marker_sha="a" * 64,
        persistent_sha="b" * 64,
        rollback_verified=True,
        canary_enabled=False,
        direct_enabled=False,
        reconciled_enabled=False,
        feed_exists=True,
    ):
        state = None
        if completed:
            state = {
                "activation_id": "step6j-test-001",
                "status": "completed",
                "date": "2026-08-27",
                "season": 2026,
                "completed_at_utc": "2026-08-27T03:00:00+00:00",
                "post_write_sha256": marker_sha,
                "verified_persistent_feed_sha256": persistent_sha,
                "offer_side_count": 8,
                "rollback_verified": rollback_verified,
            }
        return {
            "canary_enabled": canary_enabled,
            "direct_sync_enabled": direct_enabled,
            "reconciled_sync_enabled": reconciled_enabled,
            "production_runtime_enabled": False,
            "feed_exists": feed_exists,
            "feed_content_sha256": feed_sha if feed_exists else None,
            "canary_state": state,
        }

    def step5w(self, *, activation=False, checkpoint=True, live=False):
        return {
            "phase": "active_gate_ready" if live else "pre_activation_checkpoint_ready",
            "activation_requested": activation,
            "checkpoint_ready": checkpoint,
            "live_cycle_allowed": live,
            "activation_checkpoint_sha256": "c" * 64,
            "approved_checkpoint_sha256": "c" * 64 if activation else None,
        }

    def report(self, canary, gate):
        with patch.object(s, "get_step6j_canary_status", return_value=canary), patch.object(
            s, "get_staging_activation_gate", return_value=gate
        ):
            return s.get_step6k_activation_preflight()

    def test_01_missing_step6j_canary_blocks_preactivation(self):
        report = self.report(self.canary_status(completed=False, feed_exists=False), self.step5w())
        self.assertFalse(report["step6j_verified"])
        self.assertFalse(report["preactivation_ready"])
        self.assertFalse(report["scheduler_authorized"])
        self.assertIsNone(report["activation_checkpoint_sha256"])
        self.assertTrue(any("step_6j_canary_completed" in item for item in report["blocking_reasons"]))

    def test_02_step6j_hash_mismatch_blocks_activation(self):
        report = self.report(
            self.canary_status(feed_sha="1" * 64, marker_sha="2" * 64),
            self.step5w(activation=True, checkpoint=False, live=True),
        )
        self.assertFalse(report["step6j_verified"])
        self.assertFalse(report["scheduler_authorized"])
        self.assertTrue(any("step_6j_durable_bytes_still_match" in item for item in report["blocking_reasons"]))

    def test_03_step6j_temporary_switch_left_on_blocks_activation(self):
        report = self.report(
            self.canary_status(direct_enabled=True),
            self.step5w(activation=True, checkpoint=False, live=True),
        )
        self.assertFalse(report["step6j_verified"])
        self.assertFalse(report["scheduler_authorized"])
        self.assertTrue(any("step_6j_temporary_write_gates_closed" in item for item in report["blocking_reasons"]))

    def test_04_verified_canary_and_step5w_checkpoint_make_preactivation_ready_only(self):
        report = self.report(self.canary_status(), self.step5w(activation=False, checkpoint=True, live=False))
        self.assertTrue(report["step6j_verified"])
        self.assertTrue(report["preactivation_ready"])
        self.assertFalse(report["scheduler_authorized"])
        self.assertEqual("post_canary_preactivation_ready", report["phase"])
        self.assertEqual(64, len(report["activation_checkpoint_sha256"]))

    def test_05_verified_canary_plus_step5w_live_gate_authorizes_scheduler(self):
        report = self.report(
            self.canary_status(),
            self.step5w(activation=True, checkpoint=False, live=True),
        )
        self.assertTrue(report["step6j_verified"])
        self.assertTrue(report["scheduler_authorized"])
        self.assertEqual("scheduler_authorized", report["phase"])

    def test_06_require_helper_fails_closed(self):
        with patch.object(s, "get_step6j_canary_status", return_value=self.canary_status(completed=False, feed_exists=False)), patch.object(
            s, "get_staging_activation_gate", return_value=self.step5w(activation=True, checkpoint=False, live=True)
        ):
            with self.assertRaises(s.WNBAStep6KActivationNotReadyError):
                s.require_step6k_scheduler_authorized()

    def test_07_plan_keeps_paid_hosting_deferred_without_canary(self):
        with patch.object(s, "get_step6j_canary_status", return_value=self.canary_status(completed=False, feed_exists=False)), patch.object(
            s, "get_staging_activation_gate", return_value=self.step5w()
        ):
            plan = s.build_step6k_activation_plan()
        self.assertFalse(plan["scheduler_authorized"])
        self.assertFalse(plan["steps"][0]["complete"])
        self.assertIn("deferred", plan["steps"][0]["note"].lower())

    def test_08_api_is_get_only_and_read_only(self):
        import sports_api.api.wnba_step6k_activation_preflight as api
        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        with patch.object(api, "get_step6k_activation_preflight", return_value={"scheduler_authorized": False}), patch.object(
            api, "build_step6k_activation_plan", return_value={"scheduler_authorized": False, "steps": []}
        ):
            preflight = client.get("/api/v1/wnba/runtime/step6k-preflight")
            plan = client.get("/api/v1/wnba/runtime/step6k-plan")
            post = client.post("/api/v1/wnba/runtime/step6k-preflight")
        self.assertEqual(200, preflight.status_code)
        self.assertEqual(200, plan.status_code)
        self.assertEqual(405, post.status_code)

    def test_09_scheduler_transport_does_not_start_worker_when_step6k_blocked(self):
        import sports_api.api.wnba_pregame_board_scheduler_staging_activation as transport
        blocked = {
            "activation_requested": True,
            "scheduler_authorized": False,
            "phase": "activation_blocked",
            "blocking_reasons": ["step_6j_canary_completed: missing"],
            "step_5w": {"live_cycle_allowed": True},
        }
        transport._stop_worker()
        with patch.object(transport, "get_step6k_activation_preflight", return_value=blocked), patch.object(
            transport.step5q, "get_scheduler_configuration"
        ) as scheduler_config:
            transport._start_worker()
        scheduler_config.assert_not_called()
        self.assertIsNone(transport._worker_thread)
        self.assertFalse(transport._worker_state["thread_running"])
        self.assertFalse(transport._worker_state["startup_step6k_scheduler_authorized"])

    def test_10_manual_refresh_cannot_bypass_step6k(self):
        import sports_api.api.wnba_pregame_board_scheduler_staging_activation as transport
        with patch.object(
            transport,
            "require_step6k_scheduler_authorized",
            side_effect=s.WNBAStep6KActivationNotReadyError("blocked"),
        ), patch.object(transport.step5q, "refresh_current_wnba_player_prop_board") as refresh:
            with self.assertRaises(Exception) as caught:
                transport.refresh_current_wnba_player_prop_board(date="2026-08-27", season=2026)
        refresh.assert_not_called()
        self.assertEqual(503, getattr(caught.exception, "status_code", None))


if __name__ == "__main__":
    unittest.main()
