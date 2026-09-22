from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from sports_api.wnba_step8_official_box_baseline import (
    BASELINE_RELEASE_ID,
    WNBAStep8OfficialBoxBaselineNotFoundError,
    WNBAStep8OfficialBoxBaselineUpstreamError,
    build_step8_official_box_baseline,
)

PLAYER_ID = 1642291
CURRENT_GAME_ID = "1022600291"
GAME_IDS = [f"1022600{value:03d}" for value in (283, 276, 270, 264, 258)]
TEAM_KEY = "atlanta-dream"
TEAM_ID = 1611661330
OPP_KEY = "portland-fire"
OPP_ID = 1611661337
MINUTES = [30.0, 32.0, 34.0, 36.0, 38.0]
POINTS = [10, 12, 14, 16, 18]
REBOUNDS = [8, 9, 10, 11, 12]
ASSISTS = [1, 2, 3, 4, 5]


def _handoff() -> dict:
    evidence = [
        {
            "game_id": gid,
            "player_resolved_once": True,
            "player_id": PLAYER_ID,
            "player_side": "home",
            "player_team_key": TEAM_KEY,
            "player_official_team_id": TEAM_ID,
            "box_schedule_identity_match": True,
        }
        for gid in GAME_IDS
    ]
    advanced = {
        "data_type": "official_advanced_player_stats",
        "season": 2026,
        "season_type": "Regular Season",
        "last_n_games": 5,
        "filters": {"team_key": None, "player_id": PLAYER_ID},
        "selected_game_ids": list(GAME_IDS),
        "identity_evidence": evidence,
        "players": [
            {
                "player_id": PLAYER_ID,
                "player_name": "Synthetic Player",
                "team_key": TEAM_KEY,
                "minutes": 34.0,
                "advanced": {"estimated_usage_percentage": 0.2},
            }
        ],
        "verification": {
            "all_selected_games_final": True,
            "all_selected_game_ids_certified_regular_season": True,
            "box_schedule_identity_cross_checked": True,
            "third_party_sources_used": False,
        },
    }
    snapshot = {
        "player_id": PLAYER_ID,
        "game_id": CURRENT_GAME_ID,
        "season": 2026,
        "season_type": "Regular Season",
        "recent_window_games": 5,
        "focal_identity": {
            "player_id": PLAYER_ID,
            "team_key": TEAM_KEY,
            "opponent_team_key": OPP_KEY,
            "side": "home",
        },
        "inputs": {"player_advanced": advanced},
    }
    return {
        "data_type": "certified_pre_projection_model_handoff",
        "schema_version": "wnba_step_8a_v1",
        "handoff_release_id": "wnba_step8_projection_handoff_2026_regular_season_v1",
        "handoff_id": "wnba-8a-synthetic",
        "handoff_content_sha256": "a" * 64,
        "projection_execution_authorized": True,
        "production_activation_allowed": False,
        "snapshot_reference": {
            "player_id": PLAYER_ID,
            "game_id": CURRENT_GAME_ID,
            "snapshot_id": "wnba-4w-synthetic",
            "content_sha256": "b" * 64,
        },
        "snapshot": snapshot,
    }


def _player(minutes: float, points: int, rebounds: int, assists: int) -> dict:
    return {
        "player_id": PLAYER_ID,
        "full_name": "Synthetic Player",
        "team_key": TEAM_KEY,
        "official_team_id": TEAM_ID,
        "appeared": True,
        "stats": {
            "minutes": minutes,
            "points": points,
            "rebounds": rebounds,
            "assists": assists,
            "field_goals_attempted": 10,
            "free_throws_attempted": 4,
            "turnovers": 2,
        },
    }


def _box(game_id: str) -> dict:
    idx = GAME_IDS.index(game_id)
    return {
        "data_type": "official_traditional_box_score",
        "game_id": game_id,
        "home": {
            "team_key": TEAM_KEY,
            "official_team_id": TEAM_ID,
            "players": [_player(MINUTES[idx], POINTS[idx], REBOUNDS[idx], ASSISTS[idx])],
        },
        "away": {
            "team_key": OPP_KEY,
            "official_team_id": OPP_ID,
            "players": [],
        },
        "verification": {
            "requested_game_id_matches_source": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
            "player_ids_unique": True,
        },
    }


def _fetch(game_id: str, season: int) -> dict:
    assert season == 2026
    return deepcopy(_box(game_id))


class Step8OfficialBoxBaselineTests(unittest.TestCase):
    def _build(self, handoff: dict | None = None) -> dict:
        with patch(
            "sports_api.wnba_step8_official_box_baseline.get_first_party_game_box_score_dataset",
            side_effect=_fetch,
        ):
            return build_step8_official_box_baseline(_handoff() if handoff is None else handoff)

    def test_happy_path_uses_exact_official_box_counts(self) -> None:
        result = self._build()
        self.assertEqual(result["baseline_release_id"], BASELINE_RELEASE_ID)
        self.assertEqual(result["selected_game_ids"], GAME_IDS)
        self.assertEqual(result["summary"]["totals"]["points"], sum(POINTS))
        self.assertEqual(result["summary"]["totals"]["rebounds"], sum(REBOUNDS))
        self.assertEqual(result["summary"]["totals"]["assists"], sum(ASSISTS))
        self.assertEqual(result["summary"]["minutes"]["mean"], 34.0)
        self.assertAlmostEqual(result["summary"]["official_per_minute_rates"]["assists"], sum(ASSISTS) / sum(MINUTES), places=8)
        self.assertTrue(result["semantics"]["points_rebounds_assists_are_complete_official_box_counts"])
        self.assertTrue(result["semantics"]["pbp_feature_counts_are_not_used_as_official_box_totals"])
        self.assertTrue(result["guardrails"]["baseline_is_observed_history_not_projection"])
        self.assertTrue(result["verification"]["no_projection_created"])

    def test_duplicate_selected_game_id_fails_closed(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_advanced"]["selected_game_ids"][-1] = GAME_IDS[0]
        with self.assertRaises(WNBAStep8OfficialBoxBaselineUpstreamError):
            self._build(handoff)

    def test_non_regular_game_family_fails_closed(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_advanced"]["selected_game_ids"][-1] = "1052600001"
        with self.assertRaises(WNBAStep8OfficialBoxBaselineUpstreamError):
            self._build(handoff)

    def test_duplicate_player_identity_in_box_fails_closed(self) -> None:
        bad = _box(GAME_IDS[0])
        bad["away"]["players"].append(deepcopy(bad["home"]["players"][0]))
        def fetch(game_id: str, season: int) -> dict:
            return deepcopy(bad if game_id == GAME_IDS[0] else _box(game_id))
        with patch(
            "sports_api.wnba_step8_official_box_baseline.get_first_party_game_box_score_dataset",
            side_effect=fetch,
        ):
            with self.assertRaises(WNBAStep8OfficialBoxBaselineNotFoundError):
                build_step8_official_box_baseline(_handoff())

    def test_box_team_mismatch_with_handoff_evidence_fails_closed(self) -> None:
        bad = _box(GAME_IDS[0])
        bad["home"]["players"][0]["team_key"] = "wrong-team"
        def fetch(game_id: str, season: int) -> dict:
            return deepcopy(bad if game_id == GAME_IDS[0] else _box(game_id))
        with patch(
            "sports_api.wnba_step8_official_box_baseline.get_first_party_game_box_score_dataset",
            side_effect=fetch,
        ):
            with self.assertRaises(WNBAStep8OfficialBoxBaselineUpstreamError):
                build_step8_official_box_baseline(_handoff())

    def test_box_side_mismatch_with_handoff_evidence_fails_closed(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_advanced"]["identity_evidence"][0]["player_side"] = "away"
        with self.assertRaises(WNBAStep8OfficialBoxBaselineUpstreamError):
            self._build(handoff)

    def test_dnp_row_fails_closed(self) -> None:
        bad = _box(GAME_IDS[0])
        bad["home"]["players"][0]["appeared"] = False
        def fetch(game_id: str, season: int) -> dict:
            return deepcopy(bad if game_id == GAME_IDS[0] else _box(game_id))
        with patch(
            "sports_api.wnba_step8_official_box_baseline.get_first_party_game_box_score_dataset",
            side_effect=fetch,
        ):
            with self.assertRaises(WNBAStep8OfficialBoxBaselineNotFoundError):
                build_step8_official_box_baseline(_handoff())

    def test_advanced_average_minutes_mismatch_fails_closed(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_advanced"]["players"][0]["minutes"] = 33.0
        with self.assertRaises(WNBAStep8OfficialBoxBaselineUpstreamError):
            self._build(handoff)

    def test_most_recent_team_must_match_current_focal_team(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["focal_identity"]["team_key"] = "different-current-team"
        with self.assertRaises(WNBAStep8OfficialBoxBaselineUpstreamError):
            self._build(handoff)

    def test_handoff_must_be_projection_authorized(self) -> None:
        handoff = _handoff()
        handoff["projection_execution_authorized"] = False
        with self.assertRaises(WNBAStep8OfficialBoxBaselineNotFoundError):
            self._build(handoff)


if __name__ == "__main__":
    unittest.main(verbosity=2)
