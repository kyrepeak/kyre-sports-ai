import unittest
from copy import deepcopy
from unittest.mock import patch

from sports_api import wnba_baseline_projection as m


GAME_ID = "1022600284"
PLAYER_ID = 12345
TEAM = "chicago-sky"
OPPONENT = "connecticut-sun"


def role_row(role, minutes, points, rebounds, assists, games=5, team_key=TEAM):
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


def opportunity():
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
            "data_quality": {
                "feature_eligible_share_of_selected_lineup_events": 0.92,
            },
            "own_event_counts_per_feature_game": {
                "points": 14.0,
                "rebounds": 7.0,
                "assists": 3.0,
            },
        },
        "observed_role_context": {
            "available": True,
            "error": None,
            "role_summary": {
                "starter_games": 3,
                "bench_games": 2,
                "starter_game_share": 0.6,
                "primary_observed_role": "starter",
            },
            "starter": role_row("Starters", 32.0, 16.0, 8.0, 4.0, games=3),
            "bench": role_row("Bench", 20.0, 8.0, 6.0, 2.0, games=2),
            "observed_role_band": "mixed_starter_bench_history",
        },
    }


def snapshot():
    return {
        "snapshot_id": "wnba-4w-test",
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
        "inputs": {
            "player_opportunity_context": opportunity(),
            "game_availability": {
                "away": {
                    "team_key": TEAM,
                    "players": [
                        {
                            "player_id": PLAYER_ID,
                            "player_name": "Test Player",
                            "injury_report_status": None,
                            "availability_class": "not_listed",
                            "availability_blocking": False,
                            "availability_uncertain": False,
                        }
                    ],
                },
                "home": {"team_key": OPPONENT, "players": []},
            },
        },
    }


def readiness(state="READY", warning_ids=None):
    snap = snapshot()
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


class WNBABaselineProjectionTests(unittest.TestCase):
    def test_minutes_projection_uses_versioned_mean_median_blend(self):
        result = m.project_from_readiness_report(readiness())
        minutes = result["projection"]["minutes"]
        self.assertAlmostEqual(minutes["expected"], 31.2, places=4)
        self.assertAlmostEqual(minutes["sensitivity_low"], 29.2, places=4)
        self.assertAlmostEqual(minutes["sensitivity_high"], 33.2, places=4)
        self.assertEqual(result["model_inputs"]["minutes"]["weights"], {"median": 0.6, "mean": 0.4})

    def test_starter_bench_rates_blend_by_observed_start_share(self):
        result = m.project_from_readiness_report(readiness())
        rates = result["model_inputs"]["role_rates"]["stats"]
        self.assertAlmostEqual(rates["points"]["rate_per_minute"], 0.46, places=8)
        self.assertAlmostEqual(rates["rebounds"]["rate_per_minute"], 0.27, places=8)
        self.assertAlmostEqual(rates["assists"]["rate_per_minute"], 0.115, places=8)
        self.assertEqual(rates["points"]["weights"], {"starter": 0.6, "bench": 0.4})

    def test_projection_math_is_reproducible(self):
        result = m.project_from_readiness_report(readiness())
        p = result["projection"]
        self.assertAlmostEqual(p["points"]["expected"], 14.352, places=4)
        self.assertAlmostEqual(p["rebounds"]["expected"], 8.424, places=4)
        self.assertAlmostEqual(p["assists"]["expected"], 3.588, places=4)
        self.assertAlmostEqual(p["pra"]["expected"], 26.364, places=4)

    def test_pra_equals_component_expectations(self):
        result = m.project_from_readiness_report(readiness())
        projection = result["projection"]
        total = projection["points"]["expected"] + projection["rebounds"]["expected"] + projection["assists"]["expected"]
        self.assertAlmostEqual(projection["pra"]["expected"], total, places=4)

    def test_minutes_sensitivity_is_not_called_probability_interval(self):
        result = m.project_from_readiness_report(readiness())
        self.assertTrue(result["projection_semantics"]["minutes_sensitivity_is_not_probability_interval"])
        self.assertIn("not confidence intervals", result["projection"]["points"]["sensitivity_semantics"])

    def test_minutes_projection_caps_regulation_baseline_at_40(self):
        report = readiness()
        stability = report["snapshot"]["inputs"]["player_opportunity_context"]["observed_minutes_opportunity"]["tracked_minutes"]["stability"]
        stability.update({
            "tracked_minutes_mean": 44.0,
            "tracked_minutes_median": 43.0,
            "tracked_minutes_min": 41.0,
            "tracked_minutes_max": 47.0,
            "tracked_minutes_population_stddev": 3.0,
        })
        result = m.project_from_readiness_report(report)
        self.assertEqual(result["projection"]["minutes"]["expected"], 40.0)
        self.assertEqual(result["projection"]["minutes"]["sensitivity_high"], 40.0)

    def test_starter_only_role_source_is_supported(self):
        report = readiness()
        role = report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]
        role["bench"] = None
        result = m.project_from_readiness_report(report)
        self.assertAlmostEqual(result["model_inputs"]["role_rates"]["stats"]["points"]["rate_per_minute"], 0.5, places=8)
        self.assertEqual(result["model_inputs"]["role_rates"]["stats"]["points"]["method"], "starter_rate_only_available_role_split")

    def test_bench_only_role_source_is_supported(self):
        report = readiness()
        role = report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]
        role["starter"] = None
        result = m.project_from_readiness_report(report)
        self.assertAlmostEqual(result["model_inputs"]["role_rates"]["stats"]["points"]["rate_per_minute"], 0.4, places=8)
        self.assertEqual(result["model_inputs"]["role_rates"]["stats"]["points"]["method"], "bench_rate_only_available_role_split")

    def test_both_role_sources_require_valid_start_share(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]["role_summary"]["starter_game_share"] = None
        with self.assertRaisesRegex(m.WNBABaselineProjectionModelInputError, "starter_game_share"):
            m.project_from_readiness_report(report)

    def test_invalid_start_share_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]["role_summary"]["starter_game_share"] = 1.2
        with self.assertRaisesRegex(m.WNBABaselineProjectionUpstreamError, "outside 0..1"):
            m.project_from_readiness_report(report)

    def test_missing_role_context_is_model_specific_hard_stop(self):
        report = readiness("READY_WITH_WARNINGS", ["optional_starter_bench_role"])
        report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"] = {"available": False}
        with self.assertRaisesRegex(m.WNBABaselineProjectionModelInputError, "starter/bench role context"):
            m.project_from_readiness_report(report)

    def test_zero_role_minutes_does_not_create_fake_rate(self):
        report = readiness()
        role = report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]
        role["starter"]["stats"]["minutes"] = 0.0
        role["bench"]["stats"]["minutes"] = 0.0
        with self.assertRaisesRegex(m.WNBABaselineProjectionModelInputError, "no valid official role rate"):
            m.project_from_readiness_report(report)

    def test_negative_role_stat_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]["starter"]["stats"]["points"] = -1
        with self.assertRaisesRegex(m.WNBABaselineProjectionModelInputError, "nonnegative"):
            m.project_from_readiness_report(report)

    def test_not_ready_gate_blocks_model(self):
        with self.assertRaisesRegex(m.WNBABaselineProjectionNotReadyError, "blockers: bad"):
            m.project_from_readiness_report(readiness("NOT_READY"))

    def test_ready_with_warnings_is_allowed_and_propagated(self):
        result = m.project_from_readiness_report(readiness("READY_WITH_WARNINGS", ["focal_player_game_availability"]))
        self.assertTrue(result["readiness"]["projection_allowed_with_warnings"])
        self.assertEqual(result["readiness"]["warning_ids"], ["focal_player_game_availability"])

    def test_questionable_status_does_not_automatically_reduce_minutes(self):
        report = readiness("READY_WITH_WARNINGS", ["focal_player_game_availability"])
        row = report["snapshot"]["inputs"]["game_availability"]["away"]["players"][0]
        row.update({
            "injury_report_status": "Questionable",
            "availability_class": "uncertain",
            "availability_uncertain": True,
        })
        result = m.project_from_readiness_report(report)
        self.assertEqual(result["projection"]["minutes"]["expected"], 31.2)
        self.assertFalse(result["availability_condition"]["automatic_injury_minutes_penalty_applied"])
        self.assertTrue(result["availability_condition"]["conditional_on_player_active"])

    def test_event_counts_are_diagnostic_only(self):
        result = m.project_from_readiness_report(readiness())
        diagnostic = result["model_inputs"]["event_quality_diagnostics"]
        self.assertTrue(diagnostic["available"])
        self.assertIn("diagnostic_only", diagnostic["usage_in_step_5a"])
        self.assertTrue(result["guardrails"]["step_4u_event_counts_are_diagnostic_not_treated_as_complete_box_score"])

    def test_wrong_opportunity_player_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_opportunity_context"]["player_id"] = 999
        with self.assertRaisesRegex(m.WNBABaselineProjectionUpstreamError, "wrong player ID"):
            m.project_from_readiness_report(report)

    def test_wrong_opportunity_team_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_opportunity_context"]["latest_observed_team_key"] = OPPONENT
        with self.assertRaisesRegex(m.WNBABaselineProjectionUpstreamError, "wrong focal team"):
            m.project_from_readiness_report(report)

    def test_role_row_team_conflict_fails_closed(self):
        report = readiness()
        report["snapshot"]["inputs"]["player_opportunity_context"]["observed_role_context"]["starter"]["team_key"] = OPPONENT
        with self.assertRaisesRegex(m.WNBABaselineProjectionUpstreamError, "conflicting team identity"):
            m.project_from_readiness_report(report)

    def test_snapshot_reference_mismatch_fails_closed(self):
        report = readiness()
        report["snapshot_reference"]["content_sha256"] = "b" * 64
        with self.assertRaisesRegex(m.WNBABaselineProjectionUpstreamError, "content_sha256"):
            m.project_from_readiness_report(report)

    def test_projection_fingerprint_is_deterministic_for_same_evidence(self):
        first = m.project_from_readiness_report(readiness())
        second = m.project_from_readiness_report(readiness())
        self.assertEqual(first["projection_fingerprint_sha256"], second["projection_fingerprint_sha256"])
        self.assertEqual(first["projection_id"], second["projection_id"])

    def test_projection_fingerprint_changes_with_snapshot_hash(self):
        first_report = readiness()
        second_report = readiness()
        second_report["snapshot"]["content_sha256"] = "c" * 64
        second_report["snapshot_reference"]["content_sha256"] = "c" * 64
        first = m.project_from_readiness_report(first_report)
        second = m.project_from_readiness_report(second_report)
        self.assertNotEqual(first["projection_fingerprint_sha256"], second["projection_fingerprint_sha256"])

    def test_no_market_or_matchup_adjustments_in_5a(self):
        result = m.project_from_readiness_report(readiness())
        config = result["model_config"]
        self.assertFalse(config["matchup_adjustment"])
        self.assertFalse(config["pace_adjustment"])
        self.assertFalse(config["travel_adjustment"])
        self.assertFalse(config["officiating_adjustment"])
        self.assertTrue(result["guardrails"]["no_sportsbook_data_used"])
        self.assertTrue(result["guardrails"]["no_monte_carlo_created"])

    @patch("sports_api.wnba_baseline_projection.get_player_game_model_input_readiness")
    def test_wrapper_requests_only_5a_required_snapshot_context(self, gate):
        gate.return_value = readiness()
        result = m.get_player_game_baseline_projection(PLAYER_ID, GAME_ID, 2026)
        self.assertEqual(result["player_id"], PLAYER_ID)
        gate.assert_called_once_with(
            PLAYER_ID,
            GAME_ID,
            2026,
            season_type="Regular Season",
            last_n_games=5,
            require_current_availability=True,
            include_shot_context=False,
            include_advanced_context=False,
            include_officiating_context=False,
            max_snapshot_age_minutes=m.DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
            include_snapshot=True,
        )

    @patch("sports_api.wnba_baseline_projection.get_player_game_model_input_readiness")
    def test_readiness_not_found_is_translated(self, gate):
        gate.side_effect = m.WNBAModelInputReadinessNotFoundError("missing")
        with self.assertRaises(m.WNBABaselineProjectionNotFoundError):
            m.get_player_game_baseline_projection(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_baseline_projection.get_player_game_model_input_readiness")
    def test_readiness_upstream_error_is_translated(self, gate):
        gate.side_effect = m.WNBAModelInputReadinessUpstreamError("broken")
        with self.assertRaises(m.WNBABaselineProjectionUpstreamError):
            m.get_player_game_baseline_projection(PLAYER_ID, GAME_ID, 2026)

    def test_validation_happens_before_readiness_network_path(self):
        with patch("sports_api.wnba_baseline_projection.get_player_game_model_input_readiness") as gate:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_game_baseline_projection(0, GAME_ID, 2026)
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                m.get_player_game_baseline_projection(PLAYER_ID, "123", 2026)
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_player_game_baseline_projection(PLAYER_ID, GAME_ID, 2026, last_n_games=0)
            gate.assert_not_called()

    def test_model_is_conditional_on_active_player(self):
        result = m.project_from_readiness_report(readiness())
        self.assertTrue(result["projection_semantics"]["conditional_on_player_active"])
        self.assertTrue(result["availability_condition"]["conditional_on_player_active"])


if __name__ == "__main__":
    unittest.main()
