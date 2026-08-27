import unittest
from unittest.mock import patch

from sports_api import wnba_defensive_activity as m


def player_stats(*, minutes="PT30M00S", rim_made=2, rim_attempted=5, contested_made=3, contested_attempted=8):
    return {
        "minutes": minutes,
        "speed": 4.5,
        "distance": 2.1,
        "reboundChancesOffensive": 2,
        "reboundChancesDefensive": 7,
        "reboundChancesTotal": 9,
        "touches": 48,
        "secondaryAssists": 1,
        "freeThrowAssists": 0,
        "passes": 35,
        "assists": 5,
        "contestedFieldGoalsMade": contested_made,
        "contestedFieldGoalsAttempted": contested_attempted,
        "contestedFieldGoalPercentage": 0.375,
        "uncontestedFieldGoalsMade": 2,
        "uncontestedFieldGoalsAttempted": 4,
        "uncontestedFieldGoalPercentage": 0.5,
        "fieldGoalPercentage": 0.4167,
        "defendedAtRimFieldGoalsMade": rim_made,
        "defendedAtRimFieldGoalsAttempted": rim_attempted,
        "defendedAtRimFieldGoalPercentage": 0.4,
    }


def raw_player(person_id, first, last, stats=None):
    return {
        "personId": person_id,
        "firstName": first,
        "familyName": last,
        "nameI": f"{first[0]}. {last}",
        "playerSlug": f"{first.lower()}-{last.lower()}",
        "position": "G",
        "comment": "",
        "jerseyNum": "1",
        "statistics": stats or player_stats(),
    }


def raw_team(team_id, city, name, tricode, slug, players, stats=None):
    return {
        "teamId": team_id,
        "teamCity": city,
        "teamName": name,
        "teamTricode": tricode,
        "teamSlug": slug,
        "players": players,
        "statistics": stats or player_stats(minutes=200),
    }


def payload(*, game_id="1022600204", duplicate=False, unmapped=False):
    away_player_id = 10
    home_player_id = 10 if duplicate else 20
    away = raw_team(
        2,
        "Toronto" if not unmapped else "Mystery",
        "Tempo" if not unmapped else "Mystery",
        "TOR" if not unmapped else "ZZZ",
        "toronto-tempo" if not unmapped else "mystery",
        [raw_player(away_player_id, "Away", "Player")],
    )
    home = raw_team(
        1,
        "Seattle",
        "Storm",
        "SEA",
        "seattle-storm",
        [raw_player(home_player_id, "Home", "Player")],
    )
    return {
        "boxScorePlayerTrack": {
            "gameId": game_id,
            "awayTeam": away,
            "homeTeam": home,
        }
    }


def normalized_game(game_id="1022600204", player_id=20, team_key="seattle-storm", stats=None):
    profile = m._tracking_profile(stats or player_stats())
    other_team = "toronto-tempo" if team_key == "seattle-storm" else "seattle-storm"
    target = {
        "official_team_id": 1,
        "team_key": team_key,
        "team_full_name": "Seattle Storm" if team_key == "seattle-storm" else "Toronto Tempo",
        "team_abbreviation": "SEA" if team_key == "seattle-storm" else "TOR",
        "source_team_tricode": "SEA",
        "source_team_slug": team_key,
        "tracking": profile,
        "player_count": 1,
        "players": [
            {
                "game_id": game_id,
                "player_id": player_id,
                "first_name": "Test",
                "family_name": "Player",
                "name_initial": "T. Player",
                "player_slug": "test-player",
                "position": "G",
                "comment": None,
                "jersey_number": "1",
                "team_key": team_key,
                "team_full_name": "Seattle Storm",
                "tracking": profile,
            }
        ],
    }
    other = {
        "official_team_id": 2,
        "team_key": other_team,
        "team_full_name": "Toronto Tempo",
        "team_abbreviation": "TOR",
        "source_team_tricode": "TOR",
        "source_team_slug": other_team,
        "tracking": m._tracking_profile(player_stats(minutes=200)),
        "player_count": 0,
        "players": [],
    }
    return {
        "away": other,
        "home": target,
    }


class WNBADefensiveActivityTests(unittest.TestCase):
    def test_source_status_disables_dead_hustle_family(self):
        status = m.get_hustle_source_status(2026)
        self.assertEqual(
            status["legacy_hustle_endpoints"]["status"],
            "disabled_dead_no_current_wnba_replacement",
        )
        self.assertIn("deflections", status["legacy_hustle_endpoints"]["metrics_not_claimed"])
        self.assertTrue(status["verification"]["dead_hustle_endpoints_are_not_called"])

    def test_invalid_game_id_fails_before_upstream(self):
        with patch("sports_api.wnba_defensive_activity._request_stats_json") as request:
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                m.get_game_defensive_tracking("123", 2026)
            request.assert_not_called()

    @patch("sports_api.wnba_defensive_activity._request_stats_json")
    def test_game_tracking_normalizes_teams_and_players(self, request):
        request.return_value = (payload(), "x", False)
        result = m.get_game_defensive_tracking("1022600204", 2026)
        self.assertEqual(result["away"]["team_key"], "toronto-tempo")
        self.assertEqual(result["home"]["team_key"], "seattle-storm")
        self.assertEqual(result["player_count"], 2)
        self.assertFalse(result["legacy_hustle_metrics"]["available"])

    def test_contested_fields_are_labeled_offensive_not_defensive(self):
        profile = m._tracking_profile(player_stats())
        section = profile["offensive_contested_shooting"]
        self.assertTrue(section["this_is_offensive_shot_context_not_defensive_contests"])
        self.assertEqual(section["derived_contested_field_goal_percentage"], 0.375)

    def test_defended_at_rim_observed_rate_and_per36(self):
        profile = m._tracking_profile(player_stats())
        rim = profile["defended_at_rim"]
        self.assertEqual(rim["derived_field_goal_percentage_against"], 0.4)
        self.assertEqual(rim["attempts_defended_per_36_minutes"], 6.0)
        self.assertTrue(rim["observed_context_not_causal_defensive_effect"])

    @patch("sports_api.wnba_defensive_activity._request_stats_json")
    def test_duplicate_player_ids_fail_closed(self, request):
        request.return_value = (payload(duplicate=True), "x", False)
        with self.assertRaisesRegex(m.WNBADefensiveActivityUpstreamError, "duplicate player IDs"):
            m.get_game_defensive_tracking("1022600204", 2026)

    @patch("sports_api.wnba_defensive_activity._request_stats_json")
    def test_mismatched_game_id_fails_closed(self, request):
        request.return_value = (payload(game_id="1022600999"), "x", False)
        with self.assertRaisesRegex(m.WNBADefensiveActivityUpstreamError, "expected"):
            m.get_game_defensive_tracking("1022600204", 2026)

    @patch("sports_api.wnba_defensive_activity._request_stats_json")
    def test_unmapped_team_fails_closed(self, request):
        request.return_value = (payload(unmapped=True), "x", False)
        with self.assertRaisesRegex(m.WNBADefensiveActivityUpstreamError, "unmapped team"):
            m.get_game_defensive_tracking("1022600204", 2026)

    @patch("sports_api.wnba_defensive_activity._request_stats_json")
    def test_missing_playertrack_root_is_not_found(self, request):
        request.return_value = ({}, "x", False)
        with self.assertRaises(m.WNBADefensiveActivityNotFoundError):
            m.get_game_defensive_tracking("1022600204", 2026)

    def test_minutes_parser_handles_iso_and_clock(self):
        self.assertEqual(m._minutes_to_float("PT30M30S"), 30.5)
        self.assertEqual(m._minutes_to_float("30:30"), 30.5)

    @patch("sports_api.wnba_defensive_activity.get_game_defensive_tracking")
    @patch("sports_api.wnba_defensive_activity.get_player_game_log_dataset")
    def test_player_recent_tracking_aggregates_weighted_rates(self, history, game_track):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {"opponent_team_key": "toronto-tempo"}},
                {"game_id": "1022600203", "game_date": "2026-08-25", "matchup": {"opponent_team_key": "minnesota-lynx"}},
            ]
        }
        first = normalized_game("1022600204", stats=player_stats(rim_made=2, rim_attempted=5))
        second = normalized_game("1022600203", stats=player_stats(rim_made=1, rim_attempted=5))
        game_track.side_effect = [first, second]
        result = m.get_player_defensive_tracking(20, 2026, last_n_games=2)
        self.assertEqual(result["tracking_game_count"], 2)
        self.assertEqual(
            result["aggregate"]["weighted_rates"]["defended_at_rim_field_goal_percentage_against"],
            0.3,
        )
        self.assertEqual(result["aggregate"]["totals"]["minutes"], 60.0)

    @patch("sports_api.wnba_defensive_activity.get_game_defensive_tracking")
    @patch("sports_api.wnba_defensive_activity.get_player_game_log_dataset")
    def test_player_missing_tracking_game_is_reported(self, history, game_track):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}},
                {"game_id": "1022600203", "game_date": "2026-08-25", "matchup": {}},
            ]
        }
        game_track.side_effect = [
            normalized_game("1022600204"),
            m.WNBADefensiveActivityNotFoundError("missing"),
        ]
        result = m.get_player_defensive_tracking(20, 2026, last_n_games=2)
        self.assertEqual(result["tracking_game_count"], 1)
        self.assertEqual(result["missing_tracking_game_ids"], ["1022600203"])

    @patch("sports_api.wnba_defensive_activity.get_game_defensive_tracking")
    @patch("sports_api.wnba_defensive_activity.get_team_game_log_dataset")
    def test_team_recent_tracking_aggregates(self, history, game_track):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "location": "home", "opponent_team_key": "toronto-tempo"},
                {"game_id": "1022600203", "game_date": "2026-08-25", "location": "away", "opponent_team_key": "minnesota-lynx"},
            ]
        }
        game_track.side_effect = [
            normalized_game("1022600204"),
            normalized_game("1022600203"),
        ]
        result = m.get_team_defensive_tracking("seattle-storm", 2026, last_n_games=2)
        self.assertEqual(result["tracking_game_count"], 2)
        self.assertEqual(result["aggregate"]["games_with_tracking"], 2)
        self.assertTrue(result["verification"]["selected_games_come_from_official_team_game_log"])

    def test_last_n_over_20_fails_before_history(self):
        with patch("sports_api.wnba_defensive_activity.get_team_game_log_dataset") as history:
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_team_defensive_tracking("seattle-storm", 2026, last_n_games=21)
            history.assert_not_called()

    def test_bad_player_id_fails_before_history(self):
        with patch("sports_api.wnba_defensive_activity.get_player_game_log_dataset") as history:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_defensive_tracking(0, 2026)
            history.assert_not_called()

    def test_aggregate_does_not_sum_percentages(self):
        profiles = [
            m._tracking_profile(player_stats(contested_made=1, contested_attempted=2)),
            m._tracking_profile(player_stats(contested_made=1, contested_attempted=8)),
        ]
        agg = m._aggregate_profiles(profiles)
        self.assertEqual(
            agg["weighted_rates"]["offensive_contested_field_goal_percentage"],
            0.2,
        )
        self.assertTrue(
            agg["verification"]["advanced_percentages_are_weighted_from_makes_and_attempts"]
        )


if __name__ == "__main__":
    unittest.main()
