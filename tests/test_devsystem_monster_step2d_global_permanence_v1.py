from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _permanent_gate():
    try:
        return importlib.import_module("devsystem.mandatory_2d_permanent_enforcement_v1")
    except ModuleNotFoundError as exc:
        pytest.fail(f"MONSTER Step 2D permanent gate is missing: {exc}")


def test_monster_step2d_permanent_gate_composes_existing_frozen_baseline():
    gate = _permanent_gate()
    result = gate.validate()
    assert result["status"] == "GREEN"
    assert result["monster_only"] is True
    assert result["prior_step2bc_baseline_green"] is True
    assert result["step2d_data_truth_permanent"] is True
    assert result["anti_loop_step2c_step2b_step2a_step2d_chain_permanent"] is True
    assert result["final_verification_requires_step2d"] is True


def test_monster_step2d_has_one_exact_head_proof_workflow():
    workflow = (ROOT / ".github/workflows/monster-step2d-data-truth-v1.yml").read_text(encoding="utf-8")
    assert "branches: [monster-main]" in workflow
    assert "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "fetch-depth: 1" in workflow
    assert "persist-credentials: false" in workflow
    assert "fetch-depth: 0" not in workflow
    assert "api2" not in workflow.lower()
    assert "python -m devsystem.mandatory_2d_data_truth_gate_v1" in workflow
    assert "python -m devsystem.mandatory_2d_permanent_enforcement_v1" in workflow


def test_step2d_permanence_contract_names_required_failure_states():
    source = (ROOT / "devsystem/mandatory_2d_data_truth_gate_v1.py").read_text(encoding="utf-8")
    for marker in (
        "PROVIDER_FETCH_FAILURE",
        "PARSER_FAILURE",
        "EVENT_MAPPING_FAILURE",
        "ENTITY_MAPPING_FAILURE",
        "MARKET_MAPPING_FAILURE",
        "STALE_DATA",
        "SOURCE_CONFLICT",
        "ALL_SOURCES_UNAVAILABLE",
        "RETURN_TO_MONSTER_STEP_2C",
    ):
        assert marker in source
