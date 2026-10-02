"""API2 Proof Architecture V1 Step 7 — End-to-End Proof Convergence.

Final read-only convergence layer for API2 Proof Architecture V1.

It proves that Steps 1–6 are still present as one coherent proof architecture,
that every prior step is represented by a compiled plan + completed task ledger,
and that the authoritative frozen registry still contains all six frozen
checkpoints before Step 7 may claim completion.

This module performs no network calls, creates no Git mutations, and grants no
product/runtime mutation authority.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.frozen_artifact_registry_v1 import validate_registry

VERSION = "API2_PROOF_ARCHITECTURE_V1_STEP7_END_TO_END_PROOF_CONVERGENCE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
PROJECT = "API2 Proof Architecture V1"

STEP_CONTRACTS = (
    {
        "step": "1/7",
        "checkpoint": "API2_PROOF_ARCHITECTURE_V1_STEP1",
        "title": "Exact Deployment SHA Gate",
        "ledger": "devsystem/task_ledgers/api2-proof-architecture-v1-step1-exact-deployment-sha-gate.json",
        "plan": "devsystem/execution_plans/api2-proof-architecture-v1-step1-exact-deployment-sha-gate.json",
        "engine": "devsystem/api2_exact_deployment_sha_gate_v1.py",
        "workflow": ".github/workflows/api2-proof-architecture-v1-step1-exact-deployment-sha-gate.yml",
    },
    {
        "step": "2/7",
        "checkpoint": "API2_PROOF_ARCHITECTURE_V1_STEP2",
        "title": "Required Integration Lanes",
        "ledger": "devsystem/task_ledgers/api2-proof-architecture-v1-step2-required-integration-lanes.json",
        "plan": "devsystem/execution_plans/api2-proof-architecture-v1-step2-required-integration-lanes.json",
        "engine": "devsystem/monster_speed_v3_step3_lane_split_v1.py",
        "workflow": ".github/workflows/api2-proof-architecture-v1-step2-required-integration-lanes.yml",
    },
    {
        "step": "3/7",
        "checkpoint": "API2_PROOF_ARCHITECTURE_V1_STEP3",
        "title": "Dependency Chain Auto Refresh",
        "ledger": "devsystem/task_ledgers/api2-proof-architecture-v1-step3-dependency-auto-refresh.json",
        "plan": "devsystem/execution_plans/api2-proof-architecture-v1-step3-dependency-auto-refresh.json",
        "engine": "devsystem/dependency_chain_auto_refresh_v1.py",
        "workflow": ".github/workflows/api2-proof-architecture-v1-step3-dependency-auto-refresh.yml",
    },
    {
        "step": "4/7",
        "checkpoint": "API2_PROOF_ARCHITECTURE_V1_STEP4",
        "title": "Upstream Blocker Short-Circuit",
        "ledger": "devsystem/task_ledgers/api2-proof-architecture-v1-step4-upstream-blocker-short-circuit.json",
        "plan": "devsystem/execution_plans/api2-proof-architecture-v1-step4-upstream-blocker-short-circuit.json",
        "engine": "devsystem/upstream_blocker_short_circuit_v1.py",
        "workflow": ".github/workflows/api2-proof-architecture-v1-step4-upstream-blocker-short-circuit.yml",
    },
    {
        "step": "5/7",
        "checkpoint": "API2_PROOF_ARCHITECTURE_V1_STEP5",
        "title": "Failure Ownership Separation",
        "ledger": "devsystem/task_ledgers/api2-proof-architecture-v1-step5-failure-domain-separation.json",
        "plan": "devsystem/execution_plans/api2-proof-architecture-v1-step5-failure-domain-separation.json",
        "engine": "devsystem/api2_failure_domain_router_v1.py",
        "workflow": ".github/workflows/api2-proof-architecture-v1-step5-failure-domain-separation.yml",
    },
    {
        "step": "6/7",
        "checkpoint": "API2_PROOF_ARCHITECTURE_V1_STEP6",
        "title": "Frozen Registry Lifecycle Reconciliation",
        "ledger": "devsystem/task_ledgers/api2-proof-architecture-v1-step6-frozen-registry-lifecycle.json",
        "plan": "devsystem/execution_plans/api2-proof-architecture-v1-step6-frozen-registry-lifecycle.json",
        "engine": "devsystem/api2_frozen_registry_lifecycle_v1.py",
        "workflow": ".github/workflows/api2-proof-architecture-v1-step6-frozen-registry-lifecycle.yml",
    },
)


class ProofConvergenceFailure(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProofConvergenceFailure(f"cannot read JSON contract: {path}") from exc
    if not isinstance(value, dict):
        raise ProofConvergenceFailure(f"contract must be an object: {path}")
    return value


def validate_local_architecture(root: Path | str | None = None) -> dict[str, Any]:
    repo = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    rows: list[dict[str, Any]] = []

    for contract in STEP_CONTRACTS:
        for field in ("ledger", "plan", "engine", "workflow"):
            path = repo / str(contract[field])
            if not path.is_file():
                raise ProofConvergenceFailure(
                    f"{contract['checkpoint']}: missing {field}: {contract[field]}"
                )

        ledger = _load_json(repo / str(contract["ledger"]))
        plan = _load_json(repo / str(contract["plan"]))

        if ledger.get("project") != PROJECT:
            raise ProofConvergenceFailure(
                f"{contract['checkpoint']}: project identity drift"
            )
        if ledger.get("step") != contract["step"]:
            raise ProofConvergenceFailure(
                f"{contract['checkpoint']}: ledger step identity drift"
            )
        if ledger.get("status") != "DONE":
            raise ProofConvergenceFailure(
                f"{contract['checkpoint']}: ledger is not DONE"
            )
        plan_step = plan.get("step")
        if plan_step is None:
            if contract["checkpoint"] != "API2_PROOF_ARCHITECTURE_V1_STEP1":
                raise ProofConvergenceFailure(
                    f"{contract['checkpoint']}: execution-plan step missing"
                )
            mission = str(plan.get("mission") or "")
            if "API2 Proof Architecture V1 Step 1 " not in mission:
                raise ProofConvergenceFailure(
                    f"{contract['checkpoint']}: legacy plan mission identity drift"
                )
        elif plan_step != contract["step"]:
            raise ProofConvergenceFailure(
                f"{contract['checkpoint']}: execution-plan step drift"
            )
        if plan.get("status") != "COMPILED":
            raise ProofConvergenceFailure(
                f"{contract['checkpoint']}: execution plan is not COMPILED"
            )
        base = str(plan.get("base_main_sha") or "").lower()
        if not _SHA40.fullmatch(base):
            raise ProofConvergenceFailure(
                f"{contract['checkpoint']}: execution plan base_main_sha invalid"
            )

        rows.append(
            {
                "step": contract["step"],
                "checkpoint": contract["checkpoint"],
                "ledger_status": ledger["status"],
                "plan_status": plan["status"],
                "base_main_sha": base,
            }
        )

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "LOCAL_ARCHITECTURE_CONVERGED",
        "project": PROJECT,
        "steps_proven": len(rows),
        "steps": rows,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority": MUTATION_AUTHORITY_GRANTED,
    }


def validate_authoritative_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_registry(payload)
    entries = payload.get("entries")
    if not isinstance(entries, Mapping):
        raise ProofConvergenceFailure("authoritative registry entries unavailable")

    required = [str(row["checkpoint"]) for row in STEP_CONTRACTS]
    missing = [checkpoint for checkpoint in required if checkpoint not in entries]
    if missing:
        raise ProofConvergenceFailure(
            "missing frozen API2 checkpoints: " + ", ".join(missing)
        )

    frozen_rows: list[dict[str, str]] = []
    for checkpoint in required:
        entry = entries[checkpoint]
        if not isinstance(entry, Mapping) or entry.get("status") != "FROZEN":
            raise ProofConvergenceFailure(f"{checkpoint}: not FROZEN")
        source_main_sha = str(entry.get("source_main_sha") or "").lower()
        if not _SHA40.fullmatch(source_main_sha):
            raise ProofConvergenceFailure(
                f"{checkpoint}: frozen source_main_sha invalid"
            )
        frozen_rows.append(
            {
                "checkpoint": checkpoint,
                "status": "FROZEN",
                "source_main_sha": source_main_sha,
            }
        )

    return {
        "version": VERSION,
        "status": "GREEN",
        "decision": "AUTHORITATIVE_FROZEN_CHAIN_CONVERGED",
        "registry_revision": int(payload["revision"]),
        "registry_state_hash": str(validated["state_hash"]),
        "required_checkpoint_count": len(required),
        "frozen_checkpoints": frozen_rows,
        "active_thaw_count": int(validated["active_thaw_count"]),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority": MUTATION_AUTHORITY_GRANTED,
    }


def contract_self_test(root: Path | str | None = None) -> dict[str, Any]:
    result = validate_local_architecture(root)
    if result["steps_proven"] != 6:
        raise ProofConvergenceFailure("Step 7 must prove exactly Steps 1–6")
    if any(
        (
            result["network_calls"],
            result["auto_mutate"],
            result["product_runtime_mutation"],
            result["mutation_authority"],
        )
    ):
        raise ProofConvergenceFailure("read-only safety boundary drift")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("self-test")
    audit = sub.add_parser("audit-registry")
    audit.add_argument("--registry-file", required=True)
    audit.add_argument("--json-out")

    args = parser.parse_args(argv)
    if args.command == "self-test":
        result = contract_self_test()
        print("API2_PROOF_ARCHITECTURE_V1_STEP7_LOCAL_CONVERGENCE_GREEN")
    else:
        payload = _load_json(Path(args.registry_file))
        result = validate_authoritative_registry(payload)
        print("API2_PROOF_ARCHITECTURE_V1_STEP7_REGISTRY_CONVERGENCE_GREEN")

    text = json.dumps(result, indent=2, sort_keys=True)
    if getattr(args, "json_out", None):
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
