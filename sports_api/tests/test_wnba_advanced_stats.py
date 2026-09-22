import unittest
from unittest.mock import patch

from sports_api.wnba_advanced_stats import (
    WNBAAdvancedStatsUpstreamError,
    _result_set,
    get_player_advanced_stats_dataset,
    get_team_advanced_stats_dataset,
)


PLAYER_HEADERS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE",
    "GP", "W", "L", "W_PCT", "MIN",
    "E_OFF_RATING", "OFF_RATING", "E_DEF_RATING", "DEF_RATING",
    "E_NET_RATING", "NET_RATING", "AST_PCT", "AST_TO", "AST_RATIO",
    "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "EFG_PCT",
    "TS_PCT", "E_USG_PCT", "USG_PCT", "E_PACE", "PACE", "PACE_PER40",
    "POSS", "PIE", "FGM", "FGA", "FGM_PG", "FGA_PG", "FG_PCT",
]

TEAM_HEADERS = [
    "TEAM_ID", "TEAM_NAME", "GP", "W", "L", "W_PCT", "MIN",
    "E_OFF_RATING", "OFF_RATING", "E_DEF_RATING", "DEF_RATING",
    "E_NET_RATING", "NET_RATING", "AST_PCT", "AST_TO", "AST_RATIO",
    "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "EFG_PCT",
    "TS_PCT", "E_PACE", "PACE", "PACE_PER40", "POSS", "PIE",
]


def _payload(name, headers, rows):
    return {"resultSets": [{"name": name, "headers": headers, "rowSet": rows}]}


def _player_row(
    player_id=1642286,
    name="Caitlin Clark",
    team_id=1611661325,
    abbreviation="IND",
):
    return [
        player_id, name, team_id, abbreviation, 24.0,
        30, 20, 10, 0.667, 34.5,
        112.1, 113.0, 104.0, 105.0,
        8.1, 8.0, 0.42, 2.1, 22.0,
        0.03, 0.11, 0.07, 0.13, 0.55,
        0.59, 0.28, 0.29, 100.8, 99.7, 83.1,
        75.0, 0.16, 7.1, 16.0, 7.1, 16.0, 0.444,
    ]


def _team_row(
    team_id=1611661313,
    name="New York Liberty",
):
    return [
        team_id, name, 30, 21, 9, 0.700, 1200.0,
        113.2, 114.0, 105.1, 106.0,
        8.1, 8.0, 0.64, 2.0, 19.5,
        0.28, 0.72, 0.51, 0.14, 0.56,
        0.60, 101.0, 99.8, 83.2, 2994.0, 0.55,
    ]


class WNBAAdvancedStatsTests(unittest.TestCase):
    def test_result_set_maps_headers_to_rows(self):
        headers, rows = _result_set(
            _payload("Example", ["A", "B"], [[1, 2]]),
            "Example",
        )
        self.assertEqual(headers, ["A", "B"])
        self.assertEqual(rows, [{"A": 1, "B": 2}])

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_player_advanced_normalizes_usage_pace_ratings_and_registry(self, mock_request):
        mock_request.return_value = (
            _payload("LeagueDashPlayerStats", PLAYER_HEADERS, [_player_row()]),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_player_advanced_stats_dataset(2026)

        self.assertEqual(dataset["player_count"], 1)
        player = dataset["players"][0]
        self.assertEqual(player["team_key"], "indiana-fever")
        self.assertEqual(player["advanced"]["usage_percentage"], 0.29)
        self.assertEqual(player["advanced"]["pace"], 99.7)
        self.assertEqual(player["advanced"]["offensive_rating"], 113.0)
        self.assertEqual(player["advanced"]["true_shooting_percentage"], 0.59)
        self.assertTrue(dataset["verification"]["advanced_schema_verified"])

        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("MeasureType", "Advanced"), params)

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_player_advanced_supports_last_n_team_and_player_filters(self, mock_request):
        rows = [
            _player_row(),
            _player_row(1629477, "Sabrina Ionescu", 1611661313, "NYL"),
        ]
        mock_request.return_value = (
            _payload("LeagueDashPlayerStats", PLAYER_HEADERS, rows),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_player_advanced_stats_dataset(
            2026,
            last_n_games=5,
            team_key="indiana-fever",
            player_id=1642286,
        )

        self.assertEqual(dataset["window_scope"], "last_5_games")
        self.assertEqual(dataset["player_count"], 1)
        self.assertEqual(dataset["players"][0]["player_id"], 1642286)

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_team_advanced_normalizes_ratings_pace_possessions_and_ts(self, mock_request):
        mock_request.return_value = (
            _payload("LeagueDashTeamStats", TEAM_HEADERS, [_team_row()]),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_team_advanced_stats_dataset(2026)

        team = dataset["teams"][0]
        self.assertEqual(team["team_key"], "new-york-liberty")
        self.assertEqual(team["advanced"]["offensive_rating"], 114.0)
        self.assertEqual(team["advanced"]["defensive_rating"], 106.0)
        self.assertEqual(team["advanced"]["net_rating"], 8.0)
        self.assertEqual(team["advanced"]["pace"], 99.8)
        self.assertEqual(team["advanced"]["possessions"], 2994.0)
        self.assertEqual(team["advanced"]["true_shooting_percentage"], 0.60)

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_team_filter_uses_stable_team_key(self, mock_request):
        rows = [
            _team_row(),
            _team_row(1611661325, "Indiana Fever"),
        ]
        mock_request.return_value = (
            _payload("LeagueDashTeamStats", TEAM_HEADERS, rows),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_team_advanced_stats_dataset(
            2026,
            team_key="indiana-fever",
        )

        self.assertEqual(dataset["team_count"], 1)
        self.assertEqual(dataset["teams"][0]["team_key"], "indiana-fever")

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_unmapped_player_team_is_preserved_and_flagged(self, mock_request):
        mock_request.return_value = (
            _payload(
                "LeagueDashPlayerStats",
                PLAYER_HEADERS,
                [_player_row(team_id=0, abbreviation="TOT")],
            ),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_player_advanced_stats_dataset(2026)

        self.assertIsNone(dataset["players"][0]["team_key"])
        self.assertEqual(dataset["verification"]["unmapped_team_count"], 1)
        self.assertFalse(dataset["verification"]["all_rows_mapped_to_registry"])

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_duplicate_player_ids_are_reported(self, mock_request):
        mock_request.return_value = (
            _payload(
                "LeagueDashPlayerStats",
                PLAYER_HEADERS,
                [
                    _player_row(),
                    _player_row(1642286, "Caitlin Clark", 1611661313, "NYL"),
                ],
            ),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_player_advanced_stats_dataset(2026)

        self.assertFalse(dataset["verification"]["player_ids_unique"])
        self.assertEqual(dataset["verification"]["duplicate_player_ids"], [1642286])

    def test_invalid_last_n_games_fails_before_network(self):
        with patch("sports_api.wnba_advanced_stats._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "0 through 100"):
                get_team_advanced_stats_dataset(2026, last_n_games=101)
            mock_request.assert_not_called()

    def test_invalid_per_mode_fails_before_network(self):
        with patch("sports_api.wnba_advanced_stats._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "Unsupported WNBA per_mode"):
                get_player_advanced_stats_dataset(2026, per_mode="PerPossession")
            mock_request.assert_not_called()

    def test_invalid_player_id_fails_before_network(self):
        with patch("sports_api.wnba_advanced_stats._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                get_player_advanced_stats_dataset(2026, player_id=0)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_base_schema_is_rejected_fail_closed(self, mock_request):
        mock_request.return_value = (
            _payload(
                "LeagueDashPlayerStats",
                ["PLAYER_ID", "PLAYER_NAME", "PTS", "REB", "AST"],
                [[1642286, "Caitlin Clark", 21.0, 5.0, 8.0]],
            ),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        with self.assertRaises(WNBAAdvancedStatsUpstreamError):
            get_player_advanced_stats_dataset(2026)

    @patch("sports_api.wnba_advanced_stats._request_stats_json")
    def test_estimated_usage_and_pace_satisfy_schema_and_availability(self, mock_request):
        headers = [
            "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
            "GP", "MIN", "E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING",
            "AST_PCT", "E_USG_PCT", "E_PACE",
        ]
        row = [
            1642286, "Caitlin Clark", 1611661325, "IND",
            30, 34.5, 112.0, 105.0, 7.0,
            0.4, 0.28, 100.5,
        ]
        mock_request.return_value = (
            _payload("LeagueDashPlayerStats", headers, [row]),
            "2026-08-26T04:52:00+00:00",
            False,
        )

        dataset = get_player_advanced_stats_dataset(2026)

        self.assertTrue(dataset["verification"]["usage_metric_available_for_all_rows"])
        self.assertTrue(dataset["verification"]["pace_metric_available_for_all_rows"])
        self.assertEqual(dataset["players"][0]["advanced"]["estimated_usage_percentage"], 0.28)
        self.assertEqual(dataset["players"][0]["advanced"]["estimated_pace"], 100.5)


if __name__ == "__main__":
    unittest.main()
