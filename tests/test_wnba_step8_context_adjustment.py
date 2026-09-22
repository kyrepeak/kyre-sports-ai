from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from sports_api import wnba_step8_context_adjustment as mod

PLAYER_ID = 1642291
GAME_ID = "1022600291"
TEAM_KEY = "atlanta-dream"
OPP_KEY = "portland-fire"


def _advanced_row(team_key: str, pace: float, *, player: bool = False) -> dict:
    row = {
        "team_key": team_key,
        "games_played": 5,
        "minutes": 36.0 if player else 200.0,
        "advanced": {
            "estimated_pace": pace,
            "effective_field_goal_percentage": 0.5,
            "true_shooting_percentage": 0.55,
        },
    }
    if player:
        row["player_id"] = PLAYER_ID
    return row


def _handoff(*, player_pace=80.0, team_pace=82.0, opponent_pace=78.0) -> dict:
    return {
        "handoff_id": "wnba-8a-synthetic",
        "handoff_content_sha256": "a" * 64,
        "snapshot": {
            "season": 2026,
            "season_type": "Regular Season",
            "game_id": GAME_ID,
            "player_id": PLAYER_ID,
            "focal_identity": {
                "side": "home",
                "team_key": TEAM_KEY,
                "opponent_team_key": OPP_KEY,
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
                "player_advanced": {"players": [_advanced_row(TEAM_KEY, player_pace, player=True)]},
                "team_advanced": {"teams": [_advanced_row(TEAM_KEY, team_pace)]},
                "opponent_advanced": {"teams": [_advanced_row(OPP_KEY, opponent_pace)]},
                "player_opportunity_context": {
                    "observed_role_context": {
                        "available": False,
                        "error": "optional unavailable",
                        "observed_role_band": None,
                    }
                },
                "game_availability": {
                    "home": {
                        "players": [
                            {"player_id": PLAYER_ID, "player_name": "Focal"},
                            {
                                "player_id": 200,
                                "player_name": "Out Teammate",
                                "availability_class": "unavailable",
                                "availability_blocking": True,
                                "availability_uncertain": False,
                                "listed_on_injury_report": True,
                                "recent_minutes_per_game": None,
                                "observed_rotation_rank_by_recent_minutes": 3,
                            },
                        ]
                    },
                    "away": {"players": []},
                },
                "game_rest_travel_context": {
                    "home_context": {
                        "team": {"team_key": TEAM_KEY},
                        "rest": {"full_rest_days_before_date": 3, "is_second_night_of_back_to_back": False},
                        "schedule_density": {"three_in_five_through_date": False},
                        "road_trip": {"applicable": False},
                        "travel_to_target_or_next_game": {
                            "available": True,
                            "great_circle_miles": 1900.0,
                            "timezone_offset_change_hours": 3.0,
                            "same_city": False,
                        },
                        "observed_workload": {
                            "completed_games_previous_3_days": 0,
                            "completed_games_previous_5_days": 1,
                            "completed_games_previous_7_days": 2,
                            "team_minutes_previous_7_days": 400.0,
                            "team_minutes_above_regulation_previous_7_days": 0.0,
                        },
                    },
                    "away_context": {
                        "team": {"team_key": OPP_KEY},
                        "rest": {"full_rest_days_before_date": 2, "is_second_night_of_back_to_back": False},
                        "schedule_density": {"three_in_five_through_date": False},
                        "road_trip": {"applicable": True, "road_trip_game_number": 2},
                        "travel_to_target_or_next_game": {
                            "available": True,
                            "great_circle_miles": 700.0,
                            "timezone_offset_change_hours": 1.0,
                            "same_city": False,
                        },
                        "observed_workload": {
                            "completed_games_previous_3_days": 1,
                            "completed_games_previous_5_days": 2,
                            "completed_games_previous_7_days": 3,
                            "team_minutes_previous_7_days": 600.0,
                            "team_minutes_above_regulation_previous_7_days": 0.0,
                        },
                    },
                },
                "player_recent_shot_chart": {"attempt_count": 70, "selected_game_count": 5},
                "player_vs_opponent_shot_chart": {"attempt_count": 14, "selected_game_count": 2},
                "opponent_defense_by_shot_zone": {"selected_game_count": 5},
            },
        },
    }


def _baseline() -> dict:
    return {"baseline_id": "wnba-8b-box-synthetic", "baseline_content_sha256": "b" * 64}


def _core(*, mean_minutes=36.0, median_minutes=38.0) -> dict:
    rates = {
        "points": 0.5,
        "rebounds": 0.4,
        "assists": 0.1,
        "points_rebounds_assists": 1.0,
    }
    return {
        "model_version": mod.STEP8B_MODEL_VERSION,
        "projection_id": "wnba-8b-core-synthetic",
        "projection_content_sha256": "c" * 64,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM_KEY,
        "opponent_team_key": OPP_KEY,
        "neutral_regulation_minutes_anchor": mean_minutes,
        "official_per_minute_rates": rates,
        "projection": {
            "minutes": mean_minutes,
            "points": 0.5 * mean_minutes,
            "rebounds": 0.4 * mean_minutes,
            "assists": 0.1 * mean_minutes,
            "points_rebounds_assists": mean_minutes,
        },
        "historical_dispersion": {
            "minutes": {
                "recent_mean": mean_minutes,
                "recent_median": median_minutes,
                "recent_population_stddev": 3.0,
            }
        },
    }


class Step8ContextAdjustmentTests(unittest.TestCase):
    def _build(self, handoff=None, core=None):
        handoff = handoff or _handoff()
        core = core or _core()
        with patch.object(mod, "build_step8_core_projection", return_value=deepcopy(core)):
            return mod.build_step8_context_adjusted_projection(handoff, _baseline())

    def test_happy_path_uses_median_minutes_and_matchup_pace(self):
        result = self._build()
        self.assertEqual(result["projection"]["minutes"], 38.0)
        self.assertEqual(result["adjustment_summary"]["matchup_pace"]["pace_factor"], 1.0)
        self.assertAlmostEqual(result["projection"]["points"], 19.0, places=6)
        self.assertAlmostEqual(result["projection"]["rebounds"], 15.2, places=6)
        self.assertAlmostEqual(result["projection"]["assists"], 3.8, places=6)
        self.assertAlmostEqual(result["projection"]["points_rebounds_assists"], 38.0, places=6)

    def test_matchup_pace_scales_all_component_rates_linearly(self):
        result = self._build(_handoff(player_pace=80.0, team_pace=84.0, opponent_pace=80.0))
        self.assertAlmostEqual(result["adjustment_summary"]["matchup_pace"]["pace_factor"], 1.025, places=8)
        self.assertAlmostEqual(result["projection"]["points"], 19.475, places=6)
        self.assertAlmostEqual(result["projection"]["rebounds"], 15.58, places=6)
        self.assertAlmostEqual(result["projection"]["assists"], 3.895, places=6)

    def test_pra_is_recomposed_from_components(self):
        result = self._build(_handoff(player_pace=80.0, team_pace=84.0, opponent_pace=80.0))
        expected = sum(result["projection"][key] for key in ("points", "rebounds", "assists"))
        self.assertAlmostEqual(result["projection"]["points_rebounds_assists"], expected, places=6)

    def test_median_minutes_are_capped_at_40(self):
        result = self._build(core=_core(mean_minutes=39.0, median_minutes=42.0))
        self.assertEqual(result["projection"]["minutes"], 40.0)

    def test_uncertain_focal_availability_fails_closed(self):
        handoff = _handoff()
        handoff["snapshot"]["availability_summary"]["focal_player_availability"]["availability_uncertain"] = True
        with patch.object(mod, "build_step8_core_projection", return_value=_core()):
            with self.assertRaises(mod.WNBAStep8ContextAdjustmentNotReadyError):
                mod.build_step8_context_adjusted_projection(handoff, _baseline())

    def test_blocking_focal_availability_fails_closed(self):
        handoff = _handoff()
        handoff["snapshot"]["availability_summary"]["focal_player_availability"]["availability_blocking"] = True
        with patch.object(mod, "build_step8_core_projection", return_value=_core()):
            with self.assertRaises(mod.WNBAStep8ContextAdjustmentNotReadyError):
                mod.build_step8_context_adjusted_projection(handoff, _baseline())

    def test_player_advanced_identity_mismatch_fails_closed(self):
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_advanced"]["players"][0]["player_id"] = 999
        with patch.object(mod, "build_step8_core_projection", return_value=_core()):
            with self.assertRaises(mod.WNBAStep8ContextAdjustmentUpstreamError):
                mod.build_step8_context_adjusted_projection(handoff, _baseline())

    def test_opponent_advanced_identity_mismatch_fails_closed(self):
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["opponent_advanced"]["teams"][0]["team_key"] = "wrong-team"
        with patch.object(mod, "build_step8_core_projection", return_value=_core()):
            with self.assertRaises(mod.WNBAStep8ContextAdjustmentUpstreamError):
                mod.build_step8_context_adjusted_projection(handoff, _baseline())

    def test_implausible_pace_fails_closed(self):
        with self.assertRaises(mod.WNBAStep8ContextAdjustmentUpstreamError):
            self._build(_handoff(opponent_pace=200.0))

    def test_extreme_raw_pace_ratio_fails_closed_instead_of_clipping(self):
        handoff = _handoff(player_pace=60.0, team_pace=90.0, opponent_pace=90.0)
        with self.assertRaises(mod.WNBAStep8ContextAdjustmentUpstreamError):
            self._build(handoff)

    def test_unavailable_role_never_creates_role_multiplier(self):
        result = self._build()
        role = result["adjustment_summary"]["role"]
        self.assertFalse(role["available"])
        self.assertFalse(role["adjustment_applied"])
        self.assertEqual(role["mean_adjustment_factor"], 1.0)

    def test_available_historical_role_still_does_not_infer_current_role(self):
        handoff = _handoff()
        handoff["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"] = {
            "available": True,
            "observed_role_band": "mostly_starter",
        }
        result = self._build(handoff)
        role = result["adjustment_summary"]["role"]
        self.assertTrue(role["available"])
        self.assertFalse(role["adjustment_applied"])
        self.assertEqual(role["mean_adjustment_factor"], 1.0)

    def test_flagged_teammate_does_not_redistribute_opportunity(self):
        result = self._build()
        teammates = result["adjustment_summary"]["teammate_availability"]
        self.assertEqual(teammates["flagged_teammate_count"], 1)
        self.assertFalse(teammates["opportunity_redistribution_applied"])
        self.assertEqual(teammates["mean_adjustment_factor"], 1.0)

    def test_rest_travel_never_creates_uncalibrated_fatigue_penalty(self):
        result = self._build()
        rest = result["adjustment_summary"]["rest_travel"]
        self.assertFalse(rest["fatigue_or_travel_mean_adjustment_applied"])
        self.assertEqual(rest["mean_adjustment_factor"], 1.0)

    def test_shot_zone_context_never_creates_uncalibrated_mean_multiplier(self):
        result = self._build()
        shot = result["adjustment_summary"]["shot_zone_matchup"]
        self.assertTrue(shot["available"])
        self.assertFalse(shot["adjustment_applied"])
        self.assertEqual(shot["mean_adjustment_factor"], 1.0)

    def test_context_flag_is_default_off(self):
        self.assertFalse(mod.step8_context_adjustment_enabled({}))
        self.assertTrue(mod.step8_context_adjustment_enabled({"WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED": "true"}))

    def test_live_wrapper_refuses_when_context_flag_is_off(self):
        env = {
            "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
            "WNBA_STEP8_CORE_PROJECTION_ENABLED": "true",
            "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(mod.WNBAStep8ContextAdjustmentDisabledError):
                mod.get_player_game_step8_context_adjusted_projection(PLAYER_ID, GAME_ID)

    def test_live_wrapper_refuses_production_switch(self):
        env = {
            "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true",
            "WNBA_STEP8_CORE_PROJECTION_ENABLED": "true",
            "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED": "true",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(mod.WNBAStep8ContextAdjustmentDisabledError):
                mod.get_player_game_step8_context_adjusted_projection(PLAYER_ID, GAME_ID)


if __name__ == "__main__":
    unittest.main(verbosity=2)
