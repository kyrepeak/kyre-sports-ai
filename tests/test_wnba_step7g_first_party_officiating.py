from __future__ import annotations

import unittest

from sports_api import wnba_officiating_context as frozen
from sports_api import wnba_step7g_first_party_officiating as fp


class Step7GFirstPartyOfficiatingTests(unittest.TestCase):
    def test_normalize_official_rows_preserves_frozen_identity_shape(self) -> None:
        rows = fp._normalize_official_rows(
            [
                {
                    "personId": 1629176,
                    "name": "Angel Kent",
                    "nameI": "A. Kent",
                    "firstName": "Angel",
                    "familyName": "Kent",
                    "jerseyNum": "26",
                    "assignment": "OFFICIAL1",
                },
                {
                    "personId": 1629764,
                    "name": "Ken Jones",
                    "nameI": "K. Jones",
                    "firstName": "Ken",
                    "familyName": "Jones",
                    "jerseyNum": "36",
                    "assignment": "OFFICIAL3",
                },
            ],
            "1022600290",
        )
        self.assertEqual(
            rows,
            [
                {
                    "person_id": 1629176,
                    "name": "Angel Kent",
                    "name_initial": "A. Kent",
                    "first_name": "Angel",
                    "family_name": "Kent",
                    "jersey_number": "26",
                },
                {
                    "person_id": 1629764,
                    "name": "Ken Jones",
                    "name_initial": "K. Jones",
                    "first_name": "Ken",
                    "family_name": "Jones",
                    "jersey_number": "36",
                },
            ],
        )

    def test_duplicate_official_person_id_fails_closed(self) -> None:
        with self.assertRaises(frozen.WNBAOfficiatingUpstreamError):
            fp._normalize_official_rows(
                [
                    {"personId": 77, "name": "Official One"},
                    {"personId": 77, "name": "Official Two"},
                ],
                "1022600290",
            )

    def test_empty_official_assignment_uses_frozen_not_found_family(self) -> None:
        with self.assertRaises(frozen.WNBAOfficiatingNotFoundError):
            fp._normalize_official_rows([], "1022600290")

    def test_current_page_schedule_team_mismatch_fails_closed(self) -> None:
        schedule_game = {
            "game_id": "1022600290",
            "away": {"team_key": "washington-mystics", "official_team_id": 1},
            "home": {"team_key": "phoenix-mercury", "official_team_id": 2},
        }
        box = {
            "game_id": "1022600290",
            "away": {"team_key": "washington-mystics", "official_team_id": 1},
            "home": {"team_key": "seattle-storm", "official_team_id": 2},
        }
        with self.assertRaises(frozen.WNBAOfficiatingUpstreamError):
            fp._validate_current_page_identity(schedule_game, box)

    def test_game_stat_row_derives_pfd_only_from_opponent_pf_and_normalizes_minutes(self) -> None:
        pair = (
            {
                "team_key": "washington-mystics",
                "stats": {
                    "minutes": 200.0,
                    "field_goals_attempted": 70,
                    "free_throws_made": 17,
                    "free_throws_attempted": 20,
                    "personal_fouls": 15,
                    "points": 83,
                },
            },
            {
                "team_key": "phoenix-mercury",
                "stats": {
                    "minutes": 200.0,
                    "field_goals_attempted": 74,
                    "free_throws_made": 20,
                    "free_throws_attempted": 24,
                    "personal_fouls": 19,
                    "points": 88,
                },
            },
        )
        row = fp._game_stat_row("washington-mystics", "1022600001", pair)
        self.assertEqual(row["personal_fouls_drawn"], 19.0)
        self.assertEqual(row["personal_fouls"], 15.0)
        self.assertEqual(row["minutes"], 40.0)

    def test_profile_stats_uses_aggregate_weighted_free_throw_percentage(self) -> None:
        rows = [
            {
                "minutes": 40.0,
                "field_goals_attempted": 70.0,
                "free_throws_made": 5.0,
                "free_throws_attempted": 10.0,
                "personal_fouls": 14.0,
                "personal_fouls_drawn": 18.0,
                "points": 80.0,
            },
            {
                "minutes": 45.0,
                "field_goals_attempted": 80.0,
                "free_throws_made": 18.0,
                "free_throws_attempted": 20.0,
                "personal_fouls": 20.0,
                "personal_fouls_drawn": 16.0,
                "points": 95.0,
            },
        ]
        stats = fp._profile_stats(rows)
        self.assertEqual(stats["minutes"], 42.5)
        self.assertEqual(stats["free_throws_attempted"], 15.0)
        self.assertEqual(stats["free_throw_percentage"], round(23 / 30, 4))
        self.assertEqual(stats["personal_fouls_drawn"], 17.0)

    def test_team_context_preserves_frozen_profile_and_league_measure_semantics(self) -> None:
        league = {
            "source": "synthetic official",
            "source_url": "https://www.wnba.com/",
            "source_endpoint": "synthetic",
            "season": 2026,
            "season_type": "Regular Season",
            "last_n_games": 5,
            "window_scope": "last_5_games",
            "retrieved_at_utc": "2026-08-28T00:00:00+00:00",
            "teams": [
                {
                    "official_team_id": 1,
                    "team_key": "washington-mystics",
                    "team_full_name": "Washington Mystics",
                    "team_abbreviation": "WAS",
                    "games_played": 5,
                    "selected_game_ids": [f"102260000{i}" for i in range(1, 6)],
                    "stats": {
                        "minutes": 40.0,
                        "field_goals_attempted": 70.0,
                        "free_throws_made": 16.0,
                        "free_throws_attempted": 20.0,
                        "free_throw_percentage": 0.8,
                        "personal_fouls": 15.0,
                        "personal_fouls_drawn": 18.0,
                        "points": 82.0,
                    },
                },
                {
                    "official_team_id": 2,
                    "team_key": "phoenix-mercury",
                    "team_full_name": "Phoenix Mercury",
                    "team_abbreviation": "PHX",
                    "games_played": 5,
                    "selected_game_ids": [f"102260001{i}" for i in range(1, 6)],
                    "stats": {
                        "minutes": 40.0,
                        "field_goals_attempted": 75.0,
                        "free_throws_made": 20.0,
                        "free_throws_attempted": 25.0,
                        "free_throw_percentage": 0.8,
                        "personal_fouls": 19.0,
                        "personal_fouls_drawn": 17.0,
                        "points": 90.0,
                    },
                },
            ],
        }
        context = fp._team_context(league, "washington-mystics", cache_hit=False)
        self.assertEqual(context["profile"]["free_throws_attempted"], 20.0)
        self.assertEqual(
            context["league_context"]["free_throws_attempted_per_game"],
            {
                "value": 20.0,
                "league_average": 22.5,
                "higher_value_rank": 2,
                "league_team_count": 2,
            },
        )
        self.assertTrue(
            context["verification"][
                "personal_fouls_drawn_equals_paired_opponent_personal_fouls"
            ]
        )
        self.assertFalse(context["verification"]["third_party_sources_used"])

    def test_unsupported_scope_fails_closed(self) -> None:
        with self.assertRaises(frozen.WNBAOfficiatingUpstreamError):
            fp._validate_scope(2025, "Regular Season", 5)
        with self.assertRaises(frozen.WNBAOfficiatingUpstreamError):
            fp._validate_scope(2026, "Regular Season", 0)
        with self.assertRaises(frozen.WNBAOfficiatingUpstreamError):
            fp._validate_scope(2026, "Regular Season", 21)


if __name__ == "__main__":
    unittest.main(verbosity=2)
