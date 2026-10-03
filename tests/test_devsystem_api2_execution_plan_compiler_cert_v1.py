from copy import deepcopy

import pytest

from devsystem.api2_execution_plan_compiler_cert_v1 import (
    Api2ExecutionPlanFailure,
    compile_api2_execution_plan,
    run_certification,
    self_test,
)
from devsystem.execution_plan_compiler_v1 import (
    ExecutionPlanCompilerFailure,
    next_checkpoint,
    validate_execution_plan,
)


HEAD = "a" * 40


def test_step7_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["checkpoint_count"] == 6
    assert result["deterministic_plan"] is True
    assert result["rollback_dominates_mutations"] is True
    assert result["initial_checkpoint"] == "01_TRUTH"
    assert result["mutation_checkpoint"] == "03_MUTATION"
    assert result["mutation_reenters_step2a"] is True
    assert result["mutation_authority_granted"] is False
    assert result["stale_plan_blocked"] is True
    assert result["tampered_plan_blocked"] is True
    assert result["dependency_bypass_blocked"] is True
    assert result["freeze_contract_complete"] is True
    assert result["step6_adversarial_green"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False


def test_same_main_and_mission_compile_identically():
    first = compile_api2_execution_plan(HEAD)
    second = compile_api2_execution_plan(HEAD)
    assert first == second
    assert first["plan_id"].startswith("PLAN-")
    assert first["plan_digest"].startswith("sha256:")


def test_compiled_plan_is_bound_to_exact_main():
    plan = compile_api2_execution_plan(HEAD)
    validate_execution_plan(plan, observed_main_sha=HEAD)
    with pytest.raises(ExecutionPlanCompilerFailure, match="STALE_COMPILED_PLAN"):
        validate_execution_plan(plan, observed_main_sha="b" * 40)


def test_mutation_cannot_run_before_rollback_anchor():
    plan = compile_api2_execution_plan(HEAD)
    with pytest.raises(ExecutionPlanCompilerFailure, match="missing dependencies"):
        next_checkpoint(
            plan,
            observed_main_sha=HEAD,
            completed_checkpoint_ids=["01_TRUTH", "03_MUTATION"],
        )


def test_every_mutation_routes_back_to_step2a():
    plan = compile_api2_execution_plan(HEAD)
    mutation = next_checkpoint(
        plan,
        observed_main_sha=HEAD,
        completed_checkpoint_ids=["01_TRUTH", "02_BASELINE"],
    )
    assert mutation["selected_checkpoint_id"] == "03_MUTATION"
    assert mutation["next_legal_action"] == "REQUEST_STEP_2A_ACTION_GATE:03_MUTATION"
    assert mutation["mutation_authority"] is False


def test_tampered_write_scope_fails_closed():
    plan = compile_api2_execution_plan(HEAD)
    tampered = deepcopy(plan)
    tampered["checkpoints"][2]["write_paths"] = ["app.py"]
    with pytest.raises(ExecutionPlanCompilerFailure, match="digest mismatch"):
        validate_execution_plan(tampered, observed_main_sha=HEAD)


def test_plan_completion_requires_freeze_verification():
    plan = compile_api2_execution_plan(HEAD)
    complete = next_checkpoint(
        plan,
        observed_main_sha=HEAD,
        completed_checkpoint_ids=plan["topological_order"],
    )
    assert complete["decision"] == "PLAN_COMPLETE"
    assert complete["complete"] is True
    assert complete["next_legal_action"] == "VERIFY_FREEZE_CONTRACT"
    assert complete["mutation_authority"] is False


def test_full_certification_green():
    result = run_certification()
    assert result["status"] == "GREEN"
    assert result["topological_order"] == [
        "01_TRUTH",
        "02_BASELINE",
        "03_MUTATION",
        "04_PROOF",
        "05_MERGE",
        "06_FREEZE",
    ]
