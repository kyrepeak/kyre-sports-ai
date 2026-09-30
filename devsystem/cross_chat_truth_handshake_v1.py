"""MONSTER V4 Step 4 — Cross-Chat Truth Handshake V1.

Every execution-capable MONSTER session must consume one authoritative,
repository-backed bootstrap packet before the frozen semantic/lease/2A chain
is reachable.

Authoritative state lives outside normal PR branches on:
    refs/heads/monster-cross-chat-truth

The packet binds:
- repository + current main SHA,
- current MONSTER program/step/checkpoint,
- active PR/run/head,
- blocker + next legal action,
- distributed lease revision/generation/state hash/holder,
- frozen-artifact registry revision/state hash/count,
- complete frozen-checkpoint set.

A missing, stale, or tampered packet fails closed. The packet is not itself
mutation authority; a valid handshake must still pass Semantic Action
Normalizer -> Distributed Execution Lease -> MONSTER 2A.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.distributed_execution_lease_v1 import validate_lease_state
from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.semantic_action_normalizer_v1 import (
    SemanticActionNormalizerFailure,
    canonicalize_action,
    enforce_semantic_action,
    require_semantic_execution_authority,
)

VERSION = "MONSTER_V4_CROSS_CHAT_TRUTH_HANDSHAKE_V1"
TRUTH_REF = "refs/heads/monster-cross-chat-truth"
TRUTH_PATH = "devsystem/cross_chat_truth_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_CONSUMER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")


class CrossChatTruthFailure(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _without_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    result.pop("state_hash", None)
    return result


def _validate_sha(value: Any, field: str) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA40.fullmatch(sha):
        raise CrossChatTruthFailure(f"{field} must be a full 40-character SHA")
    return sha


def _validate_hash(value: Any, field: str) -> str:
    digest = str(value or "").strip().lower()
    if not _HASH64.fullmatch(digest):
        raise CrossChatTruthFailure(f"{field} must be a 64-character sha256")
    return digest


def _validate_consumer(value: Any) -> str:
    consumer = str(value or "").strip()
    if not _CONSUMER_RE.fullmatch(consumer):
        raise CrossChatTruthFailure("consumer_id has invalid format")
    return consumer


def build_truth_packet(
    *,
    repository: str,
    truth_epoch: int,
    program_id: str,
    program_title: str,
    current_step: int,
    total_steps: int,
    step_title: str,
    step_status: str,
    active_checkpoint: str,
    main_sha: str,
    active_head_sha: str,
    lease_state: Mapping[str, Any],
    registry_state: Mapping[str, Any],
    next_legal_action: str,
    active_pr: int | None = None,
    active_run: int | None = None,
    blocker: str | None = None,
) -> dict[str, Any]:
    lease = validate_lease_state(lease_state)
    registry_validation = validate_registry(registry_state)
    repo = str(repository or "").strip().lower()
    if "/" not in repo:
        raise CrossChatTruthFailure("repository must be owner/name")

    holder = lease["holder"]
    packet = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "truth_ref": TRUTH_REF,
        "truth_path": TRUTH_PATH,
        "truth_epoch": int(truth_epoch),
        "program_id": str(program_id or "").strip(),
        "program_title": str(program_title or "").strip(),
        "current_step": int(current_step),
        "total_steps": int(total_steps),
        "step_title": str(step_title or "").strip(),
        "step_status": str(step_status or "").strip().upper(),
        "active_checkpoint": str(active_checkpoint or "").strip(),
        "main_sha": _validate_sha(main_sha, "main_sha"),
        "active_pr": int(active_pr) if active_pr is not None else None,
        "active_run": int(active_run) if active_run is not None else None,
        "active_head_sha": _validate_sha(active_head_sha, "active_head_sha"),
        "blocker": str(blocker).strip() if blocker else None,
        "next_legal_action": str(next_legal_action or "").strip(),
        "lease": {
            "revision": int(lease["revision"]),
            "generation": int(lease["generation"]),
            "state_hash": str(lease["state_hash"]),
            "holder_owner_id": str(holder["owner_id"]) if holder else None,
            "holder_lease_id": str(holder["lease_id"]) if holder else None,
        },
        "frozen_registry": {
            "revision": int(registry_state["revision"]),
            "state_hash": str(registry_state["state_hash"]),
            "checkpoint_count": int(registry_validation["entry_count"]),
            "active_thaws": len(registry_state["active_thaws"]),
        },
        "frozen_checkpoints": sorted(str(key) for key in registry_state["entries"]),
    }
    packet["state_hash"] = _hash(packet)
    return validate_truth_packet(packet)


def validate_truth_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CrossChatTruthFailure("truth packet must be an object")
    packet = deepcopy(dict(payload))
    required = {
        "schema_version",
        "version",
        "repository",
        "truth_ref",
        "truth_path",
        "truth_epoch",
        "program_id",
        "program_title",
        "current_step",
        "total_steps",
        "step_title",
        "step_status",
        "active_checkpoint",
        "main_sha",
        "active_pr",
        "active_run",
        "active_head_sha",
        "blocker",
        "next_legal_action",
        "lease",
        "frozen_registry",
        "frozen_checkpoints",
        "state_hash",
    }
    missing = sorted(required - set(packet))
    if missing:
        raise CrossChatTruthFailure("truth packet missing fields: " + ", ".join(missing))
    if int(packet["schema_version"]) != 1:
        raise CrossChatTruthFailure("truth schema mismatch")
    if packet["version"] != VERSION:
        raise CrossChatTruthFailure("truth version mismatch")
    if packet["truth_ref"] != TRUTH_REF:
        raise CrossChatTruthFailure("truth ref mismatch")
    if packet["truth_path"] != TRUTH_PATH:
        raise CrossChatTruthFailure("truth path mismatch")
    if "/" not in str(packet["repository"]):
        raise CrossChatTruthFailure("truth repository invalid")
    if int(packet["truth_epoch"]) <= 0:
        raise CrossChatTruthFailure("truth_epoch must be positive")
    total = int(packet["total_steps"])
    step = int(packet["current_step"])
    if total <= 0 or step <= 0 or step > total:
        raise CrossChatTruthFailure("current_step/total_steps invalid")
    if not str(packet["program_id"] or "").strip():
        raise CrossChatTruthFailure("program_id required")
    if not str(packet["step_title"] or "").strip():
        raise CrossChatTruthFailure("step_title required")
    if packet["step_status"] not in {"ACTIVE", "READY", "FROZEN", "COMPLETE", "BLOCKED"}:
        raise CrossChatTruthFailure("step_status invalid")
    if not str(packet["active_checkpoint"] or "").strip():
        raise CrossChatTruthFailure("active_checkpoint required")
    _validate_sha(packet["main_sha"], "main_sha")
    _validate_sha(packet["active_head_sha"], "active_head_sha")
    if packet["active_pr"] is not None and int(packet["active_pr"]) <= 0:
        raise CrossChatTruthFailure("active_pr invalid")
    if packet["active_run"] is not None and int(packet["active_run"]) <= 0:
        raise CrossChatTruthFailure("active_run invalid")
    if not str(packet["next_legal_action"] or "").strip():
        raise CrossChatTruthFailure("next_legal_action required")

    lease = packet["lease"]
    if not isinstance(lease, Mapping):
        raise CrossChatTruthFailure("lease summary must be object")
    lease_required = {
        "revision",
        "generation",
        "state_hash",
        "holder_owner_id",
        "holder_lease_id",
    }
    if lease_required - set(lease):
        raise CrossChatTruthFailure("lease summary missing fields")
    if int(lease["revision"]) < 0 or int(lease["generation"]) < 0:
        raise CrossChatTruthFailure("lease revision/generation invalid")
    _validate_hash(lease["state_hash"], "lease.state_hash")
    if (lease["holder_owner_id"] is None) != (lease["holder_lease_id"] is None):
        raise CrossChatTruthFailure("lease holder summary must be fully null or fully set")

    frozen = packet["frozen_registry"]
    if not isinstance(frozen, Mapping):
        raise CrossChatTruthFailure("frozen_registry summary must be object")
    frozen_required = {"revision", "state_hash", "checkpoint_count", "active_thaws"}
    if frozen_required - set(frozen):
        raise CrossChatTruthFailure("frozen_registry summary missing fields")
    if int(frozen["revision"]) < 0 or int(frozen["checkpoint_count"]) <= 0:
        raise CrossChatTruthFailure("frozen registry revision/count invalid")
    if int(frozen["active_thaws"]) < 0:
        raise CrossChatTruthFailure("frozen active_thaws invalid")
    _validate_hash(frozen["state_hash"], "frozen_registry.state_hash")

    checkpoints = packet["frozen_checkpoints"]
    if not isinstance(checkpoints, list) or not checkpoints:
        raise CrossChatTruthFailure("frozen_checkpoints required")
    if len(checkpoints) != len(set(checkpoints)):
        raise CrossChatTruthFailure("frozen_checkpoints contain duplicates")
    if len(checkpoints) != int(frozen["checkpoint_count"]):
        raise CrossChatTruthFailure("frozen checkpoint count mismatch")
    if checkpoints != sorted(checkpoints):
        raise CrossChatTruthFailure("frozen_checkpoints must be sorted")

    expected = _hash(_without_hash(packet))
    if str(packet["state_hash"] or "") != expected:
        raise CrossChatTruthFailure("truth state hash mismatch")
    return packet


def bootstrap_view(packet: Mapping[str, Any]) -> dict[str, Any]:
    truth = validate_truth_packet(packet)
    return {
        "program": truth["program_id"],
        "step": truth["current_step"],
        "total_steps": truth["total_steps"],
        "step_title": truth["step_title"],
        "step_status": truth["step_status"],
        "main_sha": truth["main_sha"],
        "active_pr": truth["active_pr"],
        "active_run": truth["active_run"],
        "active_head_sha": truth["active_head_sha"],
        "blocker": truth["blocker"],
        "next_legal_action": truth["next_legal_action"],
        "lease_generation": truth["lease"]["generation"],
        "frozen_checkpoint_count": truth["frozen_registry"]["checkpoint_count"],
        "truth_epoch": truth["truth_epoch"],
        "truth_state_hash": truth["state_hash"],
    }


def _blocked(decision: str, reason: str) -> dict[str, Any]:
    return {
        "version": VERSION,
        "decision": decision,
        "reason": reason,
        "allowed": False,
        "cross_chat_truth_authorized": False,
        "requires_user_intervention": False,
        "continuation_policy": "CONTINUE_NON_CONFLICTING_WORK",
        "next_legal_action": "REFRESH_CROSS_CHAT_TRUTH",
    }


def authorize_handshake(
    packet: Mapping[str, Any] | None,
    *,
    consumer_id: str,
    observed_main_sha: str,
    lease_state: Mapping[str, Any],
    registry_state: Mapping[str, Any],
) -> dict[str, Any]:
    if packet is None:
        return _blocked(
            "HANDSHAKE_REQUIRED_CONTINUE",
            "authoritative cross-chat truth packet is required",
        )
    try:
        truth = validate_truth_packet(packet)
        lease = validate_lease_state(lease_state)
        registry_validation = validate_registry(registry_state)
    except Exception as exc:
        return _blocked("HANDSHAKE_INVALID_CONTINUE", str(exc))

    consumer = _validate_consumer(consumer_id)
    mismatches: list[str] = []

    main = _validate_sha(observed_main_sha, "observed_main_sha")
    if truth["main_sha"] != main:
        mismatches.append("main_sha")

    holder = lease["holder"]
    observed_holder_owner = str(holder["owner_id"]) if holder else None
    observed_holder_lease = str(holder["lease_id"]) if holder else None
    expected_lease = truth["lease"]
    if int(expected_lease["revision"]) != int(lease["revision"]):
        mismatches.append("lease.revision")
    if int(expected_lease["generation"]) != int(lease["generation"]):
        mismatches.append("lease.generation")
    if str(expected_lease["state_hash"]) != str(lease["state_hash"]):
        mismatches.append("lease.state_hash")
    if expected_lease["holder_owner_id"] != observed_holder_owner:
        mismatches.append("lease.holder_owner_id")
    if expected_lease["holder_lease_id"] != observed_holder_lease:
        mismatches.append("lease.holder_lease_id")

    expected_registry = truth["frozen_registry"]
    if int(expected_registry["revision"]) != int(registry_state["revision"]):
        mismatches.append("frozen_registry.revision")
    if str(expected_registry["state_hash"]) != str(registry_state["state_hash"]):
        mismatches.append("frozen_registry.state_hash")
    if int(expected_registry["checkpoint_count"]) != int(registry_validation["entry_count"]):
        mismatches.append("frozen_registry.checkpoint_count")
    if int(expected_registry["active_thaws"]) != len(registry_state["active_thaws"]):
        mismatches.append("frozen_registry.active_thaws")
    if truth["frozen_checkpoints"] != sorted(str(k) for k in registry_state["entries"]):
        mismatches.append("frozen_checkpoints")

    if mismatches:
        return _blocked(
            "HANDSHAKE_STALE_CONTINUE",
            "authoritative truth differs from observed repository state: "
            + ", ".join(mismatches),
        )

    proof_payload = {
        "schema_version": 1,
        "version": VERSION,
        "consumer_id": consumer,
        "truth_epoch": truth["truth_epoch"],
        "truth_state_hash": truth["state_hash"],
        "main_sha": main,
        "lease_state_hash": lease["state_hash"],
        "registry_state_hash": registry_state["state_hash"],
        "active_checkpoint": truth["active_checkpoint"],
        "current_step": truth["current_step"],
        "next_legal_action": truth["next_legal_action"],
    }
    return {
        "version": VERSION,
        "decision": "HANDSHAKE_AUTHORIZED",
        "allowed": True,
        "cross_chat_truth_authorized": True,
        "requires_user_intervention": False,
        "bootstrap": bootstrap_view(truth),
        "handshake_proof": {
            "payload": proof_payload,
            "proof_hash": _hash(proof_payload),
        },
    }


def validate_handshake_proof(
    proof: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    consumer_id: str,
    observed_main_sha: str,
    lease_state: Mapping[str, Any],
    registry_state: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(proof, Mapping):
        raise CrossChatTruthFailure("handshake proof must be object")
    expected = authorize_handshake(
        packet,
        consumer_id=consumer_id,
        observed_main_sha=observed_main_sha,
        lease_state=lease_state,
        registry_state=registry_state,
    )
    if expected.get("allowed") is not True:
        raise CrossChatTruthFailure(
            "current cross-chat truth is not authorized: "
            + str(expected.get("decision"))
        )
    expected_proof = expected["handshake_proof"]
    if proof != expected_proof:
        raise CrossChatTruthFailure("handshake proof mismatch or tamper")
    return {
        "status": "GREEN",
        "proof_hash": expected_proof["proof_hash"],
        "bootstrap": expected["bootstrap"],
    }


def enforce_handshaken_action(
    packet: Mapping[str, Any] | None,
    *,
    consumer_id: str,
    lease_state: Mapping[str, Any],
    registry_state: Mapping[str, Any],
    repository: str,
    owner_id: str,
    lease_id: str | None,
    now_utc: str,
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
    current_main_sha: str,
    current_head_sha: str,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    handshake = authorize_handshake(
        packet,
        consumer_id=consumer_id,
        observed_main_sha=current_main_sha,
        lease_state=lease_state,
        registry_state=registry_state,
    )
    if handshake.get("allowed") is not True:
        return {
            "result": {
                **handshake,
                "execution_authorized": False,
            },
            "canonical_action": None,
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    outcome = enforce_semantic_action(
        lease_state,
        repository=repository,
        owner_id=owner_id,
        lease_id=lease_id,
        now_utc=now_utc,
        brain_state=brain_state,
        action=action,
        history=history,
        replay_ledger=replay_ledger,
        consumption_ledger=consumption_ledger,
        current_main_sha=current_main_sha,
        current_head_sha=current_head_sha,
        forward_decision=forward_decision,
    )
    result = deepcopy(dict(outcome["result"]))
    result["cross_chat_truth_version"] = VERSION
    result["cross_chat_truth_authorized"] = (
        result.get("allowed") is True
        and handshake.get("cross_chat_truth_authorized") is True
    )
    result["handshake_proof"] = deepcopy(handshake["handshake_proof"])
    result["bootstrap_truth_state_hash"] = handshake["bootstrap"]["truth_state_hash"]
    result["bootstrap_truth_epoch"] = handshake["bootstrap"]["truth_epoch"]
    result["bootstrap_consumer_id"] = str(consumer_id)
    return {
        "result": result,
        "canonical_action": outcome["canonical_action"],
        "replay_ledger": deepcopy(dict(outcome["replay_ledger"])),
        "consumption_ledger": deepcopy(dict(outcome["consumption_ledger"])),
    }


def require_cross_chat_execution_authority(
    result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    raw_action: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    repository: str,
    consumer_id: str,
    observed_main_sha: str,
    lease_state: Mapping[str, Any],
    registry_state: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise CrossChatTruthFailure("execution result must be object")
    if result.get("allowed") is not True:
        raise CrossChatTruthFailure("execution result is not allowed")
    if result.get("cross_chat_truth_authorized") is not True:
        raise CrossChatTruthFailure("cross-chat truth authority missing")

    handshake_validation = validate_handshake_proof(
        result.get("handshake_proof"),
        packet,
        consumer_id=consumer_id,
        observed_main_sha=observed_main_sha,
        lease_state=lease_state,
        registry_state=registry_state,
    )
    try:
        semantic_validation = require_semantic_execution_authority(
            result,
            brain_state,
            raw_action,
            repository=repository,
        )
    except SemanticActionNormalizerFailure as exc:
        raise CrossChatTruthFailure(str(exc)) from exc

    return {
        "status": "GREEN",
        "handshake_proof_hash": handshake_validation["proof_hash"],
        "truth_epoch": handshake_validation["bootstrap"]["truth_epoch"],
        "truth_state_hash": handshake_validation["bootstrap"]["truth_state_hash"],
        "canonical_action_fingerprint": semantic_validation["canonical_action_fingerprint"],
        "global_proof_hash": semantic_validation["global_proof_hash"],
    }


def _sample_registry() -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "owner/repo",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 1,
        "source_main_sha": "1" * 40,
        "entries": {
            "MONSTER_V4_STEP1": {
                "status": "FROZEN",
                "checkpoint_id": "MONSTER_V4_STEP1",
                "source_main_sha": "1" * 40,
                "artifacts": {"a.py": "a" * 40},
            },
            "MONSTER_V4_STEP2": {
                "status": "FROZEN",
                "checkpoint_id": "MONSTER_V4_STEP2",
                "source_main_sha": "1" * 40,
                "artifacts": {"b.py": "b" * 40},
            },
            "MONSTER_V4_STEP3": {
                "status": "FROZEN",
                "checkpoint_id": "MONSTER_V4_STEP3",
                "source_main_sha": "1" * 40,
                "artifacts": {"c.py": "c" * 40},
            },
        },
        "active_thaws": [],
    }
    payload["state_hash"] = _hash(payload)
    return payload


def contract_self_test() -> dict[str, Any]:
    from devsystem.action_ledger_v2 import build_receipt
    from devsystem.distributed_execution_lease_v1 import claim_lease, new_lease_state
    from devsystem.forward_motion_v2 import fingerprint_action
    from devsystem.mandatory_2a_receipt_v1 import new_consumption_ledger
    from devsystem.mandatory_2a_replay_lock_v1 import new_replay_ledger
    from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state

    repo = "owner/repo"
    main_sha = "1" * 40
    head_sha = "2" * 40
    owner = "chat:step4-self-test"
    consumer = "chat:step4-self-test"

    lease0 = new_lease_state(repo)
    claimed = claim_lease(
        lease0,
        owner_id=owner,
        now_utc="2026-09-30T06:00:00Z",
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        expected_revision=lease0["revision"],
        expected_state_hash=lease0["state_hash"],
    )
    lease = claimed["state"]
    lease_id = claimed["result"]["lease_id"]
    registry = _sample_registry()

    packet = build_truth_packet(
        repository=repo,
        truth_epoch=7,
        program_id="MONSTER_V4",
        program_title="MONSTER V4",
        current_step=4,
        total_steps=6,
        step_title="Cross-Chat Truth Handshake",
        step_status="ACTIVE",
        active_checkpoint="MONSTER_V4_STEP4",
        main_sha=main_sha,
        active_head_sha=head_sha,
        lease_state=lease,
        registry_state=registry,
        next_legal_action="EXECUTE_STEP4_SELF_TEST",
        active_pr=42,
        active_run=9001,
    )

    handshake = authorize_handshake(
        packet,
        consumer_id=consumer,
        observed_main_sha=main_sha,
        lease_state=lease,
        registry_state=registry,
    )

    missing = authorize_handshake(
        None,
        consumer_id=consumer,
        observed_main_sha=main_sha,
        lease_state=lease,
        registry_state=registry,
    )
    stale_main = authorize_handshake(
        packet,
        consumer_id=consumer,
        observed_main_sha="3" * 40,
        lease_state=lease,
        registry_state=registry,
    )

    stale_lease = deepcopy(lease)
    stale_lease["revision"] = int(stale_lease["revision"]) + 1
    stale_lease["state_hash"] = _hash({
        key: value for key, value in stale_lease.items() if key != "state_hash"
    })
    stale_lease_result = authorize_handshake(
        packet,
        consumer_id=consumer,
        observed_main_sha=main_sha,
        lease_state=stale_lease,
        registry_state=registry,
    )

    stale_registry = deepcopy(registry)
    stale_registry["revision"] = 2
    stale_registry["state_hash"] = _hash(_without_hash(stale_registry))
    stale_registry_result = authorize_handshake(
        packet,
        consumer_id=consumer,
        observed_main_sha=main_sha,
        lease_state=lease,
        registry_state=stale_registry,
    )

    tampered_packet = deepcopy(packet)
    tampered_packet["next_legal_action"] = "MERGE_WITHOUT_PROOF"
    tamper_result = authorize_handshake(
        tampered_packet,
        consumer_id=consumer,
        observed_main_sha=main_sha,
        lease_state=lease,
        registry_state=registry,
    )

    raw_action = {
        "task_id": "step4-self-test",
        "checkpoint_id": "4",
        "action_type": "merge pull request",
        "target": "PR #42",
        "inputs": {"head_sha": head_sha, "pr_number": "42"},
    }
    canonical = canonicalize_action(raw_action, repository=repo)
    forward = {
        "decision": "AUTHORIZED",
        "receipt": build_receipt({
            "policy_version": 2,
            "task_id": str(canonical["task_id"]),
            "checkpoint_id": str(canonical["checkpoint_id"]),
            "action_fingerprint": fingerprint_action(canonical),
            "root_cause_fingerprint": "r" * 64,
            "evidence_fingerprint": "e" * 64,
            "relevant_input_fingerprint": "i" * 64,
            "decision": "AUTHORIZED",
            "previous_chain_hash": "0" * 64,
            "event_nonce": "step4-cross-chat-self-test",
            "override_event_id": None,
        }),
    }

    brain = build_state(BrainStateInput(
        program_id="step4-self-test",
        program_title="MONSTER V4 Step 4 self-test",
        total_steps=6,
        current_step=4,
        step_title="Cross-Chat Truth Handshake",
        execution_state="ACTIVE",
        repository=repo,
        main_sha=main_sha,
        work_branch="monster-v4-step4",
        observed_head_sha=head_sha,
        next_legal_action="Execute only after truth handshake.",
        completed_steps=(1, 2, 3),
        frozen_steps=(1, 2, 3),
        remaining_steps=(5, 6),
        updated_at_utc="2026-09-30T06:00:00Z",
    ))

    replay0 = new_replay_ledger()
    consume0 = new_consumption_ledger()

    denied_without_packet = enforce_handshaken_action(
        None,
        consumer_id=consumer,
        lease_state=lease,
        registry_state=registry,
        repository=repo,
        owner_id=owner,
        lease_id=lease_id,
        now_utc="2026-09-30T06:01:00Z",
        brain_state=brain,
        action=raw_action,
        history=[],
        replay_ledger=replay0,
        consumption_ledger=consume0,
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        forward_decision=forward,
    )

    allowed = enforce_handshaken_action(
        packet,
        consumer_id=consumer,
        lease_state=lease,
        registry_state=registry,
        repository=repo,
        owner_id=owner,
        lease_id=lease_id,
        now_utc="2026-09-30T06:01:00Z",
        brain_state=brain,
        action=raw_action,
        history=[],
        replay_ledger=new_replay_ledger(),
        consumption_ledger=new_consumption_ledger(),
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        forward_decision=forward,
    )
    final_validation = require_cross_chat_execution_authority(
        allowed["result"],
        brain,
        raw_action,
        packet,
        repository=repo,
        consumer_id=consumer,
        observed_main_sha=main_sha,
        lease_state=lease,
        registry_state=registry,
    )

    stripped = deepcopy(allowed["result"])
    stripped.pop("handshake_proof", None)
    stripped.pop("cross_chat_truth_authorized", None)
    raw_semantic_rejected = False
    try:
        require_cross_chat_execution_authority(
            stripped,
            brain,
            raw_action,
            packet,
            repository=repo,
            consumer_id=consumer,
            observed_main_sha=main_sha,
            lease_state=lease,
            registry_state=registry,
        )
    except CrossChatTruthFailure:
        raw_semantic_rejected = True

    proof_tampered = deepcopy(allowed["result"])
    proof_tampered["handshake_proof"]["payload"]["current_step"] = 99
    proof_tamper_rejected = False
    try:
        require_cross_chat_execution_authority(
            proof_tampered,
            brain,
            raw_action,
            packet,
            repository=repo,
            consumer_id=consumer,
            observed_main_sha=main_sha,
            lease_state=lease,
            registry_state=registry,
        )
    except CrossChatTruthFailure:
        proof_tamper_rejected = True

    view = bootstrap_view(packet)
    result = {
        "status": "GREEN",
        "version": VERSION,
        "valid_handshake_authorized": handshake["decision"] == "HANDSHAKE_AUTHORIZED",
        "missing_packet_blocked": missing["decision"] == "HANDSHAKE_REQUIRED_CONTINUE",
        "stale_main_blocked": stale_main["decision"] == "HANDSHAKE_STALE_CONTINUE",
        "stale_lease_blocked": stale_lease_result["decision"] == "HANDSHAKE_STALE_CONTINUE",
        "stale_registry_blocked": stale_registry_result["decision"] == "HANDSHAKE_STALE_CONTINUE",
        "tampered_packet_blocked": tamper_result["decision"] == "HANDSHAKE_INVALID_CONTINUE",
        "missing_packet_cannot_reach_execution": denied_without_packet["result"]["allowed"] is False,
        "denied_handshake_does_not_consume_replay": denied_without_packet["replay_ledger"] == replay0,
        "denied_handshake_does_not_consume_receipt": denied_without_packet["consumption_ledger"] == consume0,
        "valid_handshake_reaches_semantic_chain": allowed["result"].get("cross_chat_truth_authorized") is True,
        "semantic_chain_preserved": allowed["result"].get("semantic_normalization_authorized") is True,
        "lease_chain_preserved": allowed["result"].get("distributed_lease_authorized") is True,
        "two_a_chain_preserved": allowed["result"].get("certified") is True,
        "raw_semantic_authority_rejected": raw_semantic_rejected,
        "tampered_handshake_proof_rejected": proof_tamper_rejected,
        "final_authority_valid": final_validation["status"] == "GREEN",
        "bootstrap_exposes_current_step": view["step"] == 4 and view["total_steps"] == 6,
        "bootstrap_exposes_main": view["main_sha"] == main_sha,
        "bootstrap_exposes_active_pr_run": view["active_pr"] == 42 and view["active_run"] == 9001,
        "bootstrap_exposes_next_action": view["next_legal_action"] == "EXECUTE_STEP4_SELF_TEST",
        "bootstrap_exposes_frozen_count": view["frozen_checkpoint_count"] == 3,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [key for key, value in result.items() if isinstance(value, bool) and key not in {
        "network_calls", "auto_mutate", "product_runtime_mutation"
    }]
    if not all(result[key] is True for key in required):
        raise CrossChatTruthFailure("cross-chat truth self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise CrossChatTruthFailure("cross-chat truth safety invariant failed")
    return result


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")
    verify = sub.add_parser("verify-packet")
    verify.add_argument("--truth-file", required=True)
    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        print("MONSTER_V4_CROSS_CHAT_TRUTH_HANDSHAKE_V1_GREEN")
        print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
        return 0
    if args.command == "verify-packet":
        packet = validate_truth_packet(_load(args.truth_file))
        print("MONSTER_V4_CROSS_CHAT_TRUTH_PACKET_GREEN")
        print(json.dumps(bootstrap_view(packet), indent=2, sort_keys=True))
        return 0
    raise CrossChatTruthFailure("unsupported command")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CrossChatTruthFailure as exc:
        print(f"MONSTER_V4_CROSS_CHAT_TRUTH_HANDSHAKE_V1_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
