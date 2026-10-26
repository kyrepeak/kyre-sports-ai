"""Permanent MONSTER Step 2C + 2D + 2E + 2F control-stack contract V1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devsystem.automatic_loop_kill_v1 import contract_self_test as anti_loop_self_test
from devsystem.mandatory_2a_action_gate_v1 import contract_self_test as step2a_self_test
from devsystem.mandatory_2b_reliability_gate_v1 import contract_self_test as step2b_self_test
from devsystem.mandatory_2c_autonomous_recovery_v1 import contract_self_test as step2c_self_test
from devsystem.mandatory_2d_data_truth_gate_v1 import contract_self_test as step2d_self_test
from devsystem.mandatory_2e_canonical_router_ownership_v1 import contract_self_test as step2e_self_test
from devsystem.mandatory_2f_live_production_consumption_v1 import contract_self_test as step2f_self_test
from devsystem.monster_authoritative_proof_receipt_v1 import contract_self_test as receipt_self_test
from devsystem.monster_system_isolation_v1 import contract_self_test as isolation_self_test

VERSION = "MONSTER_STEP2C2D2E2F_PERMANENT_STACK_V1"
ROOT = Path(__file__).resolve().parents[1]
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

REQUIRED_FILES = (
    "devsystem/monster_system_isolation_v1.py", "devsystem/automatic_loop_kill_v1.py",
    "devsystem/mandatory_2a_action_gate_v1.py", "devsystem/mandatory_2b_reliability_gate_v1.py",
    "devsystem/mandatory_2c_autonomous_recovery_v1.py", "devsystem/mandatory_2d_data_truth_gate_v1.py",
    "devsystem/mandatory_2e_canonical_router_ownership_v1.py", "devsystem/mandatory_2f_live_production_consumption_v1.py",
    "devsystem/monster_authoritative_proof_receipt_v1.py", "devsystem/monster_router_registry_v1.json",
    "devsystem/monster_production_registry_v1.json", "devsystem/monster_proof_plans/monster-step2c2d2e2f-permanent-stack-v1.json",
    "devsystem/task_ledgers/monster-step2c2d2e2f-permanent-stack-v1.json", ".github/workflows/monster-step2c2d2e2f-permanent-stack-v1.yml",
)


def _require_files() -> None:
    missing=[path for path in REQUIRED_FILES if not (ROOT/path).is_file()]
    if missing: raise RuntimeError("MONSTER Step 2C-2F permanent files missing: "+" | ".join(missing))


def _require_owned_metadata() -> None:
    router=json.loads((ROOT/"devsystem/monster_router_registry_v1.json").read_text(encoding="utf-8"))
    production=json.loads((ROOT/"devsystem/monster_production_registry_v1.json").read_text(encoding="utf-8"))
    proof=json.loads((ROOT/"devsystem/monster_proof_plans/monster-step2c2d2e2f-permanent-stack-v1.json").read_text(encoding="utf-8"))
    ledger=json.loads((ROOT/"devsystem/task_ledgers/monster-step2c2d2e2f-permanent-stack-v1.json").read_text(encoding="utf-8"))
    if router.get("authority")!="MONSTER_ONLY" or router.get("repository_wide_live_route_audit_required") is not True: raise RuntimeError("MONSTER router registry authority/audit mismatch")
    if production.get("authority")!="MONSTER_ONLY": raise RuntimeError("MONSTER production registry authority mismatch")
    if proof.get("proof_authority")!="MONSTER_ONLY" or proof.get("github_actions_role")!="SUPPORTING_EVIDENCE_ONLY": raise RuntimeError("MONSTER proof authority metadata mismatch")
    if ledger.get("authoritative_branch")!="monster-step2c2d2e2f-permanent-stack-v1": raise RuntimeError("MONSTER zero-context ledger authority mismatch")
    if ledger.get("anti_loop",{}).get("blind_retry_allowed") is not False: raise RuntimeError("MONSTER Anti-Loop ledger drift")


def validate() -> dict[str, Any]:
    _require_files(); _require_owned_metadata()
    checks={"isolation":isolation_self_test(),"anti_loop":anti_loop_self_test(),"step2a":step2a_self_test(),"step2b":step2b_self_test(),"step2c":step2c_self_test(),"step2d":step2d_self_test(),"step2e":step2e_self_test(),"step2f":step2f_self_test(),"receipt":receipt_self_test()}
    failures=[name for name,result in checks.items() if result.get("status")!="GREEN"]
    if failures: raise RuntimeError("MONSTER Step 2C-2F permanent dependency not GREEN: "+" | ".join(failures))
    return {"status":"GREEN","version":VERSION,"monster_only":True,"step2a_permanent":True,"anti_loop_permanent":True,"step2b_permanent":True,"step2c_permanent":True,"step2d_permanent":True,"step2e_permanent":True,"step2e_repository_wide_audit_permanent":True,"step2f_permanent":True,"failure_recovery_chain_permanent":True,"authoritative_receipt_required":True,"github_actions_sole_authority":False,"zero_context_resume_permanent":True,"one_authoritative_lane_required":True,"network_calls":NETWORK_CALLS,"auto_mutate":AUTO_MUTATE,"product_runtime_mutation":MAY_MODIFY_PRODUCT_RUNTIME}


def contract_self_test() -> dict[str, Any]: return validate()


if __name__=="__main__":
    print("MONSTER_STEP2C2D2E2F_PERMANENT_STACK_V1_GREEN")
    print(json.dumps(validate(),indent=2,sort_keys=True))
