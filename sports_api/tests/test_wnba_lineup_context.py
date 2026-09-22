import unittest
from unittest.mock import patch

from sports_api.wnba_lineup_context import (
    WNBALineupContextNotFoundError,
    WNBALineupContextUpstreamError,
    _result_set,
    get_lineups_dataset,
    get_player_role_context_dataset,
    get_team_on_off_dataset,
)


LINEUP_HEADERS = [
    "GROUP_SET", "GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
    "GP", "W", "L", "W_PCT", "MIN", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB",
    "DREB", "REB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD",
    "PTS", "PLUS_MINUS",
]

ON_OFF_HEADERS = [
    "GROUP_SET", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME",
    "VS_PLAYER_ID", "VS_PLAYER_NAME", "COURT_STATUS", "GP", "MIN",
    "PLUS_MINUS", "OFF_RATING", "DEF_RATING", "NET_RATING",
]

OVERALL_HEADERS = [
    "GROUP_SET", "GROUP_VALUE", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME",
    "GP", "W", "L", "W_PCT", "MIN", "PTS", "PLUS_MINUS",
]

ROLE_HEADERS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
    "GP", "W", "L", "W_PCT", "MIN", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB",
    "DREB", "REB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD",
    "PTS", "PLUS_MINUS",
]


def _payload(name, headers, rows):
    return {"resultSets": [{"name": name, "headers": headers, "rowSet": rows}]}


def _multi_payload(result_sets):
    return {
        "resultSets": [
            {"name": name, "headers": headers, "rowSet": rows}
            for name, headers, rows in result_sets
        ]
    }


def _lineup_row():
    return [
        "Lineups",
        "-1642286-1629482-1630163-1641652-1628334-",
        "Caitlin Clark - Kelsey Mitchell - Aliyah Boston - Lexie Hull - Natasha Howard",
        1611661325,
        "IND",
        18, 12, 6, 0.667, 210.5,
        40, 80, 0.5, 12, 30, 0.4, 20, 25, 0.8,
        10, 30, 40, 25, 12, 8, 6, 2, 18, 20, 112, 18.0,
    ]


def _on_row(player_id=1642286, name="Caitlin Clark"):
    return [
        "On", 1611661325, "IND", "Indiana Fever", player_id, name, "On",
        30, 900.0, 120.0, 116.0, 108.0, 8.0,
    ]


def _off_row(player_id=1642286, name="Caitlin Clark"):
    return [
        "Off", 1611661325, "IND", "Indiana Fever", player_id, name, "Off",
        30, 500.0, -20.0, 108.0, 112.0, -4.0,
    ]


def _overall_row():
    return [
        "Overall", "Indiana Fever", 1611661325, "IND", "Indiana Fever",
        30, 20, 10, 0.667, 1400.0, 2500, 100.0,
    ]


def _role_row(role, games, minutes, points):
    del role
    return [
        1642286, "Caitlin Clark", 1611661325, "IND",
        games, 10, 5, 0.667, minutes,
        7.0, 16.0, 0.438, 3.0, 8.0, 0.375, 4.0, 5.0, 0.8,
        0.5, 4.0, 4.5, 8.0, 3.0, 1.5, 0.5, 0.2, 2.0, 4.0,
        points, 5.0,
    ]


def _current_players_dataset():
    return {
        "players": [
            {
                "player_id": 1642286,
                "team_key": "indiana-fever",
                "official_team_id": 1611661325,
            },
            {
                "player_id": 1629482,
                "team_key": "indiana-fever",
                "official_team_id": 1611661325,
            },
        ]
    }


class WNBALineupContextTests(unittest.TestCase):
    def test_result_set_maps_headers_to_rows(self):
        headers, rows = _result_set(
            _payload("Example", ["A", "B"], [[1, 2]]),
            "Example",
        )
        self.assertEqual(headers, ["A", "B"])
        self.assertEqual(rows, [{"A": 1, "B": 2}])

    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_lineups_normalize_members_stats_and_registry(self, mock_request):
        mock_request.return_value = (
            _payload("Lineups", LINEUP_HEADERS, [_lineup_row()]),
            "2026-08-26T05:05:00+00:00",
            False,
        )

        dataset = get_lineups_dataset(2026)

        self.assertEqual(dataset["lineup_count"], 1)
        lineup = dataset["lineups"][0]
        self.assertEqual(lineup["team_key"], "indiana-fever")
        self.assertEqual(lineup["member_count"], 5)
        self.assertEqual(lineup["members"][0]["player_id"], 1642286)
        self.assertEqual(lineup["members"][0]["player_name"], "Caitlin Clark")
        self.assertEqual(lineup["stats"]["minutes"], 210.5)
        self.assertTrue(dataset["verification"]["all_groups_match_requested_quantity"])

        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("GroupQuantity", "5"), params)
        self.assertIn(("MeasureType", "Base"), params)

    @patch("sports_api.wnba_lineup_context.get_current_players_dataset")
    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_lineups_team_filter_resolves_official_team_id(self, mock_request, mock_players):
        mock_players.return_value = _current_players_dataset()
        mock_request.return_value = (
            _payload("Lineups", LINEUP_HEADERS, [_lineup_row()]),
            "2026-08-26T05:05:00+00:00",
            False,
        )

        dataset = get_lineups_dataset(2026, team_key="indiana-fever")

        self.assertEqual(dataset["lineup_count"], 1)
        params = mock_request.call_args.args[1]
        self.assertIn(("TeamID", "1611661325"), params)

    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_lineups_player_filter_keeps_only_matching_groups(self, mock_request):
        other = _lineup_row()
        other[1] = "-111111-222222-333333-444444-555555-"
        other[2] = "A - B - C - D - E"
        mock_request.return_value = (
            _payload("Lineups", LINEUP_HEADERS, [_lineup_row(), other]),
            "2026-08-26T05:05:00+00:00",
            False,
        )

        dataset = get_lineups_dataset(2026, player_id=1642286)

        self.assertEqual(dataset["lineup_count"], 1)
        self.assertIn(1642286, dataset["lineups"][0]["player_ids"])

    def test_invalid_group_quantity_fails_before_network(self):
        with patch("sports_api.wnba_lineup_context._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "2 through 5"):
                get_lineups_dataset(2026, group_quantity=6)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_lineup_schema_fails_closed(self, mock_request):
        mock_request.return_value = (
            _payload("Lineups", ["TEAM_ID", "GP"], [[1611661325, 10]]),
            "2026-08-26T05:05:00+00:00",
            False,
        )
        with self.assertRaises(WNBALineupContextUpstreamError):
            get_lineups_dataset(2026)

    @patch("sports_api.wnba_lineup_context.get_current_players_dataset")
    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_on_off_joins_players_and_computes_raw_deltas(self, mock_request, mock_players):
        mock_players.return_value = _current_players_dataset()
        mock_request.return_value = (
            _multi_payload(
                [
                    ("OverallTeamPlayerOnOffSummary", OVERALL_HEADERS, [_overall_row()]),
                    ("PlayersOnCourtTeamPlayerOnOffSummary", ON_OFF_HEADERS, [_on_row()]),
                    ("PlayersOffCourtTeamPlayerOnOffSummary", ON_OFF_HEADERS, [_off_row()]),
                ]
            ),
            "2026-08-26T05:05:00+00:00",
            False,
        )

        dataset = get_team_on_off_dataset("indiana-fever", 2026)

        self.assertEqual(dataset["official_team_id"], 1611661325)
        self.assertEqual(dataset["player_count"], 1)
        player = dataset["players"][0]
        self.assertTrue(player["has_complete_pair"])
        self.assertEqual(player["deltas_on_minus_off"]["offensive_rating"], 8.0)
        self.assertEqual(player["deltas_on_minus_off"]["defensive_rating"], -4.0)
        self.assertEqual(player["deltas_on_minus_off"]["net_rating"], 12.0)

        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("TeamID", "1611661325"), params)

    @patch("sports_api.wnba_lineup_context.get_current_players_dataset")
    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_on_off_flags_incomplete_player_pairs(self, mock_request, mock_players):
        mock_players.return_value = _current_players_dataset()
        mock_request.return_value = (
            _multi_payload(
                [
                    ("OverallTeamPlayerOnOffSummary", OVERALL_HEADERS, [_overall_row()]),
                    ("PlayersOnCourtTeamPlayerOnOffSummary", ON_OFF_HEADERS, [_on_row()]),
                    ("PlayersOffCourtTeamPlayerOnOffSummary", ON_OFF_HEADERS, []),
                ]
            ),
            "2026-08-26T05:05:00+00:00",
            False,
        )

        dataset = get_team_on_off_dataset("indiana-fever", 2026)

        self.assertFalse(dataset["verification"]["all_players_have_on_off_pair"])
        self.assertEqual(dataset["verification"]["incomplete_player_ids"], [1642286])

    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_role_context_combines_starter_and_bench_splits(self, mock_request):
        mock_request.side_effect = [
            (
                _payload("LeagueDashPlayerStats", ROLE_HEADERS, [_role_row("Starters", 24, 34.0, 22.0)]),
                "2026-08-26T05:05:00+00:00",
                False,
            ),
            (
                _payload("LeagueDashPlayerStats", ROLE_HEADERS, [_role_row("Bench", 6, 25.0, 15.0)]),
                "2026-08-26T05:05:01+00:00",
                False,
            ),
        ]

        dataset = get_player_role_context_dataset(1642286, 2026)

        self.assertEqual(dataset["role_summary"]["starter_games"], 24)
        self.assertEqual(dataset["role_summary"]["bench_games"], 6)
        self.assertEqual(dataset["role_summary"]["starter_game_share"], 0.8)
        self.assertEqual(dataset["role_summary"]["primary_observed_role"], "starter")
        self.assertEqual(dataset["starter"]["team_key"], "indiana-fever")
        self.assertEqual(dataset["bench"]["stats"]["points"], 15.0)

        starter_params = mock_request.call_args_list[0].args[1]
        bench_params = mock_request.call_args_list[1].args[1]
        self.assertIn(("StarterBench", "Starters"), starter_params)
        self.assertIn(("StarterBench", "Bench"), bench_params)
        self.assertEqual(starter_params[0], ("LeagueID", "10"))

    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_role_context_allows_bench_only_player(self, mock_request):
        mock_request.side_effect = [
            (
                _payload("LeagueDashPlayerStats", ROLE_HEADERS, []),
                "2026-08-26T05:05:00+00:00",
                False,
            ),
            (
                _payload("LeagueDashPlayerStats", ROLE_HEADERS, [_role_row("Bench", 12, 18.0, 7.0)]),
                "2026-08-26T05:05:01+00:00",
                False,
            ),
        ]

        dataset = get_player_role_context_dataset(1642286, 2026)

        self.assertIsNone(dataset["starter"])
        self.assertEqual(dataset["role_summary"]["primary_observed_role"], "bench")

    @patch("sports_api.wnba_lineup_context._request_stats_json")
    def test_role_context_missing_player_raises_not_found(self, mock_request):
        mock_request.side_effect = [
            (_payload("LeagueDashPlayerStats", ROLE_HEADERS, []), "2026-08-26T05:05:00+00:00", False),
            (_payload("LeagueDashPlayerStats", ROLE_HEADERS, []), "2026-08-26T05:05:01+00:00", False),
        ]
        with self.assertRaises(WNBALineupContextNotFoundError):
            get_player_role_context_dataset(1642286, 2026)

    def test_invalid_player_id_fails_before_network(self):
        with patch("sports_api.wnba_lineup_context._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                get_player_role_context_dataset(0, 2026)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_lineup_context.get_current_players_dataset")
    def test_official_team_id_ambiguity_fails_closed(self, mock_players):
        mock_players.return_value = {
            "players": [
                {"team_key": "indiana-fever", "official_team_id": 1},
                {"team_key": "indiana-fever", "official_team_id": 2},
            ]
        }
        with self.assertRaisesRegex(WNBALineupContextUpstreamError, "ambiguous"):
            get_team_on_off_dataset("indiana-fever", 2026)


if __name__ == "__main__":
    unittest.main()
