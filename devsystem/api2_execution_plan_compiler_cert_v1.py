"""API2 Control-Plane Efficiency V1 Step 7 — Execution Plan Compiler Integration.

Final read-only integration over the frozen MONSTER V8 Execution Plan Compiler.

This layer certifies that future API2 missions are compiled into a deterministic
legal checkpoint graph before execution begins. The compiled plan binds exact
main identity, rollback dominance, write scope, shared resources, proof
obligations, Step 2A re-entry, and the final GREEN + FROZEN contract.

No network calls. No auto mutation. No mutation authority.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem import execution_plan_compiler_v1 as compiler
from devsystem import api2_chaos_adversarial_certifier_v1 as chaos

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP7_EXECUTION_PLAN_COMPILER_INTEGRATION_V1"
EXPECTED_COMPILER_VERSION = "MONSTER_V8_EXECUTION_PLAN_COMPILER_V1"
EXPECTED_STEP6_VERSION = (
    "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP6_CHAOS_ADVERSARIAL_CERTIFICATION_V1"
)
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False


class Api2ExecutionPlanFailure(RuntimeError):
    pass


def _parents_green() -> None:
    if compiler.VERSION != EXPECTED_COMPILER_VERSION:
        raise Api2ExecutionPlanFailure("frozen execution-plan compiler version drift")
    if chaos.VERSION != EXPECTED_STEP6_VERSION:
        raise Api2ExecutionPlanFailure("frozen API2 Step-6 parent version drift")


def _freeze_contract() -> dict[str, Any]:
    return {
        "exact_pr_head_proof": True,
        "devsystem_final_gate": True,
        "merge_exact_certified_head": True,
        "merged_main_proof": True,
        "terminal_proof_receipt": True,
        "green_plus_frozen": True,
        "freeze_tokens": ["GREEN", "FROZEN"],
    }


def _checkpoints() -> list[dict[str, Any]]:
    return [
        {
            "checkpoint_id": "01_TRUTH",
            "title": "Reconcile exact repository and workstream truth",
            "action_type": "READ_ONLY",
            "depends_on": [],
            "write_paths": [],
            "dependency_tokens": ["control:repository-truth"],
            "shared_resources": ["registry:intent"],
            "expected_proof": [
                "exact main identity",
                "single canonical workstream",
                "frozen parent registry aligned",
            ],
            "completion_criteria": ["authoritative truth snapshot sealed"],
        },
        {
            "checkpoint_id": "02_BASELINE",
            "title": "Seal rollback and blast-radius baseline",
            "action_type": "READ_ONLY",
            "depends_on": ["01_TRUTH"],
            "write_paths": [],
            "dependency_tokens": ["control:rollback-baseline"],
            "shared_resources": ["registry:rollback"],
            "expected_proof": [
                "pre-mutation blast simulation GREEN",
                "rollback baseline sealed",
            ],
            "completion_criteria": ["exact rollback anchor exists"],
        },
        {
            "checkpoint_id": "03_MUTATION",
            "title": "Apply exactly one approved scoped mutation",
            "action_type": "MUTATION",
            "depends_on": ["02_BASELINE"],
            "write_paths": ["devsystem/future_api2_control_plane_patch.py"],
            "dependency_tokens": ["domain:api2-control-plane"],
            "shared_resources": [
                "workflow:devsystem-targeted-ci#shard[domain=api2-control-plane]"
            ],
            "expected_proof": [
                "fresh Step 2A execution gate",
                "single-use mutation receipt",
            ],
            "completion_criteria": ["approved write surface changed exactly once"],
        },
        {
            "checkpoint_id": "04_PROOF",
            "title": "Certify exact candidate head",
            "action_type": "READ_ONLY",
            "depends_on": ["03_MUTATION"],
            "write_paths": [],
            "dependency_tokens": ["proof:exact-head"],
            "shared_resources": [
                "workflow:devsystem-targeted-ci#shard[domain=api2-control-plane]"
            ],
            "expected_proof": [
                "focused exact-head proof GREEN",
                "API2 convergence GREEN",
                "DevSystem final gate GREEN",
                "terminal proof receipt GREEN",
            ],
            "completion_criteria": ["exact candidate head certified"],
        },
        {
            "checkpoint_id": "05_MERGE",
            "title": "Merge the exact certified head",
            "action_type": "MUTATION",
            "depends_on": ["04_PROOF"],
            "write_paths": ["refs/heads/main"],
            "dependency_tokens": ["control:exact-certified-merge"],
            "shared_resources": ["git:protected-main"],
            "expected_proof": ["exact certified head merged once"],
            "completion_criteria": ["merge commit identity captured"],
        },
        {
            "checkpoint_id": "06_FREEZE",
            "title": "Certify merged main and freeze",
            "action_type": "READ_ONLY",
            "depends_on": ["05_MERGE"],
            "write_paths": [],
            "dependency_tokens": ["proof:merged-main", "registry:frozen"],
            "shared_resources": [
                "workflow:devsystem-targeted-ci#shard[domain=api2-control-plane]"
            ],
            "expected_proof": [
                "merged-main focused proof GREEN",
                "merged-main full certification GREEN",
                "merged-main DevSystem final gate GREEN",
                "merged-main terminal receipt GREEN",
                "authoritative frozen-registry read-back GREEN",
            ],
            "completion_criteria": ["mission GREEN + FROZEN"],
        },
    ]


def compile_api2_execution_plan(main_sha: str) -> dict[str, Any]:
    _parents_green()
    return compiler.compile_execution_plan(
        repository="kyrepeak/kyre-sports-ai",
        mission_id="api2-control-plane-efficiency-v1-future-mission-template",
        mission="Execute future API2 control-plane work from a compiled legal plan",
        expected_main_sha=main_sha,
        observed_main_sha=main_sha,
        checkpoints=_checkpoints(),
        rollback_checkpoint_id="02_BASELINE",
        freeze_contract=_freeze_contract(),
        completion_criteria=[
            "all compiled checkpoints complete in dependency order",
            "every mutation re-entered Step 2A",
            "exact certified head merged once",
            "merged main certified",
            "authoritative registry says GREEN + FROZEN",
        ],
    )


def run_certification() -> dict[str, Any]:
    _parents_green()

    parent = compiler.contract_self_test()
    if parent.get("status") != "GREEN":
        raise Api2ExecutionPlanFailure("frozen compiler self-test is not GREEN")

    step6 = chaos.self_test()
    if step6.get("status") != "GREEN" or step6.get("all_scenarios_pass") is not True:
        raise Api2ExecutionPlanFailure("API2 Step-6 adversarial certification is not GREEN")

    head = "a" * 40
    plan_a = compile_api2_execution_plan(head)
    plan_b = compile_api2_execution_plan(head)
    if plan_a != plan_b:
        raise Api2ExecutionPlanFailure("same mission did not compile deterministically")

    compiler.validate_execution_plan(plan_a, observed_main_sha=head)

    initial = compiler.next_checkpoint(
        plan_a,
        observed_main_sha=head,
        completed_checkpoint_ids=[],
    )
    mutation = compiler.next_checkpoint(
        plan_a,
        observed_main_sha=head,
        completed_checkpoint_ids=["01_TRUTH", "02_BASELINE"],
    )
    complete = compiler.next_checkpoint(
        plan_a,
        observed_main_sha=head,
        completed_checkpoint_ids=plan_a["topological_order"],
    )

    stale_blocked = False
    try:
        compiler.validate_execution_plan(plan_a, observed_main_sha="b" * 40)
    except compiler.ExecutionPlanCompilerFailure:
        stale_blocked = True

    tampered = deepcopy(plan_a)
    tampered["checkpoints"][2]["write_paths"] = ["app.py"]
    tamper_blocked = False
    try:
        compiler.validate_execution_plan(tampered, observed_main_sha=head)
    except compiler.ExecutionPlanCompilerFailure:
        tamper_blocked = True

    dependency_bypass_blocked = False
    try:
        compiler.next_checkpoint(
            plan_a,
            observed_main_sha=head,
            completed_checkpoint_ids=["01_TRUTH", "03_MUTATION"],
        )
    except compiler.ExecutionPlanCompilerFailure:
        dependency_bypass_blocked = True

    if not stale_blocked:
        raise Api2ExecutionPlanFailure("stale compiled plan was accepted")
    if not tamper_blocked:
        raise Api2ExecutionPlanFailure("tampered compiled plan was accepted")
    if not dependency_bypass_blocked:
        raise Api2ExecutionPlanFailure("checkpoint dependency bypass was accepted")
    if mutation.get("step_2a_required") is not True:
        raise Api2ExecutionPlanFailure("mutation did not require Step 2A")
    if mutation.get("mutation_authority") is not False:
        raise Api2ExecutionPlanFailure("compiler granted mutation authority")
    if complete.get("next_legal_action") != "VERIFY_FREEZE_CONTRACT":
        raise Api2ExecutionPlanFailure("plan completion did not route to freeze verification")

    return {
        "status": "GREEN",
        "version": VERSION,
        "compiler_version": compiler.VERSION,
        "step6_version": chaos.VERSION,
        "plan_id": plan_a["plan_id"],
        "plan_digest": plan_a["plan_digest"],
        "checkpoint_count": len(plan_a["checkpoints"]),
        "topological_order": plan_a["topological_order"],
        "deterministic_plan": plan_a == plan_b,
        "rollback_checkpoint_id": plan_a["rollback_checkpoint_id"],
        "rollback_dominates_mutations": parent["rollback_dominates_mutations"] is True,
        "initial_checkpoint": initial["selected_checkpoint_id"],
        "mutation_checkpoint": mutation["selected_checkpoint_id"],
        "mutation_reenters_step2a": mutation["step_2a_required"] is True,
        "mutation_authority_granted": mutation["mutation_authority"],
        "stale_plan_blocked": stale_blocked,
        "tampered_plan_blocked": tamper_blocked,
        "dependency_bypass_blocked": dependency_bypass_blocked,
        "freeze_contract_complete": complete["next_legal_action"] == "VERIFY_FREEZE_CONTRACT",
        "step6_adversarial_green": step6["all_scenarios_pass"] is True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def self_test() -> dict[str, Any]:
    result = run_certification()
    required_true = (
        "deterministic_plan",
        "rollback_dominates_mutations",
        "mutation_reenters_step2a",
        "stale_plan_blocked",
        "tampered_plan_blocked",
        "dependency_bypass_blocked",
        "freeze_contract_complete",
        "step6_adversarial_green",
    )
    missing = [key for key in required_true if result.get(key) is not True]
    if missing:
        raise Api2ExecutionPlanFailure("Step-7 certification failed: " + ", ".join(missing))
    if result["mutation_authority_granted"] is not False:
        raise Api2ExecutionPlanFailure("compiler mutation authority drift")
    return result


def main() -> int:
    result = self_test()
    print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP7_EXECUTION_PLAN_COMPILER_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Api2ExecutionPlanFailure as exc:
        print(
            "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP7_BLOCKED: " + str(exc),
            file=sys.stderr,
        )
        raise SystemExit(1)
