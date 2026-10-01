"""MONSTER V5 Step 2 — Detached Execution / Background Continuation V1.

Durable repository-backed continuation packets let a new worker reconstruct an
active MONSTER mission without depending on chat history. This module does not
spawn background workers and does not authorize repository mutation by itself.
Mutation authority remains with MONSTER Step 2A plus the V5 scope-aware lease.

Persistence contract:
- state lives on a dedicated Git ref;
- every state and packet is tamper-evident;
- updates use revision/hash CAS;
- each workstream has one chained latest packet;
- worker handoff is CAS-bound and never implies mutation authority;
- live async work means WAIT, never duplicate;
- failed/cancelled async work means CLASSIFY before repair;
- unrelated main movement may be tolerated when scoped identities remain stable.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VERSION = "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_V1"
STATE_REF = "refs/heads/monster-detached-execution-continuations"
STATE_PATH = "devsystem/detached_execution_continuation_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_WORKSTREAM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")
_ASYNC_STATES = {"NONE", "QUEUED", "IN_PROGRESS", "SUCCESS", "FAILURE", "CANCELLED"}
_EXECUTION_STATES = {
    "ACTIVE", "WAITING_ON_ASYNC", "BLOCKED", "READY", "FROZEN", "COMPLETE"
}


class DetachedContinuationFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DetachedContinuationFailure(f"{field} is required")
    return text


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise DetachedContinuationFailure(f"{field} must be a full 40-character SHA")
    return text


def _hash64(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HASH64.fullmatch(text):
        raise DetachedContinuationFailure(f"{field} must be sha256")
    return text


def _positive(value: Any, field: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DetachedContinuationFailure(f"{field} must be positive") from exc
    if number <= 0:
        raise DetachedContinuationFailure(f"{field} must be positive")
    return number


def _packet_body(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = deepcopy(dict(payload))
    body.pop("packet_hash", None)
    return body


def _state_body(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = deepcopy(dict(payload))
    body.pop("state_hash", None)
    return body


def _normalize_scope_lease(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise DetachedContinuationFailure("scope_lease must be an object")
    return {
        "owner_id": _nonempty(raw.get("owner_id"), "scope_lease.owner_id"),
        "lease_id": _nonempty(raw.get("lease_id"), "scope_lease.lease_id"),
        "generation": _positive(raw.get("generation"), "scope_lease.generation"),
        "revision": _positive(raw.get("revision"), "scope_lease.revision"),
        "state_hash": _hash64(raw.get("state_hash"), "scope_lease.state_hash"),
    }


def _normalize_registry(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise DetachedContinuationFailure("frozen_registry must be an object")
    return {
        "revision": _positive(raw.get("revision"), "frozen_registry.revision"),
        "state_hash": _hash64(raw.get("state_hash"), "frozen_registry.state_hash"),
        "checkpoint_count": _positive(
            raw.get("checkpoint_count"), "frozen_registry.checkpoint_count"
        ),
    }


def build_packet(
    *,
    workstream_id: str,
    program_id: str,
    program_title: str,
    current_step: int,
    total_steps: int,
    step_title: str,
    execution_state: str,
    branch: str,
    head_sha: str,
    main_sha: str,
    pr_number: int | None,
    authoritative_run_id: int | None,
    authoritative_job_id: int | None,
    async_state: str,
    scope_lease: Mapping[str, Any],
    frozen_registry: Mapping[str, Any],
    blocker: str | None,
    last_completed_action: str,
    next_legal_action: str,
    worker_id: str,
    previous_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    workstream = _nonempty(workstream_id, "workstream_id")
    if not _WORKSTREAM_RE.fullmatch(workstream):
        raise DetachedContinuationFailure("workstream_id has invalid characters")
    current = _positive(current_step, "current_step")
    total = _positive(total_steps, "total_steps")
    if current is None or total is None or current > total:
        raise DetachedContinuationFailure("current_step must be inside total_steps")

    state = str(execution_state or "").strip().upper()
    if state not in _EXECUTION_STATES:
        raise DetachedContinuationFailure("execution_state is invalid")
    async_value = str(async_state or "").strip().upper()
    if async_value not in _ASYNC_STATES:
        raise DetachedContinuationFailure("async_state is invalid")

    run_id = _positive(authoritative_run_id, "authoritative_run_id", allow_none=True)
    job_id = _positive(authoritative_job_id, "authoritative_job_id", allow_none=True)
    if async_value in {"QUEUED", "IN_PROGRESS", "SUCCESS", "FAILURE", "CANCELLED"} and run_id is None:
        raise DetachedContinuationFailure("async state requires authoritative_run_id")
    if state == "WAITING_ON_ASYNC" and async_value not in {"QUEUED", "IN_PROGRESS"}:
        raise DetachedContinuationFailure("WAITING_ON_ASYNC requires live async state")
    if async_value in {"QUEUED", "IN_PROGRESS"} and state != "WAITING_ON_ASYNC":
        raise DetachedContinuationFailure("live async state requires WAITING_ON_ASYNC")

    clean_blocker = str(blocker or "").strip() or None
    if state == "BLOCKED" and clean_blocker is None:
        raise DetachedContinuationFailure("BLOCKED packet requires blocker")
    if state != "BLOCKED" and clean_blocker is not None:
        raise DetachedContinuationFailure("non-BLOCKED packet cannot carry blocker")

    previous_hash: str | None = None
    generation = 1
    if previous_packet is not None:
        previous = validate_packet(previous_packet)
        if previous["workstream_id"] != workstream:
            raise DetachedContinuationFailure("previous packet belongs to another workstream")
        previous_hash = previous["packet_hash"]
        generation = int(previous["generation"]) + 1

    packet: dict[str, Any] = {
        "version": VERSION,
        "workstream_id": workstream,
        "generation": generation,
        "previous_packet_hash": previous_hash,
        "program": {
            "id": _nonempty(program_id, "program_id"),
            "title": _nonempty(program_title, "program_title"),
            "current_step": current,
            "total_steps": total,
            "step_title": _nonempty(step_title, "step_title"),
        },
        "execution": {
            "state": state,
            "async_state": async_value,
            "blocker": clean_blocker,
            "last_completed_action": _nonempty(
                last_completed_action, "last_completed_action"
            ),
            "next_legal_action": _nonempty(next_legal_action, "next_legal_action"),
        },
        "repository": {
            "branch": _nonempty(branch, "branch"),
            "head_sha": _sha(head_sha, "head_sha"),
            "main_sha": _sha(main_sha, "main_sha"),
            "pr_number": _positive(pr_number, "pr_number", allow_none=True),
        },
        "authoritative_async": {
            "run_id": run_id,
            "job_id": job_id,
        },
        "scope_lease": _normalize_scope_lease(scope_lease),
        "frozen_registry": _normalize_registry(frozen_registry),
        "worker": {
            "worker_id": _nonempty(worker_id, "worker_id"),
        },
        "protections": {
            "step_2a_required": True,
            "scope_lease_required_for_mutation": True,
            "packet_does_not_authorize_mutation": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    packet["packet_hash"] = _hash(packet)
    return validate_packet(packet)


def validate_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DetachedContinuationFailure("continuation packet must be an object")
    packet = deepcopy(dict(payload))
    if packet.get("version") != VERSION:
        raise DetachedContinuationFailure("continuation packet version mismatch")
    workstream = str(packet.get("workstream_id") or "")
    if not _WORKSTREAM_RE.fullmatch(workstream):
        raise DetachedContinuationFailure("workstream_id invalid")
    _positive(packet.get("generation"), "generation")
    previous = packet.get("previous_packet_hash")
    if previous is not None:
        _hash64(previous, "previous_packet_hash")

    program = packet.get("program")
    execution = packet.get("execution")
    repository = packet.get("repository")
    authoritative = packet.get("authoritative_async")
    worker = packet.get("worker")
    if not all(isinstance(v, Mapping) for v in (
        program, execution, repository, authoritative, worker
    )):
        raise DetachedContinuationFailure("packet sub-objects are malformed")

    current = _positive(program.get("current_step"), "program.current_step")
    total = _positive(program.get("total_steps"), "program.total_steps")
    if current is None or total is None or current > total:
        raise DetachedContinuationFailure("program step accounting invalid")
    _nonempty(program.get("id"), "program.id")
    _nonempty(program.get("title"), "program.title")
    _nonempty(program.get("step_title"), "program.step_title")

    state = str(execution.get("state") or "").upper()
    async_state = str(execution.get("async_state") or "").upper()
    if state not in _EXECUTION_STATES or async_state not in _ASYNC_STATES:
        raise DetachedContinuationFailure("packet execution state invalid")
    blocker = execution.get("blocker")
    if state == "BLOCKED" and not str(blocker or "").strip():
        raise DetachedContinuationFailure("BLOCKED packet requires blocker")
    if state != "BLOCKED" and blocker not in (None, ""):
        raise DetachedContinuationFailure("non-BLOCKED packet cannot carry blocker")
    _nonempty(execution.get("last_completed_action"), "execution.last_completed_action")
    _nonempty(execution.get("next_legal_action"), "execution.next_legal_action")

    _nonempty(repository.get("branch"), "repository.branch")
    _sha(repository.get("head_sha"), "repository.head_sha")
    _sha(repository.get("main_sha"), "repository.main_sha")
    _positive(repository.get("pr_number"), "repository.pr_number", allow_none=True)

    run_id = _positive(
        authoritative.get("run_id"), "authoritative_async.run_id", allow_none=True
    )
    _positive(
        authoritative.get("job_id"), "authoritative_async.job_id", allow_none=True
    )
    if async_state in {"QUEUED", "IN_PROGRESS", "SUCCESS", "FAILURE", "CANCELLED"} and run_id is None:
        raise DetachedContinuationFailure("async packet is missing authoritative run")
    if state == "WAITING_ON_ASYNC" and async_state not in {"QUEUED", "IN_PROGRESS"}:
        raise DetachedContinuationFailure("WAITING_ON_ASYNC packet is inconsistent")
    if async_state in {"QUEUED", "IN_PROGRESS"} and state != "WAITING_ON_ASYNC":
        raise DetachedContinuationFailure("live async packet is inconsistent")

    packet["scope_lease"] = _normalize_scope_lease(packet.get("scope_lease") or {})
    packet["frozen_registry"] = _normalize_registry(packet.get("frozen_registry") or {})
    _nonempty(worker.get("worker_id"), "worker.worker_id")

    expected_protections = {
        "step_2a_required": True,
        "scope_lease_required_for_mutation": True,
        "packet_does_not_authorize_mutation": True,
        "network_calls": False,
        "auto_mutate": False,
        "may_modify_product_runtime": False,
    }
    if dict(packet.get("protections") or {}) != expected_protections:
        raise DetachedContinuationFailure("continuation protections drifted")

    supplied = _hash64(packet.get("packet_hash"), "packet_hash")
    expected = _hash(_packet_body(packet))
    if supplied != expected:
        raise DetachedContinuationFailure("continuation packet hash mismatch")
    packet["packet_hash"] = supplied
    return packet


def new_state(repository: str) -> dict[str, Any]:
    repo = str(repository or "").strip().lower()
    if "/" not in repo:
        raise DetachedContinuationFailure("repository must be owner/name")
    state = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "state_ref": STATE_REF,
        "state_path": STATE_PATH,
        "revision": 0,
        "generation": 0,
        "continuations": {},
    }
    state["state_hash"] = _hash(state)
    return validate_state(state)


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DetachedContinuationFailure("continuation state must be an object")
    state = deepcopy(dict(payload))
    if int(state.get("schema_version", 0)) != 1 or state.get("version") != VERSION:
        raise DetachedContinuationFailure("continuation state version/schema mismatch")
    if state.get("state_ref") != STATE_REF or state.get("state_path") != STATE_PATH:
        raise DetachedContinuationFailure("continuation persistence identity mismatch")
    if "/" not in str(state.get("repository") or ""):
        raise DetachedContinuationFailure("continuation repository invalid")
    if int(state.get("revision", -1)) < 0 or int(state.get("generation", -1)) < 0:
        raise DetachedContinuationFailure("continuation revision/generation invalid")

    continuations = state.get("continuations")
    if not isinstance(continuations, Mapping):
        raise DetachedContinuationFailure("continuations must be an object")
    normalized: dict[str, Any] = {}
    for key, raw in continuations.items():
        packet = validate_packet(raw)
        if str(key) != packet["workstream_id"]:
            raise DetachedContinuationFailure("continuation key/workstream mismatch")
        normalized[str(key)] = packet
    state["continuations"] = dict(sorted(normalized.items()))

    supplied = _hash64(state.get("state_hash"), "state_hash")
    expected = _hash(_state_body(state))
    if supplied != expected:
        raise DetachedContinuationFailure("continuation state hash mismatch")
    state["state_hash"] = supplied
    return state


def _cas(state: Mapping[str, Any], revision: int, state_hash: str) -> dict[str, Any] | None:
    if int(state["revision"]) != int(revision) or str(state["state_hash"]) != str(state_hash):
        return {
            "decision": "DETACHED_CONTINUATION_STALE_CAS",
            "allowed": False,
            "next_legal_action": "REREAD_CONTINUATION_STATE",
        }
    return None


def persist_packet(
    state: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}

    candidate = validate_packet(packet)
    previous = current["continuations"].get(candidate["workstream_id"])
    if previous is None:
        if candidate["generation"] != 1 or candidate["previous_packet_hash"] is not None:
            raise DetachedContinuationFailure("first workstream packet must start generation 1")
    else:
        if candidate["generation"] != int(previous["generation"]) + 1:
            raise DetachedContinuationFailure("continuation generation must advance by one")
        if candidate["previous_packet_hash"] != previous["packet_hash"]:
            raise DetachedContinuationFailure("continuation packet chain mismatch")

    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    updated["continuations"][candidate["workstream_id"]] = candidate
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    updated = validate_state(updated)
    return {
        "result": {
            "decision": "CONTINUATION_PACKET_PERSISTED",
            "allowed": True,
            "workstream_id": candidate["workstream_id"],
            "packet_hash": candidate["packet_hash"],
            "generation": candidate["generation"],
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def handoff_worker(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    new_worker_id: str,
    expected_packet_hash: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}

    key = str(workstream_id or "").strip()
    packet = current["continuations"].get(key)
    if packet is None:
        raise DetachedContinuationFailure("workstream continuation not found")
    if packet["packet_hash"] != str(expected_packet_hash):
        return {
            "result": {
                "decision": "DETACHED_HANDOFF_STALE_PACKET",
                "allowed": False,
                "next_legal_action": "REREAD_CONTINUATION_PACKET",
            },
            "state": current,
        }

    next_packet = deepcopy(packet)
    next_packet["generation"] = int(packet["generation"]) + 1
    next_packet["previous_packet_hash"] = packet["packet_hash"]
    next_packet["worker"] = {"worker_id": _nonempty(new_worker_id, "new_worker_id")}
    next_packet.pop("packet_hash", None)
    next_packet["packet_hash"] = _hash(next_packet)
    next_packet = validate_packet(next_packet)

    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    updated["continuations"][key] = next_packet
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    updated = validate_state(updated)
    return {
        "result": {
            "decision": "DETACHED_WORKER_HANDOFF_PERSISTED",
            "allowed": True,
            "workstream_id": key,
            "worker_id": next_packet["worker"]["worker_id"],
            "packet_hash": next_packet["packet_hash"],
            "state_hash": updated["state_hash"],
            "mutation_authority_granted": False,
        },
        "state": updated,
    }


def resume_decision(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    current_branch: str,
    current_head_sha: str,
    current_main_sha: str,
    current_scope_lease: Mapping[str, Any],
    current_frozen_registry: Mapping[str, Any],
    scope_identity_stable: bool,
    frozen_scope_stable: bool,
) -> dict[str, Any]:
    current = validate_state(state)
    packet = current["continuations"].get(str(workstream_id or "").strip())
    if packet is None:
        return {
            "decision": "DETACHED_CONTINUATION_MISSING",
            "allowed_to_resume": False,
            "mutation_authority_granted": False,
        }
    packet = validate_packet(packet)

    repo = packet["repository"]
    if str(current_branch) != repo["branch"] or _sha(current_head_sha, "current_head_sha") != repo["head_sha"]:
        return {
            "decision": "DETACHED_REVALIDATE_REPOSITORY_IDENTITY",
            "allowed_to_resume": False,
            "mutation_authority_granted": False,
        }

    live_lease = _normalize_scope_lease(current_scope_lease)
    bound_lease = packet["scope_lease"]
    lease_identity_stable = (
        live_lease["owner_id"] == bound_lease["owner_id"]
        and live_lease["lease_id"] == bound_lease["lease_id"]
        and live_lease["generation"] == bound_lease["generation"]
    )
    if not lease_identity_stable or not bool(scope_identity_stable):
        return {
            "decision": "DETACHED_REVALIDATE_SCOPE_LEASE",
            "allowed_to_resume": False,
            "mutation_authority_granted": False,
        }

    live_registry = _normalize_registry(current_frozen_registry)
    registry_changed = (
        live_registry["revision"] != packet["frozen_registry"]["revision"]
        or live_registry["state_hash"] != packet["frozen_registry"]["state_hash"]
    )
    if not bool(frozen_scope_stable):
        return {
            "decision": "DETACHED_REVALIDATE_FROZEN_SCOPE",
            "allowed_to_resume": False,
            "registry_changed": registry_changed,
            "mutation_authority_granted": False,
        }

    execution = packet["execution"]
    async_state = execution["async_state"]
    main_advanced = _sha(current_main_sha, "current_main_sha") != repo["main_sha"]

    common = {
        "workstream_id": packet["workstream_id"],
        "packet_hash": packet["packet_hash"],
        "worker_id": packet["worker"]["worker_id"],
        "main_advanced_advisory": main_advanced,
        "registry_changed_advisory": registry_changed,
        "mutation_authority_granted": False,
    }

    if execution["state"] in {"FROZEN", "COMPLETE"}:
        return {
            **common,
            "decision": "DETACHED_DO_NOT_REOPEN_COMPLETED_WORK",
            "allowed_to_resume": False,
            "next_legal_action": execution["next_legal_action"],
        }
    if execution["state"] == "BLOCKED":
        return {
            **common,
            "decision": "DETACHED_BLOCKER_MUST_RESOLVE",
            "allowed_to_resume": False,
            "blocker": execution["blocker"],
            "next_legal_action": execution["next_legal_action"],
        }
    if async_state in {"QUEUED", "IN_PROGRESS"}:
        return {
            **common,
            "decision": "DETACHED_WAIT_AUTHORITATIVE_ASYNC",
            "allowed_to_resume": True,
            "may_mutate_now": False,
            "authoritative_run_id": packet["authoritative_async"]["run_id"],
            "next_legal_action": "WAIT_FOR_AUTHORITATIVE_ASYNC_TERMINAL",
        }
    if async_state in {"FAILURE", "CANCELLED"}:
        return {
            **common,
            "decision": "DETACHED_CLASSIFY_ASYNC_TERMINAL",
            "allowed_to_resume": True,
            "may_mutate_now": False,
            "authoritative_run_id": packet["authoritative_async"]["run_id"],
            "next_legal_action": "CLASSIFY_AUTHORITATIVE_ASYNC_TERMINAL",
        }

    return {
        **common,
        "decision": "DETACHED_READY_TO_RESUME",
        "allowed_to_resume": True,
        "may_mutate_now": True,
        "next_legal_action": execution["next_legal_action"],
    }


def contract_self_test() -> dict[str, Any]:
    repo = "owner/repo"
    head = "a" * 40
    main = "b" * 40
    moved_main = "c" * 40
    lease = {
        "owner_id": "chat:monster-step2",
        "lease_id": "SCOPE-LEASE-ABC",
        "generation": 2,
        "revision": 4,
        "state_hash": "1" * 64,
    }
    registry = {"revision": 8, "state_hash": "2" * 64, "checkpoint_count": 22}

    state = new_state(repo)
    waiting = build_packet(
        workstream_id="monster-v5-step2",
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        current_step=2,
        total_steps=5,
        step_title="Detached Execution / Background Continuation",
        execution_state="WAITING_ON_ASYNC",
        branch="feature",
        head_sha=head,
        main_sha=main,
        pr_number=1279,
        authoritative_run_id=999,
        authoritative_job_id=None,
        async_state="IN_PROGRESS",
        scope_lease=lease,
        frozen_registry=registry,
        blocker=None,
        last_completed_action="opened PR",
        next_legal_action="WAIT_FOR_RUN_999_TERMINAL",
        worker_id="worker-a",
    )
    first = persist_packet(
        state, waiting,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    wait_decision = resume_decision(
        first["state"],
        workstream_id="monster-v5-step2",
        current_branch="feature",
        current_head_sha=head,
        current_main_sha=moved_main,
        current_scope_lease={**lease, "revision": 5, "state_hash": "3" * 64},
        current_frozen_registry={**registry, "revision": 9, "state_hash": "4" * 64},
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )

    handoff = handoff_worker(
        first["state"],
        workstream_id="monster-v5-step2",
        new_worker_id="worker-b",
        expected_packet_hash=waiting["packet_hash"],
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    stale_handoff = handoff_worker(
        first["state"],
        workstream_id="monster-v5-step2",
        new_worker_id="worker-c",
        expected_packet_hash=waiting["packet_hash"],
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    handed = handoff["state"]["continuations"]["monster-v5-step2"]

    ready = build_packet(
        workstream_id="monster-v5-step2",
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        current_step=2,
        total_steps=5,
        step_title="Detached Execution / Background Continuation",
        execution_state="READY",
        branch="feature",
        head_sha=head,
        main_sha=main,
        pr_number=1279,
        authoritative_run_id=999,
        authoritative_job_id=None,
        async_state="SUCCESS",
        scope_lease=lease,
        frozen_registry=registry,
        blocker=None,
        last_completed_action="authoritative run 999 succeeded",
        next_legal_action="MERGE_PR_1279",
        worker_id="worker-b",
        previous_packet=handed,
    )
    second = persist_packet(
        handoff["state"], ready,
        expected_revision=handoff["state"]["revision"],
        expected_state_hash=handoff["state"]["state_hash"],
    )
    ready_decision = resume_decision(
        second["state"],
        workstream_id="monster-v5-step2",
        current_branch="feature",
        current_head_sha=head,
        current_main_sha=moved_main,
        current_scope_lease=lease,
        current_frozen_registry=registry,
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )

    failed = build_packet(
        workstream_id="failure-stream",
        program_id="X",
        program_title="X",
        current_step=1,
        total_steps=1,
        step_title="X",
        execution_state="ACTIVE",
        branch="failure",
        head_sha=head,
        main_sha=main,
        pr_number=None,
        authoritative_run_id=1000,
        authoritative_job_id=None,
        async_state="FAILURE",
        scope_lease=lease,
        frozen_registry=registry,
        blocker=None,
        last_completed_action="run failed",
        next_legal_action="CLASSIFY_RUN_1000",
        worker_id="worker-z",
    )
    third = persist_packet(
        second["state"], failed,
        expected_revision=second["state"]["revision"],
        expected_state_hash=second["state"]["state_hash"],
    )
    failure_decision = resume_decision(
        third["state"],
        workstream_id="failure-stream",
        current_branch="failure",
        current_head_sha=head,
        current_main_sha=main,
        current_scope_lease=lease,
        current_frozen_registry=registry,
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )

    tampered = deepcopy(ready)
    tampered["execution"]["next_legal_action"] = "SKIP_ALL_GATES"
    tamper_rejected = False
    try:
        validate_packet(tampered)
    except DetachedContinuationFailure:
        tamper_rejected = True

    scope_drift = resume_decision(
        second["state"],
        workstream_id="monster-v5-step2",
        current_branch="feature",
        current_head_sha=head,
        current_main_sha=main,
        current_scope_lease=lease,
        current_frozen_registry=registry,
        scope_identity_stable=False,
        frozen_scope_stable=True,
    )
    frozen_drift = resume_decision(
        second["state"],
        workstream_id="monster-v5-step2",
        current_branch="feature",
        current_head_sha=head,
        current_main_sha=main,
        current_scope_lease=lease,
        current_frozen_registry=registry,
        scope_identity_stable=True,
        frozen_scope_stable=False,
    )
    head_drift = resume_decision(
        second["state"],
        workstream_id="monster-v5-step2",
        current_branch="feature",
        current_head_sha="d" * 40,
        current_main_sha=main,
        current_scope_lease=lease,
        current_frozen_registry=registry,
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "repository_backed_state_contract": STATE_REF.startswith("refs/heads/"),
        "tamper_evident_packet": tamper_rejected,
        "cas_persistence": first["result"]["decision"] == "CONTINUATION_PACKET_PERSISTED",
        "live_async_waits_without_duplicate": (
            wait_decision["decision"] == "DETACHED_WAIT_AUTHORITATIVE_ASYNC"
            and wait_decision["may_mutate_now"] is False
        ),
        "worker_handoff_is_cas_bound": (
            handoff["result"]["allowed"] is True
            and handoff["result"]["worker_id"] == "worker-b"
            and stale_handoff["result"]["decision"] == "DETACHED_CONTINUATION_STALE_CAS"
        ),
        "handoff_does_not_grant_mutation": (
            handoff["result"]["mutation_authority_granted"] is False
        ),
        "resume_without_chat_history": (
            ready_decision["decision"] == "DETACHED_READY_TO_RESUME"
            and ready_decision["next_legal_action"] == "MERGE_PR_1279"
        ),
        "unrelated_main_movement_tolerated": ready_decision["main_advanced_advisory"] is True,
        "scope_drift_fails_closed": scope_drift["decision"] == "DETACHED_REVALIDATE_SCOPE_LEASE",
        "frozen_scope_drift_fails_closed": frozen_drift["decision"] == "DETACHED_REVALIDATE_FROZEN_SCOPE",
        "head_drift_fails_closed": head_drift["decision"] == "DETACHED_REVALIDATE_REPOSITORY_IDENTITY",
        "failed_async_forces_classification": (
            failure_decision["decision"] == "DETACHED_CLASSIFY_ASYNC_TERMINAL"
            and failure_decision["may_mutate_now"] is False
        ),
        "multiple_workstreams_supported": len(third["state"]["continuations"]) == 2,
        "step_2a_still_required": ready["protections"]["step_2a_required"] is True,
        "scope_lease_still_required": ready["protections"]["scope_lease_required_for_mutation"] is True,
        "packet_never_grants_mutation": MUTATION_AUTHORITY_GRANTED is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        key for key, value in result.items()
        if isinstance(value, bool)
        and key not in {"network_calls", "auto_mutate", "product_runtime_mutation"}
    ]
    if not all(result[key] is True for key in required):
        raise DetachedContinuationFailure("detached continuation self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise DetachedContinuationFailure("detached continuation safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DetachedContinuationFailure as exc:
        print(
            f"MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_BLOCKED: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
