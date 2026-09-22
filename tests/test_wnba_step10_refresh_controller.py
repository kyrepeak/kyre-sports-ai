from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_market_snapshot as step10c
from sports_api import wnba_step10_refresh_controller as step10d

UTC = timezone.utc
NOW = datetime(2026, 8, 28, 5, 27, 0, tzinfo=UTC)
ENV = {
    "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    "WNBA_BOARD_SCHEDULER_ENABLED": "false",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
    "WNBA_STEP6J_CANARY_ENABLED": "false",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
    "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
    "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
    "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
}


def flat_payload(
    provider: str,
    sportsbook: str,
    *,
    captured: str = "2026-08-28T05:26:30+00:00",
    stat: str = "points",
    line: float = 20.5,
    over: int = -110,
    under: int = -110,
    player_id: int = 1642301,
    player_name: str = "Certification Player A",
) -> dict:
    return {
        "provider": provider,
        "price_format": "american",
        "records": [{
            "game_id": "1022600291",
            "player_id": player_id,
            "player_name": player_name,
            "sportsbook": sportsbook,
            "stat": stat,
            "line": line,
            "over_price": over,
            "under_price": under,
            "market_captured_at": captured,
        }],
    }


def success_refresh(provider: str, sportsbook: str, **kwargs) -> dict:
    return {
        "provider": provider,
        "adapter_type": "flat_two_way_v1",
        "attempts": [{"ok": True, "payload": flat_payload(provider, sportsbook, **kwargs)}],
    }


def failed_refresh(provider: str, *, errors: tuple[str, ...] = ("timeout",)) -> dict:
    return {
        "provider": provider,
        "adapter_type": "flat_two_way_v1",
        "attempts": [{"ok": False, "error_code": code} for code in errors],
    }


def build_last_good(
    *,
    captured_a: str = "2026-08-28T05:25:30+00:00",
    captured_b: str = "2026-08-28T05:25:40+00:00",
    evaluated: datetime = datetime(2026, 8, 28, 5, 26, 0, tzinfo=UTC),
) -> dict:
    a = step10b.adapt_step10b_market_payload(
        "flat_two_way_v1",
        flat_payload("Provider A", "Book A", captured=captured_a, over=-110, under=-110),
        evaluated_at=evaluated,
        env=ENV,
    )
    b = step10b.adapt_step10b_market_payload(
        "flat_two_way_v1",
        flat_payload("Provider B", "Book B", captured=captured_b, over=-108, under=-112),
        evaluated_at=evaluated,
        env=ENV,
    )
    return step10c.build_step10c_market_snapshot([a, b], evaluated_at=evaluated, env=ENV)


class Step10RefreshControllerTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(step10d.step10d_refresh_controller_enabled({}))

    def test_production_switch_fails_closed(self):
        env = dict(ENV, WNBA_PRODUCTION_RUNTIME_ENABLED="true")
        with self.assertRaises(step10d.WNBAStep10RefreshControllerDisabledError):
            step10d.run_step10d_refresh_cycle([failed_refresh("Provider A")], evaluated_at=NOW, env=env)

    def test_scheduler_switch_fails_closed(self):
        env = dict(ENV, WNBA_BOARD_SCHEDULER_ENABLED="true")
        with self.assertRaises(step10d.WNBAStep10RefreshControllerDisabledError):
            step10d.run_step10d_refresh_cycle([failed_refresh("Provider A")], evaluated_at=NOW, env=env)

    def test_frozen_step10c_gate_is_required(self):
        env = dict(ENV, WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED="false")
        with self.assertRaises(step10d.WNBAStep10RefreshControllerDisabledError):
            step10d.run_step10d_refresh_cycle([failed_refresh("Provider A")], evaluated_at=NOW, env=env)

    def test_successful_providers_automatically_build_current_step10c_snapshot(self):
        out = step10d.run_step10d_refresh_cycle([
            success_refresh("Provider A", "Book A", over=-105, under=-115),
            success_refresh("Provider B", "Book B", captured="2026-08-28T05:26:40+00:00"),
        ], evaluated_at=NOW, env=ENV)
        self.assertEqual(out["status"], "ready")
        self.assertEqual(out["snapshot_source"], "current_refresh")
        self.assertTrue(out["current_refresh"]["step10c_snapshot_created"])
        self.assertEqual(out["market_snapshot"]["schema_version"], step10c.SCHEMA_VERSION)
        self.assertEqual(out["market_snapshot"]["snapshot"]["eligible_record_count"], 2)

    def test_provider_error_then_success_records_retry_without_sleeping(self):
        refresh = success_refresh("Provider A", "Book A")
        refresh["attempts"].insert(0, {"ok": False, "error_code": "timeout"})
        out = step10d.run_step10d_refresh_cycle([refresh], evaluated_at=NOW, env=ENV)
        provider = out["providers"][0]
        self.assertTrue(provider["succeeded"])
        self.assertEqual(provider["attempts_consumed"], 2)
        self.assertEqual(provider["attempts"][1]["retry_delay_seconds_before_attempt"], 2.0)
        self.assertFalse(out["refresh"]["retry_policy"]["sleep_executed"])

    def test_exponential_retry_schedule_is_capped(self):
        refresh = failed_refresh("Provider A", errors=("e1", "e2", "e3", "e4", "e5"))
        out = step10d.run_step10d_refresh_cycle(
            [refresh],
            evaluated_at=NOW,
            max_attempts_per_provider=5,
            retry_base_seconds=2,
            retry_multiplier=3,
            retry_max_seconds=5,
            env=ENV,
        )
        delays = [row["retry_delay_seconds_before_attempt"] for row in out["providers"][0]["attempts"]]
        self.assertEqual(delays, [0.0, 2.0, 5.0, 5.0, 5.0])
        self.assertEqual(out["status"], "not_ready")

    def test_max_attempts_truncates_extra_attempts(self):
        refresh = failed_refresh("Provider A", errors=("e1", "e2", "e3"))
        refresh["attempts"].append({"ok": True, "payload": flat_payload("Provider A", "Book A")})
        out = step10d.run_step10d_refresh_cycle(
            [refresh], evaluated_at=NOW, max_attempts_per_provider=3, env=ENV
        )
        self.assertEqual(out["providers"][0]["attempts_available"], 4)
        self.assertEqual(out["providers"][0]["attempts_consumed"], 3)
        self.assertFalse(out["providers"][0]["succeeded"])

    def test_provider_identity_is_unique_case_insensitively(self):
        with self.assertRaises(step10d.WNBAStep10RefreshControllerInputError):
            step10d.run_step10d_refresh_cycle([
                failed_refresh("Provider A"),
                failed_refresh("provider a"),
            ], evaluated_at=NOW, env=ENV)

    def test_declared_provider_must_match_payload_provider(self):
        refresh = success_refresh("Provider A", "Book A")
        refresh["attempts"][0]["payload"]["provider"] = "Different Provider"
        with self.assertRaises(step10d.WNBAStep10RefreshControllerInputError):
            step10d.run_step10d_refresh_cycle([refresh], evaluated_at=NOW, env=ENV)

    def test_all_provider_failures_use_verified_fresh_last_good_snapshot(self):
        last_good = build_last_good()
        out = step10d.run_step10d_refresh_cycle([
            failed_refresh("Provider A", errors=("timeout", "timeout")),
            failed_refresh("Provider B", errors=("rate_limited",)),
        ], evaluated_at=NOW, last_good_snapshot=last_good, env=ENV)
        self.assertEqual(out["status"], "degraded_last_good")
        self.assertEqual(out["snapshot_source"], "last_good_snapshot")
        self.assertTrue(out["last_good"]["used"])
        self.assertEqual(out["market_snapshot"]["snapshot_content_sha256"], last_good["snapshot_content_sha256"])

    def test_stale_last_good_is_never_served(self):
        old_eval = datetime(2026, 8, 28, 5, 10, 30, tzinfo=UTC)
        last_good = build_last_good(
            captured_a="2026-08-28T05:10:00+00:00",
            captured_b="2026-08-28T05:10:10+00:00",
            evaluated=old_eval,
        )
        out = step10d.run_step10d_refresh_cycle(
            [failed_refresh("Provider A")], evaluated_at=NOW, last_good_snapshot=last_good, env=ENV
        )
        self.assertEqual(out["status"], "not_ready")
        self.assertFalse(out["last_good"]["fallback_eligible"])
        self.assertIsNone(out["market_snapshot"])

    def test_tampered_last_good_snapshot_fails_integrity(self):
        last_good = build_last_good()
        last_good["records"][0]["over_odds"] = 999
        with self.assertRaises(step10d.WNBAStep10RefreshControllerIntegrityError):
            step10d.run_step10d_refresh_cycle(
                [failed_refresh("Provider A")], evaluated_at=NOW, last_good_snapshot=last_good, env=ENV
            )

    def test_current_success_supersedes_last_good_and_reports_movement(self):
        last_good = build_last_good()
        out = step10d.run_step10d_refresh_cycle([
            success_refresh("Provider A", "Book A", over=-105, under=-115),
            success_refresh("Provider B", "Book B", captured="2026-08-28T05:26:40+00:00", over=-110, under=-110),
        ], evaluated_at=NOW, last_good_snapshot=last_good, env=ENV)
        self.assertEqual(out["status"], "ready")
        self.assertFalse(out["last_good"]["used"])
        self.assertTrue(out["market_snapshot"]["movement"]["previous_snapshot_supplied"])
        self.assertGreaterEqual(len(out["market_snapshot"]["movement"]["exact_line_price_changes"]), 1)

    def test_partial_provider_failure_still_builds_from_surviving_provider(self):
        out = step10d.run_step10d_refresh_cycle([
            success_refresh("Provider A", "Book A"),
            failed_refresh("Provider B", errors=("timeout", "timeout", "timeout")),
        ], evaluated_at=NOW, env=ENV)
        self.assertEqual(out["status"], "ready")
        self.assertEqual(out["refresh"]["successful_provider_count"], 1)
        self.assertEqual(out["refresh"]["failed_provider_count"], 1)
        self.assertEqual(out["market_snapshot"]["snapshot"]["eligible_record_count"], 1)

    def test_current_unsynchronized_board_can_fall_back_to_last_good(self):
        last_good = build_last_good()
        out = step10d.run_step10d_refresh_cycle([
            success_refresh(
                "Provider A", "Book A", captured="2026-08-28T05:20:30+00:00", stat="points", line=20.5
            ),
            success_refresh(
                "Provider B", "Book B", captured="2026-08-28T05:26:30+00:00", stat="rebounds", line=10.5
            ),
        ], evaluated_at=NOW, last_good_snapshot=last_good, env=ENV)
        self.assertEqual(out["status"], "degraded_last_good")
        self.assertIn("WNBAStep10MarketSnapshotNotReadyError", out["current_refresh"]["failure_reason"])

    def test_no_current_and_no_fallback_returns_not_ready(self):
        out = step10d.run_step10d_refresh_cycle(
            [failed_refresh("Provider A")], evaluated_at=NOW, env=ENV
        )
        self.assertEqual(out["status"], "not_ready")
        self.assertEqual(out["snapshot_source"], "none")
        self.assertIsNone(out["market_snapshot"])

    def test_last_good_fallback_can_be_explicitly_disabled(self):
        last_good = build_last_good()
        out = step10d.run_step10d_refresh_cycle(
            [failed_refresh("Provider A")],
            evaluated_at=NOW,
            last_good_snapshot=last_good,
            allow_last_good_fallback=False,
            env=ENV,
        )
        self.assertEqual(out["status"], "not_ready")
        self.assertFalse(out["last_good"]["fallback_eligible"])

    def test_refresh_cycle_id_is_deterministic_for_same_start_and_provider_set(self):
        first = step10d.run_step10d_refresh_cycle([
            failed_refresh("Provider B"), failed_refresh("Provider A")
        ], evaluated_at=NOW, cycle_started_at=NOW, env=ENV)
        second = step10d.run_step10d_refresh_cycle([
            failed_refresh("Provider A"), failed_refresh("Provider B")
        ], evaluated_at=NOW, cycle_started_at=NOW, env=ENV)
        self.assertEqual(first["refresh_cycle_id"], second["refresh_cycle_id"])

    def test_refresh_interval_only_calculates_next_due_time(self):
        out = step10d.run_step10d_refresh_cycle(
            [failed_refresh("Provider A")], evaluated_at=NOW, refresh_interval_seconds=90, env=ENV
        )
        self.assertEqual(out["refresh"]["refresh_interval_seconds"], 90)
        self.assertEqual(out["refresh"]["next_refresh_due_at_utc"], "2026-08-28T05:28:30+00:00")
        self.assertFalse(out["guardrails"]["scheduler_started"])

    def test_adapter_rejection_can_be_followed_by_valid_retry(self):
        bad = flat_payload("Provider A", "Book A")
        bad["records"][0]["over_price"] = -50
        refresh = {
            "provider": "Provider A",
            "adapter_type": "flat_two_way_v1",
            "attempts": [
                {"ok": True, "payload": bad},
                {"ok": True, "payload": flat_payload("Provider A", "Book A")},
            ],
        }
        out = step10d.run_step10d_refresh_cycle([refresh], evaluated_at=NOW, env=ENV)
        self.assertEqual(out["providers"][0]["attempts"][0]["result"], "adapter_rejected")
        self.assertTrue(out["providers"][0]["succeeded"])
        self.assertEqual(out["status"], "ready")

    def test_attempt_contract_rejects_ambiguous_success_and_failure_shapes(self):
        bad_success = success_refresh("Provider A", "Book A")
        bad_success["attempts"][0]["error_code"] = "should_not_exist"
        with self.assertRaises(step10d.WNBAStep10RefreshControllerInputError):
            step10d.run_step10d_refresh_cycle([bad_success], evaluated_at=NOW, env=ENV)
        bad_failure = failed_refresh("Provider B")
        del bad_failure["attempts"][0]["error_code"]
        with self.assertRaises(step10d.WNBAStep10RefreshControllerInputError):
            step10d.run_step10d_refresh_cycle([bad_failure], evaluated_at=NOW, env=ENV)

    def test_guardrails_keep_network_sleep_step9_writes_scheduler_and_production_off(self):
        out = step10d.run_step10d_refresh_cycle(
            [success_refresh("Provider A", "Book A")], evaluated_at=NOW, env=ENV
        )
        guards = out["guardrails"]
        for key in (
            "sportsbook_network_fetch_performed", "retry_sleep_performed", "basketball_projection_changed",
            "step8_distribution_changed", "step9_called", "vig_removed", "edge_calculated",
            "expected_value_calculated", "cross_sportsbook_consensus_calculated",
            "cross_prop_ranking_calculated", "supabase_mutated", "persistence_mutated",
            "scheduler_started", "production_runtime_enabled", "production_activation_allowed",
        ):
            self.assertFalse(guards[key], key)
        self.assertTrue(out["contract"]["refresh_cadence_is_metadata_only"])
        self.assertFalse(out["contract"]["provider_network_fetch_allowed"])
        self.assertFalse(out["contract"]["controller_scheduler_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
