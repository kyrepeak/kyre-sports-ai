from __future__ import annotations

import unittest
from unittest.mock import patch

import sports_api.wnba_step7g_first_party_shot_context as base
import sports_api.wnba_step7g_first_party_shot_context_identity_safe as safe
from sports_api.wnba_shot_context import WNBAShotContextUpstreamError

PLAYER_ID = 1642785
SEASON = 2026


def _team(team_key: str, team_id: int, tri: str, players=None):
    return {
        "official_team_id": team_id,
        "team_key": team_key,
        "full_name": team_key.replace("-", " ").title(),
        "team_name": team_key.split("-")[-1].title(),
        "team_tricode": tri,
        "players": players or [],
        "mapped_to_registry": True,
    }


def _game():
    return {
        "game_id": "1022600280",
        "official_schedule_date": "2026-08-23",
        "game_datetime_utc": "2026-08-24T00:00:00+00:00",
        "status": {"category": "final"},
        "away": _team("washington-mystics", 1611661322, "WAS"),
        "home": _team("phoenix-mercury", 1611661317, "PHX"),
        "verification": {
            "game_id_valid": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
        },
    }


def _history_with_bad_display_matchup():
    return {
        "games": [{
            "player_id": PLAYER_ID,
            "game_id": "1022600280",
            "matchup": {
                "team_key": "washington-mystics",
                "opponent_team_key": "new-york-liberty",
            },
        }]
    }


def _box(player_team_key="washington-mystics"):
    player = {
        "player_id": PLAYER_ID,
        "full_name": "Sonia Citron",
        "appeared": True,
    }
    away_players = [player] if player_team_key == "washington-mystics" else []
    home_players = [player] if player_team_key == "phoenix-mercury" else []
    return {
        "game_id": "1022600280",
        "away": _team("washington-mystics", 1611661322, "WAS", away_players),
        "home": _team("phoenix-mercury", 1611661317, "PHX", home_players),
    }


class Step7GShotIdentitySafeTests(unittest.TestCase):
    def test_bad_display_matchup_does_not_override_box_schedule_identity(self):
        game = _game()
        with (
            patch.object(base, "get_first_party_player_recent_game_log_dataset", return_value=_history_with_bad_display_matchup()),
            patch.object(safe, "get_first_party_game_box_score_dataset", return_value=_box()),
        ):
            games, name, evidence = safe._selected_recent_games_box_verified(
                PLAYER_ID, SEASON, 1, {game["game_id"]: game}
            )
        self.assertEqual([row["game_id"] for row in games], [game["game_id"]])
        self.assertEqual(name, "Sonia Citron")
        self.assertEqual(evidence[0]["player_team_key"], "washington-mystics")
        self.assertTrue(evidence[0]["player_resolved_once"])

    def test_box_schedule_team_disagreement_fails_closed(self):
        game = _game()
        bad_box = _box()
        bad_box["home"]["team_key"] = "new-york-liberty"
        with (
            patch.object(base, "get_first_party_player_recent_game_log_dataset", return_value=_history_with_bad_display_matchup()),
            patch.object(safe, "get_first_party_game_box_score_dataset", return_value=bad_box),
        ):
            with self.assertRaises(WNBAShotContextUpstreamError):
                safe._selected_recent_games_box_verified(
                    PLAYER_ID, SEASON, 1, {game["game_id"]: game}
                )

    def test_player_must_resolve_to_exactly_one_box_team(self):
        game = _game()
        duplicate = _box()
        duplicate["home"]["players"] = [dict(duplicate["away"]["players"][0])]
        with (
            patch.object(base, "get_first_party_player_recent_game_log_dataset", return_value=_history_with_bad_display_matchup()),
            patch.object(safe, "get_first_party_game_box_score_dataset", return_value=duplicate),
        ):
            with self.assertRaises(WNBAShotContextUpstreamError):
                safe._selected_recent_games_box_verified(
                    PLAYER_ID, SEASON, 1, {game["game_id"]: game}
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
