import unittest
from unittest.mock import patch

from sports_api import wnba_clutch_context as m


TEAMS = [
    {
        "team_key": "seattle-storm",
        "slug": "seattle-storm",
        "abbreviation": "SEA",
        "nickname": "Storm",
        "full_name": "Seattle Storm",
        "conference": "Western",
    },
    {
        "team_key": "toronto-tempo",
        "slug": "toronto-tempo",
        "abbreviation": "TOR",
        "nickname": "Tempo",
        "full_name": "Toronto Tempo",
        "conference": "Eastern",
    },
    {
        "team_key": "portland-fire",
        "slug": "portland-fire",
        "abbreviation": "POR",
        "nickname": "Fire",
        "full_name": "Portland Fire",
        "conference": "Western",
    },
]

PLAYER_HEADERS = [
    "GROUP_SET", "PLAYER_ID", "PLAYER_NAME", "NICKNAME", "TEAM_ID",
    "TEAM_ABBREVIATION", "AGE", "GP", "W", "L", "W_PCT", "MIN",
    "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM",
    "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "TOV", "STL",
    "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS", "WNBA_FANTASY_PTS",
]

TEAM_HEADERS = [
    "TEAM_ID", "TEAM_NAME", "GP", "W", "L", "W_PCT", "MIN", "FGM",
    "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "BLKA", "PF",
    "PFD", "PTS", "PLUS_MINUS",
]


def player_row(player_id=99, team_id=1, abbr="SEA", name="Test Player"):
    return [
        "Clutch", player_id, name, "Test", team_id, abbr, 27, 12, 7, 5,
        .583, 42.0, 15, 34, .441, 5, 14, .357, 10, 12, .833, 3, 8, 11,
        9, 5, 2, 1, 1, 6, 8, 45, 4.0, 88.2,
    ]


def team_row(team_id=1, name="Seattle Storm"):
    return [
        team_id, name, 13, 8, 5, .615, 65.0, 25, 55, .455, 8, 21, .381,
        15, 18, .833, 6, 20, 26, 14, 7, 4, 2, 1, 12, 15, 73, 6.0,
    ]


def player_payload(rows=None, headers=None):
    return {
        "resultSets": [
            {
                "name": "LeagueDashPlayerClutch",
                "headers": headers or PLAYER_HEADERS,
                "rowSet": rows if rows is not None else [player_row()],
            }
        ]
    }


def team_payload(rows=None, headers=None):
    return {
        "resultSets": [
            {
                "name": "LeagueDashTeamClutch",
                "headers": headers or TEAM_HEADERS,
                "rowSet": rows if rows is not None else [team_row()],
            }
        ]
    }


class WNBAClutchContextTests(unittest.TestCase):
    def setUp(self):
        teams = patch("sports_api.wnba_clutch_context.get_wnba_teams", return_value=TEAMS)
        request = patch("sports_api.wnba_clutch_context._request_stats_json")
        self.mock_teams = teams.start()
        self.mock_request = request.start()
        self.addCleanup(teams.stop)
        self.addCleanup(request.stop)
        self.mock_request.return_value = (player_payload(), "x", False)

    def test_player_clutch_normalizes_standard_sample(self):
        result = m.get_player_clutch_dataset(2026)
        self.assertEqual(result["player_count"], 1)
        row = result["players"][0]
        self.assertEqual(row["player_id"], 99)
        self.assertEqual(row["team_key"], "seattle-storm")
        self.assertEqual(row["stats"]["points"], 45.0)
        self.assertEqual(row["games_played_in_sample"], 12)
        self.assertTrue(result["definition"]["standard_clutch_default"])

    def test_team_clutch_normalizes(self):
        self.mock_request.return_value = (team_payload(), "x", False)
        result = m.get_team_clutch_dataset(2026)
        self.assertEqual(result["team_count"], 1)
        self.assertEqual(result["teams"][0]["team_key"], "seattle-storm")
        self.assertEqual(result["teams"][0]["stats"]["plus_minus"], 6.0)

    def test_league_id_is_first_and_controls_forward(self):
        m.get_player_clutch_dataset(
            2026,
            clutch_time="Last 1 Minute",
            point_diff=3,
            ahead_behind="Behind or Tied",
            last_n_games=10,
            per_mode="PerGame",
            period=4,
            location="Road",
            outcome="L",
        )
        endpoint, params = self.mock_request.call_args.args
        self.assertEqual(endpoint, m.PLAYER_CLUTCH_ENDPOINT)
        self.assertEqual(params[0], ("LeagueID", "10"))
        values = dict(params)
        self.assertEqual(values["ClutchTime"], "Last 1 Minute")
        self.assertEqual(values["PointDiff"], "3")
        self.assertEqual(values["AheadBehind"], "Behind or Tied")
        self.assertEqual(values["LastNGames"], "10")
        self.assertEqual(values["Period"], "4")
        self.assertEqual(values["Location"], "Road")
        self.assertEqual(values["Outcome"], "L")

    def test_player_filter_post_fetch(self):
        self.mock_request.return_value = (
            player_payload(rows=[player_row(99), player_row(100, name="Other Player")]),
            "x",
            False,
        )
        result = m.get_player_clutch_dataset(2026, player_id=100)
        self.assertEqual(result["player_count"], 1)
        self.assertEqual(result["players"][0]["player_id"], 100)

    def test_team_filter_post_fetch(self):
        self.mock_request.return_value = (
            team_payload(rows=[team_row(1, "Seattle Storm"), team_row(2, "Toronto Tempo")]),
            "x",
            False,
        )
        result = m.get_team_clutch_dataset(2026, team_key="toronto-tempo")
        self.assertEqual(result["team_count"], 1)
        self.assertEqual(result["teams"][0]["team_key"], "toronto-tempo")

    def test_portland_pdx_alias_maps(self):
        self.mock_request.return_value = (
            player_payload(rows=[player_row(88, team_id=3, abbr="PDX", name="Portland Player")]),
            "x",
            False,
        )
        result = m.get_player_clutch_dataset(2026)
        self.assertEqual(result["players"][0]["team_key"], "portland-fire")

    def test_empty_valid_player_dataset_is_valid(self):
        self.mock_request.return_value = (player_payload(rows=[]), "x", False)
        result = m.get_player_clutch_dataset(2026)
        self.assertEqual(result["player_count"], 0)
        self.assertTrue(result["verification"]["required_schema_verified"])

    def test_malformed_schema_fails_closed(self):
        bad_headers = [header for header in PLAYER_HEADERS if header != "PTS"]
        bad_row = player_row()[:-3] + player_row()[-2:]
        self.mock_request.return_value = (
            player_payload(rows=[bad_row], headers=bad_headers), "x", False
        )
        with self.assertRaisesRegex(m.WNBAClutchUpstreamError, "missing required fields"):
            m.get_player_clutch_dataset(2026)

    def test_duplicate_player_ids_are_reported(self):
        self.mock_request.return_value = (
            player_payload(rows=[player_row(99), player_row(99)]), "x", False
        )
        result = m.get_player_clutch_dataset(2026)
        self.assertFalse(result["verification"]["player_ids_unique"])
        self.assertEqual(result["verification"]["duplicate_player_ids"], [99])

    def test_duplicate_team_ids_are_reported(self):
        self.mock_request.return_value = (
            team_payload(rows=[team_row(1), team_row(1)]), "x", False
        )
        result = m.get_team_clutch_dataset(2026)
        self.assertFalse(result["verification"]["official_team_ids_unique"])
        self.assertEqual(result["verification"]["duplicate_official_team_ids"], [1])

    def test_invalid_clutch_time_fails_before_network(self):
        with self.assertRaisesRegex(ValueError, "clutch_time"):
            m.get_player_clutch_dataset(2026, clutch_time="Last 6 Minutes")
        self.mock_request.assert_not_called()

    def test_invalid_point_diff_fails_before_network(self):
        with self.assertRaisesRegex(ValueError, "1 through 20"):
            m.get_player_clutch_dataset(2026, point_diff=0)
        self.mock_request.assert_not_called()

    def test_invalid_period_fails_before_network(self):
        with self.assertRaisesRegex(ValueError, "0 through 14"):
            m.get_team_clutch_dataset(2026, period=15)
        self.mock_request.assert_not_called()

    def test_invalid_player_id_fails_before_network(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_clutch_dataset(2026, player_id=0)
        self.mock_request.assert_not_called()

    def test_player_context_empty_raises_not_found(self):
        self.mock_request.return_value = (player_payload(rows=[]), "x", False)
        with self.assertRaises(m.WNBAClutchNotFoundError):
            m.get_player_clutch_context(99, 2026)

    def test_team_context_empty_raises_not_found(self):
        self.mock_request.return_value = (team_payload(rows=[]), "x", False)
        with self.assertRaises(m.WNBAClutchNotFoundError):
            m.get_team_clutch_context("seattle-storm", 2026)

    def test_sample_guardrails_are_explicit(self):
        result = m.get_player_clutch_dataset(2026)
        self.assertTrue(
            result["definition"]["sample_is_game_situation_subset_not_full_game_performance"]
        )
        self.assertTrue(result["verification"]["clutch_sample_is_descriptive_not_predictive"])
        self.assertTrue(result["verification"]["no_clutch_grade_created"])
        self.assertTrue(result["verification"]["no_betting_probability_created"])


if __name__ == "__main__":
    unittest.main()
