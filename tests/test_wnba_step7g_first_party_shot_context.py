from __future__ import annotations

import unittest
from unittest.mock import patch

import sports_api.wnba_step7g_first_party_shot_context as shot
from sports_api.wnba_shot_context import (
    WNBAShotContextNotFoundError,
    WNBAShotContextUpstreamError,
)


PLAYER_ID = 1642785
SEASON = 2026


def _side(team_key: str, team_id: int, tricode: str) -> dict:
    return {
        "official_team_id": team_id,
        "team_key": team_key,
        "full_name": team_key.replace("-", " ").title(),
        "team_name": team_key.split("-")[-1].title(),
        "team_tricode": tricode,
        "mapped_to_registry": True,
    }


def _game(
    game_id: str,
    date: str,
    away_key: str,
    away_id: int,
    away_tri: str,
    home_key: str,
    home_id: int,
    home_tri: str,
    *,
    status: str = "final",
) -> dict:
    return {
        "game_id": game_id,
        "official_schedule_date": date,
        "game_datetime_utc": f"{date}T23:00:00+00:00",
        "status": {"category": status},
        "away": _side(away_key, away_id, away_tri),
        "home": _side(home_key, home_id, home_tri),
        "verification": {
            "game_id_valid": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
        },
    }


def _action(
    number: int,
    player_id: int,
    team_key: str,
    *,
    description: str,
    result: str = "Missed",
    distance: float = 0.0,
    x: float = 0.0,
    y: float = 0.0,
) -> dict:
    return {
        "action_number": number,
        "action_id": str(number),
        "period": 1,
        "clock_seconds_remaining": 500.0,
        "team_key": team_key,
        "person_id": player_id,
        "player_name": "Sonia Citron" if player_id == PLAYER_ID else "Other Player",
        "description": description,
        "action_type": "Made Shot" if result == "Made" else "Missed Shot",
        "sub_type": "Jump Shot",
        "event_category": "shot",
        "shot_result": result,
        "shot_distance_feet": distance,
        "x_legacy": x,
        "y_legacy": y,
        "points_scored_on_action": 3 if result == "Made" and "3PT" in description else (2 if result == "Made" else 0),
    }


class Step7GFirstPartyShotContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.g1 = _game(
            "1022600101",
            "2026-08-20",
            "washington-mystics",
            1611661322,
            "WAS",
            "phoenix-mercury",
            1611661317,
            "PHX",
        )
        self.g2 = _game(
            "1022600102",
            "2026-08-21",
            "new-york-liberty",
            1611661313,
            "NYL",
            "washington-mystics",
            1611661322,
            "WAS",
        )
        self.cup = _game(
            "1052600001",
            "2026-06-30",
            "washington-mystics",
            1611661322,
            "WAS",
            "phoenix-mercury",
            1611661317,
            "PHX",
        )
        self.schedule = {
            "retrieved_at_utc": "2026-08-27T20:00:00+00:00",
            "cache_hit": False,
            "games": [self.cup, self.g1, self.g2],
        }
        self.history = {
            "games": [
                {
                    "player_id": PLAYER_ID,
                    "game_id": self.g2["game_id"],
                    "matchup": {
                        "team_key": "washington-mystics",
                        "opponent_team_key": "new-york-liberty",
                    },
                },
                {
                    "player_id": PLAYER_ID,
                    "game_id": self.g1["game_id"],
                    "matchup": {
                        "team_key": "washington-mystics",
                        "opponent_team_key": "phoenix-mercury",
                    },
                },
            ]
        }
        self.roster = {
            "players": [
                {
                    "player_id": PLAYER_ID,
                    "full_name": "Sonia Citron",
                    "team_key": "washington-mystics",
                }
            ]
        }
        self.actions = {
            self.g1["game_id"]: [
                _action(
                    1,
                    PLAYER_ID,
                    "washington-mystics",
                    description="Citron 3PT Jump Shot",
                    result="Made",
                    distance=0,
                    x=-229,
                    y=19,
                ),
                _action(
                    2,
                    999,
                    "phoenix-mercury",
                    description="Other 10' Jump Shot",
                    result="Missed",
                    distance=10,
                    x=51,
                    y=89,
                ),
            ],
            self.g2["game_id"]: [
                _action(
                    3,
                    PLAYER_ID,
                    "washington-mystics",
                    description="Citron 16' Pullup Jump Shot",
                    result="Missed",
                    distance=16,
                    x=120,
                    y=100,
                )
            ],
        }

    def _pbp(self, game_id: str, season: int, **kwargs):
        return {
            "source_url": f"https://www.wnba.com/game/{game_id}",
            "actions": self.actions.get(game_id, []),
        }

    def _patch_sources(self):
        return (
            patch.object(shot, "get_step7g_step4n_season_schedule_dataset", return_value=self.schedule),
            patch.object(shot, "get_first_party_player_recent_game_log_dataset", return_value=self.history),
            patch.object(shot, "get_first_party_current_players_dataset", return_value=self.roster),
            patch.object(shot, "get_first_party_play_by_play_dataset", side_effect=self._pbp),
        )

    def test_zero_distance_description_three_is_left_corner_three(self) -> None:
        action = _action(
            1,
            PLAYER_ID,
            "washington-mystics",
            description="MISS Citron 3PT Jump Shot",
            distance=0,
            x=-229,
            y=19,
        )
        key, area, range_label = shot.classify_official_shot_zone(action)
        self.assertEqual(key, "left_corner_3")
        self.assertEqual(area, "Left Side(L)")
        self.assertEqual(range_label, "16-24 ft.")

    def test_above_break_three_uses_official_geometry(self) -> None:
        action = _action(
            1,
            PLAYER_ID,
            "washington-mystics",
            description="Citron 3PT Jump Shot",
            distance=0,
            x=-122,
            y=200,
        )
        self.assertEqual(shot.classify_official_shot_zone(action)[0], "above_the_break_3")

    def test_restricted_paint_midrange_and_backcourt_classification(self) -> None:
        restricted = _action(1, PLAYER_ID, "washington-mystics", description="Layup", distance=3, x=20, y=20)
        paint = _action(2, PLAYER_ID, "washington-mystics", description="Floater", distance=10, x=51, y=89)
        mid = _action(3, PLAYER_ID, "washington-mystics", description="Jumper", distance=18, x=120, y=120)
        backcourt = _action(4, PLAYER_ID, "washington-mystics", description="Heave", distance=50, x=0, y=500)
        self.assertEqual(shot.classify_official_shot_zone(restricted)[0], "restricted_area")
        self.assertEqual(shot.classify_official_shot_zone(paint)[0], "paint_non_ra")
        self.assertEqual(shot.classify_official_shot_zone(mid)[0], "mid_range")
        self.assertEqual(shot.classify_official_shot_zone(backcourt)[0], "backcourt")

    def test_recent_player_chart_uses_exact_latest_regular_game_window(self) -> None:
        patches = self._patch_sources()
        with patches[0], patches[1], patches[2], patches[3]:
            result = shot.get_first_party_player_shot_chart_dataset(
                PLAYER_ID, SEASON, last_n_games=1
            )
        self.assertEqual(result["selected_game_ids"], [self.g2["game_id"]])
        self.assertEqual(result["shot_count"], 1)
        self.assertEqual(result["shots"][0]["player_id"], PLAYER_ID)
        self.assertEqual(result["shots"][0]["game_date"], "2026-08-21")
        self.assertTrue(result["verification"]["shot_event_keys_unique"])

    def test_season_to_date_player_chart_without_opponent_fails_closed(self) -> None:
        patches = self._patch_sources()
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(WNBAShotContextNotFoundError):
                shot.get_first_party_player_shot_chart_dataset(
                    PLAYER_ID, SEASON, last_n_games=0
                )

    def test_h2h_chart_excludes_exact_cup_non_regular_game(self) -> None:
        patches = self._patch_sources()
        with patches[0], patches[1], patches[2], patches[3]:
            result = shot.get_first_party_player_shot_chart_dataset(
                PLAYER_ID,
                SEASON,
                last_n_games=0,
                opponent_team_key="phoenix-mercury",
            )
        self.assertEqual(result["selected_game_ids"], [self.g1["game_id"]])
        self.assertNotIn(self.cup["game_id"], result["selected_game_ids"])
        self.assertEqual(result["shots"][0]["canonical_zone"], "left_corner_3")

    def test_opponent_defense_aggregates_only_opponent_shots(self) -> None:
        patches = self._patch_sources()
        with patches[0], patches[1], patches[2], patches[3]:
            result = shot.get_first_party_opponent_defense_by_shot_zone_dataset(
                "phoenix-mercury", SEASON, last_n_games=1
            )
        self.assertEqual(result["selected_game_ids"], [self.g1["game_id"]])
        self.assertEqual(result["opponent_shooting_team_count"], 1)
        row = result["opponent_shooting_rows"][0]
        self.assertEqual(row["team_key"], "washington-mystics")
        self.assertTrue(result["verification"]["all_opponent_rows_mapped_to_registry"])

    def test_duplicate_game_event_keys_fail_closed(self) -> None:
        row = {
            "game_id": "1022600101",
            "game_event_id": 7,
            "game_id_valid": True,
            "mapped_to_registry": True,
        }
        with self.assertRaises(WNBAShotContextUpstreamError):
            shot._validate_shot_keys([dict(row), dict(row)])

    def test_action_team_must_match_scheduled_participant(self) -> None:
        bad = _action(
            1,
            PLAYER_ID,
            "seattle-storm",
            description="Citron 10' Jump Shot",
            distance=10,
            x=50,
            y=80,
        )
        with self.assertRaises(WNBAShotContextUpstreamError):
            shot._normalize_shot(bad, self.g1, expected_player_id=PLAYER_ID)

    def test_current_roster_player_identity_must_be_unique(self) -> None:
        duplicate_roster = {
            "players": [
                {"player_id": PLAYER_ID, "team_key": "washington-mystics"},
                {"player_id": PLAYER_ID, "team_key": "phoenix-mercury"},
            ]
        }
        with patch.object(shot, "get_first_party_current_players_dataset", return_value=duplicate_roster):
            with self.assertRaises(WNBAShotContextNotFoundError):
                shot._current_player_team(PLAYER_ID, SEASON)


if __name__ == "__main__":
    unittest.main(verbosity=2)
