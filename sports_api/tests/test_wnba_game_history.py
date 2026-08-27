import unittest
from unittest.mock import patch

from sports_api.wnba_game_history import (
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    _minutes_to_float,
    get_game_box_score_dataset,
    get_player_game_log_dataset,
)


def _traditional_stats(
    *,
    minutes="PT35M30.00S",
    points=24,
    rebounds=7,
    assists=9,
    plus_minus=6,
):
    return {
        "minutes": minutes,
        "fieldGoalsMade": 8,
        "fieldGoalsAttempted": 16,
        "fieldGoalsPercentage": 0.5,
        "threePointersMade": 3,
        "threePointersAttempted": 7,
        "threePointersPercentage": 0.4286,
        "freeThrowsMade": 5,
        "freeThrowsAttempted": 6,
        "freeThrowsPercentage": 0.8333,
        "reboundsOffensive": 1,
        "reboundsDefensive": rebounds - 1,
        "reboundsTotal": rebounds,
        "assists": assists,
        "steals": 2,
        "blocks": 1,
        "turnovers": 3,
        "foulsPersonal": 2,
        "points": points,
        "plusMinusPoints": plus_minus,
    }


def _player(
    player_id,
    first_name,
    last_name,
    *,
    position="G",
    jersey="22",
    points=24,
    rebounds=7,
    assists=9,
):
    return {
        "personId": player_id,
        "firstName": first_name,
        "familyName": last_name,
        "nameI": f"{first_name[:1]}. {last_name}",
        "playerSlug": f"{first_name}-{last_name}".lower(),
        "position": position,
        "comment": "",
        "jerseyNum": jersey,
        "statistics": _traditional_stats(
            points=points,
            rebounds=rebounds,
            assists=assists,
        ),
    }


def _team(team_id, city, name, tricode, slug, players):
    return {
        "teamId": team_id,
        "teamCity": city,
        "teamName": name,
        "teamTricode": tricode,
        "teamSlug": slug,
        "statistics": _traditional_stats(
            minutes="PT200M00.00S",
            points=88,
            rebounds=35,
            assists=21,
        ),
        "starters": _traditional_stats(
            minutes="PT150M00.00S",
            points=68,
            rebounds=25,
            assists=17,
        ),
        "bench": _traditional_stats(
            minutes="PT50M00.00S",
            points=20,
            rebounds=10,
            assists=4,
        ),
        "players": players,
    }


def _box_payload(game_id="1022600300"):
    return {
        "boxScoreTraditional": {
            "gameId": game_id,
            "homeTeamId": 1611661313,
            "awayTeamId": 1611661325,
            "homeTeam": _team(
                1611661313,
                "New York",
                "Liberty",
                "NYL",
                "liberty",
                [
                    _player(
                        1629477,
                        "Sabrina",
                        "Ionescu",
                        points=22,
                        rebounds=5,
                        assists=8,
                    )
                ],
            ),
            "awayTeam": _team(
                1611661325,
                "Indiana",
                "Fever",
                "IND",
                "fever",
                [
                    _player(
                        1642286,
                        "Caitlin",
                        "Clark",
                        points=24,
                        rebounds=7,
                        assists=9,
                    )
                ],
            ),
        }
    }


def _game_log_payload(rows):
    headers = [
        "SEASON_ID",
        "Player_ID",
        "Game_ID",
        "GAME_DATE",
        "MATCHUP",
        "WL",
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
        "STL",
        "BLK",
        "TOV",
        "PF",
        "PTS",
        "PLUS_MINUS",
        "VIDEO_AVAILABLE",
    ]
    return {
        "resultSets": [
            {
                "name": "PlayerGameLog",
                "headers": headers,
                "rowSet": rows,
            }
        ]
    }


def _game_log_row(
    game_id,
    matchup,
    *,
    player_id=1642286,
    game_date="AUG 24, 2026",
    points=24,
):
    return [
        "22026",
        player_id,
        game_id,
        game_date,
        matchup,
        "W",
        35.5,
        8,
        16,
        0.5,
        3,
        7,
        0.4286,
        5,
        6,
        0.8333,
        1,
        6,
        7,
        9,
        2,
        1,
        3,
        2,
        points,
        6,
        1,
    ]


class WNBAGameHistoryTests(unittest.TestCase):
    def test_minutes_parser_handles_v3_iso_and_clock_formats(self):
        self.assertAlmostEqual(_minutes_to_float("PT35M30.00S"), 35.5)
        self.assertAlmostEqual(_minutes_to_float("12:30"), 12.5)
        self.assertEqual(_minutes_to_float("40"), 40.0)

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_box_score_normalizes_teams_players_and_traditional_stats(self, mock_request):
        mock_request.return_value = (
            _box_payload(),
            "2026-08-26T04:40:00+00:00",
            False,
            30,
        )

        dataset = get_game_box_score_dataset("1022600300", 2026)

        self.assertEqual(dataset["game_id"], "1022600300")
        self.assertEqual(dataset["home"]["team_key"], "new-york-liberty")
        self.assertEqual(dataset["away"]["team_key"], "indiana-fever")
        self.assertEqual(dataset["player_count"], 2)

        player = dataset["away"]["players"][0]
        self.assertEqual(player["player_id"], 1642286)
        self.assertEqual(player["full_name"], "Caitlin Clark")
        self.assertTrue(player["is_starter"])
        self.assertTrue(player["appeared"])
        self.assertEqual(player["stats"]["points"], 24)
        self.assertEqual(player["stats"]["rebounds"], 7)
        self.assertEqual(player["stats"]["assists"], 9)
        self.assertAlmostEqual(player["stats"]["minutes"], 35.5)

        params = mock_request.call_args.args[1]
        self.assertIn(("GameID", "1022600300"), params)

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_box_score_rejects_mismatched_game_id(self, mock_request):
        mock_request.return_value = (
            _box_payload("1022600999"),
            "2026-08-26T04:40:00+00:00",
            False,
            30,
        )

        with self.assertRaises(WNBAHistoryUpstreamError):
            get_game_box_score_dataset("1022600300", 2026)

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_box_score_rejects_unmapped_team_identity(self, mock_request):
        payload = _box_payload()
        payload["boxScoreTraditional"]["homeTeam"]["teamId"] = 9999999999
        payload["boxScoreTraditional"]["homeTeam"]["teamCity"] = "Unknown"
        payload["boxScoreTraditional"]["homeTeam"]["teamName"] = "Team"
        payload["boxScoreTraditional"]["homeTeam"]["teamTricode"] = "XXX"
        payload["boxScoreTraditional"]["homeTeam"]["teamSlug"] = "unknown-team"
        mock_request.return_value = (
            payload,
            "2026-08-26T04:40:00+00:00",
            False,
            30,
        )

        with self.assertRaises(WNBAHistoryUpstreamError):
            get_game_box_score_dataset("1022600300", 2026)

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_missing_box_score_is_not_found(self, mock_request):
        mock_request.return_value = (
            {},
            "2026-08-26T04:40:00+00:00",
            False,
            30,
        )

        with self.assertRaises(WNBAHistoryNotFoundError):
            get_game_box_score_dataset("1022600300", 2026)

    def test_invalid_game_id_fails_before_network(self):
        with patch("sports_api.wnba_game_history._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                get_game_box_score_dataset("bad-id", 2026)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_player_game_log_maps_home_and_away_matchups(self, mock_request):
        payload = _game_log_payload(
            [
                _game_log_row("1022600300", "IND vs. NYL"),
                _game_log_row(
                    "1022600291",
                    "IND @ CHI",
                    game_date="AUG 22, 2026",
                    points=19,
                ),
            ]
        )
        mock_request.return_value = (
            payload,
            "2026-08-26T04:40:00+00:00",
            False,
            120,
        )

        dataset = get_player_game_log_dataset(
            1642286,
            2026,
            season_type="regular season",
        )

        self.assertEqual(dataset["season_type"], "Regular Season")
        self.assertEqual(dataset["game_count"], 2)

        home_game = dataset["games"][0]
        self.assertEqual(home_game["game_date"], "2026-08-24")
        self.assertEqual(home_game["matchup"]["location"], "home")
        self.assertEqual(home_game["matchup"]["team_key"], "indiana-fever")
        self.assertEqual(home_game["matchup"]["opponent_team_key"], "new-york-liberty")

        away_game = dataset["games"][1]
        self.assertEqual(away_game["matchup"]["location"], "away")
        self.assertEqual(away_game["matchup"]["opponent_team_key"], "chicago-sky")

        self.assertTrue(dataset["verification"]["all_game_ids_valid"])
        self.assertTrue(dataset["verification"]["all_game_ids_unique"])
        self.assertTrue(
            dataset["verification"]["all_matchup_teams_mapped_to_registry"]
        )

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_empty_player_game_log_is_valid_empty_dataset(self, mock_request):
        mock_request.return_value = (
            _game_log_payload([]),
            "2026-08-26T04:40:00+00:00",
            False,
            120,
        )

        dataset = get_player_game_log_dataset(1642286, 2026)

        self.assertEqual(dataset["game_count"], 0)
        self.assertEqual(dataset["games"], [])
        self.assertTrue(dataset["verification"]["all_game_ids_valid"])
        self.assertTrue(dataset["verification"]["all_game_ids_unique"])

    @patch("sports_api.wnba_game_history._request_stats_json")
    def test_player_game_log_rejects_wrong_player_id(self, mock_request):
        mock_request.return_value = (
            _game_log_payload(
                [
                    _game_log_row(
                        "1022600300",
                        "IND vs. NYL",
                        player_id=9999999,
                    )
                ]
            ),
            "2026-08-26T04:40:00+00:00",
            False,
            120,
        )

        with self.assertRaises(WNBAHistoryUpstreamError):
            get_player_game_log_dataset(1642286, 2026)

    def test_invalid_season_type_fails_before_network(self):
        with patch("sports_api.wnba_game_history._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "Unsupported WNBA season_type"):
                get_player_game_log_dataset(
                    1642286,
                    2026,
                    season_type="Summer League",
                )
            mock_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
