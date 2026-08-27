import unittest
from unittest.mock import patch

from sports_api.wnba_schedule_context import (
    WNBARestTravelNotFoundError,
    WNBARestTravelUpstreamError,
    _haversine_miles,
    _season_schedule_dataset,
    get_game_rest_travel_context,
    get_rest_travel_board,
    get_team_rest_travel_context,
)


def game(game_id, date, away, home, city, *, utc="2026-08-26T23:00:00+00:00", neutral=False):
    return {
        "game_id": game_id,
        "official_schedule_date": date,
        "game_datetime_utc": utc,
        "game_datetime_eastern": utc,
        "status": {"category": "scheduled", "code": 1, "text": "7:00 pm ET"},
        "schedule_change": {"cancelled": False, "postponed": False, "schedule_changed": False},
        "venue": {"name": "Arena", "city": city, "state": None, "is_neutral": neutral},
        "away": {"team_key": away, "mapped_to_registry": True},
        "home": {"team_key": home, "mapped_to_registry": True},
        "verification": {"game_id_valid": True, "teams_mapped_to_registry": True},
    }


def schedule(games):
    return {
        "source": "WNBA Official Schedule",
        "source_url": "official",
        "source_variant": "test",
        "league_id": "10",
        "season": 2026,
        "retrieved_at_utc": "2026-08-26T06:20:00+00:00",
        "cache_hit": False,
        "games": games,
        "verification": {
            "all_game_ids_valid": True,
            "all_game_ids_unique": True,
            "all_teams_mapped_to_registry": True,
        },
    }


BASE_GAMES = [
    game("1022600201", "2026-08-22", "seattle-storm", "portland-fire", "Portland", utc="2026-08-23T02:00:00+00:00"),
    game("1022600202", "2026-08-24", "seattle-storm", "dallas-wings", "Arlington", utc="2026-08-24T23:00:00+00:00"),
    game("1022600203", "2026-08-25", "seattle-storm", "minnesota-lynx", "Minneapolis", utc="2026-08-26T00:00:00+00:00"),
    game("1022600204", "2026-08-26", "toronto-tempo", "seattle-storm", "Seattle", utc="2026-08-27T02:00:00+00:00"),
    game("1022600205", "2026-08-27", "seattle-storm", "las-vegas-aces", "Las Vegas", utc="2026-08-28T02:00:00+00:00"),
    game("1022600206", "2026-08-30", "los-angeles-sparks", "seattle-storm", "Seattle", utc="2026-08-30T21:00:00+00:00"),
]


def history(minutes=225.0):
    return {
        "source": "WNBA Stats API",
        "source_endpoint": "leaguegamelog",
        "games": [
            {"game_id": "1022600203", "game_date": "2026-08-25", "minutes": minutes},
            {"game_id": "1022600202", "game_date": "2026-08-24", "minutes": 200.0},
            {"game_id": "1022600201", "game_date": "2026-08-22", "minutes": 200.0},
        ],
        "verification": {"schema_verified": True},
    }


class WNBAScheduleContextTests(unittest.TestCase):
    @patch("sports_api.wnba_schedule_context.get_team_game_log_dataset")
    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_back_to_back_and_density(self, mock_schedule, mock_history):
        mock_schedule.return_value = schedule(BASE_GAMES)
        mock_history.return_value = history()
        ctx = get_team_rest_travel_context("seattle-storm", 2026, "2026-08-26")
        self.assertTrue(ctx["has_game_on_date"])
        self.assertEqual(ctx["rest"]["calendar_days_since_previous_game"], 1)
        self.assertEqual(ctx["rest"]["full_rest_days_before_date"], 0)
        self.assertTrue(ctx["rest"]["is_second_night_of_back_to_back"])
        self.assertTrue(ctx["rest"]["is_first_night_of_back_to_back"])
        self.assertEqual(ctx["rest"]["back_to_back_position"], "middle_of_three_consecutive_calendar_days")
        self.assertTrue(ctx["schedule_density"]["three_in_five_through_date"])
        self.assertTrue(ctx["schedule_density"]["four_in_seven_through_date"])

    @patch("sports_api.wnba_schedule_context.get_team_game_log_dataset")
    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_travel_context_uses_city_centroid_not_route_miles(self, mock_schedule, mock_history):
        mock_schedule.return_value = schedule(BASE_GAMES)
        mock_history.return_value = history()
        ctx = get_team_rest_travel_context("seattle-storm", 2026, "2026-08-26")
        travel = ctx["travel_to_target_or_next_game"]
        self.assertTrue(travel["available"])
        self.assertGreater(travel["great_circle_miles"], 1000)
        self.assertFalse(travel["distance_is_route_miles"])
        self.assertEqual(travel["method"], "venue_city_centroid_haversine")
        self.assertEqual(travel["timezone_offset_change_hours"], -2.0)

    @patch("sports_api.wnba_schedule_context.get_team_game_log_dataset")
    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_road_trip_game_number(self, mock_schedule, mock_history):
        road = [
            game("1022600301", "2026-08-23", "seattle-storm", "dallas-wings", "Arlington"),
            game("1022600302", "2026-08-25", "seattle-storm", "minnesota-lynx", "Minneapolis"),
            game("1022600303", "2026-08-26", "seattle-storm", "chicago-sky", "Chicago"),
        ]
        mock_schedule.return_value = schedule(road)
        mock_history.return_value = history()
        ctx = get_team_rest_travel_context("seattle-storm", 2026, "2026-08-26")
        self.assertEqual(ctx["road_trip"]["road_trip_game_number"], 3)

    @patch("sports_api.wnba_schedule_context.get_team_game_log_dataset")
    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_observed_workload_tracks_minutes_above_regulation(self, mock_schedule, mock_history):
        mock_schedule.return_value = schedule(BASE_GAMES)
        mock_history.return_value = history(225.0)
        ctx = get_team_rest_travel_context("seattle-storm", 2026, "2026-08-26")
        load = ctx["observed_workload"]
        self.assertEqual(load["completed_games_previous_3_days"], 2)
        self.assertEqual(load["completed_games_previous_5_days"], 3)
        self.assertEqual(load["team_minutes_previous_7_days"], 625.0)
        self.assertEqual(load["team_minutes_above_regulation_previous_7_days"], 25.0)
        self.assertEqual(load["games_above_regulation_team_minutes_previous_7_days"], 1)

    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_workload_can_be_disabled(self, mock_schedule):
        mock_schedule.return_value = schedule(BASE_GAMES)
        ctx = get_team_rest_travel_context(
            "seattle-storm", 2026, "2026-08-26", include_observed_workload=False
        )
        self.assertEqual(ctx["observed_workload"], {"included": False})

    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_off_day_context_uses_next_game(self, mock_schedule):
        mock_schedule.return_value = schedule(BASE_GAMES)
        ctx = get_team_rest_travel_context(
            "seattle-storm", 2026, "2026-08-28", include_observed_workload=False
        )
        self.assertFalse(ctx["has_game_on_date"])
        self.assertEqual(ctx["previous_game"]["date"], "2026-08-27")
        self.assertEqual(ctx["next_game"]["date"], "2026-08-30")
        self.assertTrue(ctx["travel_to_target_or_next_game"]["available"])

    @patch("sports_api.wnba_schedule_context.get_team_rest_travel_context")
    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_game_context_requires_both_team_contexts_match(self, mock_schedule, mock_team):
        target = BASE_GAMES[3]
        mock_schedule.return_value = schedule(BASE_GAMES)

        def side(team_key, season, target_date, include_observed_workload=True):
            return {
                "target_game": {"game_id": target["game_id"]},
                "team": {"team_key": team_key},
            }

        mock_team.side_effect = side
        ctx = get_game_rest_travel_context(target["game_id"], 2026, include_observed_workload=False)
        self.assertTrue(ctx["verification"]["requested_game_id_matches_both_team_contexts"])
        self.assertEqual(ctx["away_team_key"], "toronto-tempo")
        self.assertEqual(ctx["home_team_key"], "seattle-storm")

    @patch("sports_api.wnba_schedule_context.get_team_rest_travel_context")
    def test_board_games_only(self, mock_team):
        def ctx(team_key, season, target_date, include_observed_workload=False):
            has_game = team_key in {"seattle-storm", "toronto-tempo"}
            return {
                "has_game_on_date": has_game,
                "target_game": {"game_datetime_utc": "2026-08-27T02:00:00+00:00"} if has_game else None,
                "team": {"team_key": team_key},
            }

        mock_team.side_effect = ctx
        board = get_rest_travel_board(2026, "2026-08-26", games_only=True)
        self.assertEqual(board["team_count"], 2)
        self.assertEqual(
            {item["team"]["team_key"] for item in board["teams"]},
            {"seattle-storm", "toronto-tempo"},
        )

    def test_invalid_game_id_fails_before_schedule(self):
        with patch("sports_api.wnba_schedule_context._season_schedule_dataset") as mock_schedule:
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                get_game_rest_travel_context("123", 2026)
            mock_schedule.assert_not_called()

    def test_unknown_team_fails_before_schedule(self):
        with patch("sports_api.wnba_schedule_context._season_schedule_dataset") as mock_schedule:
            with self.assertRaises(WNBARestTravelNotFoundError):
                get_team_rest_travel_context("not-a-team", 2026, "2026-08-26")
            mock_schedule.assert_not_called()

    @patch("sports_api.wnba_schedule_context._fetch_schedule_payload")
    def test_full_schedule_rejects_duplicate_game_ids(self, mock_fetch):
        raw = {
            "leagueSchedule": {
                "leagueId": "10",
                "gameDates": [
                    {"gameDate": "2026-08-26", "games": [{"gameId": "1022600999"}, {"gameId": "1022600999"}]}
                ],
            }
        }
        mock_fetch.return_value = (raw, "x", "test", "url", False)
        normalized = game("1022600999", "2026-08-26", "toronto-tempo", "seattle-storm", "Seattle")
        with patch("sports_api.wnba_schedule_context._normalize_game", return_value=normalized):
            with self.assertRaises(WNBARestTravelUpstreamError):
                _season_schedule_dataset(2026)

    def test_haversine_same_point_zero(self):
        point = {"lat": 47.6062, "lon": -122.3321}
        self.assertAlmostEqual(_haversine_miles(point, point), 0.0, places=6)

    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_multiple_team_games_same_date_fails_closed(self, mock_schedule):
        duplicate_day = BASE_GAMES + [
            game("1022600299", "2026-08-26", "seattle-storm", "phoenix-mercury", "Phoenix")
        ]
        mock_schedule.return_value = schedule(duplicate_day)
        with self.assertRaisesRegex(WNBARestTravelUpstreamError, "multiple active games"):
            get_team_rest_travel_context(
                "seattle-storm", 2026, "2026-08-26", include_observed_workload=False
            )

    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_game_not_found(self, mock_schedule):
        mock_schedule.return_value = schedule(BASE_GAMES)
        with self.assertRaises(WNBARestTravelNotFoundError):
            get_game_rest_travel_context("1022699999", 2026, include_observed_workload=False)

    @patch("sports_api.wnba_schedule_context._season_schedule_dataset")
    def test_invalid_date_fails(self, mock_schedule):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            get_team_rest_travel_context(
                "seattle-storm", 2026, "08/26/2026", include_observed_workload=False
            )
        mock_schedule.assert_not_called()


if __name__ == "__main__":
    unittest.main()
