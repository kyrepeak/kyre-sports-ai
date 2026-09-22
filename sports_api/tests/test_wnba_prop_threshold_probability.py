import unittest
from copy import deepcopy
import hashlib
import json
from math import sqrt
from unittest.mock import patch

from sports_api import wnba_prop_threshold_probability as m
from sports_api.wnba_correlated_monte_carlo import (
    WNBACorrelatedMonteCarloModelInputError,
    WNBACorrelatedMonteCarloNotFoundError,
    WNBACorrelatedMonteCarloNotReadyError,
    WNBACorrelatedMonteCarloUpstreamError,
)

GAME_ID = "1022600300"
PLAYER_ID = 12345
TEAM = "chicago-sky"
OPPONENT = "connecticut-sun"
N = 100_000

PAIRS = {
    "low": [(15, 40_000), (18, 35_000), (20, 25_000)],
    "base": [(16, 20_000), (18, 30_000), (19, 10_000), (20, 30_000), (22, 10_000)],
    "high": [(18, 15_000), (20, 35_000), (22, 30_000), (24, 20_000)],
}

TARGETS = {
    "low": {"points": 17.5, "rebounds": 7.0, "assists": 4.0, "pra": 28.5},
    "base": {"points": 19.0, "rebounds": 8.0, "assists": 5.0, "pra": 32.0},
    "high": {"points": 21.0, "rebounds": 9.0, "assists": 6.0, "pra": 36.0},
}


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def summary(pairs, total=N):
    assert sum(count for _, count in pairs) == total
    sum_values = sum(value * count for value, count in pairs)
    sum_sq = sum(value * value * count for value, count in pairs)
    mean = sum_values / total
    pop_var = sum_sq / total - mean * mean
    sample_var = (sum_sq - total * mean * mean) / (total - 1)
    highest = max(count for _, count in pairs)
    return {
        "simulation_count": total,
        "mean": mean,
        "median": pairs[len(pairs) // 2][0],
        "modes": [value for value, count in pairs if count == highest],
        "minimum": pairs[0][0],
        "maximum": pairs[-1][0],
        "population_stddev": sqrt(max(0.0, pop_var)),
        "sample_stddev": sqrt(max(0.0, sample_var)),
        "mc_standard_error_of_mean": sqrt(max(0.0, sample_var / total)),
        "simulated_quantiles": {"p50": pairs[len(pairs) // 2][0]},
        "simulated_distribution": [
            {"value": value, "count": count}
            for value, count in pairs
        ],
    }


def recalc_fingerprint(payload):
    scenario_results = payload["conditional_scenario_results"]
    fp_payload = {
        "step_5c_scenario_fingerprint_sha256": payload["step_5c_reference"][
            "scenario_fingerprint_sha256"
        ],
        "step_5d_distribution_fingerprint_sha256": payload["step_5d_reference"][
            "distribution_fingerprint_sha256"
        ],
        "model_config": payload["model_config"],
        "targets": {
            key: scenario_results[key]["target_means"]
            for key in m.SCENARIO_KEYS
        },
        "scenario_results": scenario_results,
    }
    payload["simulation_fingerprint_sha256"] = canonical_hash(fp_payload)
    return payload


def monte_carlo(*, converged=True):
    scenario_results = {}
    for scenario_name in m.SCENARIO_KEYS:
        scenario_results[scenario_name] = {
            "conditional_scenario": scenario_name,
            "target_means": deepcopy(TARGETS[scenario_name]),
            "stats": {
                stat: summary(PAIRS[scenario_name])
                for stat in m.SUPPORTED_STATS
            },
            "dependence": {},
            "convergence": {"converged": converged},
        }
    payload = {
        "source": "Step 5E test",
        "model_version": m.MONTE_CARLO_MODEL_VERSION,
        "simulation_id": "wnba-5e-test",
        "simulation_fingerprint_sha256": None,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM,
        "opponent_team_key": OPPONENT,
        "snapshot_reference": {"snapshot_id": "snap"},
        "step_5c_reference": {
            "model_version": "5c",
            "scenario_id": "scenario",
            "scenario_fingerprint_sha256": "b" * 64,
        },
        "step_5d_reference": {
            "model_version": "5d",
            "distribution_id": "distribution",
            "distribution_fingerprint_sha256": "c" * 64,
        },
        "simulation": {
            "requested_simulations": N,
            "completed_simulations_per_scenario": N,
            "conditional_scenario_count": 3,
            "batch_size": 25_000,
            "batch_count": 4,
            "random_seed": 56001,
            "scenario_weights": None,
            "primary_scenario": "base",
        },
        "conditional_scenario_results": scenario_results,
        "primary_distribution": deepcopy(scenario_results["base"]),
        "model_config": {
            "model_version": m.MONTE_CARLO_MODEL_VERSION,
            "simulation_count": N,
            "batch_size": 25_000,
            "random_seed": 56001,
            "scenario_weights": None,
            "primary_scenario": "base",
        },
    }
    return recalc_fingerprint(payload)


def evaluate(line=18.5, stat="points", require_convergence=True, payload=None):
    return m.evaluate_prop_threshold(
        monte_carlo() if payload is None else payload,
        stat=stat,
        line=line,
        require_convergence=require_convergence,
    )


class WNBAPropThresholdProbabilityTests(unittest.TestCase):
    def test_half_point_line_has_no_push(self):
        result = evaluate(18.5)
        base = result["primary_result"]
        self.assertEqual(base["counts"], {
            "over": 50_000, "under": 50_000, "push": 0, "resolved": 100_000
        })
        self.assertFalse(base["settlement"]["push_possible_for_this_line"])

    def test_integer_line_preserves_push(self):
        base = evaluate(19)["primary_result"]
        self.assertEqual(base["counts"]["over"], 40_000)
        self.assertEqual(base["counts"]["under"], 50_000)
        self.assertEqual(base["counts"]["push"], 10_000)
        self.assertTrue(base["settlement"]["push_possible_for_this_line"])

    def test_raw_probabilities_sum_to_one(self):
        for scenario in evaluate(19)["conditional_scenario_results"].values():
            self.assertEqual(scenario["raw_probabilities"]["sum"], 1.0)

    def test_push_probability_is_unconditional(self):
        base = evaluate(19)["primary_result"]
        self.assertEqual(base["raw_probabilities"]["push"]["probability"], 0.1)

    def test_fair_over_probability_conditions_out_push(self):
        over = evaluate(19)["primary_result"]["fair_odds"]["over"]
        self.assertAlmostEqual(over["fair_probability"], 4 / 9, places=9)

    def test_fair_under_probability_conditions_out_push(self):
        under = evaluate(19)["primary_result"]["fair_odds"]["under"]
        self.assertAlmostEqual(under["fair_probability"], 5 / 9, places=9)

    def test_resolved_fair_probabilities_sum_to_one(self):
        fair = evaluate(19)["primary_result"]["fair_odds"]
        self.assertEqual(fair["resolved_probability_sum"], 1.0)

    def test_even_probability_maps_to_plus_100(self):
        fair = evaluate(18.5)["primary_result"]["fair_odds"]
        self.assertEqual(fair["over"]["fair_decimal_odds"], 2.0)
        self.assertEqual(fair["over"]["fair_american_odds"], 100)
        self.assertEqual(fair["under"]["fair_american_odds"], 100)

    def test_44_44_percent_maps_to_plus_125(self):
        over = evaluate(19)["primary_result"]["fair_odds"]["over"]
        self.assertEqual(over["fair_decimal_odds"], 2.25)
        self.assertEqual(over["fair_american_odds"], 125)

    def test_55_56_percent_maps_to_negative_125(self):
        under = evaluate(19)["primary_result"]["fair_odds"]["under"]
        self.assertEqual(under["fair_decimal_odds"], 1.8)
        self.assertEqual(under["fair_american_odds"], -125)

    def test_line_below_minimum_is_all_over(self):
        base = evaluate(0.5)["primary_result"]
        self.assertEqual(base["counts"]["over"], N)
        self.assertEqual(base["counts"]["under"], 0)
        self.assertEqual(base["counts"]["push"], 0)
        self.assertEqual(base["fair_odds"]["over"]["fair_decimal_odds"], 1.0)
        self.assertIsNone(base["fair_odds"]["over"]["fair_american_odds"])

    def test_line_above_maximum_is_all_under(self):
        base = evaluate(100)["primary_result"]
        self.assertEqual(base["counts"]["under"], N)
        self.assertFalse(base["fair_odds"]["over"]["available"])
        self.assertEqual(base["fair_odds"]["under"]["fair_decimal_odds"], 1.0)

    def test_all_push_has_no_resolved_fair_odds(self):
        payload = monte_carlo()
        for scenario_name in m.SCENARIO_KEYS:
            one = [(19, N)]
            for stat in m.SUPPORTED_STATS:
                payload["conditional_scenario_results"][scenario_name]["stats"][stat] = summary(one)
        recalc_fingerprint(payload)
        result = m.evaluate_prop_threshold(payload, stat="points", line=19, require_convergence=True)
        base = result["primary_result"]
        self.assertEqual(base["counts"]["push"], N)
        self.assertFalse(base["fair_odds"]["over"]["available"])
        self.assertIsNone(base["fair_odds"]["over"]["fair_probability"])
        self.assertFalse(result["numerical_readiness"]["ready_for_fair_odds"])

    def test_mc_standard_error_matches_binomial_formula(self):
        over = evaluate(18.5)["primary_result"]["raw_probabilities"]["over"]
        self.assertAlmostEqual(
            over["mc_standard_error"], sqrt(0.5 * 0.5 / N), places=9
        )

    def test_resolved_mc_se_uses_resolved_sample_count(self):
        over = evaluate(19)["primary_result"]["fair_odds"]["over"]
        expected = sqrt((4/9) * (5/9) / 90_000)
        self.assertAlmostEqual(over["mc_standard_error"], expected, places=9)

    def test_mc_95_interval_contains_probability(self):
        over = evaluate(18.5)["primary_result"]["raw_probabilities"]["over"]
        interval = over["mc_95_interval"]
        self.assertLess(interval["low"], over["probability"])
        self.assertGreater(interval["high"], over["probability"])

    def test_probability_precision_passes_at_100k(self):
        result = evaluate()
        self.assertTrue(result["numerical_readiness"]["all_threshold_precision_passed"])

    def test_nonconverged_source_blocks_by_default(self):
        payload = monte_carlo(converged=False)
        with self.assertRaisesRegex(m.WNBAPropThresholdNotReadyError, "not converged"):
            evaluate(payload=payload)

    def test_nonconverged_source_can_be_returned_for_diagnostics(self):
        payload = monte_carlo(converged=False)
        result = evaluate(payload=payload, require_convergence=False)
        self.assertFalse(result["numerical_readiness"]["all_step_5e_scenarios_converged"])
        self.assertFalse(result["numerical_readiness"]["strict_numerical_readiness_passed"])

    def test_low_base_high_sensitivity_is_exposed(self):
        sensitivity = evaluate(19)["scenario_sensitivity"]
        self.assertEqual(sensitivity["raw_over_probability_by_scenario"], {
            "low": 0.25, "base": 0.4, "high": 0.85
        })
        self.assertEqual(sensitivity["raw_over_probability_span_percentage_points"], 60.0)

    def test_sensitivity_detects_direction_change(self):
        sensitivity = evaluate(19)["scenario_sensitivity"]
        self.assertEqual(sensitivity["favored_side_by_scenario"]["low"], "under")
        self.assertEqual(sensitivity["favored_side_by_scenario"]["high"], "over")
        self.assertFalse(sensitivity["same_favored_side_across_all_scenarios"])

    def test_base_is_primary_result(self):
        result = evaluate(19)
        self.assertEqual(
            result["primary_result"],
            result["conditional_scenario_results"]["base"],
        )

    def test_stat_alias_pts_normalizes_to_points(self):
        result = evaluate(stat="PTS")
        self.assertEqual(result["prop"]["stat"], "points")

    def test_stat_alias_reb_normalizes_to_rebounds(self):
        result = evaluate(stat="reb")
        self.assertEqual(result["prop"]["stat"], "rebounds")

    def test_stat_alias_ast_normalizes_to_assists(self):
        result = evaluate(stat="AST")
        self.assertEqual(result["prop"]["stat"], "assists")

    def test_pra_alias_normalizes(self):
        result = evaluate(stat="points+rebounds+assists")
        self.assertEqual(result["prop"]["stat"], "pra")

    def test_invalid_stat_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported WNBA prop stat"):
            evaluate(stat="steals")

    def test_negative_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "prop line"):
            evaluate(line=-0.5)

    def test_too_large_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "prop line"):
            evaluate(line=251)

    def test_nan_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "prop line"):
            evaluate(line=float("nan"))

    def test_inf_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "prop line"):
            evaluate(line=float("inf"))

    def test_boolean_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "prop line"):
            evaluate(line=True)

    def test_line_is_normalized_to_six_decimals(self):
        result = evaluate(line=18.5000004)
        self.assertEqual(result["prop"]["line"], 18.5)

    def test_fingerprint_is_deterministic_for_same_threshold(self):
        first = evaluate(19)
        second = evaluate(19)
        self.assertEqual(
            first["probability_fingerprint_sha256"],
            second["probability_fingerprint_sha256"],
        )

    def test_fingerprint_changes_when_line_changes(self):
        first = evaluate(18.5)
        second = evaluate(19.5)
        self.assertNotEqual(
            first["probability_fingerprint_sha256"],
            second["probability_fingerprint_sha256"],
        )

    def test_fingerprint_changes_when_stat_changes(self):
        first = evaluate(stat="points")
        second = evaluate(stat="rebounds")
        self.assertNotEqual(
            first["probability_fingerprint_sha256"],
            second["probability_fingerprint_sha256"],
        )

    def test_wrong_step_5e_model_version_fails_closed(self):
        payload = monte_carlo()
        payload["model_version"] = "wrong"
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "unexpected Step 5E"):
            evaluate(payload=payload)

    def test_invalid_step_5e_fingerprint_format_fails_closed(self):
        payload = monte_carlo()
        payload["simulation_fingerprint_sha256"] = "bad"
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "fingerprint"):
            evaluate(payload=payload)

    def test_tampered_hash_covered_distribution_fails_closed(self):
        payload = monte_carlo()
        payload["conditional_scenario_results"]["base"]["stats"]["points"][
            "simulated_distribution"
        ][0]["count"] -= 1
        payload["conditional_scenario_results"]["base"]["stats"]["points"][
            "simulated_distribution"
        ][1]["count"] += 1
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "does not match"):
            evaluate(payload=payload)

    def test_missing_upstream_fingerprint_source_fails_closed(self):
        payload = monte_carlo()
        payload["step_5d_reference"]["distribution_fingerprint_sha256"] = None
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "upstream"):
            evaluate(payload=payload)

    def test_wrong_player_identity_fails_closed(self):
        payload = monte_carlo()
        payload["player_id"] = None
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "identity"):
            evaluate(payload=payload)

    def test_same_team_and_opponent_fails_closed(self):
        payload = monte_carlo()
        payload["opponent_team_key"] = TEAM
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "identity"):
            evaluate(payload=payload)

    def test_simulation_count_mismatch_fails_closed(self):
        payload = monte_carlo()
        payload["simulation"]["requested_simulations"] = N - 1
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "count metadata"):
            evaluate(payload=payload)

    def test_scenario_weights_fail_closed(self):
        payload = monte_carlo()
        payload["simulation"]["scenario_weights"] = {"base": 1.0}
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "mixture weights"):
            evaluate(payload=payload)

    def test_missing_conditional_scenario_fails_closed(self):
        payload = monte_carlo()
        payload["conditional_scenario_results"].pop("high")
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "missing HIGH"):
            evaluate(payload=payload)

    def test_scenario_identity_mismatch_fails_closed(self):
        payload = monte_carlo()
        payload["conditional_scenario_results"]["base"]["conditional_scenario"] = "low"
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "identity"):
            evaluate(payload=payload)

    def test_missing_requested_stat_fails_closed(self):
        payload = monte_carlo()
        payload["conditional_scenario_results"]["base"]["stats"].pop("points")
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "missing simulated points"):
            evaluate(payload=payload)

    def test_histogram_count_sum_mismatch_fails_closed(self):
        payload = monte_carlo()
        rows = payload["conditional_scenario_results"]["base"]["stats"]["points"][
            "simulated_distribution"
        ]
        rows[0]["count"] -= 1
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "do not equal simulations"):
            evaluate(payload=payload)

    def test_histogram_duplicate_value_fails_closed(self):
        payload = monte_carlo()
        rows = payload["conditional_scenario_results"]["base"]["stats"]["points"][
            "simulated_distribution"
        ]
        rows[1]["value"] = rows[0]["value"]
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "duplicate or unsorted"):
            evaluate(payload=payload)

    def test_histogram_unsorted_value_fails_closed(self):
        payload = monte_carlo()
        rows = payload["conditional_scenario_results"]["base"]["stats"]["points"][
            "simulated_distribution"
        ]
        rows[1]["value"] = 15
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "duplicate or unsorted"):
            evaluate(payload=payload)

    def test_histogram_negative_value_fails_closed(self):
        payload = monte_carlo()
        rows = payload["conditional_scenario_results"]["base"]["stats"]["points"][
            "simulated_distribution"
        ]
        rows[0]["value"] = -1
        recalc_fingerprint(payload)
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "invalid value/count"):
            evaluate(payload=payload)

    def test_source_summary_is_preserved_without_full_distribution(self):
        base = evaluate()["primary_result"]
        self.assertIn("mean", base["source_distribution_summary"])
        self.assertNotIn("simulated_distribution", base["source_distribution_summary"])

    def test_guardrails_exclude_price_edge_and_ev(self):
        guardrails = evaluate()["guardrails"]
        self.assertTrue(guardrails["no_sportsbook_price_used"])
        self.assertTrue(guardrails["no_market_edge_created"])
        self.assertTrue(guardrails["no_ev_created"])
        self.assertTrue(guardrails["threshold_cannot_change_projection_means"])

    def test_probability_semantics_are_explicit(self):
        semantics = evaluate()["probability_semantics"]
        self.assertTrue(semantics["fair_odds_use_resolved_non_push_probability"])
        self.assertTrue(semantics["mc_standard_error_is_numerical_simulation_error_only"])
        self.assertTrue(semantics["low_base_high_are_conditional_scenarios_not_mixture_weights"])

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_wrapper_calls_step_5e_with_exact_controls(self, getter):
        getter.return_value = monte_carlo()
        result = m.get_player_game_prop_threshold_probability(
            PLAYER_ID,
            GAME_ID,
            2026,
            stat="points",
            line=18.5,
            last_n_games=7,
            distribution_last_n_games=12,
            simulation_count=100_000,
            batch_size=25_000,
            random_seed=77,
            require_current_availability=False,
            max_snapshot_age_minutes=30,
            require_convergence=True,
        )
        self.assertEqual(result["prop"]["line"], 18.5)
        getter.assert_called_once_with(
            PLAYER_ID,
            GAME_ID,
            2026,
            season_type="Regular Season",
            last_n_games=7,
            distribution_last_n_games=12,
            simulation_count=100_000,
            batch_size=25_000,
            random_seed=77,
            require_current_availability=False,
            max_snapshot_age_minutes=30,
        )

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_invalid_player_fails_before_network(self, getter):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_game_prop_threshold_probability(
                0, GAME_ID, 2026, stat="points", line=18.5
            )
        getter.assert_not_called()

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_invalid_game_fails_before_network(self, getter):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, "bad", 2026, stat="points", line=18.5
            )
        getter.assert_not_called()

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_invalid_stat_fails_before_network(self, getter):
        with self.assertRaises(ValueError):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, GAME_ID, 2026, stat="steals", line=1.5
            )
        getter.assert_not_called()

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_invalid_line_fails_before_network(self, getter):
        with self.assertRaises(ValueError):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, GAME_ID, 2026, stat="points", line=-1
            )
        getter.assert_not_called()

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_wrapper_translates_not_found(self, getter):
        getter.side_effect = WNBACorrelatedMonteCarloNotFoundError("missing")
        with self.assertRaisesRegex(m.WNBAPropThresholdNotFoundError, "missing"):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, GAME_ID, 2026, stat="points", line=18.5
            )

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_wrapper_translates_not_ready(self, getter):
        getter.side_effect = WNBACorrelatedMonteCarloNotReadyError("not ready")
        with self.assertRaisesRegex(m.WNBAPropThresholdNotReadyError, "not ready"):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, GAME_ID, 2026, stat="points", line=18.5
            )

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_wrapper_translates_model_input(self, getter):
        getter.side_effect = WNBACorrelatedMonteCarloModelInputError("model")
        with self.assertRaisesRegex(m.WNBAPropThresholdModelInputError, "model"):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, GAME_ID, 2026, stat="points", line=18.5
            )

    @patch("sports_api.wnba_prop_threshold_probability.get_player_game_correlated_monte_carlo")
    def test_wrapper_translates_upstream(self, getter):
        getter.side_effect = WNBACorrelatedMonteCarloUpstreamError("upstream")
        with self.assertRaisesRegex(m.WNBAPropThresholdUpstreamError, "upstream"):
            m.get_player_game_prop_threshold_probability(
                PLAYER_ID, GAME_ID, 2026, stat="points", line=18.5
            )


if __name__ == "__main__":
    unittest.main()
