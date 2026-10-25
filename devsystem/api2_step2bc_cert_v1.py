"""Whole-stack certification for permanent API2 Step 2A/B/C/D controls."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import devsystem.api2_anti_loop_v1 as anti
import devsystem.api2_execution_controller_v3 as controller
import devsystem.api2_execution_plan_compiler_cert_v1 as compiler
import devsystem.api2_frozen_registry_v1 as frozen
import devsystem.api2_isolation_guard_v1 as isolation
import devsystem.api2_proof_registry_v1 as proof_registry
import devsystem.api2_step2a_authority_v1 as step2a
import devsystem.api2_step2b_reliability_gate_v1 as step2b
import devsystem.api2_step2c_root_cause_v1 as step2c
import devsystem.api2_step2d_data_truth_gate_v1 as step2d

VERSION = "API2_STEP2ABCD_CERT_V2"


def authoritative_module_paths() -> list[str]:
    return [
        "devsystem/api2_isolation_guard_v1.py",
        "devsystem/api2_anti_loop_v1.py",
        "devsystem/api2_step2c_root_cause_v1.py",
        "devsystem/api2_step2b_reliability_gate_v1.py",
        "devsystem/api2_step2a_authority_v1.py",
        "devsystem/api2_step2d_data_truth_gate_v1.py",
        "devsystem/api2_execution_controller_v3.py",
        "devsystem/api2_frozen_registry_v1.py",
        "devsystem/api2_proof_registry_v1.py",
        "devsystem/api2_execution_plan_compiler_cert_v1.py",
        "devsystem/api2_step2bc_cert_v1.py",
    ]


def _imports_are_api2_only() -> bool:
    for path in authoritative_module_paths():
        tree = ast.parse(Path(path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("devsystem"):
                if not (node.module or "").startswith("devsystem.api2_"):
                    return False
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("devsystem.") and not alias.name.startswith("devsystem.api2_"):
                        return False
    return True


def _good_reliability(evidence_digest: str) -> dict[str, Any]:
    criteria = ["repair control chain", "prove recovery"]
    return {
        "system": "api2",
        "acceptance_criteria": criteria,
        "authoritative_path": {
            "problem_id": "api2-step2d-cert-problem",
            "branch": "api2-step2d-data-truth-gate-v1",
            "proof_path": "api2-step2d-data-truth-proof-v1",
        },
        "root_cause": {
            "finding": "provider failure collapsed into false empty state",
            "evidence_digest": evidence_digest,
        },
        "requirement_to_implementation": {
            criteria[0]: ["devsystem/api2_execution_controller_v3.py"],
            criteria[1]: ["devsystem/api2_step2d_data_truth_gate_v1.py"],
        },
        "requirement_to_proof": {
            criteria[0]: ["test_control_chain"],
            criteria[1]: ["test_step2d_data_truth"],
        },
        "production_dependencies": [{"name": "python", "verified": True}],
        "provider_reachability": [{"name": "FanDuel", "relevant": True, "verified": True}],
        "configuration_assumptions": [{"name": "api2-main", "verified": True}],
        "regression_risks": [
            {"risk": "blind retry", "proof": "test_recovery_cycle"},
            {"risk": "false MARKET_NOT_POSTED", "proof": "test_step2d_data_truth"},
        ],
        "verification": [
            "pytest -q tests/test_api2_step2d_data_truth_gate_v1.py tests/test_api2_step2d_integration_v1.py"
        ],
        "repair_delta": {
            "prior_repair": "empty provider result could reach MARKET_NOT_POSTED",
            "new_repair": "mandatory post-execution data-truth gate preserves provider failure state",
            "new_evidence_digest": "b" * 64,
            "materially_different": True,
        },
    }


def self_test() -> dict[str, Any]:
    isolation_green = _imports_are_api2_only()
    isolation.validate_api2_authority(
        {
            "system": "api2",
            "problem_id": "api2-step2d-cert-problem",
            "branch": "api2-step2d-data-truth-gate-v1",
            "proof_path": "api2-step2d-data-truth-proof-v1",
            "base_ref": "refs/heads/api2-main",
        }
    )

    failed_action = {"type": "PATCH", "target": "devsystem/api2_execution_controller_v3.py"}
    anti_state = anti.record_failure(
        {}, action=failed_action, evidence=["verification failed"], hypothesis="surface symptom"
    )
    blind = anti.authorize_retry(
        anti_state,
        action=failed_action,
        evidence=["verification failed"],
        hypothesis="surface symptom",
    )
    anti_loop_blind_retry_blocked = blind.get("allowed") is False

    investigation = step2c.investigate(
        failure={"class": "RUNTIME", "failed_action": "PATCH"},
        probes=[
            {"domain": "runtime", "depth": 1, "supported": True, "finding": "runtime false blank", "evidence": "trace"},
            {"domain": "tests", "depth": 2, "supported": True, "finding": "data-truth contract red", "evidence": "pytest"},
            {"domain": "configuration", "depth": 2, "supported": True, "finding": "provider configured", "evidence": "route config"},
            {"domain": "dependency", "depth": 4, "supported": True, "finding": "provider failure collapsed into false empty state", "evidence": "collector boundary"},
        ],
    )
    step2c_autonomous_recovery_green = (
        investigation.get("next_phase") == "STEP_2B"
        and investigation.get("root_cause") == "provider failure collapsed into false empty state"
        and investigation.get("human_only_blocker") is False
    )

    bad_payload = _good_reliability(str(investigation["evidence_digest"]))
    bad_payload["requirement_to_proof"].pop("prove recovery")
    fail_closed = step2b.validate_repair(bad_payload).get("allowed") is False
    good_payload = _good_reliability(str(investigation["evidence_digest"]))
    good_decision = step2b.validate_repair(good_payload)
    step2b_fail_closed_green = fail_closed and good_decision.get("allowed") is True

    authority = step2a.begin_problem(
        {},
        problem_id="api2-step2d-cert-problem",
        branch="api2-step2d-data-truth-gate-v1",
        proof_path="api2-step2d-data-truth-proof-v1",
    )
    retry = anti.authorize_retry(
        anti_state,
        action=failed_action,
        evidence=[investigation["evidence_digest"]],
        hypothesis=str(investigation["hypothesis"]),
    )
    token = step2a.authorize_repair(
        authority, repair=failed_action, reliability=good_decision, anti_loop=retry
    )
    consumed = step2a.consume_authorization(authority, token)
    replay_blocked = False
    try:
        step2a.consume_authorization(consumed, token)
    except step2a.Step2AError:
        replay_blocked = True
    step2a_one_use_green = replay_blocked

    # Independent Step 2D contract: technical failure is not a market absence.
    false_empty = step2d.evaluate_field(
        {
            "requested_field": "nfl.player.rushing_yards",
            "source_observations": [{"provider": "fanduel", "reachable": False}],
            "api_state": "MARKET_NOT_POSTED",
            "frontend_state": "LINE_PENDING",
        }
    )
    available = step2d.evaluate_field(
        {
            "requested_field": "nfl.player.rushing_yards",
            "source_observations": [
                {
                    "provider": "fanduel",
                    "reachable": True,
                    "parsed": True,
                    "matched": True,
                    "fresh": True,
                    "present": True,
                    "value": 37.5,
                }
            ],
            "api_value": 37.5,
            "frontend_value": 37.5,
        }
    )
    step2d_contract_green = (
        false_empty.get("allowed") is False
        and false_empty.get("state") == "PROVIDER_FETCH_FAILURE"
        and available.get("allowed") is True
        and available.get("state") == "AVAILABLE"
    )

    state = controller.new_state(
        problem_id="api2-step2d-cert-problem",
        branch="api2-step2d-data-truth-gate-v1",
        proof_path="api2-step2d-data-truth-proof-v1",
        acceptance_criteria=["repair control chain", "prove recovery"],
    )
    state = controller.record_failure(
        state, action=failed_action, evidence=["verification failed"], hypothesis="surface symptom"
    )
    state = controller.submit_step2c(state, investigation)
    state = controller.submit_step2b(state, good_payload)
    state, controller_token = controller.authorize_repair(state, failed_action)
    state = controller.mark_repair_executed(state, controller_token)

    verify_before_step2d_blocked = False
    try:
        controller.record_verification(
            state, {"repair control chain": True, "prove recovery": True}
        )
    except controller.ControllerError:
        verify_before_step2d_blocked = True

    state = controller.submit_step2d(
        state,
        [
            {
                "requested_field": "nfl.player.rushing_yards",
                "source_observations": [
                    {
                        "provider": "fanduel",
                        "reachable": True,
                        "parsed": True,
                        "matched": True,
                        "fresh": True,
                        "present": True,
                        "value": 37.5,
                    }
                ],
                "api_value": 37.5,
                "frontend_value": 37.5,
            }
        ],
    )
    step2d_controller_green = (
        verify_before_step2d_blocked
        and state.get("phase") == "VERIFY"
        and state.get("step2d_status") == "GREEN"
    )

    partial_green_blocked = False
    try:
        controller.record_verification(state, {"repair control chain": True})
    except controller.ControllerError:
        partial_green_blocked = True
    state = controller.record_verification(
        state, {"repair control chain": True, "prove recovery": True}
    )
    green_requires_proof = (
        partial_green_blocked and state.get("green") is True and state.get("frozen") is False
    )

    registry = frozen.freeze_checkpoint(
        frozen.new_registry(),
        checkpoint_id="API2_STEP2D_CERT_FROZEN",
        candidate_sha="1" * 40,
        merged_sha="2" * 40,
        evidence_digest="3" * 64,
        artifacts={"devsystem/api2_execution_controller_v3.py": "4" * 40},
    )
    checkpoint = frozen.verify_checkpoint(registry, "API2_STEP2D_CERT_FROZEN")
    state = controller.record_freeze_readback(state, checkpoint)
    freeze_readback_green = state.get("frozen") is True and state.get("phase") == "FROZEN"

    snapshot = controller.status_snapshot(state)
    required_status = {
        "current_phase",
        "progress_percent",
        "active_problem",
        "authoritative_api2_path",
        "current_root_cause_hypothesis",
        "step_2c_status",
        "step_2b_status",
        "step_2a_authorization_status",
        "step_2d_status",
        "anti_loop_status",
        "verification_status",
        "blocker",
        "green_frozen_checkpoint",
    }
    live_status_complete = required_status.issubset(snapshot) and snapshot["progress_percent"] == 100

    proof_state = proof_registry.record_green_proof(
        proof_registry.new_registry(),
        proof_id="api2-step2d-cert-proof-v1",
        candidate_sha="5" * 40,
        base_sha="6" * 40,
        evidence_digest="7" * 64,
        artifacts={"devsystem/api2_execution_controller_v3.py": "8" * 40},
        acceptance_proofs={
            "isolation": True,
            "recovery": True,
            "step2d": True,
            "verification": True,
        },
        certification={"status": "GREEN"},
    )
    proof_registry_green = (
        proof_registry.verify_proof(proof_state, "api2-step2d-cert-proof-v1").get("state")
        == "GREEN"
    )
    compiler_result = compiler.self_test()
    compiler_green = (
        compiler_result.get("status") == "GREEN"
        and compiler_result.get("step2d_mandatory") is True
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "isolation_green": isolation_green,
        "anti_loop_blind_retry_blocked": anti_loop_blind_retry_blocked,
        "step2c_autonomous_recovery_green": step2c_autonomous_recovery_green,
        "step2b_fail_closed_green": step2b_fail_closed_green,
        "step2a_one_use_green": step2a_one_use_green,
        "step2d_contract_green": step2d_contract_green,
        "step2d_controller_green": step2d_controller_green,
        "green_requires_proof": green_requires_proof,
        "freeze_readback_green": freeze_readback_green,
        "live_status_complete": live_status_complete,
        "proof_registry_green": proof_registry_green,
        "compiler_green": compiler_green,
    }
    required_true = [
        key
        for key, value in result.items()
        if key not in {"status", "version"} and value is not True
    ]
    if required_true:
        raise RuntimeError("API2_STEP2D_CERT_FAILED:" + ",".join(sorted(required_true)))
    return result
