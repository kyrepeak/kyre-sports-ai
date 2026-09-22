from __future__ import annotations

import unittest

import sports_api.wnba_step7g_first_party_advanced_stats_contract_safe as contract
from sports_api.wnba_advanced_stats import WNBAAdvancedStatsUpstreamError


class Step7GAdvancedContractUnitTests(unittest.TestCase):
    def test_player_pct_fields_convert_from_human_percent_to_fraction_units(self) -> None:
        raw = {
            "assist_percentage": 25.0,
            "estimated_offensive_rebound_percentage": 7.5,
            "estimated_defensive_rebound_percentage": 14.0,
            "estimated_rebound_percentage": 10.0,
            "estimated_turnover_percentage": 8.0,
            "estimated_usage_percentage": 22.5,
            "effective_field_goal_percentage": 0.55,
            "true_shooting_percentage": 0.59,
            "player_impact_estimate": 0.12,
            "estimated_assist_ratio": 18.4,
            "estimated_pace": 82.1,
            "estimated_offensive_rating": None,
            "estimated_defensive_rating": None,
        }
        result = contract._normalize_advanced(raw, include_usage=True)
        self.assertEqual(result["assist_percentage"], 0.25)
        self.assertEqual(result["estimated_offensive_rebound_percentage"], 0.075)
        self.assertEqual(result["estimated_defensive_rebound_percentage"], 0.14)
        self.assertEqual(result["estimated_rebound_percentage"], 0.10)
        self.assertEqual(result["estimated_turnover_percentage"], 0.08)
        self.assertEqual(result["estimated_usage_percentage"], 0.225)
        self.assertEqual(result["effective_field_goal_percentage"], 0.55)
        self.assertEqual(result["true_shooting_percentage"], 0.59)
        self.assertEqual(result["player_impact_estimate"], 0.12)
        self.assertEqual(result["estimated_assist_ratio"], 18.4)
        self.assertEqual(result["estimated_pace"], 82.1)

    def test_team_ratings_pace_and_assist_ratio_keep_native_scales(self) -> None:
        raw = {
            "assist_percentage": 62.0,
            "estimated_offensive_rebound_percentage": 28.0,
            "estimated_defensive_rebound_percentage": 72.0,
            "estimated_rebound_percentage": 50.0,
            "estimated_turnover_percentage": 12.0,
            "effective_field_goal_percentage": 0.52,
            "true_shooting_percentage": 0.56,
            "player_impact_estimate": 0.49,
            "estimated_assist_ratio": 19.7,
            "estimated_pace": 79.8,
            "estimated_offensive_rating": 108.5,
            "estimated_defensive_rating": 104.2,
            "estimated_net_rating": 4.3,
        }
        result = contract._normalize_advanced(raw, include_usage=False)
        self.assertEqual(result["assist_percentage"], 0.62)
        self.assertEqual(result["estimated_offensive_rebound_percentage"], 0.28)
        self.assertEqual(result["estimated_defensive_rebound_percentage"], 0.72)
        self.assertEqual(result["estimated_rebound_percentage"], 0.50)
        self.assertEqual(result["estimated_turnover_percentage"], 0.12)
        self.assertEqual(result["estimated_assist_ratio"], 19.7)
        self.assertEqual(result["estimated_pace"], 79.8)
        self.assertEqual(result["estimated_offensive_rating"], 108.5)
        self.assertEqual(result["estimated_defensive_rating"], 104.2)

    def test_window_scope_matches_frozen_spelling(self) -> None:
        self.assertEqual(contract._frozen_window_scope(0), "season_to_date")
        self.assertEqual(contract._frozen_window_scope(5), "last_5_games")

    def test_fraction_guard_rejects_invalid_rescaled_rate(self) -> None:
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            contract._normalize_advanced(
                {
                    "assist_percentage": 125.0,
                    "estimated_pace": 80.0,
                    "effective_field_goal_percentage": 0.5,
                    "true_shooting_percentage": 0.55,
                    "player_impact_estimate": 0.1,
                },
                include_usage=False,
            )

    def test_existing_fraction_fields_must_remain_fraction_units(self) -> None:
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            contract._normalize_advanced(
                {
                    "assist_percentage": 50.0,
                    "estimated_pace": 80.0,
                    "effective_field_goal_percentage": 55.0,
                    "true_shooting_percentage": 0.55,
                    "player_impact_estimate": 0.1,
                },
                include_usage=False,
            )

    def test_rating_and_pace_guards_catch_accidental_fraction_scaling(self) -> None:
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            contract._normalize_advanced(
                {
                    "assist_percentage": 50.0,
                    "estimated_pace": 0.82,
                    "estimated_offensive_rating": 1.08,
                    "effective_field_goal_percentage": 0.5,
                    "true_shooting_percentage": 0.55,
                    "player_impact_estimate": 0.1,
                },
                include_usage=False,
            )

    def test_dataset_wrapper_restores_contract_scope_and_verification(self) -> None:
        dataset = {
            "last_n_games": 5,
            "window_scope": "last_5_certified_completed_regular_games",
            "players": [
                {
                    "advanced": {
                        "assist_percentage": 30.0,
                        "estimated_offensive_rebound_percentage": 6.0,
                        "estimated_defensive_rebound_percentage": 12.0,
                        "estimated_rebound_percentage": 9.0,
                        "estimated_turnover_percentage": 10.0,
                        "estimated_usage_percentage": 24.0,
                        "effective_field_goal_percentage": 0.53,
                        "true_shooting_percentage": 0.57,
                        "player_impact_estimate": 0.11,
                        "estimated_pace": 80.0,
                        "estimated_assist_ratio": 16.0,
                    }
                }
            ],
            "derivation": {},
            "verification": {},
        }
        result = contract._normalize_dataset(
            dataset,
            collection="players",
            include_usage=True,
        )
        self.assertEqual(result["window_scope"], "last_5_games")
        self.assertEqual(result["players"][0]["advanced"]["estimated_usage_percentage"], 0.24)
        self.assertTrue(result["verification"]["frozen_step4f_percentage_units_verified"])
        self.assertTrue(result["verification"]["frozen_window_scope_spelling_verified"])
        self.assertFalse(result["verification"]["third_party_sources_used"])
        self.assertEqual(result["source_variant"], contract.SOURCE_VARIANT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
