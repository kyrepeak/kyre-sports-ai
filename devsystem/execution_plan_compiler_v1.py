"""MONSTER V8 Step 7 — Execution Plan Compiler V1.

Compiles a mission into a deterministic legal execution graph before execution.

The compiler binds the mission to exact repository identity and turns declared
checkpoint intent into one tamper-evident plan containing:
- checkpoint dependencies and deterministic topological order;
- write scope, dependency tokens, and shared-resource shards;
- expected proof for every checkpoint;
- one explicit rollback anchor that dominates all mutation checkpoints;
- the final freeze contract and completion criteria;
- mandatory Step 2A re-entry before every mutation.

The compiler is a read-only decision engine. It performs no network calls,
does not create branches/PRs/runs, and never grants mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.pre_mutation_blast_radius_simulator_v1 import (
    VERSION as BLAST_SIMULATOR_VERSION,
)
from devsystem.transactional_rollback_engine_v1 import (
    VERSION as ROLLBACK_ENGINE_VERSION,
)
from devsystem.cross_workstream_intent_arbiter_v1 import (
    VERSION as INTENT_ARBITER_VERSION,
)
from devsystem.adaptive_stuck_thresholds_v1 import (
    VERSION as ADAPTIVE_STUCK_VERSION,
)
from devsystem.chaos_adversarial_certification_harness_v1 import (
    VERSION as CHAOS_CERT_VERSION,
)
from devsystem.shared_resource_lease_sharding_v1 import parse_resource
from sports_api.monster_project_state_v1 import PROJECT_STATE_VERSION

VERSION = "MONSTER_V8_EXECUTION_PLAN_COMPILER_V1"

EXPECTED_DEPENDENCY_VERSIONS = {
    "step1_blast_simulator": "MONSTER_V8_PRE_MUTATION_BLAST_RADIUS_SIMULATOR_V1",
    "step2_rollback_engine": "MONSTER_V8_TRANSACTIONAL_ROLLBACK_ENGINE_V1",
    "step3_intent_arbiter": "MONSTER_V8_CROSS_WORKSTREAM_INTENT_ARBITER_V1",
    "step4_project_state": "MONSTER_PROJECT_STATE_V1",
    "step5_adaptive_stuck": "MONSTER_V8_ADAPTIVE_STUCK_THRESHOLDS_V1",
    "step6_chaos_certification": "MONSTER_V8_CHAOS_ADVERSARIAL_CERTIFICATION_HARNESS_V1",
}

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{1,127}$")
_ALLOWED_ACTION_TYPES = {"READ_ONLY", "MUTATION"}
_REQUIRED_FREEZE_FLAGS = (
    "exact_pr_head_proof",
    "devsystem_final_gate",
    "merge_exact_certified_head",
    "merged_main_proof",
    "terminal_proof_receipt",
    "green_plus_frozen",
)


class ExecutionPlanCompilerFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ExecutionPlanCompilerFailure(f"{field} is required")
    return out


def _identifier(value: Any, field: str) -> str:
    out = _text(value, field)
    if not _ID.fullmatch(out):
        raise ExecutionPlanCompilerFailure(f"{field} contains unsupported characters")
    return out


def _sha(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _SHA40.fullmatch(out):
        raise ExecutionPlanCompilerFailure(f"{field} must be a full git SHA")
    return out


def _path(value: Any, field: str = "path") -> str:
    out = str(value or "").strip().replace("\\", "/")
    while out.startswith("./"):
        out = out[2:]
    if (
        not out
        or out.startswith("/")
        or out.startswith("../")
        or ".." in PurePosixPath(out).parts
    ):
        raise ExecutionPlanCompilerFailure(f"{field} must be repository-relative")
    return out


def _unique_texts(values: Sequence[Any], field: str) -> list[str]:
    out = sorted({_text(value, field) for value in values})
    return out


def _unique_paths(values: Sequence[Any]) -> list[str]:
    return sorted({_path(value) for value in values})


def _dependency_versions() -> dict[str, str]:
    return {
        "step1_blast_simulator": BLAST_SIMULATOR_VERSION,
        "step2_rollback_engine": ROLLBACK_ENGINE_VERSION,
        "step3_intent_arbiter": INTENT_ARBITER_VERSION,
        "step4_project_state": PROJECT_STATE_VERSION,
        "step5_adaptive_stuck": ADAPTIVE_STUCK_VERSION,
        "step6_chaos_certification": CHAOS_CERT_VERSION,
    }


def _require_dependency_versions() -> None:
    actual = _dependency_versions()
    if actual != EXPECTED_DEPENDENCY_VERSIONS:
        raise ExecutionPlanCompilerFailure(
            "frozen MONSTER V8 dependency version drift: "
            + _canonical({"expected": EXPECTED_DEPENDENCY_VERSIONS, "actual": actual})
        )


def _normalize_checkpoint(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ExecutionPlanCompilerFailure("checkpoint must be an object")

    checkpoint_id = _identifier(raw.get("checkpoint_id"), "checkpoint_id")
    title = _text(raw.get("title"), f"{checkpoint_id}.title")
    action_type = _text(
        raw.get("action_type"), f"{checkpoint_id}.action_type"
    ).upper()
    if action_type not in _ALLOWED_ACTION_TYPES:
        raise ExecutionPlanCompilerFailure(
            f"{checkpoint_id}.action_type must be READ_ONLY or MUTATION"
        )

    depends_on = sorted(
        {
            _identifier(value, f"{checkpoint_id}.depends_on")
            for value in (raw.get("depends_on") or [])
        }
    )
    if checkpoint_id in depends_on:
        raise ExecutionPlanCompilerFailure(
            f"{checkpoint_id} cannot depend on itself"
        )

    write_paths = _unique_paths(raw.get("write_paths") or [])
    dependency_tokens = _unique_texts(
        raw.get("dependency_tokens") or [],
        f"{checkpoint_id}.dependency_token",
    )
    shared_resources = _unique_texts(
        raw.get("shared_resources") or [],
        f"{checkpoint_id}.shared_resource",
    )
    for resource in shared_resources:
        try:
            parse_resource(resource)
        except Exception as exc:
            raise ExecutionPlanCompilerFailure(
                f"{checkpoint_id}.shared_resource invalid: {resource}"
            ) from exc

    expected_proof = _unique_texts(
        raw.get("expected_proof") or [],
        f"{checkpoint_id}.expected_proof",
    )
    completion_criteria = _unique_texts(
        raw.get("completion_criteria") or [],
        f"{checkpoint_id}.completion_criteria",
    )
    if not expected_proof:
        raise ExecutionPlanCompilerFailure(
            f"{checkpoint_id} requires expected proof"
        )
    if not completion_criteria:
        raise ExecutionPlanCompilerFailure(
            f"{checkpoint_id} requires completion criteria"
        )
    if action_type == "MUTATION" and not write_paths:
        raise ExecutionPlanCompilerFailure(
            f"{checkpoint_id} mutation requires explicit write_paths"
        )

    return {
        "checkpoint_id": checkpoint_id,
        "title": title,
        "action_type": action_type,
        "depends_on": depends_on,
        "write_paths": write_paths,
        "dependency_tokens": dependency_tokens,
        "shared_resources": shared_resources,
        "expected_proof": expected_proof,
        "completion_criteria": completion_criteria,
        "step_2a_required": action_type == "MUTATION",
        "mutation_authority": False,
    }


def _checkpoint_map(
    checkpoints: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not checkpoints:
        raise ExecutionPlanCompilerFailure("at least one checkpoint is required")
    normalized = [_normalize_checkpoint(raw) for raw in checkpoints]
    ids = [row["checkpoint_id"] for row in normalized]
    if len(ids) != len(set(ids)):
        raise ExecutionPlanCompilerFailure("duplicate checkpoint_id")
    rows = {row["checkpoint_id"]: row for row in normalized}
    for row in normalized:
        missing = sorted(set(row["depends_on"]) - set(rows))
        if missing:
            raise ExecutionPlanCompilerFailure(
                f"{row['checkpoint_id']} has unknown dependencies: {missing}"
            )
    return rows


def _topological_order(
    rows: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    remaining = {
        checkpoint_id: set(row["depends_on"])
        for checkpoint_id, row in rows.items()
    }
    order: list[str] = []
    while remaining:
        ready = sorted(
            checkpoint_id
            for checkpoint_id, dependencies in remaining.items()
            if not dependencies
        )
        if not ready:
            raise ExecutionPlanCompilerFailure("checkpoint graph contains a cycle")
        for checkpoint_id in ready:
            order.append(checkpoint_id)
            del remaining[checkpoint_id]
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return order


def _ancestors(
    rows: Mapping[str, Mapping[str, Any]],
    checkpoint_id: str,
) -> set[str]:
    seen: set[str] = set()
    stack = list(rows[checkpoint_id]["depends_on"])
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(rows[current]["depends_on"])
    return seen


def _normalize_freeze_contract(
    raw: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ExecutionPlanCompilerFailure("freeze_contract must be an object")
    normalized: dict[str, Any] = {}
    for field in _REQUIRED_FREEZE_FLAGS:
        value = raw.get(field)
        if value is not True:
            raise ExecutionPlanCompilerFailure(
                f"freeze_contract.{field} must be true"
            )
        normalized[field] = True
    tokens = _unique_texts(
        raw.get("freeze_tokens") or [],
        "freeze_contract.freeze_token",
    )
    if "GREEN" not in tokens or "FROZEN" not in tokens:
        raise ExecutionPlanCompilerFailure(
            "freeze_contract requires GREEN and FROZEN tokens"
        )
    normalized["freeze_tokens"] = tokens
    return normalized


def _plan_core(plan: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "version",
        "repository",
        "mission_id",
        "mission",
        "base_main_sha",
        "dependency_versions",
        "checkpoints",
        "topological_order",
        "edges",
        "resource_plan",
        "proof_plan",
        "rollback_checkpoint_id",
        "freeze_contract",
        "completion_criteria",
        "step_2a_required",
        "mutation_authority",
        "network_calls",
        "auto_mutate",
        "may_modify_product_runtime",
    )
    return {key: deepcopy(plan[key]) for key in keys}


def compile_execution_plan(
    *,
    repository: str,
    mission_id: str,
    mission: str,
    expected_main_sha: str,
    observed_main_sha: str,
    checkpoints: Sequence[Mapping[str, Any]],
    rollback_checkpoint_id: str,
    freeze_contract: Mapping[str, Any],
    completion_criteria: Sequence[str],
) -> dict[str, Any]:
    _require_dependency_versions()

    repo = _text(repository, "repository")
    mid = _identifier(mission_id, "mission_id")
    mission_text = _text(mission, "mission")
    expected = _sha(expected_main_sha, "expected_main_sha")
    observed = _sha(observed_main_sha, "observed_main_sha")
    if expected != observed:
        raise ExecutionPlanCompilerFailure(
            "STALE_MAIN_IDENTITY: expected_main_sha != observed_main_sha"
        )

    rows = _checkpoint_map(checkpoints)
    order = _topological_order(rows)

    rollback_id = _identifier(
        rollback_checkpoint_id, "rollback_checkpoint_id"
    )
    if rollback_id not in rows:
        raise ExecutionPlanCompilerFailure(
            "rollback_checkpoint_id must name a checkpoint"
        )

    mutation_ids = [
        checkpoint_id
        for checkpoint_id, row in rows.items()
        if row["action_type"] == "MUTATION"
    ]
    for checkpoint_id in mutation_ids:
        if checkpoint_id == rollback_id:
            raise ExecutionPlanCompilerFailure(
                "rollback checkpoint must precede mutation checkpoints"
            )
        if rollback_id not in _ancestors(rows, checkpoint_id):
            raise ExecutionPlanCompilerFailure(
                f"rollback checkpoint does not dominate mutation {checkpoint_id}"
            )

    final_completion = _unique_texts(
        completion_criteria, "completion_criterion"
    )
    if not final_completion:
        raise ExecutionPlanCompilerFailure(
            "mission completion criteria are required"
        )
    freeze = _normalize_freeze_contract(freeze_contract)

    ordered_checkpoints = [deepcopy(rows[checkpoint_id]) for checkpoint_id in order]
    edges = sorted(
        [
            {"from": dependency, "to": checkpoint_id}
            for checkpoint_id, row in rows.items()
            for dependency in row["depends_on"]
        ],
        key=lambda edge: (edge["from"], edge["to"]),
    )
    resource_plan = {
        "write_paths": sorted(
            {
                path
                for row in rows.values()
                for path in row["write_paths"]
            }
        ),
        "dependency_tokens": sorted(
            {
                token
                for row in rows.values()
                for token in row["dependency_tokens"]
            }
        ),
        "shared_resources": sorted(
            {
                resource
                for row in rows.values()
                for resource in row["shared_resources"]
            }
        ),
    }
    proof_plan = {
        checkpoint_id: deepcopy(rows[checkpoint_id]["expected_proof"])
        for checkpoint_id in order
    }

    plan: dict[str, Any] = {
        "version": VERSION,
        "repository": repo,
        "mission_id": mid,
        "mission": mission_text,
        "base_main_sha": expected,
        "dependency_versions": deepcopy(EXPECTED_DEPENDENCY_VERSIONS),
        "checkpoints": ordered_checkpoints,
        "topological_order": order,
        "edges": edges,
        "resource_plan": resource_plan,
        "proof_plan": proof_plan,
        "rollback_checkpoint_id": rollback_id,
        "freeze_contract": freeze,
        "completion_criteria": final_completion,
        "step_2a_required": True,
        "mutation_authority": False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    digest = _digest(_plan_core(plan))
    plan["plan_id"] = "PLAN-" + digest[:24].upper()
    plan["plan_digest"] = "sha256:" + digest
    plan["status"] = "COMPILED"
    plan["decision"] = "EXECUTE_COMPILED_PLAN"
    plan["next_legal_action"] = "ENTER_CHECKPOINT:" + order[0]
    return plan


def validate_execution_plan(
    payload: Mapping[str, Any],
    *,
    observed_main_sha: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ExecutionPlanCompilerFailure("execution plan must be an object")
    plan = deepcopy(dict(payload))
    if plan.get("version") != VERSION:
        raise ExecutionPlanCompilerFailure("execution plan version mismatch")
    if plan.get("status") != "COMPILED":
        raise ExecutionPlanCompilerFailure("execution plan status must be COMPILED")
    if plan.get("decision") != "EXECUTE_COMPILED_PLAN":
        raise ExecutionPlanCompilerFailure("execution plan decision mismatch")

    _require_dependency_versions()
    if plan.get("dependency_versions") != EXPECTED_DEPENDENCY_VERSIONS:
        raise ExecutionPlanCompilerFailure("execution plan dependency version drift")

    observed = _sha(observed_main_sha, "observed_main_sha")
    base = _sha(plan.get("base_main_sha"), "base_main_sha")
    if base != observed:
        raise ExecutionPlanCompilerFailure(
            "STALE_COMPILED_PLAN: base_main_sha != observed_main_sha"
        )

    rows = _checkpoint_map(plan.get("checkpoints") or [])
    order = _topological_order(rows)
    if plan.get("topological_order") != order:
        raise ExecutionPlanCompilerFailure("topological_order mismatch")

    expected_edges = sorted(
        [
            {"from": dependency, "to": checkpoint_id}
            for checkpoint_id, row in rows.items()
            for dependency in row["depends_on"]
        ],
        key=lambda edge: (edge["from"], edge["to"]),
    )
    if plan.get("edges") != expected_edges:
        raise ExecutionPlanCompilerFailure("edge manifest mismatch")

    rollback_id = _identifier(
        plan.get("rollback_checkpoint_id"), "rollback_checkpoint_id"
    )
    if rollback_id not in rows:
        raise ExecutionPlanCompilerFailure("rollback checkpoint missing")
    for checkpoint_id, row in rows.items():
        if row["action_type"] == "MUTATION":
            if rollback_id == checkpoint_id or rollback_id not in _ancestors(
                rows, checkpoint_id
            ):
                raise ExecutionPlanCompilerFailure(
                    "rollback checkpoint does not dominate every mutation"
                )

    freeze = _normalize_freeze_contract(plan.get("freeze_contract"))
    if freeze != plan.get("freeze_contract"):
        raise ExecutionPlanCompilerFailure("freeze contract normalization mismatch")

    if plan.get("step_2a_required") is not True:
        raise ExecutionPlanCompilerFailure("Step 2A requirement missing")
    if plan.get("mutation_authority") is not False:
        raise ExecutionPlanCompilerFailure("compiler cannot grant mutation authority")
    if (
        plan.get("network_calls") is not False
        or plan.get("auto_mutate") is not False
        or plan.get("may_modify_product_runtime") is not False
    ):
        raise ExecutionPlanCompilerFailure("read-only safety contract drift")

    digest = str(plan.get("plan_digest") or "").lower()
    if not digest.startswith("sha256:") or not _HASH64.fullmatch(digest[7:]):
        raise ExecutionPlanCompilerFailure("plan_digest malformed")
    expected_digest = "sha256:" + _digest(_plan_core(plan))
    if digest != expected_digest:
        raise ExecutionPlanCompilerFailure("execution plan digest mismatch")
    expected_plan_id = "PLAN-" + expected_digest[7:31].upper()
    if plan.get("plan_id") != expected_plan_id:
        raise ExecutionPlanCompilerFailure("execution plan id mismatch")

    return plan


def next_checkpoint(
    payload: Mapping[str, Any],
    *,
    observed_main_sha: str,
    completed_checkpoint_ids: Sequence[str],
) -> dict[str, Any]:
    plan = validate_execution_plan(
        payload, observed_main_sha=observed_main_sha
    )
    rows = {
        row["checkpoint_id"]: row
        for row in plan["checkpoints"]
    }
    completed = {
        _identifier(value, "completed_checkpoint_id")
        for value in completed_checkpoint_ids
    }
    unknown = sorted(completed - set(rows))
    if unknown:
        raise ExecutionPlanCompilerFailure(
            f"unknown completed checkpoints: {unknown}"
        )

    for checkpoint_id in completed:
        missing = sorted(set(rows[checkpoint_id]["depends_on"]) - completed)
        if missing:
            raise ExecutionPlanCompilerFailure(
                f"completed checkpoint {checkpoint_id} is missing dependencies: {missing}"
            )

    if len(completed) == len(rows):
        return {
            "decision": "PLAN_COMPLETE",
            "complete": True,
            "ready_checkpoint_ids": [],
            "next_legal_action": "VERIFY_FREEZE_CONTRACT",
            "mutation_authority": False,
        }

    ready = [
        checkpoint_id
        for checkpoint_id in plan["topological_order"]
        if checkpoint_id not in completed
        and set(rows[checkpoint_id]["depends_on"]).issubset(completed)
    ]
    if not ready:
        raise ExecutionPlanCompilerFailure(
            "no legal checkpoint is ready; compiled plan state is inconsistent"
        )

    first = ready[0]
    row = rows[first]
    if row["action_type"] == "MUTATION":
        action = "REQUEST_STEP_2A_ACTION_GATE:" + first
    else:
        action = "EXECUTE_READ_ONLY_CHECKPOINT:" + first
    return {
        "decision": "CHECKPOINT_READY",
        "complete": False,
        "ready_checkpoint_ids": ready,
        "selected_checkpoint_id": first,
        "selected_action_type": row["action_type"],
        "step_2a_required": row["step_2a_required"],
        "next_legal_action": action,
        "mutation_authority": False,
    }


def _self_test_checkpoints() -> list[dict[str, Any]]:
    return [
        {
            "checkpoint_id": "01_INTENT",
            "title": "Register canonical mission intent",
            "action_type": "READ_ONLY",
            "depends_on": [],
            "write_paths": [],
            "dependency_tokens": ["control:mission"],
            "shared_resources": ["registry:intent"],
            "expected_proof": ["intent arbiter ALLOW_NEW_INTENT"],
            "completion_criteria": ["canonical intent exists"],
        },
        {
            "checkpoint_id": "02_BASELINE",
            "title": "Seal blast-radius and rollback baseline",
            "action_type": "READ_ONLY",
            "depends_on": ["01_INTENT"],
            "write_paths": [],
            "dependency_tokens": ["control:baseline"],
            "shared_resources": ["registry:rollback"],
            "expected_proof": [
                "blast simulation GREEN",
                "rollback baseline sealed",
            ],
            "completion_criteria": ["exact base identity sealed"],
        },
        {
            "checkpoint_id": "03_MUTATE",
            "title": "Apply exact approved mutation",
            "action_type": "MUTATION",
            "depends_on": ["02_BASELINE"],
            "write_paths": ["feature.py"],
            "dependency_tokens": ["domain:feature"],
            "shared_resources": ["workflow:devsystem-targeted-ci#shard[domain=feature]"],
            "expected_proof": ["Step 2A execution receipt consumed once"],
            "completion_criteria": ["approved write surface changed exactly once"],
        },
        {
            "checkpoint_id": "04_PROVE",
            "title": "Run exact-head certification",
            "action_type": "READ_ONLY",
            "depends_on": ["03_MUTATE"],
            "write_paths": [],
            "dependency_tokens": ["proof:exact-head"],
            "shared_resources": ["workflow:devsystem-targeted-ci#shard[domain=feature]"],
            "expected_proof": [
                "focused proof success",
                "devsystem-final-gate success",
                "terminal proof receipt success",
            ],
            "completion_criteria": ["exact head certified"],
        },
        {
            "checkpoint_id": "05_MERGE",
            "title": "Merge exact certified head",
            "action_type": "MUTATION",
            "depends_on": ["04_PROVE"],
            "write_paths": ["refs/heads/main"],
            "dependency_tokens": ["control:merge"],
            "shared_resources": ["git:protected-main"],
            "expected_proof": ["exact certified head merged"],
            "completion_criteria": ["merge commit identity captured"],
        },
        {
            "checkpoint_id": "06_FREEZE",
            "title": "Certify merged main and freeze",
            "action_type": "READ_ONLY",
            "depends_on": ["05_MERGE"],
            "write_paths": [],
            "dependency_tokens": ["proof:merged-main"],
            "shared_resources": ["workflow:devsystem-targeted-ci#shard[domain=feature]"],
            "expected_proof": [
                "merged-main focused proof success",
                "merged-main full certification success",
                "merged-main terminal receipt success",
            ],
            "completion_criteria": ["GREEN + FROZEN"],
        },
    ]


def _self_test_freeze() -> dict[str, Any]:
    return {
        "exact_pr_head_proof": True,
        "devsystem_final_gate": True,
        "merge_exact_certified_head": True,
        "merged_main_proof": True,
        "terminal_proof_receipt": True,
        "green_plus_frozen": True,
        "freeze_tokens": ["GREEN", "FROZEN"],
    }


def contract_self_test() -> dict[str, Any]:
    head = "a" * 40
    plan = compile_execution_plan(
        repository="owner/repo",
        mission_id="monster-v8-step7-self-test",
        mission="Compile execution graph before work begins",
        expected_main_sha=head,
        observed_main_sha=head,
        checkpoints=_self_test_checkpoints(),
        rollback_checkpoint_id="02_BASELINE",
        freeze_contract=_self_test_freeze(),
        completion_criteria=[
            "all declared checkpoints complete",
            "merged main certified",
            "mission GREEN + FROZEN",
        ],
    )
    validate_execution_plan(plan, observed_main_sha=head)

    first = next_checkpoint(
        plan, observed_main_sha=head, completed_checkpoint_ids=[]
    )
    mutation = next_checkpoint(
        plan,
        observed_main_sha=head,
        completed_checkpoint_ids=["01_INTENT", "02_BASELINE"],
    )
    complete = next_checkpoint(
        plan,
        observed_main_sha=head,
        completed_checkpoint_ids=plan["topological_order"],
    )

    stale_blocked = False
    try:
        validate_execution_plan(plan, observed_main_sha="b" * 40)
    except ExecutionPlanCompilerFailure:
        stale_blocked = True

    tampered = deepcopy(plan)
    tampered["checkpoints"][2]["write_paths"] = ["evil.py"]
    tamper_blocked = False
    try:
        validate_execution_plan(tampered, observed_main_sha=head)
    except ExecutionPlanCompilerFailure:
        tamper_blocked = True

    cycle_blocked = False
    cyclic = _self_test_checkpoints()
    cyclic[0]["depends_on"] = ["06_FREEZE"]
    try:
        compile_execution_plan(
            repository="owner/repo",
            mission_id="cycle-test",
            mission="cycle test",
            expected_main_sha=head,
            observed_main_sha=head,
            checkpoints=cyclic,
            rollback_checkpoint_id="02_BASELINE",
            freeze_contract=_self_test_freeze(),
            completion_criteria=["must fail"],
        )
    except ExecutionPlanCompilerFailure:
        cycle_blocked = True

    bypass_blocked = False
    try:
        next_checkpoint(
            plan,
            observed_main_sha=head,
            completed_checkpoint_ids=["01_INTENT", "03_MUTATE"],
        )
    except ExecutionPlanCompilerFailure:
        bypass_blocked = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "dependency_versions_bound": (
            _dependency_versions() == EXPECTED_DEPENDENCY_VERSIONS
        ),
        "deterministic_topological_order": (
            plan["topological_order"]
            == [
                "01_INTENT",
                "02_BASELINE",
                "03_MUTATE",
                "04_PROVE",
                "05_MERGE",
                "06_FREEZE",
            ]
        ),
        "resource_shards_compiled": (
            "workflow:devsystem-targeted-ci#shard[domain=feature]"
            in plan["resource_plan"]["shared_resources"]
        ),
        "proof_plan_compiled": (
            set(plan["proof_plan"]) == set(plan["topological_order"])
        ),
        "rollback_dominates_mutations": True,
        "freeze_contract_complete": all(
            plan["freeze_contract"][field] is True
            for field in _REQUIRED_FREEZE_FLAGS
        ),
        "read_only_first_checkpoint": (
            first["next_legal_action"]
            == "EXECUTE_READ_ONLY_CHECKPOINT:01_INTENT"
        ),
        "mutation_reenters_step2a": (
            mutation["next_legal_action"]
            == "REQUEST_STEP_2A_ACTION_GATE:03_MUTATE"
            and mutation["mutation_authority"] is False
        ),
        "plan_completion_routes_to_freeze": (
            complete["decision"] == "PLAN_COMPLETE"
            and complete["next_legal_action"] == "VERIFY_FREEZE_CONTRACT"
        ),
        "stale_plan_blocked": stale_blocked,
        "tampered_plan_blocked": tamper_blocked,
        "cycle_blocked": cycle_blocked,
        "dependency_bypass_blocked": bypass_blocked,
        "tamper_evident_digest": str(plan["plan_digest"]).startswith("sha256:"),
        "step_2a_required": plan["step_2a_required"] is True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = (
        "dependency_versions_bound",
        "deterministic_topological_order",
        "resource_shards_compiled",
        "proof_plan_compiled",
        "rollback_dominates_mutations",
        "freeze_contract_complete",
        "read_only_first_checkpoint",
        "mutation_reenters_step2a",
        "plan_completion_routes_to_freeze",
        "stale_plan_blocked",
        "tampered_plan_blocked",
        "cycle_blocked",
        "dependency_bypass_blocked",
        "tamper_evident_digest",
        "step_2a_required",
    )
    if not all(result[name] is True for name in required):
        raise ExecutionPlanCompilerFailure(
            "execution plan compiler self-test failed"
        )
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["product_runtime_mutation"]
        or result["mutation_authority_granted"]
    ):
        raise ExecutionPlanCompilerFailure("read-only safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V8_STEP7_EXECUTION_PLAN_COMPILER_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExecutionPlanCompilerFailure as exc:
        print("MONSTER_V8_STEP7_EXECUTION_PLAN_COMPILER_BLOCKED: " + str(exc))
        raise SystemExit(1)
