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

    def _refresh(self, calls=None):
        def run(**kwargs):
            if calls is not None:
                calls.append(("refresh", kwargs))
            return {
                "outcome": "refreshed",
                "content_sha256": "b" * 64,
                "persistent_feed_sha256": "c" * 64,
                "offer_side_count": 20,
            }
        return run

    def _base_failover(self, calls=None):
        def run(provider_ids, **kwargs):
            if calls is not None:
                calls.append(("step5o", {"provider_ids": list(provider_ids), **kwargs}))
            return {"selected_provider_id": "kyre", "line_board": {}}
        return run

    def _cycle_that_collects(self, calls=None, outcome="published"):
        def run(**kwargs):
            if calls is not None:
                calls.append(("step5p", kwargs))
            failover = kwargs["failover_collector"](
                kwargs["provider_ids"],
                date=kwargs["date"],
                season=kwargs["season"],
                env=kwargs["env"],
                store_path="/tmp/feed.sqlite3",
            )
            self.assertEqual("kyre", failover["selected_provider_id"])
            return {
                "outcome": outcome,
                "provider_collection_attempted": True,
                "board_rebuild_attempted": True,
                "publication": {"publication_id": "pub-1"},
            }
        return run

    def test_01_status_blocks_when_step6l_is_not_ready(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.blocked6l):
            report = s.get_step6m_scheduler_orchestration_status(env={})
        self.assertFalse(report["scheduler_cycle_ready"])
        self.assertTrue(report["blocking_reasons"])

    def test_02_status_declares_step5p_guards_before_refresh(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            report = s.get_step6m_scheduler_orchestration_status(env={})
        self.assertTrue(report["scheduler_cycle_ready"])
        order = report["execution_order"]
        self.assertLess(order.index("frozen_step_5p_due_official_slate_and_provider_spacing_guards"), order.index("step_6l_owned_market_feed_refresh_at_step_5p_provider_collection"))
        self.assertTrue(report["semantics"]["refresh_injected_only_at_step_5p_provider_collection"])

    def test_03_require_helper_fails_closed(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.blocked6l):
            with self.assertRaises(s.WNBAStep6MOrchestrationNotReadyError):
                s.require_step6m_scheduler_ready(env={})

    def test_04_step5p_enters_before_refresh_and_step5o_reads_after_refresh(self):
        calls = []
        result = s._run_frozen_cycle_with_scoped_refresh(
            target_date="2026-08-27",
            season=2026,
            force=False,
            environment={"WNBA_MARKET_PROVIDER_MODE": "kyre"},
            refresher=self._refresh(calls),
            cycle_runner=self._cycle_that_collects(calls),
            base_failover_collector=self._base_failover(calls),
        )
        self.assertEqual(["step5p", "refresh", "step5o"], [item[0] for item in calls])
        self.assertTrue(result["step_6m"]["owned_feed_refresh_attempted"])
        self.assertTrue(result["step_6m"]["step_5p_pre_provider_guards_preserved"])

    def test_05_refresh_failure_stops_step5o_and_model_continuation(self):
        base = MagicMock()

        def cycle(**kwargs):
            kwargs["failover_collector"](
                kwargs["provider_ids"], date=kwargs["date"], season=kwargs["season"], env=kwargs["env"]
            )
            raise AssertionError("unreachable")

        with self.assertRaises(s.WNBAStep6MOrchestrationUpstreamError):
            s._run_frozen_cycle_with_scoped_refresh(
                target_date="2026-08-27",
                season=2026,
                force=False,
                environment={},
                refresher=MagicMock(side_effect=s.WNBAStep6LRefreshError("synthetic refresh failure")),
                cycle_runner=cycle,
                base_failover_collector=base,
            )
        base.assert_not_called()

    def test_06_not_due_cycle_performs_no_refresh(self):
        refresh = MagicMock()
        result = s._run_frozen_cycle_with_scoped_refresh(
            target_date="2026-08-27",
            season=2026,
            force=False,
            environment={},
            refresher=refresh,
            cycle_runner=MagicMock(return_value={"outcome": "skipped_not_due", "provider_collection_attempted": False, "board_rebuild_attempted": False}),
            base_failover_collector=MagicMock(),
        )
        refresh.assert_not_called()
        self.assertFalse(result["step_6m"]["owned_feed_refresh_attempted"])

    def test_07_empty_official_slate_performs_no_refresh(self):
        refresh = MagicMock()
        result = s._run_frozen_cycle_with_scoped_refresh(
            target_date="2026-08-27",
            season=2026,
            force=False,
            environment={},
            refresher=refresh,
            cycle_runner=MagicMock(return_value={"outcome": "empty_official_slate", "provider_collection_attempted": False, "board_rebuild_attempted": False}),
            base_failover_collector=MagicMock(),
        )
        refresh.assert_not_called()
        self.assertFalse(result["step_6m"]["owned_feed_refresh_attempted"])

    def test_08_provider_spacing_guard_performs_no_refresh(self):
        refresh = MagicMock()
        result = s._run_frozen_cycle_with_scoped_refresh(
            target_date="2026-08-27",
            season=2026,
            force=False,
            environment={},
            refresher=refresh,
            cycle_runner=MagicMock(return_value={"outcome": "skipped_provider_rate_guard", "provider_collection_attempted": False, "board_rebuild_attempted": False}),
            base_failover_collector=MagicMock(),
        )
        refresh.assert_not_called()
        self.assertFalse(result["step_6m"]["owned_feed_refresh_attempted"])

    def test_09_provider_hook_rejects_non_kyre_chain(self):
        hook = s._refresh_at_provider_collection(
            target_date="2026-08-27",
            season=2026,
            environment={},
            refresher=self._refresh(),
            base_failover_collector=MagicMock(),
            refresh_evidence={},
        )
        with self.assertRaises(s.WNBAStep6MOrchestrationError):
            hook(["sportsgameodds"], date="2026-08-27", season=2026, env={})

    def test_10_provider_hook_rejects_date_mismatch_before_refresh(self):
        refresh = MagicMock()
        hook = s._refresh_at_provider_collection(
            target_date="2026-08-27",
            season=2026,
            environment={},
            refresher=refresh,
            base_failover_collector=MagicMock(),
            refresh_evidence={},
        )
        with self.assertRaises(s.WNBAStep6MOrchestrationError):
            hook(["kyre"], date="2026-08-28", season=2026, env={})
        refresh.assert_not_called()

    def test_11_losing_distributed_worker_never_enters_step5p(self):
        refresh = MagicMock()
        cycle = MagicMock()
        skipped = {"outcome": "skipped_cross_process_lock", "provider_collection_attempted": False, "board_rebuild_attempted": False}
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s.step5q, "_run_cycle_with_distributed_lock", return_value=skipped
        ):
            result = s.run_step6m_background_cycle(date="2026-08-27", season=2026, env={}, refresher=refresh, cycle_runner=cycle)
        refresh.assert_not_called()
        cycle.assert_not_called()
        self.assertFalse(result["step_6m"]["owned_feed_refresh_attempted"])
        self.assertFalse(result["step_6m"]["model_cycle_attempted"])

    def test_12_winning_worker_refreshes_only_when_step5p_requests_collection(self):
        calls = []

        def own(call, *, contention_is_error):
            self.assertFalse(contention_is_error)
            return call()

        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s.step5q, "_run_cycle_with_distributed_lock", side_effect=own
        ):
            result = s.run_step6m_background_cycle(
                date="2026-08-27",
                season=2026,
                env={},
                refresher=self._refresh(calls),
                cycle_runner=self._cycle_that_collects(calls),
                base_failover_collector=self._base_failover(calls),
            )
        self.assertEqual(["step5p", "refresh", "step5o"], [item[0] for item in calls])
        self.assertEqual("published", result["outcome"])

    def test_13_manual_provider_override_is_kyre_only(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            with self.assertRaises(ValueError):
                s.run_step6m_manual_cycle(date="2026-08-27", season=2026, provider_ids="sportsgameodds", env={}, refresher=MagicMock(), cycle_runner=MagicMock())

    def test_14_none_date_is_resolved_once_and_provider_hook_receives_same_date(self):
        refresh = MagicMock(return_value={"outcome": "refreshed", "content_sha256": "f" * 64})
        seen = {}

        def base(provider_ids, **kwargs):
            seen["base_date"] = kwargs["date"]
            return {"selected_provider_id": "kyre", "line_board": {}}

        def cycle(**kwargs):
            seen["cycle_date"] = kwargs["date"]
            kwargs["failover_collector"](kwargs["provider_ids"], date=kwargs["date"], season=kwargs["season"], env=kwargs["env"])
            return {"outcome": "published", "provider_collection_attempted": True, "board_rebuild_attempted": True}

        def own(call, *, contention_is_error):
            return call()

        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l), patch.object(
            s, "_target_date", return_value="2026-08-27"
        ) as target, patch.object(s.step5q, "_run_cycle_with_distributed_lock", side_effect=own):
            s.run_step6m_manual_cycle(date=None, season=2026, env={}, refresher=refresh, cycle_runner=cycle, base_failover_collector=base)
        target.assert_called_once_with(None)
        self.assertEqual("2026-08-27", seen["cycle_date"])
        self.assertEqual("2026-08-27", refresh.call_args.kwargs["date"])
        self.assertEqual("2026-08-27", seen["base_date"])

    def test_15_plan_keeps_step5p_pre_provider_guards_authoritative(self):
        with patch.object(s, "get_step6l_production_refresh_status", return_value=self.green6l):
            plan = s.build_step6m_scheduler_orchestration_plan(env={})
        safety = plan["safety"]
        self.assertTrue(safety["step_5p_due_guard_precedes_network_refresh"])
        self.assertTrue(safety["official_slate_guard_precedes_network_refresh"])
        self.assertTrue(safety["provider_spacing_guard_precedes_network_refresh"])
        self.assertFalse(safety["paid_provider_fallback_allowed"])

    def test_16_step6m_api_is_get_only(self):
        import sports_api.api.wnba_step6m_scheduler_orchestration as api
        app = FastAPI(); app.include_router(api.router); client = TestClient(app)
        with patch.object(api, "get_step6m_scheduler_orchestration_status", return_value={"scheduler_cycle_ready": False}), patch.object(api, "build_step6m_scheduler_orchestration_plan", return_value={"scheduler_cycle_ready": False}):
            status = client.get("/api/v1/wnba/runtime/step6m-scheduler-orchestration-status")
            plan = client.get("/api/v1/wnba/runtime/step6m-scheduler-orchestration-plan")
            post = client.post("/api/v1/wnba/runtime/step6m-scheduler-orchestration-status")
        self.assertEqual(200, status.status_code); self.assertEqual(200, plan.status_code); self.assertEqual(405, post.status_code)

    def test_17_transport_background_path_targets_step6m_not_raw_step5q(self):
        import sports_api.api.wnba_pregame_board_scheduler_staging_activation as transport
        stop = MagicMock(); stop.is_set.return_value = False; stop.wait.return_value = True
        with patch.object(transport, "_worker_stop", stop), patch.object(transport, "require_staging_activation_ready", return_value={"scheduler_authorized": True}), patch.object(transport.step6m, "require_step6m_scheduler_ready", return_value={"scheduler_cycle_ready": True}), patch.object(transport.step6m, "run_step6m_background_cycle", return_value={"outcome": "published"}) as step6m_cycle, patch.object(transport.step5q, "_run_one_background_cycle") as raw_cycle:
            transport._worker_loop(30)
        step6m_cycle.assert_called_once(); raw_cycle.assert_not_called()

    def test_18_transport_manual_path_targets_step6m(self):
        import sports_api.api.wnba_pregame_board_scheduler_staging_activation as transport
        with patch.object(transport, "require_staging_activation_ready", return_value={"scheduler_authorized": True}), patch.object(transport.step6m, "require_step6m_scheduler_ready", return_value={"scheduler_cycle_ready": True}), patch.object(transport.step6m, "run_step6m_manual_cycle", return_value={"outcome": "published"}) as step6m_cycle, patch.object(transport.step5q, "refresh_current_wnba_player_prop_board") as raw_refresh:
            result = transport.refresh_current_wnba_player_prop_board(date="2026-08-27", season=2026, provider_ids="kyre", force=True)
        self.assertEqual("published", result["outcome"]); step6m_cycle.assert_called_once(); raw_refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
