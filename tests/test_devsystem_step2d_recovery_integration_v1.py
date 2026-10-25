from __future__ import annotations

import importlib

import pytest


def _module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        pytest.fail(f"required MONSTER module missing: {name}: {exc}")


def _execution():
    return {
        "task_id": "monster-step2d-recovery-test",
        "execution_id": "exec-recovery-1",
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


def test_step2d_failure_routes_to_anti_loop_then_step2c_with_new_evidence():
    gate = _module("devsystem.mandatory_2d_data_truth_gate_v1")
    step2c = _module("devsystem.mandatory_2c_autonomous_recovery_v1")
    trace = {
        "task_id": "monster-step2d-recovery-test",
        "execution_id": "exec-recovery-1",
        "field_id": "nba.pra.odds",
        "authoritative_path": _execution()["authoritative_path"],
        "negative_cache_written": False,
        "stages": {
            "source": {"state": "VALUE_PRESENT", "value": -110, "truth_value": -110},
            "ingestion": {"state": "SUCCESS", "truth_value": -110},
            "parser": {"state": "PARSER_FAILURE", "detail": "unexpected nested price shape"},
            "identification_mapping": {"state": "SUCCESS"},
            "normalization": {"state": "SUCCESS"},
            "monster_authoritative": {"state": "NOT_AVAILABLE"},
            "consumer": {"state": "NOT_AVAILABLE"},
            "final_output": {"state": "NOT_AVAILABLE"},
        },
    }
    failed = gate.verify_post_execution(_execution(), [trace])
    assert failed["status"] == "BLOCKED"
    assert failed["recovery_sequence"] == [
        "ANTI_LOOP",
        "STEP_2C",
        "STEP_2B",
        "STEP_2A",
        "EXECUTE",
        "STEP_2D",
    ]
    candidate = failed["step2c_evidence_candidate"]
    recovery = step2c.decide_recovery({
        "task_id": "monster-step2d-recovery-test",
        "checkpoint_id": "2D",
        "authoritative_path": _execution()["authoritative_path"],
        "failed_generation": 1,
        "failed_attempts": [],
        "diagnostic_history": [],
        "evidence_candidates": [candidate],
    })
    assert recovery["decision"] == "TWO_C_GATHER_NEW_EVIDENCE"
    assert recovery["selected_evidence"]["fingerprint"] == candidate["fingerprint"]


def test_step2d_failure_fingerprint_is_deterministic_for_identical_evidence():
    gate = _module("devsystem.mandatory_2d_data_truth_gate_v1")
    execution = _execution()
    trace = {
        "task_id": execution["task_id"],
        "execution_id": execution["execution_id"],
        "field_id": "nba.pra.line",
        "authoritative_path": execution["authoritative_path"],
        "negative_cache_written": False,
        "stages": {
            "source": {"state": "STALE_DATA", "detail": "age exceeded field TTL"},
            "ingestion": {"state": "SUCCESS"},
            "parser": {"state": "SUCCESS"},
            "identification_mapping": {"state": "SUCCESS"},
            "normalization": {"state": "SUCCESS"},
            "monster_authoritative": {"state": "NOT_AVAILABLE"},
            "consumer": {"state": "NOT_AVAILABLE"},
            "final_output": {"state": "NOT_AVAILABLE"},
        },
    }
    first = gate.verify_post_execution(execution, [trace])
    second = gate.verify_post_execution(execution, [trace])
    assert first["failure_fingerprint"] == second["failure_fingerprint"]
