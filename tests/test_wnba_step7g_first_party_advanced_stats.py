from __future__ import annotations

import unittest

import sports_api.wnba_step7g_first_party_advanced_stats as advanced
from sports_api.wnba_advanced_stats import WNBAAdvancedStatsUpstreamError


def _stats(**overrides):
    base = {
        "minutes": 200.0,
        "field_goals_made": 30,
        "field_goals_attempted": 70,
        "three_pointers_made": 8,
        "three_pointers_attempted": 24,
        "free_throws_made": 16,
        "free_throws_attempted": 20,
        "offensive_rebounds": 10,
        "defensive_rebounds": 28,
        "rebounds": 38,
        "assists": 20,
        "steals": 7,
        "blocks": 4,
        "turnovers": 13,
        "personal_fouls": 18,
        "points": 84,
    }
    base.update(overrides)
    return base


def _player_stats(**overrides):
    base = {
        "minutes": 32.0,
        "field_goals_made": 7,
        "field_goals_attempted": 15,
        "three_pointers_made": 3,
        "three_pointers_attempted": 7,
        "free_throws_made": 4,
        "free_throws_attempted": 5,
        "offensive_rebounds": 1,
        "defensive_rebounds": 4,
        "rebounds": 5,
        "assists": 4,
        "steals": 2,
        "blocks": 1,
        "turnovers": 2,
        "personal_fouls": 3,
        "points": 21,
    }
    base.update(overrides)
    return base


class Step7GFirstPartyAdvancedStatsTests(unittest.TestCase):
    def test_team_derivation_populates_only_explicit_estimates_for_ratings_and_pace(self) -> None:
        team = _stats()
        opp = _stats(field_goals_made=28, points=78, offensive_rebounds=8, defensive_rebounds=30)
        result = advanced._team_advanced(team, opp, 1)
        self.assertIsNotNone(result["estimated_offensive_rating"])
        self.assertIsNotNone(result["estimated_defensive_rating"])
        self.assertIsNotNone(result["estimated_net_rating"])
        self.assertIsNotNone(result["estimated_pace"])
        self.assertIsNone(result["offensive_rating"])
        self.assertIsNone(result["defensive_rating"])
        self.assertIsNone(result["net_rating"])
        self.assertIsNone(result["pace"])
        self.assertIsNotNone(result["effective_field_goal_percentage"])
        self.assertIsNotNone(result["true_shooting_percentage"])
        self.assertIsNotNone(result["player_impact_estimate"])

    def test_player_derivation_has_usage_shooting_rebounding_pie_without_fake_on_court_ratings(self) -> None:
        player = _player_stats()
        team = _stats()
        opp = _stats(field_goals_made=28, points=78, offensive_rebounds=8, defensive_rebounds=30)
        result = advanced._player_advanced(player, team, opp, 1)
        self.assertIsNotNone(result["estimated_usage_percentage"])
        self.assertIsNone(result["usage_percentage"])
        self.assertIsNotNone(result["effective_field_goal_percentage"])
        self.assertIsNotNone(result["true_shooting_percentage"])
        self.assertIsNotNone(result["estimated_rebound_percentage"])
        self.assertIsNotNone(result["estimated_pace"])
        self.assertIsNotNone(result["player_impact_estimate"])
        self.assertIsNone(result["estimated_offensive_rating"])
        self.assertIsNone(result["offensive_rating"])
        self.assertIsNone(result["estimated_defensive_rating"])
        self.assertIsNone(result["defensive_rating"])

    def test_true_shooting_and_efg_use_reproducible_box_formulas(self) -> None:
        player = _player_stats()
        team = _stats()
        opp = _stats()
        result = advanced._player_advanced(player, team, opp, 1)
        expected_efg = (7 + 0.5 * 3) / 15
        expected_ts = 21 / (2 * (15 + 0.44 * 5))
        self.assertAlmostEqual(result["effective_field_goal_percentage"], expected_efg, places=6)
        self.assertAlmostEqual(result["true_shooting_percentage"], expected_ts, places=6)

    def test_usage_formula_uses_player_and_team_minutes_and_events(self) -> None:
        player = _player_stats()
        team = _stats()
        opp = _stats()
        result = advanced._player_advanced(player, team, opp, 1)
        expected = 100 * ((15 + 0.44 * 5 + 2) * (200 / 5)) / (32 * (70 + 0.44 * 20 + 13))
        self.assertAlmostEqual(result["estimated_usage_percentage"], expected, places=6)

    def test_pie_is_bounded_for_normal_box_inputs(self) -> None:
        player = _player_stats()
        team = _stats()
        opp = _stats(points=78)
        player_result = advanced._player_advanced(player, team, opp, 1)
        team_result = advanced._team_advanced(team, opp, 1)
        self.assertGreaterEqual(player_result["player_impact_estimate"], -1.0)
        self.assertLessEqual(player_result["player_impact_estimate"], 1.0)
        self.assertGreaterEqual(team_result["player_impact_estimate"], -1.0)
        self.assertLessEqual(team_result["player_impact_estimate"], 1.0)

    def test_scope_is_explicitly_2026_regular_pergame_recent_only(self) -> None:
        self.assertEqual(
            advanced._validate_scope(2026, "Regular Season", "PerGame", 5),
            ("Regular Season", "PerGame", 5),
        )
        for args in (
            (2025, "Regular Season", "PerGame", 5),
            (2026, "Playoffs", "PerGame", 5),
            (2026, "Regular Season", "Totals", 5),
            (2026, "Regular Season", "PerGame", 0),
        ):
            with self.assertRaises((WNBAAdvancedStatsUpstreamError, ValueError)):
                advanced._validate_scope(*args)

    def test_game_family_admits_certified_regular_and_excludes_exact_cup(self) -> None:
        self.assertTrue(advanced._regular_game_id("1022600286", 2026))
        self.assertFalse(advanced._regular_game_id("1052600001", 2026))
        self.assertFalse(advanced._regular_game_id("1042600001", 2026))

    def test_duplicate_home_away_team_identity_fails_closed(self) -> None:
        team = {"team_key": "washington-mystics", "stats": _stats()}
        box = {"game_id": "1022600001", "away": team, "home": dict(team)}
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            advanced._box_teams(box, "1022600001")

    def test_player_must_resolve_exactly_once_across_box(self) -> None:
        player = {
            "player_id": 1642785,
            "appeared": True,
            "full_name": "Sonia Citron",
            "stats": _player_stats(),
        }
        away = {
            "team_key": "washington-mystics",
            "official_team_id": 1,
            "stats": _stats(),
            "players": [player],
        }
        home = {
            "team_key": "phoenix-mercury",
            "official_team_id": 2,
            "stats": _stats(),
            "players": [dict(player)],
        }
        box = {"game_id": "1022600001", "away": away, "home": home}
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            advanced._player_side(box, "1022600001", 1642785)

    def test_missing_numeric_box_count_fails_closed(self) -> None:
        broken = {"stats": _stats(field_goals_attempted=None)}
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            advanced._stats(broken, label="broken")

    def test_player_latest_games_cap_fails_instead_of_claiming_unseen_history(self) -> None:
        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            advanced.get_first_party_player_advanced_stats_dataset(
                2026,
                season_type="Regular Season",
                last_n_games=6,
                per_mode="PerGame",
                player_id=1642785,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
