import unittest
from unittest.mock import patch

from sports_api import wnba_matchup_context as m


def stint(start, end):
    return {
        "in_time_real": float(start),
        "out_time_real": float(end),
    }


def player(player_id, name, team_key, intervals):
    total_tenths = sum(end - start for start, end in intervals)
    return {
        "player_id": player_id,
        "player_name": name,
        "team_key": team_key,
        "team_full_name": team_key.replace("-", " ").title(),
        "tracked_seconds": total_tenths / 10.0,
        "tracked_minutes": total_tenths / 600.0,
        "stints": [stint(start, end) for start, end in intervals],
    }


def rotation_game(game_id="1022600204"):
    away_players = [
        player(10, "Away One", "toronto-tempo", [(0, 6000), (12000, 18000)]),
        player(11, "Away Two", "toronto-tempo", [(6000, 12000), (18000, 24000)]),
    ]
    home_players = [
        player(20, "Home One", "seattle-storm", [(0, 9000), (15000, 24000)]),
        player(21, "Home Two", "seattle-storm", [(9000, 15000)]),
    ]
    return {
        "source": "WNBA Stats API",
        "source_url": "https://stats.wnba.com/",
        "source_endpoint": "gamerotation",
        "game_id": game_id,
        "away": {
            "official_team_id": 2,
            "team_key": "toronto-tempo",
            "team_full_name": "Toronto Tempo",
            "players": away_players,
        },
        "home": {
            "official_team_id": 1,
            "team_key": "seattle-storm",
            "team_full_name": "Seattle Storm",
            "players": home_players,
        },
    }


class WNBAMatchupContextTests(unittest.TestCase):
    def test_source_status_refuses_defender_claims(self):
        result = m.get_matchup_source_status(2026)
        self.assertFalse(result["official_player_vs_defender_matchup_feed_available"])
        self.assertEqual(result["research_endpoint"], "boxscorematchupsv3")
        self.assertTrue(result["guardrails"]["do_not_fabricate_defender_assignments"])
        self.assertTrue(result["guardrails"]["shared_court_time_is_not_defender_time"])

    def test_overlap_segments_use_exact_rotation_intersections(self):
        left = player(1, "A", "toronto-tempo", [(0, 6000), (12000, 18000)])
        right = player(2, "B", "seattle-storm", [(3000, 9000), (15000, 21000)])
        segments = m._overlap_segments(left, right)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["duration_seconds"], 300.0)
        self.assertEqual(segments[1]["duration_seconds"], 300.0)

    def test_same_player_overlapping_intervals_are_merged_before_pairing(self):
        left = player(1, "A", "toronto-tempo", [(0, 6000), (5000, 10000)])
        right = player(2, "B", "seattle-storm", [(0, 10000)])
        segments = m._overlap_segments(left, right)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["duration_seconds"], 1000.0)

    def test_zero_duration_boundary_overlap_is_omitted(self):
        left = player(1, "A", "toronto-tempo", [(0, 6000)])
        right = player(2, "B", "seattle-storm", [(6000, 12000)])
        self.assertEqual(m._overlap_segments(left, right), [])

    @patch("sports_api.wnba_matchup_context.get_game_rotation")
    def test_game_overlap_builds_cross_team_pairs(self, game_rotation):
        game_rotation.return_value = rotation_game()
        result = m.get_game_opponent_overlap("1022600204", 2026)
        self.assertEqual(result["pair_count"], 4)
        self.assertEqual(result["pairs"][0]["shared_court_seconds"], 900.0)
        self.assertTrue(result["verification"]["no_primary_defender_assignment_inferred"])

    @patch("sports_api.wnba_matchup_context.get_game_rotation")
    def test_focal_player_filter_only_returns_that_players_pairs(self, game_rotation):
        game_rotation.return_value = rotation_game()
        result = m.get_game_opponent_overlap("1022600204", 2026, player_id=20)
        self.assertEqual(result["focal_side"], "home")
        self.assertEqual(result["focal_player"]["player_id"], 20)
        self.assertEqual(result["pair_count"], 2)
        self.assertTrue(all(pair["home_player"]["player_id"] == 20 for pair in result["pairs"]))

    @patch("sports_api.wnba_matchup_context.get_game_rotation")
    def test_focal_player_not_in_rotation_is_not_found(self, game_rotation):
        game_rotation.return_value = rotation_game()
        with self.assertRaises(m.WNBAMatchupContextNotFoundError):
            m.get_game_opponent_overlap("1022600204", 2026, player_id=999)

    @patch("sports_api.wnba_matchup_context.get_game_rotation")
    def test_rotation_not_found_maps_to_matchup_not_found(self, game_rotation):
        game_rotation.side_effect = m.WNBARotationNotFoundError("missing")
        with self.assertRaises(m.WNBAMatchupContextNotFoundError):
            m.get_game_opponent_overlap("1022600204", 2026)

    @patch("sports_api.wnba_matchup_context.get_game_rotation")
    def test_rotation_upstream_error_maps_to_matchup_upstream(self, game_rotation):
        game_rotation.side_effect = m.WNBARotationUpstreamError("bad upstream")
        with self.assertRaises(m.WNBAMatchupContextUpstreamError):
            m.get_game_opponent_overlap("1022600204", 2026)

    def test_bad_player_id_fails_before_rotation(self):
        with patch("sports_api.wnba_matchup_context.get_game_rotation") as game_rotation:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_game_opponent_overlap("1022600204", 2026, player_id=0)
            game_rotation.assert_not_called()

    @patch("sports_api.wnba_matchup_context.get_game_opponent_overlap")
    @patch("sports_api.wnba_matchup_context.get_player_game_log_dataset")
    def test_recent_context_aggregates_same_opponent_across_games(self, history, overlap):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}},
                {"game_id": "1022600203", "game_date": "2026-08-24", "matchup": {}},
            ]
        }
        base = {
            "focal_side": "home",
            "focal_player": {"player_id": 20, "team_key": "seattle-storm", "tracked_seconds": 1800.0},
            "pairs": [
                {
                    "away_player": {"player_id": 10, "player_name": "Away One", "team_key": "toronto-tempo"},
                    "home_player": {"player_id": 20, "player_name": "Home One", "team_key": "seattle-storm"},
                    "shared_court_seconds": 1200.0,
                    "shared_court_minutes": 20.0,
                    "shared_court_share_of_home_tracked_time": 2 / 3,
                    "overlap_segment_count": 2,
                }
            ],
        }
        overlap.side_effect = [base, base]
        result = m.get_player_recent_opponent_overlap_context(20, 2026, last_n_games=2)
        self.assertEqual(result["rotation_game_count"], 2)
        self.assertEqual(result["unique_opponent_count"], 1)
        opponent = result["opponents"][0]
        self.assertEqual(opponent["games_with_overlap"], 2)
        self.assertEqual(opponent["shared_court_seconds"], 2400.0)
        self.assertEqual(opponent["shared_court_minutes"], 40.0)
        self.assertAlmostEqual(opponent["shared_court_share_of_focal_time_in_overlap_games"], 2 / 3, places=6)

    @patch("sports_api.wnba_matchup_context.get_game_opponent_overlap")
    @patch("sports_api.wnba_matchup_context.get_player_game_log_dataset")
    def test_recent_opponent_player_filter(self, history, overlap):
        history.return_value = {"games": [{"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}}]}
        overlap.return_value = {
            "focal_side": "home",
            "focal_player": {"player_id": 20, "team_key": "seattle-storm", "tracked_seconds": 1800.0},
            "pairs": [
                {
                    "away_player": {"player_id": 10, "player_name": "Away One", "team_key": "toronto-tempo"},
                    "home_player": {"player_id": 20, "player_name": "Home One", "team_key": "seattle-storm"},
                    "shared_court_seconds": 600.0,
                    "shared_court_minutes": 10.0,
                    "shared_court_share_of_home_tracked_time": 1 / 3,
                    "overlap_segment_count": 1,
                },
                {
                    "away_player": {"player_id": 11, "player_name": "Away Two", "team_key": "toronto-tempo"},
                    "home_player": {"player_id": 20, "player_name": "Home One", "team_key": "seattle-storm"},
                    "shared_court_seconds": 900.0,
                    "shared_court_minutes": 15.0,
                    "shared_court_share_of_home_tracked_time": 0.5,
                    "overlap_segment_count": 2,
                },
            ],
        }
        result = m.get_player_recent_opponent_overlap_context(
            20, 2026, last_n_games=1, opponent_player_id=11
        )
        self.assertEqual(result["unique_opponent_count"], 1)
        self.assertEqual(result["opponents"][0]["opponent_player_id"], 11)

    @patch("sports_api.wnba_matchup_context.get_game_opponent_overlap")
    @patch("sports_api.wnba_matchup_context.get_player_game_log_dataset")
    def test_missing_rotation_game_is_reported(self, history, overlap):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}},
                {"game_id": "1022600203", "game_date": "2026-08-24", "matchup": {}},
            ]
        }
        valid = {
            "focal_side": "home",
            "focal_player": {"player_id": 20, "team_key": "seattle-storm", "tracked_seconds": 600.0},
            "pairs": [],
        }
        overlap.side_effect = [valid, m.WNBAMatchupContextNotFoundError("missing")]
        result = m.get_player_recent_opponent_overlap_context(20, 2026, last_n_games=2)
        self.assertEqual(result["rotation_game_count"], 1)
        self.assertEqual(result["missing_rotation_game_ids"], ["1022600203"])

    @patch("sports_api.wnba_matchup_context.get_player_game_log_dataset")
    def test_empty_player_history_is_not_found(self, history):
        history.return_value = {"games": []}
        with self.assertRaises(m.WNBAMatchupContextNotFoundError):
            m.get_player_recent_opponent_overlap_context(20, 2026)

    @patch("sports_api.wnba_matchup_context.get_game_opponent_overlap")
    @patch("sports_api.wnba_matchup_context.get_player_game_log_dataset")
    def test_specific_opponent_without_overlap_is_not_found(self, history, overlap):
        history.return_value = {"games": [{"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}}]}
        overlap.return_value = {
            "focal_side": "home",
            "focal_player": {"player_id": 20, "team_key": "seattle-storm", "tracked_seconds": 600.0},
            "pairs": [],
        }
        with self.assertRaisesRegex(m.WNBAMatchupContextNotFoundError, "No shared-court overlap"):
            m.get_player_recent_opponent_overlap_context(
                20, 2026, last_n_games=1, opponent_player_id=99
            )

    def test_same_player_cannot_be_opponent_filter(self):
        with patch("sports_api.wnba_matchup_context.get_player_game_log_dataset") as history:
            with self.assertRaisesRegex(ValueError, "must differ"):
                m.get_player_recent_opponent_overlap_context(
                    20, 2026, opponent_player_id=20
                )
            history.assert_not_called()

    def test_bad_last_n_fails_before_history(self):
        with patch("sports_api.wnba_matchup_context.get_player_game_log_dataset") as history:
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_player_recent_opponent_overlap_context(20, 2026, last_n_games=21)
            history.assert_not_called()

    def test_guardrails_never_label_overlap_as_defense(self):
        status = m.get_matchup_source_status(2026)
        unsupported = set(status["unsupported_claims"])
        self.assertIn("primary_defender_assignment", unsupported)
        self.assertIn("matchup_partial_possessions", unsupported)
        self.assertFalse(status["official_player_vs_defender_matchup_feed_available"])


if __name__ == "__main__":
    unittest.main()
