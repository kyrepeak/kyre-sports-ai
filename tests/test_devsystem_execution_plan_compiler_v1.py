from __future__ import annotations

import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.execution_plan_compiler_v1 import (
    ExecutionPlanCompilerFailure,
    VERSION,
    compile_execution_plan,
    contract_self_test,
    next_checkpoint,
    validate_execution_plan,
)


ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40


def _freeze():
    return {
        "exact_pr_head_proof": True,
        "devsystem_final_gate": True,
        "merge_exact_certified_head": True,
        "merged_main_proof": True,
        "terminal_proof_receipt": True,
        "green_plus_frozen": True,
        "freeze_tokens": ["GREEN", "FROZEN"],
    }


def _checkpoints():
    return [
        {
            "checkpoint_id": "01_INTENT",
            "title": "Register intent",
            "action_type": "READ_ONLY",
            "depends_on": [],
            "expected_proof": ["canonical intent"],
            "completion_criteria": ["intent active"],
            "shared_resources": ["registry:intent"],
        },
        {
            "checkpoint_id": "02_BASELINE",
            "title": "Seal rollback baseline",
            "action_type": "READ_ONLY",
            "depends_on": ["01_INTENT"],
            "expected_proof": ["blast GREEN", "baseline sealed"],
            "completion_criteria": ["exact baseline"],
            "shared_resources": ["registry:rollback"],
        },
        {
            "checkpoint_id": "03_PATCH",
            "title": "Apply patch",
            "action_type": "MUTATION",
            "depends_on": ["02_BASELINE"],
            "write_paths": ["devsystem/example.py"],
            "dependency_tokens": ["domain:control-plane"],
            "shared_resources": [
                "workflow:devsystem-targeted-ci#shard[domain=monster-v8]"
            ],
            "expected_proof": ["single-use Step 2A receipt"],
            "completion_criteria": ["exact scoped mutation applied"],
        },
        {
            "checkpoint_id": "04_PROOF",
            "title": "Prove exact head",
            "action_type": "READ_ONLY",
            "depends_on": ["03_PATCH"],
            "shared_resources": [
                "workflow:devsystem-targeted-ci#shard[domain=monster-v8]"
            ],
            "expected_proof": ["focused GREEN", "final gate GREEN"],
            "completion_criteria": ["exact head certified"],
        },
        {
            "checkpoint_id": "05_MERGE",
            "title": "Merge certified head",
            "action_type": "MUTATION",
            "depends_on": ["04_PROOF"],
            "write_paths": ["refs/heads/main"],
            "shared_resources": ["git:protected-main"],
            "expected_proof": ["exact head merged"],
            "completion_criteria": ["merge identity captured"],
        },
        {
            "checkpoint_id": "06_FREEZE",
            "title": "Merged-main freeze",
            "action_type": "READ_ONLY",
            "depends_on": ["05_MERGE"],
            "expected_proof": ["merged-main GREEN", "terminal receipt GREEN"],
            "completion_criteria": ["GREEN + FROZEN"],
        },
    ]


def _plan(checkpoints=None, head=HEAD):
    return compile_execution_plan(
        repository="kyrepeak/kyre-sports-ai",
        mission_id="monster-v8-step7-test",
        mission="Compile the mission before execution",
        expected_main_sha=head,
        observed_main_sha=head,
        checkpoints=checkpoints or _checkpoints(),
        rollback_checkpoint_id="02_BASELINE",
        freeze_contract=_freeze(),
        completion_criteria=[
            "all checkpoints complete",
            "merged main certified",
            "mission frozen",
        ],
    )


def test_contract_self_test_green_and_read_only():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["version"] == VERSION
    assert result["dependency_versions_bound"] is True
    assert result["deterministic_topological_order"] is True
    assert result["resource_shards_compiled"] is True
    assert result["proof_plan_compiled"] is True
    assert result["rollback_dominates_mutations"] is True
    assert result["freeze_contract_complete"] is True
    assert result["mutation_reenters_step2a"] is True
    assert result["stale_plan_blocked"] is True
    assert result["tampered_plan_blocked"] is True
    assert result["cycle_blocked"] is True
    assert result["dependency_bypass_blocked"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_compiler_is_deterministic_for_same_mission():
    first = _plan()
    second = _plan()
    assert first == second
    assert first["plan_digest"].startswith("sha256:")
    assert first["plan_id"].startswith("PLAN-")


def test_stale_main_fails_closed_before_execution():
    with pytest.raises(ExecutionPlanCompilerFailure, match="STALE_MAIN_IDENTITY"):
        compile_execution_plan(
            repository="kyrepeak/kyre-sports-ai",
            mission_id="stale-test",
            mission="stale main test",
            expected_main_sha="a" * 40,
            observed_main_sha="b" * 40,
            checkpoints=_checkpoints(),
            rollback_checkpoint_id="02_BASELINE",
            freeze_contract=_freeze(),
            completion_criteria=["never run stale"],
        )


def test_unknown_dependency_and_cycle_fail_closed():
    unknown = _checkpoints()
    unknown[2]["depends_on"] = ["DOES_NOT_EXIST"]
    with pytest.raises(ExecutionPlanCompilerFailure, match="unknown dependencies"):
        _plan(unknown)

    cycle = _checkpoints()
    cycle[0]["depends_on"] = ["06_FREEZE"]
    with pytest.raises(ExecutionPlanCompilerFailure, match="cycle"):
        _plan(cycle)


def test_every_mutation_must_be_downstream_of_rollback_anchor():
    bypass = _checkpoints()
    bypass[2]["depends_on"] = ["01_INTENT"]
    with pytest.raises(
        ExecutionPlanCompilerFailure,
        match="rollback checkpoint does not dominate",
    ):
        _plan(bypass)


def test_tampered_plan_digest_fails_closed():
    plan = _plan()
    tampered = deepcopy(plan)
    tampered["mission"] = "silently changed mission"
    with pytest.raises(ExecutionPlanCompilerFailure, match="digest mismatch"):
        validate_execution_plan(tampered, observed_main_sha=HEAD)


def test_next_checkpoint_never_grants_mutation_authority():
    plan = _plan()
    first = next_checkpoint(
        plan,
        observed_main_sha=HEAD,
        completed_checkpoint_ids=[],
    )
    assert first["selected_checkpoint_id"] == "01_INTENT"
    assert first["mutation_authority"] is False

    mutation = next_checkpoint(
        plan,
        observed_main_sha=HEAD,
        completed_checkpoint_ids=["01_INTENT", "02_BASELINE"],
    )
    assert mutation["selected_checkpoint_id"] == "03_PATCH"
    assert mutation["step_2a_required"] is True
    assert mutation["next_legal_action"] == "REQUEST_STEP_2A_ACTION_GATE:03_PATCH"
    assert mutation["mutation_authority"] is False


def test_cannot_claim_child_complete_before_dependency():
    plan = _plan()
    with pytest.raises(ExecutionPlanCompilerFailure, match="missing dependencies"):
        next_checkpoint(
            plan,
            observed_main_sha=HEAD,
            completed_checkpoint_ids=["01_INTENT", "03_PATCH"],
        )


def test_freeze_contract_cannot_be_weakened():
    weak = _freeze()
    weak["terminal_proof_receipt"] = False
    with pytest.raises(
        ExecutionPlanCompilerFailure,
        match="terminal_proof_receipt must be true",
    ):
        compile_execution_plan(
            repository="kyrepeak/kyre-sports-ai",
            mission_id="weak-freeze",
            mission="weak freeze test",
            expected_main_sha=HEAD,
            observed_main_sha=HEAD,
            checkpoints=_checkpoints(),
            rollback_checkpoint_id="02_BASELINE",
            freeze_contract=weak,
            completion_criteria=["must fail"],
        )


def test_direct_script_execution_green():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "devsystem" / "execution_plan_compiler_v1.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V8_STEP7_EXECUTION_PLAN_COMPILER_GREEN" in completed.stdout
