from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import sports_api.wnba_multi_sportsbook_market_consensus as h


EVALUATED = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)


def threshold_fixture(over_probs=(0.48, 0.55, 0.62)):
    scenarios = {}
    for name, over in zip(("low", "base", "high"), over_probs):
        under = 1.0 - over
        scenarios[name] = {
            "conditional_scenario": name,
            "stat": "points",
            "line": 19.5,
            "raw_probabilities": {
                "over": {"probability": over},
                "under": {"probability": under},
                "push": {"probability": 0.0},
            },
            "fair_odds": {
                "over": {"available": True, "fair_probability": over},
                "under": {"available": True, "fair_probability": under},
            },
        }
    return {
        "model_version": h.THRESHOLD_MODEL_VERSION,
        "probability_id": "wnba-5f-test",
        "probability_fingerprint_sha256": "a" * 64,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": "1022600001",
        "player_id": 123,
        "team_key": "NYL",
        "opponent_team_key": "LVA",
        "prop": {
            "stat": "points",
            "line": 19.5,
            "line_is_integer": False,
            "line_is_threshold_only": True,
            "line_does_not_change_basketball_projection": True,
        },
        "primary_result": scenarios["base"],
        "conditional_scenario_results": scenarios,
        "snapshot_reference": {"snapshot_id": "s1", "content_sha256": "b" * 64},
    }


def quote(book, over=-110, under=-110, captured="2026-08-26T17:58:00Z"):
    return {
        "sportsbook": book,
        "over_odds": over,
        "under_odds": under,
        "market_captured_at_utc": captured,
    }


def three_quotes():
    return [
        quote("DraftKings", -110, -110, "2026-08-26T17:58:00Z"),
        quote("FanDuel", 100, -120, "2026-08-26T17:59:00Z"),
        quote("BetMGM", -105, -115, "2026-08-26T17:57:00Z"),
    ]


class TestWNBAMultiSportsbookMarketConsensus(unittest.TestCase):
    def build(self, quotes=None, threshold=None, **kwargs):
        return h.build_multi_sportsbook_market_consensus(
            threshold or threshold_fixture(),
            quotes or three_quotes(),
            evaluated_at=kwargs.pop("evaluated_at", EVALUATED),
            **kwargs,
        )

    def test_01_requires_quote_list(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes("not-a-list")

    def test_02_requires_at_least_two_quotes(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote("DraftKings")])

    def test_03_rejects_more_than_max_quotes(self):
        rows = [quote(f"Book {i}") for i in range(h.MAX_SPORTSBOOK_QUOTES + 1)]
        with self.assertRaises(ValueError):
            h._normalize_quotes(rows)

    def test_04_accepts_max_quote_count(self):
        rows = [quote(f"Book {i}") for i in range(h.MAX_SPORTSBOOK_QUOTES)]
        self.assertEqual(len(h._normalize_quotes(rows)), h.MAX_SPORTSBOOK_QUOTES)

    def test_05_rejects_non_object_quote(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote("A"), "bad"])

    def test_06_rejects_duplicate_book_case_insensitive(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote("DraftKings"), quote("draftkings")])

    def test_07_rejects_duplicate_book_after_whitespace_normalization(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote("Draft  Kings"), quote("Draft Kings")])

    def test_08_rejects_empty_sportsbook(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote(""), quote("FanDuel")])

    def test_09_rejects_invalid_over_odds(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote("A", -99), quote("B")])

    def test_10_rejects_noninteger_under_odds(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([quote("A", under=-110.5), quote("B")])

    def test_11_rejects_timezone_naive_timestamp(self):
        with self.assertRaises(ValueError):
            h._normalize_quotes([
                quote("A", captured="2026-08-26T17:58:00"),
                quote("B"),
            ])

    def test_12_normalizes_z_timestamp_to_utc_offset(self):
        rows = h._normalize_quotes([quote("B"), quote("A")])
        self.assertEqual(rows[0]["market_captured_at_utc"], "2026-08-26T17:58:00+00:00")

    def test_13_normalized_quotes_are_sorted_by_book(self):
        rows = h._normalize_quotes([quote("FanDuel"), quote("BetMGM"), quote("DraftKings")])
        self.assertEqual([r["sportsbook"] for r in rows], ["BetMGM", "DraftKings", "FanDuel"])

    def test_14_summary_math(self):
        result = h._summary([0.4, 0.5, 0.6])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["mean"], 0.5)
        self.assertEqual(result["median"], 0.5)
        self.assertEqual(result["range"], 0.2)

    def test_15_summary_empty(self):
        self.assertIsNone(h._summary([])["mean"])

    def test_16_best_over_price(self):
        result = self.build()
        self.assertEqual(result["best_prices"]["over"]["sportsbooks"][0]["sportsbook"], "FanDuel")
        self.assertEqual(result["best_prices"]["over"]["best_american_odds"], 100)

    def test_17_best_under_price(self):
        result = self.build()
        self.assertEqual(result["best_prices"]["under"]["sportsbooks"][0]["sportsbook"], "DraftKings")
        self.assertEqual(result["best_prices"]["under"]["best_american_odds"], -110)

    def test_18_best_price_reports_ties(self):
        rows = [
            quote("A", 100, -110),
            quote("B", 100, -115),
        ]
        result = self.build(rows)
        self.assertEqual(result["best_prices"]["over"]["tie_count"], 2)
        self.assertEqual(
            [x["sportsbook"] for x in result["best_prices"]["over"]["sportsbooks"]],
            ["A", "B"],
        )

    def test_19_consensus_is_equal_weighted(self):
        result = self.build()
        per_book = []
        for row in result["ev_rankings"]["over"]:
            per_book.append(0.55 - row["base_no_vig_edge_probability"])
        expected = sum(per_book) / len(per_book)
        self.assertAlmostEqual(
            result["consensus"]["no_vig_probability"]["consensus_over"],
            expected,
            places=9,
        )

    def test_20_consensus_no_vig_sums_to_one(self):
        result = self.build()
        no_vig = result["consensus"]["no_vig_probability"]
        self.assertAlmostEqual(no_vig["consensus_over"] + no_vig["consensus_under"], 1.0, places=9)

    def test_21_consensus_reports_dispersion(self):
        result = self.build()
        dispersion = result["consensus"]["no_vig_probability"]["over_dispersion_percentage_points"]
        self.assertGreater(dispersion["range"], 0.0)
        self.assertGreater(dispersion["population_stddev"], 0.0)

    def test_22_consensus_reports_average_book_margin(self):
        result = self.build()
        margin = result["consensus"]["sportsbook_margin"]["probability"]
        self.assertEqual(margin["count"], 3)
        self.assertGreater(margin["mean"], 0.0)

    def test_23_quote_capture_span(self):
        result = self.build()
        span = result["consensus"]["quote_capture_span"]
        self.assertEqual(span["span_minutes"], 2.0)

    def test_24_stale_quote_is_excluded_by_default(self):
        rows = [
            quote("OldBook", 200, -300, "2026-08-26T17:30:00Z"),
            quote("DraftKings", -110, -110, "2026-08-26T17:58:00Z"),
        ]
        result = self.build(rows)
        self.assertEqual(result["quote_set"]["eligible_quote_count"], 1)
        self.assertEqual(result["quote_set"]["excluded_quote_count"], 1)
        self.assertFalse(result["consensus"]["available"])

    def test_25_stale_quote_can_be_retained_explicitly(self):
        rows = [
            quote("OldBook", 200, -300, "2026-08-26T17:30:00Z"),
            quote("DraftKings", -110, -110, "2026-08-26T17:58:00Z"),
        ]
        result = self.build(rows, exclude_stale_quotes=False)
        self.assertEqual(result["quote_set"]["eligible_quote_count"], 2)
        self.assertTrue(result["consensus"]["available"])

    def test_26_all_stale_quotes_block_when_excluded(self):
        rows = [
            quote("A", -110, -110, "2026-08-26T17:30:00Z"),
            quote("B", -110, -110, "2026-08-26T17:35:00Z"),
        ]
        with self.assertRaises(h.WNBAMultiSportsbookNotReadyError):
            self.build(rows)

    def test_27_stale_best_price_cannot_win_when_excluded(self):
        rows = [
            quote("OldBest", 250, -400, "2026-08-26T17:30:00Z"),
            quote("FreshA", -110, -110, "2026-08-26T17:58:00Z"),
            quote("FreshB", -105, -115, "2026-08-26T17:59:00Z"),
        ]
        result = self.build(rows)
        self.assertNotIn("OldBest", [x["sportsbook"] for x in result["best_prices"]["over"]["sportsbooks"]])

    def test_28_future_quote_beyond_tolerance_fails(self):
        rows = [
            quote("A", captured="2026-08-26T18:03:00Z"),
            quote("B", captured="2026-08-26T17:59:00Z"),
        ]
        with self.assertRaises(ValueError):
            self.build(rows)

    def test_29_base_ev_best_quote_is_fanduel_over(self):
        result = self.build()
        best = result["decision_summary"]["best_positive_base_ev_quote"]
        self.assertEqual((best["sportsbook"], best["side"]), ("FanDuel", "over"))
        self.assertAlmostEqual(best["base_ev_percentage"], 10.0, places=6)

    def test_30_risk_adjusted_value_not_forced_when_negative(self):
        result = self.build()
        self.assertIsNone(result["decision_summary"]["best_positive_risk_adjusted_ev_quote"])
        self.assertTrue(result["decision_summary"]["no_risk_adjusted_value_quote_forced_when_all_nonpositive"])

    def test_31_no_base_value_is_forced_when_model_is_balanced_and_prices_bad(self):
        threshold = threshold_fixture((0.45, 0.45, 0.45))
        rows = [quote("A", -150, -150), quote("B", -160, -140)]
        result = self.build(rows, threshold=threshold)
        self.assertIsNone(result["decision_summary"]["best_positive_base_ev_quote"])

    def test_32_playable_books_base_contains_positive_price_thresholds(self):
        result = self.build()
        names = [x["sportsbook"] for x in result["playable_books"]["over"]["base_scenario"]]
        self.assertEqual(names, ["FanDuel", "BetMGM", "DraftKings"])

    def test_33_conservative_playable_books_are_empty_for_fixture(self):
        result = self.build()
        self.assertEqual(result["playable_books"]["over"]["all_scenarios_count"], 0)

    def test_34_minimum_required_ev_tightens_playable_books(self):
        result = self.build(minimum_required_ev=0.08)
        names = [x["sportsbook"] for x in result["playable_books"]["over"]["base_scenario"]]
        self.assertEqual(names, ["FanDuel"])

    def test_35_model_vs_consensus_edge_is_exposed(self):
        result = self.build()
        edge = result["model_vs_market_consensus"]["model_edge_vs_consensus_no_vig"]
        self.assertGreater(edge["over_probability"], 0.0)
        self.assertLess(edge["under_probability"], 0.0)

    def test_36_model_favored_side(self):
        result = self.build()
        self.assertEqual(result["model_vs_market_consensus"]["model_favored_side"], "over")

    def test_37_consensus_favored_side(self):
        result = self.build()
        self.assertEqual(result["model_vs_market_consensus"]["market_consensus_favored_side"], "under")

    def test_38_input_order_does_not_change_fingerprint(self):
        rows = three_quotes()
        first = self.build(rows)
        second = self.build(list(reversed(rows)))
        self.assertEqual(
            first["market_consensus_fingerprint_sha256"],
            second["market_consensus_fingerprint_sha256"],
        )

    def test_39_price_change_changes_fingerprint(self):
        first = self.build()
        rows = three_quotes()
        rows[0] = quote("DraftKings", -105, -115, "2026-08-26T17:58:00Z")
        second = self.build(rows)
        self.assertNotEqual(
            first["market_consensus_fingerprint_sha256"],
            second["market_consensus_fingerprint_sha256"],
        )

    def test_40_capture_timestamp_change_changes_fingerprint(self):
        first = self.build()
        rows = three_quotes()
        rows[0] = quote("DraftKings", -110, -110, "2026-08-26T17:57:30Z")
        second = self.build(rows)
        self.assertNotEqual(
            first["market_consensus_fingerprint_sha256"],
            second["market_consensus_fingerprint_sha256"],
        )

    def test_41_evaluation_clock_with_same_freshness_state_does_not_change_fingerprint(self):
        first = self.build(evaluated_at=EVALUATED)
        second = self.build(evaluated_at=datetime(2026, 8, 26, 18, 1, tzinfo=timezone.utc))
        self.assertEqual(
            first["market_consensus_fingerprint_sha256"],
            second["market_consensus_fingerprint_sha256"],
        )

    def test_42_crossing_stale_boundary_changes_fingerprint_when_other_books_remain(self):
        rows = [
            quote("A", -110, -110, "2026-08-26T17:50:30Z"),
            quote("B", -110, -110, "2026-08-26T17:59:00Z"),
            quote("C", -110, -110, "2026-08-26T17:59:30Z"),
        ]
        first = self.build(rows, evaluated_at=EVALUATED)
        second = self.build(rows, evaluated_at=datetime(2026, 8, 26, 18, 1, tzinfo=timezone.utc))
        self.assertNotEqual(
            first["market_consensus_fingerprint_sha256"],
            second["market_consensus_fingerprint_sha256"],
        )

    def test_43_step_5f_fingerprint_change_changes_5h_fingerprint(self):
        first_threshold = threshold_fixture()
        second_threshold = threshold_fixture()
        second_threshold["probability_fingerprint_sha256"] = "c" * 64
        first = self.build(threshold=first_threshold)
        second = self.build(threshold=second_threshold)
        self.assertNotEqual(
            first["market_consensus_fingerprint_sha256"],
            second["market_consensus_fingerprint_sha256"],
        )

    def test_44_quote_audit_is_sorted(self):
        result = self.build()
        self.assertEqual(
            [row["sportsbook"] for row in result["quote_set"]["quotes"]],
            ["BetMGM", "DraftKings", "FanDuel"],
        )

    def test_45_output_marks_quotes_caller_supplied(self):
        result = self.build()
        self.assertTrue(result["market_semantics"]["all_quotes_are_caller_supplied_not_fetched_or_verified"])

    def test_46_no_handle_weighting_is_invented(self):
        result = self.build()
        self.assertTrue(result["market_semantics"]["no_handle_or_liquidity_weighting_invented"])
        self.assertEqual(result["model_config"]["book_weighting"], "equal_unweighted")

    def test_47_no_scenario_weights_are_invented(self):
        result = self.build()
        self.assertIsNone(result["model_config"]["scenario_weights"])
        self.assertTrue(result["guardrails"]["no_scenario_weights_invented"])

    def test_48_no_bet_size_or_kelly_created(self):
        result = self.build()
        self.assertTrue(result["guardrails"]["no_kelly_stake_created"])
        self.assertTrue(result["guardrails"]["no_bet_size_created"])

    def test_49_duplicate_books_cannot_overweight_consensus(self):
        with self.assertRaises(ValueError):
            self.build([quote("A"), quote("a")])

    def test_50_one_fresh_book_keeps_best_price_but_disables_multibook_consensus(self):
        rows = [
            quote("Fresh", -110, -110, "2026-08-26T17:59:00Z"),
            quote("Old", 200, -300, "2026-08-26T17:20:00Z"),
        ]
        result = self.build(rows)
        self.assertIsNotNone(result["best_prices"]["over"])
        self.assertFalse(result["decision_summary"]["multi_book_consensus_available"])

    def test_51_wrong_step_5g_model_version_fails_closed(self):
        original = h.compare_threshold_to_sportsbook_market
        def bad(*args, **kwargs):
            result = original(*args, **kwargs)
            result["model_version"] = "wrong"
            return result
        with patch.object(h, "compare_threshold_to_sportsbook_market", side_effect=bad):
            with self.assertRaises(h.WNBAMultiSportsbookUpstreamError):
                self.build()

    def test_52_wrong_step_5f_reference_from_5g_fails_closed(self):
        original = h.compare_threshold_to_sportsbook_market
        def bad(*args, **kwargs):
            result = original(*args, **kwargs)
            result["step_5f_reference"]["probability_fingerprint_sha256"] = "d" * 64
            return result
        with patch.object(h, "compare_threshold_to_sportsbook_market", side_effect=bad):
            with self.assertRaises(h.WNBAMultiSportsbookUpstreamError):
                self.build()

    def test_53_wrong_market_input_identity_fails_closed(self):
        original = h.compare_threshold_to_sportsbook_market
        def bad(*args, **kwargs):
            result = original(*args, **kwargs)
            result["market_input"]["over_odds"] = -999
            return result
        with patch.object(h, "compare_threshold_to_sportsbook_market", side_effect=bad):
            with self.assertRaises(h.WNBAMultiSportsbookUpstreamError):
                self.build()

    def test_54_cross_book_team_identity_mismatch_fails_closed(self):
        original = h.compare_threshold_to_sportsbook_market
        def bad(*args, **kwargs):
            result = original(*args, **kwargs)
            if kwargs["sportsbook"] == "FanDuel":
                result["team_key"] = "SEA"
            return result
        with patch.object(h, "compare_threshold_to_sportsbook_market", side_effect=bad):
            with self.assertRaises(h.WNBAMultiSportsbookUpstreamError):
                self.build()

    def test_55_wrapper_calls_step_5f_once_for_all_books(self):
        threshold = threshold_fixture()
        with patch.object(h, "get_player_game_prop_threshold_probability", return_value=threshold) as getter:
            result = h.get_player_game_multi_sportsbook_market_consensus(
                123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(),
                exclude_stale_quotes=False,
            )
        getter.assert_called_once()
        self.assertEqual(result["quote_set"]["input_quote_count"], 3)

    def test_56_wrapper_passes_projection_controls(self):
        threshold = threshold_fixture()
        with patch.object(h, "get_player_game_prop_threshold_probability", return_value=threshold) as getter:
            h.get_player_game_multi_sportsbook_market_consensus(
                123,
                "1022600001",
                2026,
                stat="pts",
                line=19.5,
                quotes=three_quotes(),
                season_type="Playoffs",
                last_n_games=7,
                distribution_last_n_games=12,
                simulation_count=100000,
                batch_size=10000,
                random_seed=42,
                require_current_availability=False,
                max_snapshot_age_minutes=30,
                require_convergence=False,
                exclude_stale_quotes=False,
            )
        kwargs = getter.call_args.kwargs
        self.assertEqual(kwargs["stat"], "points")
        self.assertEqual(kwargs["season_type"], "Playoffs")
        self.assertEqual(kwargs["last_n_games"], 7)
        self.assertEqual(kwargs["distribution_last_n_games"], 12)
        self.assertEqual(kwargs["simulation_count"], 100000)
        self.assertEqual(kwargs["batch_size"], 10000)
        self.assertEqual(kwargs["random_seed"], 42)
        self.assertFalse(kwargs["require_current_availability"])
        self.assertEqual(kwargs["max_snapshot_age_minutes"], 30)
        self.assertFalse(kwargs["require_convergence"])

    def test_57_wrapper_rejects_invalid_player_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    0, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes()
                )
            getter.assert_not_called()

    def test_58_wrapper_rejects_invalid_game_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "bad", 2026, stat="points", line=19.5, quotes=three_quotes()
                )
            getter.assert_not_called()

    def test_59_wrapper_rejects_invalid_stat_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="steals", line=1.5, quotes=three_quotes()
                )
            getter.assert_not_called()

    def test_60_wrapper_rejects_invalid_line_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=-1, quotes=three_quotes()
                )
            getter.assert_not_called()

    def test_61_wrapper_rejects_duplicate_books_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123,
                    "1022600001",
                    2026,
                    stat="points",
                    line=19.5,
                    quotes=[quote("A"), quote("a")],
                )
            getter.assert_not_called()

    def test_62_wrapper_rejects_bad_last_n_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), last_n_games=0
                )
            getter.assert_not_called()

    def test_63_wrapper_rejects_bad_distribution_window_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), distribution_last_n_games=51
                )
            getter.assert_not_called()

    def test_64_wrapper_rejects_bad_simulation_count_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), simulation_count=999
                )
            getter.assert_not_called()

    def test_65_wrapper_rejects_bad_batch_size_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), batch_size=999
                )
            getter.assert_not_called()

    def test_66_wrapper_rejects_bad_seed_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), random_seed=-1
                )
            getter.assert_not_called()

    def test_67_wrapper_rejects_bad_boolean_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), require_convergence="yes"
                )
            getter.assert_not_called()

    def test_68_wrapper_rejects_bad_snapshot_age_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), max_snapshot_age_minutes=0
                )
            getter.assert_not_called()

    def test_69_wrapper_rejects_bad_minimum_ev_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), minimum_required_ev=1.1
                )
            getter.assert_not_called()

    def test_70_wrapper_rejects_bad_market_age_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), max_market_age_minutes=0
                )
            getter.assert_not_called()

    def test_71_wrapper_rejects_bad_exclude_stale_boolean_before_upstream(self):
        with patch.object(h, "get_player_game_prop_threshold_probability") as getter:
            with self.assertRaises(ValueError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes(), exclude_stale_quotes="yes"
                )
            getter.assert_not_called()

    def test_72_wrapper_maps_not_found(self):
        with patch.object(
            h,
            "get_player_game_prop_threshold_probability",
            side_effect=h.WNBAPropThresholdNotFoundError("missing"),
        ):
            with self.assertRaises(h.WNBAMultiSportsbookNotFoundError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes()
                )

    def test_73_wrapper_maps_not_ready(self):
        with patch.object(
            h,
            "get_player_game_prop_threshold_probability",
            side_effect=h.WNBAPropThresholdNotReadyError("not ready"),
        ):
            with self.assertRaises(h.WNBAMultiSportsbookNotReadyError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes()
                )

    def test_74_wrapper_maps_model_input(self):
        with patch.object(
            h,
            "get_player_game_prop_threshold_probability",
            side_effect=h.WNBAPropThresholdModelInputError("bad model"),
        ):
            with self.assertRaises(h.WNBAMultiSportsbookModelInputError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes()
                )

    def test_75_wrapper_maps_upstream(self):
        with patch.object(
            h,
            "get_player_game_prop_threshold_probability",
            side_effect=h.WNBAPropThresholdUpstreamError("upstream"),
        ):
            with self.assertRaises(h.WNBAMultiSportsbookUpstreamError):
                h.get_player_game_multi_sportsbook_market_consensus(
                    123, "1022600001", 2026, stat="points", line=19.5, quotes=three_quotes()
                )

    def test_76_consensus_uses_eligible_quotes_only(self):
        rows = [
            quote("FreshA", -110, -110, "2026-08-26T17:59:00Z"),
            quote("FreshB", -105, -115, "2026-08-26T17:58:00Z"),
            quote("Stale", 300, -500, "2026-08-26T17:20:00Z"),
        ]
        result = self.build(rows)
        self.assertEqual(result["consensus"]["eligible_book_count"], 2)
        self.assertNotIn("Stale", result["consensus"]["sportsbooks"])

    def test_77_best_price_and_best_ev_use_same_eligible_pool(self):
        rows = [
            quote("FreshA", -110, -110, "2026-08-26T17:59:00Z"),
            quote("FreshB", 100, -120, "2026-08-26T17:58:00Z"),
            quote("StaleBest", 300, -500, "2026-08-26T17:20:00Z"),
        ]
        result = self.build(rows)
        self.assertEqual(result["best_prices"]["over"]["sportsbooks"][0]["sportsbook"], "FreshB")
        self.assertEqual(result["decision_summary"]["best_positive_base_ev_quote"]["sportsbook"], "FreshB")

    def test_78_market_analysis_fingerprint_is_present_for_each_quote(self):
        result = self.build()
        for row in result["quote_set"]["quotes"]:
            self.assertTrue(row["market_analysis_fingerprint_sha256"])

    def test_79_model_config_records_stale_policy(self):
        result = self.build()
        self.assertTrue(result["model_config"]["exclude_stale_quotes"])
        self.assertEqual(result["model_config"]["max_market_age_minutes"], 10)

    def test_80_primary_prop_is_unchanged(self):
        threshold = threshold_fixture()
        result = self.build(threshold=threshold)
        self.assertEqual(result["prop"], {
            "stat": "points",
            "line": 19.5,
            "same_threshold_as_step_5f": True,
            "sportsbook_market_does_not_change_projection": True,
        })


if __name__ == "__main__":
    unittest.main()
