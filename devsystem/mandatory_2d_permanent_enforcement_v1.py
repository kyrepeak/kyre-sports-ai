"""Permanent MONSTER Step 2D data-truth enforcement V1.

Additive permanence layer over the already-frozen MONSTER Step 2B/Step 2C
baseline. This module never replaces that baseline and never mutates product
runtime. It proves that the Step 2D data-truth gate, recovery route, exact-head
workflow, proof plan, and regression contracts are present and GREEN.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from devsystem.mandatory_2d_data_truth_gate_v1 import contract_self_test as step2d_self_test
from devsystem.monster_system_permanent_gate_v1 import validate as validate_prior_system

VERSION = "MONSTER_STEP2D_PERMANENT_ENFORCEMENT_V1"
ROOT = Path(__file__).resolve().parents[1]
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

REQUIRED_FILES = (
    "devsystem/mandatory_2d_data_truth_gate_v1.py",
    "devsystem/mandatory_2d_permanent_enforcement_v1.py",
    "devsystem/monster_proof_plans/monster-step2d-data-truth-v1.json",
    "devsystem/task_ledgers/monster-step2d-data-truth-v1.json",
    "tests/test_devsystem_mandatory_2d_data_truth_gate_v1.py",
    "tests/test_devsystem_step2d_recovery_integration_v1.py",
    "tests/test_devsystem_monster_step2d_global_permanence_v1.py",
    ".github/workflows/monster-step2d-data-truth-v1.yml",
    "docs/superpowers/specs/2026-10-24-monster-step2d-data-truth-v1.md",
    "docs/superpowers/plans/2026-10-24-monster-step2d-data-truth-v1.md",
)

WORKFLOW_MARKERS = (
    "name: MONSTER Step 2D Data Truth V1",
    "branches: [monster-main]",
    "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}",
    "fetch-depth: 1",
    "persist-credentials: false",
    "python -m devsystem.monster_system_isolation_v1",
    "python devsystem/automatic_loop_kill_v1.py",
    "python devsystem/mandatory_2c_autonomous_recovery_v1.py",
    "python devsystem/mandatory_2b_reliability_gate_v1.py",
    "python devsystem/mandatory_2a_action_gate_v1.py",
    "python -m devsystem.mandatory_2d_data_truth_gate_v1",
    "python -m devsystem.monster_system_permanent_gate_v1",
    "python -m devsystem.mandatory_2d_permanent_enforcement_v1",
    "tests/test_devsystem_mandatory_2d_data_truth_gate_v1.py",
    "tests/test_devsystem_step2d_recovery_integration_v1.py",
    "tests/test_devsystem_monster_step2d_global_permanence_v1.py",
)

STEP2D_SOURCE_MARKERS = (
    "PROVIDER_FETCH_FAILURE",
    "PARSER_FAILURE",
    "EVENT_MAPPING_FAILURE",
    "ENTITY_MAPPING_FAILURE",
    "MARKET_MAPPING_FAILURE",
    "STALE_DATA",
    "SOURCE_CONFLICT",
    "ALL_SOURCES_UNAVAILABLE",
    "RETURN_TO_MONSTER_STEP_2C",
    "NEGATIVE_CACHE_TECHNICAL_FAILURE",
    "VERIFIED_ABSENT",
)


class Step2DPermanentEnforcementFailure(RuntimeError):
    pass


def _read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise Step2DPermanentEnforcementFailure(f"required MONSTER Step 2D artifact missing: {path}")
    return target.read_text(encoding="utf-8")


def _require_markers(source: str, markers: Iterable[str], label: str) -> None:
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise Step2DPermanentEnforcementFailure(f"{label} markers missing: " + " | ".join(missing))


def _validate_workflow() -> None:
    source = _read(".github/workflows/monster-step2d-data-truth-v1.yml")
    if "api2" in source.lower():
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D proof workflow contains foreign-system identity")
    if "fetch-depth: 0" in source:
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D proof workflow may not fetch all repository refs")
    _require_markers(source, WORKFLOW_MARKERS, "MONSTER Step 2D proof workflow")


def _validate_proof_plan() -> dict[str, Any]:
    payload = json.loads(_read("devsystem/monster_proof_plans/monster-step2d-data-truth-v1.json"))
    expected = {
        "task_id": "monster-step2d-data-truth-v1",
        "workstream": "monster-step2d-data-truth-v1",
        "source_monster_sha": "127db7ca1f23400055ff130f54704386823b4947",
        "authoritative_base": "monster-main",
        "authoritative_branch": "monster-step2d-data-truth-v1",
        "authoritative_pr": 1794,
        "proof_authority": "MONSTER_ONLY",
        "required_workflow": "MONSTER Step 2D Data Truth V1",
        "required_check": "monster-step2d-data-truth-certification",
        "merge_target": "monster-main",
        "freeze_token": "MONSTER_STEP2D_DATA_TRUTH_V1_FROZEN",
        "foreign_system_evidence_allowed": False,
        "foreign_repository_refs_allowed": False,
        "checkout_ref_policy": "EXACT_EVENT_HEAD_SHA",
        "checkout_fetch_depth": 1,
        "checkout_persist_credentials": False,
        "blind_retry_allowed": False,
        "freeze_requires_postmerge_gate": True,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise Step2DPermanentEnforcementFailure(f"MONSTER Step 2D proof plan drift: {key}")
    if payload.get("recovery_sequence") != ["ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "EXECUTE", "STEP_2D"]:
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D recovery sequence drift")
    return payload


def _validate_ledger() -> None:
    payload = json.loads(_read("devsystem/task_ledgers/monster-step2d-data-truth-v1.json"))
    if payload.get("task_id") != "monster-step2d-data-truth-v1":
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D ledger task mismatch")
    if payload.get("authoritative_pr") != 1794:
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D ledger PR mismatch")
    if payload.get("one_authoritative_proof_workflow") is not True:
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D ledger lost single proof authority")


def validate() -> dict[str, Any]:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D permanent files missing: " + " | ".join(missing))

    _validate_workflow()
    _validate_proof_plan()
    _validate_ledger()
    _require_markers(_read("devsystem/mandatory_2d_data_truth_gate_v1.py"), STEP2D_SOURCE_MARKERS, "MONSTER Step 2D source")

    prior = validate_prior_system()
    step2d = step2d_self_test()
    if prior.get("status") != "GREEN" or prior.get("monster_only") is not True:
        raise Step2DPermanentEnforcementFailure("existing MONSTER permanent baseline is not GREEN")
    if step2d.get("status") != "GREEN" or step2d.get("monster_only") is not True:
        raise Step2DPermanentEnforcementFailure("MONSTER Step 2D contract is not GREEN")

    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "prior_step2bc_baseline_green": True,
        "step2d_data_truth_permanent": True,
        "anti_loop_step2c_step2b_step2a_step2d_chain_permanent": True,
        "final_verification_requires_step2d": True,
        "verified_absence_required": True,
        "technical_failures_preserved": True,
        "technical_failure_negative_cache_blocked": True,
        "fabricated_values_blocked": True,
        "field_specific_fallback_required": True,
        "end_to_end_truth_required": True,
        "one_authoritative_proof_workflow": True,
        "exact_head_proof_required": True,
        "postmerge_gate_required_for_freeze": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    return validate()


if __name__ == "__main__":
    print("MONSTER_STEP2D_PERMANENT_ENFORCEMENT_V1_GREEN")
    print(json.dumps(validate(), indent=2, sort_keys=True))
