import unittest
from unittest.mock import patch

from sports_api.wnba_tracking import (
    WNBATrackingMeasureUnavailableError,
    WNBATrackingNotFoundError,
    WNBATrackingUpstreamError,
    _result_set,
    get_player_opportunity_context_dataset,
    get_player_tracking_dataset,
)


PASSING_HEADERS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE",
    "GP", "W", "L", "MIN", "PASSES_MADE", "PASSES_RECEIVED", "AST",
    "FT_AST", "SECONDARY_AST", "POTENTIAL_AST", "AST_PTS_CREATED",
    "AST_PCT", "AST_ADJ", "AST_TO_PASS_PCT", "AST_TO_PASS_PCT_ADJ",
    "BAD_PASS_TURNOVER", "BAD_PASS_TO_TURNOVER_RATIO",
]

REBOUNDING_HEADERS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE",
    "GP", "W", "L", "MIN", "OREB", "OREB_CONTEST", "OREB_UNCONTEST",
    "OREB_CHANCES", "OREB_CHANCE_PCT", "OREB_CHANCE_DEFER",
    "OREB_CHANCE_PCT_ADJ", "DREB", "DREB_CONTEST", "DREB_UNCONTEST",
    "DREB_CHANCES", "DREB_CHANCE_PCT", "DREB_CHANCE_DEFER",
    "DREB_CHANCE_PCT_ADJ", "REB", "REB_CONTEST", "REB_UNCONTEST",
    "REB_CHANCES", "REB_CHANCE_PCT", "REB_CHANCE_DEFER",
    "REB_CHANCE_PCT_ADJ", "AVG_REB_DIST",
]

POSSESSIONS_HEADERS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE",
    "GP", "W", "L", "MIN", "TOUCHES", "FRONT_CT_TOUCHES", "TIME_OF_POSS",
    "AVG_SEC_PER_TOUCH", "AVG_DRIB_PER_TOUCH", "PTS_PER_TOUCH",
    "ELBOW_TOUCHES", "POST_TOUCHES", "PAINT_TOUCHES",
    "PTS_PER_ELBOW_TOUCH", "PTS_PER_POST_TOUCH", "PTS_PER_PAINT_TOUCH",
]


def _payload(headers, rows):
    return {
        "resultSets": [
            {"name": "LeagueDashPtStats", "headers": headers, "rowSet": rows}
        ]
    }


def _passing_row(
    player_id=1642286,
    name="Caitlin Clark",
    team_id=1611661325,
    abbreviation="IND",
):
    return [
        player_id, name, team_id, abbreviation, 24.0,
        30, 20, 10, 34.0,
        55.0, 60.0, 8.0, 0.8, 0.5, 15.0, 21.0,
        0.42, 9.1, 0.145, 0.165, 3.0, 0.31,
    ]


def _rebounding_row(
    player_id=1630163,
    name="Aliyah Boston",
    team_id=1611661325,
    abbreviation="IND",
):
    return [
        player_id, name, team_id, abbreviation, 24.0,
        30, 20, 10, 31.0,
        2.0, 1.1, 0.9, 4.0, 0.50, 0.4, 0.56,
        6.0, 2.5, 3.5, 10.0, 0.60, 1.0, 0.67,
        8.0, 3.6, 4.4, 14.0, 0.571, 1.4, 0.635, 5.2,
    ]


def _possessions_row(
    player_id=1642286,
    name="Caitlin Clark",
    team_id=1611661325,
    abbreviation="IND",
):
    return [
        player_id, name, team_id, abbreviation, 24.0,
        30, 20, 10, 34.0,
        78.0, 52.0, 7.8, 6.0, 3.4, 0.27,
        4.0, 1.0, 5.0, 0.5, 0.8, 1.1,
    ]


class WNBATrackingTests(unittest.TestCase):
    def test_result_set_maps_headers_to_rows(self):
        headers, rows = _result_set(
            _payload(["A", "B"], [[1, 2]]),
            "LeagueDashPtStats",
        )
        self.assertEqual(headers, ["A", "B"])
        self.assertEqual(rows, [{"A": 1, "B": 2}])

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_passing_normalizes_potential_assists_and_rates(self, mock_request):
        mock_request.return_value = (
            _payload(PASSING_HEADERS, [_passing_row()]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        dataset = get_player_tracking_dataset(2026, measure="Passing")

        self.assertEqual(dataset["player_count"], 1)
        player = dataset["players"][0]
        self.assertEqual(player["team_key"], "indiana-fever")
        self.assertEqual(player["passing"]["potential_assists"], 15.0)
        self.assertEqual(player["passing"]["passes_made"], 55.0)
        self.assertAlmostEqual(
            player["derived_observed"]["assist_conversion_from_potential"],
            8.0 / 15.0,
        )
        self.assertTrue(dataset["field_availability"]["potential_assists"])

        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("PlayerOrTeam", "Player"), params)
        self.assertIn(("PtMeasureType", "Passing"), params)

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_rebounding_normalizes_rebound_chances(self, mock_request):
        mock_request.return_value = (
            _payload(REBOUNDING_HEADERS, [_rebounding_row()]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        dataset = get_player_tracking_dataset(2026, measure="Rebounding")
        player = dataset["players"][0]

        self.assertEqual(player["rebounding"]["rebound_chances"], 14.0)
        self.assertEqual(player["rebounding"]["average_rebound_distance_feet"], 5.2)
        self.assertAlmostEqual(
            player["derived_observed"]["rebounds_per_chance"],
            8.0 / 14.0,
        )
        self.assertTrue(dataset["field_availability"]["rebound_chances"])

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_possessions_normalizes_touches_and_possession_time(self, mock_request):
        mock_request.return_value = (
            _payload(POSSESSIONS_HEADERS, [_possessions_row()]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        dataset = get_player_tracking_dataset(2026, measure="Possessions")
        player = dataset["players"][0]

        self.assertEqual(player["possessions"]["touches"], 78.0)
        self.assertEqual(player["possessions"]["time_of_possession_minutes"], 7.8)
        self.assertEqual(player["possessions"]["average_dribbles_per_touch"], 3.4)
        self.assertAlmostEqual(
            player["derived_observed"]["touches_per_minute"],
            78.0 / 34.0,
        )

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_last_n_team_and_player_filters(self, mock_request):
        other = _passing_row(1629477, "Sabrina Ionescu", 1611661313, "NYL")
        mock_request.return_value = (
            _payload(PASSING_HEADERS, [_passing_row(), other]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        dataset = get_player_tracking_dataset(
            2026,
            measure="Passing",
            last_n_games=5,
            team_key="indiana-fever",
            player_id=1642286,
        )

        self.assertEqual(dataset["window_scope"], "last_5_games")
        self.assertEqual(dataset["player_count"], 1)
        self.assertEqual(dataset["players"][0]["player_id"], 1642286)
        self.assertIn(("LastNGames", "5"), mock_request.call_args.args[1])

    def test_invalid_measure_fails_before_network(self):
        with patch("sports_api.wnba_tracking._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "tracking_measure"):
                get_player_tracking_dataset(2026, measure="Drives")
            mock_request.assert_not_called()

    def test_invalid_player_id_fails_before_network(self):
        with patch("sports_api.wnba_tracking._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                get_player_tracking_dataset(2026, measure="Passing", player_id=0)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_wrong_measure_schema_fails_closed(self, mock_request):
        speed_headers = [
            "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
            "GP", "MIN", "DIST_MILES", "AVG_SPEED",
        ]
        mock_request.return_value = (
            _payload(speed_headers, [[1642286, "Caitlin Clark", 1611661325, "IND", 30, 34.0, 2.1, 4.2]]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        with self.assertRaises(WNBATrackingMeasureUnavailableError):
            get_player_tracking_dataset(2026, measure="Passing")

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_duplicate_player_ids_are_reported(self, mock_request):
        mock_request.return_value = (
            _payload(PASSING_HEADERS, [_passing_row(), _passing_row()]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        dataset = get_player_tracking_dataset(2026, measure="Passing")
        self.assertFalse(dataset["verification"]["player_ids_unique"])
        self.assertEqual(dataset["verification"]["duplicate_player_ids"], [1642286])

    @patch("sports_api.wnba_tracking._request_stats_json")
    def test_unmapped_team_is_preserved_and_flagged(self, mock_request):
        mock_request.return_value = (
            _payload(PASSING_HEADERS, [_passing_row(team_id=0, abbreviation="TOT")]),
            "2026-08-26T05:15:00+00:00",
            False,
        )

        dataset = get_player_tracking_dataset(2026, measure="Passing")
        self.assertIsNone(dataset["players"][0]["team_key"])
        self.assertEqual(dataset["verification"]["unmapped_team_count"], 1)

    @patch("sports_api.wnba_tracking.get_player_tracking_dataset")
    def test_opportunity_context_combines_three_measures(self, mock_dataset):
        def side_effect(season, **kwargs):
            measure = kwargs["measure"]
            row_by_measure = {
                "Passing": {
                    "player_id": 1642286,
                    "player_name": "Caitlin Clark",
                    "team_key": "indiana-fever",
                    "team_full_name": "Indiana Fever",
                    "passing": {"potential_assists": 15.0},
                },
                "Rebounding": {
                    "player_id": 1642286,
                    "player_name": "Caitlin Clark",
                    "team_key": "indiana-fever",
                    "team_full_name": "Indiana Fever",
                    "rebounding": {"rebound_chances": 7.0},
                },
                "Possessions": {
                    "player_id": 1642286,
                    "player_name": "Caitlin Clark",
                    "team_key": "indiana-fever",
                    "team_full_name": "Indiana Fever",
                    "possessions": {"touches": 78.0},
                },
            }
            return {
                "retrieved_at_utc": "2026-08-26T05:15:00+00:00",
                "cache_hit": False,
                "field_availability": {},
                "players": [row_by_measure[measure]],
            }

        mock_dataset.side_effect = side_effect
        dataset = get_player_opportunity_context_dataset(1642286, 2026)

        self.assertTrue(dataset["availability"]["passing"])
        self.assertTrue(dataset["availability"]["rebounding"])
        self.assertTrue(dataset["availability"]["possessions"])
        self.assertEqual(dataset["passing"]["passing"]["potential_assists"], 15.0)
        self.assertEqual(dataset["rebounding"]["rebounding"]["rebound_chances"], 7.0)
        self.assertEqual(dataset["possessions"]["possessions"]["touches"], 78.0)
        self.assertTrue(dataset["verification"]["all_three_measures_available"])

    @patch("sports_api.wnba_tracking.get_player_tracking_dataset")
    def test_opportunity_context_marks_measure_schema_unavailable(self, mock_dataset):
        def side_effect(season, **kwargs):
            measure = kwargs["measure"]
            if measure == "Possessions":
                raise WNBATrackingMeasureUnavailableError("Possessions unavailable")
            row = {
                "player_id": 1642286,
                "player_name": "Caitlin Clark",
                "team_key": "indiana-fever",
                "team_full_name": "Indiana Fever",
            }
            return {
                "retrieved_at_utc": "2026-08-26T05:15:00+00:00",
                "cache_hit": False,
                "field_availability": {},
                "players": [row],
            }

        mock_dataset.side_effect = side_effect
        dataset = get_player_opportunity_context_dataset(1642286, 2026)

        self.assertFalse(dataset["availability"]["possessions"])
        self.assertIn("Possessions", dataset["availability"]["unavailable_measures"])
        self.assertEqual(dataset["verification"]["available_measure_count"], 2)
        self.assertFalse(dataset["verification"]["all_three_measures_available"])

    @patch("sports_api.wnba_tracking.get_player_tracking_dataset")
    def test_opportunity_context_missing_player_raises_not_found(self, mock_dataset):
        mock_dataset.return_value = {
            "retrieved_at_utc": "2026-08-26T05:15:00+00:00",
            "cache_hit": False,
            "field_availability": {},
            "players": [],
        }
        with self.assertRaises(WNBATrackingNotFoundError):
            get_player_opportunity_context_dataset(1642286, 2026)

    @patch("sports_api.wnba_tracking.get_player_tracking_dataset")
    def test_opportunity_context_identity_disagreement_fails_closed(self, mock_dataset):
        def side_effect(season, **kwargs):
            measure = kwargs["measure"]
            team_key = "new-york-liberty" if measure == "Rebounding" else "indiana-fever"
            return {
                "retrieved_at_utc": "2026-08-26T05:15:00+00:00",
                "cache_hit": False,
                "field_availability": {},
                "players": [{
                    "player_id": 1642286,
                    "player_name": "Caitlin Clark",
                    "team_key": team_key,
                    "team_full_name": "Team",
                }],
            }

        mock_dataset.side_effect = side_effect
        with self.assertRaisesRegex(WNBATrackingUpstreamError, "disagree"):
            get_player_opportunity_context_dataset(1642286, 2026)


if __name__ == "__main__":
    unittest.main()
