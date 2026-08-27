import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.wnba_step6m_scheduler_orchestration as s


class Step6MSchedulerOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.green6l = {
            "production_refresh_ready": True,
            "production_refresh_enabled": True,
            "market_provider_mode": "kyre",
            "global_temporary_write_switches_off": True,
            "step_6k": {
                "scheduler_authorized": True,
                "activation_checkpoint_sha256": "a" * 64,
                "step6j_verified": True,
            },
            "blocking_reasons": [],
        }
        self.blocked6l = {
            "production_refresh_ready": False,
            "production_refresh_enabled": False,
            "market_provider_mode": "kyre",
            "global_temporary_write_switches_off": True,
            "step_6k": {"scheduler_authorized": False},
            "blocking_reasons": ["step_6l_explicit_refresh_enablement: disabled"],
        }

    def test_01_status_blocks_when_step6l_is_not_ready(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.blocked6l):
            report = s.get_step6m_scheduler_orchestration_status(env={})
        self.assertFalse(report["scheduler_cycle_ready"])
        self.assertTrue(report["blocking_reasons"])

    def test_02_status_ready_only_when_step6l_is_ready(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            report = s.get_step6m_scheduler_orchestration_status(env={})
        self.assertTrue(report["scheduler_cycle_ready"])
        self.assertEqual("step_5q_distributed_cycle_lock", report["lock_order"][1])
        self.assertEqual("step_6l_owned_market_feed_refresh", report["lock_order"][2])

    def test_03_require_helper_fails_closed(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.blocked6l):
            with self.assertRaises(s.WNBAStep6MOrchestrationNotReadyError):
                s.require_step6m_scheduler_ready(env={})

    def test_04_refresh_precedes_model_and_uses_same_date(self):
        calls = []

        def refresher(**kwargs):
            calls.append(("refresh", kwargs))
            return {
                "outcome": "refreshed",
                "content_sha256": "b" * 64,
                "persistent_feed_sha256": "c" * 64,
                "offer_side_count": 20,
            }

        def cycle_runner(**kwargs):
            calls.append(("model", kwargs))
            return {"outcome": "published", "publication": {"publication_id": "pub-1"}}

        result = s._refresh_then_run_frozen_cycle(
            target_date="2026-08-27",
            season=2026,
            force=False,
            environment={"WNBA_MARKET_PROVIDER_MODE": "kyre"},
            refresher=refresher,
            cycle_runner=cycle_runner,
        )
        self.assertEqual(["refresh", "model"], [item[0] for item in calls])
        self.assertEqual("2026-08-27", calls[0][1]["date"])
        self.assertEqual("2026-08-27", calls[1][1]["date"])
        self.assertEqual(["kyre"], calls[1][1]["provider_ids"])
        self.assertTrue(result["step_6m"]["distributed_lock_owned_before_refresh"])

    def test_05_refresh_failure_prevents_model_execution(self):
        cycle = MagicMock()
        refresher = MagicMock(side_effect=s.WNBAStep6LRefreshError("synthetic refresh failure"))
        with self.assertRaises(s.WNBAStep6MOrchestrationUpstreamError):
            s._refresh_then_run_frozen_cycle(
                target_date="2026-08-27",
                season=2026,
                force=False,
                environment={},
                refresher=refresher,
                cycle_runner=cycle,
            )
        cycle.assert_not_called()

    def test_06_losing_distributed_worker_never_refreshes_or_models(self):
        refresh = MagicMock()
        cycle = MagicMock()
        skipped = {
            "outcome": "skipped_cross_process_lock",
            "provider_collection_attempted": False,
            "board_rebuild_attempted": False,
        }
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s.step5q, "_run_cycle_with_distributed_lock", return_value=skipped
        ):
            result = s.run_step6m_background_cycle(
                date="2026-08-27", season=2026, env={}, refresher=refresh, cycle_runner=cycle
            )
        refresh.assert_not_called()
        cycle.assert_not_called()
        self.assertFalse(result["step_6m"]["owned_feed_refresh_attempted"])
        self.assertFalse(result["step_6m"]["model_cycle_attempted"])

    def test_07_winning_background_worker_refreshes_then_models_once(self):
        order = []

        def refresh(**kwargs):
            order.append("refresh")
            return {"outcome": "refreshed", "content_sha256": "d" * 64}

        def cycle(**kwargs):
            order.append("model")
            return {"outcome": "published", "publication": {"publication_id": "pub-2"}}

        def own(call, *, contention_is_error):
            self.assertFalse(contention_is_error)
            return call()

        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s.step5q, "_run_cycle_with_distributed_lock", side_effect=own
        ):
            result = s.run_step6m_background_cycle(
                date="2026-08-27", season=2026, env={}, refresher=refresh, cycle_runner=cycle
            )
        self.assertEqual(["refresh", "model"], order)
        self.assertEqual("published", result["outcome"])

    def test_08_manual_provider_override_is_kyre_only(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            with self.assertRaises(ValueError):
                s.run_step6m_manual_cycle(
                    date="2026-08-27",
                    season=2026,
                    provider_ids="sportsgameodds",
                    env={},
                    refresher=MagicMock(),
                    cycle_runner=MagicMock(),
                )

    def test_09_manual_cycle_uses_distributed_lock_before_callback(self):
        refresh = MagicMock(return_value={"outcome": "refreshed", "content_sha256": "e" * 64})
        cycle = MagicMock(return_value={"outcome": "published"})
        observed = {}

        def own(call, *, contention_is_error):
            observed["contention_is_error"] = contention_is_error
            return call()

        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s.step5q, "_run_cycle_with_distributed_lock", side_effect=own
        ):
            result = s.run_step6m_manual_cycle(
                date="2026-08-27",
                season=2026,
                provider_ids="kyre",
                force=True,
                env={},
                refresher=refresh,
                cycle_runner=cycle,
            )
        self.assertTrue(observed["contention_is_error"])
        cycle.assert_called_once()
        self.assertEqual(["kyre"], cycle.call_args.kwargs["provider_ids"])
        self.assertTrue(cycle.call_args.kwargs["force"])
        self.assertEqual("published", result["outcome"])

    def test_10_none_date_is_resolved_once_for_both_operations(self):
        refresh = MagicMock(return_value={"outcome": "refreshed", "content_sha256": "f" * 64})
        cycle = MagicMock(return_value={"outcome": "published"})

        def own(call, *, contention_is_error):
            return call()

        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s, "_target_date", return_value="2026-08-27"
        ) as target, patch.object(s.step5q, "_run_cycle_with_distributed_lock", side_effect=own):
            s.run_step6m_manual_cycle(
                date=None, season=2026, env={}, refresher=refresh, cycle_runner=cycle
            )
        target.assert_called_once_with(None)
        self.assertEqual("2026-08-27", refresh.call_args.kwargs["date"])
        self.assertEqual("2026-08-27", cycle.call_args.kwargs["date"])

    def test_11_plan_keeps_step5p_and_step5q_authoritative(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            plan = s.build_step6m_scheduler_orchestration_plan(env={})
        self.assertTrue(plan["safety"]["frozen_step_5p_model_semantics_preserved"])
        self.assertTrue(plan["safety"]["frozen_step_5q_lock_semantics_preserved"])
        self.assertFalse(plan["safety"]["paid_provider_fallback_allowed"])

    def test_12_status_declares_losing_worker_does_no_work(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            report = s.get_step6m_scheduler_orchestration_status(env={})
        semantics = report["semantics"]
        self.assertFalse(semantics["losing_worker_refreshes_feed"])
        self.assertFalse(semantics["losing_worker_runs_model"])
        self.assertFalse(semantics["losing_worker_publishes_board"])

    def test_13_step6m_api_is_get_only(self):
        import sports_api.api.wnba_step6m_scheduler_orchestration as api

        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        with patch.object(api, "get_step6m_scheduler_orchestration_status", return_value={"scheduler_cycle_ready": False}), patch.object(
            api, "build_step6m_scheduler_orchestration_plan", return_value={"scheduler_cycle_ready": False}
        ):
            status = client.get("/api/v1/wnba/runtime/step6m-scheduler-orchestration-status")
            plan = client.get("/api/v1/wnba/runtime/step6m-scheduler-orchestration-plan")
            post = client.post("/api/v1/wnba/runtime/step6m-scheduler-orchestration-status")
        self.assertEqual(200, status.status_code)
        self.assertEqual(200, plan.status_code)
        self.assertEqual(405, post.status_code)

    def test_14_transport_background_path_targets_step6m_not_raw_step5q_cycle(self):
        import sports_api.api.wnba_pregame_board_scheduler_staging_activation as transport

        stop = MagicMock()
        stop.is_set.return_value = False
        stop.wait.return_value = True
        with patch.object(transport, "_worker_stop", stop), patch.object(
            transport, "require_staging_activation_ready", return_value={"scheduler_authorized": True}
        ), patch.object(transport.step6m, "require_step6m_scheduler_ready", return_value={"scheduler_cycle_ready": True}), patch.object(
            transport.step6m, "run_step6m_background_cycle", return_value={"outcome": "published"}
        ) as step6m_cycle, patch.object(transport.step5q, "_run_one_background_cycle") as raw_cycle:
            transport._worker_loop(30)
        step6m_cycle.assert_called_once()
        raw_cycle.assert_not_called()

    def test_15_transport_manual_path_targets_step6m(self):
        import sports_api.api.wnba_pregame_board_scheduler_staging_activation as transport

        with patch.object(transport, "require_staging_activation_ready", return_value={"scheduler_authorized": True}), patch.object(
            transport.step6m, "require_step6m_scheduler_ready", return_value={"scheduler_cycle_ready": True}
        ), patch.object(
            transport.step6m, "run_step6m_manual_cycle", return_value={"outcome": "published"}
        ) as step6m_cycle, patch.object(transport.step5q, "refresh_current_wnba_player_prop_board") as raw_refresh:
            result = transport.refresh_current_wnba_player_prop_board(
                date="2026-08-27", season=2026, provider_ids="kyre", force=True
            )
        self.assertEqual("published", result["outcome"])
        step6m_cycle.assert_called_once()
        raw_refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
