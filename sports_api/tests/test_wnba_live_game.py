import unittest
from unittest.mock import patch

from sports_api.wnba_live_game import (
    WNBALiveUpstreamError,
    clock_to_seconds_remaining,
    get_live_game_state_dataset,
    get_live_scoreboard_dataset,
    get_play_by_play_dataset,
)


def _scoreboard_payload():
    return {
        "scoreboard": {
            "gameDate": "2026-08-26",
            "leagueId": "10",
            "games": [{
                "gameId": "1022600200",
                "gameCode": "20260826/NYLIND",
                "gameStatus": 2,
                "gameStatusText": "Q3 04:31",
                "period": 3,
                "gameClock": "PT04M31.00S",
                "homeTeam": {
                    "teamId": 1611661325,
                    "teamTricode": "IND",
                    "teamCity": "Indiana",
                    "teamName": "Fever",
                    "score": 61,
                },
                "awayTeam": {
                    "teamId": 1611661313,
                    "teamTricode": "NYL",
                    "teamCity": "New York",
                    "teamName": "Liberty",
                    "score": 58,
                },
            }],
        }
    }


def _player(player_id, oncourt="1"):
    return {
        "personId": player_id,
        "name": f"Player {player_id}",
        "nameI": f"P. {player_id}",
        "jerseyNum": str(player_id % 30),
        "position": "G",
        "starter": "1",
        "oncourt": oncourt,
        "played": "1",
        "statistics": {
            "minutes": "PT20M00.00S",
            "points": 8,
            "reboundsTotal": 3,
            "reboundsOffensive": 1,
            "reboundsDefensive": 2,
            "assists": 4,
            "steals": 1,
            "blocks": 0,
            "turnovers": 2,
            "foulsPersonal": 1,
            "fieldGoalsMade": 3,
            "fieldGoalsAttempted": 6,
            "fieldGoalsPercentage": 0.5,
            "threePointersMade": 1,
            "threePointersAttempted": 2,
            "threePointersPercentage": 0.5,
            "freeThrowsMade": 1,
            "freeThrowsAttempted": 1,
            "freeThrowsPercentage": 1.0,
            "plusMinusPoints": 3,
        },
    }


def _team(team_id, tricode, city, name, score, start_id):
    return {
        "teamId": team_id,
        "teamTricode": tricode,
        "teamCity": city,
        "teamName": name,
        "score": score,
        "inBonus": "1",
        "timeoutsRemaining": 3,
        "players": [_player(start_id + index) for index in range(5)]
        + [_player(start_id + 10, "0")],
    }


def _box_payload(unmapped=False):
    home = (
        _team(999999, "XXX", "Unknown", "Unknown", 61, 100)
        if unmapped
        else _team(1611661325, "IND", "Indiana", "Fever", 61, 100)
    )
    return {
        "game": {
            "gameId": "1022600200",
            "gameStatus": 2,
            "gameStatusText": "Q3 04:31",
            "period": 3,
            "periodType": "REGULAR",
            "gameClock": "PT04M31.00S",
            "homeTeam": home,
            "awayTeam": _team(
                1611661313, "NYL", "New York", "Liberty", 58, 200
            ),
        }
    }


def _pbp_payload(duplicate=False):
    last_id = "4" if duplicate else "5"
    return {
        "game": {
            "gameId": "1022600200",
            "actions": [
                {
                    "actionNumber": 1,
                    "actionId": "1",
                    "clock": "PT10M00.00S",
                    "period": 1,
                    "actionType": "period",
                    "subType": "start",
                    "scoreHome": "0",
                    "scoreAway": "0",
                },
                {
                    "actionNumber": 2,
                    "actionId": "2",
                    "clock": "PT09M44.00S",
                    "period": 1,
                    "teamId": 1611661325,
                    "teamTricode": "IND",
                    "personId": 1642286,
                    "playerName": "Caitlin Clark",
                    "actionType": "3pt",
                    "subType": "Jump Shot",
                    "shotResult": "Made",
                    "isFieldGoal": 1,
                    "scoreHome": "3",
                    "scoreAway": "0",
                },
                {
                    "actionNumber": 3,
                    "actionId": "3",
                    "clock": "PT09M20.00S",
                    "period": 1,
                    "teamId": 1611661313,
                    "teamTricode": "NYL",
                    "actionType": "freethrow",
                    "scoreHome": "3",
                    "scoreAway": "1",
                },
                {
                    "actionNumber": 4,
                    "actionId": "4",
                    "clock": "PT08M58.00S",
                    "period": 1,
                    "teamId": 1611661325,
                    "teamTricode": "IND",
                    "actionType": "rebound",
                    "scoreHome": "3",
                    "scoreAway": "1",
                },
                {
                    "actionNumber": 99,
                    "actionId": last_id,
                    "clock": "PT04M31.00S",
                    "period": 3,
                    "teamId": 1611661325,
                    "teamTricode": "IND",
                    "actionType": "substitution",
                    "scoreHome": "61",
                    "scoreAway": "58",
                },
            ],
        }
    }


class WNBALiveGameTests(unittest.TestCase):
    def test_clock_conversion(self):
        self.assertEqual(clock_to_seconds_remaining("PT04M31.00S"), 271.0)
        self.assertEqual(clock_to_seconds_remaining("PT45.50S"), 45.5)
        self.assertIsNone(clock_to_seconds_remaining("4:31"))

    @patch("sports_api.wnba_live_game._request_json")
    def test_scoreboard_normalizes_live_game_and_teams(self, mock_request):
        mock_request.return_value = (
            _scoreboard_payload(), "2026-08-26T05:45:00+00:00", False
        )
        dataset = get_live_scoreboard_dataset(2026)
        self.assertEqual(dataset["game_count"], 1)
        self.assertEqual(dataset["live_game_count"], 1)
        game = dataset["games"][0]
        self.assertEqual(game["home"]["team_key"], "indiana-fever")
        self.assertEqual(game["away"]["team_key"], "new-york-liberty")
        self.assertEqual(game["clock_seconds_remaining"], 271.0)

    @patch("sports_api.wnba_live_game._request_json")
    def test_play_by_play_categories_and_score_deltas(self, mock_request):
        mock_request.return_value = (
            _pbp_payload(), "2026-08-26T05:45:00+00:00", False
        )
        dataset = get_play_by_play_dataset("1022600200", 2026)
        self.assertEqual(dataset["source_action_count"], 5)
        self.assertEqual(dataset["actions"][1]["event_category"], "shot")
        self.assertEqual(dataset["actions"][1]["points_scored_on_action"], 3)
        self.assertEqual(dataset["actions"][2]["event_category"], "free_throw")
        self.assertEqual(dataset["actions"][2]["points_scored_on_action"], 1)
        self.assertEqual(dataset["actions"][3]["event_category"], "rebound")

    @patch("sports_api.wnba_live_game._request_json")
    def test_play_by_play_filter_and_limit(self, mock_request):
        mock_request.return_value = (
            _pbp_payload(), "2026-08-26T05:45:00+00:00", False
        )
        dataset = get_play_by_play_dataset(
            "1022600200", 2026, event_category="shot", limit=1
        )
        self.assertEqual(dataset["action_count"], 1)
        self.assertEqual(dataset["actions"][0]["action_number"], 2)

    def test_invalid_game_id_fails_before_network(self):
        with patch("sports_api.wnba_live_game._request_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "10-digit"):
                get_play_by_play_dataset("123", 2026)
            mock_request.assert_not_called()

    @patch("sports_api.wnba_live_game._request_json")
    def test_play_by_play_game_id_mismatch_fails_closed(self, mock_request):
        bad = _pbp_payload()
        bad["game"]["gameId"] = "1022609999"
        mock_request.return_value = (
            bad, "2026-08-26T05:45:00+00:00", False
        )
        with self.assertRaisesRegex(WNBALiveUpstreamError, "did not match"):
            get_play_by_play_dataset("1022600200", 2026)

    @patch("sports_api.wnba_live_game.get_play_by_play_dataset")
    @patch("sports_api.wnba_live_game._request_json")
    def test_live_state_has_exact_five_on_court(self, mock_request, mock_pbp):
        mock_request.return_value = (
            _box_payload(), "2026-08-26T05:45:00+00:00", False
        )
        mock_pbp.return_value = {
            "source_url": "pbp",
            "source_action_count": 1,
            "latest_event": {"score_home": 61, "score_away": 58},
        }
        dataset = get_live_game_state_dataset("1022600200", 2026)
        self.assertEqual(dataset["home"]["on_court_count"], 5)
        self.assertTrue(dataset["verification"]["home_on_court_exactly_five"])
        self.assertTrue(dataset["verification"]["away_on_court_exactly_five"])
        self.assertTrue(
            dataset["verification"]["box_score_matches_latest_play_by_play_score"]
        )

    @patch("sports_api.wnba_live_game.get_play_by_play_dataset")
    @patch("sports_api.wnba_live_game._request_json")
    def test_live_state_degrades_when_pbp_unavailable(self, mock_request, mock_pbp):
        mock_request.return_value = (
            _box_payload(), "2026-08-26T05:45:00+00:00", False
        )
        mock_pbp.side_effect = WNBALiveUpstreamError("blocked")
        dataset = get_live_game_state_dataset("1022600200", 2026)
        self.assertFalse(dataset["play_by_play"]["available"])
        self.assertIsNone(
            dataset["verification"]["box_score_matches_latest_play_by_play_score"]
        )

    @patch("sports_api.wnba_live_game.get_play_by_play_dataset")
    @patch("sports_api.wnba_live_game._request_json")
    def test_live_state_unmapped_team_fails_closed(self, mock_request, mock_pbp):
        mock_request.return_value = (
            _box_payload(unmapped=True), "2026-08-26T05:45:00+00:00", False
        )
        mock_pbp.return_value = {
            "source_url": "pbp", "source_action_count": 0, "latest_event": None
        }
        with self.assertRaisesRegex(WNBALiveUpstreamError, "unmapped team"):
            get_live_game_state_dataset("1022600200", 2026)

    @patch("sports_api.wnba_live_game._request_json")
    def test_duplicate_action_ids_are_flagged(self, mock_request):
        mock_request.return_value = (
            _pbp_payload(duplicate=True), "2026-08-26T05:45:00+00:00", False
        )
        dataset = get_play_by_play_dataset("1022600200", 2026)
        self.assertFalse(dataset["verification"]["action_ids_unique_when_present"])
        self.assertEqual(dataset["verification"]["duplicate_action_ids"], ["4"])

    @patch("sports_api.wnba_live_game._request_json")
    def test_scoreboard_wrong_league_fails_closed(self, mock_request):
        bad = _scoreboard_payload()
        bad["scoreboard"]["leagueId"] = "00"
        mock_request.return_value = (
            bad, "2026-08-26T05:45:00+00:00", False
        )
        with self.assertRaisesRegex(WNBALiveUpstreamError, "unexpected leagueId"):
            get_live_scoreboard_dataset(2026)

    def test_bad_event_category_fails_before_network(self):
        with patch("sports_api.wnba_live_game._request_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "event_category"):
                get_play_by_play_dataset(
                    "1022600200", 2026, event_category="assist"
                )
            mock_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
