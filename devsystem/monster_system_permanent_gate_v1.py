"""MONSTER permanent Step 2B/Step 2C system gate V1.

This is the MONSTER-only permanence contract above the existing DevSystem
baseline. It requires the completed Anti-Loop + Step 2A + Step 2B + Step 2C
stack, the hard system-isolation guard, and the canonical MONSTER execution
front door. It also requires a dedicated certification workflow scoped to the
MONSTER canonical branch.

No API 2 state is read or accepted as evidence. This validator is read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devsystem import permanent_gate_v1
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


def validate() -> dict[str, Any]:
    _require_files()
    _validate_workflow()

    base = permanent_gate_v1.validate()
    step2bc = validate_step2bc()
    isolation = isolation_self_test()
    front_door = front_door_self_test()

    if base.get("status") != "GREEN":
        raise MonsterSystemPermanentGateFailure("MONSTER base permanent gate is not GREEN")
    if step2bc.get("status") != "GREEN":
        raise MonsterSystemPermanentGateFailure("MONSTER Step 2B/2C permanent enforcement is not GREEN")
    if isolation.get("status") != "GREEN" or isolation.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER hard isolation contract is not GREEN")
    if front_door.get("status") != "GREEN" or front_door.get("monster_only") is not True:
        raise MonsterSystemPermanentGateFailure("MONSTER canonical execution front door is not GREEN")

    result: dict[str, Any] = {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "canonical_branch": "monster-main",
        "base_permanent_gate_green": True,
        "step2bc_permanent_enforcement_green": True,
        "isolation_guard_green": True,
        "canonical_front_door_green": True,
        "step2a_step2b_step2c_chain_permanent": True,
        "anti_loop_permanent": True,
        "human_only_blocker_rule_permanent": True,
        "no_blind_retry_permanent": True,
        "own_evidence_required": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    return result


def contract_self_test() -> dict[str, Any]:
    return validate()


if __name__ == "__main__":
    print("MONSTER_STEP2BC_PERMANENT_SYSTEM_V1_GREEN")
    print(json.dumps(validate(), indent=2, sort_keys=True))
