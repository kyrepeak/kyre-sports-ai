from __future__ import annotations

import importlib
from copy import deepcopy

import pytest


def _gate():
    try:
        return importlib.import_module("devsystem.mandatory_2d_data_truth_gate_v1")
    except ModuleNotFoundError as exc:
        pytest.fail(f"MONSTER Step 2D module is missing: {exc}")


def _execution():
    return {
        "task_id": "monster-step2d-self-test",
        "execution_id": "exec-001",
        "completed": True,
        "status": "SUCCESS",
        "monster_only": True,
        "authoritative_path": {
            "repository": "kyrepeak/kyre-sports-ai",
            "branch": "monster-step2d-data-truth-v1",
            "target": "monster:data-truth",
            "proof_path": "monster-step2d-data-truth-v1",
        },
    }


def _trace(value=22.5):
    stages = {
        "source": {"state": "VALUE_PRESENT", "value": value, "truth_value": value},
        "ingestion": {"state": "SUCCESS", "truth_value": value},
        "parser": {"state": "SUCCESS", "truth_value": value},
        "identification_mapping": {"state": "SUCCESS", "truth_value": value},
        "normalization": {"state": "SUCCESS", "truth_value": value},
        "monster_authoritative": {"state": "VALUE_PRESENT", "value": value, "truth_value": value},
        "consumer": {"state": "SUCCESS", "truth_value": value},
        "final_output": {"state": "VALUE_PRESENT", "value": value, "truth_value": value},
    }
    return {
        "task_id": "monster-step2d-self-test",
        "execution_id": "exec-001",
        "field_id": "nba.pra.line",
        "authoritative_path": _execution()["authoritative_path"],
        "stages": stages,
        "negative_cache_written": False,
    }


def test_step2d_allows_value_only_when_source_authoritative_and_output_truth_match():
    gate = _gate()
    result = gate.verify_post_execution(_execution(), [_trace(22.5)])
    assert result["status"] == "GREEN"
    assert result["decision"] == "STEP_2D_VERIFIED"
    assert result["final_verification_authorized"] is True
    assert result["fields_verified"] == 1


def test_step2d_preserves_parser_failure_and_never_turns_it_into_absence():
    gate = _gate()
    trace = _trace()
    trace["stages"]["parser"] = {"state": "PARSER_FAILURE", "detail": "schema drift"}
    trace["stages"]["final_output"] = {"state": "NOT_AVAILABLE"}
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "TECHNICAL_FAILURE"
    assert result["preserved_failure_state"] == "PARSER_FAILURE"
    assert result["final_verification_authorized"] is False
    assert result["negative_cache_allowed"] is False
    assert result["next_legal_action"] == "RETURN_TO_MONSTER_STEP_2C"


def test_step2d_blocks_unverified_absence():
    gate = _gate()
    trace = _trace()
    trace["stages"]["source"] = {"state": "NOT_FOUND"}
    trace["stages"]["final_output"] = {"state": "NOT_FOUND"}
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "UNVERIFIED_ABSENCE"
    assert result["final_verification_authorized"] is False


def test_step2d_allows_verified_absence_only_with_successful_path_and_fingerprinted_proof():
    gate = _gate()
    trace = _trace()
    for stage in trace["stages"].values():
        stage.clear()
        stage.update({"state": "SUCCESS"})
    trace["stages"]["final_output"] = {"state": "VERIFIED_ABSENT"}
    trace["absence_proof"] = {
        "source_path_succeeded": True,
        "requested_field_checked": True,
        "genuinely_absent": True,
        "evidence_fingerprint": "absence-proof-001",
    }
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "GREEN"
    assert result["fields"][0]["absence_verified"] is True


def test_step2d_blocks_false_blank_when_source_value_exists():
    gate = _gate()
    trace = _trace(31.5)
    trace["stages"]["final_output"] = {"state": "NOT_AVAILABLE"}
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "FALSE_BLANK"


def test_step2d_blocks_authoritative_or_final_truth_mismatch():
    gate = _gate()
    trace = _trace(22.5)
    trace["stages"]["monster_authoritative"] = {"state": "VALUE_PRESENT", "value": 23.5, "truth_value": 23.5}
    trace["stages"]["final_output"] = {"state": "VALUE_PRESENT", "value": 23.5, "truth_value": 23.5}
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "VALUE_MISMATCH"


def test_step2d_never_treats_real_zero_as_blank():
    gate = _gate()
    result = gate.verify_post_execution(_execution(), [_trace(0)])
    assert result["status"] == "GREEN"
    assert result["fields"][0]["verified_truth_value"] == 0


def test_step2d_blocks_fabricated_downstream_value_after_source_failure():
    gate = _gate()
    trace = _trace(10)
    trace["stages"]["source"] = {"state": "PROVIDER_FETCH_FAILURE", "detail": "timeout"}
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] in {"FABRICATED_VALUE", "TECHNICAL_FAILURE"}
    assert result["preserved_failure_state"] == "PROVIDER_FETCH_FAILURE"


def test_step2d_blocks_negative_cache_for_technical_failure():
    gate = _gate()
    trace = _trace()
    trace["stages"]["source"] = {"state": "ALL_SOURCES_UNAVAILABLE", "detail": "upstream outage"}
    trace["negative_cache_written"] = True
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "NEGATIVE_CACHE_TECHNICAL_FAILURE"
    assert result["negative_cache_allowed"] is False


def test_step2d_allows_only_field_specific_approved_nonblind_fallback():
    gate = _gate()
    trace = _trace(18.5)
    trace["fallback"] = {
        "used": True,
        "primary_failure_state": "PROVIDER_FETCH_FAILURE",
        "field_specific": True,
        "approved": True,
        "selected_source": "approved-secondary",
        "approved_sources": ["approved-secondary", "approved-tertiary"],
        "selection_reason": "primary source unavailable for this field",
        "blind_fanout": False,
    }
    result = gate.verify_post_execution(_execution(), [trace])
    assert result["status"] == "GREEN"
    assert result["fields"][0]["fallback_verified"] is True
    assert result["fields"][0]["primary_failure_state"] == "PROVIDER_FETCH_FAILURE"

    bad = deepcopy(trace)
    bad["fallback"]["blind_fanout"] = True
    blocked = gate.verify_post_execution(_execution(), [bad])
    assert blocked["status"] == "BLOCKED"
    assert blocked["failure_kind"] == "FALLBACK_POLICY_FAILURE"


def test_step2d_requires_completed_execution_before_it_can_run():
    gate = _gate()
    execution = _execution()
    execution["completed"] = False
    execution["status"] = "RUNNING"
    result = gate.verify_post_execution(execution, [_trace()])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "EXECUTION_NOT_COMPLETE"
    assert result["final_verification_authorized"] is False


def test_step2d_hard_isolation_rejects_foreign_runtime_state():
    gate = _gate()
    execution = _execution()
    execution["task_id"] = "api2-foreign-runtime"
    result = gate.verify_post_execution(execution, [_trace()])
    assert result["status"] == "BLOCKED"
    assert result["failure_kind"] == "FOREIGN_STATE_REJECTED"
    assert result["monster_only"] is True
