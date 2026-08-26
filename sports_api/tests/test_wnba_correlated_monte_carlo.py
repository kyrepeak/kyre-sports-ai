import unittest
from copy import deepcopy
from unittest.mock import patch

import numpy as np

from sports_api import wnba_correlated_monte_carlo as m
from sports_api.wnba_empirical_outcome_distribution import (
    WNBAEmpiricalDistributionModelInputError,
    WNBAEmpiricalDistributionNotFoundError,
    WNBAEmpiricalDistributionNotReadyError,
    WNBAEmpiricalDistributionUpstreamError,
)
from sports_api.wnba_game_history import WNBAHistoryNotFoundError, WNBAHistoryUpstreamError
from sports_api.wnba_model_input_readiness import (
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
)
from sports_api.wnba_projection_scenarios import (
    WNBAProjectionScenarioModelInputError,
    WNBAProjectionScenarioNotReadyError,
    WNBAProjectionScenarioUpstreamError,
)


GAME_ID = "1022600300"
PLAYER_ID = 12345
TEAM = "chicago-sky"
OPPONENT = "connecticut-sun"
SMALL_SIM = 6000
SMALL_BATCH = 2000


def snapshot_reference():
    return {
        "snapshot_id": "wnba-4w-5e-test",
        "content_sha256": "a" * 64,
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "recent_window_games": 5,
    }


def scenarios():
    return {
        "model_version": m.SCENARIO_MODEL_VERSION,
        "scenario_id": "wnba-5c-test",
        "scenario_fingerprint_sha256": "c" * 64,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM,
        "opponent_team_key": OPPONENT,
        "side": "away",
        "snapshot_reference": snapshot_reference(),
        "scenarios": {
            "low": {
                "minutes": 28.0,
                "points": 14.0,
                "rebounds": 7.0,
                "assists": 4.0,
                "pra": 25.0,
            },
            "base": {
                "minutes": 32.0,
                "points": 18.0,
                "rebounds": 9.0,
                "assists": 5.0,
                "pra": 32.0,
            },
            "high": {
                "minutes": 36.0,
                "points": 23.0,
                "rebounds": 11.0,
                "assists": 7.0,
                "pra": 41.0,
            },
        },
    }


def observation_rows():
    raw = [
        ("1022600299", 20, 8, 5),
        ("1022600298", 15, 10, 4),
        ("1022600297", 25, 6, 7),
        ("1022600296", 10, 12, 3),
        ("1022600295", 18, 9, 6),
        ("1022600294", 22, 7, 8),
    ]
    return [
        {
            "game_id": game_id,
            "game_date": f"2026-08-{20 - index * 2:02d}",
            "team_key": TEAM,
            "opponent_team_key": OPPONENT,
            "location": "home",
            "minutes": 30.0 + index,
            "points": points,
            "rebounds": rebounds,
            "assists": assists,
            "pra": points + rebounds + assists,
        }
        for index, (game_id, points, rebounds, assists) in enumerate(raw)
    ]


def _corr_basis(rows):
    matrix = np.asarray(
        [[row["points"], row["rebounds"], row["assists"]] for row in rows],
        dtype=np.float64,
    )
    corr = np.corrcoef(matrix, rowvar=False)
    return {
        left: {
            right: round(float(corr[i, j]), 8)
            for j, right in enumerate(m.STAT_KEYS)
        }
        for i, left in enumerate(m.STAT_KEYS)
    }


def distribution(rows=None):
    rows = deepcopy(observation_rows() if rows is None else rows)
    means = {
        stat: round(sum(row[stat] for row in rows) / len(rows), 6)
        for stat in m.STAT_KEYS
    }
    return {
        "model_version": m.EMPIRICAL_MODEL_VERSION,
        "distribution_id": "wnba-5d-test",
        "distribution_fingerprint_sha256": "d" * 64,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM,
        "opponent_team_key": OPPONENT,
        "snapshot_reference": snapshot_reference(),
        "step_5c_scenario_reference": {
            "model_version": m.SCENARIO_MODEL_VERSION,
            "scenario_id": "wnba-5c-test",
            "scenario_fingerprint_sha256": "c" * 64,
        },
        "distribution_window": {
            "selected_game_count": len(rows),
            "selected_game_ids": [row["game_id"] for row in rows],
        },
        "observations": rows,
        "summary_by_stat": {
            stat: {"mean": means[stat]}
            for stat in m.STAT_KEYS
        },
        "dependence": {
            "p_r_a_monte_carlo_basis": {
                "pearson_correlation_matrix": _corr_basis(rows)
            }
        },
        "data_quality": {
            "dependence_ready_without_zero_variance": True,
        },
    }


def simulate(seed=1234, count=SMALL_SIM, batch=SMALL_BATCH, *, sc=None, dist=None):
    return m.simulate_correlated_outcomes(
        scenarios() if sc is None else sc,
        distribution() if dist is None else dist,
        simulation_count=count,
        batch_size=batch,
        random_seed=seed,
    )


class WNBACorrelatedMonteCarloTests(unittest.TestCase):
    def test_default_simulation_count_is_five_million(self):
        self.assertEqual(m.DEFAULT_SIMULATION_COUNT, 5_000_000)

    def test_max_simulation_count_allows_ten_million(self):
        self.assertEqual(m.MAX_SIMULATION_COUNT, 10_000_000)

    def test_returns_low_base_high_conditional_scenarios(self):
        result = simulate()
        self.assertEqual(
            set(result["conditional_scenario_results"]),
            {"low", "base", "high"},
        )

    def test_base_is_primary_distribution(self):
        result = simulate()
        self.assertEqual(result["simulation"]["primary_scenario"], "base")
        self.assertEqual(
            result["primary_distribution"],
            result["conditional_scenario_results"]["base"],
        )

    def test_same_seed_is_deterministic(self):
        first = simulate(seed=77)
        second = simulate(seed=77)
        self.assertEqual(
            first["simulation_fingerprint_sha256"],
            second["simulation_fingerprint_sha256"],
        )
        self.assertEqual(
            first["conditional_scenario_results"],
            second["conditional_scenario_results"],
        )

    def test_different_seed_changes_fingerprint(self):
        self.assertNotEqual(
            simulate(seed=77)["simulation_fingerprint_sha256"],
            simulate(seed=78)["simulation_fingerprint_sha256"],
        )

    def test_requested_simulation_count_completed_per_scenario(self):
        result = simulate(count=5000, batch=2000)
        self.assertEqual(result["simulation"]["requested_simulations"], 5000)
        self.assertEqual(
            result["simulation"]["completed_simulations_per_scenario"], 5000
        )
        for scenario in m.SCENARIO_KEYS:
            for stat in m.OUTPUT_KEYS:
                self.assertEqual(
                    result["conditional_scenario_results"][scenario]["stats"][stat][
                        "simulation_count"
                    ],
                    5000,
                )

    def test_batch_count_uses_ceiling(self):
        self.assertEqual(simulate(count=5000, batch=2000)["simulation"]["batch_count"], 3)

    def test_all_simulated_values_are_nonnegative(self):
        result = simulate()
        for scenario in m.SCENARIO_KEYS:
            for stat in m.OUTPUT_KEYS:
                summary = result["conditional_scenario_results"][scenario]["stats"][stat]
                self.assertGreaterEqual(summary["minimum"], 0)

    def test_histogram_counts_sum_to_simulation_count(self):
        result = simulate()
        for scenario in m.SCENARIO_KEYS:
            for stat in m.OUTPUT_KEYS:
                rows = result["conditional_scenario_results"][scenario]["stats"][stat][
                    "simulated_distribution"
                ]
                self.assertEqual(sum(row["count"] for row in rows), SMALL_SIM)

    def test_histogram_frequencies_sum_to_one(self):
        result = simulate()
        rows = result["primary_distribution"]["stats"]["points"]["simulated_distribution"]
        self.assertAlmostEqual(sum(row["frequency"] for row in rows), 1.0, places=7)

    def test_tail_probabilities_are_monotone_nonincreasing(self):
        rows = simulate()["primary_distribution"]["stats"]["pra"]["simulated_distribution"]
        tails = [row["tail_probability_at_or_above"] for row in rows]
        self.assertTrue(all(a >= b for a, b in zip(tails, tails[1:])))

    def test_tail_at_minimum_is_one(self):
        rows = simulate()["primary_distribution"]["stats"]["assists"]["simulated_distribution"]
        self.assertEqual(rows[0]["tail_probability_at_or_above"], 1.0)

    def test_pra_covariance_obeys_exact_component_sum(self):
        matrix = simulate()["primary_distribution"]["dependence"]["sample_covariance_matrix"]
        expected = (
            matrix["points"]["points"]
            + matrix["points"]["rebounds"]
            + matrix["points"]["assists"]
        )
        self.assertAlmostEqual(matrix["points"]["pra"], expected, places=5)

    def test_simulated_means_track_scenario_targets(self):
        result = simulate(count=20_000, batch=5000)
        for scenario in m.SCENARIO_KEYS:
            row = result["conditional_scenario_results"][scenario]
            for stat in m.OUTPUT_KEYS:
                self.assertLess(
                    abs(row["stats"][stat]["mean"] - row["target_means"][stat]),
                    0.35,
                )

    def test_low_base_high_simulated_means_are_ordered(self):
        result = simulate(count=20_000, batch=5000)
        for stat in m.OUTPUT_KEYS:
            low = result["conditional_scenario_results"]["low"]["stats"][stat]["mean"]
            base = result["conditional_scenario_results"]["base"]["stats"][stat]["mean"]
            high = result["conditional_scenario_results"]["high"]["stats"][stat]["mean"]
            self.assertLess(low, base)
            self.assertLess(base, high)

    def test_quantiles_are_ordered(self):
        q = simulate()["primary_distribution"]["stats"]["points"]["simulated_quantiles"]
        values = [q["p05"], q["p10"], q["p25"], q["p50"], q["p75"], q["p90"], q["p95"]]
        self.assertEqual(values, sorted(values))

    def test_modes_are_integer_outcomes(self):
        modes = simulate()["primary_distribution"]["stats"]["rebounds"]["modes"]
        self.assertTrue(modes)
        self.assertTrue(all(isinstance(value, int) for value in modes))

    def test_mc_standard_error_of_mean_is_reported(self):
        value = simulate()["primary_distribution"]["stats"]["points"]["mc_standard_error_of_mean"]
        self.assertGreater(value, 0)

    def test_tail_mc_standard_error_is_reported(self):
        rows = simulate()["primary_distribution"]["stats"]["points"]["simulated_distribution"]
        middle = rows[len(rows) // 2]
        self.assertGreaterEqual(middle["mc_standard_error_tail"], 0)

    def test_simulated_covariance_is_symmetric(self):
        matrix = simulate()["primary_distribution"]["dependence"]["sample_covariance_matrix"]
        for left in m.OUTPUT_KEYS:
            for right in m.OUTPUT_KEYS:
                self.assertAlmostEqual(matrix[left][right], matrix[right][left], places=7)

    def test_simulated_correlation_diagonal_is_one(self):
        matrix = simulate()["primary_distribution"]["dependence"]["pearson_correlation_matrix"]
        for key in m.OUTPUT_KEYS:
            self.assertAlmostEqual(matrix[key][key], 1.0, places=7)

    def test_empirical_basis_reports_joint_sampling(self):
        basis = simulate()["empirical_basis"]
        self.assertEqual(basis["game_count"], 6)
        self.assertTrue(basis["joint_rows_sampled_together"])
        self.assertEqual(len(basis["observed_game_ids"]), 6)

    def test_empirical_means_are_recomputed(self):
        result = simulate()
        self.assertAlmostEqual(result["empirical_basis"]["empirical_means"]["points"], 110 / 6)
        self.assertAlmostEqual(result["empirical_basis"]["empirical_means"]["rebounds"], 52 / 6)
        self.assertAlmostEqual(result["empirical_basis"]["empirical_means"]["assists"], 33 / 6)

    def test_no_scenario_weights_are_invented(self):
        result = simulate()
        self.assertIsNone(result["simulation"]["scenario_weights"])
        self.assertTrue(
            result["projection_semantics"]["low_base_high_scenario_probabilities_not_invented"]
        )

    def test_no_sportsbook_or_ev_created(self):
        result = simulate()
        self.assertTrue(result["guardrails"]["no_sportsbook_line_used"])
        self.assertTrue(result["guardrails"]["no_sportsbook_price_used"])
        self.assertTrue(result["guardrails"]["no_betting_edge_created"])
        self.assertTrue(result["guardrails"]["no_ev_created"])

    def test_pra_is_not_independently_simulated(self):
        result = simulate()
        self.assertFalse(result["model_config"]["pra_simulated_independently"])
        self.assertTrue(result["projection_semantics"]["pra_is_exact_simulated_p_plus_r_plus_a"])

    def test_small_empirical_sample_blocks_correlated_simulation(self):
        dist = distribution(observation_rows()[:2])
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloNotReadyError, "at least 3"):
            simulate(dist=dist)

    def test_zero_variance_stat_blocks_correlated_simulation(self):
        rows = observation_rows()[:4]
        for row in rows:
            row["points"] = 10
            row["pra"] = row["points"] + row["rebounds"] + row["assists"]
        dist = distribution(rows)
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloNotReadyError, "zero-variance"):
            simulate(dist=dist)

    def test_step_5d_not_ready_quality_flag_blocks(self):
        dist = distribution()
        dist["data_quality"]["dependence_ready_without_zero_variance"] = False
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloNotReadyError, "not ready"):
            simulate(dist=dist)

    def test_wrong_scenario_model_version_fails_closed(self):
        sc = scenarios()
        sc["model_version"] = "wrong"
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "Step 5C"):
            simulate(sc=sc)

    def test_wrong_distribution_model_version_fails_closed(self):
        dist = distribution()
        dist["model_version"] = "wrong"
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "Step 5D"):
            simulate(dist=dist)

    def test_player_identity_mismatch_fails_closed(self):
        sc = scenarios()
        sc["player_id"] = 999
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "player_id"):
            simulate(sc=sc)

    def test_team_identity_mismatch_fails_closed(self):
        sc = scenarios()
        sc["team_key"] = OPPONENT
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "team_key"):
            simulate(sc=sc)

    def test_scenario_reference_id_mismatch_fails_closed(self):
        dist = distribution()
        dist["step_5c_scenario_reference"]["scenario_id"] = "wrong"
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "scenario_id"):
            simulate(dist=dist)

    def test_scenario_reference_hash_mismatch_fails_closed(self):
        dist = distribution()
        dist["step_5c_scenario_reference"]["scenario_fingerprint_sha256"] = "e" * 64
        with self.assertRaisesRegex(
            m.WNBACorrelatedMonteCarloUpstreamError, "scenario_fingerprint_sha256"
        ):
            simulate(dist=dist)

    def test_snapshot_reference_mismatch_fails_closed(self):
        dist = distribution()
        dist["snapshot_reference"]["content_sha256"] = "b" * 64
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "content_sha256"):
            simulate(dist=dist)

    def test_invalid_distribution_fingerprint_fails_closed(self):
        dist = distribution()
        dist["distribution_fingerprint_sha256"] = "bad"
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "distribution fingerprint"):
            simulate(dist=dist)

    def test_invalid_scenario_fingerprint_fails_closed(self):
        sc = scenarios()
        sc["scenario_fingerprint_sha256"] = "bad"
        sc["step_5c_unused"] = True
        dist = distribution()
        dist["step_5c_scenario_reference"]["scenario_fingerprint_sha256"] = "bad"
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "scenario fingerprint"):
            simulate(sc=sc, dist=dist)

    def test_scenario_pra_must_equal_component_sum(self):
        sc = scenarios()
        sc["scenarios"]["base"]["pra"] = 33
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "PRA"):
            simulate(sc=sc)

    def test_scenario_ordering_must_hold(self):
        sc = scenarios()
        sc["scenarios"]["low"]["points"] = 20
        sc["scenarios"]["low"]["pra"] = 31
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "ordering"):
            simulate(sc=sc)

    def test_duplicate_observation_game_id_fails_closed(self):
        dist = distribution()
        dist["observations"][1]["game_id"] = dist["observations"][0]["game_id"]
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "duplicate"):
            simulate(dist=dist)

    def test_observation_pra_must_equal_component_sum(self):
        dist = distribution()
        dist["observations"][0]["pra"] += 1
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "inconsistent PRA"):
            simulate(dist=dist)

    def test_empirical_summary_mean_mismatch_fails_closed(self):
        dist = distribution()
        dist["summary_by_stat"]["points"]["mean"] += 1
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "mean disagrees"):
            simulate(dist=dist)

    def test_selected_game_ids_mismatch_fails_closed(self):
        dist = distribution()
        dist["distribution_window"]["selected_game_ids"] = list(
            reversed(dist["distribution_window"]["selected_game_ids"])
        )
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "selected_game_ids"):
            simulate(dist=dist)

    def test_empirical_correlation_basis_mismatch_fails_closed(self):
        dist = distribution()
        dist["dependence"]["p_r_a_monte_carlo_basis"]["pearson_correlation_matrix"]["points"][
            "rebounds"
        ] = 0.99
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "correlation basis"):
            simulate(dist=dist)

    def test_simulation_count_validation(self):
        with self.assertRaisesRegex(ValueError, "1,000"):
            m._simulation_count(999)
        with self.assertRaisesRegex(ValueError, "10,000,000"):
            m._simulation_count(10_000_001)

    def test_batch_size_validation(self):
        with self.assertRaisesRegex(ValueError, "batch_size"):
            m._batch_size(999)
        with self.assertRaisesRegex(ValueError, "batch_size"):
            m._batch_size(1_000_001)

    def test_random_seed_validation(self):
        with self.assertRaisesRegex(ValueError, "random_seed"):
            m._random_seed(-1)
        with self.assertRaisesRegex(ValueError, "random_seed"):
            m._random_seed(4_294_967_296)

    def test_low_sim_count_is_explicitly_not_converged(self):
        result = simulate(count=5000, batch=1000)
        self.assertFalse(result["convergence"]["all_conditional_scenarios_converged"])
        self.assertFalse(
            result["primary_distribution"]["convergence"]["simulation_count_threshold_met"]
        )

    def test_convergence_reports_batch_ranges_and_mc_se(self):
        convergence = simulate()["primary_distribution"]["convergence"]
        self.assertEqual(
            set(convergence["max_minus_min_batch_mean_by_stat"]),
            set(m.OUTPUT_KEYS),
        )
        self.assertEqual(
            set(convergence["mc_standard_error_of_mean_by_stat"]),
            set(m.OUTPUT_KEYS),
        )

    @patch("sports_api.wnba_correlated_monte_carlo.simulate_correlated_outcomes")
    @patch("sports_api.wnba_correlated_monte_carlo.build_empirical_outcome_distribution")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_uses_single_verified_chain(
        self, gate, scenario_builder, log_getter, distribution_builder, simulator
    ):
        gate.return_value = {"ready": True}
        scenario_builder.return_value = scenarios()
        log_getter.return_value = {"games": []}
        distribution_builder.return_value = distribution()
        simulator.return_value = {"ok": True}

        result = m.get_player_game_correlated_monte_carlo(
            PLAYER_ID,
            GAME_ID,
            2026,
            simulation_count=5000,
            batch_size=2000,
            random_seed=99,
        )
        self.assertEqual(result, {"ok": True})
        gate.assert_called_once_with(
            PLAYER_ID,
            GAME_ID,
            2026,
            season_type="Regular Season",
            last_n_games=5,
            require_current_availability=True,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=False,
            max_snapshot_age_minutes=15,
            include_snapshot=True,
        )
        scenario_builder.assert_called_once_with(gate.return_value)
        log_getter.assert_called_once_with(PLAYER_ID, 2026, season_type="Regular Season")
        distribution_builder.assert_called_once_with(
            gate.return_value,
            scenario_builder.return_value,
            log_getter.return_value,
            season=2026,
            season_type="Regular Season",
            distribution_last_n_games=10,
        )
        simulator.assert_called_once_with(
            scenario_builder.return_value,
            distribution_builder.return_value,
            simulation_count=5000,
            batch_size=2000,
            random_seed=99,
        )

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_invalid_player_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_game_correlated_monte_carlo(0, GAME_ID, 2026)
        gate.assert_not_called()

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_invalid_game_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, "bad", 2026)
        gate.assert_not_called()

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_invalid_simulation_count_fails_before_network(self, gate):
        with self.assertRaises(ValueError):
            m.get_player_game_correlated_monte_carlo(
                PLAYER_ID, GAME_ID, 2026, simulation_count=999
            )
        gate.assert_not_called()

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_not_found(self, gate):
        gate.side_effect = WNBAModelInputReadinessNotFoundError("missing")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloNotFoundError, "missing"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_upstream(self, gate):
        gate.side_effect = WNBAModelInputReadinessUpstreamError("bad")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "bad"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_scenario_not_ready(self, gate, scenario_builder):
        gate.return_value = {}
        scenario_builder.side_effect = WNBAProjectionScenarioNotReadyError("not ready")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloNotReadyError, "not ready"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_scenario_model_input(self, gate, scenario_builder):
        gate.return_value = {}
        scenario_builder.side_effect = WNBAProjectionScenarioModelInputError("model")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloModelInputError, "model"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_scenario_upstream(self, gate, scenario_builder):
        gate.return_value = {}
        scenario_builder.side_effect = WNBAProjectionScenarioUpstreamError("scenario bad")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "scenario bad"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_history_not_found(self, gate, scenario_builder, log_getter):
        gate.return_value = {}
        scenario_builder.return_value = {}
        log_getter.side_effect = WNBAHistoryNotFoundError("history missing")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloNotFoundError, "history missing"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_history_upstream(self, gate, scenario_builder, log_getter):
        gate.return_value = {}
        scenario_builder.return_value = {}
        log_getter.side_effect = WNBAHistoryUpstreamError("history bad")
        with self.assertRaisesRegex(m.WNBACorrelatedMonteCarloUpstreamError, "history bad"):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.build_empirical_outcome_distribution")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_empirical_not_found(
        self, gate, scenario_builder, log_getter, builder
    ):
        gate.return_value = {}
        scenario_builder.return_value = {}
        log_getter.return_value = {}
        builder.side_effect = WNBAEmpiricalDistributionNotFoundError("distribution missing")
        with self.assertRaisesRegex(
            m.WNBACorrelatedMonteCarloNotFoundError, "distribution missing"
        ):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.build_empirical_outcome_distribution")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_empirical_not_ready(
        self, gate, scenario_builder, log_getter, builder
    ):
        gate.return_value = {}
        scenario_builder.return_value = {}
        log_getter.return_value = {}
        builder.side_effect = WNBAEmpiricalDistributionNotReadyError("distribution not ready")
        with self.assertRaisesRegex(
            m.WNBACorrelatedMonteCarloNotReadyError, "distribution not ready"
        ):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.build_empirical_outcome_distribution")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_empirical_model_input(
        self, gate, scenario_builder, log_getter, builder
    ):
        gate.return_value = {}
        scenario_builder.return_value = {}
        log_getter.return_value = {}
        builder.side_effect = WNBAEmpiricalDistributionModelInputError("distribution model")
        with self.assertRaisesRegex(
            m.WNBACorrelatedMonteCarloModelInputError, "distribution model"
        ):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_correlated_monte_carlo.build_empirical_outcome_distribution")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_log_dataset")
    @patch("sports_api.wnba_correlated_monte_carlo.project_scenarios_from_readiness")
    @patch("sports_api.wnba_correlated_monte_carlo.get_player_game_model_input_readiness")
    def test_wrapper_translates_empirical_upstream(
        self, gate, scenario_builder, log_getter, builder
    ):
        gate.return_value = {}
        scenario_builder.return_value = {}
        log_getter.return_value = {}
        builder.side_effect = WNBAEmpiricalDistributionUpstreamError("distribution bad")
        with self.assertRaisesRegex(
            m.WNBACorrelatedMonteCarloUpstreamError, "distribution bad"
        ):
            m.get_player_game_correlated_monte_carlo(PLAYER_ID, GAME_ID, 2026)


if __name__ == "__main__":
    unittest.main()
