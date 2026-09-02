import unittest
from unittest.mock import patch

from sports_api.wnba_step7g_first_party_history import (
    EXACT_ROTATION_SUPPORTED,
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    _extract_action_rows,
    get_first_party_exact_rotation_dataset,
    get_first_party_game_box_score_dataset,
    get_first_party_play_by_play_dataset,
    get_first_party_player_recent_game_log_dataset,
)

STAMP = "2026-08-27T18:50:00+00:00"


def _stats(minutes="PT35M30.00S", points=24, rebounds=7, assists=9):
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
        "plusMinusPoints": 6,
    }


def _player(player_id, first, last, *, points=24):
    return {
        "personId": player_id,
        "firstName": first,
        "familyName": last,
        "nameI": f"{first[0]}. {last}",
        "playerSlug": f"{first}-{last}".lower(),
        "jerseyNum": "22",
        "position": "G",
        "comment": "",
        "statistics": _stats(points=points),
    }


def _team(team_id, city, name, tricode, slug, players):
    return {
        "teamId": team_id,
        "teamCity": city,
        "teamName": name,
        "teamTricode": tricode,
        "teamSlug": slug,
        "statistics": _stats(minutes="PT200M00.00S", points=88, rebounds=35, assists=21),
        "starters": _stats(minutes="PT150M00.00S", points=68, rebounds=25, assists=17),
        "bench": _stats(minutes="PT50M00.00S", points=20, rebounds=10, assists=4),
        "players": players,
    }


def _game(game_id="1022600300"):
    return {
        "gameId": game_id,
        "homeTeam": _team(
            1611661313, "New York", "Liberty", "NYL", "liberty",
            [_player(1629477, "Sabrina", "Ionescu", points=22)],
        ),
        "awayTeam": _team(
            1611661325, "Indiana", "Fever", "IND", "fever",
            [_player(1642286, "Caitlin", "Clark", points=24)],
        ),
    }


def _log_row(game_id, matchup, *, season_id="22026", player_id=1642286, date="AUG 24, 2026"):
    return {
        "SEASON_ID": season_id,
        "Player_ID": player_id,
        "Game_ID": game_id,
        "GAME_DATE": date,
        "MATCHUP": matchup,
        "WL": "W",
        "MIN": 35.5,
        "FGM": 8,
        "FGA": 16,
        "FG_PCT": 0.5,
        "FG3M": 3,
        "FG3A": 7,
        "FG3_PCT": 0.4286,
        "FTM": 5,
        "FTA": 6,
        "FT_PCT": 0.8333,
        "OREB": 1,
        "DREB": 6,
        "REB": 7,
        "AST": 9,
        "STL": 2,
        "BLK": 1,
        "TOV": 3,
        "PF": 2,
        "PTS": 24,
        "PLUS_MINUS": 6,
        "VIDEO_AVAILABLE": 1,
    }


def _action(number, action_type, *, score_home="0", score_away="0", subtype=""):
    return {
        "actionNumber": number,
        "actionId": str(number),
        "period": 1,
        "clock": "PT9M30.00S",
        "teamId": 1611661325,
        "teamTricode": "IND",
        "personId": 1642286,
        "playerName": "Caitlin Clark",
        "playerNameI": "C. Clark",
        "description": action_type,
        "actionType": action_type,
        "subType": subtype,
        "scoreHome": score_home,
        "scoreAway": score_away,
        "videoAvailable": False,
        "qualifiers": [],
    }


class Step7GFirstPartyHistoryTests(unittest.TestCase):
    @patch("sports_api.wnba_step7g_first_party_history._request_page_props")
    def test_box_score_matches_frozen_step4d_shape(self, request):
        request.return_value = ({"game": _game()}, STAMP, False, 30)
        data = get_first_party_game_box_score_dataset("1022600300", 2026)
        self.assertEqual(data["data_type"], "official_traditional_box_score")
        self.assertEqual(data["home"]["team_key"], "new-york-liberty")
        self.assertEqual(data["away"]["team_key"], "indiana-fever")
        self.assertEqual(data["away"]["players"][0]["stats"]["points"], 24)
        self.assertAlmostEqual(data["away"]["players"][0]["stats"]["minutes"], 35.5)
        self.assertTrue(data["verification"]["normalized_with_frozen_step4d_box_contract"])
        self.assertFalse(data["verification"]["production_provider_replaced"])

    @patch("sports_api.wnba_step7g_first_party_history._request_page_props")
    def test_box_score_rejects_mismatched_game_id(self, request):
        request.return_value = ({"game": _game("1022600999")}, STAMP, False, 30)
        with self.assertRaises(WNBAStep7GFirstPartyUpstreamError):
            get_first_party_game_box_score_dataset("1022600300", 2026)

    @patch("sports_api.wnba_step7g_first_party_history._request_page_props")
    def test_recent_game_log_filters_season_type_and_normalizes_rows(self, request):
        request.return_value = (
            {
                "player": {
                    "cms": {"playerId": "1642286"},
                    "latestGames": [
                        _log_row("1022600300", "IND vs. NYL"),
                        _log_row("1022600291", "IND @ CHI", date="AUG 22, 2026"),
                        _log_row("1022500001", "IND @ NYL", season_id="22025"),
                    ],
                }
            },
            STAMP,
            False,
            120,
        )
        data = get_first_party_player_recent_game_log_dataset(1642286, 2026)
        self.assertEqual(data["game_count"], 2)
        self.assertEqual(data["season_id_filter"], "22026")
        self.assertEqual(data["games"][0]["game_date"], "2026-08-24")
        self.assertEqual(data["games"][0]["matchup"]["team_key"], "indiana-fever")
        self.assertEqual(data["games"][1]["matchup"]["opponent_team_key"], "chicago-sky")
        self.assertFalse(data["history_scope"]["full_season_history_guaranteed"])
        self.assertTrue(data["verification"]["normalized_with_frozen_step4d_game_log_contract"])
        self.assertFalse(data["verification"]["full_season_history_claimed"])

    @patch("sports_api.wnba_step7g_first_party_history._request_page_props")
    def test_recent_game_log_rejects_wrong_page_player_identity(self, request):
        request.return_value = (
            {"player": {"cms": {"playerId": "9999999"}, "latestGames": []}},
            STAMP,
            False,
            120,
        )
        with self.assertRaises(WNBAStep7GFirstPartyUpstreamError):
            get_first_party_player_recent_game_log_dataset(1642286, 2026)

    def test_action_extractor_supports_direct_and_grouped_surfaces(self):
        a1 = _action(1, "2pt", score_away="2")
        a2 = _action(2, "substitution", score_away="2")
        self.assertEqual(_extract_action_rows([a1, a2]), [a1, a2])
        self.assertEqual(
            _extract_action_rows({"periods": [{"actions": [a1]}, {"actions": [a2]}]}),
            [a1, a2],
        )

    @patch("sports_api.wnba_step7g_first_party_history._request_page_props")
    def test_play_by_play_matches_frozen_step4k_action_shape(self, request):
        actions = [
            _action(1, "2pt", score_away="2"),
            _action(2, "substitution", score_away="2"),
        ]
        request.return_value = (
            {"game": _game(), "playByPlay": {"actions": actions}},
            STAMP,
            False,
            4,
        )
        data = get_first_party_play_by_play_dataset("1022600300", 2026)
        self.assertEqual(data["source_action_count"], 2)
        self.assertEqual(data["actions"][0]["event_category"], "shot")
        self.assertEqual(data["actions"][0]["points_scored_on_action"], 2)
        self.assertEqual(data["actions"][1]["event_category"], "substitution")
        self.assertTrue(data["verification"]["normalized_with_frozen_step4k_action_contract"])
        self.assertFalse(data["verification"]["production_provider_replaced"])

    @patch("sports_api.wnba_step7g_first_party_history._request_page_props")
    def test_play_by_play_category_filter_preserves_source_count(self, request):
        actions = [_action(1, "2pt", score_away="2"), _action(2, "substitution", score_away="2")]
        request.return_value = (
            {"game": _game(), "playByPlay": actions}, STAMP, False, 4
        )
        data = get_first_party_play_by_play_dataset(
            "1022600300", 2026, event_category="substitution"
        )
        self.assertEqual(data["source_action_count"], 2)
        self.assertEqual(data["action_count"], 1)
        self.assertEqual(data["actions"][0]["event_category"], "substitution")

    def test_exact_rotation_is_explicitly_unsupported_and_fail_closed(self):
        self.assertFalse(EXACT_ROTATION_SUPPORTED)
        with self.assertRaisesRegex(
            WNBAStep7GFirstPartyNotFoundError,
            "PBP substitution reconstruction is intentionally disabled",
        ):
            get_first_party_exact_rotation_dataset("1022600300", 2026)

    def test_invalid_ids_fail_before_network(self):
        with patch("sports_api.wnba_step7g_first_party_history._request_page_props") as request:
            with self.assertRaises(ValueError):
                get_first_party_game_box_score_dataset("bad", 2026)
            with self.assertRaises(ValueError):
                get_first_party_player_recent_game_log_dataset(0, 2026)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
