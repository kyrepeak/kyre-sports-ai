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


def _shot_row(*, player_id=PLAYER_ID, player_name="S. Citron"):
    return {
        "game_id": "1022600280",
        "game_event_id": 101,
        "game_id_valid": True,
        "player_id": player_id,
        "player_name": player_name,
        "team_key": "washington-mystics",
        "mapped_to_registry": True,
        "canonical_zone": "above_the_break_3",
        "shot_zone_basic": "Above the Break 3",
        "attempted": True,
        "made": False,
        "points_scored": 0,
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
        self.assertFalse(evidence[0]["display_name_used_for_identity"])

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

    def test_same_player_id_different_display_labels_are_audit_only(self):
        game = _game()
        schedule = {
            "retrieved_at_utc": "2026-08-27T20:00:00+00:00",
            "cache_hit": False,
            "games": [game],
        }
        with (
            patch.object(base, "_schedule", return_value=(schedule, {game["game_id"]: game})),
            patch.object(
                safe,
                "_selected_recent_games_box_verified",
                return_value=([game], "Sonia Citron", [{"game_id": game["game_id"]}]),
            ),
            patch.object(
                base,
                "_player_shots_from_games",
                return_value=([_shot_row(player_name="S. Citron")], ["https://www.wnba.com/game/test"]),
            ),
        ):
            result = safe.get_first_party_player_shot_chart_dataset(
                PLAYER_ID, SEASON, last_n_games=1
            )
        self.assertEqual(result["player_id"], PLAYER_ID)
        self.assertEqual(result["player_name"], "Sonia Citron")
        self.assertEqual(
            result["display_name_audit"]["play_by_play_player_name_labels"],
            ["S. Citron"],
        )
        self.assertFalse(result["display_name_audit"]["labels_match_exactly"])
        self.assertFalse(result["display_name_audit"]["labels_used_for_identity"])
        self.assertTrue(result["verification"]["numeric_player_id_authoritative"])
        self.assertFalse(result["verification"]["display_name_labels_used_for_identity"])

    def test_numeric_player_id_conflict_still_fails_in_shot_normalizer(self):
        game = _game()
        action = {
            "event_category": "shot",
            "person_id": PLAYER_ID + 1,
            "team_key": "washington-mystics",
            "shot_result": "Missed",
            "action_type": "2pt",
            "sub_type": "Jump Shot",
            "description": "Other Player 12' Jump Shot",
            "action_number": 7,
            "period": 1,
            "clock_seconds_remaining": 500,
            "x_legacy": 80,
            "y_legacy": 80,
            "shot_distance_feet": 12,
        }
        with self.assertRaises(WNBAShotContextUpstreamError):
            base._normalize_shot(action, game, expected_player_id=PLAYER_ID)


if __name__ == "__main__":
    unittest.main(verbosity=2)
