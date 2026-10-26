from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def _load(name,rel):
    path=ROOT/rel
    assert path.is_file(),f"required MONSTER module missing: {rel}"
    spec=importlib.util.spec_from_file_location(name,path); assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module


def test_authoritative_receipt_is_deterministic_and_rejects_foreign_evidence():
    receipt=_load("monster_authoritative_proof_receipt_v1","devsystem/monster_authoritative_proof_receipt_v1.py")
    payload={
        "task_id":"monster-step2c2d2e2f-permanent-stack-v1",
        "candidate_sha":"1"*40,
        "gates":{name:"GREEN" for name in ("step2a","anti_loop","step2c","step2b","execution","step2d","step2e","step2f","step2g","final_verify")},
        "regressions":{"status":"GREEN","count":99},
        "production":{"deployment_applicable":False,"proof":"NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE"},
        "convergence":{
            "status":"GREEN",
            "evidence_digest":"c"*64,
            "final_sha":"2"*40,
            "runtime_sha":"2"*40,
            "deployment_id":"monster-regression",
            "stable_alias":"https://pickvault.streamlit.app"
        },
        "rollback_anchor":{"sha":"0"*40},
        "freeze_target":"MONSTER_STEP2C2D2E2F_PERMANENT_STACK_V1_FROZEN",
        "evidence":{"source":"monster-only","value":"ok"}
    }
    first=receipt.build_receipt(payload); second=receipt.build_receipt(payload)
    assert first["receipt_digest"]==second["receipt_digest"]
    assert receipt.validate_receipt(first)["status"]=="GREEN"
    poisoned=json.loads(json.dumps(payload)); poisoned["evidence"]["source"]="api2-foreign-proof"
    assert receipt.build_receipt(poisoned)["status"]=="BLOCKED"


def test_permanent_stack_requires_all_owned_gates():
    gate=_load("mandatory_2c2d2e2f_permanent_enforcement_v1","devsystem/mandatory_2c2d2e2f_permanent_enforcement_v1.py")
    result=gate.validate()
    assert result["status"]=="GREEN" and result["monster_only"] is True
    for key in ("step2c_permanent","step2d_permanent","step2e_permanent","step2f_permanent","step2g_permanent","authoritative_receipt_required","zero_context_resume_permanent"):
        assert result[key] is True
    assert result["final_green_requires_step2g"] is True
    assert result["final_frozen_requires_step2g"] is True
    assert result["github_actions_sole_authority"] is False


def test_proof_workflow_is_single_lane_exact_sha_and_supporting_only():
    workflow=(ROOT/".github/workflows/monster-step2c2d2e2f-permanent-stack-v1.yml").read_text(encoding="utf-8")
    assert "branches: [monster-main]" in workflow
    assert "fetch-depth: 1" in workflow
    assert "persist-credentials: false" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "supporting-evidence-only" in workflow


def test_monster_proof_plan_and_ledgers_are_owned_and_bound():
    proof=json.loads((ROOT/"devsystem/monster_proof_plans/monster-step2c2d2e2f-permanent-stack-v1.json").read_text(encoding="utf-8"))
    ledger=json.loads((ROOT/"devsystem/task_ledgers/monster-step2c2d2e2f-permanent-stack-v1.json").read_text(encoding="utf-8"))
    assert proof["proof_authority"]=="MONSTER_ONLY"
    assert proof["github_actions_role"]=="SUPPORTING_EVIDENCE_ONLY"
    assert proof["freeze_target"]=="MONSTER_STEP2C2D2E2F_PERMANENT_STACK_V1_FROZEN"
    assert ledger["authoritative_branch"]=="monster-step2c2d2e2f-permanent-stack-v1"
    assert ledger["anti_loop"]["blind_retry_allowed"] is False
