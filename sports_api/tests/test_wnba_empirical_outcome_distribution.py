import unittest
from copy import deepcopy
from unittest.mock import patch

from sports_api import wnba_empirical_outcome_distribution as m
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
TARGET_DATE = "2026-08-26"


def snapshot_reference(content_hash="a" * 64):
    return {
        "snapshot_id": "wnba-4w-5d-test",
        "content_sha256": content_hash,
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "recent_window_games": 5,
    }


def readiness(state="READY", content_hash="a" * 64):
    ref = snapshot_reference(content_hash)
    return {
        "readiness": state,
        "can_start_projection": state != "NOT_READY",
        "snapshot_included": True,
        "snapshot_reference": deepcopy(ref),
        "summary": {
            "blocker_ids": ["blocked"] if state == "NOT_READY" else [],
            "warning_ids": [],
        },
        "snapshot": {
            **deepcopy(ref),
            "season": 2026,
            "season_type": "Regular Season",
            "game_identity": {
                "game_id": GAME_ID,
                "date": TARGET_DATE,
                "away_team_key": TEAM,
                "home_team_key": OPPONENT,
            },
            "focal_identity": {
                "player_id": PLAYER_ID,
                "team_key": TEAM,
                "opponent_team_key": OPPONENT,
                "side": "away",
            },
        },
    }


def scenarios(content_hash="a" * 64):
    return {
        "model_version": m.SCENARIO_MODEL_VERSION,
        "scenario_id": "wnba-5c-test",
        "scenario_fingerprint_sha256": "c" * 64,
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM,
        "opponent_team_key": OPPONENT,
        "side": "away",
        "snapshot_reference": snapshot_reference(content_hash),
        "scenarios": {
            "low": {"minutes": 28.0, "points": 14.0, "rebounds": 7.0, "assists": 4.0, "pra": 25.0},
            "base": {"minutes": 32.0, "points": 18.0, "rebounds": 9.0, "assists": 5.0, "pra": 32.0},
            "high": {"minutes": 36.0, "points": 23.0, "rebounds": 11.0, "assists": 7.0, "pra": 41.0},
        },
    }


def game_row(game_id, date, points, rebounds, assists, minutes, *, team=TEAM, opponent=OPPONENT, player_id=PLAYER_ID):
    return {
        "player_id": player_id,
        "game_id": game_id,
        "game_id_valid": True,
        "game_date": date,
        "matchup": {
            "team_key": team,
            "opponent_team_key": opponent,
            "location": "home",
        },
        "minutes": minutes,
        "points": points,
        "rebounds": rebounds,
        "assists": assists,
        "result": "W",
    }


def base_games():
    return [
        game_row("1022600299", "2026-08-20", 20, 8, 5, 34.0),
        game_row("1022600298", "2026-08-18", 15, 10, 4, 32.0),
        game_row("1022600297", "2026-08-16", 25, 6, 7, 36.0),
        game_row("1022600296", "2026-08-14", 10, 12, 3, 28.0),
        game_row("1022600295", "2026-08-12", 18, 9, 6, 30.0),
        game_row("1022600294", "2026-08-10", 22, 7, 8, 35.0),
    ]


def game_log(games=None, *, player_id=PLAYER_ID, season=2026, season_type="Regular Season", retrieved="2026-08-26T16:00:00+00:00"):
    rows = deepcopy(base_games() if games is None else games)
    return {
        "source": "WNBA Stats API",
        "source_url": "https://stats.wnba.com/",
        "source_endpoint": "playergamelog",
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "retrieved_at_utc": retrieved,
        "cache_hit": False,
        "cache_ttl_seconds": 120,
        "game_count": len(rows),
        "games": rows,
        "verification": {
            "returned_player_ids_match_request": True,
            "all_game_ids_valid": True,
            "all_game_ids_unique": True,
            "duplicate_game_ids": [],
            "all_matchup_teams_mapped_to_registry": True,
        },
    }


def build(distribution_last_n_games=5, *, games=None):
    return m.build_empirical_outcome_distribution(
        readiness(),
        scenarios(),
        game_log(games),
        season=2026,
        season_type="Regular Season",
        distribution_last_n_games=distribution_last_n_games,
    )


class WNBAEmpiricalOutcomeDistributionTests(unittest.TestCase):
    def test_selects_latest_requested_complete_target_team_games(self):
        result = build(5)
        self.assertEqual(result["distribution_window"]["selected_game_ids"], [
            "1022600299", "1022600298", "1022600297", "1022600296", "1022600295"
        ])
        self.assertEqual(result["distribution_window"]["selected_game_count"], 5)

    def test_future_rows_are_excluded(self):
        games = base_games() + [game_row("1022600301", "2026-08-28", 40, 20, 10, 39.0)]
        result = build(10, games=games)
        self.assertIn("1022600301", result["distribution_window"]["excluded_same_date_or_future_game_ids"])
        self.assertNotIn("1022600301", result["distribution_window"]["selected_game_ids"])

    def test_same_date_non_target_row_is_excluded(self):
        games = base_games() + [game_row("1022600302", TARGET_DATE, 40, 20, 10, 39.0)]
        result = build(10, games=games)
        self.assertIn("1022600302", result["distribution_window"]["excluded_same_date_or_future_game_ids"])

    def test_target_game_row_is_excluded(self):
        games = base_games() + [game_row(GAME_ID, TARGET_DATE, 40, 20, 10, 39.0)]
        result = build(10, games=games)
        self.assertEqual(result["distribution_window"]["excluded_target_game_ids"], [GAME_ID])

    def test_prior_team_rows_are_excluded(self):
        games = base_games() + [
            game_row("1022600293", "2026-08-08", 30, 10, 10, 38.0, team="seattle-storm", opponent="las-vegas-aces")
        ]
        result = build(10, games=games)
        self.assertIn("1022600293", result["distribution_window"]["excluded_prior_team_game_ids"])

    def test_zero_minutes_rows_are_excluded(self):
        games = base_games() + [game_row("1022600292", "2026-08-07", 0, 0, 0, 0.0)]
        result = build(10, games=games)
        self.assertIn("1022600292", result["distribution_window"]["excluded_incomplete_or_nonappearance_game_ids"])

    def test_missing_pra_component_row_is_excluded(self):
        games = base_games()
        bad = game_row("1022600292", "2026-08-07", 12, 4, 3, 22.0)
        bad["assists"] = None
        games.append(bad)
        result = build(10, games=games)
        self.assertIn("1022600292", result["distribution_window"]["excluded_incomplete_or_nonappearance_game_ids"])

    def test_no_eligible_observations_is_not_found(self):
        games = [game_row("1022600301", "2026-08-28", 20, 8, 5, 30.0)]
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionNotFoundError, "No complete target-team"):
            build(5, games=games)

    def test_points_summary_mean_median_variance(self):
        result = build(5)
        points = result["summary_by_stat"]["points"]
        self.assertEqual(points["mean"], 17.6)
        self.assertEqual(points["median"], 18.0)
        self.assertEqual(points["population_variance"], 25.04)
        self.assertEqual(points["sample_variance"], 31.3)

    def test_rebound_and_assist_sample_variance(self):
        result = build(5)
        self.assertEqual(result["summary_by_stat"]["rebounds"]["sample_variance"], 5.0)
        self.assertEqual(result["summary_by_stat"]["assists"]["sample_variance"], 2.5)

    def test_pra_is_recomputed_and_summarized(self):
        result = build(5)
        self.assertEqual([row["pra"] for row in result["observations"]], [33, 29, 38, 25, 33])
        self.assertEqual(result["summary_by_stat"]["pra"]["mean"], 31.6)
        self.assertEqual(result["summary_by_stat"]["pra"]["sample_variance"], 23.8)

    def test_empirical_quantiles_use_nearest_rank(self):
        points = build(5)["summary_by_stat"]["points"]["empirical_quantiles"]
        self.assertEqual(points["p10"], 10.0)
        self.assertEqual(points["p25"], 15.0)
        self.assertEqual(points["p50"], 18.0)
        self.assertEqual(points["p75"], 20.0)
        self.assertEqual(points["p90"], 25.0)
        self.assertEqual(points["method"], "nearest_rank_empirical")

    def test_modes_support_multimodal_observed_values(self):
        games = [
            game_row("1022600299", "2026-08-20", 10, 5, 3, 30),
            game_row("1022600298", "2026-08-18", 10, 6, 4, 31),
            game_row("1022600297", "2026-08-16", 20, 7, 5, 32),
            game_row("1022600296", "2026-08-14", 20, 8, 6, 33),
        ]
        modes = build(4, games=games)["summary_by_stat"]["points"]["modes"]
        self.assertEqual(modes, [10.0, 20.0])

    def test_empirical_distribution_frequency_and_tail(self):
        rows = build(5)["summary_by_stat"]["pra"]["observed_distribution"]
        row33 = next(row for row in rows if row["value"] == 33)
        self.assertEqual(row33["count"], 2)
        self.assertEqual(row33["frequency"], 0.4)
        self.assertEqual(row33["empirical_tail_at_or_above"], 0.6)

    def test_covariance_matrix_is_symmetric(self):
        matrix = build(5)["dependence"]["sample_covariance_matrix"]
        for left in m.DEPENDENCE_KEYS:
            for right in m.DEPENDENCE_KEYS:
                self.assertEqual(matrix[left][right], matrix[right][left])

    def test_correlation_diagonal_is_one_for_nonconstant_stats(self):
        matrix = build(5)["dependence"]["pearson_correlation_matrix"]
        for key in m.DEPENDENCE_KEYS:
            self.assertEqual(matrix[key][key], 1.0)

    def test_pra_covariance_obeys_component_sum_identity(self):
        matrix = build(5)["dependence"]["sample_covariance_matrix"]
        expected = matrix["points"]["points"] + matrix["points"]["rebounds"] + matrix["points"]["assists"]
        self.assertAlmostEqual(matrix["points"]["pra"], expected, places=7)

    def test_pra_only_not_used_as_independent_monte_carlo_basis(self):
        basis = build(5)["dependence"]["p_r_a_monte_carlo_basis"]
        self.assertEqual(basis["stats"], ["points", "rebounds", "assists"])
        self.assertNotIn("pra", basis["sample_covariance_matrix"])

    def test_minutes_correlations_are_reported(self):
        result = build(5)
        correlations = result["dependence"]["minutes_pearson_correlation_with_stats"]
        self.assertEqual(set(correlations), set(m.DEPENDENCE_KEYS))
        self.assertIsNotNone(correlations["points"])

    def test_one_game_has_no_sample_variance_or_dependence(self):
        result = build(1)
        self.assertIsNone(result["summary_by_stat"]["points"]["sample_variance"])
        self.assertFalse(result["data_quality"]["sample_variance_available"])
        self.assertFalse(result["dependence"]["dependence_estimation_available"])

    def test_zero_variance_stat_is_flagged(self):
        games = [
            game_row("1022600299", "2026-08-20", 10, 5, 3, 30),
            game_row("1022600298", "2026-08-18", 10, 6, 4, 31),
            game_row("1022600297", "2026-08-16", 10, 7, 5, 32),
        ]
        result = build(3, games=games)
        self.assertIn("points", result["dependence"]["zero_sample_variance_stats"])
        self.assertFalse(result["data_quality"]["dependence_ready_without_zero_variance"])

    def test_wrong_game_log_player_fails_closed(self):
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "wrong player ID"):
            m.build_empirical_outcome_distribution(readiness(), scenarios(), game_log(player_id=999), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_wrong_game_log_season_fails_closed(self):
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "wrong season"):
            m.build_empirical_outcome_distribution(readiness(), scenarios(), game_log(season=2025), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_wrong_game_log_season_type_fails_closed(self):
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "wrong season type"):
            m.build_empirical_outcome_distribution(readiness(), scenarios(), game_log(season_type="Playoffs"), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_duplicate_game_log_verification_fails_closed(self):
        log = game_log()
        log["verification"]["all_game_ids_unique"] = False
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "duplicate game IDs"):
            m.build_empirical_outcome_distribution(readiness(), scenarios(), log, season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_wrong_player_inside_game_row_fails_closed(self):
        games = base_games()
        games[0]["player_id"] = 999
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "row has the wrong player ID"):
            build(5, games=games)

    def test_wrong_step_5c_model_version_fails_closed(self):
        sc = scenarios()
        sc["model_version"] = "wrong"
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "unexpected Step 5C"):
            m.build_empirical_outcome_distribution(readiness(), sc, game_log(), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_step_5c_identity_mismatch_fails_closed(self):
        sc = scenarios()
        sc["team_key"] = OPPONENT
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "identity disagrees"):
            m.build_empirical_outcome_distribution(readiness(), sc, game_log(), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_snapshot_reference_mismatch_fails_closed(self):
        sc = scenarios("b" * 64)
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "content_sha256"):
            m.build_empirical_outcome_distribution(readiness(), sc, game_log(), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_invalid_target_date_fails_closed(self):
        report = readiness()
        report["snapshot"]["game_identity"]["date"] = "08/26/2026"
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "ISO"):
            m.build_empirical_outcome_distribution(report, scenarios(), game_log(), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_invalid_base_scenario_stat_fails_closed(self):
        sc = scenarios()
        sc["scenarios"]["base"]["points"] = None
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "invalid points"):
            m.build_empirical_outcome_distribution(readiness(), sc, game_log(), season=2026, season_type="Regular Season", distribution_last_n_games=5)

    def test_distribution_fingerprint_is_deterministic_for_same_content(self):
        first = build(5)
        second = build(5)
        self.assertEqual(first["distribution_fingerprint_sha256"], second["distribution_fingerprint_sha256"])
        self.assertEqual(first["distribution_id"], second["distribution_id"])

    def test_distribution_fingerprint_changes_when_observation_changes(self):
        first = build(5)
        games = base_games()
        games[0]["points"] += 1
        second = build(5, games=games)
        self.assertNotEqual(first["distribution_fingerprint_sha256"], second["distribution_fingerprint_sha256"])

    def test_step_5c_base_projection_is_preserved_as_reference(self):
        result = build(5)
        self.assertEqual(result["step_5c_base_projection"], {
            "minutes": 32.0, "points": 18.0, "rebounds": 9.0, "assists": 5.0, "pra": 32.0
        })
        self.assertTrue(result["semantics"]["step_5c_central_projection_unchanged"])

    def test_no_predictive_probability_or_monte_carlo_claims(self):
        result = build(5)
        self.assertTrue(result["guardrails"]["no_predictive_probability_created"])
        self.assertTrue(result["guardrails"]["no_monte_carlo_created"])
        self.assertTrue(result["guardrails"]["no_sportsbook_data_used"])
        self.assertTrue(result["semantics"]["observed_empirical_frequencies_are_not_predictive_probabilities"])

    def test_distribution_last_n_validation(self):
        with self.assertRaisesRegex(ValueError, "1 through 50"):
            m._distribution_last_n(0)
        with self.assertRaisesRegex(ValueError, "1 through 50"):
            m._distribution_last_n(51)

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_log_dataset")
    @patch("sports_api.wnba_empirical_outcome_distribution.project_scenarios_from_readiness")
    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_requests_same_snapshot_then_official_log(self, gate, scenario_builder, log_getter):
        gate.return_value = readiness()
        scenario_builder.return_value = scenarios()
        log_getter.return_value = game_log()
        result = m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026, distribution_last_n_games=5)
        self.assertEqual(result["player_id"], PLAYER_ID)
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

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_not_found(self, gate):
        gate.side_effect = WNBAModelInputReadinessNotFoundError("missing")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionNotFoundError, "missing"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_upstream(self, gate):
        gate.side_effect = WNBAModelInputReadinessUpstreamError("bad")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "bad"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.project_scenarios_from_readiness")
    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_scenario_not_ready(self, gate, scenario_builder):
        gate.return_value = readiness()
        scenario_builder.side_effect = WNBAProjectionScenarioNotReadyError("not ready")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionNotReadyError, "not ready"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.project_scenarios_from_readiness")
    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_scenario_model_input(self, gate, scenario_builder):
        gate.return_value = readiness()
        scenario_builder.side_effect = WNBAProjectionScenarioModelInputError("model")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionModelInputError, "model"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.project_scenarios_from_readiness")
    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_scenario_upstream(self, gate, scenario_builder):
        gate.return_value = readiness()
        scenario_builder.side_effect = WNBAProjectionScenarioUpstreamError("scenario upstream")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "scenario upstream"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_log_dataset")
    @patch("sports_api.wnba_empirical_outcome_distribution.project_scenarios_from_readiness")
    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_history_not_found(self, gate, scenario_builder, log_getter):
        gate.return_value = readiness()
        scenario_builder.return_value = scenarios()
        log_getter.side_effect = WNBAHistoryNotFoundError("history missing")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionNotFoundError, "history missing"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_log_dataset")
    @patch("sports_api.wnba_empirical_outcome_distribution.project_scenarios_from_readiness")
    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_wrapper_translates_history_upstream(self, gate, scenario_builder, log_getter):
        gate.return_value = readiness()
        scenario_builder.return_value = scenarios()
        log_getter.side_effect = WNBAHistoryUpstreamError("history upstream")
        with self.assertRaisesRegex(m.WNBAEmpiricalDistributionUpstreamError, "history upstream"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_invalid_player_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_game_empirical_outcome_distribution(0, GAME_ID, 2026)
        gate.assert_not_called()

    @patch("sports_api.wnba_empirical_outcome_distribution.get_player_game_model_input_readiness")
    def test_invalid_game_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_player_game_empirical_outcome_distribution(PLAYER_ID, "bad", 2026)
        gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
