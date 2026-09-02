from __future__ import annotations

import copy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step10_market_adapters as step10b
from sports_api import wnba_step10_market_snapshot as step10c


EVAL = datetime(2026, 8, 28, 5, 20, 0, tzinfo=timezone.utc)
SAFE_ENV = {
    "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    "WNBA_BOARD_SCHEDULER_ENABLED": "false",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
    "WNBA_STEP6J_CANARY_ENABLED": "false",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
    "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
    "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
}


def row(
    *,
    book: str = "Book A",
    player_id: int = 1642301,
    player_name: str = "Certification Player A",
    stat: str = "points",
    line: float = 20.5,
    over: int = -110,
    under: int = -110,
    captured: str = "2026-08-28T05:19:30Z",
    game_id: str = "1022600291",
) -> dict:
    return {
        "game_id": game_id,
        "player_id": player_id,
        "player_name": player_name,
        "sportsbook": book,
        "stat": stat,
        "line": line,
        "over_price": over,
        "under_price": under,
        "market_captured_at": captured,
    }


def adapter(provider: str, rows: list[dict], *, evaluated_at: datetime = EVAL) -> dict:
    return step10b.adapt_step10b_market_payload(
        "flat_two_way_v1",
        {"provider": provider, "price_format": "american", "records": rows},
        evaluated_at=evaluated_at,
        env=SAFE_ENV,
    )


class Step10MarketSnapshotTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(step10c.step10c_market_snapshot_enabled({}))

    def test_production_switch_fails_closed(self):
        env = dict(SAFE_ENV)
        env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotDisabledError):
            step10c.build_step10c_market_snapshot([adapter("P", [row()])], evaluated_at=EVAL, env=env)

    def test_frozen_step10b_gate_is_required(self):
        env = dict(SAFE_ENV)
        env["WNBA_STEP10B_MARKET_ADAPTER_ENABLED"] = "false"
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotDisabledError):
            step10c.build_step10c_market_snapshot([adapter("P", [row()])], evaluated_at=EVAL, env=env)

    def test_two_books_same_line_are_consensus_ready(self):
        a = adapter("Provider A", [row(book="Book A", captured="2026-08-28T05:19:30Z")])
        b = adapter("Provider B", [row(book="Book B", over=-105, under=-115, captured="2026-08-28T05:19:40Z")])
        result = step10c.build_step10c_market_snapshot([a, b], evaluated_at=EVAL, env=SAFE_ENV)
        self.assertEqual(result["snapshot"]["eligible_record_count"], 2)
        self.assertEqual(result["market_groups"][0]["sportsbook_count"], 2)
        self.assertTrue(result["market_groups"][0]["consensus_ready_two_plus_books"])
        self.assertTrue(result["snapshot"]["board_synchronized"])

    def test_stale_quote_is_excluded_while_fresh_quote_survives(self):
        a = adapter("Provider A", [row(book="Old Book", captured="2026-08-28T05:00:00Z")])
        b = adapter("Provider B", [row(book="Fresh Book", captured="2026-08-28T05:19:30Z")])
        result = step10c.build_step10c_market_snapshot([a, b], evaluated_at=EVAL, env=SAFE_ENV)
        self.assertEqual(result["snapshot"]["stale_record_count"], 1)
        self.assertEqual(result["snapshot"]["eligible_record_count"], 1)
        self.assertEqual(result["excluded_records"][0]["reason"], "stale")
        self.assertEqual(result["records"][0]["sportsbook"], "Fresh Book")

    def test_all_stale_quotes_are_not_ready(self):
        a = adapter("Provider A", [row(captured="2026-08-28T05:00:00Z")])
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotNotReadyError):
            step10c.build_step10c_market_snapshot([a], evaluated_at=EVAL, env=SAFE_ENV)

    def test_market_sync_excludes_old_book_at_same_exact_line(self):
        a = adapter("Provider A", [row(book="Book A", captured="2026-08-28T05:16:00Z")])
        b = adapter("Provider B", [row(book="Book B", captured="2026-08-28T05:19:30Z")])
        result = step10c.build_step10c_market_snapshot(
            [a, b], evaluated_at=EVAL, max_quote_age_seconds=600, max_market_sync_seconds=120,
            env=SAFE_ENV,
        )
        self.assertEqual(result["snapshot"]["market_out_of_sync_record_count"], 1)
        self.assertEqual(result["excluded_records"][0]["reason"], "market_out_of_sync")
        self.assertEqual(result["records"][0]["sportsbook"], "Book B")

    def test_board_sync_fails_closed_across_market_families(self):
        a = adapter("Provider A", [row(book="Book A", captured="2026-08-28T05:13:00Z")])
        b = adapter("Provider B", [row(book="Book B", player_id=1642302, player_name="Certification Player B", stat="rebounds", line=10.5, captured="2026-08-28T05:19:30Z")])
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotNotReadyError):
            step10c.build_step10c_market_snapshot(
                [a, b], evaluated_at=EVAL, max_quote_age_seconds=600,
                max_board_sync_seconds=300, env=SAFE_ENV,
            )

    def test_board_sync_can_be_reported_without_fail_closed_requirement(self):
        a = adapter("Provider A", [row(book="Book A", captured="2026-08-28T05:13:00Z")])
        b = adapter("Provider B", [row(book="Book B", player_id=1642302, player_name="Certification Player B", stat="rebounds", line=10.5, captured="2026-08-28T05:19:30Z")])
        result = step10c.build_step10c_market_snapshot(
            [a, b], evaluated_at=EVAL, max_quote_age_seconds=600,
            max_board_sync_seconds=300, require_board_synchronized=False, env=SAFE_ENV,
        )
        self.assertFalse(result["snapshot"]["board_synchronized"])
        self.assertEqual(result["snapshot"]["eligible_record_count"], 2)

    def test_latest_repeated_update_wins(self):
        older = adapter("Provider A", [row(over=-115, under=-105, captured="2026-08-28T05:18:30Z")])
        newer = adapter("Provider B", [row(over=-105, under=-115, captured="2026-08-28T05:19:30Z")])
        result = step10c.build_step10c_market_snapshot([older, newer], evaluated_at=EVAL, env=SAFE_ENV)
        current = result["records"][0]
        self.assertEqual(current["over_odds"], -105)
        self.assertEqual(current["under_odds"], -115)
        self.assertEqual(current["superseded_update_count"], 1)
        self.assertEqual(current["earliest_seen_capture_utc"], "2026-08-28T05:18:30+00:00")

    def test_equal_timestamp_conflicting_updates_fail_closed(self):
        a = adapter("Provider A", [row(over=-110, under=-110, captured="2026-08-28T05:19:30Z")])
        b = adapter("Provider B", [row(over=-105, under=-115, captured="2026-08-28T05:19:30Z")])
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotConflictError):
            step10c.build_step10c_market_snapshot([a, b], evaluated_at=EVAL, env=SAFE_ENV)

    def test_alternative_lines_are_preserved(self):
        a = adapter("Provider A", [
            row(book="Book A", line=19.5, over=-125, under=105),
            row(book="Book A", line=20.5, over=-110, under=-110),
        ])
        result = step10c.build_step10c_market_snapshot([a], evaluated_at=EVAL, env=SAFE_ENV)
        self.assertEqual([record["line"] for record in result["records"]], [19.5, 20.5])
        self.assertEqual(result["market_families"][0]["available_lines"], [19.5, 20.5])

    def test_missing_expected_sportsbook_is_reported(self):
        a = adapter("Provider A", [row(book="Book A")])
        result = step10c.build_step10c_market_snapshot(
            [a], evaluated_at=EVAL,
            expected_sportsbooks=["Book A", "Book B", "Book C"], env=SAFE_ENV,
        )
        self.assertEqual(result["market_families"][0]["missing_expected_sportsbooks"], ["Book B", "Book C"])

    def test_tampered_step10b_hash_is_rejected(self):
        bad = copy.deepcopy(adapter("Provider A", [row()]))
        bad["adapter"]["provider"] = "Tampered Provider"
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotIntegrityError):
            step10c.build_step10c_market_snapshot([bad], evaluated_at=EVAL, env=SAFE_ENV)

    def test_tampered_nested_step10a_snapshot_is_rejected_independently(self):
        bad = copy.deepcopy(adapter("Provider A", [row()]))
        bad["step10a_snapshot"]["records"][0]["over_odds"] = -125
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotIntegrityError):
            step10c.build_step10c_market_snapshot([bad], evaluated_at=EVAL, env=SAFE_ENV)

    def test_previous_snapshot_exact_line_price_change_is_reported(self):
        prior_adapter = adapter("Prior", [row(over=-110, under=-110, captured="2026-08-28T05:17:30Z")], evaluated_at=datetime(2026, 8, 28, 5, 18, 0, tzinfo=timezone.utc))
        prior = step10c.build_step10c_market_snapshot(
            [prior_adapter], evaluated_at=datetime(2026, 8, 28, 5, 18, 0, tzinfo=timezone.utc), env=SAFE_ENV,
        )
        current_adapter = adapter("Current", [row(over=-105, under=-115, captured="2026-08-28T05:19:30Z")])
        current = step10c.build_step10c_market_snapshot(
            [current_adapter], evaluated_at=EVAL, previous_snapshot=prior, env=SAFE_ENV,
        )
        movement = current["movement"]
        self.assertTrue(movement["previous_snapshot_supplied"])
        self.assertEqual(len(movement["exact_line_price_changes"]), 1)
        self.assertEqual(movement["exact_line_price_changes"][0]["current_over_odds"], -105)

    def test_previous_snapshot_unambiguous_line_change_is_reported(self):
        prior_adapter = adapter("Prior", [row(line=20.5, captured="2026-08-28T05:17:30Z")], evaluated_at=datetime(2026, 8, 28, 5, 18, 0, tzinfo=timezone.utc))
        prior = step10c.build_step10c_market_snapshot(
            [prior_adapter], evaluated_at=datetime(2026, 8, 28, 5, 18, 0, tzinfo=timezone.utc), env=SAFE_ENV,
        )
        current_adapter = adapter("Current", [row(line=21.5, captured="2026-08-28T05:19:30Z")])
        current = step10c.build_step10c_market_snapshot(
            [current_adapter], evaluated_at=EVAL, previous_snapshot=prior, env=SAFE_ENV,
        )
        move = current["movement"]["unique_line_changes"][0]
        self.assertEqual(move["previous_line"], 20.5)
        self.assertEqual(move["current_line"], 21.5)
        self.assertEqual(move["line_delta"], 1.0)

    def test_missing_since_previous_is_reported(self):
        prior_adapter = adapter("Prior", [row(book="Book A"), row(book="Book B")])
        prior = step10c.build_step10c_market_snapshot([prior_adapter], evaluated_at=EVAL, env=SAFE_ENV)
        current_adapter = adapter("Current", [row(book="Book A")])
        current = step10c.build_step10c_market_snapshot(
            [current_adapter], evaluated_at=EVAL, previous_snapshot=prior, env=SAFE_ENV,
        )
        self.assertEqual(len(current["movement"]["missing_since_previous"]), 1)
        self.assertEqual(current["movement"]["missing_since_previous"][0]["sportsbook"], "Book B")

    def test_tampered_previous_snapshot_is_rejected(self):
        a = adapter("Provider A", [row()])
        prior = step10c.build_step10c_market_snapshot([a], evaluated_at=EVAL, env=SAFE_ENV)
        bad = copy.deepcopy(prior)
        bad["records"][0]["over_odds"] = -125
        with self.assertRaises(step10c.WNBAStep10MarketSnapshotIntegrityError):
            step10c.build_step10c_market_snapshot([a], evaluated_at=EVAL, previous_snapshot=bad, env=SAFE_ENV)

    def test_input_adapter_order_does_not_change_reconciled_market_content(self):
        a = adapter("Provider A", [row(book="Book A", captured="2026-08-28T05:19:30Z")])
        b = adapter("Provider B", [row(book="Book B", captured="2026-08-28T05:19:40Z")])
        one = step10c.build_step10c_market_snapshot([a, b], evaluated_at=EVAL, env=SAFE_ENV)
        two = step10c.build_step10c_market_snapshot([b, a], evaluated_at=EVAL, env=SAFE_ENV)
        self.assertEqual(one["records"], two["records"])
        self.assertEqual(one["market_groups"], two["market_groups"])
        self.assertEqual(one["market_families"], two["market_families"])
        self.assertEqual(one["lineage"], two["lineage"])

    def test_guardrails_keep_step9_network_model_math_and_writes_off(self):
        result = step10c.build_step10c_market_snapshot([adapter("Provider A", [row()])], evaluated_at=EVAL, env=SAFE_ENV)
        guards = result["guardrails"]
        self.assertTrue(guards["market_snapshot_reconciled"])
        self.assertTrue(guards["freshness_evaluated"])
        for key in (
            "sportsbook_network_fetch_performed", "basketball_projection_changed",
            "step8_distribution_changed", "step9_called", "vig_removed", "edge_calculated",
            "expected_value_calculated", "cross_sportsbook_consensus_calculated",
            "cross_prop_ranking_calculated", "supabase_mutated", "persistence_mutated",
            "scheduler_started", "production_runtime_enabled", "production_activation_allowed",
        ):
            self.assertFalse(guards[key], key)
        self.assertEqual(
            result["lineage"]["reconciled_step10a_snapshot_content_sha256"],
            result["reconciled_step10a_snapshot"]["snapshot_content_sha256"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
