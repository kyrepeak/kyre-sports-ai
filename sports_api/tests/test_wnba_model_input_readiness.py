import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from sports_api import wnba_model_input_readiness as m


GAME_ID = "1022600284"
PLAYER_ID = 12345
AWAY = "chicago-sky"
HOME = "connecticut-sun"
EVALUATED = datetime(2026, 8, 26, 16, 0, 0, tzinfo=timezone.utc)


def _status(requested=True, available=True, error=None):
    return {
        "requested": requested,
        "available": available,
        "error": error,
        "component": "x",
    }


def _rehash(snap):
    snap["content_sha256"] = m._canonical_hash(m._snapshot_hash_content(snap))
    snap["snapshot_id"] = f"wnba-4w-{GAME_ID}-{PLAYER_ID}-{snap['content_sha256'][:16]}"
    return snap


def _snapshot():
    focal_availability = {
        "player_id": PLAYER_ID,
        "player_name": "Focal Player",
        "injury_report_status": None,
        "availability_class": "not_listed",
        "availability_blocking": False,
        "availability_uncertain": False,
    }
    report = {
        "report_timestamp_eastern": "2026-08-26T10:00:00-04:00",
        "retrieved_at_utc": "2026-08-26T15:55:00+00:00",
    }
    snap = {
        "source": "Step 4W",
        "data_type": "content_addressed_pre_model_projection_input_snapshot",
        "schema_version": "wnba_step_4w_v1",
        "snapshot_id": None,
        "content_sha256": None,
        "captured_at_utc": "2026-08-26T15:59:00+00:00",
        "finalized_at_utc": "2026-08-26T15:59:30+00:00",
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "recent_window_games": 5,
        "game_identity": {
            "game_id": GAME_ID,
            "date": "2026-08-26",
            "away_team_key": AWAY,
            "home_team_key": HOME,
            "game_datetime_utc": "2026-08-27T00:00:00+00:00",
            "game_datetime_eastern": "2026-08-26T20:00:00-04:00",
            "venue": {"name": "Arena"},
            "status": {"category": "scheduled"},
            "schedule_change": {"cancelled": False, "postponed": False},
        },
        "focal_identity": {
            "player_id": PLAYER_ID,
            "team_key": HOME,
            "side": "home",
            "opponent_team_key": AWAY,
        },
        "availability_summary": {
            "focal_player_current_roster_match": True,
            "focal_player_availability": deepcopy(focal_availability),
            "injury_report": deepcopy(report),
        },
        "component_status": {
            "game_availability": _status(),
            "player_recent_shot_chart": _status(),
            "player_vs_opponent_shot_chart": _status(),
            "opponent_defense_by_shot_zone": _status(),
            "player_advanced": _status(),
            "team_advanced": _status(),
            "opponent_advanced": _status(),
            "game_whistle_context": _status(),
        },
        "source_timestamps": [
            {
                "path": "inputs.game_availability.retrieved_at_utc",
                "value": "2026-08-26T15:55:00+00:00",
            },
            {
                "path": "inputs.game_availability.injury_report.report_timestamp_eastern",
                "value": "2026-08-26T10:00:00-04:00",
            },
        ],
        "inputs": {
            "player_opportunity_context": {
                "player_id": PLAYER_ID,
                "latest_observed_team_key": HOME,
                "components": {
                    "rotation": {"available": True},
                    "event_features": {"available": True},
                    "starter_bench_role": {"available": True},
                    "five_player_lineups": {"available": True},
                },
                "observed_minutes_opportunity": {
                    "source_game_count": 5,
                    "tracked_minutes": {
                        "stability": {
                            "rotation_game_count": 5,
                            "tracked_minutes_coefficient_of_variation": 0.10,
                        }
                    },
                },
                "observed_event_opportunity": {
                    "feature_game_count": 5,
                    "data_quality": {
                        "feature_eligible_share_of_selected_lineup_events": 0.95,
                    },
                },
            },
            "game_rest_travel_context": {
                "game": {"game_id": GAME_ID},
                "away_team_key": AWAY,
                "home_team_key": HOME,
            },
            "game_availability": {
                "game_id": GAME_ID,
                "date": "2026-08-26",
                "away": {"team_key": AWAY, "players": []},
                "home": {"team_key": HOME, "players": [deepcopy(focal_availability)]},
                "injury_report": deepcopy(report),
                "verification": {
                    "injury_report_game_present": True,
                    "injury_report_submission_complete": True,
                },
            },
            "player_recent_shot_chart": {"player_id": PLAYER_ID},
            "player_vs_opponent_shot_chart": {"player_id": PLAYER_ID},
            "opponent_defense_by_shot_zone": {"team_key": AWAY},
            "player_advanced": {"filters": {"player_id": PLAYER_ID}},
            "team_advanced": {"team_key": HOME},
            "opponent_advanced": {"team_key": AWAY},
            "game_whistle_context": {"game_id": GAME_ID},
            "matchup_source_status": {
                "official_player_defender_matchup_available": False,
                "no_matchups_data_for_wnba_yet": True,
            },
        },
        "guardrails": {
            "snapshot_is_pre_model_input_not_projection": True,
            "no_projected_minutes_created": True,
            "no_projected_starters_created": True,
            "no_missing_teammate_opportunity_redistribution_created": True,
            "no_monte_carlo_created": True,
            "no_sportsbook_data_created": True,
            "no_betting_probability_created": True,
            "court_context_is_not_defender_assignment": True,
            "official_wnba_player_defender_assignment_remains_unavailable": True,
        },
        "verification": {
            "required_step_4v_opportunity_available": True,
            "required_official_game_schedule_rest_travel_available": True,
            "focal_latest_observed_team_is_in_requested_game": True,
            "opponent_resolved_from_official_game_identity": True,
            "step_4v_availability_disabled_to_avoid_duplicate_snapshot_report_fetch": True,
            "game_level_availability_captures_both_teams_when_available": True,
            "optional_returned_components_identity_checked": True,
            "optional_source_failures_do_not_fabricate_values": True,
            "content_hash_created": True,
        },
    }
    return _rehash(snap)


def _eval(snap, **kwargs):
    return m.evaluate_projection_input_snapshot(
        snap,
        evaluated_at_utc=EVALUATED,
        **kwargs,
    )


def _raw_focal(snap):
    return snap["inputs"]["game_availability"]["home"]["players"][0]


class WNBAModelInputReadinessTests(unittest.TestCase):
    def test_strong_snapshot_is_ready(self):
        result = _eval(_snapshot())
        self.assertEqual(result["readiness"], "READY")
        self.assertTrue(result["can_start_projection"])
        self.assertEqual(result["summary"]["blocker_count"], 0)
        self.assertEqual(result["summary"]["warning_count"], 0)
        self.assertEqual(result["diagnostic_data_quality_score"], 100)

    def test_rotation_coverage_below_preferred_is_warning(self):
        snap = _snapshot()
        opp = snap["inputs"]["player_opportunity_context"]
        opp["observed_minutes_opportunity"]["source_game_count"] = 3
        opp["observed_minutes_opportunity"]["tracked_minutes"]["stability"]["rotation_game_count"] = 3
        _rehash(snap)
        result = _eval(snap)
        self.assertEqual(result["readiness"], "READY_WITH_WARNINGS")
        self.assertIn("rotation_game_coverage", result["summary"]["warning_ids"])

    def test_rotation_coverage_below_minimum_blocks(self):
        snap = _snapshot()
        opp = snap["inputs"]["player_opportunity_context"]
        opp["observed_minutes_opportunity"]["source_game_count"] = 2
        opp["observed_minutes_opportunity"]["tracked_minutes"]["stability"]["rotation_game_count"] = 2
        _rehash(snap)
        result = _eval(snap)
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertIn("rotation_game_coverage", result["summary"]["blocker_ids"])

    def test_event_feature_coverage_below_minimum_blocks(self):
        snap = _snapshot()
        snap["inputs"]["player_opportunity_context"]["observed_event_opportunity"]["feature_game_count"] = 2
        _rehash(snap)
        self.assertIn("event_feature_game_coverage", _eval(snap)["summary"]["blocker_ids"])

    def test_feature_eligible_share_warning_band(self):
        snap = _snapshot()
        snap["inputs"]["player_opportunity_context"]["observed_event_opportunity"]["data_quality"]["feature_eligible_share_of_selected_lineup_events"] = 0.70
        _rehash(snap)
        self.assertIn("feature_eligible_event_share", _eval(snap)["summary"]["warning_ids"])

    def test_feature_eligible_share_below_minimum_blocks(self):
        snap = _snapshot()
        snap["inputs"]["player_opportunity_context"]["observed_event_opportunity"]["data_quality"]["feature_eligible_share_of_selected_lineup_events"] = 0.50
        _rehash(snap)
        self.assertIn("feature_eligible_event_share", _eval(snap)["summary"]["blocker_ids"])

    def test_missing_role_context_warns(self):
        snap = _snapshot()
        snap["inputs"]["player_opportunity_context"]["components"]["starter_bench_role"] = {"available": False}
        _rehash(snap)
        self.assertIn("optional_starter_bench_role", _eval(snap)["summary"]["warning_ids"])

    def test_missing_lineup_context_warns(self):
        snap = _snapshot()
        snap["inputs"]["player_opportunity_context"]["components"]["five_player_lineups"] = {"available": False}
        _rehash(snap)
        self.assertIn("optional_five_player_lineups", _eval(snap)["summary"]["warning_ids"])

    def test_high_observed_minute_variability_warns(self):
        snap = _snapshot()
        snap["inputs"]["player_opportunity_context"]["observed_minutes_opportunity"]["tracked_minutes"]["stability"]["tracked_minutes_coefficient_of_variation"] = 0.50
        _rehash(snap)
        self.assertIn("observed_minutes_variability", _eval(snap)["summary"]["warning_ids"])

    def test_required_availability_not_requested_blocks(self):
        snap = _snapshot()
        snap["component_status"]["game_availability"] = _status(False, False)
        snap["inputs"].pop("game_availability")
        snap["availability_summary"] = None
        _rehash(snap)
        self.assertIn("current_availability_requested", _eval(snap)["summary"]["blocker_ids"])

    def test_availability_can_be_optional_without_warning(self):
        snap = _snapshot()
        snap["component_status"]["game_availability"] = _status(False, False)
        snap["inputs"].pop("game_availability")
        snap["availability_summary"] = None
        _rehash(snap)
        self.assertEqual(_eval(snap, require_current_availability=False)["readiness"], "READY")

    def test_focal_current_roster_mismatch_blocks(self):
        snap = _snapshot()
        snap["inputs"]["game_availability"]["home"]["players"] = []
        snap["availability_summary"]["focal_player_current_roster_match"] = False
        snap["availability_summary"]["focal_player_availability"] = None
        _rehash(snap)
        self.assertIn("focal_current_roster_match", _eval(snap)["summary"]["blocker_ids"])

    def test_focal_player_out_blocks(self):
        snap = _snapshot()
        changes = {"injury_report_status": "Out", "availability_class": "unavailable", "availability_blocking": True}
        _raw_focal(snap).update(changes)
        snap["availability_summary"]["focal_player_availability"].update(changes)
        _rehash(snap)
        self.assertIn("focal_player_game_availability", _eval(snap)["summary"]["blocker_ids"])

    def test_questionable_player_warns(self):
        snap = _snapshot()
        changes = {"injury_report_status": "Questionable", "availability_class": "uncertain", "availability_uncertain": True}
        _raw_focal(snap).update(changes)
        snap["availability_summary"]["focal_player_availability"].update(changes)
        _rehash(snap)
        self.assertIn("focal_player_game_availability", _eval(snap)["summary"]["warning_ids"])

    def test_unhashed_availability_summary_tampering_blocks(self):
        snap = _snapshot()
        snap["availability_summary"]["focal_player_availability"]["injury_report_status"] = "Out"
        result = _eval(snap)
        self.assertIn("availability_summary_integrity", result["summary"]["blocker_ids"])
        self.assertNotIn("snapshot_content_hash", result["summary"]["blocker_ids"])

    def test_missing_report_game_near_tip_blocks(self):
        snap = _snapshot()
        snap["inputs"]["game_availability"]["verification"]["injury_report_game_present"] = False
        _rehash(snap)
        self.assertIn("injury_report_game_present", _eval(snap)["summary"]["blocker_ids"])

    def test_missing_report_game_far_from_tip_warns(self):
        snap = _snapshot()
        snap["game_identity"]["game_datetime_utc"] = "2026-08-29T00:00:00+00:00"
        snap["inputs"]["game_availability"]["verification"]["injury_report_game_present"] = False
        _rehash(snap)
        result = _eval(snap)
        self.assertIn("injury_report_game_present", result["summary"]["warning_ids"])
        self.assertNotIn("injury_report_game_present", result["summary"]["blocker_ids"])

    def test_stale_injury_report_near_tip_blocks(self):
        snap = _snapshot()
        value = "2026-08-25T10:00:00-04:00"
        snap["inputs"]["game_availability"]["injury_report"]["report_timestamp_eastern"] = value
        snap["availability_summary"]["injury_report"]["report_timestamp_eastern"] = value
        _rehash(snap)
        self.assertIn("injury_report_freshness", _eval(snap)["summary"]["blocker_ids"])

    def test_moderately_old_injury_report_warns(self):
        snap = _snapshot()
        value = "2026-08-26T01:00:00-04:00"
        snap["inputs"]["game_availability"]["injury_report"]["report_timestamp_eastern"] = value
        snap["availability_summary"]["injury_report"]["report_timestamp_eastern"] = value
        _rehash(snap)
        self.assertIn("injury_report_freshness", _eval(snap)["summary"]["warning_ids"])

    def test_hash_mismatch_blocks_even_with_good_inputs(self):
        snap = _snapshot()
        snap["content_sha256"] = "0" * 64
        result = _eval(snap)
        self.assertIn("snapshot_content_hash", result["summary"]["blocker_ids"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_stale_snapshot_blocks(self):
        snap = _snapshot()
        snap["captured_at_utc"] = "2026-08-26T15:00:00+00:00"
        snap["finalized_at_utc"] = "2026-08-26T15:00:30+00:00"
        self.assertIn("snapshot_age", _eval(snap)["summary"]["blocker_ids"])

    def test_future_snapshot_clock_skew_blocks(self):
        snap = _snapshot()
        snap["captured_at_utc"] = "2026-08-26T16:10:00+00:00"
        snap["finalized_at_utc"] = "2026-08-26T16:10:01+00:00"
        self.assertIn("snapshot_clock_skew", _eval(snap)["summary"]["blocker_ids"])

    def test_live_game_blocks_pregame_gate(self):
        snap = _snapshot()
        snap["game_identity"]["status"]["category"] = "live"
        _rehash(snap)
        self.assertIn("pregame_status", _eval(snap)["summary"]["blocker_ids"])

    def test_final_game_blocks_pregame_gate(self):
        snap = _snapshot()
        snap["game_identity"]["status"]["category"] = "final"
        _rehash(snap)
        self.assertIn("pregame_status", _eval(snap)["summary"]["blocker_ids"])

    def test_scheduled_game_with_passed_tip_blocks(self):
        snap = _snapshot()
        snap["game_identity"]["game_datetime_utc"] = "2026-08-26T14:00:00+00:00"
        _rehash(snap)
        self.assertIn("game_tip_not_passed", _eval(snap)["summary"]["blocker_ids"])

    def test_cancelled_game_blocks(self):
        snap = _snapshot()
        snap["game_identity"]["schedule_change"]["cancelled"] = True
        _rehash(snap)
        self.assertIn("game_schedule_active", _eval(snap)["summary"]["blocker_ids"])

    def test_focal_identity_mismatch_blocks(self):
        snap = _snapshot()
        snap["focal_identity"]["opponent_team_key"] = "seattle-storm"
        _rehash(snap)
        self.assertIn("game_focal_identity_consistency", _eval(snap)["summary"]["blocker_ids"])

    def test_official_defender_matchup_unavailability_does_not_downgrade(self):
        snap = _snapshot()
        snap["inputs"]["matchup_source_status"] = {
            "official_player_defender_matchup_available": False,
            "no_matchups_data_for_wnba_yet": True,
            "wnba_boxscorematchupsv3_defunct": True,
        }
        _rehash(snap)
        result = _eval(snap)
        self.assertEqual(result["readiness"], "READY")
        self.assertTrue(result["guardrails"]["official_defender_matchup_unavailability_is_not_penalized"])

    def test_requested_shot_context_outage_warns(self):
        snap = _snapshot()
        snap["component_status"]["player_recent_shot_chart"] = _status(True, False, "unavailable")
        snap["inputs"].pop("player_recent_shot_chart")
        _rehash(snap)
        self.assertIn("shot_context_coverage", _eval(snap)["summary"]["warning_ids"])

    def test_unrequested_shot_context_is_informational_only(self):
        snap = _snapshot()
        for name in ("player_recent_shot_chart", "player_vs_opponent_shot_chart", "opponent_defense_by_shot_zone"):
            snap["component_status"][name] = _status(False, False)
            snap["inputs"].pop(name)
        _rehash(snap)
        self.assertEqual(_eval(snap)["readiness"], "READY")

    def test_future_source_timestamp_blocks(self):
        snap = _snapshot()
        snap["source_timestamps"].append({
            "path": "inputs.team_advanced.retrieved_at_utc",
            "value": "2026-08-26T16:30:00+00:00",
        })
        self.assertIn("source_timestamp_clock_skew", _eval(snap)["summary"]["blocker_ids"])

    def test_missing_opportunity_input_fails_closed(self):
        snap = _snapshot()
        snap["inputs"].pop("player_opportunity_context")
        _rehash(snap)
        result = _eval(snap)
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertIn("player_opportunity_component", result["summary"]["blocker_ids"])

    def test_blocker_overrides_high_diagnostic_score(self):
        snap = _snapshot()
        snap["game_identity"]["status"]["category"] = "live"
        _rehash(snap)
        result = _eval(snap)
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertFalse(result["can_start_projection"])
        self.assertGreater(result["diagnostic_data_quality_score"], 0)

    @patch("sports_api.wnba_model_input_readiness.get_player_game_projection_input_snapshot")
    @patch("sports_api.wnba_model_input_readiness._utc_now")
    def test_getter_builds_fresh_snapshot_then_evaluates(self, utc_now, get_snapshot):
        utc_now.return_value = EVALUATED
        get_snapshot.return_value = _snapshot()
        result = m.get_player_game_model_input_readiness(PLAYER_ID, GAME_ID, 2026)
        self.assertEqual(result["readiness"], "READY")
        self.assertFalse(result["snapshot_included"])
        get_snapshot.assert_called_once_with(
            PLAYER_ID,
            GAME_ID,
            2026,
            season_type="Regular Season",
            last_n_games=5,
            include_current_availability=True,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=True,
        )

    @patch("sports_api.wnba_model_input_readiness.get_player_game_projection_input_snapshot")
    @patch("sports_api.wnba_model_input_readiness._utc_now")
    def test_getter_can_include_full_snapshot(self, utc_now, get_snapshot):
        utc_now.return_value = EVALUATED
        snap = _snapshot()
        get_snapshot.return_value = snap
        result = m.get_player_game_model_input_readiness(PLAYER_ID, GAME_ID, 2026, include_snapshot=True)
        self.assertTrue(result["snapshot_included"])
        self.assertEqual(result["snapshot"]["content_sha256"], snap["content_sha256"])

    def test_validation_happens_before_snapshot_network_call(self):
        with patch("sports_api.wnba_model_input_readiness.get_player_game_projection_input_snapshot") as get_snapshot:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_game_model_input_readiness(0, GAME_ID, 2026)
            with self.assertRaisesRegex(ValueError, "1 through 1440"):
                m.get_player_game_model_input_readiness(PLAYER_ID, GAME_ID, 2026, max_snapshot_age_minutes=0)
            get_snapshot.assert_not_called()

    @patch("sports_api.wnba_model_input_readiness.get_player_game_projection_input_snapshot")
    def test_snapshot_not_found_is_translated(self, get_snapshot):
        get_snapshot.side_effect = m.WNBAProjectionInputSnapshotNotFoundError("missing")
        with self.assertRaises(m.WNBAModelInputReadinessNotFoundError):
            m.get_player_game_model_input_readiness(PLAYER_ID, GAME_ID, 2026)

    @patch("sports_api.wnba_model_input_readiness.get_player_game_projection_input_snapshot")
    def test_snapshot_upstream_failure_is_translated(self, get_snapshot):
        get_snapshot.side_effect = m.WNBAProjectionInputSnapshotUpstreamError("bad upstream")
        with self.assertRaises(m.WNBAModelInputReadinessUpstreamError):
            m.get_player_game_model_input_readiness(PLAYER_ID, GAME_ID, 2026)

    def test_gate_guardrails_remain_pre_model_only(self):
        result = _eval(_snapshot())
        self.assertTrue(result["guardrails"]["gate_does_not_create_projected_minutes"])
        self.assertTrue(result["guardrails"]["gate_does_not_create_monte_carlo"])
        self.assertTrue(result["guardrails"]["gate_does_not_create_betting_probability"])
        self.assertTrue(result["verification"]["hash_covered_availability_rechecked"])
        self.assertTrue(result["verification"]["no_projection_created"])


if __name__ == "__main__":
    unittest.main()
