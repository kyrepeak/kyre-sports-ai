import unittest
from unittest.mock import patch

from sports_api import wnba_rotation_context as m


HEADERS = [
    "GAME_ID", "TEAM_ID", "TEAM_CITY", "TEAM_NAME", "PERSON_ID",
    "PLAYER_FIRST", "PLAYER_LAST", "IN_TIME_REAL", "OUT_TIME_REAL",
    "PLAYER_PTS", "PT_DIFF", "USG_PCT",
]


def row(
    *,
    game_id="1022600204",
    team_id=1,
    city="Seattle",
    team_name="Storm",
    player_id=20,
    first="Test",
    last="Player",
    in_time=0.0,
    out_time=6000.0,
    points=4,
    point_diff=3.0,
    usage=.25,
):
    return [
        game_id, team_id, city, team_name, player_id, first, last,
        in_time, out_time, points, point_diff, usage,
    ]


def payload(*, away_rows=None, home_rows=None, headers=None):
    if away_rows is None:
        away_rows = [
            row(
                team_id=2,
                city="Toronto",
                team_name="Tempo",
                player_id=10,
                first="Away",
                last="Player",
                in_time=0,
                out_time=24000,
                points=12,
                point_diff=-2,
                usage=.2,
            )
        ]
    if home_rows is None:
        home_rows = [
            row(in_time=0, out_time=6000, points=5, point_diff=4, usage=.3),
            row(in_time=9000, out_time=24000, points=10, point_diff=6, usage=.4),
        ]
    used_headers = headers or HEADERS
    return {
        "resultSets": [
            {"name": "AwayTeam", "headers": used_headers, "rowSet": away_rows},
            {"name": "HomeTeam", "headers": used_headers, "rowSet": home_rows},
        ]
    }


def normalized_game(game_id="1022600204", player_id=20, team_key="seattle-storm"):
    stint = {
        "side": "home",
        "game_id": game_id,
        "official_team_id": 1,
        "team_key": team_key,
        "team_full_name": "Seattle Storm",
        "player_id": player_id,
        "player_first_name": "Test",
        "player_last_name": "Player",
        "player_name": "Test Player",
        "in_time_real": 0.0,
        "out_time_real": 6000.0,
        "in_elapsed_seconds": 0.0,
        "out_elapsed_seconds": 600.0,
        "in_elapsed_minutes": 0.0,
        "out_elapsed_minutes": 10.0,
        "duration_seconds": 600.0,
        "duration_minutes": 10.0,
        "start": {"period": 1},
        "end": {"period": 1},
        "player_points_during_stint": 6.0,
        "team_point_differential_during_stint": 2.0,
        "usage_percentage_during_stint": .25,
    }
    player = {
        "player_id": player_id,
        "player_name": "Test Player",
        "official_team_id": 1,
        "team_key": team_key,
        "team_full_name": "Seattle Storm",
        "stint_count": 1,
        "tracked_seconds": 600.0,
        "tracked_minutes": 10.0,
        "average_stint_seconds": 600.0,
        "longest_stint_seconds": 600.0,
        "shortest_stint_seconds": 600.0,
        "player_points_during_stints": 6.0,
        "team_point_differential_during_stints": 2.0,
        "time_weighted_usage_percentage": .25,
        "started_game": True,
        "finished_game": False,
        "first_entry_elapsed_seconds": 0.0,
        "last_exit_elapsed_seconds": 600.0,
        "stints": [stint],
    }
    other = {
        "side": "away",
        "official_team_id": 2,
        "team_key": "toronto-tempo",
        "team_full_name": "Toronto Tempo",
        "player_count": 0,
        "stint_count": 0,
        "maximum_source_time_tenths": 6000,
        "maximum_elapsed_seconds": 600.0,
        "players": [],
        "stints": [],
    }
    side = {
        "side": "home",
        "official_team_id": 1,
        "team_key": team_key,
        "team_full_name": "Seattle Storm",
        "player_count": 1,
        "stint_count": 1,
        "maximum_source_time_tenths": 6000,
        "maximum_elapsed_seconds": 600.0,
        "players": [player],
        "stints": [stint],
    }
    return {
        "source": "WNBA Stats API",
        "source_url": "https://stats.wnba.com/",
        "source_endpoint": "gamerotation",
        "league_id": "10",
        "rotation_stat": "PLAYER_PTS",
        "time_basis": {},
        "away": other,
        "home": side,
        "game_id": game_id,
    }


class WNBARotationContextTests(unittest.TestCase):
    def test_rotation_clock_uses_wnba_period_lengths_and_boundary_roles(self):
        self.assertEqual(m._clock_from_tenths(6000, boundary_role="in")["period_label"], "Q2")
        self.assertEqual(m._clock_from_tenths(6000, boundary_role="in")["game_clock"], "10:00.0")
        self.assertEqual(m._clock_from_tenths(6000, boundary_role="out")["period_label"], "Q1")
        self.assertEqual(m._clock_from_tenths(6000, boundary_role="out")["game_clock"], "0:00.0")
        self.assertEqual(m._clock_from_tenths(24000, boundary_role="in")["period_label"], "OT1")
        self.assertEqual(m._clock_from_tenths(24000, boundary_role="in")["game_clock"], "5:00.0")
        self.assertEqual(m._clock_from_tenths(24000, boundary_role="out")["period_label"], "Q4")

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_game_rotation_normalizes_stints_and_player_summary(self, request):
        request.return_value = (payload(), "x", False, 60)
        result = m.get_game_rotation("1022600204", 2026)
        self.assertEqual(result["away"]["team_key"], "toronto-tempo")
        self.assertEqual(result["home"]["team_key"], "seattle-storm")
        player = result["home"]["players"][0]
        self.assertEqual(player["stint_count"], 2)
        self.assertEqual(player["tracked_minutes"], 35.0)
        self.assertEqual(player["player_points_during_stints"], 15.0)
        self.assertAlmostEqual(player["time_weighted_usage_percentage"], 0.371429, places=6)
        self.assertTrue(player["started_game"])
        self.assertTrue(player["finished_game"])

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_league_id_is_first_and_rotation_stat_forwarded(self, request):
        request.return_value = (payload(), "x", False, 60)
        m.get_game_rotation("1022600204", 2026, rotation_stat="USG_PCT")
        endpoint, params = request.call_args.args
        self.assertEqual(endpoint, m.ROTATION_ENDPOINT)
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertEqual(dict(params)["RotationStat"], "USG_PCT")

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_source_tenths_convert_to_seconds_and_minutes(self, request):
        request.return_value = (payload(), "x", False, 60)
        result = m.get_game_rotation("1022600204", 2026)
        stint = result["home"]["stints"][0]
        self.assertEqual(stint["out_elapsed_seconds"], 600.0)
        self.assertEqual(stint["duration_minutes"], 10.0)
        self.assertEqual(result["time_basis"]["source_units"], "tenths_of_a_second_elapsed_from_game_start")

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_duplicate_stint_fails_closed(self, request):
        duplicate = row(in_time=0, out_time=6000)
        request.return_value = (payload(home_rows=[duplicate, duplicate]), "x", False, 60)
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "duplicate stint"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_mismatched_game_id_fails_closed(self, request):
        request.return_value = (payload(home_rows=[row(game_id="1022600999")]), "x", False, 60)
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "expected"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_multiple_team_ids_on_one_side_fail_closed(self, request):
        request.return_value = (
            payload(home_rows=[row(team_id=1), row(team_id=3, in_time=6000, out_time=12000)]),
            "x", False, 60,
        )
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "multiple team identities"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_empty_rotation_is_not_found(self, request):
        request.return_value = (payload(away_rows=[], home_rows=[]), "x", False, 60)
        with self.assertRaises(m.WNBARotationNotFoundError):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_one_sided_rotation_fails_closed(self, request):
        request.return_value = (payload(away_rows=[], home_rows=[row()]), "x", False, 60)
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "only one team"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_player_id_cannot_appear_on_both_teams(self, request):
        request.return_value = (
            payload(
                away_rows=[row(team_id=2, city="Toronto", team_name="Tempo", player_id=20, in_time=0, out_time=24000)],
                home_rows=[row(player_id=20, in_time=0, out_time=24000)],
            ),
            "x", False, 60,
        )
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "both teams"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_bad_interval_fails_closed(self, request):
        request.return_value = (payload(home_rows=[row(in_time=7000, out_time=6000)]), "x", False, 60)
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "invalid in/out"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_malformed_schema_fails_closed(self, request):
        bad_headers = [item for item in HEADERS if item != "USG_PCT"]
        request.return_value = (
            payload(
                away_rows=[row(team_id=2, city="Toronto", team_name="Tempo", player_id=10)[:-1]],
                home_rows=[row()[:-1]],
                headers=bad_headers,
            ),
            "x", False, 60,
        )
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "missing required fields"):
            m.get_game_rotation("1022600204", 2026)

    @patch("sports_api.wnba_rotation_context.get_game_rotation")
    def test_game_player_rotation_returns_one_player(self, game_rotation):
        game_rotation.return_value = normalized_game()
        result = m.get_game_player_rotation("1022600204", 20, 2026)
        self.assertEqual(result["player"]["player_id"], 20)
        self.assertTrue(result["verification"]["stints_are_observed_not_projected"])

    @patch("sports_api.wnba_rotation_context.get_game_rotation")
    def test_game_player_rotation_missing_player_is_not_found(self, game_rotation):
        game_rotation.return_value = normalized_game()
        with self.assertRaises(m.WNBARotationNotFoundError):
            m.get_game_player_rotation("1022600204", 999, 2026)

    @patch("sports_api.wnba_rotation_context.get_game_rotation")
    @patch("sports_api.wnba_rotation_context.get_player_game_log_dataset")
    def test_recent_player_rotation_aggregates_games(self, history, game_rotation):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}},
                {"game_id": "1022600203", "game_date": "2026-08-24", "matchup": {}},
            ]
        }
        game_rotation.side_effect = [normalized_game("1022600204"), normalized_game("1022600203")]
        result = m.get_player_recent_rotation_context(20, 2026, last_n_games=2)
        self.assertEqual(result["rotation_game_count"], 2)
        self.assertEqual(result["aggregate"]["stint_count"], 2)
        self.assertEqual(result["aggregate"]["tracked_minutes"], 20.0)
        self.assertEqual(result["aggregate"]["time_weighted_usage_percentage"], .25)
        self.assertEqual(result["aggregate"]["start_share"], 1.0)

    @patch("sports_api.wnba_rotation_context.get_game_rotation")
    @patch("sports_api.wnba_rotation_context.get_player_game_log_dataset")
    def test_recent_missing_rotation_game_is_reported(self, history, game_rotation):
        history.return_value = {
            "games": [
                {"game_id": "1022600204", "game_date": "2026-08-26", "matchup": {}},
                {"game_id": "1022600203", "game_date": "2026-08-24", "matchup": {}},
            ]
        }
        game_rotation.side_effect = [normalized_game("1022600204"), m.WNBARotationNotFoundError("missing")]
        result = m.get_player_recent_rotation_context(20, 2026, last_n_games=2)
        self.assertEqual(result["rotation_game_count"], 1)
        self.assertEqual(result["missing_rotation_game_ids"], ["1022600203"])

    def test_invalid_rotation_stat_fails_before_network(self):
        with patch("sports_api.wnba_rotation_context._request_stats_json") as request:
            with self.assertRaisesRegex(ValueError, "rotation_stat"):
                m.get_game_rotation("1022600204", 2026, rotation_stat="BAD")
            request.assert_not_called()

    def test_bad_game_id_fails_before_network(self):
        with patch("sports_api.wnba_rotation_context._request_stats_json") as request:
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                m.get_game_rotation("123", 2026)
            request.assert_not_called()

    def test_bad_player_id_and_last_n_fail_before_history(self):
        with patch("sports_api.wnba_rotation_context.get_player_game_log_dataset") as history:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_recent_rotation_context(0, 2026)
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_player_recent_rotation_context(20, 2026, last_n_games=21)
            history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
