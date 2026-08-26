import unittest
from unittest.mock import patch

from sports_api.wnba_team_history import (
    WNBATeamHistoryUpstreamError,
    _result_set,
    get_head_to_head_dataset,
    get_team_game_log_dataset,
    get_team_recent_form_dataset,
)


HEADERS = [
    "SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "GAME_ID",
    "GAME_DATE", "MATCHUP", "WL", "MIN", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB",
    "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS",
    "PLUS_MINUS", "VIDEO_AVAILABLE",
]


def payload(rows, headers=HEADERS):
    return {
        "resultSets": [
            {"name": "LeagueGameLog", "headers": headers, "rowSet": rows}
        ]
    }


def row(
    team_id,
    abbreviation,
    team_name,
    game_id,
    game_date,
    matchup,
    result,
    points,
    plus_minus,
    *,
    fgm=30,
    fga=70,
    fg3m=8,
    fg3a=24,
    ftm=14,
    fta=18,
    reb=35,
    ast=20,
    tov=12,
):
    return [
        "22026", team_id, abbreviation, team_name, game_id, game_date,
        matchup, result, 200.0, fgm, fga, fgm / fga, fg3m, fg3a,
        fg3m / fg3a, ftm, fta, ftm / fta, 8, reb - 8, reb, ast,
        7, 4, tov, 18, points, plus_minus, 1,
    ]


def league_rows():
    return [
        row(
            1611661325, "IND", "Indiana Fever", "1022600003", "AUG 20, 2026",
            "IND vs. CHI", "W", 88, 6, fgm=32, fga=68, fg3m=10, fg3a=25,
        ),
        row(
            1611661329, "CHI", "Chicago Sky", "1022600003", "AUG 20, 2026",
            "CHI @ IND", "L", 82, -6, fgm=29, fga=69, fg3m=8, fg3a=24,
        ),
        row(
            1611661325, "IND", "Indiana Fever", "1022600002", "AUG 18, 2026",
            "IND @ NYL", "L", 78, -7, fgm=27, fga=70, fg3m=7, fg3a=25,
        ),
        row(
            1611661313, "NYL", "New York Liberty", "1022600002", "AUG 18, 2026",
            "NYL vs. IND", "W", 85, 7, fgm=31, fga=67, fg3m=11, fg3a=27,
        ),
        row(
            1611661325, "IND", "Indiana Fever", "1022600001", "AUG 10, 2026",
            "IND vs. NYL", "W", 91, 4, fgm=33, fga=71, fg3m=9, fg3a=23,
        ),
        row(
            1611661313, "NYL", "New York Liberty", "1022600001", "AUG 10, 2026",
            "NYL @ IND", "L", 87, -4, fgm=32, fga=70, fg3m=10, fg3a=29,
        ),
    ]


class WNBATeamHistoryTests(unittest.TestCase):
    def test_result_set_maps_headers_to_rows(self):
        headers, rows = _result_set(
            payload([[1, 2]], headers=["A", "B"]),
            "LeagueGameLog",
        )
        self.assertEqual(headers, ["A", "B"])
        self.assertEqual(rows, [{"A": 1, "B": 2}])

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_team_game_log_normalizes_and_pairs_official_rows(self, mock_request):
        mock_request.return_value = (
            payload(league_rows()),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_team_game_log_dataset("indiana-fever", 2026)

        self.assertEqual(dataset["game_count"], 3)
        newest = dataset["games"][0]
        self.assertEqual(newest["game_id"], "1022600003")
        self.assertEqual(newest["location"], "home")
        self.assertEqual(newest["opponent_team_key"], "chicago-sky")
        self.assertEqual(newest["opponent_points"], 82.0)
        self.assertEqual(newest["point_margin_from_scores"], 6.0)
        self.assertTrue(newest["paired_opponent_row"])
        self.assertEqual(newest["opponent_stats"]["team_key"], "chicago-sky")
        self.assertTrue(dataset["verification"]["all_game_ids_have_two_team_rows"])

        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("PlayerOrTeam", "T"), params)
        self.assertIn(("Sorter", "DATE"), params)
        self.assertIn(("Direction", "DESC"), params)

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_last_n_and_location_filters_use_newest_first(self, mock_request):
        mock_request.return_value = (
            payload(league_rows()),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_team_game_log_dataset(
            "indiana-fever",
            2026,
            last_n_games=1,
            location="Home",
        )

        self.assertEqual(dataset["game_count"], 1)
        self.assertEqual(dataset["games"][0]["game_id"], "1022600003")
        self.assertEqual(dataset["games"][0]["location"], "home")

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_opponent_filter_returns_only_requested_matchup(self, mock_request):
        mock_request.return_value = (
            payload(league_rows()),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_team_game_log_dataset(
            "indiana-fever",
            2026,
            opponent_team_key="new-york-liberty",
        )

        self.assertEqual(dataset["game_count"], 2)
        self.assertTrue(
            all(
                game["opponent_team_key"] == "new-york-liberty"
                for game in dataset["games"]
            )
        )

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_recent_form_summary_has_record_streak_and_weighted_shooting(self, mock_request):
        mock_request.return_value = (
            payload(league_rows()),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_team_recent_form_dataset(
            "indiana-fever",
            2026,
            last_n_games=2,
        )

        self.assertEqual(dataset["summary"]["record"], {
            "wins": 1,
            "losses": 1,
            "win_percentage": 0.5,
        })
        self.assertEqual(dataset["summary"]["current_streak"]["label"], "W1")
        self.assertEqual(dataset["summary"]["averages"]["points_for"], 83.0)
        self.assertEqual(dataset["summary"]["averages"]["points_against"], 83.5)
        expected_fg = round((32 + 27) / (68 + 70), 4)
        self.assertEqual(
            dataset["summary"]["weighted_shooting"]["field_goal_percentage"],
            expected_fg,
        )

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_head_to_head_builds_record_and_meeting_history(self, mock_request):
        mock_request.return_value = (
            payload(league_rows()),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_head_to_head_dataset(
            "indiana-fever",
            "new-york-liberty",
            2026,
        )

        self.assertEqual(dataset["meeting_count"], 2)
        self.assertEqual(dataset["summary"]["record"]["wins"], 1)
        self.assertEqual(dataset["summary"]["record"]["losses"], 1)
        self.assertEqual(dataset["most_recent_meeting_date"], "2026-08-18")
        self.assertEqual(dataset["first_meeting_date"], "2026-08-10")
        self.assertTrue(
            dataset["verification"]["all_returned_rows_match_requested_opponent"]
        )
        self.assertTrue(
            dataset["verification"]["all_meetings_have_paired_opponent_row"]
        )

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_head_to_head_location_is_from_first_team_perspective(self, mock_request):
        mock_request.return_value = (
            payload(league_rows()),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_head_to_head_dataset(
            "indiana-fever",
            "new-york-liberty",
            2026,
            location="Home",
        )

        self.assertEqual(dataset["meeting_count"], 1)
        self.assertEqual(dataset["meetings"][0]["game_id"], "1022600001")
        self.assertEqual(dataset["meetings"][0]["result"], "W")

    def test_same_team_head_to_head_fails_before_network(self):
        with patch("sports_api.wnba_team_history._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "must be different"):
                get_head_to_head_dataset(
                    "indiana-fever",
                    "indiana-fever",
                    2026,
                )
            mock_request.assert_not_called()

    def test_unknown_team_fails_before_network(self):
        with patch("sports_api.wnba_team_history._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "was not found"):
                get_team_game_log_dataset("not-a-team", 2026)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_missing_required_schema_fails_closed(self, mock_request):
        mock_request.return_value = (
            payload([[1611661325, "IND"]], headers=["TEAM_ID", "TEAM_ABBREVIATION"]),
            "2026-08-26T05:33:00+00:00",
            False,
        )
        with self.assertRaises(WNBATeamHistoryUpstreamError):
            get_team_game_log_dataset("indiana-fever", 2026)

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_duplicate_team_game_row_fails_closed(self, mock_request):
        rows = league_rows()
        rows.append(list(rows[0]))
        mock_request.return_value = (
            payload(rows),
            "2026-08-26T05:33:00+00:00",
            False,
        )
        with self.assertRaisesRegex(WNBATeamHistoryUpstreamError, "duplicate team/game"):
            get_team_game_log_dataset("indiana-fever", 2026)

    @patch("sports_api.wnba_team_history._request_stats_json")
    def test_unpaired_game_is_flagged_without_inventing_opponent_score(self, mock_request):
        rows = [league_rows()[0]]
        mock_request.return_value = (
            payload(rows),
            "2026-08-26T05:33:00+00:00",
            False,
        )

        dataset = get_team_game_log_dataset("indiana-fever", 2026)

        self.assertFalse(
            dataset["verification"]["all_game_ids_have_two_team_rows"]
        )
        self.assertEqual(
            dataset["verification"]["invalid_pair_game_ids"],
            ["1022600003"],
        )
        self.assertIsNone(dataset["games"][0]["opponent_points"])
        self.assertFalse(dataset["games"][0]["paired_opponent_row"])


if __name__ == "__main__":
    unittest.main()
