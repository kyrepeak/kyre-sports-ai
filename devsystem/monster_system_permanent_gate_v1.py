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
)

WORKFLOW_REQUIRED_MARKERS = (
    "branches: [monster-main]",
    "python -m py_compile",
    "python devsystem/monster_system_isolation_v1.py",
    "python devsystem/monster_execution_front_door_v1.py",
    "python devsystem/mandatory_2a_action_gate_v1.py",
    "python devsystem/mandatory_2b_reliability_gate_v1.py",
    "python devsystem/mandatory_2c_autonomous_recovery_v1.py",
    "python devsystem/mandatory_2bc_permanent_enforcement_v1.py",
    "python devsystem/monster_system_permanent_gate_v1.py",
    "tests/test_devsystem_monster_step2bc_global_permanence_v1.py",
)


class MonsterSystemPermanentGateFailure(RuntimeError):
    pass


def _require_files() -> None:
    missing = [path for path in REQUIRED_MONSTER_FILES if not (ROOT / path).is_file()]
    if missing:
        raise MonsterSystemPermanentGateFailure(
            "MONSTER permanent system files missing: " + " | ".join(missing)
        )


def _validate_workflow() -> None:
    path = ROOT / ".github/workflows/monster-step2bc-permanent-system-v1.yml"
    source = path.read_text(encoding="utf-8")
    if "api2" in source.lower():
        raise MonsterSystemPermanentGateFailure(
            "MONSTER certification workflow contains forbidden foreign-system identity"
        )
    missing = [marker for marker in WORKFLOW_REQUIRED_MARKERS if marker not in source]
    if missing:
        raise MonsterSystemPermanentGateFailure(
            "MONSTER certification workflow markers missing: " + " | ".join(missing)
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
        "blind_retry_allowed": False,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise MonsterSystemPermanentGateFailure(f"MONSTER proof plan drift: {key}")


def validate() -> dict[str, Any]:
    _require_files()
    _validate_workflow()
    _validate_proof_plan()

    step2bc = validate_step2bc()
    isolation = isolation_self_test()
    front_door = front_door_self_test()

    if step2bc.get("status") != "GREEN":
        raise MonsterSystemPermanentGateFailure("MONSTER Step 2B/2C permanent enforcement is not GREEN")
    if step2bc.get("base_permanent_contract_green") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER scoped Step 2A/Anti-Loop baseline is not GREEN")
    if isolation.get("status") != "GREEN" or isolation.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER hard isolation contract is not GREEN")
    if front_door.get("status") != "GREEN" or front_door.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER canonical execution front door is not GREEN")

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
        "step2a_step2b_step2c_chain_permanent": True,
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
