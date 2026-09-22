import unittest
from unittest.mock import patch

from sports_api.wnba_shot_context import (
    WNBAShotContextUpstreamError,
    _flatten_shot_location_headers,
    get_opponent_defense_by_shot_zone_dataset,
    get_player_shot_chart_dataset,
    get_team_shot_zones_dataset,
)

SHOT_HEADERS = [
    "GRID_TYPE", "GAME_ID", "GAME_EVENT_ID", "PLAYER_ID", "PLAYER_NAME",
    "TEAM_ID", "TEAM_NAME", "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING",
    "EVENT_TYPE", "ACTION_TYPE", "SHOT_TYPE", "SHOT_ZONE_BASIC",
    "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE", "SHOT_DISTANCE", "LOC_X", "LOC_Y",
    "SHOT_ATTEMPTED_FLAG", "SHOT_MADE_FLAG", "GAME_DATE", "HTM", "VTM",
]
LEAGUE_HEADERS = [
    "GRID_TYPE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE",
    "FGA", "FGM", "FG_PCT",
]


def shot_row(event_id, zone, made, *, player_id=1642286, team_name="Indiana Fever", shot_type="2PT Field Goal"):
    return [
        "Shot Chart Detail", "1022600200", event_id, player_id, "Test Player",
        1611661325, team_name, 1, 8, 30, "Made Shot" if made else "Missed Shot",
        "Jump Shot", shot_type, zone, "Center(C)", "Less Than 8 ft.", 5,
        10, 50, 1, 1 if made else 0, "20260820", "IND", "NYL",
    ]


def shot_payload(rows):
    return {
        "resultSets": [
            {"name": "Shot_Chart_Detail", "headers": SHOT_HEADERS, "rowSet": rows},
            {
                "name": "LeagueAverages",
                "headers": LEAGUE_HEADERS,
                "rowSet": [
                    ["League Averages", "Restricted Area", "Center(C)", "Less Than 8 ft.", 100, 65, 0.65],
                    ["League Averages", "Left Corner 3", "Left Side(L)", "24+ ft.", 40, 14, 0.35],
                    ["League Averages", "Right Corner 3", "Right Side(R)", "24+ ft.", 40, 16, 0.40],
                ],
            },
        ]
    }


ZONE_NAMES = [
    "Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3",
    "Right Corner 3", "Above the Break 3", "Backcourt",
]


def location_headers(include_corner_composite=False):
    columns = ["TEAM_ID", "TEAM_NAME"]
    for _ in ZONE_NAMES:
        columns += ["FGM", "FGA", "FG_PCT"]
    if include_corner_composite:
        columns += ["FGM", "FGA", "FG_PCT"]
    return [
        {"name": "SHOT_CATEGORY", "columnNames": list(ZONE_NAMES), "columnSpan": 3, "columnsToSkip": 2},
        {"name": "columns", "columnNames": columns, "columnSpan": 1},
    ]


def location_row(team_id, team_name, *, multiplier=1, include_corner_composite=False):
    result = [team_id, team_name]
    for made, attempts in [(10, 20), (5, 12), (4, 10), (3, 8), (2, 6), (6, 18), (0, 1)]:
        made *= multiplier
        attempts *= multiplier
        result += [made, attempts, made / attempts if attempts else None]
    if include_corner_composite:
        made, attempts = 5 * multiplier, 14 * multiplier
        result += [made, attempts, made / attempts]
    return result


def location_payload(rows, *, include_corner_composite=False):
    return {"resultSets": [{
        "name": "ShotLocations",
        "headers": location_headers(include_corner_composite),
        "rowSet": rows,
    }]}


class WNBAShotContextTests(unittest.TestCase):
    def test_multilevel_headers_flatten_named_zones(self):
        flat = _flatten_shot_location_headers(location_headers())
        self.assertEqual(flat[:2], ["TEAM_ID", "TEAM_NAME"])
        self.assertIn("Restricted Area|FGM", flat)
        self.assertIn("Above the Break 3|FG_PCT", flat)
        self.assertEqual(len(flat), 23)

    def test_multilevel_headers_accept_documented_corner_composite(self):
        flat = _flatten_shot_location_headers(location_headers(True))
        self.assertIn("Corner 3|FGM", flat)
        self.assertIn("Corner 3|FG_PCT", flat)
        self.assertEqual(len(flat), 26)

    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_player_shot_chart_normalizes_coordinates_and_zones(self, mock_request):
        rows = [
            shot_row(1, "Restricted Area", True),
            shot_row(2, "Left Corner 3", False, shot_type="3PT Field Goal"),
            shot_row(3, "Right Corner 3", True, shot_type="3PT Field Goal"),
        ]
        mock_request.return_value = (shot_payload(rows), "2026-08-26T05:54:00+00:00", False)
        dataset = get_player_shot_chart_dataset(1642286, 2026)
        self.assertEqual(dataset["attempt_count"], 3)
        self.assertEqual(dataset["made_count"], 2)
        self.assertEqual(dataset["shots"][0]["game_date"], "2026-08-20")
        self.assertEqual(dataset["shots"][0]["coordinate_system"], "official_stats_source_units")
        self.assertEqual(dataset["shots"][1]["canonical_zone"], "left_corner_3")
        self.assertEqual(dataset["corner_three_composite"]["field_goals_attempted"], 2.0)
        self.assertEqual(dataset["corner_three_composite"]["field_goals_made"], 1.0)

    @patch("sports_api.wnba_shot_context._resolve_official_team_id")
    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_player_opponent_filter_uses_official_team_id_and_league_first(self, mock_request, mock_team_id):
        mock_team_id.return_value = 1611661313
        mock_request.return_value = (shot_payload([]), "2026-08-26T05:54:00+00:00", False)
        dataset = get_player_shot_chart_dataset(1642286, 2026, opponent_team_key="new-york-liberty")
        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("OpponentTeamID", "1611661313"), params)
        self.assertEqual(dataset["filters"]["opponent_team_key"], "new-york-liberty")

    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_player_mismatch_fails_closed(self, mock_request):
        mock_request.return_value = (
            shot_payload([shot_row(1, "Restricted Area", True, player_id=999)]),
            "2026-08-26T05:54:00+00:00", False,
        )
        with self.assertRaisesRegex(WNBAShotContextUpstreamError, "other than the requested"):
            get_player_shot_chart_dataset(1642286, 2026)

    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_duplicate_shot_event_fails_closed(self, mock_request):
        same = shot_row(1, "Restricted Area", True)
        mock_request.return_value = (shot_payload([same, list(same)]), "2026-08-26T05:54:00+00:00", False)
        with self.assertRaisesRegex(WNBAShotContextUpstreamError, "duplicate game/event"):
            get_player_shot_chart_dataset(1642286, 2026)

    @patch("sports_api.wnba_shot_context._resolve_official_team_id")
    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_team_shot_zones_select_requested_team_and_recompute_pct(self, mock_request, mock_team_id):
        mock_team_id.return_value = 1611661325
        mock_request.return_value = (
            location_payload([location_row(1611661325, "Indiana Fever")]),
            "2026-08-26T05:54:00+00:00", False,
        )
        dataset = get_team_shot_zones_dataset("indiana-fever", 2026)
        restricted = next(z for z in dataset["zones"] if z["canonical_zone"] == "restricted_area")
        self.assertEqual(restricted["field_goal_percentage_recomputed"], 0.5)
        self.assertTrue(dataset["verification"]["requested_team_matches_source"])
        params = mock_request.call_args.args[1]
        self.assertIn(("TeamID", "1611661325"), params)
        self.assertIn(("OpponentTeamID", "0"), params)

    @patch("sports_api.wnba_shot_context._resolve_official_team_id")
    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_team_corner_three_is_derived_when_source_has_only_sides(self, mock_request, mock_team_id):
        mock_team_id.return_value = 1611661325
        mock_request.return_value = (
            location_payload([location_row(1611661325, "Indiana Fever")]),
            "2026-08-26T05:54:00+00:00", False,
        )
        dataset = get_team_shot_zones_dataset("indiana-fever", 2026)
        corner = dataset["corner_three_composite"]
        self.assertEqual(corner["field_goals_made"], 5.0)
        self.assertEqual(corner["field_goals_attempted"], 14.0)
        self.assertEqual(corner["derived_from"], ["Left Corner 3", "Right Corner 3"])

    @patch("sports_api.wnba_shot_context._resolve_official_team_id")
    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_defense_aggregates_opponent_rows_by_zone(self, mock_request, mock_team_id):
        mock_team_id.return_value = 1611661325
        rows = [
            location_row(1611661313, "New York Liberty", multiplier=1),
            location_row(1611661329, "Chicago Sky", multiplier=2),
        ]
        mock_request.return_value = (location_payload(rows), "2026-08-26T05:54:00+00:00", False)
        dataset = get_opponent_defense_by_shot_zone_dataset("indiana-fever", 2026)
        restricted = next(z for z in dataset["zones_allowed"] if z["canonical_zone"] == "restricted_area")
        self.assertEqual(restricted["field_goals_made_allowed"], 30.0)
        self.assertEqual(restricted["field_goals_attempted_allowed"], 60.0)
        self.assertEqual(restricted["field_goal_percentage_allowed"], 0.5)
        self.assertEqual(dataset["opponent_shooting_team_count"], 2)
        self.assertTrue(dataset["derivation"]["not_a_projection"])

    @patch("sports_api.wnba_shot_context._resolve_official_team_id")
    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_defense_request_uses_blank_shooting_team_and_defender_as_opponent(self, mock_request, mock_team_id):
        mock_team_id.return_value = 1611661325
        mock_request.return_value = (location_payload([]), "2026-08-26T05:54:00+00:00", False)
        get_opponent_defense_by_shot_zone_dataset("indiana-fever", 2026)
        params = mock_request.call_args.args[1]
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertIn(("TeamID", ""), params)
        self.assertIn(("OpponentTeamID", "1611661325"), params)

    def test_unknown_team_fails_before_stats_request(self):
        with patch("sports_api.wnba_shot_context._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "was not found"):
                get_team_shot_zones_dataset("not-a-team", 2026)
            mock_request.assert_not_called()

    def test_unsupported_season_fails_before_stats_request(self):
        with patch("sports_api.wnba_shot_context._request_stats_json") as mock_request:
            with self.assertRaises(ValueError):
                get_player_shot_chart_dataset(1642286, 2025)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_malformed_shot_chart_schema_fails_closed(self, mock_request):
        bad = shot_payload([])
        bad["resultSets"][0]["headers"] = ["GAME_ID", "PLAYER_ID"]
        mock_request.return_value = (bad, "2026-08-26T05:54:00+00:00", False)
        with self.assertRaisesRegex(WNBAShotContextUpstreamError, "missing required fields"):
            get_player_shot_chart_dataset(1642286, 2026)

    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_empty_player_chart_is_valid_zero_attempt_state(self, mock_request):
        mock_request.return_value = (shot_payload([]), "2026-08-26T05:54:00+00:00", False)
        dataset = get_player_shot_chart_dataset(1642286, 2026)
        self.assertEqual(dataset["shot_count"], 0)
        self.assertEqual(dataset["attempt_count"], 0)
        self.assertIsNone(dataset["field_goal_percentage"])

    @patch("sports_api.wnba_shot_context._request_stats_json")
    def test_unmapped_player_shot_team_is_flagged_not_guessed(self, mock_request):
        mock_request.return_value = (
            shot_payload([shot_row(1, "Restricted Area", True, team_name="Mystery Team")]),
            "2026-08-26T05:54:00+00:00", False,
        )
        dataset = get_player_shot_chart_dataset(1642286, 2026)
        self.assertFalse(dataset["verification"]["all_shot_teams_mapped_to_registry"])
        self.assertIsNone(dataset["shots"][0]["team_key"])


if __name__ == "__main__":
    unittest.main()
