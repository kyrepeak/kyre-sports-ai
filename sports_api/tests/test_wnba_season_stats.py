import unittest
from unittest.mock import patch

from sports_api.wnba_season_stats import (
    WNBASeasonStatsUpstreamError,
    _normalize_windows,
    _result_rows,
    get_player_rolling_stats_dataset,
    get_player_season_stats_dataset,
    get_team_season_stats_dataset,
)


def _result_set(name, headers, rows):
    return {"name": name, "headers": headers, "rowSet": rows}


def _player_payload(rows):
    headers = [
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ID",
        "TEAM_ABBREVIATION",
        "AGE",
        "GP",
        "W",
        "L",
        "W_PCT",
        "MIN",
        "FGM",
        "FGA",
        "FG_PCT",
        "FG3M",
        "FG3A",
        "FG3_PCT",
        "FTM",
        "FTA",
        "FT_PCT",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "TOV",
        "STL",
        "BLK",
        "BLKA",
        "PF",
        "PFD",
        "PTS",
        "PLUS_MINUS",
        "NBA_FANTASY_PTS",
        "DD2",
        "TD3",
    ]
    return {
        "resultSets": [
            _result_set("LeagueDashPlayerStats", headers, rows)
        ]
    }


def _player_row(
    player_id=1642286,
    name="Caitlin Clark",
    team_id=1611661325,
    abbreviation="IND",
    points=21.4,
):
    return [
        player_id,
        name,
        team_id,
        abbreviation,
        24.0,
        30,
        20,
        10,
        0.667,
        34.5,
        7.1,
        16.0,
        0.444,
        3.0,
        8.0,
        0.375,
        4.2,
        4.8,
        0.875,
        0.7,
        4.5,
        5.2,
        8.1,
        4.1,
        1.5,
        0.7,
        0.4,
        2.3,
        4.5,
        points,
        5.4,
        39.2,
        8,
        2,
    ]


def _team_payload(rows):
    headers = [
        "TEAM_ID",
        "TEAM_NAME",
        "GP",
        "W",
        "L",
        "W_PCT",
        "MIN",
        "FGM",
        "FGA",
        "FG_PCT",
        "FG3M",
        "FG3A",
        "FG3_PCT",
        "FTM",
        "FTA",
        "FT_PCT",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "TOV",
        "STL",
        "BLK",
        "BLKA",
        "PF",
        "PFD",
        "PTS",
        "PLUS_MINUS",
    ]
    return {
        "resultSets": [
            _result_set("LeagueDashTeamStats", headers, rows)
        ]
    }


def _team_row(
    team_id=1611661313,
    name="New York Liberty",
    points=86.5,
):
    return [
        team_id,
        name,
        30,
        21,
        9,
        0.700,
        200.0,
        31.0,
        69.0,
        0.449,
        10.0,
        28.0,
        0.357,
        14.5,
        18.0,
        0.806,
        8.0,
        26.0,
        34.0,
        21.0,
        12.0,
        7.0,
        4.0,
        3.0,
        17.0,
        18.0,
        points,
        4.5,
    ]


def _game(game_id, game_date, points, rebounds, assists, *, fgm=8, fga=16):
    return {
        "game_id": game_id,
        "game_id_valid": True,
        "game_date": game_date,
        "minutes": 35.0,
        "field_goals_made": fgm,
        "field_goals_attempted": fga,
        "field_goal_percentage": fgm / fga,
        "three_pointers_made": 3,
        "three_pointers_attempted": 8,
        "three_point_percentage": 0.375,
        "free_throws_made": 4,
        "free_throws_attempted": 5,
        "free_throw_percentage": 0.8,
        "offensive_rebounds": 1,
        "defensive_rebounds": rebounds - 1,
        "rebounds": rebounds,
        "assists": assists,
        "steals": 1,
        "blocks": 0,
        "turnovers": 3,
        "personal_fouls": 2,
        "points": points,
        "plus_minus": 5,
    }


class WNBASeasonStatsTests(unittest.TestCase):
    def test_result_rows_maps_headers(self):
        payload = {
            "resultSets": [
                _result_set("Example", ["A", "B"], [[1, 2]])
            ]
        }
        self.assertEqual(_result_rows(payload, "Example"), [{"A": 1, "B": 2}])

    @patch("sports_api.wnba_season_stats._request_stats_json")
    def test_player_season_stats_normalize_and_map_registry(self, mock_request):
        mock_request.return_value = (
            _player_payload([_player_row()]),
            "2026-08-26T04:45:00+00:00",
            False,
        )

        dataset = get_player_season_stats_dataset(2026)

        self.assertEqual(dataset["player_count"], 1)
        player = dataset["players"][0]
        self.assertEqual(player["player_id"], 1642286)
        self.assertEqual(player["team_key"], "indiana-fever")
        self.assertEqual(player["stats"]["points"], 21.4)
        self.assertEqual(player["stats"]["assists"], 8.1)
        self.assertTrue(dataset["verification"]["all_rows_mapped_to_registry"])

        params = mock_request.call_args.args[1]
        self.assertIn(("LeagueID", "10"), params)
        self.assertIn(("LastNGames", "0"), params)
        self.assertIn(("PerMode", "PerGame"), params)

    @patch("sports_api.wnba_season_stats._request_stats_json")
    def test_player_stats_support_last_n_and_team_filter(self, mock_request):
        mock_request.return_value = (
            _player_payload(
                [
                    _player_row(),
                    _player_row(
                        player_id=1629477,
                        name="Sabrina Ionescu",
                        team_id=1611661313,
                        abbreviation="NYL",
                        points=19.8,
                    ),
                ]
            ),
            "2026-08-26T04:45:00+00:00",
            False,
        )

        dataset = get_player_season_stats_dataset(
            2026,
            last_n_games=5,
            team_key="indiana-fever",
        )

        self.assertEqual(dataset["window_scope"], "last_5_games")
        self.assertEqual(dataset["player_count"], 1)
        self.assertEqual(dataset["players"][0]["team_key"], "indiana-fever")

    @patch("sports_api.wnba_season_stats._request_stats_json")
    def test_team_season_stats_normalize_and_map_registry(self, mock_request):
        mock_request.return_value = (
            _team_payload([_team_row()]),
            "2026-08-26T04:45:00+00:00",
            False,
        )

        dataset = get_team_season_stats_dataset(2026, per_mode="totals")

        self.assertEqual(dataset["per_mode"], "Totals")
        self.assertEqual(dataset["team_count"], 1)
        team = dataset["teams"][0]
        self.assertEqual(team["team_key"], "new-york-liberty")
        self.assertEqual(team["stats"]["points"], 86.5)
        self.assertTrue(team["mapped_to_registry"])

    @patch("sports_api.wnba_season_stats._request_stats_json")
    def test_unmapped_player_team_is_reported_not_silently_mapped(self, mock_request):
        mock_request.return_value = (
            _player_payload(
                [
                    _player_row(
                        team_id=0,
                        abbreviation="TOT",
                    )
                ]
            ),
            "2026-08-26T04:45:00+00:00",
            False,
        )

        dataset = get_player_season_stats_dataset(2026)

        self.assertIsNone(dataset["players"][0]["team_key"])
        self.assertEqual(dataset["verification"]["unmapped_team_count"], 1)
        self.assertFalse(dataset["verification"]["all_rows_mapped_to_registry"])

    def test_invalid_last_n_games_fails_before_network(self):
        with patch("sports_api.wnba_season_stats._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "0 through 100"):
                get_team_season_stats_dataset(2026, last_n_games=101)
            mock_request.assert_not_called()

    def test_invalid_per_mode_fails_before_network(self):
        with patch("sports_api.wnba_season_stats._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "Unsupported WNBA per_mode"):
                get_player_season_stats_dataset(2026, per_mode="PerPossession")
            mock_request.assert_not_called()

    def test_windows_parser_deduplicates_and_validates(self):
        self.assertEqual(_normalize_windows("5,10,5"), (5, 10))
        with self.assertRaisesRegex(ValueError, "1 through 50"):
            _normalize_windows("0,5")

    @patch("sports_api.wnba_season_stats.get_player_game_log_dataset")
    def test_player_rolling_stats_build_last_5_and_last_10(self, mock_game_log):
        games = [
            _game(f"10226003{i:02d}", f"2026-08-{25 - i:02d}", 20 + i, 5 + i, 7 + i)
            for i in range(10)
        ]
        mock_game_log.return_value = {
            "source": "WNBA Stats API",
            "source_url": "https://stats.wnba.com/",
            "source_endpoint": "playergamelog",
            "player_id": 1642286,
            "retrieved_at_utc": "2026-08-26T04:45:00+00:00",
            "cache_hit": False,
            "games": games,
            "verification": {
                "all_game_ids_valid": True,
                "all_game_ids_unique": True,
                "all_matchup_teams_mapped_to_registry": True,
            },
        }

        dataset = get_player_rolling_stats_dataset(1642286, 2026)

        self.assertEqual(dataset["windows"], [5, 10])
        last_5 = dataset["rolling"]["last_5"]
        self.assertEqual(last_5["games_used"], 5)
        self.assertTrue(last_5["complete_window"])
        self.assertEqual(last_5["averages"]["points"], 22.0)
        self.assertEqual(last_5["averages"]["rebounds"], 7.0)
        self.assertEqual(last_5["averages"]["assists"], 9.0)
        self.assertEqual(last_5["averages"]["points_rebounds_assists"], 38.0)
        self.assertEqual(last_5["shooting"]["field_goal_percentage"], 0.5)

    @patch("sports_api.wnba_season_stats.get_player_game_log_dataset")
    def test_player_rolling_stats_marks_incomplete_window(self, mock_game_log):
        mock_game_log.return_value = {
            "source": "WNBA Stats API",
            "source_url": "https://stats.wnba.com/",
            "source_endpoint": "playergamelog",
            "player_id": 1642286,
            "retrieved_at_utc": "2026-08-26T04:45:00+00:00",
            "cache_hit": False,
            "games": [
                _game("1022600300", "2026-08-25", 20, 5, 7),
                _game("1022600299", "2026-08-23", 18, 4, 6),
            ],
            "verification": {
                "all_game_ids_valid": True,
                "all_game_ids_unique": True,
                "all_matchup_teams_mapped_to_registry": True,
            },
        }

        dataset = get_player_rolling_stats_dataset(
            1642286,
            2026,
            windows="5",
        )

        last_5 = dataset["rolling"]["last_5"]
        self.assertEqual(last_5["games_used"], 2)
        self.assertFalse(last_5["complete_window"])

    def test_missing_result_set_fails_closed(self):
        with self.assertRaises(WNBASeasonStatsUpstreamError):
            _result_rows({"resultSets": []}, "LeagueDashPlayerStats")


if __name__ == "__main__":
    unittest.main()
