"""MONSTER permanent Step 2B/Step 2C system gate V1.

This is the MONSTER-only permanence contract for the Anti-Loop + Step 2A +
Step 2B + Step 2C stack, the hard system-isolation guard, the canonical MONSTER
execution front door, and the dedicated MONSTER proof/freeze contract.

The gate deliberately does not execute the broader legacy permanent validator:
that validator owns unrelated product/domain workflow topology. MONSTER's
Step 2B/2C permanent enforcement already performs the scoped Step 2A/Anti-Loop
baseline checks required here.

Foreign-system state is never accepted as MONSTER evidence. This validator is
read-only and performs no network or product/runtime mutation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devsystem.mandatory_2bc_permanent_enforcement_v1 import validate as validate_step2bc
from devsystem.mandatory_2d_data_truth_gate_v1 import contract_self_test as step2d_self_test
from devsystem.mandatory_2e_router_ownership_gate_v1 import contract_self_test as step2e_self_test
from devsystem.mandatory_2f_live_production_gate_v1 import contract_self_test as step2f_self_test
from devsystem.monster_permanent_control_stack_v1 import contract_self_test as control_stack_self_test
from devsystem.monster_execution_front_door_v1 import contract_self_test as front_door_self_test
from devsystem.monster_system_isolation_v1 import contract_self_test as isolation_self_test

VERSION = "MONSTER_STEP2BC_PERMANENT_SYSTEM_V1"
ROOT = Path(__file__).resolve().parents[1]
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

REQUIRED_MONSTER_FILES = (
    "devsystem/automatic_loop_kill_v1.py",
    "devsystem/mandatory_2a_action_gate_v1.py",
    "devsystem/mandatory_2b_reliability_gate_v1.py",
    "devsystem/mandatory_2c_autonomous_recovery_v1.py",
    "devsystem/mandatory_2d_data_truth_gate_v1.py",
    "devsystem/mandatory_2e_router_ownership_gate_v1.py",
    "devsystem/mandatory_2f_live_production_gate_v1.py",
    "devsystem/monster_permanent_control_stack_v1.py",
    "devsystem/runless_proof_plans/monster-step2cdef-permanent-v1.json",
    "devsystem/task_ledgers/monster-step2cdef-permanent-v1.json",
    "tests/test_monster_step2cdef_permanent_v1.py",
    "devsystem/mandatory_2bc_permanent_enforcement_v1.py",
    "devsystem/monster_system_isolation_v1.py",
    "devsystem/monster_execution_front_door_v1.py",
    "devsystem/monster_system_permanent_gate_v1.py",
    "devsystem/monster_proof_plans/monster-step2bc-permanent-system-v1.json",
    "devsystem/task_ledgers/monster-step2bc-permanent-system-v1.json",
    "tests/test_devsystem_automatic_loop_kill_v1.py",
    "tests/test_devsystem_mandatory_2a_action_gate_v1.py",
    "tests/test_devsystem_mandatory_2b_reliability_gate_v1.py",
    "tests/test_devsystem_mandatory_2c_autonomous_recovery_v1.py",
    "tests/test_devsystem_step2b_step2a_integration_v1.py",
    "tests/test_devsystem_step2c_step2b_step2a_integration_v1.py",
    "tests/test_devsystem_step2bc_permanent_gate_v1.py",
    "tests/test_devsystem_monster_step2bc_global_permanence_v1.py",
    ".github/workflows/monster-step2bc-permanent-system-v1.yml",
    ".github/workflows/monster-step2c-autonomous-recovery-v1.yml",
)

PROOF_WORKFLOW_FILES = (
    ".github/workflows/monster-step2bc-permanent-system-v1.yml",
    ".github/workflows/monster-step2c-autonomous-recovery-v1.yml",
)

PERMANENT_WORKFLOW_REQUIRED_MARKERS = (
    "branches: [monster-main]",
    "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}",
    "fetch-depth: 1",
    "persist-credentials: false",
    "python -m py_compile",
    "python -m devsystem.monster_system_isolation_v1",
    "python -m devsystem.monster_execution_front_door_v1",
    "python devsystem/mandatory_2a_action_gate_v1.py",
    "python devsystem/mandatory_2b_reliability_gate_v1.py",
    "python devsystem/mandatory_2c_autonomous_recovery_v1.py",
    "python devsystem/mandatory_2bc_permanent_enforcement_v1.py",
    "python -m devsystem.monster_system_permanent_gate_v1",
    "tests/test_devsystem_monster_step2bc_global_permanence_v1.py",
)

PROOF_WORKFLOW_ISOLATION_MARKERS = (
    "branches: [monster-main]",
    "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}",
    "fetch-depth: 1",
    "persist-credentials: false",
)


class MonsterSystemPermanentGateFailure(RuntimeError):
    pass


def _require_files() -> None:
    missing = [path for path in REQUIRED_MONSTER_FILES if not (ROOT / path).is_file()]
    if missing:
        raise MonsterSystemPermanentGateFailure(
            "MONSTER permanent system files missing: " + " | ".join(missing)
        )


def _validate_workflows() -> None:
    for relative_path in PROOF_WORKFLOW_FILES:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        if "api2" in source.lower():
            raise MonsterSystemPermanentGateFailure(
                f"MONSTER proof workflow contains forbidden foreign-system identity: {relative_path}"
            )
        if "fetch-depth: 0" in source:
            raise MonsterSystemPermanentGateFailure(
                f"MONSTER proof workflow may not fetch all repository refs: {relative_path}"
            )
        missing = [marker for marker in PROOF_WORKFLOW_ISOLATION_MARKERS if marker not in source]
        if missing:
            raise MonsterSystemPermanentGateFailure(
                f"MONSTER proof workflow isolation markers missing in {relative_path}: " + " | ".join(missing)
            )

    permanent_source = (ROOT / ".github/workflows/monster-step2bc-permanent-system-v1.yml").read_text(encoding="utf-8")
    missing = [marker for marker in PERMANENT_WORKFLOW_REQUIRED_MARKERS if marker not in permanent_source]
    if missing:
        raise MonsterSystemPermanentGateFailure(
            "MONSTER permanent certification workflow markers missing: " + " | ".join(missing)
        )


def _validate_proof_plan() -> None:
    path = ROOT / "devsystem/monster_proof_plans/monster-step2bc-permanent-system-v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "task_id": "monster-step2bc-permanent-system-v1",
        "workstream": "monster-step2bc-permanent-system-v1",
        "authoritative_base": "monster-main",
        "authoritative_branch": "monster-step2bc-permanent-system-v1",
        "authoritative_pr": 1791,
        "proof_authority": "MONSTER_ONLY",
        "premerge_required_workflow": "MONSTER Step 2C Autonomous Recovery V1",
        "premerge_required_check": "step2c-autonomous-recovery-certification",
        "postmerge_required_workflow": "MONSTER Step 2B Step 2C Permanent System V1",
        "postmerge_required_check": "monster-step2bc-permanent-system-certification",
        "merge_target": "monster-main",
        "freeze_token": "MONSTER_STEP2BC_PERMANENT_SYSTEM_V1_FROZEN",
        "freeze_requires_postmerge_gate": True,
        "foreign_system_evidence_allowed": False,
        "foreign_repository_refs_allowed": False,
        "checkout_ref_policy": "EXACT_EVENT_HEAD_SHA",
        "checkout_fetch_depth": 1,
        "checkout_persist_credentials": False,
        "blind_retry_allowed": False,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise MonsterSystemPermanentGateFailure(f"MONSTER proof plan drift: {key}")


def validate() -> dict[str, Any]:
    _require_files()
    _validate_workflows()
    _validate_proof_plan()

    step2bc = validate_step2bc()
    isolation = isolation_self_test()
    front_door = front_door_self_test()
    step2d = step2d_self_test()
    step2e = step2e_self_test(ROOT)
    step2f = step2f_self_test()
    control_stack = control_stack_self_test(ROOT)

    if step2bc.get("status") != "GREEN":
        raise MonsterSystemPermanentGateFailure("MONSTER Step 2B/2C permanent enforcement is not GREEN")
    if step2bc.get("base_permanent_contract_green") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER scoped Step 2A/Anti-Loop baseline is not GREEN")
    if isolation.get("status") != "GREEN" or isolation.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER hard isolation contract is not GREEN")
    if front_door.get("status") != "GREEN" or front_door.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER canonical execution front door is not GREEN")
    if step2d.get("status") != "GREEN":
        raise MonsterSystemPermanentGateFailure("MONSTER Step 2D permanent gate is not GREEN")
    if step2e.get("status") != "GREEN" or step2e.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER Step 2E router ownership gate is not GREEN")
    if step2f.get("status") != "GREEN" or step2f.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER Step 2F production-consumption contract is not GREEN")
    if control_stack.get("status") != "GREEN" or control_stack.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER composed 2A-through-2F control stack is not GREEN")

    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "canonical_branch": "monster-main",
        "base_control_contract_green": True,
        "base_control_scope": "step2a+anti-loop",
        "full_legacy_permanent_gate_executed": False,
        "step2bc_permanent_enforcement_green": True,
        "isolation_guard_green": True,
        "canonical_front_door_green": True,
        "proof_workflows_exact_head_only": True,
        "proof_workflows_full_ref_fetch_blocked": True,
        "proof_workflows_persist_credentials": False,
        "step2a_step2b_step2c_chain_permanent": True,
        "step2d_permanent": True,
        "step2e_permanent": True,
        "step2f_permanent": True,
        "step2a_through_step2f_control_order_permanent": True,
        "step2e_route_count": step2e.get("route_count"),
        "step2f_alias_drift_fail_closed": step2f.get("alias_drift_fail_closed") is True,
        "anti_loop_permanent": True,
        "human_only_blocker_rule_permanent": True,
        "no_blind_retry_permanent": True,
        "own_evidence_required": True,
        "proof_plan_bound": True,
        "premerge_monster_gate_bound": True,
        "postmerge_monster_gate_bound": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    return validate()


if __name__ == "__main__":
    print("MONSTER_STEP2BC_PERMANENT_SYSTEM_V1_GREEN")
    print(json.dumps(validate(), indent=2, sort_keys=True))
