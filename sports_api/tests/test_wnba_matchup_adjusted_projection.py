import unittest
from copy import deepcopy
from unittest.mock import patch

from sports_api import wnba_matchup_adjusted_projection as m
from sports_api.wnba_model_input_readiness import (
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
)


GAME_ID = "1022600284"
PLAYER_ID = 12345
TEAM = "chicago-sky"
OPPONENT = "connecticut-sun"
TEAMMATE_ID = 222


def role_row(role, minutes, points, rebounds, assists, games, team_key=TEAM):
    return {
        "role": role,
        "player_id": PLAYER_ID,
        "team_key": team_key,
        "games_played": games,
        "stats": {
            "minutes": minutes,
            "points": points,
            "rebounds": rebounds,
            "assists": assists,
        },
    }


def opportunity(lineups_available=True):
    return {
        "player_id": PLAYER_ID,
        "latest_observed_team_key": TEAM,
        "observed_minutes_opportunity": {
            "source_game_count": 5,
            "tracked_minutes": {
                "stability": {
                    "rotation_game_count": 5,
                    "tracked_minutes_mean": 30.0,
                    "tracked_minutes_median": 32.0,
                    "tracked_minutes_min": 25.0,
                    "tracked_minutes_max": 35.0,
                    "tracked_minutes_population_stddev": 2.0,
                }
            },
        },
        "observed_event_opportunity": {
            "feature_game_count": 5,
            "missing_feature_game_ids": [],
            "data_quality": {"feature_eligible_share_of_selected_lineup_events": 0.92},
            "own_event_counts_per_feature_game": {"points": 14.0, "rebounds": 7.0, "assists": 3.0},
        },
        "observed_role_context": {
            "available": True,
            "role_summary": {
                "starter_games": 3,
                "bench_games": 2,
                "starter_game_share": 0.6,
                "primary_observed_role": "starter",
            },
            "starter": role_row("Starters", 32.0, 16.0, 8.0, 4.0, 3),
            "bench": role_row("Bench", 20.0, 8.0, 6.0, 2.0, 2),
            "observed_role_band": "mixed_starter_bench_history",
        },
        "observed_five_player_lineup_context": (
            {
                "available": True,
                "lineup_count": 2,
                "top_five_player_lineups": [
                    {
                        "group_id": "a",
                        "player_ids": [PLAYER_ID, TEAMMATE_ID, 3, 4, 5],
                        "minutes": 10.0,
                    },
                    {
                        "group_id": "b",
                        "player_ids": [PLAYER_ID, 6, 7, 8, 9],
                        "minutes": 5.0,
                    },
                ],
            }
            if lineups_available
            else {"available": False, "top_five_player_lineups": []}
        ),
    }


def advanced_dataset(team_key, *, pace, off_rating, def_rating, reb_pct):
    return {
        "filters": {"team_key": team_key},
        "teams": [
            {
                "team_key": team_key,
                "advanced": {
                    "pace": pace,
                    "estimated_pace": pace,
                    "offensive_rating": off_rating,
                    "estimated_offensive_rating": off_rating,
                    "defensive_rating": def_rating,
                    "estimated_defensive_rating": def_rating,
                    "rebound_percentage": reb_pct,
                    "estimated_rebound_percentage": reb_pct,
                },
            }
        ],
    }


def recent_shot_chart(attempt_count=20):
    scale = attempt_count / 20.0
    return {
        "player_id": PLAYER_ID,
        "filters": {"last_n_games": 5, "opponent_team_key": None},
        "attempt_count": attempt_count,
        "field_goal_percentage": 0.45,
        "zone_summary": [
            {
                "canonical_zone": "restricted_area",
                "field_goals_attempted": 10.0 * scale,
                "points_scored": 12.0 * scale,
                "attempt_share": 0.5,
                "observed_points_per_attempt": 1.2,
            },
            {
                "canonical_zone": "above_the_break_3",
                "field_goals_attempted": 10.0 * scale,
                "points_scored": 12.0 * scale,
                "attempt_share": 0.5,
                "observed_points_per_attempt": 1.2,
            },
        ],
        "league_average_rows": [
            {
                "canonical_zone": "restricted_area",
                "field_goals_attempted": 100.0,
                "field_goals_made": 60.0,
                "field_goal_percentage": 0.60,
            },
            {
                "canonical_zone": "above_the_break_3",
                "field_goals_attempted": 100.0,
                "field_goals_made": 35.0,
                "field_goal_percentage": 0.35,
            },
        ],
    }


def versus_shot_chart():
    return {
        "player_id": PLAYER_ID,
        "filters": {"last_n_games": 0, "opponent_team_key": OPPONENT},
        "attempt_count": 12,
        "field_goal_percentage": 0.50,
        "zone_summary": [],
        "league_average_rows": [],
    }


def opponent_zone_defense(defending_team=OPPONENT):
    return {
        "defending_team_key": defending_team,
        "zones_allowed": [
            {
                "canonical_zone": "restricted_area",
                "field_goal_percentage_allowed": 0.70,
                "field_goals_attempted_allowed": 80.0,
            },
            {
                "canonical_zone": "above_the_break_3",
                "field_goal_percentage_allowed": 0.40,
                "field_goals_attempted_allowed": 80.0,
            },
        ],
    }


def team_rest_context(*, full_rest_days, second_b2b=False, miles=0.0, tz=0.0, road_game=None):
    return {
        "rest": {
            "full_rest_days_before_date": full_rest_days,
            "is_second_night_of_back_to_back": second_b2b,
        },
        "travel_to_target_or_next_game": {
            "available": True,
            "great_circle_miles": miles,
            "timezone_offset_change_hours": tz,
        },
        "road_trip": {
            "applicable": road_game is not None,
            "road_trip_game_number": road_game,
        },
    }


def rest_travel():
    return {
        "away_team_key": TEAM,
        "home_team_key": OPPONENT,
        "away_context": team_rest_context(
            full_rest_days=1,
            second_b2b=True,
            miles=1600.0,
            tz=0.0,
        ),
        "home_context": team_rest_context(
            full_rest_days=2,
            second_b2b=False,
            miles=0.0,
            tz=0.0,
        ),
    }


def component_status(available=True, requested=True):
    return {"requested": requested, "available": available, "error": None if available else "unavailable"}


def snapshot(*, lineups_available=True):
    return {
        "snapshot_id": "wnba-4w-5b-test",
        "content_sha256": "a" * 64,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "recent_window_games": 5,
        "game_identity": {
            "game_id": GAME_ID,
            "date": "2026-08-26",
            "away_team_key": TEAM,
            "home_team_key": OPPONENT,
            "game_datetime_utc": "2026-08-27T00:00:00+00:00",
            "status": {"category": "scheduled"},
        },
        "focal_identity": {
            "player_id": PLAYER_ID,
            "team_key": TEAM,
            "opponent_team_key": OPPONENT,
            "side": "away",
        },
        "component_status": {
            "player_recent_shot_chart": component_status(),
            "player_vs_opponent_shot_chart": component_status(),
            "opponent_defense_by_shot_zone": component_status(),
            "team_advanced": component_status(),
            "opponent_advanced": component_status(),
        },
        "inputs": {
            "player_opportunity_context": opportunity(lineups_available=lineups_available),
            "game_rest_travel_context": rest_travel(),
            "team_advanced": advanced_dataset(
                TEAM, pace=80.0, off_rating=110.0, def_rating=104.0, reb_pct=0.50
            ),
            "opponent_advanced": advanced_dataset(
                OPPONENT, pace=84.0, off_rating=108.0, def_rating=106.0, reb_pct=0.48
            ),
            "player_recent_shot_chart": recent_shot_chart(),
            "player_vs_opponent_shot_chart": versus_shot_chart(),
            "opponent_defense_by_shot_zone": opponent_zone_defense(),
            "game_availability": {
                "away": {
                    "team_key": TEAM,
                    "players": [
                        {
                            "player_id": PLAYER_ID,
                            "player_name": "Test Player",
                            "injury_report_status": None,
                            "availability_blocking": False,
                            "availability_uncertain": False,
                        },
                        {
                            "player_id": TEAMMATE_ID,
                            "player_name": "Unavailable Teammate",
                            "injury_report_status": "Out",
                            "availability_blocking": True,
                            "availability_uncertain": False,
                        },
                    ],
                },
                "home": {"team_key": OPPONENT, "players": []},
            },
        },
    }


def readiness(state="READY", warning_ids=None, *, lineups_available=True):
    snap = snapshot(lineups_available=lineups_available)
    warnings = warning_ids or []
    return {
        "readiness": state,
        "can_start_projection": state != "NOT_READY",
        "diagnostic_data_quality_score": 100 if state == "READY" else 92,
        "snapshot_included": True,
        "snapshot_reference": {
            "snapshot_id": snap["snapshot_id"],
            "content_sha256": snap["content_sha256"],
            "game_id": snap["game_id"],
            "player_id": snap["player_id"],
            "recent_window_games": snap["recent_window_games"],
        },
        "summary": {
            "blocker_ids": ["bad"] if state == "NOT_READY" else [],
            "warning_ids": warnings,
        },
        "snapshot": snap,
    }


class WNBAMatchupAdjustedProjectionTests(unittest.TestCase):
    def test_not_ready_gate_blocks_5b(self):
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionNotReadyError, "NOT_READY"):
            m.project_matchup_adjusted_from_readiness(readiness("NOT_READY"))

    def test_minutes_remain_exactly_step_5a_baseline(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        self.assertEqual(result["baseline_projection"]["minutes"], result["projection"]["minutes"] | {"adjusted_in_step_5b": False})
        self.assertEqual(result["projection"]["minutes"]["expected"], 31.2)
        self.assertFalse(result["projection"]["minutes"]["adjusted_in_step_5b"])

    def test_pace_adjustment_is_hand_calculable(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        pace = result["adjustments"]["pace"]
        self.assertAlmostEqual(pace["target_matchup_pace"], 82.0, places=6)
        self.assertAlmostEqual(pace["capped_adjustment_pct"], 0.025, places=8)
        self.assertAlmostEqual(pace["stat_adjustment_pct"]["rebounds"], 0.025, places=8)

    def test_defense_adjustment_uses_midpoint_efficiency(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        defense = result["adjustments"]["opponent_defensive_environment"]
        self.assertAlmostEqual(defense["midpoint_matchup_efficiency"], 108.0, places=6)
        self.assertAlmostEqual(defense["points_adjustment_pct"], 108.0 / 110.0 - 1.0, places=8)
        self.assertAlmostEqual(
            defense["stat_adjustment_pct"]["assists"],
            (108.0 / 110.0 - 1.0) * 0.5,
            places=8,
        )
        self.assertEqual(defense["stat_adjustment_pct"]["rebounds"], 0.0)

    def test_rebound_environment_adjustment_is_separate(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        rebound = result["adjustments"]["rebound_environment"]
        self.assertAlmostEqual(rebound["midpoint_matchup_rebound_share"], 0.51, places=8)
        self.assertAlmostEqual(rebound["stat_adjustment_pct"]["rebounds"], 0.02, places=8)
        self.assertEqual(rebound["stat_adjustment_pct"]["points"], 0.0)

    def test_shot_zone_fit_is_shrunk_and_capped(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        shot = result["adjustments"]["shot_zone_fit"]
        self.assertTrue(shot["applied"])
        self.assertAlmostEqual(shot["weighted_points_per_attempt_delta_vs_league"], 0.175, places=8)
        self.assertEqual(shot["capped_points_adjustment_pct"], 0.04)
        self.assertEqual(shot["stat_adjustment_pct"]["rebounds"], 0.0)

    def test_historical_vs_opponent_shooting_is_diagnostic_only(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        diagnostic = result["adjustments"]["shot_zone_fit"]["historical_vs_opponent"]
        self.assertTrue(diagnostic["available"])
        self.assertEqual(diagnostic["attempt_count"], 12)
        self.assertIn("diagnostic_only", diagnostic["usage_in_step_5b"])
        self.assertTrue(result["guardrails"]["historical_vs_opponent_shooting_is_diagnostic_not_directly_applied"])

    def test_low_player_shot_sample_disables_directional_shot_adjustment(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_recent_shot_chart"] = recent_shot_chart(attempt_count=8)
        result = m.project_matchup_adjusted_from_readiness(report)
        shot = result["adjustments"]["shot_zone_fit"]
        self.assertTrue(shot["available"])
        self.assertFalse(shot["applied"])
        self.assertEqual(shot["stat_adjustment_pct"]["points"], 0.0)

    def test_low_zone_match_share_disables_shot_adjustment(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_recent_shot_chart"]["zone_summary"][1]["canonical_zone"] = "mid_range"
        result = m.project_matchup_adjusted_from_readiness(report)
        shot = result["adjustments"]["shot_zone_fit"]
        self.assertFalse(shot["applied"])
        self.assertAlmostEqual(shot["matched_player_attempt_share"], 0.5, places=8)

    def test_wrong_shot_player_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_recent_shot_chart"]["player_id"] = 999
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "wrong player ID"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_wrong_opponent_shot_filter_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_vs_opponent_shot_chart"]["filters"]["opponent_team_key"] = TEAM
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "filter disagrees"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_wrong_defending_team_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["opponent_defense_by_shot_zone"]["defending_team_key"] = TEAM
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "wrong defending team"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_rest_travel_relative_adjustment_hits_small_cap(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        rest = result["adjustments"]["rest_travel"]
        self.assertAlmostEqual(rest["rest_difference_effect"], -0.0025, places=8)
        self.assertAlmostEqual(rest["focal_schedule_travel_penalty"]["penalty"], -0.0125, places=8)
        self.assertAlmostEqual(rest["capped_adjustment_pct"], -0.015, places=8)

    def test_rest_travel_wrong_opponent_identity_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["game_rest_travel_context"]["home_team_key"] = "seattle-storm"
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "opponent identity"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_lineup_disruption_is_uncertainty_only(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        lineup = result["adjustments"]["lineup_continuity"]
        self.assertTrue(lineup["uncertainty_flag"])
        self.assertFalse(lineup["central_projection_adjustment_applied"])
        self.assertAlmostEqual(lineup["blocking_lineup_share_of_returned_minutes"], 2.0 / 3.0, places=6)
        self.assertEqual(lineup["stat_adjustment_pct"], {"points": 0.0, "rebounds": 0.0, "assists": 0.0})

    def test_unavailable_lineup_context_does_not_invent_adjustment(self):
        result = m.project_matchup_adjusted_from_readiness(readiness(lineups_available=False))
        lineup = result["adjustments"]["lineup_continuity"]
        self.assertFalse(lineup["available"])
        self.assertFalse(lineup["central_projection_adjustment_applied"])

    def test_final_points_adjustment_receipt_is_sum_of_components(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        points = result["projection"]["points"]
        expected_pct = 0.025 + (108.0 / 110.0 - 1.0) + 0.04 - 0.015
        self.assertAlmostEqual(points["total_adjustment_pct"], expected_pct, places=8)
        self.assertAlmostEqual(points["expected"], 14.352 * (1.0 + expected_pct), places=4)

    def test_final_rebound_adjustment_receipt(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        rebounds = result["projection"]["rebounds"]
        self.assertAlmostEqual(rebounds["total_adjustment_pct"], 0.025 + 0.02 - 0.015, places=8)
        self.assertAlmostEqual(rebounds["expected"], 8.424 * 1.03, places=4)

    def test_final_assist_adjustment_receipt(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        assists = result["projection"]["assists"]
        expected_pct = 0.025 + ((108.0 / 110.0 - 1.0) * 0.5) - 0.015
        self.assertAlmostEqual(assists["total_adjustment_pct"], expected_pct, places=8)

    def test_pra_equals_adjusted_component_sum(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        p = result["projection"]
        self.assertAlmostEqual(
            p["pra"]["expected"],
            p["points"]["expected"] + p["rebounds"]["expected"] + p["assists"]["expected"],
            places=4,
        )

    def test_total_adjustment_cap_overrides_extreme_component_sum(self):
        baseline = {
            "projection": {
                "points": {"expected": 10.0, "minutes_sensitivity_low": 9.0, "minutes_sensitivity_high": 11.0},
                "rebounds": {"expected": 5.0, "minutes_sensitivity_low": 4.0, "minutes_sensitivity_high": 6.0},
                "assists": {"expected": 3.0, "minutes_sensitivity_low": 2.0, "minutes_sensitivity_high": 4.0},
            }
        }
        components = {
            "a": {"applied": True, "stat_adjustment_pct": {"points": 0.07, "rebounds": 0.07, "assists": 0.07}},
            "b": {"applied": True, "stat_adjustment_pct": {"points": 0.07, "rebounds": 0.07, "assists": 0.07}},
        }
        stats, _ = m._combine_adjustments(baseline, components)
        self.assertEqual(stats["points"]["total_adjustment_pct"], 0.08)
        self.assertEqual(stats["points"]["expected"], 10.8)

    def test_advanced_component_unavailable_degrades_to_partial_context(self):
        report = readiness("READY_WITH_WARNINGS", ["advanced_context_coverage"])
        report["snapshot"]["component_status"]["team_advanced"] = component_status(False)
        report["snapshot"]["component_status"]["opponent_advanced"] = component_status(False)
        report["snapshot"]["inputs"].pop("team_advanced")
        report["snapshot"]["inputs"].pop("opponent_advanced")
        result = m.project_matchup_adjusted_from_readiness(report)
        self.assertEqual(result["adjustment_context"]["context_level"], "partial")
        self.assertFalse(result["adjustments"]["pace"]["available"])
        self.assertFalse(result["adjustments"]["opponent_defensive_environment"]["available"])
        self.assertFalse(result["adjustments"]["rebound_environment"]["available"])

    def test_available_component_with_missing_payload_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"].pop("team_advanced")
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "marks component team_advanced available"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_wrong_team_advanced_filter_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["team_advanced"]["filters"]["team_key"] = OPPONENT
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "conflicting team filter"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_duplicate_team_advanced_rows_fail_closed(self):
        report = readiness()
        row = deepcopy(report["snapshot"]["inputs"]["team_advanced"]["teams"][0])
        report["snapshot"]["inputs"]["team_advanced"]["teams"].append(row)
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "returned 2 rows"):
            m.project_matchup_adjusted_from_readiness(report)

    def test_ready_with_warnings_propagates_from_5a(self):
        result = m.project_matchup_adjusted_from_readiness(readiness("READY_WITH_WARNINGS", ["shot_context_coverage"]))
        self.assertEqual(result["readiness"]["state"], "READY_WITH_WARNINGS")
        self.assertIn("shot_context_coverage", result["readiness"]["warning_ids"])

    def test_projection_fingerprint_is_deterministic(self):
        first = m.project_matchup_adjusted_from_readiness(readiness())
        second = m.project_matchup_adjusted_from_readiness(readiness())
        self.assertEqual(first["projection_fingerprint_sha256"], second["projection_fingerprint_sha256"])
        self.assertEqual(first["projection_id"], second["projection_id"])

    def test_projection_fingerprint_changes_with_snapshot_hash(self):
        first_report = readiness()
        second_report = readiness()
        second_report["snapshot"]["content_sha256"] = "b" * 64
        second_report["snapshot_reference"]["content_sha256"] = "b" * 64
        first = m.project_matchup_adjusted_from_readiness(first_report)
        second = m.project_matchup_adjusted_from_readiness(second_report)
        self.assertNotEqual(first["projection_fingerprint_sha256"], second["projection_fingerprint_sha256"])

    def test_no_market_probability_or_monte_carlo_in_5b(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        self.assertTrue(result["guardrails"]["no_sportsbook_data_used"])
        self.assertTrue(result["guardrails"]["no_betting_probability_created"])
        self.assertTrue(result["guardrails"]["no_monte_carlo_created"])
        self.assertTrue(result["guardrails"]["no_named_defender_assignment_inferred"])

    def test_matchup_components_cannot_change_minutes(self):
        result = m.project_matchup_adjusted_from_readiness(readiness())
        self.assertTrue(result["guardrails"]["no_matchup_component_can_change_minutes"])
        self.assertTrue(result["projection_semantics"]["minutes_remain_step_5a_baseline"])

    @patch("sports_api.wnba_matchup_adjusted_projection.get_player_game_model_input_readiness")
    def test_wrapper_requests_required_5b_context(self, gate):
        gate.return_value = readiness()
        result = m.get_player_game_matchup_adjusted_projection(PLAYER_ID, GAME_ID, 2026)
        self.assertEqual(result["player_id"], PLAYER_ID)
        gate.assert_called_once_with(
            PLAYER_ID,
            GAME_ID,
            2026,
            season_type="Regular Season",
            last_n_games=5,
            require_current_availability=True,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=False,
            max_snapshot_age_minutes=15,
            include_snapshot=True,
        )

    @patch("sports_api.wnba_matchup_adjusted_projection.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_not_found(self, gate):
        gate.side_effect = WNBAModelInputReadinessNotFoundError("missing")
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionNotFoundError, "missing"):
            m.get_player_game_matchup_adjusted_projection(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_matchup_adjusted_projection.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_upstream(self, gate):
        gate.side_effect = WNBAModelInputReadinessUpstreamError("upstream")
        with self.assertRaisesRegex(m.WNBAMatchupAdjustedProjectionUpstreamError, "upstream"):
            m.get_player_game_matchup_adjusted_projection(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_matchup_adjusted_projection.get_player_game_model_input_readiness")
    def test_invalid_player_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_game_matchup_adjusted_projection(0, GAME_ID, 2026)
        gate.assert_not_called()

    @patch("sports_api.wnba_matchup_adjusted_projection.get_player_game_model_input_readiness")
    def test_invalid_game_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_player_game_matchup_adjusted_projection(PLAYER_ID, "bad", 2026)
        gate.assert_not_called()

    def test_shot_value_rules(self):
        self.assertEqual(m._shot_value("restricted_area"), 2)
        self.assertEqual(m._shot_value("above_the_break_3"), 3)
        self.assertEqual(m._shot_value("backcourt"), 3)


if __name__ == "__main__":
    unittest.main()
