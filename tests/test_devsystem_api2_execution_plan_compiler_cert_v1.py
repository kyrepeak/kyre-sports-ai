from copy import deepcopy

import pytest

from devsystem.api2_execution_plan_compiler_cert_v1 import (
    Api2ExecutionPlanFailure,
    compile_api2_execution_plan,
    next_checkpoint,
    run_certification,
    self_test,
    validate_execution_plan,
)

HEAD = "a" * 40


def test_api2_native_compiler_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["checkpoint_count"] == 6
    assert result["deterministic_plan"] is True
    assert result["stale_plan_blocked"] is True
    assert result["tampered_plan_blocked"] is True
    assert result["dependency_bypass_blocked"] is True
    assert result["mutation_checkpoint"] == "04_EXECUTE"
    assert result["mutation_reenters_step2a"] is True
    assert result["mutation_authority_granted"] is False
    assert result["freeze_contract_complete"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False


def test_same_api2_base_compiles_identically():
    first = compile_api2_execution_plan(HEAD)
    second = compile_api2_execution_plan(HEAD)
    assert first == second
    assert first["system"] == "api2"
    assert first["authoritative_base_ref"] == "refs/heads/api2-main"
    assert first["plan_id"].startswith("API2-PLAN-")
    assert first["plan_digest"].startswith("sha256:")


def test_compiled_plan_is_bound_to_exact_api2_base():
    plan = compile_api2_execution_plan(HEAD)
    validate_execution_plan(plan, observed_base_sha=HEAD)
    with pytest.raises(Api2ExecutionPlanFailure, match="API2_STALE_COMPILED_PLAN"):
        validate_execution_plan(plan, observed_base_sha="b" * 40)


def test_checkpoint_history_must_be_monotonic_prefix():
    plan = compile_api2_execution_plan(HEAD)
    with pytest.raises(Api2ExecutionPlanFailure, match="API2_CHECKPOINT_HISTORY_NOT_MONOTONIC"):
        next_checkpoint(plan, observed_base_sha=HEAD, completed_checkpoint_ids=["01_TRUTH", "03_STEP2A_AUTHORIZATION"])


def test_execute_checkpoint_requires_step2a_and_never_grants_mutation_authority():
    plan = compile_api2_execution_plan(HEAD)
    mutation = next_checkpoint(plan, observed_base_sha=HEAD, completed_checkpoint_ids=["01_TRUTH", "02_STEP2B_PREFLIGHT", "03_STEP2A_AUTHORIZATION"])
    assert mutation["selected_checkpoint_id"] == "04_EXECUTE"
    assert mutation["next_legal_action"] == "CONSUME_STEP_2A_AUTHORIZATION:04_EXECUTE"
    assert mutation["step_2a_required"] is True
    assert mutation["mutation_authority"] is False


def test_tampered_api2_plan_fails_closed():
    plan = compile_api2_execution_plan(HEAD)
    tampered = deepcopy(plan)
    tampered["checkpoints"][3]["action_type"] = "READ_ONLY"
    with pytest.raises(Api2ExecutionPlanFailure, match="API2_PLAN_DIGEST_MISMATCH"):
        validate_execution_plan(tampered, observed_base_sha=HEAD)


def test_completion_requires_api2_freeze_contract():
    plan = compile_api2_execution_plan(HEAD)
    complete = next_checkpoint(plan, observed_base_sha=HEAD, completed_checkpoint_ids=plan["topological_order"])
    assert complete["decision"] == "PLAN_COMPLETE"
    assert complete["complete"] is True
    assert complete["next_legal_action"] == "VERIFY_API2_FREEZE_CONTRACT"
    assert complete["mutation_authority"] is False


def test_full_api2_compiler_certification_green():
    result = run_certification()
    assert result["status"] == "GREEN"
    assert result["topological_order"] == ["01_TRUTH", "02_STEP2B_PREFLIGHT", "03_STEP2A_AUTHORIZATION", "04_EXECUTE", "05_VERIFY", "06_FREEZE"]
