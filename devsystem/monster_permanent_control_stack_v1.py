"""MONSTER permanent control stack V1.

Locks the mandatory gate order and recovery order for MONSTER only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from devsystem.monster_system_isolation_v1 import assert_monster_only

VERSION = "MONSTER_PERMANENT_CONTROL_STACK_2A_THROUGH_2F_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

CONTROL_ORDER = (
    "STEP_2A", "ANTI_LOOP", "STEP_2C", "STEP_2B", "EXECUTE",
    "STEP_2D", "STEP_2E", "STEP_2F", "FINAL_VERIFY", "GREEN", "FROZEN",
)
FAILURE_RECOVERY = (
    "ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "CORRECTED_EXECUTION",
    "STEP_2D", "STEP_2E", "STEP_2F",
)


class MonsterPermanentControlStackFailure(RuntimeError):
    pass


def evaluate_gate_results(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    assert_monster_only({"system": "MONSTER", "results": results})
    required = ("STEP_2A", "ANTI_LOOP", "STEP_2B", "EXECUTE", "STEP_2D", "STEP_2E", "STEP_2F", "FINAL_VERIFY")
    for gate in required:
        if str((results.get(gate) or {}).get("status") or "").upper() != "GREEN":
            raise MonsterPermanentControlStackFailure(f"{gate}_NOT_GREEN")
    if "STEP_2C" in results and str((results.get("STEP_2C") or {}).get("status") or "").upper() != "GREEN":
        raise MonsterPermanentControlStackFailure("STEP_2C_NOT_GREEN")
    return {"status": "GREEN", "monster_only": True, "control_order": CONTROL_ORDER, "ready_to_freeze": True}


def contract_self_test(root: Path | str | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    permanent_source = (root / "devsystem/monster_system_permanent_gate_v1.py").read_text(encoding="utf-8")
    step2d_wired = "mandatory_2d_data_truth_gate_v1" in permanent_source
    step2e_wired = "mandatory_2e_router_ownership_gate_v1" in permanent_source
    step2f_wired = "mandatory_2f_live_production_gate_v1" in permanent_source
    if not (step2d_wired and step2e_wired and step2f_wired):
        raise MonsterPermanentControlStackFailure("PERMANENT_GATE_WIRING_INCOMPLETE")
    result = evaluate_gate_results({
        "STEP_2A": {"status": "GREEN"},
        "ANTI_LOOP": {"status": "GREEN"},
        "STEP_2C": {"status": "GREEN"},
        "STEP_2B": {"status": "GREEN"},
        "EXECUTE": {"status": "GREEN"},
        "STEP_2D": {"status": "GREEN"},
        "STEP_2E": {"status": "GREEN"},
        "STEP_2F": {"status": "GREEN"},
        "FINAL_VERIFY": {"status": "GREEN"},
    })
    return {**result, "version": VERSION, "step2d_wired": True, "step2e_wired": True, "step2f_wired": True, "failure_recovery": FAILURE_RECOVERY}


if __name__ == "__main__":
    contract_self_test()
    print("MONSTER_PERMANENT_CONTROL_STACK_2A_THROUGH_2F_V1_GREEN")
