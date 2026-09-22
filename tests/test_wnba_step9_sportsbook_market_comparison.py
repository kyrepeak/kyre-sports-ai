from __future__ import annotations

from datetime import datetime, timezone
import unittest

from sports_api import wnba_step9_sportsbook_market_comparison as market
from sports_api import wnba_step9_threshold_pricing as pricing


EVALUATED_AT = datetime(2026, 8, 28, 4, 40, 0, tzinfo=timezone.utc)


def _pricing_payload() -> dict:
    result = {
        "data_type": "post_projection_prop_threshold_pricing",
        "schema_version": pricing.SCHEMA_VERSION,
        "source": pricing.SOURCE,
        "model_version": pricing.MODEL_VERSION,
        "release_id": pricing.RELEASE_ID,
        "generated_at_utc": "2026-08-28T04:39:00+00:00",
        "game_id": "1022600291",
        "player_id": 1642291,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "prop": {
            "stat": "points",
            "step8_distribution_key": "points",
            "line": 20.5,
            "line_does_not_change_basketball_projection": True,
        },
        "raw_probabilities": {
            "over": {"probability": 0.60, "percentage": 60.0},
            "push": {"probability": 0.00, "percentage": 0.0},
            "under": {"probability": 0.40, "percentage": 40.0},
            "sum": 1.0,
        },
        "resolved_non_push": {
            "probability": 1.0,
            "percentage": 100.0,
            "over": {
                "available": True,
                "fair_probability": 0.60,
                "fair_percentage": 60.0,
                "fair_decimal_odds": 1.66666667,
                "fair_american_odds": -150,
            },
            "under": {
                "available": True,
                "fair_probability": 0.40,
                "fair_percentage": 40.0,
                "fair_decimal_odds": 2.5,
                "fair_american_odds": 150,
            },
            "fair_probability_sum": 1.0,
            "settlement_basis": "fair prices are conditional on a resolved non-push outcome",
        },
        "precision": {
            "simulations": 5_000_000,
            "over_monte_carlo_standard_error": 0.0002191,
            "push_monte_carlo_standard_error": 0.0,
            "under_monte_carlo_standard_error": 0.0002191,
            "step8_converged": True,
        },
        "step8_lineage": {
            "release_id": "wnba_step8_projection_probability_2026_regular_season_frozen_v1",
            "integration_version": "wnba_step8e_fastapi_projection_probability_v1",
            "step8d_model_version": "wnba_step8d_regularized_gaussian_copula_counts_2026_regular_v1",
            "result_content_sha256": "a" * 64,
            "certified_step8d_sha": "932e1baf05bf762cfb149de1f58be4f72bb7a526",
            "minimum_required_simulations": 5_000_000,
        },
        "guardrails": {
            "post_projection_only": True,
            "sportsbook_quote_consumed": False,
            "sportsbook_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    surface = dict(result)
    surface.pop("generated_at_utc", None)
    result["pricing_content_sha256"] = market._canonical_hash(surface)
    return result


def _env(**updates: str) -> dict[str, str]:
    values = {market.STEP9B_MARKET_COMPARISON_ENABLED_ENV: "true"}
    values.update(updates)
    return values


class Step9SportsbookMarketComparisonTests(unittest.TestCase):
    def test_flag_is_default_off(self) -> None:
        self.assertFalse(market.step9b_market_comparison_enabled({}))

    def test_production_switch_fails_closed(self) -> None:
        with self.assertRaises(market.WNBAStep9MarketComparisonDisabledError):
            market.build_step9b_market_comparison(
                _pricing_payload(),
                sportsbook="ExampleBook",
                over_odds=-110,
                under_odds=-110,
                market_captured_at_utc="2026-08-28T04:39:00Z",
                evaluated_at=EVALUATED_AT,
                env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true"),
            )

    def test_symmetric_minus_110_quote_has_expected_no_vig_and_ev(self) -> None:
        result = market.build_step9b_market_comparison(
            _pricing_payload(),
            sportsbook="ExampleBook",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-28T04:39:00Z",
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        quote = result["sportsbook"]["quote"]
        self.assertAlmostEqual(quote["over"]["no_vig_probability"], 0.5, places=10)
        self.assertAlmostEqual(quote["under"]["no_vig_probability"], 0.5, places=10)
        over = result["comparison"]["over"]
        self.assertAlmostEqual(over["edge"]["vs_no_vig_market_probability"], 0.10, places=10)
        self.assertAlmostEqual(over["expected_value"]["net_profit_per_unit_staked"], 0.1454545455, places=9)
        self.assertTrue(over["expected_value"]["positive_ev"])
        self.assertEqual(result["comparison"]["higher_ev_side"], "over")
        self.assertFalse(result["comparison"]["ranking_or_qualification_applied"])

    def test_asymmetric_quote_removes_vig_proportionally(self) -> None:
        result = market.build_step9b_market_comparison(
            _pricing_payload(),
            sportsbook="ExampleBook",
            over_odds=-125,
            under_odds=105,
            market_captured_at_utc="2026-08-28T04:39:00Z",
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        quote = result["sportsbook"]["quote"]
        total = quote["over"]["no_vig_probability"] + quote["under"]["no_vig_probability"]
        self.assertAlmostEqual(total, 1.0, places=9)
        self.assertGreater(quote["sportsbook_margin_probability"], 0.0)

    def test_integer_line_push_is_used_in_ev_not_discarded(self) -> None:
        payload = _pricing_payload()
        payload["prop"]["line"] = 20.0
        payload["raw_probabilities"] = {
            "over": {"probability": 0.50, "percentage": 50.0},
            "push": {"probability": 0.20, "percentage": 20.0},
            "under": {"probability": 0.30, "percentage": 30.0},
            "sum": 1.0,
        }
        payload["resolved_non_push"] = {
            "probability": 0.8,
            "percentage": 80.0,
            "over": {
                "available": True,
                "fair_probability": 0.625,
                "fair_percentage": 62.5,
                "fair_decimal_odds": 1.6,
                "fair_american_odds": -167,
            },
            "under": {
                "available": True,
                "fair_probability": 0.375,
                "fair_percentage": 37.5,
                "fair_decimal_odds": 2.66666667,
                "fair_american_odds": 167,
            },
            "fair_probability_sum": 1.0,
            "settlement_basis": "fair prices are conditional on a resolved non-push outcome",
        }
        surface = dict(payload)
        surface.pop("generated_at_utc", None)
        surface.pop("pricing_content_sha256", None)
        payload["pricing_content_sha256"] = market._canonical_hash(surface)
        result = market.build_step9b_market_comparison(
            payload,
            sportsbook="ExampleBook",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-28T04:39:00Z",
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        over = result["comparison"]["over"]
        self.assertAlmostEqual(over["model"]["raw_push_probability"], 0.2)
        expected_ev = 0.5 * (100 / 110) - 0.3
        self.assertAlmostEqual(over["expected_value"]["net_profit_per_unit_staked"], expected_ev, places=9)

    def test_minimum_playable_price_for_five_percent_ev(self) -> None:
        result = market.build_step9b_market_comparison(
            _pricing_payload(),
            sportsbook="ExampleBook",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-28T04:39:00Z",
            minimum_required_ev=0.05,
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        threshold = result["comparison"]["over"]["price_threshold"]
        expected_decimal = 1.0 + (0.05 + 0.40) / 0.60
        self.assertAlmostEqual(threshold["minimum_acceptable_decimal_odds"], expected_decimal, places=8)
        self.assertEqual(threshold["minimum_acceptable_american_odds"], -133)
        self.assertTrue(threshold["offered_price_meets_minimum_required_ev"])

    def test_stale_quote_fails_when_freshness_required(self) -> None:
        with self.assertRaises(market.WNBAStep9MarketComparisonNotReadyError):
            market.build_step9b_market_comparison(
                _pricing_payload(),
                sportsbook="ExampleBook",
                over_odds=-110,
                under_odds=-110,
                market_captured_at_utc="2026-08-28T04:00:00Z",
                evaluated_at=EVALUATED_AT,
                env=_env(),
            )

    def test_stale_quote_can_be_labeled_for_explicit_historical_use(self) -> None:
        result = market.build_step9b_market_comparison(
            _pricing_payload(),
            sportsbook="ExampleBook",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-28T04:00:00Z",
            require_fresh_market=False,
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        self.assertTrue(result["sportsbook"]["market_freshness"]["stale"])

    def test_future_quote_beyond_tolerance_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            market.build_step9b_market_comparison(
                _pricing_payload(),
                sportsbook="ExampleBook",
                over_odds=-110,
                under_odds=-110,
                market_captured_at_utc="2026-08-28T04:43:00Z",
                evaluated_at=EVALUATED_AT,
                env=_env(),
            )

    def test_tampered_step9a_payload_fails_hash_validation(self) -> None:
        payload = _pricing_payload()
        payload["raw_probabilities"]["over"]["probability"] = 0.61
        with self.assertRaises(market.WNBAStep9MarketComparisonUpstreamError):
            market.build_step9b_market_comparison(
                payload,
                sportsbook="ExampleBook",
                over_odds=-110,
                under_odds=-110,
                market_captured_at_utc="2026-08-28T04:39:00Z",
                evaluated_at=EVALUATED_AT,
                env=_env(),
            )

    def test_output_hash_is_stable_for_same_market_snapshot(self) -> None:
        kwargs = dict(
            sportsbook="ExampleBook",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-28T04:39:00Z",
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        first = market.build_step9b_market_comparison(_pricing_payload(), **kwargs)
        second = market.build_step9b_market_comparison(_pricing_payload(), **kwargs)
        self.assertEqual(first["comparison_content_sha256"], second["comparison_content_sha256"])

    def test_guardrails_preserve_post_projection_boundary(self) -> None:
        result = market.build_step9b_market_comparison(
            _pricing_payload(),
            sportsbook="ExampleBook",
            over_odds=-110,
            under_odds=-110,
            market_captured_at_utc="2026-08-28T04:39:00Z",
            evaluated_at=EVALUATED_AT,
            env=_env(),
        )
        guards = result["guardrails"]
        self.assertFalse(guards["basketball_projection_changed"])
        self.assertFalse(guards["step8_distribution_changed"])
        self.assertFalse(guards["step9a_probabilities_changed"])
        self.assertTrue(guards["sportsbook_quote_consumed"])
        self.assertFalse(guards["sportsbook_called"])
        self.assertTrue(guards["vig_removed"])
        self.assertTrue(guards["edge_calculated"])
        self.assertTrue(guards["expected_value_calculated"])
        self.assertFalse(guards["cross_sportsbook_consensus_calculated"])
        self.assertFalse(guards["cross_prop_ranking_calculated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
