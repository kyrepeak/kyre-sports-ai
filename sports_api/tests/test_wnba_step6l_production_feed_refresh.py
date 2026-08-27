from pathlib import Path
import fcntl
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import sports_api.wnba_step6d_direct_integration as step6d
import sports_api.wnba_reconciled_direct_sync as step6i
import sports_api.wnba_step6j_canary_activation as step6j
from sports_api.collectors.wnba_kyre_market_feed import MARKET_PROVIDER_MODE_ENV
import sports_api.wnba_step6l_production_feed_refresh as s
from sports_api.main import app


class Step6LProductionFeedRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lock_path = str(Path(self.tmp.name) / "step6l.lock")
        self.env = {
            s.PRODUCTION_REFRESH_ENABLED_ENV: "true",
            s.MARKET_PROVIDER_MODE_ENV: "kyre",
            s.CANARY_ENABLED_ENV: "false",
            s.DIRECT_SYNC_ENABLED_ENV: "false",
            s.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
            s.RECONCILED_SYNC_ENABLED_ENV: "false",
            s.REFRESH_LOCK_PATH_ENV: self.lock_path,
        }
        self.green_step6k = {
            "phase": "scheduler_authorized",
            "scheduler_authorized": True,
            "activation_checkpoint_sha256": "a" * 64,
            "step6j_verified": True,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def status(self, env=None, step6k=None):
        with patch.object(
            s,
            "get_step6k_activation_preflight",
            return_value=self.green_step6k if step6k is None else step6k,
        ):
            return s.get_step6l_production_refresh_status(env=self.env if env is None else env)

    def test_01_explicit_step6l_enablement_is_required(self):
        env = dict(self.env)
        env[s.PRODUCTION_REFRESH_ENABLED_ENV] = "false"
        report = self.status(env)
        self.assertFalse(report["production_refresh_ready"])
        self.assertIn("step_6l_explicit_refresh_enablement", repr(report["blocking_reasons"]))

    def test_02_step6k_scheduler_authorization_is_required(self):
        blocked = dict(self.green_step6k)
        blocked["scheduler_authorized"] = False
        report = self.status(step6k=blocked)
        self.assertFalse(report["production_refresh_ready"])
        self.assertIn("step_6k_scheduler_authorized", repr(report["blocking_reasons"]))

    def test_03_market_mode_must_be_kyre_only(self):
        env = dict(self.env)
        env[s.MARKET_PROVIDER_MODE_ENV] = "auto"
        report = self.status(env)
        self.assertFalse(report["production_refresh_ready"])
        self.assertIn("kyre_owned_market_mode_only", repr(report["blocking_reasons"]))

    def test_04_global_step6j_write_switches_must_remain_off(self):
        env = dict(self.env)
        env[s.DIRECT_SYNC_ENABLED_ENV] = "true"
        report = self.status(env)
        self.assertFalse(report["production_refresh_ready"])
        self.assertFalse(report["global_temporary_write_switches_off"])

    def test_05_refresh_lock_path_must_be_absolute(self):
        env = dict(self.env)
        env[s.REFRESH_LOCK_PATH_ENV] = "relative.lock"
        report = self.status(env)
        self.assertFalse(report["production_refresh_ready"])
        self.assertIn("refresh_lock_path_valid", repr(report["blocking_reasons"]))

    def test_06_scoped_step6i_environment_does_not_mutate_input(self):
        before = dict(self.env)
        scoped = s._scoped_step6i_environment(self.env)
        self.assertEqual(before, self.env)
        self.assertEqual("true", scoped[s.DIRECT_SYNC_ENABLED_ENV])
        self.assertEqual("draftkings", scoped[s.DIRECT_SYNC_PROVIDER_ENV])
        self.assertEqual("true", scoped[s.RECONCILED_SYNC_ENABLED_ENV])
        self.assertEqual("false", scoped[s.CANARY_ENABLED_ENV])
        self.assertEqual("kyre", scoped[s.MARKET_PROVIDER_MODE_ENV])

    def test_07_successful_refresh_uses_private_step6i_switches_only(self):
        original = dict(self.env)
        observed = {}

        def syncer(**kwargs):
            observed.update(kwargs)
            return {
                "provider_id": "draftkings_direct",
                "synced": True,
                "feed_write_performed": True,
                "storage": {"content_sha256": "b" * 64},
                "persistent_feed_sha256": "c" * 64,
                "snapshot_sha256": "d" * 64,
                "reconciliation_fingerprint_sha256": "e" * 64,
                "offer_side_count": 42,
                "step6h_ready": True,
            }

        with patch.object(s, "get_step6k_activation_preflight", return_value=self.green_step6k):
            result = s.refresh_step6l_owned_market_feed(
                date="2026-08-27",
                season=2026,
                env=self.env,
                syncer=syncer,
            )

        self.assertEqual(original, self.env)
        self.assertEqual("refreshed", result["outcome"])
        self.assertEqual("b" * 64, result["content_sha256"])
        self.assertTrue(result["global_temporary_write_switches_off_after_refresh"])
        self.assertFalse(result["global_environment_mutated"])
        scoped = observed["env"]
        self.assertEqual("true", scoped[s.DIRECT_SYNC_ENABLED_ENV])
        self.assertEqual("true", scoped[s.RECONCILED_SYNC_ENABLED_ENV])
        self.assertEqual("false", scoped[s.CANARY_ENABLED_ENV])
        self.assertEqual("kyre", scoped[s.MARKET_PROVIDER_MODE_ENV])

    def test_08_blocked_refresh_never_calls_step6i(self):
        env = dict(self.env)
        env[s.PRODUCTION_REFRESH_ENABLED_ENV] = "false"
        syncer = MagicMock()
        with patch.object(s, "get_step6k_activation_preflight", return_value=self.green_step6k):
            with self.assertRaises(s.WNBAStep6LRefreshNotReadyError):
                s.refresh_step6l_owned_market_feed(
                    date="2026-08-27",
                    season=2026,
                    env=env,
                    syncer=syncer,
                )
        syncer.assert_not_called()

    def test_09_unconfirmed_step6i_write_is_rejected(self):
        def syncer(**kwargs):
            return {"synced": False, "feed_write_performed": False}

        with patch.object(s, "get_step6k_activation_preflight", return_value=self.green_step6k):
            with self.assertRaises(s.WNBAStep6LRefreshError):
                s.refresh_step6l_owned_market_feed(
                    date="2026-08-27",
                    season=2026,
                    env=self.env,
                    syncer=syncer,
                )
        self.assertEqual("false", self.env[s.DIRECT_SYNC_ENABLED_ENV])
        self.assertEqual("false", self.env[s.RECONCILED_SYNC_ENABLED_ENV])

    def test_10_sync_exception_cannot_mutate_caller_environment(self):
        original = dict(self.env)

        def syncer(**kwargs):
            raise RuntimeError("synthetic Step 6I failure")

        with patch.object(s, "get_step6k_activation_preflight", return_value=self.green_step6k):
            with self.assertRaises(RuntimeError):
                s.refresh_step6l_owned_market_feed(
                    date="2026-08-27",
                    season=2026,
                    env=self.env,
                    syncer=syncer,
                )
        self.assertEqual(original, self.env)

    def test_11_cross_process_refresh_lock_fails_closed(self):
        Path(self.lock_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with patch.object(s, "get_step6k_activation_preflight", return_value=self.green_step6k):
                    with self.assertRaises(s.WNBAStep6LRefreshBusyError):
                        s.refresh_step6l_owned_market_feed(
                            date="2026-08-27",
                            season=2026,
                            env=self.env,
                            syncer=MagicMock(),
                        )
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def test_12_plan_explicitly_forbids_paid_fallback_and_defers_scheduler_wiring(self):
        with patch.object(s, "get_step6k_activation_preflight", return_value=self.green_step6k):
            plan = s.build_step6l_production_refresh_plan(env=self.env)
        self.assertFalse(plan["safety"]["paid_odds_vendor_allowed"])
        self.assertFalse(plan["safety"]["sports_game_odds_fallback_allowed"])
        self.assertFalse(plan["safety"]["scheduler_wiring_performed_in_step_6l"])
        self.assertFalse(plan["steps"][-1]["complete"])

    def test_13_step6l_constants_match_existing_authoritative_switches(self):
        self.assertEqual(step6d.DIRECT_SYNC_ENABLED_ENV, s.DIRECT_SYNC_ENABLED_ENV)
        self.assertEqual(step6d.DIRECT_SYNC_PROVIDER_ENV, s.DIRECT_SYNC_PROVIDER_ENV)
        self.assertEqual(step6i.RECONCILED_SYNC_ENABLED_ENV, s.RECONCILED_SYNC_ENABLED_ENV)
        self.assertEqual(step6j.CANARY_ENABLED_ENV, s.CANARY_ENABLED_ENV)
        self.assertEqual(MARKET_PROVIDER_MODE_ENV, s.MARKET_PROVIDER_MODE_ENV)

    def test_14_step6l_routes_are_get_only(self):
        paths = app.openapi()["paths"]
        for route in (
            "/api/v1/wnba/runtime/step6l-feed-refresh-status",
            "/api/v1/wnba/runtime/step6l-feed-refresh-plan",
        ):
            self.assertIn(route, paths)
            self.assertEqual({"get"}, set(paths[route]))

    def test_15_status_declares_no_paid_vendor_and_no_scheduler_start(self):
        report = self.status()
        self.assertFalse(report["semantics"]["paid_odds_vendor_allowed"])
        self.assertFalse(report["semantics"]["scheduler_started_by_step_6l"])
        self.assertTrue(report["semantics"]["global_step_6j_switches_must_remain_off"])


if __name__ == "__main__":
    unittest.main()
