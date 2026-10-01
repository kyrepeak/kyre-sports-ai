"""MONSTER V5 Step 5 — Zero-Context Resume Packet V1.

A fresh chat/worker can read one repository-backed packet and immediately know:
- the mission and exact MONSTER program/step;
- what is completed, frozen, and remaining;
- the exact main/head snapshot;
- the authoritative async run and its state;
- the last completed action;
- the only legal next action;
- the frozen-registry identity and complete checkpoint set;
- detached continuation, event-resume, and heartbeat/dead-man identities;
- proof/terminal-receipt identity;
- the immutable rule that this packet is context, never mutation authority.

Mutation still requires MONSTER Step 2A plus a valid V5 scope-aware lease.
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

VERSION = "MONSTER_V5_ZERO_CONTEXT_RESUME_PACKET_V1"
PACKET_REF = "refs/heads/monster-zero-context-resume"
PACKET_PATH = "devsystem/zero_context_resume_packet_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{1,255}$")
_STEP_STATES = {"ACTIVE", "WAITING_ON_ASYNC", "BLOCKED", "READY", "FROZEN", "COMPLETE"}
_RUN_STATES = {"NONE", "QUEUED", "PENDING", "WAITING", "IN_PROGRESS", "RUNNING", "SUCCESS", "FAILURE", "CANCELLED", "SKIPPED", "COMPLETED", "ABSENT"}
_LIVE_RUN_STATES = {"QUEUED", "PENDING", "WAITING", "IN_PROGRESS", "RUNNING"}
_FAILURE_RUN_STATES = {"FAILURE", "CANCELLED"}


class ZeroContextResumeFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _required(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ZeroContextResumeFailure(f"{field} is required")
    return text


def _identity(value: Any, field: str) -> str:
    text = _required(value, field)
    if not _ID_RE.fullmatch(text):
        raise ZeroContextResumeFailure(f"{field} has invalid characters")
    return text


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise ZeroContextResumeFailure(f"{field} must be a full 40-character SHA")
    return text


def _hash64(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HASH64.fullmatch(text):
        raise ZeroContextResumeFailure(f"{field} must be a 64-character sha256")
    return text


def _positive(value: Any, field: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ZeroContextResumeFailure(f"{field} must be positive") from exc
    if number <= 0:
        raise ZeroContextResumeFailure(f"{field} must be positive")
    return number


def _nonnegative(value: Any, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ZeroContextResumeFailure(f"{field} must be non-negative") from exc
    if number < 0:
        raise ZeroContextResumeFailure(f"{field} must be non-negative")
    return number


def _normalize_steps(values: Sequence[Any], field: str, total_steps: int) -> list[int]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ZeroContextResumeFailure(f"{field} must be a sequence")
    out = sorted({int(value) for value in values})
    if any(value <= 0 or value > total_steps for value in out):
        raise ZeroContextResumeFailure(f"{field} contains an invalid step")
    return out


def _normalize_checkpoints(values: Sequence[Any]) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ZeroContextResumeFailure("frozen_checkpoints must be a sequence")
    out = sorted({_identity(value, "frozen checkpoint") for value in values})
    if not out:
        raise ZeroContextResumeFailure("frozen_checkpoints cannot be empty")
    return out


def _packet_body(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = deepcopy(dict(payload))
    body.pop("packet_hash", None)
    return body


def _normalize_registry(raw: Mapping[str, Any], frozen_checkpoints: Sequence[str]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ZeroContextResumeFailure("frozen_registry must be an object")
    checkpoint_count = _positive(raw.get("checkpoint_count"), "frozen_registry.checkpoint_count")
    active_thaws = _nonnegative(raw.get("active_thaws"), "frozen_registry.active_thaws")
    if checkpoint_count != len(frozen_checkpoints):
        raise ZeroContextResumeFailure("frozen registry checkpoint count mismatch")
    return {
        "revision": _positive(raw.get("revision"), "frozen_registry.revision"),
        "state_hash": _hash64(raw.get("state_hash"), "frozen_registry.state_hash"),
        "checkpoint_count": checkpoint_count,
        "active_thaws": active_thaws,
    }


def _normalize_scope_lease(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ZeroContextResumeFailure("scope_lease must be an object")
    holder_count = _nonnegative(raw.get("holder_count"), "scope_lease.holder_count")
    owner = str(raw.get("current_owner_id") or "").strip() or None
    lease_id = str(raw.get("current_lease_id") or "").strip() or None
    if (owner is None) != (lease_id is None):
        raise ZeroContextResumeFailure("scope current owner/lease must both be present or absent")
    if owner is not None:
        _identity(owner, "scope_lease.current_owner_id")
        _identity(lease_id, "scope_lease.current_lease_id")
    return {
        "revision": _positive(raw.get("revision"), "scope_lease.revision"),
        "generation": _nonnegative(raw.get("generation"), "scope_lease.generation"),
        "state_hash": _hash64(raw.get("state_hash"), "scope_lease.state_hash"),
        "holder_count": holder_count,
        "current_owner_id": owner,
        "current_lease_id": lease_id,
    }


def _normalize_layer(raw: Mapping[str, Any], field: str, *, count_fields: Sequence[str]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ZeroContextResumeFailure(f"{field} must be an object")
    result: dict[str, Any] = {
        "version": _required(raw.get("version"), f"{field}.version"),
        "revision": _nonnegative(raw.get("revision"), f"{field}.revision"),
        "generation": _nonnegative(raw.get("generation"), f"{field}.generation"),
        "state_hash": _hash64(raw.get("state_hash"), f"{field}.state_hash"),
    }
    for key in count_fields:
        result[key] = _nonnegative(raw.get(key), f"{field}.{key}")
    return result


def _normalize_proof(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ZeroContextResumeFailure("proof must be an object")
    receipt = str(raw.get("terminal_receipt_digest") or "").strip().lower()
    if not receipt.startswith("sha256:") or not _HASH64.fullmatch(receipt[7:]):
        raise ZeroContextResumeFailure("proof.terminal_receipt_digest must be sha256:<64hex>")
    return {
        "proof_run_id": _positive(raw.get("proof_run_id"), "proof.proof_run_id"),
        "terminal_receipt_digest": receipt,
    }


def build_packet(
    *,
    repository: str,
    generation: int,
    program_id: str,
    program_title: str,
    mission: str,
    current_step: int,
    total_steps: int,
    step_title: str,
    step_status: str,
    active_checkpoint: str,
    completed_steps: Sequence[int],
    frozen_steps: Sequence[int],
    remaining_steps: Sequence[int],
    main_sha: str,
    head_sha: str,
    branch: str,
    pr_number: int | None,
    authoritative_run_id: int | None,
    authoritative_run_state: str,
    last_completed_action: str,
    only_next_legal_action: str,
    blocker: str | None,
    frozen_registry: Mapping[str, Any],
    frozen_checkpoints: Sequence[str],
    scope_lease: Mapping[str, Any],
    detached_continuation: Mapping[str, Any],
    event_driven_resume: Mapping[str, Any],
    execution_heartbeat_deadman: Mapping[str, Any],
    proof: Mapping[str, Any],
    previous_packet_hash: str | None = None,
) -> dict[str, Any]:
    repo = str(repository or "").strip().lower()
    if "/" not in repo:
        raise ZeroContextResumeFailure("repository must be owner/name")
    gen = _positive(generation, "generation")
    current = _positive(current_step, "current_step")
    total = _positive(total_steps, "total_steps")
    if current is None or total is None or current > total:
        raise ZeroContextResumeFailure("current_step must be inside total_steps")

    status = str(step_status or "").strip().upper()
    if status not in _STEP_STATES:
        raise ZeroContextResumeFailure("step_status is invalid")
    run_state = str(authoritative_run_state or "").strip().upper()
    if run_state not in _RUN_STATES:
        raise ZeroContextResumeFailure("authoritative_run_state is invalid")

    run_id = _positive(authoritative_run_id, "authoritative_run_id", allow_none=True)
    if run_state not in {"NONE", "ABSENT"} and run_id is None:
        raise ZeroContextResumeFailure("authoritative run state requires run id")
    if run_state in {"NONE", "ABSENT"} and run_id is not None:
        raise ZeroContextResumeFailure("NONE/ABSENT run state cannot carry run id")

    next_action = _required(only_next_legal_action, "only_next_legal_action")
    if run_state in _LIVE_RUN_STATES and next_action != "WAIT_FOR_AUTHORITATIVE_RUN_TERMINAL_EVENT":
        raise ZeroContextResumeFailure("live authoritative run must force WAIT_FOR_AUTHORITATIVE_RUN_TERMINAL_EVENT")
    if run_state in _FAILURE_RUN_STATES and not next_action.startswith("CLASSIFY_"):
        raise ZeroContextResumeFailure("failed/cancelled authoritative run must force CLASSIFY_* next action")

    clean_blocker = str(blocker or "").strip() or None
    if status == "BLOCKED" and clean_blocker is None:
        raise ZeroContextResumeFailure("BLOCKED packet requires blocker")
    if status != "BLOCKED" and clean_blocker is not None:
        raise ZeroContextResumeFailure("non-BLOCKED packet cannot carry blocker")

    completed = _normalize_steps(completed_steps, "completed_steps", total)
    frozen = _normalize_steps(frozen_steps, "frozen_steps", total)
    remaining = _normalize_steps(remaining_steps, "remaining_steps", total)
    all_steps = set(range(1, total + 1))
    if set(completed) | set(remaining) != all_steps or set(completed) & set(remaining):
        raise ZeroContextResumeFailure("completed/remaining steps must partition the program")
    if not set(frozen).issubset(set(completed)):
        raise ZeroContextResumeFailure("frozen steps must be completed")
    if status in {"FROZEN", "COMPLETE"} and current not in frozen:
        raise ZeroContextResumeFailure("FROZEN/COMPLETE current step must be frozen")

    checkpoints = _normalize_checkpoints(frozen_checkpoints)
    prior = None if previous_packet_hash is None else _hash64(previous_packet_hash, "previous_packet_hash")
    packet = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "packet_ref": PACKET_REF,
        "packet_path": PACKET_PATH,
        "generation": gen,
        "previous_packet_hash": prior,
        "program": {
            "id": _identity(program_id, "program_id"),
            "title": _required(program_title, "program_title"),
            "mission": _required(mission, "mission"),
            "current_step": current,
            "total_steps": total,
            "step_title": _required(step_title, "step_title"),
            "step_status": status,
            "active_checkpoint": _identity(active_checkpoint, "active_checkpoint"),
            "completed_steps": completed,
            "frozen_steps": frozen,
            "remaining_steps": remaining,
        },
        "repository_state": {
            "main_sha": _sha(main_sha, "main_sha"),
            "head_sha": _sha(head_sha, "head_sha"),
            "branch": _required(branch, "branch"),
            "pr_number": _positive(pr_number, "pr_number", allow_none=True),
        },
        "authoritative_async": {
            "run_id": run_id,
            "state": run_state,
        },
        "execution": {
            "last_completed_action": _required(last_completed_action, "last_completed_action"),
            "only_next_legal_action": next_action,
            "blocker": clean_blocker,
        },
        "frozen_registry": _normalize_registry(frozen_registry, checkpoints),
        "frozen_checkpoints": checkpoints,
        "scope_lease": _normalize_scope_lease(scope_lease),
        "continuation_layers": {
            "detached_continuation": _normalize_layer(
                detached_continuation,
                "detached_continuation",
                count_fields=("workstream_count",),
            ),
            "event_driven_resume": _normalize_layer(
                event_driven_resume,
                "event_driven_resume",
                count_fields=("active_watch_count", "ready_count"),
            ),
            "execution_heartbeat_deadman": _normalize_layer(
                execution_heartbeat_deadman,
                "execution_heartbeat_deadman",
                count_fields=("worker_count", "recovery_receipt_count", "consumed_recovery_receipt_count"),
            ),
        },
        "proof": _normalize_proof(proof),
        "protections": {
            "step_2a_required": True,
            "scope_lease_required_for_mutation": True,
            "frozen_registry_required": True,
            "packet_does_not_authorize_mutation": True,
            "duplicate_async_run_forbidden": True,
            "blind_poll_loop_forbidden": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    packet["packet_hash"] = _hash(packet)
    return validate_packet(packet)


def validate_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ZeroContextResumeFailure("zero-context packet must be an object")
    packet = deepcopy(dict(payload))
    if int(packet.get("schema_version", 0)) != 1 or packet.get("version") != VERSION:
        raise ZeroContextResumeFailure("zero-context packet version/schema mismatch")
    if packet.get("packet_ref") != PACKET_REF or packet.get("packet_path") != PACKET_PATH:
        raise ZeroContextResumeFailure("zero-context persistence identity mismatch")
    if "/" not in str(packet.get("repository") or ""):
        raise ZeroContextResumeFailure("repository invalid")
    _positive(packet.get("generation"), "generation")
    previous = packet.get("previous_packet_hash")
    if previous is not None:
        _hash64(previous, "previous_packet_hash")

    program = packet.get("program")
    repo_state = packet.get("repository_state")
    async_state = packet.get("authoritative_async")
    execution = packet.get("execution")
    layers = packet.get("continuation_layers")
    if not all(isinstance(value, Mapping) for value in (program, repo_state, async_state, execution, layers)):
        raise ZeroContextResumeFailure("zero-context packet sub-objects malformed")

    current = _positive(program.get("current_step"), "program.current_step")
    total = _positive(program.get("total_steps"), "program.total_steps")
    if current is None or total is None or current > total:
        raise ZeroContextResumeFailure("program step accounting invalid")
    _identity(program.get("id"), "program.id")
    _required(program.get("title"), "program.title")
    _required(program.get("mission"), "program.mission")
    _required(program.get("step_title"), "program.step_title")
    _identity(program.get("active_checkpoint"), "program.active_checkpoint")
    status = str(program.get("step_status") or "").upper()
    if status not in _STEP_STATES:
        raise ZeroContextResumeFailure("program.step_status invalid")

    completed = _normalize_steps(program.get("completed_steps") or [], "program.completed_steps", total)
    frozen = _normalize_steps(program.get("frozen_steps") or [], "program.frozen_steps", total)
    remaining = _normalize_steps(program.get("remaining_steps") or [], "program.remaining_steps", total)
    if set(completed) | set(remaining) != set(range(1, total + 1)) or set(completed) & set(remaining):
        raise ZeroContextResumeFailure("program completed/remaining partition invalid")
    if not set(frozen).issubset(set(completed)):
        raise ZeroContextResumeFailure("program frozen steps invalid")
    if status in {"FROZEN", "COMPLETE"} and current not in frozen:
        raise ZeroContextResumeFailure("frozen/complete current step not frozen")

    _sha(repo_state.get("main_sha"), "repository_state.main_sha")
    _sha(repo_state.get("head_sha"), "repository_state.head_sha")
    _required(repo_state.get("branch"), "repository_state.branch")
    _positive(repo_state.get("pr_number"), "repository_state.pr_number", allow_none=True)

    run_state = str(async_state.get("state") or "").upper()
    if run_state not in _RUN_STATES:
        raise ZeroContextResumeFailure("authoritative async state invalid")
    run_id = _positive(async_state.get("run_id"), "authoritative_async.run_id", allow_none=True)
    if run_state not in {"NONE", "ABSENT"} and run_id is None:
        raise ZeroContextResumeFailure("authoritative run id missing")
    if run_state in {"NONE", "ABSENT"} and run_id is not None:
        raise ZeroContextResumeFailure("NONE/ABSENT run cannot carry run id")

    last_action = _required(execution.get("last_completed_action"), "execution.last_completed_action")
    next_action = _required(execution.get("only_next_legal_action"), "execution.only_next_legal_action")
    if run_state in _LIVE_RUN_STATES and next_action != "WAIT_FOR_AUTHORITATIVE_RUN_TERMINAL_EVENT":
        raise ZeroContextResumeFailure("live async next action drift")
    if run_state in _FAILURE_RUN_STATES and not next_action.startswith("CLASSIFY_"):
        raise ZeroContextResumeFailure("failed async next action drift")
    blocker = execution.get("blocker")
    if status == "BLOCKED" and not str(blocker or "").strip():
        raise ZeroContextResumeFailure("blocked packet missing blocker")
    if status != "BLOCKED" and blocker not in (None, ""):
        raise ZeroContextResumeFailure("non-blocked packet carries blocker")

    checkpoints = _normalize_checkpoints(packet.get("frozen_checkpoints") or [])
    packet["frozen_registry"] = _normalize_registry(packet.get("frozen_registry") or {}, checkpoints)
    packet["scope_lease"] = _normalize_scope_lease(packet.get("scope_lease") or {})
    packet["continuation_layers"] = {
        "detached_continuation": _normalize_layer(
            layers.get("detached_continuation") or {},
            "detached_continuation",
            count_fields=("workstream_count",),
        ),
        "event_driven_resume": _normalize_layer(
            layers.get("event_driven_resume") or {},
            "event_driven_resume",
            count_fields=("active_watch_count", "ready_count"),
        ),
        "execution_heartbeat_deadman": _normalize_layer(
            layers.get("execution_heartbeat_deadman") or {},
            "execution_heartbeat_deadman",
            count_fields=("worker_count", "recovery_receipt_count", "consumed_recovery_receipt_count"),
        ),
    }
    packet["proof"] = _normalize_proof(packet.get("proof") or {})

    expected_protections = {
        "step_2a_required": True,
        "scope_lease_required_for_mutation": True,
        "frozen_registry_required": True,
        "packet_does_not_authorize_mutation": True,
        "duplicate_async_run_forbidden": True,
        "blind_poll_loop_forbidden": True,
        "network_calls": False,
        "auto_mutate": False,
        "may_modify_product_runtime": False,
    }
    if dict(packet.get("protections") or {}) != expected_protections:
        raise ZeroContextResumeFailure("zero-context protections drifted")

    supplied = _hash64(packet.get("packet_hash"), "packet_hash")
    expected = _hash(_packet_body(packet))
    if supplied != expected:
        raise ZeroContextResumeFailure("zero-context packet hash mismatch")
    packet["packet_hash"] = supplied
    return packet


def bootstrap_view(packet: Mapping[str, Any]) -> dict[str, Any]:
    current = validate_packet(packet)
    program = current["program"]
    execution = current["execution"]
    async_state = current["authoritative_async"]
    return {
        "version": VERSION,
        "packet_hash": current["packet_hash"],
        "generation": current["generation"],
        "program_id": program["id"],
        "mission": program["mission"],
        "step": program["current_step"],
        "total_steps": program["total_steps"],
        "step_title": program["step_title"],
        "step_status": program["step_status"],
        "active_checkpoint": program["active_checkpoint"],
        "completed_steps": program["completed_steps"],
        "frozen_steps": program["frozen_steps"],
        "remaining_steps": program["remaining_steps"],
        "main_sha": current["repository_state"]["main_sha"],
        "authoritative_run_id": async_state["run_id"],
        "authoritative_run_state": async_state["state"],
        "last_completed_action": execution["last_completed_action"],
        "only_next_legal_action": execution["only_next_legal_action"],
        "blocker": execution["blocker"],
        "frozen_checkpoints": current["frozen_checkpoints"],
        "proof_run_id": current["proof"]["proof_run_id"],
        "terminal_receipt_digest": current["proof"]["terminal_receipt_digest"],
        "mutation_authority": False,
        "step_2a_required": True,
        "scope_lease_required_for_mutation": True,
    }


def verify_observed_snapshot(
    packet: Mapping[str, Any],
    *,
    observed_main_sha: str,
    observed_registry_state_hash: str,
) -> dict[str, Any]:
    current = validate_packet(packet)
    if current["repository_state"]["main_sha"] != _sha(observed_main_sha, "observed_main_sha"):
        return {
            "decision": "ZERO_CONTEXT_MAIN_STALE_CONTINUE",
            "allowed": False,
            "next_legal_action": "REREAD_ZERO_CONTEXT_PACKET",
        }
    if current["frozen_registry"]["state_hash"] != _hash64(
        observed_registry_state_hash, "observed_registry_state_hash"
    ):
        return {
            "decision": "ZERO_CONTEXT_REGISTRY_STALE_CONTINUE",
            "allowed": False,
            "next_legal_action": "REREAD_ZERO_CONTEXT_PACKET",
        }
    return {
        "decision": "ZERO_CONTEXT_SNAPSHOT_MATCH",
        "allowed": True,
        "context_authorized": True,
        "mutation_authority": False,
        "only_next_legal_action": current["execution"]["only_next_legal_action"],
    }


def require_context_authority(
    packet: Mapping[str, Any],
    *,
    observed_main_sha: str,
    observed_registry_state_hash: str,
) -> dict[str, Any]:
    result = verify_observed_snapshot(
        packet,
        observed_main_sha=observed_main_sha,
        observed_registry_state_hash=observed_registry_state_hash,
    )
    if result.get("allowed") is not True:
        raise ZeroContextResumeFailure(str(result.get("decision")))
    if result.get("mutation_authority") is not False:
        raise ZeroContextResumeFailure("zero-context packet must never grant mutation authority")
    return result


def contract_self_test() -> dict[str, Any]:
    main = "1" * 40
    registry_hash = "2" * 64
    scope_hash = "3" * 64
    detached_hash = "4" * 64
    event_hash = "5" * 64
    heartbeat_hash = "6" * 64
    receipt_hash = "7" * 64

    packet = build_packet(
        repository="owner/repo",
        generation=1,
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        mission="Finish the five-step execution-resilience upgrade without reopening frozen work.",
        current_step=5,
        total_steps=5,
        step_title="Zero-Context Resume Packet",
        step_status="FROZEN",
        active_checkpoint="MONSTER_V5_STEP5",
        completed_steps=(1, 2, 3, 4, 5),
        frozen_steps=(1, 2, 3, 4, 5),
        remaining_steps=(),
        main_sha=main,
        head_sha=main,
        branch="main",
        pr_number=None,
        authoritative_run_id=5005,
        authoritative_run_state="SUCCESS",
        last_completed_action="MONSTER_V5_STEP5_FROZEN",
        only_next_legal_action="MONSTER_V5_COMPLETE",
        blocker=None,
        frozen_registry={
            "revision": 14,
            "state_hash": registry_hash,
            "checkpoint_count": 5,
            "active_thaws": 0,
        },
        frozen_checkpoints=(
            "MONSTER_V5_STEP1",
            "MONSTER_V5_STEP2",
            "MONSTER_V5_STEP3",
            "MONSTER_V5_STEP4",
            "MONSTER_V5_STEP5",
        ),
        scope_lease={
            "revision": 30,
            "generation": 10,
            "state_hash": scope_hash,
            "holder_count": 0,
            "current_owner_id": None,
            "current_lease_id": None,
        },
        detached_continuation={
            "version": "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_V1",
            "revision": 0,
            "generation": 0,
            "state_hash": detached_hash,
            "workstream_count": 0,
        },
        event_driven_resume={
            "version": "MONSTER_V5_EVENT_DRIVEN_RESUME_V1",
            "revision": 0,
            "generation": 0,
            "state_hash": event_hash,
            "active_watch_count": 0,
            "ready_count": 0,
        },
        execution_heartbeat_deadman={
            "version": "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_V1",
            "revision": 0,
            "generation": 0,
            "state_hash": heartbeat_hash,
            "worker_count": 0,
            "recovery_receipt_count": 0,
            "consumed_recovery_receipt_count": 0,
        },
        proof={
            "proof_run_id": 5005,
            "terminal_receipt_digest": "sha256:" + receipt_hash,
        },
    )
    view = bootstrap_view(packet)
    snapshot = verify_observed_snapshot(
        packet,
        observed_main_sha=main,
        observed_registry_state_hash=registry_hash,
    )
    stale_main = verify_observed_snapshot(
        packet,
        observed_main_sha="8" * 40,
        observed_registry_state_hash=registry_hash,
    )
    stale_registry = verify_observed_snapshot(
        packet,
        observed_main_sha=main,
        observed_registry_state_hash="9" * 64,
    )

    tampered = deepcopy(packet)
    tampered["execution"]["only_next_legal_action"] = "MERGE_ANYTHING"
    tamper_blocked = False
    try:
        validate_packet(tampered)
    except ZeroContextResumeFailure:
        tamper_blocked = True

    chained = build_packet(
        repository="owner/repo",
        generation=2,
        previous_packet_hash=packet["packet_hash"],
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        mission=packet["program"]["mission"],
        current_step=5,
        total_steps=5,
        step_title="Zero-Context Resume Packet",
        step_status="FROZEN",
        active_checkpoint="MONSTER_V5_STEP5",
        completed_steps=(1, 2, 3, 4, 5),
        frozen_steps=(1, 2, 3, 4, 5),
        remaining_steps=(),
        main_sha=main,
        head_sha=main,
        branch="main",
        pr_number=None,
        authoritative_run_id=5006,
        authoritative_run_state="SUCCESS",
        last_completed_action="ZERO_CONTEXT_PACKET_REFRESHED",
        only_next_legal_action="MONSTER_V5_COMPLETE",
        blocker=None,
        frozen_registry=packet["frozen_registry"],
        frozen_checkpoints=packet["frozen_checkpoints"],
        scope_lease=packet["scope_lease"],
        detached_continuation=packet["continuation_layers"]["detached_continuation"],
        event_driven_resume=packet["continuation_layers"]["event_driven_resume"],
        execution_heartbeat_deadman=packet["continuation_layers"]["execution_heartbeat_deadman"],
        proof={"proof_run_id": 5006, "terminal_receipt_digest": "sha256:" + receipt_hash},
    )

    live_wait_enforced = False
    try:
        build_packet(
            repository="owner/repo",
            generation=1,
            program_id="MONSTER_V5",
            program_title="MONSTER V5",
            mission="test",
            current_step=5,
            total_steps=5,
            step_title="Zero-Context Resume Packet",
            step_status="ACTIVE",
            active_checkpoint="MONSTER_V5_STEP5",
            completed_steps=(1, 2, 3, 4),
            frozen_steps=(1, 2, 3, 4),
            remaining_steps=(5,),
            main_sha=main,
            head_sha=main,
            branch="feature",
            pr_number=5,
            authoritative_run_id=99,
            authoritative_run_state="IN_PROGRESS",
            last_completed_action="PATCH_COMPLETE",
            only_next_legal_action="RERUN_ANYWAY",
            blocker=None,
            frozen_registry=packet["frozen_registry"],
            frozen_checkpoints=packet["frozen_checkpoints"],
            scope_lease=packet["scope_lease"],
            detached_continuation=packet["continuation_layers"]["detached_continuation"],
            event_driven_resume=packet["continuation_layers"]["event_driven_resume"],
            execution_heartbeat_deadman=packet["continuation_layers"]["execution_heartbeat_deadman"],
            proof=packet["proof"],
        )
    except ZeroContextResumeFailure:
        live_wait_enforced = True

    result = {
        "status": "GREEN",
        "single_object_bootstrap": view["program_id"] == "MONSTER_V5",
        "mission_embedded": bool(view["mission"]),
        "progress_embedded": view["completed_steps"] == [1, 2, 3, 4, 5] and view["remaining_steps"] == [],
        "frozen_items_embedded": len(view["frozen_checkpoints"]) == 5,
        "authoritative_run_embedded": view["authoritative_run_id"] == 5005,
        "last_completed_action_embedded": view["last_completed_action"] == "MONSTER_V5_STEP5_FROZEN",
        "only_next_legal_action_embedded": view["only_next_legal_action"] == "MONSTER_V5_COMPLETE",
        "packet_tamper_blocked": tamper_blocked,
        "packet_chain_preserved": chained["previous_packet_hash"] == packet["packet_hash"] and chained["generation"] == 2,
        "stale_main_fails_closed": stale_main["decision"] == "ZERO_CONTEXT_MAIN_STALE_CONTINUE",
        "stale_registry_fails_closed": stale_registry["decision"] == "ZERO_CONTEXT_REGISTRY_STALE_CONTINUE",
        "matching_snapshot_context_authorized": snapshot["allowed"] is True,
        "live_async_forces_wait": live_wait_enforced,
        "step_2a_required": view["step_2a_required"] is True,
        "scope_lease_required": view["scope_lease_required_for_mutation"] is True,
        "packet_never_grants_mutation": view["mutation_authority"] is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        key for key, value in result.items()
        if isinstance(value, bool) and key not in {"network_calls", "auto_mutate", "product_runtime_mutation"}
    ]
    if not all(result[key] is True for key in required):
        raise ZeroContextResumeFailure(f"zero-context self-test failed: {result}")
    if result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise ZeroContextResumeFailure(f"unsafe zero-context capability enabled: {result}")
    return result


def main() -> int:
    print("MONSTER_V5_ZERO_CONTEXT_RESUME_PACKET_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
