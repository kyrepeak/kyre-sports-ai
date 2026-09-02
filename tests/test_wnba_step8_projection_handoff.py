from __future__ import annotations

from copy import deepcopy
import unittest

from sports_api import wnba_step7g_release_freeze as freeze
from sports_api.wnba_step8_projection_handoff import (
    HANDOFF_RELEASE_ID,
    SCHEMA_VERSION,
    WNBAStep8ProjectionHandoffDisabledError,
    WNBAStep8ProjectionHandoffNotReadyError,
    WNBAStep8ProjectionHandoffUpstreamError,
    _assert_safe_environment,
    recompute_step4w_snapshot_content_sha256,
    step8_projection_handoff_enabled,
    validate_step7g_projection_handoff,
)


GAME_ID = "1022600291"
PLAYER_ID = 1642291


def _integration_status() -> dict:
    return {
        "model_version": freeze.INTEGRATION_VERSION,
        "candidate_scope": {},
        "all_core_seams_installed": True,
        "certified_scope": dict(freeze.CERTIFIED_SCOPE),
    }


def _snapshot() -> dict:
    value = {
        "source": "synthetic frozen Step 4W fixture",
        "data_type": "content_addressed_pre_model_projection_input_snapshot",
        "schema_version": "wnba_step_4w_v1",
        "snapshot_id": "pending",
        "content_sha256": "pending",
        "captured_at_utc": "2026-08-28T03:00:00+00:00",
        "finalized_at_utc": "2026-08-28T03:00:01+00:00",
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": GAME_ID,
        "player_id": PLAYER_ID,
        "recent_window_games": 5,
        "game_identity": {
            "game_id": GAME_ID,
            "away_team_key": "portland-fire",
            "home_team_key": "atlanta-dream",
            "date": "2026-08-28",
        },
        "focal_identity": {
            "player_id": PLAYER_ID,
            "team_key": "atlanta-dream",
            "side": "home",
            "opponent_team_key": "portland-fire",
        },
        "component_status": {
            "game_availability": {"requested": True, "available": True},
            "player_recent_shot_chart": {"requested": True, "available": True},
            "player_vs_opponent_shot_chart": {"requested": True, "available": True},
            "opponent_defense_by_shot_zone": {"requested": True, "available": True},
            "player_advanced": {"requested": True, "available": True},
            "team_advanced": {"requested": True, "available": True},
            "opponent_advanced": {"requested": True, "available": True},
            "game_whistle_context": {"requested": True, "available": True},
        },
        "inputs": {
            "player_opportunity_context": {"player_id": PLAYER_ID},
            "game_rest_travel_context": {"game_id": GAME_ID},
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
    }
    digest = recompute_step4w_snapshot_content_sha256(value)
    value["content_sha256"] = digest
    value["snapshot_id"] = f"wnba-4w-{GAME_ID}-{PLAYER_ID}-{digest[:16]}"
    # snapshot_id/content_sha256 are outside the Step-4W hash surface, so this is final.
    return value


def _required_check(check_id: str) -> dict:
    observed = None
    if check_id == "shot_context_coverage":
        observed = {"requested": [
            "player_recent_shot_chart",
            "player_vs_opponent_shot_chart",
            "opponent_defense_by_shot_zone",
        ]}
    elif check_id == "advanced_context_coverage":
        observed = {"requested": ["player_advanced", "team_advanced", "opponent_advanced"]}
    elif check_id == "officiating_context_coverage":
        observed = {"requested": ["game_whistle_context"]}
    return {
        "check_id": check_id,
        "category": "fixture",
        "severity": "pass",
        "blocking": False,
        "message": "synthetic pass",
        "observed": observed,
        "threshold": None,
    }


def _readiness() -> dict:
    snap = _snapshot()
    checks = [_required_check(check_id) for check_id in freeze.REQUIRED_RELEASE_DEFAULT_CHECKS]
    checks.extend(
        [
            {
                "check_id": "optional_starter_bench_role",
                "category": "fixture",
                "severity": "warning",
                "blocking": False,
                "message": "allowed synthetic warning",
            },
            {
                "check_id": "optional_five_player_lineups",
                "category": "fixture",
                "severity": "warning",
                "blocking": False,
                "message": "allowed synthetic warning",
            },
        ]
    )
    reference = {
        key: snap.get(key)
        for key in (
            "snapshot_id",
            "content_sha256",
            "captured_at_utc",
            "finalized_at_utc",
            "season",
            "season_type",
            "game_id",
            "player_id",
            "recent_window_games",
        )
    }
    return {
        "source": "synthetic frozen Step 4X fixture",
        "data_type": "rule_based_model_input_readiness_gate",
        "schema_version": "wnba_step_4x_v1",
        "evaluated_at_utc": "2026-08-28T03:00:02+00:00",
        "readiness": "READY_WITH_WARNINGS",
        "can_start_projection": True,
        "diagnostic_data_quality_score": 92,
        "snapshot_reference": reference,
        "summary": {
            "check_count": 6,
            "pass_count": 4,
            "warning_count": 2,
            "blocker_count": 0,
            "info_count": 0,
            "blocker_ids": [],
            "warning_ids": [
                "optional_starter_bench_role",
                "optional_five_player_lineups",
            ],
        },
        "blockers": [],
        "warnings": [],
        "checks": checks,
        "guardrails": {
            "gate_does_not_repair_or_impute_inputs": True,
            "gate_does_not_redistribute_missing_teammate_opportunity": True,
            "gate_does_not_create_projected_minutes": True,
            "gate_does_not_create_projected_starters": True,
            "gate_does_not_create_monte_carlo": True,
            "gate_does_not_create_sportsbook_data": True,
            "gate_does_not_create_betting_probability": True,
            "official_defender_matchup_unavailability_is_not_penalized": True,
            "blockers_override_diagnostic_score": True,
        },
        "verification": {
            "step_4w_content_hash_recomputed": True,
            "hash_covered_availability_rechecked": True,
            "derived_availability_summary_cross_checked": True,
            "required_core_identity_checked": True,
            "rotation_and_event_history_coverage_checked": True,
            "feature_eligible_event_share_checked": True,
            "availability_and_roster_state_checked_when_required": True,
            "injury_report_freshness_is_tip_time_aware": True,
            "optional_component_outages_are_reported_not_fabricated": True,
            "readiness_state_is_rule_based": True,
            "no_projection_created": True,
        },
        "snapshot_included": True,
        "snapshot": snap,
    }


class Step8ProjectionHandoffTests(unittest.TestCase):
    def _validate(self, readiness: dict | None = None, status: dict | None = None) -> dict:
        return validate_step7g_projection_handoff(
            _readiness() if readiness is None else readiness,
            _integration_status() if status is None else status,
            expected_player_id=PLAYER_ID,
            expected_game_id=GAME_ID,
        )

    def test_happy_path_creates_only_content_addressed_pre_projection_handoff(self) -> None:
        result = self._validate()
        self.assertEqual(result["data_type"], "certified_pre_projection_model_handoff")
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["handoff_release_id"], HANDOFF_RELEASE_ID)
        self.assertTrue(result["projection_execution_authorized"])
        self.assertFalse(result["production_activation_allowed"])
        self.assertEqual(result["upstream_release"]["release_id"], freeze.RELEASE_ID)
        self.assertEqual(result["upstream_release"]["candidate_scope"], {})
        self.assertEqual(result["snapshot_reference"]["game_id"], GAME_ID)
        self.assertEqual(result["snapshot_reference"]["player_id"], PLAYER_ID)
        self.assertTrue(result["guardrails"]["handoff_is_not_projection"])
        self.assertTrue(result["guardrails"]["no_monte_carlo_created"])
        self.assertTrue(result["verification"]["snapshot_content_hash_matches_independent_recompute"])
        self.assertEqual(len(result["handoff_content_sha256"]), 64)

    def test_handoff_content_hash_is_stable_across_evaluation_timestamp_only(self) -> None:
        first = _readiness()
        second = deepcopy(first)
        second["evaluated_at_utc"] = "2026-08-28T03:01:55+00:00"
        self.assertEqual(
            self._validate(first)["handoff_content_sha256"],
            self._validate(second)["handoff_content_sha256"],
        )

    def test_step8_is_default_off(self) -> None:
        self.assertFalse(step8_projection_handoff_enabled({}))
        self.assertTrue(step8_projection_handoff_enabled({"WNBA_STEP8_PROJECTION_HANDOFF_ENABLED": "true"}))

    def test_production_switch_prevents_handoff_process(self) -> None:
        with self.assertRaises(WNBAStep8ProjectionHandoffDisabledError):
            _assert_safe_environment({"WNBA_PRODUCTION_RUNTIME_ENABLED": "true"})

    def test_candidate_scope_reappearing_fails_closed(self) -> None:
        status = _integration_status()
        status["candidate_scope"] = {"future_surface": "candidate"}
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(status=status)

    def test_integration_version_drift_fails_closed(self) -> None:
        status = _integration_status()
        status["model_version"] = "wnba_step_7g_unexpected_v99"
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(status=status)

    def test_blocker_fails_closed_even_if_readiness_string_is_startable(self) -> None:
        readiness = _readiness()
        readiness["summary"]["blocker_count"] = 1
        readiness["summary"]["blocker_ids"] = ["synthetic_blocker"]
        with self.assertRaises(WNBAStep8ProjectionHandoffNotReadyError):
            self._validate(readiness)

    def test_unexpected_warning_fails_closed(self) -> None:
        readiness = _readiness()
        readiness["summary"]["warning_ids"].append("new_unreviewed_warning")
        readiness["summary"]["warning_count"] = 3
        with self.assertRaises(WNBAStep8ProjectionHandoffNotReadyError):
            self._validate(readiness)

    def test_missing_required_release_check_fails_closed(self) -> None:
        readiness = _readiness()
        readiness["checks"] = [
            row for row in readiness["checks"]
            if row.get("check_id") != "advanced_context_coverage"
        ]
        with self.assertRaises(WNBAStep8ProjectionHandoffNotReadyError):
            self._validate(readiness)

    def test_duplicate_required_release_check_fails_closed(self) -> None:
        readiness = _readiness()
        readiness["checks"].append(_required_check("officiating_context_coverage"))
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(readiness)

    def test_tampered_snapshot_content_fails_independent_hash_check(self) -> None:
        readiness = _readiness()
        readiness["snapshot"]["inputs"]["tampered"] = {"value": 1}
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(readiness)

    def test_snapshot_reference_mismatch_fails_closed(self) -> None:
        readiness = _readiness()
        readiness["snapshot_reference"]["player_id"] = PLAYER_ID + 1
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(readiness)

    def test_wrong_requested_identity_fails_closed(self) -> None:
        readiness = _readiness()
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            validate_step7g_projection_handoff(
                readiness,
                _integration_status(),
                expected_player_id=PLAYER_ID + 1,
                expected_game_id=GAME_ID,
            )

    def test_missing_included_snapshot_fails_closed(self) -> None:
        readiness = _readiness()
        readiness["snapshot_included"] = False
        readiness.pop("snapshot")
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(readiness)

    def test_step4x_no_projection_guardrail_must_remain_true(self) -> None:
        readiness = _readiness()
        readiness["verification"]["no_projection_created"] = False
        with self.assertRaises(WNBAStep8ProjectionHandoffUpstreamError):
            self._validate(readiness)


if __name__ == "__main__":
    unittest.main(verbosity=2)
