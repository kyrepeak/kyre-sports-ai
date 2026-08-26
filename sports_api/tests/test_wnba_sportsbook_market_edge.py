import unittest
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from sports_api import wnba_sportsbook_market_edge as m
from sports_api.wnba_prop_threshold_probability import (
    WNBAPropThresholdModelInputError,
    WNBAPropThresholdNotFoundError,
    WNBAPropThresholdNotReadyError,
    WNBAPropThresholdUpstreamError,
)


GAME_ID = "1022600300"
PLAYER_ID = 12345
TEAM = "chicago-sky"
OPPONENT = "connecticut-sun"
NOW = datetime(2026, 8, 26, 17, 50, 0, tzinfo=timezone.utc)
CAPTURED = "2026-08-26T17:45:00Z"


def probability_record(value):
    return {"probability": value}


def fair_record(value):
    return {
        "available": True,
        "fair_probability": value,
        "fair_percentage": value * 100,
    }


def scenario(name, over, under, push, *, stat="points", line=19.0):
    resolved = over + under
    return {
        "conditional_scenario": name,
        "stat": stat,
        "line": line,
        "raw_probabilities": {
            "over": probability_record(over),
            "under": probability_record(under),
            "push": probability_record(push),
        },
        "fair_odds": {
            "over": fair_record(over / resolved),
            "under": fair_record(under / resolved),
            "push_probability": push,
        },
    }


def threshold(*, ready=True, stat="points", line=19.0):
    results = {
        "low": scenario("low", 0.36, 0.54, 0.10, stat=stat, line=line),
        "base": scenario("base", 0.495, 0.405, 0.10, stat=stat, line=line),
        "high": scenario("high", 0.585, 0.315, 0.10, stat=stat, line=line),
    }
    model_config = {
        "model_version": m.THRESHOLD_MODEL_VERSION,
        "stat": stat,
        "line": line,
        "primary_scenario": "base",
    }
    sensitivity = {
        "raw_over_probability_by_scenario": {
            key: results[key]["raw_probabilities"]["over"]["probability"]
            for key in m.SCENARIO_KEYS
        }
    }
    step_5e = {
        "model_version": "wnba_step_5e_correlated_monte_carlo_v1",
        "simulation_id": "wnba-5e-test",
        "simulation_fingerprint_sha256": "e" * 64,
    }
    payload = {
        "step_5e_simulation_fingerprint_sha256": step_5e["simulation_fingerprint_sha256"],
        "model_config": model_config,
        "conditional_threshold_results": results,
        "scenario_sensitivity": sensitivity,
    }
    fingerprint = m._canonical_hash(payload)
    return {
        "source": "Step 5F fixture",
        "model_version": m.THRESHOLD_MODEL_VERSION,
        "probability_id": "wnba-5f-test",
        "probability_fingerprint_sha256": fingerprint,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM,
        "opponent_team_key": OPPONENT,
        "prop": {
            "stat": stat,
            "line": line,
            "line_is_integer": float(line).is_integer(),
            "line_is_threshold_only": True,
            "line_does_not_change_basketball_projection": True,
        },
        "step_5e_reference": step_5e,
        "snapshot_reference": {
            "snapshot_id": "wnba-4w-test",
            "content_sha256": "a" * 64,
            "game_id": GAME_ID,
            "player_id": PLAYER_ID,
        },
        "conditional_scenario_results": results,
        "primary_result": deepcopy(results["base"]),
        "scenario_sensitivity": sensitivity,
        "numerical_readiness": {
            "ready_for_fair_odds": ready,
            "strict_numerical_readiness_passed": ready,
        },
        "model_config": model_config,
    }


def compare(**kwargs):
    params = {
        "sportsbook": "DraftKings",
        "over_odds": -110,
        "under_odds": -110,
        "market_captured_at_utc": CAPTURED,
        "minimum_required_ev": 0.0,
        "max_market_age_minutes": 10,
        "require_fresh_market": True,
        "evaluated_at": NOW,
    }
    params.update(kwargs)
    return m.compare_threshold_to_sportsbook_market(threshold(), **params)


class WNBASportsbookMarketEdgeTests(unittest.TestCase):
    def test_negative_american_to_decimal(self):
        self.assertAlmostEqual(m._american_to_decimal(-110), 1.9090909091, places=9)

    def test_positive_american_to_decimal(self):
        self.assertEqual(m._american_to_decimal(125), 2.25)

    def test_negative_american_implied_probability(self):
        self.assertAlmostEqual(m._american_implied_probability(-110), 0.5238095238, places=9)

    def test_positive_american_implied_probability(self):
        self.assertAlmostEqual(m._american_implied_probability(125), 0.4444444444, places=9)

    def test_decimal_to_american_even_money(self):
        self.assertEqual(m._decimal_to_american(2.0), 100)

    def test_decimal_to_american_favorite(self):
        self.assertEqual(m._decimal_to_american(1.8), -125)

    def test_decimal_to_american_underdog(self):
        self.assertEqual(m._decimal_to_american(2.25), 125)

    def test_even_minus_110_market_has_fifty_fifty_no_vig(self):
        quote = m._market_quote(-110, -110)
        self.assertEqual(quote["over"]["no_vig_probability"], 0.5)
        self.assertEqual(quote["under"]["no_vig_probability"], 0.5)
        self.assertEqual(quote["no_vig_probability_sum"], 1.0)

    def test_minus_110_market_margin(self):
        quote = m._market_quote(-110, -110)
        self.assertAlmostEqual(quote["sportsbook_margin_percentage"], 4.761905, places=6)

    def test_unequal_market_no_vig_normalizes(self):
        quote = m._market_quote(-120, 100)
        self.assertAlmostEqual(quote["over"]["no_vig_probability"], 0.5217391304, places=9)
        self.assertAlmostEqual(quote["under"]["no_vig_probability"], 0.4782608696, places=9)

    def test_base_over_resolved_fair_probability_is_fifty_five_percent(self):
        result = compare()
        fair = result["conditional_market_results"]["base"]["over"]["model"]["resolved_fair_win_probability"]
        self.assertEqual(fair, 0.55)

    def test_base_over_no_vig_edge_is_five_points(self):
        result = compare()
        edge = result["conditional_market_results"]["base"]["over"]["edge"]["vs_no_vig_market_percentage_points"]
        self.assertEqual(edge, 5.0)

    def test_base_over_raw_implied_edge_accounts_for_vig(self):
        result = compare()
        edge = result["conditional_market_results"]["base"]["over"]["edge"]["vs_raw_sportsbook_implied_percentage_points"]
        self.assertAlmostEqual(edge, 2.619048, places=6)

    def test_base_over_ev_uses_raw_push_aware_probabilities(self):
        result = compare()
        ev = result["conditional_market_results"]["base"]["over"]["expected_value"]["net_profit_per_unit_staked"]
        self.assertAlmostEqual(ev, 0.045, places=8)

    def test_base_over_ev_percentage(self):
        result = compare()
        self.assertAlmostEqual(result["side_summaries"]["over"]["base_ev_percentage"], 4.5, places=6)

    def test_push_reduces_ev_magnitude_with_same_resolved_edge(self):
        profit = m._american_to_decimal(-110) - 1.0
        no_push_ev = 0.55 * profit - 0.45
        push_ev = 0.495 * profit - 0.405
        self.assertAlmostEqual(no_push_ev, 0.05, places=9)
        self.assertAlmostEqual(push_ev, 0.045, places=9)

    def test_under_base_ev_is_negative(self):
        result = compare()
        self.assertLess(result["side_summaries"]["under"]["base_ev_per_unit"], 0.0)

    def test_primary_base_value_side_is_over(self):
        result = compare()
        self.assertEqual(result["decision_summary"]["primary_base_ev_side"], "over")

    def test_risk_adjusted_ev_is_worst_conditional_scenario(self):
        result = compare()
        evs = result["side_summaries"]["over"]["conditional_ev_by_scenario"]
        self.assertEqual(result["side_summaries"]["over"]["risk_adjusted_ev_per_unit"], min(evs.values()))

    def test_risk_adjusted_method_does_not_invent_scenario_weights(self):
        result = compare()
        self.assertEqual(
            result["side_summaries"]["over"]["risk_adjusted_ev_method"],
            "minimum_low_base_high_conditional_scenario_ev_no_scenario_weights",
        )
        self.assertTrue(result["guardrails"]["no_scenario_weights_invented"])

    def test_conservative_positive_ev_side_is_none_when_low_scenario_loses(self):
        result = compare()
        self.assertIsNone(result["decision_summary"]["conservative_positive_ev_side"])

    def test_no_side_forced_when_both_base_evs_nonpositive(self):
        report = threshold()
        result = m.compare_threshold_to_sportsbook_market(
            report,
            sportsbook="TestBook",
            over_odds=-200,
            under_odds=-200,
            market_captured_at_utc=CAPTURED,
            evaluated_at=NOW,
        )
        self.assertIsNone(result["decision_summary"]["primary_base_ev_side"])
        self.assertTrue(result["decision_summary"]["no_side_forced_when_both_base_evs_nonpositive"])

    def test_zero_ev_base_price_threshold_matches_resolved_fair_probability(self):
        result = compare()
        price = result["side_summaries"]["over"]["price_thresholds"]
        self.assertAlmostEqual(price["base_minimum_acceptable_decimal_odds"], 1 / 0.55, places=7)
        self.assertEqual(price["base_minimum_acceptable_american_odds"], -122)

    def test_positive_minimum_ev_requires_better_price(self):
        zero = compare(minimum_required_ev=0.0)
        five = compare(minimum_required_ev=0.05)
        self.assertGreater(
            five["side_summaries"]["over"]["price_thresholds"]["base_minimum_acceptable_decimal_odds"],
            zero["side_summaries"]["over"]["price_thresholds"]["base_minimum_acceptable_decimal_odds"],
        )

    def test_offered_minus_110_meets_base_zero_ev_threshold(self):
        result = compare()
        self.assertTrue(
            result["side_summaries"]["over"]["price_thresholds"]["offered_price_meets_base_minimum_required_ev"]
        )

    def test_offered_minus_110_does_not_meet_all_scenarios_zero_ev_threshold(self):
        result = compare()
        self.assertFalse(
            result["side_summaries"]["over"]["price_thresholds"]["offered_price_meets_minimum_required_ev_in_all_scenarios"]
        )

    def test_conservative_required_price_is_maximum_scenario_decimal_threshold(self):
        result = compare()
        prices = result["side_summaries"]["over"]["price_thresholds"]
        self.assertEqual(
            prices["conservative_all_scenarios_minimum_acceptable_decimal_odds"],
            max(prices["required_decimal_odds_by_scenario"].values()),
        )

    def test_market_quote_is_explicitly_caller_supplied(self):
        result = compare()
        self.assertEqual(result["market_input"]["source_mode"], "caller_supplied_two_way_quote")
        self.assertTrue(result["market_semantics"]["sportsbook_quote_is_caller_supplied_not_fetched_or_verified"])

    def test_market_price_does_not_change_projection_guardrail(self):
        result = compare()
        self.assertTrue(result["prop"]["sportsbook_market_does_not_change_projection"])
        self.assertTrue(result["guardrails"]["sportsbook_price_cannot_change_monte_carlo_draws"])
        self.assertTrue(result["guardrails"]["sportsbook_price_cannot_change_step_5f_probability"])

    def test_no_kelly_or_bet_size_created(self):
        result = compare()
        self.assertTrue(result["guardrails"]["no_kelly_stake_created"])
        self.assertTrue(result["guardrails"]["no_bet_size_created"])

    def test_fresh_market_status(self):
        result = compare()
        self.assertEqual(result["market_freshness"]["status"], "fresh")
        self.assertEqual(result["market_freshness"]["market_age_minutes"], 5.0)

    def test_stale_market_blocks_when_required(self):
        with self.assertRaisesRegex(m.WNBASportsbookMarketNotReadyError, "stale"):
            m.compare_threshold_to_sportsbook_market(
                threshold(),
                sportsbook="Book",
                over_odds=-110,
                under_odds=-110,
                market_captured_at_utc="2026-08-26T17:00:00Z",
                max_market_age_minutes=10,
                require_fresh_market=True,
                evaluated_at=NOW,
            )

    def test_stale_market_can_be_returned_when_freshness_not_required(self):
        result = m.compare_threshold_to_sportsbook_market(
            threshold(),
            sportsbook="Book",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-26T17:00:00Z",
            max_market_age_minutes=10,
            require_fresh_market=False,
            evaluated_at=NOW,
        )
        self.assertTrue(result["market_freshness"]["stale"])

    def test_market_timestamp_more_than_two_minutes_future_fails(self):
        future = (NOW + timedelta(seconds=121)).isoformat()
        with self.assertRaisesRegex(ValueError, "120 seconds"):
            m.compare_threshold_to_sportsbook_market(
                threshold(),
                sportsbook="Book",
                over_odds=-110,
                under_odds=-110,
                market_captured_at_utc=future,
                evaluated_at=NOW,
            )

    def test_market_timestamp_z_is_timezone_aware(self):
        parsed = m._parse_market_timestamp("2026-08-26T17:45:00Z")
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_market_timestamp_offset_normalizes_to_utc(self):
        parsed = m._parse_market_timestamp("2026-08-26T10:45:00-07:00")
        self.assertEqual(parsed, datetime(2026, 8, 26, 17, 45, tzinfo=timezone.utc))

    def test_naive_market_timestamp_fails(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            m._parse_market_timestamp("2026-08-26T17:45:00")

    def test_empty_sportsbook_fails(self):
        with self.assertRaisesRegex(ValueError, "sportsbook"):
            m._sportsbook("")

    def test_long_sportsbook_fails(self):
        with self.assertRaisesRegex(ValueError, "80"):
            m._sportsbook("x" * 81)

    def test_invalid_american_odds_inside_minus_100_plus_100_fails(self):
        with self.assertRaisesRegex(ValueError, "absolute value"):
            m._american_odds(-99, "over_odds")

    def test_non_integer_american_odds_fails(self):
        with self.assertRaisesRegex(ValueError, "integer American"):
            m._american_odds(-110.5, "over_odds")

    def test_minus_100_is_accepted(self):
        self.assertEqual(m._american_odds(-100, "over_odds"), -100)

    def test_plus_100_is_accepted(self):
        self.assertEqual(m._american_odds(100, "over_odds"), 100)

    def test_invalid_threshold_model_version_fails_closed(self):
        report = threshold()
        report["model_version"] = "wrong"
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "unexpected Step 5F"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_threshold_fingerprint_tamper_fails_closed(self):
        report = threshold()
        report["conditional_scenario_results"]["base"]["raw_probabilities"]["over"]["probability"] += 0.01
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "fingerprint"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_primary_result_must_match_base(self):
        report = threshold()
        report["primary_result"]["stat"] = "rebounds"
        report["probability_fingerprint_sha256"] = m._canonical_hash({
            "step_5e_simulation_fingerprint_sha256": report["step_5e_reference"]["simulation_fingerprint_sha256"],
            "model_config": report["model_config"],
            "conditional_threshold_results": report["conditional_scenario_results"],
            "scenario_sensitivity": report["scenario_sensitivity"],
        })
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "primary result"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_not_ready_threshold_blocks_market_comparison(self):
        with self.assertRaisesRegex(m.WNBASportsbookMarketNotReadyError, "not ready"):
            m.compare_threshold_to_sportsbook_market(threshold(ready=False), sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_raw_probabilities_must_sum_to_one(self):
        report = threshold()
        report["conditional_scenario_results"]["base"]["raw_probabilities"]["push"]["probability"] = 0.11
        report["primary_result"] = deepcopy(report["conditional_scenario_results"]["base"])
        report["probability_fingerprint_sha256"] = m._canonical_hash({
            "step_5e_simulation_fingerprint_sha256": report["step_5e_reference"]["simulation_fingerprint_sha256"],
            "model_config": report["model_config"],
            "conditional_threshold_results": report["conditional_scenario_results"],
            "scenario_sensitivity": report["scenario_sensitivity"],
        })
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "sum to one"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_resolved_fair_probability_must_match_win_over_resolved(self):
        report = threshold()
        report["conditional_scenario_results"]["base"]["fair_odds"]["over"]["fair_probability"] = 0.60
        report["primary_result"] = deepcopy(report["conditional_scenario_results"]["base"])
        report["probability_fingerprint_sha256"] = m._canonical_hash({
            "step_5e_simulation_fingerprint_sha256": report["step_5e_reference"]["simulation_fingerprint_sha256"],
            "model_config": report["model_config"],
            "conditional_threshold_results": report["conditional_scenario_results"],
            "scenario_sensitivity": report["scenario_sensitivity"],
        })
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "resolved fair"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_unavailable_fair_probability_blocks(self):
        report = threshold()
        report["conditional_scenario_results"]["low"]["fair_odds"]["over"]["available"] = False
        report["probability_fingerprint_sha256"] = m._canonical_hash({
            "step_5e_simulation_fingerprint_sha256": report["step_5e_reference"]["simulation_fingerprint_sha256"],
            "model_config": report["model_config"],
            "conditional_threshold_results": report["conditional_scenario_results"],
            "scenario_sensitivity": report["scenario_sensitivity"],
        })
        with self.assertRaisesRegex(m.WNBASportsbookMarketNotReadyError, "unavailable"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_scenario_prop_identity_mismatch_fails(self):
        report = threshold()
        report["conditional_scenario_results"]["high"]["line"] = 20.0
        report["probability_fingerprint_sha256"] = m._canonical_hash({
            "step_5e_simulation_fingerprint_sha256": report["step_5e_reference"]["simulation_fingerprint_sha256"],
            "model_config": report["model_config"],
            "conditional_threshold_results": report["conditional_scenario_results"],
            "scenario_sensitivity": report["scenario_sensitivity"],
        })
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "prop identity"):
            m.compare_threshold_to_sportsbook_market(report, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED, evaluated_at=NOW)

    def test_market_fingerprint_is_deterministic_for_same_math_content(self):
        first = compare(evaluated_at=NOW)
        second = compare(evaluated_at=NOW + timedelta(seconds=30))
        self.assertEqual(first["market_analysis_fingerprint_sha256"], second["market_analysis_fingerprint_sha256"])
        self.assertEqual(first["market_analysis_id"], second["market_analysis_id"])

    def test_market_fingerprint_changes_with_over_price(self):
        first = compare()
        second = compare(over_odds=-105)
        self.assertNotEqual(first["market_analysis_fingerprint_sha256"], second["market_analysis_fingerprint_sha256"])

    def test_market_fingerprint_changes_with_under_price(self):
        first = compare()
        second = compare(under_odds=-105)
        self.assertNotEqual(first["market_analysis_fingerprint_sha256"], second["market_analysis_fingerprint_sha256"])

    def test_market_fingerprint_changes_with_sportsbook(self):
        first = compare()
        second = compare(sportsbook="Caesars")
        self.assertNotEqual(first["market_analysis_fingerprint_sha256"], second["market_analysis_fingerprint_sha256"])

    def test_market_fingerprint_changes_with_capture_timestamp(self):
        first = compare()
        second = compare(market_captured_at_utc="2026-08-26T17:46:00Z")
        self.assertNotEqual(first["market_analysis_fingerprint_sha256"], second["market_analysis_fingerprint_sha256"])

    def test_market_fingerprint_changes_with_required_ev(self):
        first = compare(minimum_required_ev=0.0)
        second = compare(minimum_required_ev=0.05)
        self.assertNotEqual(first["market_analysis_fingerprint_sha256"], second["market_analysis_fingerprint_sha256"])

    def test_minimum_required_ev_validation(self):
        with self.assertRaisesRegex(ValueError, "0 through 1.0"):
            m._minimum_required_ev(-0.01)
        with self.assertRaisesRegex(ValueError, "0 through 1.0"):
            m._minimum_required_ev(1.01)

    def test_market_age_limit_validation(self):
        with self.assertRaisesRegex(ValueError, "1 through 1440"):
            m._market_age_limit(0)
        with self.assertRaisesRegex(ValueError, "1 through 1440"):
            m._market_age_limit(1441)

    def test_stat_alias_pts(self):
        self.assertEqual(m._stat("PTS"), "points")

    def test_stat_alias_reb(self):
        self.assertEqual(m._stat("REB"), "rebounds")

    def test_stat_alias_ast(self):
        self.assertEqual(m._stat("AST"), "assists")

    @patch("sports_api.wnba_sportsbook_market_edge.compare_threshold_to_sportsbook_market")
    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_wrapper_passes_exact_threshold_and_market_parameters(self, threshold_getter, comparer):
        threshold_getter.return_value = threshold()
        comparer.return_value = {"ok": True}
        result = m.get_player_game_sportsbook_market_edge(
            PLAYER_ID,
            GAME_ID,
            2026,
            stat="points",
            line=19,
            sportsbook="DraftKings",
            over_odds=-110,
            under_odds=-112,
            market_captured_at_utc=CAPTURED,
            minimum_required_ev=0.02,
            max_market_age_minutes=15,
            require_fresh_market=False,
        )
        self.assertEqual(result, {"ok": True})
        threshold_getter.assert_called_once_with(
            PLAYER_ID,
            GAME_ID,
            2026,
            stat="points",
            line=19.0,
            season_type="Regular Season",
            last_n_games=5,
            distribution_last_n_games=10,
            simulation_count=m.DEFAULT_SIMULATION_COUNT,
            batch_size=m.DEFAULT_BATCH_SIZE,
            random_seed=m.DEFAULT_RANDOM_SEED,
            require_current_availability=True,
            max_snapshot_age_minutes=15,
            require_convergence=True,
        )
        comparer.assert_called_once_with(
            threshold_getter.return_value,
            sportsbook="DraftKings",
            over_odds=-110,
            under_odds=-112,
            market_captured_at_utc=CAPTURED,
            minimum_required_ev=0.02,
            max_market_age_minutes=15,
            require_fresh_market=False,
        )

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_wrapper_translates_threshold_not_found(self, getter):
        getter.side_effect = WNBAPropThresholdNotFoundError("missing")
        with self.assertRaisesRegex(m.WNBASportsbookMarketNotFoundError, "missing"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED)

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_wrapper_translates_threshold_not_ready(self, getter):
        getter.side_effect = WNBAPropThresholdNotReadyError("not ready")
        with self.assertRaisesRegex(m.WNBASportsbookMarketNotReadyError, "not ready"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED)

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_wrapper_translates_threshold_model_input(self, getter):
        getter.side_effect = WNBAPropThresholdModelInputError("model")
        with self.assertRaisesRegex(m.WNBASportsbookMarketModelInputError, "model"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED)

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_wrapper_translates_threshold_upstream(self, getter):
        getter.side_effect = WNBAPropThresholdUpstreamError("upstream")
        with self.assertRaisesRegex(m.WNBASportsbookMarketUpstreamError, "upstream"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED)

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_invalid_player_id_fails_before_threshold_network(self, getter):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_game_sportsbook_market_edge(0, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED)
        getter.assert_not_called()

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_invalid_game_id_fails_before_threshold_network(self, getter):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, "bad", 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc=CAPTURED)
        getter.assert_not_called()

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_invalid_market_timestamp_fails_before_threshold_network(self, getter):
        with self.assertRaisesRegex(ValueError, "timezone"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=-110, market_captured_at_utc="2026-08-26T17:45:00")
        getter.assert_not_called()

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_invalid_over_odds_fail_before_threshold_network(self, getter):
        with self.assertRaisesRegex(ValueError, "absolute value"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-99, under_odds=-110, market_captured_at_utc=CAPTURED)
        getter.assert_not_called()

    @patch("sports_api.wnba_sportsbook_market_edge.get_player_game_prop_threshold_probability")
    def test_invalid_under_odds_fail_before_threshold_network(self, getter):
        with self.assertRaisesRegex(ValueError, "absolute value"):
            m.get_player_game_sportsbook_market_edge(PLAYER_ID, GAME_ID, 2026, stat="points", line=19, sportsbook="Book", over_odds=-110, under_odds=99, market_captured_at_utc=CAPTURED)
        getter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
