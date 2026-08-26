import unittest
from unittest.mock import patch

from sports_api import wnba_officiating_context as m


TEAM_ROWS = [
    {
        "official_team_id": 1,
        "team_key": "seattle-storm",
        "team_full_name": "Seattle Storm",
        "team_abbreviation": "SEA",
        "games_played": 30,
        "stats": {
            "minutes": 40.0,
            "field_goals_attempted": 70.0,
            "free_throws_made": 18.0,
            "free_throws_attempted": 22.0,
            "free_throw_percentage": .818,
            "personal_fouls": 17.0,
            "personal_fouls_drawn": 19.0,
            "points": 82.0,
        },
    },
    {
        "official_team_id": 2,
        "team_key": "toronto-tempo",
        "team_full_name": "Toronto Tempo",
        "team_abbreviation": "TOR",
        "games_played": 30,
        "stats": {
            "minutes": 40.0,
            "field_goals_attempted": 72.0,
            "free_throws_made": 14.0,
            "free_throws_attempted": 18.0,
            "free_throw_percentage": .778,
            "personal_fouls": 20.0,
            "personal_fouls_drawn": 16.0,
            "points": 78.0,
        },
    },
    {
        "official_team_id": 3,
        "team_key": "las-vegas-aces",
        "team_full_name": "Las Vegas Aces",
        "team_abbreviation": "LVA",
        "games_played": 30,
        "stats": {
            "minutes": 40.0,
            "field_goals_attempted": 68.0,
            "free_throws_made": 20.0,
            "free_throws_attempted": 25.0,
            "free_throw_percentage": .800,
            "personal_fouls": 15.0,
            "personal_fouls_drawn": 21.0,
            "points": 88.0,
        },
    },
]


def team_dataset():
    return {
        "source": "WNBA Stats API",
        "source_url": "https://stats.wnba.com/",
        "source_endpoint": "leaguedashteamstats",
        "window_scope": "season_to_date",
        "retrieved_at_utc": "x",
        "cache_hit": False,
        "teams": TEAM_ROWS,
    }


def player_dataset(multiple=False):
    rows = [
        {
            "player_id": 99,
            "player_name": "Test Player",
            "team_key": "seattle-storm",
            "team_full_name": "Seattle Storm",
            "official_team_id": 1,
            "games_played": 20,
            "mapped_to_registry": True,
            "stats": {
                "minutes": 30.0,
                "field_goals_attempted": 15.0,
                "free_throws_made": 4.0,
                "free_throws_attempted": 5.0,
                "free_throw_percentage": .8,
                "personal_fouls": 2.0,
                "personal_fouls_drawn": 3.0,
                "points": 18.0,
            },
        }
    ]
    if multiple:
        rows.append(
            {
                **rows[0],
                "team_key": None,
                "team_full_name": None,
                "official_team_id": 0,
                "mapped_to_registry": False,
            }
        )
    return {
        "source": "WNBA Stats API",
        "source_url": "https://stats.wnba.com/",
        "source_endpoint": "leaguedashplayerstats",
        "window_scope": "season_to_date",
        "retrieved_at_utc": "x",
        "cache_hit": False,
        "players": rows,
    }


def summary_payload(*, officials=True, mismatch=False, duplicate=False):
    crew = []
    if officials:
        crew = [
            {
                "personId": 101,
                "name": "Ref One",
                "nameI": "R. One",
                "firstName": "Ref",
                "familyName": "One",
                "jerseyNum": "11",
            },
            {
                "personId": 102 if not duplicate else 101,
                "name": "Ref Two",
                "nameI": "R. Two",
                "firstName": "Ref",
                "familyName": "Two",
                "jerseyNum": "22",
            },
            {
                "personId": 103,
                "name": "Ref Three",
                "nameI": "R. Three",
                "firstName": "Ref",
                "familyName": "Three",
                "jerseyNum": "33",
            },
        ]
    return {
        "boxScoreSummary": {
            "gameId": "1022600204" if not mismatch else "1022600999",
            "gameStatus": 1,
            "gameStatusText": "7:00 pm ET",
            "period": 0,
            "gameClock": "",
            "awayTeam": {
                "teamId": 2,
                "teamCity": "Toronto",
                "teamName": "Tempo",
                "teamTricode": "TOR",
                "teamSlug": "toronto-tempo",
            },
            "homeTeam": {
                "teamId": 1,
                "teamCity": "Seattle",
                "teamName": "Storm",
                "teamTricode": "SEA",
                "teamSlug": "seattle-storm",
            },
            "officials": crew,
        }
    }


class WNBAOfficiatingContextTests(unittest.TestCase):
    def setUp(self):
        request_patcher = patch("sports_api.wnba_officiating_context._request_stats_json")
        team_patcher = patch("sports_api.wnba_officiating_context.get_team_season_stats_dataset")
        player_patcher = patch("sports_api.wnba_officiating_context.get_player_season_stats_dataset")
        self.mock_request = request_patcher.start()
        self.mock_team_stats = team_patcher.start()
        self.mock_player_stats = player_patcher.start()
        self.addCleanup(request_patcher.stop)
        self.addCleanup(team_patcher.stop)
        self.addCleanup(player_patcher.stop)
        self.mock_request.return_value = (summary_payload(), "x", False)
        self.mock_team_stats.return_value = team_dataset()
        self.mock_player_stats.return_value = player_dataset()

    def test_invalid_game_id_fails_before_upstream(self):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_game_officials_dataset("123", 2026)
        self.mock_request.assert_not_called()

    def test_officials_normalize(self):
        dataset = m.get_game_officials_dataset("1022600204", 2026)
        self.assertEqual(dataset["official_count"], 3)
        self.assertTrue(dataset["officials_available"])
        self.assertEqual(dataset["officials"][0]["person_id"], 101)
        self.assertEqual(dataset["away"]["team_key"], "toronto-tempo")
        self.assertEqual(dataset["home"]["team_key"], "seattle-storm")

    def test_empty_officials_are_explicitly_unavailable(self):
        self.mock_request.return_value = (summary_payload(officials=False), "x", False)
        dataset = m.get_game_officials_dataset("1022600204", 2026)
        self.assertFalse(dataset["officials_available"])
        self.assertEqual(
            dataset["assignment_status"],
            "not_available_from_official_box_score_summary",
        )

    def test_duplicate_official_person_ids_fail_closed(self):
        self.mock_request.return_value = (summary_payload(duplicate=True), "x", False)
        with self.assertRaisesRegex(m.WNBAOfficiatingUpstreamError, "duplicate official"):
            m.get_game_officials_dataset("1022600204", 2026)

    def test_mismatched_game_id_fails_closed(self):
        self.mock_request.return_value = (summary_payload(mismatch=True), "x", False)
        with self.assertRaisesRegex(m.WNBAOfficiatingUpstreamError, "expected"):
            m.get_game_officials_dataset("1022600204", 2026)

    def test_unmapped_summary_team_fails_closed(self):
        payload = summary_payload()
        payload["boxScoreSummary"]["awayTeam"] = {
            "teamId": 999,
            "teamCity": "Mystery",
            "teamName": "Mystery",
            "teamTricode": "ZZZ",
            "teamSlug": "mystery",
        }
        self.mock_request.return_value = (payload, "x", False)
        with self.assertRaisesRegex(m.WNBAOfficiatingUpstreamError, "unmapped team"):
            m.get_game_officials_dataset("1022600204", 2026)

    def test_team_profile_observed_rates(self):
        dataset = m.get_team_foul_ft_context("seattle-storm", 2026)
        derived = dataset["profile"]["derived_observed"]
        self.assertEqual(derived["free_throw_attempt_rate_per_fga"], round(22 / 70, 4))
        self.assertEqual(derived["fouls_drawn_minus_committed"], 2.0)
        self.assertEqual(
            dataset["league_context"]["free_throws_attempted_per_game"]["higher_value_rank"],
            2,
        )

    def test_team_rank_is_not_labeled_quality(self):
        dataset = m.get_team_foul_ft_context("seattle-storm", 2026)
        self.assertTrue(dataset["verification"]["higher_value_rank_is_not_a_quality_rank"])

    def test_unknown_team_fails_before_stats(self):
        with self.assertRaises(m.WNBAOfficiatingNotFoundError):
            m.get_team_foul_ft_context("not-a-team", 2026)
        self.mock_team_stats.assert_not_called()

    def test_player_per36_rates(self):
        dataset = m.get_player_foul_ft_context(99, 2026)
        derived = dataset["rows"][0]["profile"]["derived_observed"]
        self.assertEqual(derived["free_throw_attempts_per_36_minutes"], 6.0)
        self.assertEqual(derived["fouls_drawn_per_36_minutes"], 3.6)

    def test_multiple_player_rows_are_preserved(self):
        self.mock_player_stats.return_value = player_dataset(multiple=True)
        dataset = m.get_player_foul_ft_context(99, 2026)
        self.assertEqual(dataset["official_row_count"], 2)
        self.assertEqual(
            dataset["aggregation_status"],
            "multiple_official_rows_preserved_no_guess",
        )

    def test_missing_player_raises_not_found(self):
        empty = player_dataset()
        empty["players"] = []
        self.mock_player_stats.return_value = empty
        with self.assertRaises(m.WNBAOfficiatingNotFoundError):
            m.get_player_foul_ft_context(99, 2026)

    def test_invalid_last_n_fails_before_stats(self):
        with self.assertRaisesRegex(ValueError, "0 through 100"):
            m.get_team_foul_ft_context("seattle-storm", 2026, last_n_games=101)
        self.mock_team_stats.assert_not_called()

    def test_game_whistle_context_combines_observed_team_rates(self):
        dataset = m.get_game_whistle_context("1022600204", 2026)
        combined = dataset["combined_observed_team_rates"]
        self.assertEqual(combined["sum_free_throw_attempts_per_game"], 40.0)
        self.assertEqual(combined["sum_personal_fouls_per_game"], 37.0)
        self.assertTrue(dataset["verification"]["combined_rates_are_not_expected_game_totals"])
        self.assertFalse(dataset["verification"]["historical_referee_tendencies_included"])

    def test_wrong_summary_schema_fails_closed(self):
        self.mock_request.return_value = ({"wrong": {}}, "x", False)
        with self.assertRaisesRegex(m.WNBAOfficiatingUpstreamError, "missing boxScoreSummary"):
            m.get_game_officials_dataset("1022600204", 2026)


if __name__ == "__main__":
    unittest.main()
