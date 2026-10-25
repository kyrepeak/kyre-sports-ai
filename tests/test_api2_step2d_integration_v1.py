from __future__ import annotations

import json
from pathlib import Path

import pytest


def _good_reliability(root_digest: str) -> dict:
    criteria = ["repair false blank", "prove data truth"]
    return {
        "system": "api2",
        "acceptance_criteria": criteria,
        "authoritative_path": {
            "problem_id": "api2-step2d-cert-problem",
            "branch": "api2-step2d-data-truth-gate-v1",
            "proof_path": "api2-step2d-data-truth-proof-v1",
        },
        "root_cause": {"finding": "provider failure collapsed into empty list", "evidence_digest": root_digest},
        "requirement_to_implementation": {
            criteria[0]: ["sports_api/nfl_rushing_yards_data_truth_v1.py"],
            criteria[1]: ["devsystem/api2_execution_controller_v3.py"],
        },
        "requirement_to_proof": {
            criteria[0]: ["test_rushing_provider_failure_cannot_be_market_not_posted"],
            criteria[1]: ["test_step2d_is_mandatory_between_execute_and_verify"],
        },
        "production_dependencies": [{"name": "python", "verified": True}],
        "provider_reachability": [{"name": "FanDuel", "relevant": True, "verified": True}],
        "configuration_assumptions": [{"name": "api2-main", "verified": True}],
        "regression_risks": [{"risk": "provider exception becomes false blank", "proof": "test_rushing_provider_failure_cannot_be_market_not_posted"}],
        "verification": ["pytest -q tests/test_api2_step2d_integration_v1.py"],
        "repair_delta": {
            "prior_repair": "empty list means market not posted",
            "new_repair": "preserve provider failure state and require Step 2D truth proof",
            "new_evidence_digest": "b" * 64,
            "materially_different": True,
        },
    }


def _investigation():
    from devsystem.api2_step2c_root_cause_v1 import investigate

    return investigate(
        failure={"class": "RUNTIME", "failed_action": "PATCH"},
        probes=[
            {"domain": "runtime", "depth": 1, "supported": True, "finding": "FanDuel line absent in API", "evidence": "Page 1 false blank"},
            {"domain": "tests", "depth": 2, "supported": True, "finding": "semantic state regression", "evidence": "contract red"},
            {"domain": "configuration", "depth": 2, "supported": True, "finding": "provider configured", "evidence": "route active"},
            {"domain": "dependency", "depth": 4, "supported": True, "finding": "provider exception collapsed into empty list", "evidence": "_collect_markets except Exception -> []"},
        ],
    )


def test_step2d_is_mandatory_between_execute_and_verify():
    from devsystem import api2_execution_controller_v3 as controller

    investigation = _investigation()
    state = controller.new_state(
        problem_id="api2-step2d-cert-problem",
        branch="api2-step2d-data-truth-gate-v1",
        proof_path="api2-step2d-data-truth-proof-v1",
        acceptance_criteria=["repair false blank", "prove data truth"],
    )
    failed_action = {"type": "PATCH", "target": "sports_api/nfl_rushing_yards_data_truth_v1.py"}
    state = controller.record_failure(state, action=failed_action, evidence=["false blank"], hypothesis="surface symptom")
    state = controller.submit_step2c(state, investigation)
    state = controller.submit_step2b(state, _good_reliability(investigation["evidence_digest"]))
    state, token = controller.authorize_repair(state, failed_action)
    state = controller.mark_repair_executed(state, token)

    assert state["phase"] == "STEP_2D"
    with pytest.raises(controller.ControllerError, match="OUT_OF_ORDER"):
        controller.record_verification(state, {"repair false blank": True, "prove data truth": True})

    state = controller.submit_step2d(
        state,
        [
            {
                "requested_field": "nfl.player.rushing_yards",
                "source_observations": [
                    {"provider": "fanduel", "reachable": True, "parsed": True, "matched": True, "fresh": True, "present": True, "value": 37.5}
                ],
                "api_value": 37.5,
                "frontend_value": 37.5,
            }
        ],
    )
    assert state["phase"] == "VERIFY"
    assert state["step2d_status"] == "GREEN"


def test_step2d_failure_routes_back_to_root_cause_investigation():
    from devsystem import api2_execution_controller_v3 as controller

    state = {"system": "api2", "phase": "STEP_2D", "step2d_status": "REQUIRED"}
    state = controller.submit_step2d(
        state,
        [
            {
                "requested_field": "nfl.player.rushing_yards",
                "source_observations": [{"provider": "fanduel", "reachable": False}],
                "api_state": "MARKET_NOT_POSTED",
                "frontend_state": "LINE_PENDING",
            }
        ],
    )
    assert state["phase"] == "STEP_2C"
    assert state["step2d_status"] == "BLOCKED"
    assert state["step2c_status"] == "REQUIRED_DEEPER_INVESTIGATION"


def test_execution_plan_and_manifest_make_step2d_permanent():
    from devsystem.api2_execution_plan_compiler_cert_v1 import compile_api2_execution_plan

    plan = compile_api2_execution_plan("a" * 40)
    assert plan["failure_recovery_chain"] == [
        "ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "EXECUTE", "STEP_2D", "VERIFY", "GREEN", "FROZEN"
    ]
    assert "05_STEP2D_DATA_TRUTH" in plan["topological_order"]

    manifest = json.loads(Path("devsystem/api2_authority_manifest_v1.json").read_text())
    assert manifest["required_chain"] == [
        "FAILURE", "ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "EXECUTE", "STEP_2D", "VERIFY", "GREEN", "FROZEN"
    ]
    assert "devsystem/api2_step2d_data_truth_gate_v1.py" in manifest["authority_modules"]
    assert "devsystem/api2_execution_controller_v3.py" in manifest["authority_modules"]


def test_rushing_provider_failure_cannot_be_market_not_posted():
    from sports_api import nfl_rushing_yards_data_truth_v1 as truth

    result = truth.market_state_from_bundle(
        {"state": "PROVIDER_FETCH_FAILURE", "observations": [], "provider": "FanDuel"},
        player={"player_name": "Kendre Miller", "team_abbr": "NO"},
    )
    assert result["status"] == "PROVIDER_FETCH_FAILURE"
    assert result["line"] is None
    assert result["status"] != "MARKET_NOT_POSTED"


def test_rushing_successful_provider_value_survives_to_market_state():
    from sports_api import nfl_rushing_yards_data_truth_v1 as truth

    bundle = {
        "state": "AVAILABLE",
        "provider": "FanDuel",
        "observations": [
            {
                "player_name": "Kendre Miller",
                "team_abbr": "NO",
                "position": "RB",
                "sportsbook": "FanDuel",
                "market": "Rushing Yards",
                "line": 37.5,
                "over_odds": -110,
                "under_odds": -110,
                "source_timestamp": "2026-10-25T03:00:00+00:00",
            }
        ],
    }
    result = truth.market_state_from_bundle(bundle, player={"player_name": "Kendre Miller", "team_abbr": "NO"})
    assert result["status"] == "VERIFIED"
    assert result["line"] == 37.5
    assert result["sportsbook"] == "FanDuel"
