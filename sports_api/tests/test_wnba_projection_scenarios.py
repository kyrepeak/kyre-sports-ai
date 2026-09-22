import unittest
from copy import deepcopy
from unittest.mock import patch

from sports_api import wnba_projection_scenarios as m
from sports_api.wnba_matchup_adjusted_projection import (
    MODEL_VERSION as MATCHUP_MODEL_VERSION,
    WNBAMatchupAdjustedProjectionModelInputError,
    WNBAMatchupAdjustedProjectionNotReadyError,
    WNBAMatchupAdjustedProjectionUpstreamError,
)
from sports_api.wnba_model_input_readiness import (
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
)


GAME_ID = "1022600284"
PLAYER_ID = 12345
TEAM = "chicago-sky"
OPPONENT = "connecticut-sun"


def snapshot(status=None, uncertain=False, blocking=False):
    return {
        "snapshot_id": "wnba-4w-5c-test",
        "content_sha256": "a" * 64,
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "recent_window_games": 5,
        "focal_identity": {
            "player_id": PLAYER_ID,
            "team_key": TEAM,
            "opponent_team_key": OPPONENT,
            "side": "away",
        },
        "inputs": {
            "game_availability": {
                "away": {
                    "team_key": TEAM,
                    "players": [
                        {
                            "player_id": PLAYER_ID,
                            "player_name": "Test Player",
                            "injury_report_status": status,
                            "availability_class": (
                                "unavailable" if blocking else "uncertain" if uncertain else "not_listed"
                            ),
                            "availability_blocking": blocking,
                            "availability_uncertain": uncertain,
                        }
                    ],
                },
                "home": {"team_key": OPPONENT, "players": []},
            }
        },
    }


def readiness(state="READY", warning_ids=None, **snapshot_kwargs):
    snap = snapshot(**snapshot_kwargs)
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
            "blocker_ids": ["blocked"] if state == "NOT_READY" else [],
            "warning_ids": warning_ids or [],
        },
        "snapshot": snap,
    }


def matchup(
    *,
    context_level="full",
    lineup_available=True,
    blocking_share=0.0,
    uncertain_share=0.0,
    shot_available=True,
    shot_applied=True,
):
    ref = readiness()["snapshot_reference"]
    return {
        "model_version": MATCHUP_MODEL_VERSION,
        "projection_id": "wnba-5b-test",
        "projection_fingerprint_sha256": "b" * 64,
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "team_key": TEAM,
        "opponent_team_key": OPPONENT,
        "side": "away",
        "snapshot_reference": deepcopy(ref),
        "readiness": {
            "state": "READY",
            "warning_ids": [],
        },
        "adjustment_context": {
            "context_level": context_level,
            "applied_components": [],
            "available_not_applied_components": [],
            "unavailable_components": [] if context_level == "full" else ["pace"],
        },
        "adjustments": {
            "lineup_continuity": {
                "available": lineup_available,
                "blocking_lineup_share_of_returned_minutes": blocking_share,
                "uncertain_lineup_share_of_returned_minutes": uncertain_share,
                "uncertainty_flag": bool(blocking_share or uncertain_share),
                "central_projection_adjustment_applied": False,
                "stat_adjustment_pct": {"points": 0.0, "rebounds": 0.0, "assists": 0.0},
            },
            "shot_zone_fit": {
                "available": shot_available,
                "applied": shot_applied,
                "reason": None if shot_applied else "shot_zone_sample_or_match_coverage_below_step_5b_threshold",
                "stat_adjustment_pct": {"points": 0.0, "rebounds": 0.0, "assists": 0.0},
            },
        },
        "projection": {
            "minutes": {
                "expected": 30.0,
                "sensitivity_low": 27.0,
                "sensitivity_high": 33.0,
                "adjusted_in_step_5b": False,
            },
            "points": {
                "expected": 20.0,
                "minutes_sensitivity_low": 18.0,
                "minutes_sensitivity_high": 22.0,
            },
            "rebounds": {
                "expected": 10.0,
                "minutes_sensitivity_low": 9.0,
                "minutes_sensitivity_high": 11.0,
            },
            "assists": {
                "expected": 5.0,
                "minutes_sensitivity_low": 4.5,
                "minutes_sensitivity_high": 5.5,
            },
            "pra": {
                "expected": 35.0,
                "minutes_sensitivity_low": 31.5,
                "minutes_sensitivity_high": 38.5,
            },
        },
    }


class WNBAProjectionScenarioTests(unittest.TestCase):
    def test_base_scenario_exactly_preserves_step_5b_central_projection(self):
        report = readiness()
        result = m.build_projection_scenarios(matchup(), report)
        base = result["scenarios"]["base"]
        self.assertEqual(base["minutes"], 30.0)
        self.assertEqual(base["points"], 20.0)
        self.assertEqual(base["rebounds"], 10.0)
        self.assertEqual(base["assists"], 5.0)
        self.assertEqual(base["pra"], 35.0)
        self.assertEqual(result["central_projection"], matchup()["projection"])

    def test_healthy_full_context_scenarios_use_observed_minutes_only(self):
        result = m.build_projection_scenarios(matchup(), readiness())
        self.assertEqual(result["scenarios"]["low"]["minutes"], 27.0)
        self.assertEqual(result["scenarios"]["high"]["minutes"], 33.0)
        self.assertEqual(result["scenarios"]["low"]["points"], 18.0)
        self.assertEqual(result["scenarios"]["high"]["points"], 22.0)
        self.assertEqual(result["scenario_components"]["context_spread_pct_by_stat"]["points"], 0.0)

    def test_questionable_status_stresses_only_low_minutes_scenario(self):
        report = readiness(status="Questionable", uncertain=True)
        result = m.build_projection_scenarios(matchup(), report)
        self.assertAlmostEqual(result["scenarios"]["low"]["minutes"], 27.0 * 0.925, places=4)
        self.assertEqual(result["scenarios"]["base"]["minutes"], 30.0)
        self.assertEqual(result["scenarios"]["high"]["minutes"], 33.0)
        self.assertAlmostEqual(result["scenarios"]["low"]["points"], 18.0 * 0.925, places=4)
        self.assertEqual(result["scenarios"]["base"]["points"], 20.0)
        self.assertEqual(result["scenarios"]["high"]["points"], 22.0)

    def test_doubtful_has_larger_low_scenario_stress_than_questionable(self):
        questionable = m.build_projection_scenarios(
            matchup(), readiness(status="Questionable", uncertain=True)
        )
        doubtful = m.build_projection_scenarios(
            matchup(), readiness(status="Doubtful", uncertain=True)
        )
        self.assertLess(doubtful["scenarios"]["low"]["minutes"], questionable["scenarios"]["low"]["minutes"])
        self.assertEqual(doubtful["scenarios"]["base"]["minutes"], 30.0)

    def test_probable_has_small_scenario_only_stress(self):
        result = m.build_projection_scenarios(
            matchup(), readiness(status="Probable", uncertain=True)
        )
        self.assertAlmostEqual(result["scenarios"]["low"]["minutes"], 27.0 * 0.975, places=4)
        self.assertFalse(result["scenario_components"]["focal_availability"]["central_projection_penalty_applied"])

    def test_generic_uncertain_status_uses_generic_stress(self):
        result = m.build_projection_scenarios(
            matchup(), readiness(status="Game Time Decision", uncertain=True)
        )
        self.assertAlmostEqual(result["scenarios"]["low"]["minutes"], 27.0 * 0.95, places=4)

    def test_out_player_fails_closed_even_if_it_leaks_past_gate(self):
        with self.assertRaisesRegex(m.WNBAProjectionScenarioNotReadyError, "unavailable/Out"):
            m.build_projection_scenarios(
                matchup(), readiness(status="Out", blocking=True)
            )

    def test_lineup_blocking_share_widens_all_stat_scenarios_without_moving_base(self):
        result = m.build_projection_scenarios(
            matchup(blocking_share=2.0 / 3.0), readiness()
        )
        spread = result["scenario_components"]["context_spread_pct_by_stat"]
        self.assertAlmostEqual(spread["points"], 0.02, places=8)
        self.assertAlmostEqual(result["scenarios"]["low"]["points"], 18.0 * 0.98, places=4)
        self.assertAlmostEqual(result["scenarios"]["high"]["points"], 22.0 * 1.02, places=4)
        self.assertEqual(result["scenarios"]["base"]["points"], 20.0)

    def test_uncertain_lineup_share_has_smaller_spread(self):
        result = m.build_projection_scenarios(
            matchup(uncertain_share=0.5), readiness()
        )
        self.assertAlmostEqual(
            result["scenario_components"]["context_spread_pct_by_stat"]["points"],
            0.0075,
            places=8,
        )

    def test_lineup_share_outside_zero_one_fails_closed(self):
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "outside 0..1"):
            m.build_projection_scenarios(
                matchup(blocking_share=1.2), readiness()
            )

    def test_partial_matchup_context_adds_symmetric_two_percent_spread(self):
        result = m.build_projection_scenarios(
            matchup(context_level="partial"), readiness()
        )
        spreads = result["scenario_components"]["context_spread_pct_by_stat"]
        self.assertEqual(spreads, {"points": 0.02, "rebounds": 0.02, "assists": 0.02})
        self.assertAlmostEqual(result["scenarios"]["low"]["rebounds"], 9.0 * 0.98, places=4)
        self.assertAlmostEqual(result["scenarios"]["high"]["rebounds"], 11.0 * 1.02, places=4)

    def test_invalid_matchup_context_level_fails_closed(self):
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "context level is invalid"):
            m.build_projection_scenarios(
                matchup(context_level="mystery"), readiness()
            )

    def test_unavailable_shot_zone_context_widens_points_only(self):
        result = m.build_projection_scenarios(
            matchup(shot_available=False, shot_applied=False), readiness()
        )
        spreads = result["scenario_components"]["context_spread_pct_by_stat"]
        self.assertEqual(spreads["points"], 0.015)
        self.assertEqual(spreads["rebounds"], 0.0)
        self.assertEqual(spreads["assists"], 0.0)

    def test_low_sample_shot_zone_context_widens_points_by_one_percent(self):
        result = m.build_projection_scenarios(
            matchup(shot_available=True, shot_applied=False), readiness()
        )
        self.assertEqual(
            result["scenario_components"]["context_spread_pct_by_stat"]["points"],
            0.01,
        )

    def test_context_spread_is_capped_per_stat(self):
        with patch.object(m, "PARTIAL_MATCHUP_CONTEXT_SPREAD", 0.06), patch.object(
            m, "LINEUP_BLOCKING_SPREAD_PER_FULL_SHARE", 0.06
        ), patch.object(m, "MAX_LINEUP_CONTEXT_SPREAD", 0.06), patch.object(
            m, "SHOT_ZONE_UNAVAILABLE_POINTS_SPREAD", 0.06
        ):
            spreads, _ = m._context_spreads(
                matchup(
                    context_level="partial",
                    blocking_share=1.0,
                    shot_available=False,
                    shot_applied=False,
                )
            )
        self.assertEqual(spreads["points"], m.MAX_CONTEXT_SPREAD_PER_STAT)
        self.assertEqual(spreads["rebounds"], m.MAX_CONTEXT_SPREAD_PER_STAT)
        self.assertEqual(spreads["assists"], m.MAX_CONTEXT_SPREAD_PER_STAT)

    def test_pra_is_sum_of_components_in_every_scenario(self):
        result = m.build_projection_scenarios(
            matchup(blocking_share=0.5),
            readiness(status="Questionable", uncertain=True),
        )
        for name in ("low", "base", "high"):
            row = result["scenarios"][name]
            self.assertAlmostEqual(
                row["pra"], row["points"] + row["rebounds"] + row["assists"], places=4
            )

    def test_broken_step_5b_pra_fails_closed(self):
        value = matchup()
        value["projection"]["pra"]["expected"] = 36.0
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "PRA does not equal"):
            m.build_projection_scenarios(value, readiness())

    def test_minutes_sensitivity_must_contain_central_projection(self):
        value = matchup()
        value["projection"]["minutes"]["sensitivity_low"] = 31.0
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "minutes sensitivity"):
            m.build_projection_scenarios(value, readiness())

    def test_stat_sensitivity_must_contain_central_projection(self):
        value = matchup()
        value["projection"]["points"]["minutes_sensitivity_high"] = 19.0
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "points minutes sensitivity"):
            m.build_projection_scenarios(value, readiness())

    def test_unexpected_step_5b_model_version_fails_closed(self):
        value = matchup()
        value["model_version"] = "wrong"
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "unexpected Step 5B"):
            m.build_projection_scenarios(value, readiness())

    def test_step_5b_identity_mismatch_fails_closed(self):
        value = matchup()
        value["team_key"] = OPPONENT
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "identity disagrees"):
            m.build_projection_scenarios(value, readiness())

    def test_step_5b_snapshot_reference_mismatch_fails_closed(self):
        value = matchup()
        value["snapshot_reference"]["content_sha256"] = "c" * 64
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "content_sha256"):
            m.build_projection_scenarios(value, readiness())

    def test_not_ready_gate_blocks_before_scenario_build(self):
        with self.assertRaisesRegex(m.WNBAProjectionScenarioNotReadyError, "NOT_READY"):
            m.build_projection_scenarios(matchup(), readiness("NOT_READY"))

    def test_ready_with_warnings_are_preserved_as_context_not_probability(self):
        report = readiness("READY_WITH_WARNINGS", ["observed_minutes_variability"])
        result = m.build_projection_scenarios(matchup(), report)
        self.assertEqual(
            result["scenario_components"]["readiness_warning_ids"],
            ["observed_minutes_variability"],
        )
        self.assertEqual(result["scenarios"]["base"]["points"], 20.0)

    def test_default_scenario_breadth_is_tight(self):
        result = m.build_projection_scenarios(matchup(), readiness())
        self.assertEqual(result["scenario_breadth"]["by_stat"]["points"]["breadth_tier"], "TIGHT")
        self.assertEqual(result["scenario_breadth"]["overall_tier"], "TIGHT")

    def test_questionable_status_can_widen_breadth_to_moderate(self):
        result = m.build_projection_scenarios(
            matchup(), readiness(status="Questionable", uncertain=True)
        )
        self.assertEqual(result["scenario_breadth"]["by_stat"]["points"]["breadth_tier"], "MODERATE")

    def test_scenario_fingerprint_is_deterministic(self):
        first = m.build_projection_scenarios(matchup(), readiness())
        second = m.build_projection_scenarios(matchup(), readiness())
        self.assertEqual(first["scenario_fingerprint_sha256"], second["scenario_fingerprint_sha256"])
        self.assertEqual(first["scenario_id"], second["scenario_id"])

    def test_scenario_fingerprint_changes_with_snapshot_hash(self):
        first_report = readiness()
        second_report = readiness()
        second_report["snapshot"]["content_sha256"] = "c" * 64
        second_report["snapshot_reference"]["content_sha256"] = "c" * 64
        second_matchup = matchup()
        second_matchup["snapshot_reference"]["content_sha256"] = "c" * 64
        first = m.build_projection_scenarios(matchup(), first_report)
        second = m.build_projection_scenarios(second_matchup, second_report)
        self.assertNotEqual(first["scenario_fingerprint_sha256"], second["scenario_fingerprint_sha256"])

    def test_scenario_fingerprint_changes_with_availability_status(self):
        healthy = m.build_projection_scenarios(matchup(), readiness())
        questionable = m.build_projection_scenarios(
            matchup(), readiness(status="Questionable", uncertain=True)
        )
        self.assertNotEqual(
            healthy["scenario_fingerprint_sha256"],
            questionable["scenario_fingerprint_sha256"],
        )

    def test_no_probability_confidence_interval_or_monte_carlo_claims(self):
        result = m.build_projection_scenarios(matchup(), readiness())
        self.assertTrue(result["guardrails"]["no_confidence_interval_created"])
        self.assertTrue(result["guardrails"]["no_empirical_standard_deviation_invented"])
        self.assertTrue(result["guardrails"]["no_betting_probability_created"])
        self.assertTrue(result["guardrails"]["no_monte_carlo_created"])
        self.assertTrue(result["projection_semantics"]["low_high_are_not_probability_quantiles"])

    def test_lineup_disruption_never_redistributes_teammate_opportunity(self):
        result = m.build_projection_scenarios(
            matchup(blocking_share=1.0), readiness()
        )
        self.assertTrue(
            result["guardrails"]["lineup_disruption_does_not_redistribute_teammate_opportunity"]
        )
        self.assertEqual(result["scenarios"]["base"]["points"], 20.0)

    @patch("sports_api.wnba_projection_scenarios.project_matchup_adjusted_from_readiness")
    def test_project_from_readiness_uses_exact_same_readiness_package(self, project_5b):
        project_5b.return_value = matchup()
        report = readiness()
        result = m.project_scenarios_from_readiness(report)
        self.assertEqual(result["player_id"], PLAYER_ID)
        project_5b.assert_called_once_with(report)

    @patch("sports_api.wnba_projection_scenarios.project_matchup_adjusted_from_readiness")
    def test_project_from_readiness_translates_5b_not_ready(self, project_5b):
        project_5b.side_effect = WNBAMatchupAdjustedProjectionNotReadyError("blocked")
        with self.assertRaisesRegex(m.WNBAProjectionScenarioNotReadyError, "blocked"):
            m.project_scenarios_from_readiness(readiness())

    @patch("sports_api.wnba_projection_scenarios.project_matchup_adjusted_from_readiness")
    def test_project_from_readiness_translates_5b_model_input(self, project_5b):
        project_5b.side_effect = WNBAMatchupAdjustedProjectionModelInputError("bad model input")
        with self.assertRaisesRegex(m.WNBAProjectionScenarioModelInputError, "bad model input"):
            m.project_scenarios_from_readiness(readiness())

    @patch("sports_api.wnba_projection_scenarios.project_matchup_adjusted_from_readiness")
    def test_project_from_readiness_translates_5b_upstream(self, project_5b):
        project_5b.side_effect = WNBAMatchupAdjustedProjectionUpstreamError("upstream")
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "upstream"):
            m.project_scenarios_from_readiness(readiness())

    @patch("sports_api.wnba_projection_scenarios.get_player_game_model_input_readiness")
    @patch("sports_api.wnba_projection_scenarios.project_matchup_adjusted_from_readiness")
    def test_wrapper_requests_exact_5c_required_context(self, project_5b, gate):
        gate.return_value = readiness()
        project_5b.return_value = matchup()
        result = m.get_player_game_projection_scenarios(PLAYER_ID, GAME_ID, 2026)
        self.assertEqual(result["game_id"], GAME_ID)
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

    @patch("sports_api.wnba_projection_scenarios.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_not_found(self, gate):
        gate.side_effect = WNBAModelInputReadinessNotFoundError("missing")
        with self.assertRaisesRegex(m.WNBAProjectionScenarioNotFoundError, "missing"):
            m.get_player_game_projection_scenarios(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_projection_scenarios.get_player_game_model_input_readiness")
    def test_wrapper_translates_readiness_upstream(self, gate):
        gate.side_effect = WNBAModelInputReadinessUpstreamError("upstream")
        with self.assertRaisesRegex(m.WNBAProjectionScenarioUpstreamError, "upstream"):
            m.get_player_game_projection_scenarios(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_projection_scenarios.get_player_game_model_input_readiness")
    def test_invalid_player_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            m.get_player_game_projection_scenarios(0, GAME_ID, 2026)
        gate.assert_not_called()

    @patch("sports_api.wnba_projection_scenarios.get_player_game_model_input_readiness")
    def test_invalid_game_id_fails_before_network(self, gate):
        with self.assertRaisesRegex(ValueError, "10 numeric digits"):
            m.get_player_game_projection_scenarios(PLAYER_ID, "bad", 2026)
        gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
