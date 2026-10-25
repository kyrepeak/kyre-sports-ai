"""Permanent Step 2B/2C control-stack enforcement extension.

This module composes with the existing permanent DevSystem validator instead of
rewriting it. It fails closed unless the base permanent contract is GREEN and
the Step 2A / Anti-Loop / Step 2B / Step 2C recovery stack, targeted tests, and
dedicated certification workflows are all present with required control
markers.

The extension is read-only: no network calls, repository writes, deployments,
or product/runtime mutation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem import permanent_gate_v1 as base_permanent_gate

VERSION = "MONSTER_STEP2BC_PERMANENT_ENFORCEMENT_V1"
ROOT = Path(__file__).resolve().parents[1]
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

REQUIRED_CONTROL_FILES = (
    "devsystem/automatic_loop_kill_v1.py",
    "tests/test_devsystem_automatic_loop_kill_v1.py",
    "devsystem/mandatory_2a_action_gate_v1.py",
    "tests/test_devsystem_mandatory_2a_action_gate_v1.py",
    "devsystem/mandatory_2b_reliability_gate_v1.py",
    "tests/test_devsystem_mandatory_2b_reliability_gate_v1.py",
    ".github/workflows/monster-step2b-reliability-gate-v1.yml",
    "devsystem/mandatory_2c_autonomous_recovery_v1.py",
    "tests/test_devsystem_mandatory_2c_autonomous_recovery_v1.py",
    "tests/test_devsystem_step2c_step2b_step2a_integration_v1.py",
    "tests/test_devsystem_step2b_step2a_integration_v1.py",
    ".github/workflows/monster-step2c-autonomous-recovery-v1.yml",
    "tests/test_devsystem_step2bc_permanent_gate_v1.py",
)

_STEP2A_MARKERS = (
    "MONSTER_2A_MANDATORY_ACTION_GATE_V1",
    "automatic_loop_kill_v1",
    "mandatory_2b_reliability_gate_v1",
    "two_c_enforced",
    "recovery_decision",
    "recovery_receipt_hash",
)
_ANTI_LOOP_MARKERS = (
    "MONSTER_AUTOMATIC_LOOP_KILL_V1",
    "LOOP_SKIPPED_CONTINUE",
    "ASYNC_LOCKED",
)
_STEP2B_MARKERS = (
    "MONSTER_2B_FIRST_SECOND_PASS_RELIABILITY_GATE_V1",
    "TWO_B_TWO_C_RECOVERY_REQUIRED",
    "TWO_B_RECOVERY_ATTEMPT_AUTHORIZED",
    "ONLY_AFTER_MATERIALLY_NEW_EVIDENCE",
    "recovery_receipt_hash",
)
_STEP2C_MARKERS = (
    "MONSTER_2C_AUTONOMOUS_RECOVERY_GREEN_CONVERGENCE_V1",
    "TWO_C_EXPAND_DIAGNOSIS",
    "TWO_C_GATHER_NEW_EVIDENCE",
    "TWO_C_RECOVERY_AUTHORIZED",
    "TWO_C_HUMAN_BLOCKER",
    "REENTER_STEP_2B_WITH_RECOVERY_RECEIPT",
)
_STEP2B_WORKFLOW_MARKERS = (
    "python devsystem/mandatory_2b_reliability_gate_v1.py",
    "python devsystem/mandatory_2a_action_gate_v1.py",
    "tests/test_devsystem_mandatory_2b_reliability_gate_v1.py",
    "tests/test_devsystem_step2b_step2a_integration_v1.py",
    "tests/test_devsystem_automatic_loop_kill_v1.py",
)
_STEP2C_WORKFLOW_MARKERS = (
    "python devsystem/mandatory_2c_autonomous_recovery_v1.py",
    "python devsystem/mandatory_2b_reliability_gate_v1.py",
    "python devsystem/mandatory_2a_action_gate_v1.py",
    "tests/test_devsystem_step2c_step2b_step2a_integration_v1.py",
    "tests/test_devsystem_step2bc_permanent_gate_v1.py",
    "python devsystem/mandatory_2bc_permanent_enforcement_v1.py",
)


class Step2BCPermanentEnforcementFailure(RuntimeError):
    pass


def _read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise Step2BCPermanentEnforcementFailure(f"required control artifact missing: {path}")
    return target.read_text(encoding="utf-8")


def _require_markers(source: str, markers: Iterable[str], label: str) -> None:
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise Step2BCPermanentEnforcementFailure(
            f"{label} permanent markers missing: " + " | ".join(missing)
        )


def validate() -> dict[str, object]:
    base = base_permanent_gate.validate()
    if base.get("status") != "GREEN":
        raise Step2BCPermanentEnforcementFailure("base permanent DevSystem contract is not GREEN")

    missing = [path for path in REQUIRED_CONTROL_FILES if not (ROOT / path).is_file()]
    if missing:
        raise Step2BCPermanentEnforcementFailure(
            "Step 2B/2C permanent control files missing: " + " | ".join(missing)
        )

    step2a_source = _read("devsystem/mandatory_2a_action_gate_v1.py")
    anti_loop_source = _read("devsystem/automatic_loop_kill_v1.py")
    step2b_source = _read("devsystem/mandatory_2b_reliability_gate_v1.py")
    step2c_source = _read("devsystem/mandatory_2c_autonomous_recovery_v1.py")
    step2b_workflow = _read(".github/workflows/monster-step2b-reliability-gate-v1.yml")
    step2c_workflow = _read(".github/workflows/monster-step2c-autonomous-recovery-v1.yml")

    _require_markers(step2a_source, _STEP2A_MARKERS, "Step 2A")
    _require_markers(anti_loop_source, _ANTI_LOOP_MARKERS, "Anti-Loop")
    _require_markers(step2b_source, _STEP2B_MARKERS, "Step 2B")
    _require_markers(step2c_source, _STEP2C_MARKERS, "Step 2C")
    _require_markers(step2b_workflow, _STEP2B_WORKFLOW_MARKERS, "Step 2B workflow")
    _require_markers(step2c_workflow, _STEP2C_WORKFLOW_MARKERS, "Step 2C workflow")

    result: dict[str, object] = {
        "status": "GREEN",
        "version": VERSION,
        "base_permanent_contract_green": True,
        "step2a_permanent_chain_preserved": True,
        "automatic_loop_kill_permanent": True,
        "mandatory_2b_reliability_gate_v1_permanent": True,
        "mandatory_2c_autonomous_recovery_v1_permanent": True,
        "step2b_step2c_workflows_permanent": True,
        "no_blind_attempt_three": True,
        "autonomous_diagnosis_after_two_failures": True,
        "human_intervention_only_for_verified_blocker": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    print("MONSTER_STEP2BC_PERMANENT_ENFORCEMENT_V1_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def contract_self_test() -> dict[str, object]:
    return validate()


if __name__ == "__main__":
    contract_self_test()
