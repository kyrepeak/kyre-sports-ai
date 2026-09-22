from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from sports_api.wnba_step8_core_projection import (
    MODEL_VERSION,
    WNBAStep8CoreProjectionDisabledError,
    WNBAStep8CoreProjectionNotReadyError,
    WNBAStep8CoreProjectionUpstreamError,
    build_step8_core_projection,
    get_player_game_step8_core_projection,
    recompute_step8_official_box_baseline_content_sha256,
    step8_core_projection_enabled,
)

PLAYER_ID = 1642291
GAME_ID = "1022600291"
TEAM_KEY = "atlanta-dream"
OPP_KEY = "portland-fire"
GAME_IDS = ["1022600283", "1022600277", "1022600271", "1022600266", "1022600261"]
HANDOFF_HASH = "a" * 64
SNAPSHOT_HASH = "b" * 64


def _handoff() -> dict:
    return {
        "data_type": "certified_pre_projection_model_handoff",
        "schema_version": "wnba_step_8a_v1",
        "handoff_release_id": "wnba_step8_projection_handoff_2026_regular_season_v1",
        "handoff_id": "wnba-8a-synthetic",
        "handoff_content_sha256": HANDOFF_HASH,
        "projection_execution_authorized": True,
        "production_activation_allowed": False,
        "snapshot_reference": {
            "snapshot_id": "wnba-4w-synthetic",
            "content_sha256": SNAPSHOT_HASH,
            "player_id": PLAYER_ID,
            "game_id": GAME_ID,
        },
        "snapshot": {
            "season": 2026,
            "season_type": "Regular Season",
            "recent_window_games": 5,
            "player_id": PLAYER_ID,
            "game_id": GAME_ID,
            "focal_identity": {
                "player_id": PLAYER_ID,
                "team_key": TEAM_KEY,
                "opponent_team_key": OPP_KEY,
                "side": "home",
            },
            "availability_summary": {
                "focal_player_current_roster_match": True,
                "focal_player_availability": {
                    "availability_class": "not_listed",
                    "listed_on_injury_report": False,
                    "availability_uncertain": False,
                    "availability_blocking": False,
                },
            },
            "inputs": {
                "player_opportunity_context": {
                    "observed_minutes_opportunity": {
                        "tracked_minutes": {
                            "stability": {
                                "rotation_game_count": 5,
                                "tracked_minutes_mean": 34.0,
                                "tracked_minutes_population_stddev": 2.8284,
                                "tracked_minutes_coefficient_of_variation": 0.083188,
                            }
                        }
                    }
                }
            },
        },
    }


def _summary(mean_minutes: float = 34.0) -> dict:
    total_minutes = mean_minutes * 5.0
    points_total = 70.0
    rebounds_total = 50.0
    assists_total = 15.0
    pra_total = points_total + rebounds_total + assists_total
    return {
        "game_count": 5,
        "minutes": {
            "mean": mean_minutes,
            "median": mean_minutes,
            "minimum": max(1.0, mean_minutes - 4.0),
            "maximum": mean_minutes + 4.0,
            "population_stddev": 2.8284,
        },
        "points": {"mean": 14.0, "median": 14.0, "minimum": 10.0, "maximum": 18.0, "population_stddev": 2.8284},
        "rebounds": {"mean": 10.0, "median": 10.0, "minimum": 8.0, "maximum": 12.0, "population_stddev": 1.4142},
        "assists": {"mean": 3.0, "median": 3.0, "minimum": 1.0, "maximum": 5.0, "population_stddev": 1.4142},
        "points_rebounds_assists": {"mean": 27.0, "median": 27.0, "minimum": 19.0, "maximum": 35.0, "population_stddev": 5.6569},
        "totals": {
            "minutes": total_minutes,
            "points": int(points_total),
            "rebounds": int(rebounds_total),
            "assists": int(assists_total),
            "points_rebounds_assists": int(pra_total),
        },
        "official_per_minute_rates": {
            "points": round(points_total / total_minutes, 8),
            "rebounds": round(rebounds_total / total_minutes, 8),
            "assists": round(assists_total / total_minutes, 8),
            "points_rebounds_assists": round(pra_total / total_minutes, 8),
        },
    }


def _baseline(mean_minutes: float = 34.0) -> dict:
    result = {
        "source": "synthetic",
        "data_type": "official_recent_player_box_stat_baseline",
        "schema_version": "wnba_step_8b_box_baseline_v1",
        "baseline_release_id": "wnba_step8b_official_recent_box_baseline_2026_regular_v1",
        "baseline_id": "wnba-8b-box-synthetic",
        "baseline_content_sha256": "",
        "season": 2026,
        "season_type": "Regular Season",
        "requested_game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "current_team_key": TEAM_KEY,
        "selected_game_ids": list(GAME_IDS),
        "games": [
            {
                "game_id": gid,
                "player_id": PLAYER_ID,
                "team_key": TEAM_KEY,
                "side": "home",
                "minutes": mean_minutes,
                "points": 14,
                "rebounds": 10,
                "assists": 3,
                "points_rebounds_assists": 27,
                "appeared": True,
                "handoff_identity_match": True,
            }
            for gid in GAME_IDS
        ],
        "summary": _summary(mean_minutes),
        "provenance": {
            "step8a_handoff_id": "wnba-8a-synthetic",
            "step8a_handoff_content_sha256": HANDOFF_HASH,
            "step4w_snapshot_id": "wnba-4w-synthetic",
            "step4w_snapshot_content_sha256": SNAPSHOT_HASH,
            "game_ids_from_certified_handoff_player_advanced": True,
            "boxes_reloaded_from_official_wnba_com": True,
        },
        "verification": {
            "step8a_handoff_identity_verified": True,
            "advanced_selected_game_ids_used_exactly": True,
            "all_game_ids_unique_certified_regular_family": True,
            "player_resolved_exactly_once_per_box": True,
            "box_player_team_identity_matches_handoff_evidence": True,
            "advanced_and_box_average_minutes_match": True,
            "most_recent_team_matches_current_focal_team": True,
            "third_party_sources_used": False,
            "no_projection_created": True,
        },
    }
    result["baseline_content_sha256"] = recompute_step8_official_box_baseline_content_sha256(result)
    return result


def _rehash(baseline: dict) -> None:
    baseline["baseline_content_sha256"] = recompute_step8_official_box_baseline_content_sha256(baseline)


class Step8CoreProjectionTests(unittest.TestCase):
    def test_happy_path_creates_neutral_official_rate_projection(self) -> None:
        result = build_step8_core_projection(_handoff(), _baseline())
        self.assertEqual(result["model_version"], MODEL_VERSION)
        self.assertEqual(result["neutral_regulation_minutes_anchor"], 34.0)
        self.assertAlmostEqual(result["projection"]["points"], 14.0, places=5)
        self.assertAlmostEqual(result["projection"]["rebounds"], 10.0, places=5)
        self.assertAlmostEqual(result["projection"]["assists"], 3.0, places=5)
        self.assertAlmostEqual(result["projection"]["points_rebounds_assists"], 27.0, places=5)
        self.assertFalse(result["regulation_cap_applied"])
        self.assertTrue(result["guardrails"]["deterministic_projection_created"])
        self.assertTrue(result["guardrails"]["no_monte_carlo_created"])
        self.assertFalse(result["semantics"]["current_matchup_adjustment_applied"])
        self.assertFalse(result["semantics"]["current_role_adjustment_applied"])

    def test_regulation_minutes_are_capped_at_40(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_opportunity_context"]["observed_minutes_opportunity"]["tracked_minutes"]["stability"]["tracked_minutes_mean"] = 41.0
        baseline = _baseline(41.0)
        result = build_step8_core_projection(handoff, baseline)
        self.assertEqual(result["neutral_regulation_minutes_anchor"], 40.0)
        self.assertTrue(result["regulation_cap_applied"])
        self.assertLess(result["projection"]["points"], baseline["summary"]["points"]["mean"])

    def test_tampered_baseline_hash_fails_closed(self) -> None:
        baseline = _baseline()
        baseline["summary"]["points"]["mean"] = 99.0
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(_handoff(), baseline)

    def test_baseline_bound_to_different_handoff_fails_closed(self) -> None:
        baseline = _baseline()
        baseline["provenance"]["step8a_handoff_content_sha256"] = "c" * 64
        _rehash(baseline)
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(_handoff(), baseline)

    def test_wrong_baseline_game_identity_fails_closed(self) -> None:
        baseline = _baseline()
        baseline["requested_game_id"] = "1022600999"
        _rehash(baseline)
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(_handoff(), baseline)

    def test_wrong_current_team_fails_closed(self) -> None:
        baseline = _baseline()
        baseline["current_team_key"] = "wrong-team"
        _rehash(baseline)
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(_handoff(), baseline)

    def test_projection_authorization_is_required(self) -> None:
        handoff = _handoff()
        handoff["projection_execution_authorized"] = False
        with self.assertRaises(WNBAStep8CoreProjectionNotReadyError):
            build_step8_core_projection(handoff, _baseline())

    def test_current_roster_match_is_required(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["availability_summary"]["focal_player_current_roster_match"] = False
        with self.assertRaises(WNBAStep8CoreProjectionNotReadyError):
            build_step8_core_projection(handoff, _baseline())

    def test_blocking_current_availability_fails_closed(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["availability_summary"]["focal_player_availability"]["availability_blocking"] = True
        with self.assertRaises(WNBAStep8CoreProjectionNotReadyError):
            build_step8_core_projection(handoff, _baseline())

    def test_rotation_mean_drift_fails_closed(self) -> None:
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_opportunity_context"]["observed_minutes_opportunity"]["tracked_minutes"]["stability"]["tracked_minutes_mean"] = 30.0
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(handoff, _baseline())

    def test_pra_rate_mismatch_fails_closed(self) -> None:
        baseline = _baseline()
        baseline["summary"]["official_per_minute_rates"]["points_rebounds_assists"] += 0.1
        _rehash(baseline)
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(_handoff(), baseline)

    def test_third_party_baseline_fails_closed(self) -> None:
        baseline = _baseline()
        baseline["verification"]["third_party_sources_used"] = True
        _rehash(baseline)
        with self.assertRaises(WNBAStep8CoreProjectionUpstreamError):
            build_step8_core_projection(_handoff(), baseline)

    def test_core_flag_is_default_off(self) -> None:
        self.assertFalse(step8_core_projection_enabled({}))
        self.assertTrue(step8_core_projection_enabled({"WNBA_STEP8_CORE_PROJECTION_ENABLED": "true"}))

    def test_live_wrapper_refuses_when_core_flag_is_off(self) -> None:
        env = {
            "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
            "WNBA_STEP8_CORE_PROJECTION_ENABLED": "false",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_BOARD_SCHEDULER_ENABLED": "false",
            "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
            "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
            "WNBA_STEP6J_CANARY_ENABLED": "false",
            "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(WNBAStep8CoreProjectionDisabledError):
                get_player_game_step8_core_projection(PLAYER_ID, GAME_ID)

    def test_live_wrapper_refuses_production_switch(self) -> None:
        env = {
            "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
            "WNBA_STEP8_CORE_PROJECTION_ENABLED": "true",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(WNBAStep8CoreProjectionDisabledError):
                get_player_game_step8_core_projection(PLAYER_ID, GAME_ID)


if __name__ == "__main__":
    unittest.main(verbosity=2)
