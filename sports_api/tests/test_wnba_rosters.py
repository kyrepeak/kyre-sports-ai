import unittest
from unittest.mock import patch

from sports_api.wnba_rosters import (
    WNBAEntityNotFoundError,
    WNBAStatsUpstreamError,
    _result_rows,
    get_current_players_dataset,
    get_player_profile_dataset,
    get_team_roster_dataset,
)


def _result_set(name, headers, rows):
    return {
        "name": name,
        "headers": headers,
        "rowSet": rows,
    }


class WNBARosterTests(unittest.TestCase):
    def test_result_set_rows_are_mapped_by_headers(self):
        payload = {
            "resultSets": [
                _result_set(
                    "Example",
                    ["PLAYER_ID", "PLAYER"],
                    [[1, "Test Player"]],
                )
            ]
        }
        self.assertEqual(
            _result_rows(payload, "Example"),
            [{"PLAYER_ID": 1, "PLAYER": "Test Player"}],
        )

    @patch("sports_api.wnba_rosters._request_stats_json")
    def test_current_players_use_official_ids_and_step_4a_team_keys(self, mock_request):
        payload = {
            "resultSets": [
                _result_set(
                    "CommonAllPlayers",
                    [
                        "PERSON_ID",
                        "DISPLAY_LAST_COMMA_FIRST",
                        "DISPLAY_FIRST_LAST",
                        "ROSTERSTATUS",
                        "FROM_YEAR",
                        "TO_YEAR",
                        "PLAYERCODE",
                        "PLAYER_SLUG",
                        "TEAM_ID",
                        "TEAM_CITY",
                        "TEAM_NAME",
                        "TEAM_ABBREVIATION",
                        "TEAM_CODE",
                        "TEAM_SLUG",
                        "GAMES_PLAYED_FLAG",
                    ],
                    [
                        [
                            1642291,
                            "Reese, Angel",
                            "Angel Reese",
                            1,
                            2024,
                            2026,
                            "angel-reese",
                            "angel-reese",
                            1611661329,
                            "Atlanta",
                            "Atlanta Dream",
                            "ATL",
                            "dream",
                            "atlanta-dream",
                            1,
                        ],
                        [
                            1999999,
                            "Free, Agent",
                            "Free Agent",
                            0,
                            2026,
                            2026,
                            "free-agent",
                            "free-agent",
                            0,
                            "",
                            "",
                            "",
                            "",
                            "",
                            1,
                        ],
                    ],
                )
            ]
        }
        mock_request.return_value = (
            payload,
            "2026-08-26T00:00:00+00:00",
            False,
        )

        dataset = get_current_players_dataset(2026)

        self.assertEqual(dataset["player_count"], 1)
        player = dataset["players"][0]
        self.assertEqual(player["player_id"], 1642291)
        self.assertEqual(player["team_key"], "atlanta-dream")
        self.assertEqual(player["official_team_id"], 1611661329)
        self.assertTrue(player["is_current_roster"])

    @patch("sports_api.wnba_rosters._request_stats_json")
    def test_team_roster_resolves_team_id_before_roster_call(self, mock_request):
        all_players_payload = {
            "resultSets": [
                _result_set(
                    "CommonAllPlayers",
                    [
                        "PERSON_ID",
                        "DISPLAY_FIRST_LAST",
                        "ROSTERSTATUS",
                        "TEAM_ID",
                        "TEAM_NAME",
                        "TEAM_ABBREVIATION",
                    ],
                    [
                        [
                            1642291,
                            "Angel Reese",
                            1,
                            1611661329,
                            "Atlanta Dream",
                            "ATL",
                        ]
                    ],
                )
            ]
        }

        roster_payload = {
            "resultSets": [
                _result_set(
                    "CommonTeamRoster",
                    [
                        "PLAYER",
                        "NICKNAME",
                        "PLAYER_SLUG",
                        "NUM",
                        "POSITION",
                        "HEIGHT",
                        "WEIGHT",
                        "BIRTH_DATE",
                        "AGE",
                        "EXP",
                        "SCHOOL",
                        "PLAYER_ID",
                        "HOW_ACQUIRED",
                    ],
                    [
                        [
                            "Angel Reese",
                            "Angel",
                            "angel-reese",
                            "5",
                            "F",
                            "6-4",
                            "165",
                            "2002-05-06",
                            24.0,
                            "2",
                            "LSU",
                            1642291,
                            "Trade",
                        ]
                    ],
                )
            ]
        }

        mock_request.side_effect = [
            (all_players_payload, "2026-08-26T00:00:00+00:00", False),
            (roster_payload, "2026-08-26T00:00:01+00:00", False),
        ]

        dataset = get_team_roster_dataset("atlanta-dream", 2026)

        self.assertEqual(dataset["team"]["official_team_id"], 1611661329)
        self.assertEqual(dataset["roster_count"], 1)
        self.assertEqual(dataset["players"][0]["player_id"], 1642291)
        self.assertEqual(dataset["players"][0]["jersey_number"], "5")

        second_call_params = mock_request.call_args_list[1].args[1]
        self.assertEqual(
            second_call_params,
            [
                ("LeagueID", "10"),
                ("Season", "2026"),
                ("TeamID", "1611661329"),
            ],
        )

    @patch("sports_api.wnba_rosters._request_stats_json")
    def test_player_profile_normalizes_bio_headline_and_seasons(self, mock_request):
        payload = {
            "resultSets": [
                _result_set(
                    "CommonPlayerInfo",
                    [
                        "PERSON_ID",
                        "FIRST_NAME",
                        "LAST_NAME",
                        "DISPLAY_FIRST_LAST",
                        "ROSTERSTATUS",
                        "TEAM_ID",
                        "TEAM_NAME",
                        "TEAM_ABBREVIATION",
                        "POSITION",
                        "HEIGHT",
                        "WEIGHT",
                        "JERSEY",
                    ],
                    [
                        [
                            1642286,
                            "Caitlin",
                            "Clark",
                            "Caitlin Clark",
                            1,
                            1611661325,
                            "Indiana Fever",
                            "IND",
                            "G",
                            "6-0",
                            "152",
                            "22",
                        ]
                    ],
                ),
                _result_set(
                    "PlayerHeadlineStats",
                    [
                        "PLAYER_ID",
                        "PLAYER_NAME",
                        "TimeFrame",
                        "PTS",
                        "AST",
                        "REB",
                        "ALL_STAR_APPEARANCES",
                    ],
                    [[1642286, "Caitlin Clark", "2026", 21.4, 8.2, 5.1, 2]],
                ),
                _result_set(
                    "AvailableSeasons",
                    ["SEASON_ID"],
                    [["2024"], ["2025"], ["2026"]],
                ),
            ]
        }
        mock_request.return_value = (
            payload,
            "2026-08-26T00:00:00+00:00",
            False,
        )

        dataset = get_player_profile_dataset(1642286)

        self.assertEqual(dataset["player"]["full_name"], "Caitlin Clark")
        self.assertEqual(dataset["player"]["official_team_id"], 1611661325)
        self.assertEqual(dataset["headline_stats"]["assists"], 8.2)
        self.assertEqual(dataset["available_seasons"], ["2024", "2025", "2026"])

    @patch("sports_api.wnba_rosters._request_stats_json")
    def test_missing_player_returns_not_found(self, mock_request):
        payload = {
            "resultSets": [
                _result_set("CommonPlayerInfo", ["PERSON_ID"], []),
                _result_set("PlayerHeadlineStats", ["PLAYER_ID"], []),
                _result_set("AvailableSeasons", ["SEASON_ID"], []),
            ]
        }
        mock_request.return_value = (
            payload,
            "2026-08-26T00:00:00+00:00",
            False,
        )

        with self.assertRaises(WNBAEntityNotFoundError):
            get_player_profile_dataset(9999999)

    def test_missing_result_set_fails_closed(self):
        with self.assertRaises(WNBAStatsUpstreamError):
            _result_rows({"resultSets": []}, "CommonAllPlayers")

    def test_unknown_team_key_returns_not_found_before_network(self):
        with self.assertRaises(WNBAEntityNotFoundError):
            get_team_roster_dataset("not-a-team", 2026)


if __name__ == "__main__":
    unittest.main()
