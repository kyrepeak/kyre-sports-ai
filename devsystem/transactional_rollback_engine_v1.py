"""MONSTER V8 Step 2 — Transactional Rollback Engine V1.

Rollback is path-scoped and evidence-bound. The engine never rewinds a whole
repository ref and never invents a repair. It restores only transaction-owned
surfaces to a pre-sealed, previously proven GREEN baseline.

Lifecycle:

    PREPARED
      -> MUTATION_APPLIED
      -> CLOSED_SUCCESS

or, on a terminal mutation failure:

    PREPARED
      -> MUTATION_APPLIED
      -> FAILURE_CONFIRMED
      -> RESTORE_ISSUED
      -> RECERTIFY
      -> CLOSED_ROLLED_BACK

Before RESTORE_ISSUED, the engine proves that each owned path/resource still
contains the exact state produced by this failed mutation and that baseline
dependencies have not drifted. This permits unrelated newer commits elsewhere
while preventing rollback from clobbering a newer writer on the same surface.

This module performs no network calls and grants no mutation authority.
External restore and proof actions still require Step 2A.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.pre_mutation_blast_radius_simulator_v1 import (
    VERSION as BLAST_SIMULATOR_VERSION,
)
from devsystem.terminal_proof_receipt_v1 import (
    VERSION as TERMINAL_RECEIPT_VERSION,
    validate_receipt,
)

VERSION = "MONSTER_V8_TRANSACTIONAL_ROLLBACK_ENGINE_V1"
REQUIRED_BLAST_SIMULATOR_VERSION = "MONSTER_V8_PRE_MUTATION_BLAST_RADIUS_SIMULATOR_V1"
REQUIRED_TERMINAL_RECEIPT_VERSION = "MONSTER_V4_TERMINAL_PROOF_RECEIPT_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_PHASES = {
    "PREPARED",
    "MUTATION_APPLIED",
    "FAILURE_CONFIRMED",
    "RESTORE_ISSUED",
    "RECERTIFY",
    "CLOSED_SUCCESS",
    "CLOSED_ROLLED_BACK",
    "BLOCKED",
}


class TransactionalRollbackFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise TransactionalRollbackFailure(f"{field} is required")
    return out


def _sha(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _SHA40.fullmatch(out):
        raise TransactionalRollbackFailure(f"{field} must be a full git SHA")
    return out


def _path(value: Any) -> str:
    out = str(value or "").strip().replace("\\", "/")
    while out.startswith("./"):
        out = out[2:]
    if not out or out.startswith("/") or ".." in Path(out).parts:
        raise TransactionalRollbackFailure("invalid repository-relative path")
    return out


def _blob(value: Any, field: str, *, allow_none: bool) -> str | None:
    if value is None and allow_none:
        return None
    return _sha(value, field)


def _blob_map(
    payload: Mapping[str, Any],
    field: str,
    *,
    allow_none: bool,
) -> dict[str, str | None]:
    if not isinstance(payload, Mapping):
        raise TransactionalRollbackFailure(f"{field} must be an object")
    out: dict[str, str | None] = {}
    for raw_path, raw_blob in payload.items():
        path = _path(raw_path)
        if path in out:
            raise TransactionalRollbackFailure(f"duplicate path in {field}: {path}")
        out[path] = _blob(raw_blob, f"{field}[{path}]", allow_none=allow_none)
    return dict(sorted(out.items()))


def _resource_map(
    payload: Mapping[str, Any] | None,
    field: str,
) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise TransactionalRollbackFailure(f"{field} must be an object")
    out: dict[str, str] = {}
    for key, value in payload.items():
        name = _text(key, f"{field} key")
        if name in out:
            raise TransactionalRollbackFailure(f"duplicate resource in {field}: {name}")
        out[name] = _text(value, f"{field}[{name}]")
    return dict(sorted(out.items()))


def _receipt_hash(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _HASH64.fullmatch(out):
        raise TransactionalRollbackFailure(f"{field} must be sha256")
    return out


def _simulation_core(receipt: Mapping[str, Any]) -> dict[str, Any]:
    legacy = receipt.get("legacy_blast")
    if not isinstance(legacy, Mapping):
        raise TransactionalRollbackFailure("simulation legacy_blast must be an object")
    return {
        "version": receipt.get("version"),
        "owner_id": receipt.get("owner_id"),
        "expected_head_sha": receipt.get("expected_head_sha"),
        "observed_head_sha": receipt.get("observed_head_sha"),
        "proposed_paths": receipt.get("proposed_paths"),
        "impact_paths": receipt.get("impact_paths"),
        "required_scope": receipt.get("required_scope"),
        "declared_scope": receipt.get("declared_scope"),
        "workflow_impacts": receipt.get("workflow_impacts"),
        "deployment_impacts": receipt.get("deployment_impacts"),
        "frozen_registry_state_hash": receipt.get("frozen_registry_state_hash"),
        "lease_state_hash": receipt.get("lease_state_hash"),
        "legacy_blast_state": legacy.get("state"),
        "legacy_blast_risk": legacy.get("risk"),
        "blockers": receipt.get("blockers"),
        "decision": receipt.get("decision"),
    }


def _validate_simulation_receipt(
    receipt: Mapping[str, Any],
    *,
    owner_id: str,
    baseline_head_sha: str,
    baseline_paths: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise TransactionalRollbackFailure("blast simulation receipt must be an object")
    if receipt.get("version") != REQUIRED_BLAST_SIMULATOR_VERSION:
        raise TransactionalRollbackFailure("blast simulation version mismatch")
    if receipt.get("status") != "GREEN":
        raise TransactionalRollbackFailure("blast simulation must be GREEN")
    if receipt.get("decision") != "SAFE_TO_REQUEST_MUTATION_GATE":
        raise TransactionalRollbackFailure("blast simulation is not safe for mutation gate")
    if receipt.get("step_2a_required") is not True:
        raise TransactionalRollbackFailure("blast simulation must require Step 2A")
    if receipt.get("mutation_authority") is not False:
        raise TransactionalRollbackFailure("blast simulation cannot grant mutation authority")
    if int(receipt.get("blocker_count", -1)) != 0 or receipt.get("blockers") != []:
        raise TransactionalRollbackFailure("blast simulation contains blockers")

    owner = _text(receipt.get("owner_id"), "simulation owner_id")
    if owner != owner_id:
        raise TransactionalRollbackFailure("blast simulation owner mismatch")
    expected = _sha(receipt.get("expected_head_sha"), "simulation expected_head_sha")
    observed = _sha(receipt.get("observed_head_sha"), "simulation observed_head_sha")
    if expected != baseline_head_sha or observed != baseline_head_sha:
        raise TransactionalRollbackFailure("blast simulation is not bound to baseline head")

    proposed = sorted(_path(item) for item in (receipt.get("proposed_paths") or []))
    if proposed != sorted(baseline_paths):
        raise TransactionalRollbackFailure("blast simulation proposed paths mismatch baseline paths")

    digest = str(receipt.get("simulation_receipt_digest") or "").strip().lower()
    if not digest.startswith("sha256:") or not _HASH64.fullmatch(digest[7:]):
        raise TransactionalRollbackFailure("invalid blast simulation receipt digest")
    expected_digest = "sha256:" + _digest(_simulation_core(receipt))
    if digest != expected_digest:
        raise TransactionalRollbackFailure("blast simulation receipt digest mismatch")

    return {
        "version": receipt["version"],
        "owner_id": owner,
        "head_sha": baseline_head_sha,
        "receipt_digest": digest,
        "proposed_paths": proposed,
    }


def _seal(state: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(state))
    out.pop("state_hash", None)
    out["state_hash"] = _digest(out)
    return validate_state(out)


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TransactionalRollbackFailure("transaction state must be an object")
    state = deepcopy(dict(payload))
    if int(state.get("schema_version", 0)) != 1 or state.get("version") != VERSION:
        raise TransactionalRollbackFailure("transaction state version/schema mismatch")
    _text(state.get("transaction_id"), "transaction_id")
    _text(state.get("owner_id"), "owner_id")
    phase = state.get("phase")
    if phase not in _PHASES:
        raise TransactionalRollbackFailure("unknown transaction phase")
    if int(state.get("revision", -1)) < 0:
        raise TransactionalRollbackFailure("transaction revision invalid")

    baseline = state.get("baseline")
    if not isinstance(baseline, Mapping):
        raise TransactionalRollbackFailure("baseline must be an object")
    _sha(baseline.get("head_sha"), "baseline head_sha")
    baseline_paths = _blob_map(
        baseline.get("path_blobs") or {},
        "baseline path_blobs",
        allow_none=True,
    )
    if not baseline_paths:
        raise TransactionalRollbackFailure("baseline path_blobs cannot be empty")
    _blob_map(
        baseline.get("dependency_blobs") or {},
        "baseline dependency_blobs",
        allow_none=False,
    )
    _resource_map(baseline.get("resource_snapshots") or {}, "baseline resource_snapshots")
    _receipt_hash(baseline.get("terminal_receipt_hash"), "baseline terminal_receipt_hash")
    sim_digest = str(baseline.get("simulation_receipt_digest") or "").strip().lower()
    if not sim_digest.startswith("sha256:") or not _HASH64.fullmatch(sim_digest[7:]):
        raise TransactionalRollbackFailure("baseline simulation_receipt_digest invalid")

    mutation = state.get("mutation")
    if not isinstance(mutation, Mapping):
        raise TransactionalRollbackFailure("mutation must be an object")
    mutation_head = str(mutation.get("head_sha") or "").strip().lower()
    if mutation_head:
        _sha(mutation_head, "mutation head_sha")
        mutation_paths = _blob_map(
            mutation.get("path_blobs") or {},
            "mutation path_blobs",
            allow_none=True,
        )
        if set(mutation_paths) != set(baseline_paths):
            raise TransactionalRollbackFailure("mutation path set differs from baseline")
        mutation_resources = _resource_map(
            mutation.get("resource_snapshots") or {},
            "mutation resource_snapshots",
        )
        baseline_resources = _resource_map(
            baseline.get("resource_snapshots") or {},
            "baseline resource_snapshots",
        )
        if set(mutation_resources) != set(baseline_resources):
            raise TransactionalRollbackFailure("mutation resource set differs from baseline")
    elif mutation.get("path_blobs") or mutation.get("resource_snapshots"):
        raise TransactionalRollbackFailure("mutation surfaces require mutation head_sha")

    issued = state.get("issued_actions")
    if not isinstance(issued, Mapping):
        raise TransactionalRollbackFailure("issued_actions must be an object")
    for action, fingerprint in issued.items():
        _text(action, "issued action")
        _receipt_hash(fingerprint, "issued action fingerprint")

    history = state.get("history")
    if not isinstance(history, list):
        raise TransactionalRollbackFailure("history must be a list")

    supplied = str(state.get("state_hash") or "").strip().lower()
    if not _HASH64.fullmatch(supplied):
        raise TransactionalRollbackFailure("state_hash must be sha256")
    unsigned = deepcopy(state)
    unsigned.pop("state_hash", None)
    if supplied != _digest(unsigned):
        raise TransactionalRollbackFailure("transaction state hash mismatch")
    return state


def prepare_transaction(
    *,
    transaction_id: str,
    owner_id: str,
    baseline_head_sha: str,
    baseline_path_blobs: Mapping[str, Any],
    baseline_dependency_blobs: Mapping[str, Any],
    baseline_resource_snapshots: Mapping[str, Any] | None,
    baseline_terminal_receipt: Mapping[str, Any],
    blast_simulation_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if BLAST_SIMULATOR_VERSION != REQUIRED_BLAST_SIMULATOR_VERSION:
        raise TransactionalRollbackFailure("V8 Step-1 simulator version mismatch")
    if TERMINAL_RECEIPT_VERSION != REQUIRED_TERMINAL_RECEIPT_VERSION:
        raise TransactionalRollbackFailure("terminal proof receipt version mismatch")

    txid = _text(transaction_id, "transaction_id")
    owner = _text(owner_id, "owner_id")
    baseline_head = _sha(baseline_head_sha, "baseline_head_sha")
    paths = _blob_map(
        baseline_path_blobs,
        "baseline_path_blobs",
        allow_none=True,
    )
    if not paths:
        raise TransactionalRollbackFailure("baseline_path_blobs cannot be empty")
    dependencies = _blob_map(
        baseline_dependency_blobs,
        "baseline_dependency_blobs",
        allow_none=False,
    )
    resources = _resource_map(
        baseline_resource_snapshots,
        "baseline_resource_snapshots",
    )

    proof = validate_receipt(baseline_terminal_receipt)
    if proof["head_sha"] != baseline_head:
        raise TransactionalRollbackFailure("baseline terminal proof is bound to wrong head")

    simulation = _validate_simulation_receipt(
        blast_simulation_receipt,
        owner_id=owner,
        baseline_head_sha=baseline_head,
        baseline_paths=list(paths),
    )

    state = {
        "schema_version": 1,
        "version": VERSION,
        "transaction_id": txid,
        "owner_id": owner,
        "phase": "PREPARED",
        "revision": 0,
        "baseline": {
            "head_sha": baseline_head,
            "path_blobs": paths,
            "dependency_blobs": dependencies,
            "resource_snapshots": resources,
            "terminal_receipt_hash": proof["receipt_hash"],
            "simulation_receipt_digest": simulation["receipt_digest"],
        },
        "mutation": {
            "head_sha": "",
            "path_blobs": {},
            "resource_snapshots": {},
        },
        "failure": None,
        "restoration": None,
        "issued_actions": {},
        "history": [
            {
                "revision": 0,
                "phase": "PREPARED",
                "reason": "LAST_GREEN_BASELINE_SEALED",
            }
        ],
    }
    return _seal(state)


def record_mutation_applied(
    payload: Mapping[str, Any],
    *,
    mutation_head_sha: str,
    mutation_path_blobs: Mapping[str, Any],
    mutation_resource_snapshots: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state = validate_state(payload)
    if state["phase"] != "PREPARED":
        raise TransactionalRollbackFailure("mutation may only be recorded from PREPARED")

    head = _sha(mutation_head_sha, "mutation_head_sha")
    paths = _blob_map(
        mutation_path_blobs,
        "mutation_path_blobs",
        allow_none=True,
    )
    baseline_paths = state["baseline"]["path_blobs"]
    if set(paths) != set(baseline_paths):
        raise TransactionalRollbackFailure("mutation path set must exactly match baseline")

    resources = _resource_map(
        mutation_resource_snapshots,
        "mutation_resource_snapshots",
    )
    baseline_resources = state["baseline"]["resource_snapshots"]
    if set(resources) != set(baseline_resources):
        raise TransactionalRollbackFailure("mutation resource set must exactly match baseline")

    changed = any(paths[path] != baseline_paths[path] for path in paths) or any(
        resources[name] != baseline_resources[name] for name in resources
    )
    if not changed:
        raise TransactionalRollbackFailure("recorded mutation changed no owned surface")

    updated = deepcopy(state)
    updated["revision"] += 1
    updated["phase"] = "MUTATION_APPLIED"
    updated["mutation"] = {
        "head_sha": head,
        "path_blobs": paths,
        "resource_snapshots": resources,
    }
    updated["history"].append(
        {
            "revision": updated["revision"],
            "phase": "MUTATION_APPLIED",
            "reason": "MUTATION_SURFACES_RECORDED",
        }
    )
    return _seal(updated)


def _block(
    state: Mapping[str, Any],
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
    next_legal_action: str = "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE",
) -> dict[str, Any]:
    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["phase"] = "BLOCKED"
    updated["failure"] = {
        "code": code,
        "details_digest": _digest(details or {}),
        "next_legal_action": next_legal_action,
    }
    updated["history"].append(
        {
            "revision": updated["revision"],
            "phase": "BLOCKED",
            "reason": code,
        }
    )
    return _seal(updated)


def _transition(
    state: Mapping[str, Any],
    *,
    phase: str,
    reason: str,
) -> dict[str, Any]:
    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["phase"] = phase
    updated["history"].append(
        {
            "revision": updated["revision"],
            "phase": phase,
            "reason": reason,
        }
    )
    return _seal(updated)


def _surface_snapshot(
    raw: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise TransactionalRollbackFailure("current_surface must be an object")
    return {
        "head_sha": _sha(raw.get("head_sha"), "current_surface head_sha"),
        "path_blobs": _blob_map(
            raw.get("path_blobs") or {},
            "current_surface path_blobs",
            allow_none=True,
        ),
        "dependency_blobs": _blob_map(
            raw.get("dependency_blobs") or {},
            "current_surface dependency_blobs",
            allow_none=False,
        ),
        "resource_snapshots": _resource_map(
            raw.get("resource_snapshots") or {},
            "current_surface resource_snapshots",
        ),
    }


def _rollback_conflicts(
    state: Mapping[str, Any],
    current_surface: Mapping[str, Any],
) -> list[dict[str, Any]]:
    current = _surface_snapshot(current_surface, state)
    mutation_paths = state["mutation"]["path_blobs"]
    baseline_dependencies = state["baseline"]["dependency_blobs"]
    mutation_resources = state["mutation"]["resource_snapshots"]

    conflicts: list[dict[str, Any]] = []
    if set(current["path_blobs"]) != set(mutation_paths):
        conflicts.append({"code": "CURRENT_PATH_SET_DRIFT"})
    else:
        changed = sorted(
            path
            for path in mutation_paths
            if current["path_blobs"][path] != mutation_paths[path]
        )
        if changed:
            conflicts.append(
                {
                    "code": "POST_MUTATION_PATH_OWNERSHIP_DRIFT",
                    "paths": changed,
                }
            )

    if current["dependency_blobs"] != baseline_dependencies:
        drift = sorted(
            set(current["dependency_blobs"]) | set(baseline_dependencies)
        )
        conflicts.append(
            {
                "code": "DEPENDENCY_DRIFT_SINCE_BASELINE",
                "paths": drift,
            }
        )

    if current["resource_snapshots"] != mutation_resources:
        drift = sorted(
            set(current["resource_snapshots"]) | set(mutation_resources)
        )
        conflicts.append(
            {
                "code": "POST_MUTATION_RESOURCE_OWNERSHIP_DRIFT",
                "resources": drift,
            }
        )
    return conflicts


def _issue_restore(
    state: Mapping[str, Any],
    current_surface: Mapping[str, Any],
) -> dict[str, Any]:
    fingerprint = _digest(
        {
            "transaction_id": state["transaction_id"],
            "failure": state["failure"],
            "current_surface": current_surface,
            "baseline": state["baseline"],
            "mutation": state["mutation"],
        }
    )

    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["phase"] = "RESTORE_ISSUED"
    updated["issued_actions"]["RESTORE_BASELINE_MANIFEST"] = fingerprint
    updated["history"].append(
        {
            "revision": updated["revision"],
            "phase": "RESTORE_ISSUED",
            "reason": "PATH_SCOPED_ROLLBACK_ISSUED",
        }
    )
    updated = _seal(updated)

    return {
        "result": {
            "decision": "ROLLBACK_ACTION_ISSUED",
            "action": "RESTORE_BASELINE_MANIFEST",
            "phase": "RESTORE_ISSUED",
            "action_fingerprint": fingerprint,
            "expected_current_head_sha": current_surface["head_sha"],
            "restore_manifest": {
                "path_blobs": state["baseline"]["path_blobs"],
                "resource_snapshots": state["baseline"]["resource_snapshots"],
            },
            "expected_current_path_blobs": state["mutation"]["path_blobs"],
            "expected_current_resource_snapshots": state["mutation"]["resource_snapshots"],
            "baseline_provenance_head_sha": state["baseline"]["head_sha"],
            "whole_repo_ref_reset_allowed": False,
            "step_2a_required": True,
            "mutation_authority": False,
            "polling_required": False,
        },
        "state": updated,
    }


def _issue_recertification(
    state: Mapping[str, Any],
    restored_head_sha: str,
) -> dict[str, Any]:
    fingerprint = _digest(
        {
            "transaction_id": state["transaction_id"],
            "restored_head_sha": restored_head_sha,
            "restoration": state["restoration"],
        }
    )
    updated = deepcopy(dict(state))
    updated["revision"] += 1
    updated["phase"] = "RECERTIFY"
    updated["issued_actions"]["RUN_ROLLBACK_RECERTIFICATION"] = fingerprint
    updated["history"].append(
        {
            "revision": updated["revision"],
            "phase": "RECERTIFY",
            "reason": "ROLLBACK_SURFACES_RESTORED",
        }
    )
    updated = _seal(updated)
    return {
        "result": {
            "decision": "ROLLBACK_RECERTIFICATION_ISSUED",
            "action": "RUN_ROLLBACK_RECERTIFICATION",
            "phase": "RECERTIFY",
            "head_sha": restored_head_sha,
            "action_fingerprint": fingerprint,
            "step_2a_required": True,
            "mutation_authority": False,
            "polling_required": False,
        },
        "state": updated,
    }


def advance(
    payload: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = validate_state(payload)
    evidence = dict(evidence or {})

    phase = state["phase"]

    if phase == "CLOSED_SUCCESS":
        return {
            "result": {
                "decision": "TRANSACTION_COMMITTED_SUCCESS",
                "complete": True,
                "rollback_allowed": False,
                "next_legal_action": "NONE",
                "mutation_authority": False,
            },
            "state": state,
        }

    if phase == "CLOSED_ROLLED_BACK":
        return {
            "result": {
                "decision": "TRANSACTION_ROLLBACK_CERTIFIED",
                "complete": True,
                "rollback_allowed": False,
                "next_legal_action": "NONE",
                "mutation_authority": False,
            },
            "state": state,
        }

    if phase == "BLOCKED":
        return {
            "result": {
                "decision": "TRANSACTION_BLOCKED",
                "complete": False,
                "blocker": state["failure"],
                "next_legal_action": state["failure"]["next_legal_action"],
                "mutation_authority": False,
            },
            "state": state,
        }

    if phase == "PREPARED":
        return {
            "result": {
                "decision": "BASELINE_SEALED_READY_FOR_STEP2A_MUTATION",
                "phase": phase,
                "next_legal_action": "REQUEST_STEP_2A_MUTATION_GATE",
                "rollback_allowed": False,
                "mutation_authority": False,
            },
            "state": state,
        }

    if phase == "MUTATION_APPLIED":
        outcome = evidence.get("outcome")
        if outcome is None:
            return {
                "result": {
                    "decision": "WAIT_FOR_MUTATION_OUTCOME_EVENT",
                    "phase": phase,
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }
        if not isinstance(outcome, Mapping):
            raise TransactionalRollbackFailure("outcome evidence must be an object")
        terminal = outcome.get("terminal")
        if terminal is not True:
            return {
                "result": {
                    "decision": "WAIT_FOR_TERMINAL_MUTATION_OUTCOME",
                    "phase": phase,
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }
        txid = _text(outcome.get("transaction_id"), "outcome transaction_id")
        if txid != state["transaction_id"]:
            blocked = _block(
                state,
                code="OUTCOME_TRANSACTION_ID_MISMATCH",
                details=outcome,
            )
            return advance(blocked, evidence)
        head = _sha(outcome.get("head_sha"), "outcome head_sha")
        if head != state["mutation"]["head_sha"]:
            blocked = _block(
                state,
                code="OUTCOME_HEAD_MISMATCH",
                details=outcome,
            )
            return advance(blocked, evidence)
        status = _text(outcome.get("status"), "outcome status").upper()
        if status == "SUCCESS":
            closed = _transition(
                state,
                phase="CLOSED_SUCCESS",
                reason="MUTATION_TERMINAL_SUCCESS",
            )
            return advance(closed, evidence)
        if status != "FAILURE":
            raise TransactionalRollbackFailure("terminal outcome status must be SUCCESS or FAILURE")

        updated = deepcopy(state)
        updated["revision"] += 1
        updated["phase"] = "FAILURE_CONFIRMED"
        updated["failure"] = {
            "code": "TERMINAL_MUTATION_FAILURE",
            "failure_class": _text(
                outcome.get("failure_class"),
                "outcome failure_class",
            ),
            "failure_digest": _digest(outcome),
            "head_sha": head,
            "next_legal_action": "VERIFY_ROLLBACK_OWNERSHIP",
        }
        updated["history"].append(
            {
                "revision": updated["revision"],
                "phase": "FAILURE_CONFIRMED",
                "reason": "TERMINAL_MUTATION_FAILURE",
            }
        )
        state = _seal(updated)
        phase = "FAILURE_CONFIRMED"

    if phase == "FAILURE_CONFIRMED":
        current_raw = evidence.get("current_surface")
        if current_raw is None:
            return {
                "result": {
                    "decision": "REQUIRE_CURRENT_ROLLBACK_SURFACE_SNAPSHOT",
                    "phase": phase,
                    "next_legal_action": "CAPTURE_CURRENT_ROLLBACK_SURFACES",
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }
        current = _surface_snapshot(current_raw, state)
        conflicts = _rollback_conflicts(state, current)
        if conflicts:
            blocked = _block(
                state,
                code="ROLLBACK_OWNERSHIP_OR_DEPENDENCY_DRIFT",
                details={"conflicts": conflicts, "current_surface": current},
                next_legal_action="RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE",
            )
            result = advance(blocked, evidence)
            result["result"]["rollback_conflicts"] = conflicts
            return result
        return _issue_restore(state, current)

    if phase == "RESTORE_ISSUED":
        restoration = evidence.get("restoration")
        if restoration is None:
            return {
                "result": {
                    "decision": "WAIT_FOR_RESTORATION_EVENT",
                    "phase": phase,
                    "duplicate_restore_suppressed": True,
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }
        if not isinstance(restoration, Mapping):
            raise TransactionalRollbackFailure("restoration evidence must be an object")
        if str(restoration.get("status") or "").upper() != "RESTORED":
            blocked = _block(
                state,
                code="RESTORATION_TERMINAL_FAILURE",
                details=restoration,
            )
            return advance(blocked, evidence)

        restored_head = _sha(restoration.get("restored_head_sha"), "restored_head_sha")
        restored_paths = _blob_map(
            restoration.get("path_blobs") or {},
            "restoration path_blobs",
            allow_none=True,
        )
        restored_resources = _resource_map(
            restoration.get("resource_snapshots") or {},
            "restoration resource_snapshots",
        )
        if restored_paths != state["baseline"]["path_blobs"]:
            blocked = _block(
                state,
                code="RESTORATION_PATH_IDENTITY_MISMATCH",
                details=restoration,
            )
            return advance(blocked, evidence)
        if restored_resources != state["baseline"]["resource_snapshots"]:
            blocked = _block(
                state,
                code="RESTORATION_RESOURCE_IDENTITY_MISMATCH",
                details=restoration,
            )
            return advance(blocked, evidence)

        updated = deepcopy(state)
        updated["restoration"] = {
            "restored_head_sha": restored_head,
            "path_blobs": restored_paths,
            "resource_snapshots": restored_resources,
            "restoration_receipt_digest": _digest(restoration),
        }
        updated = _seal(updated)
        return _issue_recertification(updated, restored_head)

    if phase == "RECERTIFY":
        failure = evidence.get("recertification_failure")
        if failure is not None:
            if not isinstance(failure, Mapping) or failure.get("terminal") is not True:
                raise TransactionalRollbackFailure("recertification failure must be terminal evidence")
            blocked = _block(
                state,
                code="ROLLBACK_RECERTIFICATION_FAILED",
                details=failure,
            )
            return advance(blocked, evidence)

        receipt = evidence.get("recertification_receipt")
        if receipt is None:
            return {
                "result": {
                    "decision": "WAIT_FOR_ROLLBACK_RECERTIFICATION_EVENT",
                    "phase": phase,
                    "duplicate_recertification_suppressed": True,
                    "polling_required": False,
                    "mutation_authority": False,
                },
                "state": state,
            }
        proof = validate_receipt(receipt)
        restored_head = state["restoration"]["restored_head_sha"]
        if proof["head_sha"] != restored_head:
            blocked = _block(
                state,
                code="ROLLBACK_RECERTIFICATION_HEAD_MISMATCH",
                details=receipt,
            )
            return advance(blocked, evidence)
        closed = _transition(
            state,
            phase="CLOSED_ROLLED_BACK",
            reason="ROLLBACK_RECERTIFIED_GREEN",
        )
        return advance(closed, evidence)

    raise TransactionalRollbackFailure("unreachable transaction phase")


def _test_simulation(
    *,
    owner_id: str,
    head_sha: str,
    paths: Sequence[str],
) -> dict[str, Any]:
    receipt = {
        "version": REQUIRED_BLAST_SIMULATOR_VERSION,
        "status": "GREEN",
        "decision": "SAFE_TO_REQUEST_MUTATION_GATE",
        "owner_id": owner_id,
        "expected_head_sha": head_sha,
        "observed_head_sha": head_sha,
        "proposed_paths": sorted(paths),
        "impact_paths": sorted(paths),
        "required_scope": {
            "write_paths": sorted(paths),
            "dependency_tokens": [],
            "shared_resources": [],
            "resource_identity": {"main:base": head_sha},
            "exclusive": False,
        },
        "declared_scope": {
            "write_paths": sorted(paths),
            "dependency_tokens": [],
            "shared_resources": [],
            "resource_identity": {"main:base": head_sha},
            "exclusive": False,
        },
        "workflow_impacts": [],
        "deployment_impacts": [],
        "frozen_registry_state_hash": "1" * 64,
        "lease_state_hash": "2" * 64,
        "legacy_blast": {
            "version": "MONSTER_PROJECT_BLAST_RADIUS_MAP_V1",
            "state": "ALLOW_EDIT",
            "risk": "LOW",
            "blast_radius": 0,
            "impacted_entrypoints": [],
            "protected_reach": [],
        },
        "blockers": [],
        "blocker_count": 0,
        "step_2a_required": True,
        "mutation_authority": False,
    }
    receipt["simulation_receipt_digest"] = "sha256:" + _digest(_simulation_core(receipt))
    return receipt


def contract_self_test() -> dict[str, Any]:
    from devsystem.terminal_proof_receipt_v1 import build_receipt

    baseline = "a" * 40
    mutation = "b" * 40
    restored = "c" * 40
    path = "app.py"
    owner = "chat:monster"
    baseline_blob = "1" * 40
    mutation_blob = "2" * 40
    dep_blob = "3" * 40

    proof = build_receipt(
        repository="owner/repo",
        checkpoint_id="BASELINE",
        head_sha=baseline,
        authoritative_run=1,
        authoritative_workflow="proof",
        test_count=10,
        required_lanes={"focused": "success"},
        scope_diff=[path],
        freeze_tokens=["GREEN"],
    )
    sim = _test_simulation(owner_id=owner, head_sha=baseline, paths=[path])
    tx = prepare_transaction(
        transaction_id="TX-1",
        owner_id=owner,
        baseline_head_sha=baseline,
        baseline_path_blobs={path: baseline_blob},
        baseline_dependency_blobs={"dep.py": dep_blob},
        baseline_resource_snapshots={"deploy:app": "release-a"},
        baseline_terminal_receipt=proof,
        blast_simulation_receipt=sim,
    )
    ready = advance(tx)
    applied = record_mutation_applied(
        tx,
        mutation_head_sha=mutation,
        mutation_path_blobs={path: mutation_blob},
        mutation_resource_snapshots={"deploy:app": "release-b"},
    )
    failure = {
        "outcome": {
            "terminal": True,
            "status": "FAILURE",
            "transaction_id": "TX-1",
            "head_sha": mutation,
            "failure_class": "PRODUCT_RUNTIME",
        },
        "current_surface": {
            "head_sha": "d" * 40,
            "path_blobs": {path: mutation_blob},
            "dependency_blobs": {"dep.py": dep_blob},
            "resource_snapshots": {"deploy:app": "release-b"},
        },
    }
    restore = advance(applied, failure)
    wait = advance(restore["state"], {})
    restored_state = advance(
        restore["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": restored,
                "path_blobs": {path: baseline_blob},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    recert = build_receipt(
        repository="owner/repo",
        checkpoint_id="ROLLBACK",
        head_sha=restored,
        authoritative_run=2,
        authoritative_workflow="proof",
        test_count=10,
        required_lanes={"focused": "success"},
        scope_diff=[path],
        freeze_tokens=["GREEN"],
    )
    closed = advance(
        restored_state["state"],
        {"recertification_receipt": recert},
    )

    drift = advance(
        applied,
        {
            **failure,
            "current_surface": {
                **failure["current_surface"],
                "path_blobs": {path: "9" * 40},
            },
        },
    )

    success = advance(
        applied,
        {
            "outcome": {
                "terminal": True,
                "status": "SUCCESS",
                "transaction_id": "TX-1",
                "head_sha": mutation,
            }
        },
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "step1_simulator_version_bound": (
            BLAST_SIMULATOR_VERSION == REQUIRED_BLAST_SIMULATOR_VERSION
        ),
        "terminal_receipt_version_bound": (
            TERMINAL_RECEIPT_VERSION == REQUIRED_TERMINAL_RECEIPT_VERSION
        ),
        "baseline_sealed_before_mutation": (
            ready["result"]["decision"]
            == "BASELINE_SEALED_READY_FOR_STEP2A_MUTATION"
        ),
        "unrelated_newer_head_can_rollback_owned_paths": (
            restore["result"]["decision"] == "ROLLBACK_ACTION_ISSUED"
            and restore["result"]["expected_current_head_sha"] == "d" * 40
        ),
        "whole_repo_reset_forbidden": (
            restore["result"]["whole_repo_ref_reset_allowed"] is False
        ),
        "duplicate_restore_suppressed": (
            wait["result"]["decision"] == "WAIT_FOR_RESTORATION_EVENT"
            and wait["result"]["duplicate_restore_suppressed"] is True
        ),
        "restoration_requires_recertification": (
            restored_state["result"]["action"] == "RUN_ROLLBACK_RECERTIFICATION"
        ),
        "rollback_closes_only_after_green_recertification": (
            closed["result"]["decision"] == "TRANSACTION_ROLLBACK_CERTIFIED"
        ),
        "newer_writer_on_owned_path_blocks_rollback": (
            drift["result"]["decision"] == "TRANSACTION_BLOCKED"
            and drift["result"]["rollback_conflicts"][0]["code"]
            == "POST_MUTATION_PATH_OWNERSHIP_DRIFT"
        ),
        "successful_transaction_forbids_rollback": (
            success["result"]["decision"] == "TRANSACTION_COMMITTED_SUCCESS"
            and success["result"]["rollback_allowed"] is False
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "step1_simulator_version_bound",
        "terminal_receipt_version_bound",
        "baseline_sealed_before_mutation",
        "unrelated_newer_head_can_rollback_owned_paths",
        "whole_repo_reset_forbidden",
        "duplicate_restore_suppressed",
        "restoration_requires_recertification",
        "rollback_closes_only_after_green_recertification",
        "newer_writer_on_owned_path_blocks_rollback",
        "successful_transaction_forbids_rollback",
    ]
    if not all(result[name] is True for name in required):
        raise TransactionalRollbackFailure("transactional rollback self-test failed")
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise TransactionalRollbackFailure("read-only controller invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V8_STEP2_TRANSACTIONAL_ROLLBACK_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TransactionalRollbackFailure as exc:
        print("MONSTER_V8_STEP2_TRANSACTIONAL_ROLLBACK_BLOCKED: " + str(exc))
        raise SystemExit(1)
