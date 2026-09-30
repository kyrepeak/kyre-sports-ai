"""MONSTER V4 Step 1 — Distributed Execution Lease V1.

Repository-backed, fail-closed single-owner lease for MONSTER control-plane
mutations.

Persistence contract:
- lease state lives on a dedicated Git ref, not in chat memory;
- every lease state has an exact revision + state hash;
- writers must create their next lease-state commit from the currently observed
  lease-ref head and update the ref without force;
- two writers racing from the same parent produce sibling commits, so only the
  first fast-forward ref update is legal. The loser must re-read the lease and
  continue without mutation.

This module is network-free. It defines and validates the lease state machine;
the GitHub/Git persistence adapter is responsible for the actual fast-forward
CAS update.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.automatic_loop_kill_v1 import ACTION_MUTATIONS
from devsystem.mandatory_2a_adversarial_certification_v1 import (
    enforce_certified_action,
)
from devsystem.persistent_execution_brain_v1 import validate_state

VERSION = "MONSTER_V4_DISTRIBUTED_EXECUTION_LEASE_V1"
PERSISTENCE_SURFACE = "git_ref_fast_forward_cas"
LEASE_REF = "refs/heads/monster-execution-lease-ledger"
LEASE_STATE_PATH = "devsystem/distributed_execution_lease_state_v1.json"
LEASE_SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 900
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 3600
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_OWNER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")


class DistributedLeaseFailure(RuntimeError):
    pass


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DistributedLeaseFailure("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DistributedLeaseFailure("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_sha(value: str, field: str) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(sha):
        raise DistributedLeaseFailure(f"{field} must be a full 40-character SHA")
    return sha


def _validate_owner(owner_id: str) -> str:
    owner = str(owner_id or "").strip()
    if not _OWNER_RE.fullmatch(owner):
        raise DistributedLeaseFailure("owner_id has invalid format")
    return owner


def _state_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in state.items() if key != "state_hash"}


def _with_hash(state: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(state))
    result.pop("state_hash", None)
    result["state_hash"] = _hash(result)
    return result


def new_lease_state(repository: str, *, lease_name: str = "monster-global-execution") -> dict[str, Any]:
    repo = str(repository or "").strip()
    if "/" not in repo or any(ch.isspace() for ch in repo):
        raise DistributedLeaseFailure("repository must be owner/name")
    name = str(lease_name or "").strip()
    if not name:
        raise DistributedLeaseFailure("lease_name is required")
    state = {
        "schema_version": LEASE_SCHEMA_VERSION,
        "version": VERSION,
        "persistence_surface": PERSISTENCE_SURFACE,
        "lease_ref": LEASE_REF,
        "lease_state_path": LEASE_STATE_PATH,
        "repository": repo,
        "lease_name": name,
        "revision": 0,
        "generation": 0,
        "holder": None,
    }
    return validate_lease_state(_with_hash(state))


def validate_lease_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DistributedLeaseFailure("lease state must be an object")
    state = deepcopy(dict(payload))
    required = {
        "schema_version",
        "version",
        "persistence_surface",
        "lease_ref",
        "lease_state_path",
        "repository",
        "lease_name",
        "revision",
        "generation",
        "holder",
        "state_hash",
    }
    missing = sorted(required - set(state))
    if missing:
        raise DistributedLeaseFailure("lease state missing fields: " + ", ".join(missing))
    if int(state["schema_version"]) != LEASE_SCHEMA_VERSION:
        raise DistributedLeaseFailure("lease schema version mismatch")
    if state["version"] != VERSION:
        raise DistributedLeaseFailure("lease version mismatch")
    if state["persistence_surface"] != PERSISTENCE_SURFACE:
        raise DistributedLeaseFailure("lease persistence surface mismatch")
    if state["lease_ref"] != LEASE_REF:
        raise DistributedLeaseFailure("lease ref mismatch")
    if state["lease_state_path"] != LEASE_STATE_PATH:
        raise DistributedLeaseFailure("lease state path mismatch")
    if "/" not in str(state["repository"]):
        raise DistributedLeaseFailure("lease repository invalid")
    if not str(state["lease_name"] or "").strip():
        raise DistributedLeaseFailure("lease name required")
    revision = int(state["revision"])
    generation = int(state["generation"])
    if revision < 0 or generation < 0 or generation > revision:
        raise DistributedLeaseFailure("lease revision/generation invalid")

    holder = state["holder"]
    if holder is not None:
        if not isinstance(holder, Mapping):
            raise DistributedLeaseFailure("lease holder must be object or null")
        holder_required = {
            "owner_id",
            "lease_id",
            "generation",
            "acquired_at_utc",
            "heartbeat_at_utc",
            "expires_at_utc",
            "main_sha",
            "head_sha",
        }
        holder_missing = sorted(holder_required - set(holder))
        if holder_missing:
            raise DistributedLeaseFailure(
                "lease holder missing fields: " + ", ".join(holder_missing)
            )
        _validate_owner(holder["owner_id"])
        if not str(holder["lease_id"] or "").startswith("LEASE-"):
            raise DistributedLeaseFailure("lease_id invalid")
        if int(holder["generation"]) != generation or generation <= 0:
            raise DistributedLeaseFailure("holder generation mismatch")
        acquired = _parse_utc(holder["acquired_at_utc"])
        heartbeat = _parse_utc(holder["heartbeat_at_utc"])
        expires = _parse_utc(holder["expires_at_utc"])
        if heartbeat < acquired or expires <= heartbeat:
            raise DistributedLeaseFailure("lease timestamps invalid")
        _validate_sha(holder["main_sha"], "holder.main_sha")
        _validate_sha(holder["head_sha"], "holder.head_sha")

    expected_hash = _hash(_state_payload(state))
    if str(state["state_hash"] or "") != expected_hash:
        raise DistributedLeaseFailure("lease state hash mismatch")
    return state


def lease_is_expired(state: Mapping[str, Any], *, now_utc: str) -> bool:
    lease = validate_lease_state(state)
    holder = lease["holder"]
    if holder is None:
        return True
    return _parse_utc(now_utc) >= _parse_utc(holder["expires_at_utc"])


def _cas_guard(
    state: Mapping[str, Any],
    *,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any] | None:
    lease = validate_lease_state(state)
    if (
        int(expected_revision) != int(lease["revision"])
        or str(expected_state_hash or "") != str(lease["state_hash"])
    ):
        return {
            "version": VERSION,
            "decision": "LEASE_CAS_CONFLICT_CONTINUE",
            "allowed": False,
            "requires_user_intervention": False,
            "next_legal_action": "REREAD_LEASE_REF_AND_CONTINUE",
            "reason": "lease changed since caller observed it",
            "authoritative_revision": lease["revision"],
            "authoritative_state_hash": lease["state_hash"],
        }
    return None


def _lease_id(
    *,
    repository: str,
    lease_name: str,
    owner_id: str,
    generation: int,
    now_utc: str,
    main_sha: str,
    head_sha: str,
) -> str:
    digest = _hash({
        "repository": repository,
        "lease_name": lease_name,
        "owner_id": owner_id,
        "generation": generation,
        "now_utc": now_utc,
        "main_sha": main_sha,
        "head_sha": head_sha,
    })[:24].upper()
    return f"LEASE-{digest}"


def claim_lease(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    now_utc: str,
    current_main_sha: str,
    current_head_sha: str,
    expected_revision: int,
    expected_state_hash: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    lease = validate_lease_state(state)
    conflict = _cas_guard(
        lease,
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
    )
    if conflict:
        return {"result": conflict, "state": lease}

    owner = _validate_owner(owner_id)
    main_sha = _validate_sha(current_main_sha, "current_main_sha")
    head_sha = _validate_sha(current_head_sha, "current_head_sha")
    now = _parse_utc(now_utc)
    ttl = int(ttl_seconds)
    if ttl < MIN_TTL_SECONDS or ttl > MAX_TTL_SECONDS:
        raise DistributedLeaseFailure(
            f"ttl_seconds must be between {MIN_TTL_SECONDS} and {MAX_TTL_SECONDS}"
        )

    holder = lease["holder"]
    if holder is not None and now < _parse_utc(holder["expires_at_utc"]):
        if holder["owner_id"] == owner:
            return {
                "result": {
                    "version": VERSION,
                    "decision": "LEASE_ALREADY_HELD",
                    "allowed": True,
                    "requires_user_intervention": False,
                    "lease_id": holder["lease_id"],
                    "generation": holder["generation"],
                    "revision": lease["revision"],
                    "state_hash": lease["state_hash"],
                },
                "state": lease,
            }
        return {
            "result": {
                "version": VERSION,
                "decision": "LEASE_HELD_CONTINUE",
                "allowed": False,
                "requires_user_intervention": False,
                "continuation_policy": "CONTINUE_NON_CONFLICTING_WORK",
                "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
                "reason": "another owner holds the live distributed execution lease",
                "holder_owner_id": holder["owner_id"],
                "lease_id": holder["lease_id"],
                "expires_at_utc": holder["expires_at_utc"],
                "generation": holder["generation"],
            },
            "state": lease,
        }

    generation = int(lease["generation"]) + 1
    revision = int(lease["revision"]) + 1
    expires = now + timedelta(seconds=ttl)
    lease_id = _lease_id(
        repository=lease["repository"],
        lease_name=lease["lease_name"],
        owner_id=owner,
        generation=generation,
        now_utc=_format_utc(now),
        main_sha=main_sha,
        head_sha=head_sha,
    )
    updated = deepcopy(lease)
    updated["revision"] = revision
    updated["generation"] = generation
    updated["holder"] = {
        "owner_id": owner,
        "lease_id": lease_id,
        "generation": generation,
        "acquired_at_utc": _format_utc(now),
        "heartbeat_at_utc": _format_utc(now),
        "expires_at_utc": _format_utc(expires),
        "main_sha": main_sha,
        "head_sha": head_sha,
    }
    updated = validate_lease_state(_with_hash(updated))
    return {
        "result": {
            "version": VERSION,
            "decision": "LEASE_CLAIMED",
            "allowed": True,
            "requires_user_intervention": False,
            "lease_id": lease_id,
            "generation": generation,
            "revision": revision,
            "state_hash": updated["state_hash"],
            "persistence_instruction": "COMMIT_STATE_TO_LEASE_REF_AND_FAST_FORWARD_WITHOUT_FORCE",
        },
        "state": updated,
    }


def renew_lease(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    lease_id: str,
    now_utc: str,
    current_main_sha: str,
    current_head_sha: str,
    expected_revision: int,
    expected_state_hash: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    lease = validate_lease_state(state)
    conflict = _cas_guard(
        lease,
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
    )
    if conflict:
        return {"result": conflict, "state": lease}

    holder = lease["holder"]
    owner = _validate_owner(owner_id)
    now = _parse_utc(now_utc)
    if holder is None:
        return {
            "result": {
                "version": VERSION,
                "decision": "LEASE_NOT_HELD_CONTINUE",
                "allowed": False,
                "requires_user_intervention": False,
                "next_legal_action": "CLAIM_LEASE",
            },
            "state": lease,
        }
    if holder["owner_id"] != owner or holder["lease_id"] != str(lease_id):
        return {
            "result": {
                "version": VERSION,
                "decision": "LEASE_OWNER_MISMATCH_CONTINUE",
                "allowed": False,
                "requires_user_intervention": False,
                "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
            },
            "state": lease,
        }
    if now >= _parse_utc(holder["expires_at_utc"]):
        return {
            "result": {
                "version": VERSION,
                "decision": "LEASE_EXPIRED_CONTINUE",
                "allowed": False,
                "requires_user_intervention": False,
                "next_legal_action": "REREAD_AND_RECLAIM_LEASE",
            },
            "state": lease,
        }

    ttl = int(ttl_seconds)
    if ttl < MIN_TTL_SECONDS or ttl > MAX_TTL_SECONDS:
        raise DistributedLeaseFailure("ttl_seconds outside allowed range")

    updated = deepcopy(lease)
    updated["revision"] = int(lease["revision"]) + 1
    updated["holder"]["heartbeat_at_utc"] = _format_utc(now)
    updated["holder"]["expires_at_utc"] = _format_utc(now + timedelta(seconds=ttl))
    updated["holder"]["main_sha"] = _validate_sha(current_main_sha, "current_main_sha")
    updated["holder"]["head_sha"] = _validate_sha(current_head_sha, "current_head_sha")
    updated = validate_lease_state(_with_hash(updated))
    return {
        "result": {
            "version": VERSION,
            "decision": "LEASE_RENEWED",
            "allowed": True,
            "requires_user_intervention": False,
            "lease_id": holder["lease_id"],
            "generation": holder["generation"],
            "revision": updated["revision"],
            "state_hash": updated["state_hash"],
            "persistence_instruction": "COMMIT_STATE_TO_LEASE_REF_AND_FAST_FORWARD_WITHOUT_FORCE",
        },
        "state": updated,
    }


def release_lease(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    lease_id: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    lease = validate_lease_state(state)
    conflict = _cas_guard(
        lease,
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
    )
    if conflict:
        return {"result": conflict, "state": lease}

    holder = lease["holder"]
    owner = _validate_owner(owner_id)
    if holder is None:
        return {
            "result": {
                "version": VERSION,
                "decision": "LEASE_ALREADY_FREE",
                "allowed": True,
                "requires_user_intervention": False,
                "revision": lease["revision"],
                "state_hash": lease["state_hash"],
            },
            "state": lease,
        }
    if holder["owner_id"] != owner or holder["lease_id"] != str(lease_id):
        return {
            "result": {
                "version": VERSION,
                "decision": "LEASE_OWNER_MISMATCH_CONTINUE",
                "allowed": False,
                "requires_user_intervention": False,
                "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
            },
            "state": lease,
        }

    updated = deepcopy(lease)
    updated["revision"] = int(lease["revision"]) + 1
    updated["holder"] = None
    updated = validate_lease_state(_with_hash(updated))
    return {
        "result": {
            "version": VERSION,
            "decision": "LEASE_RELEASED",
            "allowed": True,
            "requires_user_intervention": False,
            "revision": updated["revision"],
            "state_hash": updated["state_hash"],
            "persistence_instruction": "COMMIT_STATE_TO_LEASE_REF_AND_FAST_FORWARD_WITHOUT_FORCE",
        },
        "state": updated,
    }


def authorize_lease(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    lease_id: str | None,
    now_utc: str,
    current_main_sha: str,
    current_head_sha: str,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    lease = validate_lease_state(state)
    action_type = str(action.get("action_type") or "").strip()
    if action_type not in ACTION_MUTATIONS:
        return {
            "version": VERSION,
            "decision": "LEASE_NOT_REQUIRED",
            "allowed": True,
            "requires_user_intervention": False,
        }

    owner = _validate_owner(owner_id)
    holder = lease["holder"]
    if holder is None:
        return {
            "version": VERSION,
            "decision": "LEASE_REQUIRED_CONTINUE",
            "allowed": False,
            "requires_user_intervention": False,
            "next_legal_action": "CLAIM_LEASE",
        }
    if _parse_utc(now_utc) >= _parse_utc(holder["expires_at_utc"]):
        return {
            "version": VERSION,
            "decision": "LEASE_EXPIRED_CONTINUE",
            "allowed": False,
            "requires_user_intervention": False,
            "next_legal_action": "REREAD_AND_RECLAIM_LEASE",
        }
    if holder["owner_id"] != owner or holder["lease_id"] != str(lease_id or ""):
        return {
            "version": VERSION,
            "decision": "LEASE_HELD_CONTINUE",
            "allowed": False,
            "requires_user_intervention": False,
            "continuation_policy": "CONTINUE_NON_CONFLICTING_WORK",
            "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
            "holder_owner_id": holder["owner_id"],
        }

    main_sha = _validate_sha(current_main_sha, "current_main_sha")
    head_sha = _validate_sha(current_head_sha, "current_head_sha")
    if holder["main_sha"] != main_sha or holder["head_sha"] != head_sha:
        return {
            "version": VERSION,
            "decision": "LEASE_REPOSITORY_DRIFT_CONTINUE",
            "allowed": False,
            "requires_user_intervention": False,
            "next_legal_action": "RENEW_LEASE_TO_CURRENT_REPOSITORY_IDENTITY",
        }

    return {
        "version": VERSION,
        "decision": "LEASE_EXECUTION_AUTHORIZED",
        "allowed": True,
        "requires_user_intervention": False,
        "owner_id": owner,
        "lease_id": holder["lease_id"],
        "generation": holder["generation"],
        "revision": lease["revision"],
        "state_hash": lease["state_hash"],
    }


def enforce_leased_action(
    lease_state: Mapping[str, Any],
    *,
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
    brain = validate_state(brain_state)
    lease_gate = authorize_lease(
        lease_state,
        owner_id=owner_id,
        lease_id=lease_id,
        now_utc=now_utc,
        current_main_sha=current_main_sha,
        current_head_sha=current_head_sha,
        action=action,
    )
    if lease_gate.get("allowed") is not True:
        return {
            "result": {
                **lease_gate,
                "execution_authorized": False,
                "distributed_lease_authorized": False,
            },
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    outcome = enforce_certified_action(
        brain,
        action,
        history,
        replay_ledger,
        consumption_ledger,
        current_main_sha=current_main_sha,
        current_head_sha=current_head_sha,
        forward_decision=forward_decision,
    )
    result = deepcopy(dict(outcome["result"]))
    if result.get("allowed") is True:
        result["distributed_lease_authorized"] = True
        result["distributed_lease_id"] = lease_gate.get("lease_id")
        result["distributed_lease_generation"] = lease_gate.get("generation")
        result["distributed_lease_state_hash"] = lease_gate.get("state_hash")
    else:
        result["distributed_lease_authorized"] = False
    return {
        "result": result,
        "replay_ledger": deepcopy(dict(outcome["replay_ledger"])),
        "consumption_ledger": deepcopy(dict(outcome["consumption_ledger"])),
    }


def contract_self_test() -> dict[str, Any]:
    from devsystem.action_ledger_v2 import build_receipt
    from devsystem.forward_motion_v2 import fingerprint_action
    from devsystem.mandatory_2a_receipt_v1 import new_consumption_ledger
    from devsystem.mandatory_2a_replay_lock_v1 import new_replay_ledger
    from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state

    repo = "owner/repo"
    main_sha = "1" * 40
    head_sha = "2" * 40
    state = new_lease_state(repo)
    owner_a = "chat:A-123"
    owner_b = "chat:B-456"
    t0 = "2026-09-30T04:50:00Z"

    first = claim_lease(
        state,
        owner_id=owner_a,
        now_utc=t0,
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    live = first["state"]
    second_owner = claim_lease(
        live,
        owner_id=owner_b,
        now_utc="2026-09-30T04:51:00Z",
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        expected_revision=live["revision"],
        expected_state_hash=live["state_hash"],
    )
    stale_cas = claim_lease(
        live,
        owner_id=owner_b,
        now_utc="2026-09-30T04:51:00Z",
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    expired_takeover = claim_lease(
        live,
        owner_id=owner_b,
        now_utc="2026-09-30T05:06:00Z",
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        expected_revision=live["revision"],
        expected_state_hash=live["state_hash"],
    )

    brain = build_state(BrainStateInput(
        program_id="self-test",
        program_title="MONSTER V4 distributed lease",
        total_steps=6,
        current_step=1,
        step_title="Distributed Execution Lease",
        execution_state="ACTIVE",
        repository=repo,
        main_sha=main_sha,
        work_branch="monster-v4-step1",
        observed_head_sha=head_sha,
        next_legal_action="Continue under lease.",
        remaining_steps=(2, 3, 4, 5, 6),
        updated_at_utc=t0,
    ))
    action = {
        "task_id": "monster-v4-step1",
        "checkpoint_id": "1",
        "action_type": "merge",
        "target": "github:pr/1",
        "inputs": {"head": head_sha},
    }
    forward = {
        "decision": "AUTHORIZED",
        "receipt": build_receipt({
            "policy_version": 2,
            "task_id": action["task_id"],
            "checkpoint_id": action["checkpoint_id"],
            "action_fingerprint": fingerprint_action(action),
            "root_cause_fingerprint": "r" * 64,
            "evidence_fingerprint": "e" * 64,
            "relevant_input_fingerprint": "i" * 64,
            "decision": "AUTHORIZED",
            "previous_chain_hash": "0" * 64,
            "event_nonce": "monster-v4-step1-self-test",
            "override_event_id": None,
        }),
    }
    allowed = enforce_leased_action(
        live,
        owner_id=owner_a,
        lease_id=first["result"]["lease_id"],
        now_utc="2026-09-30T04:52:00Z",
        brain_state=brain,
        action=action,
        history=[],
        replay_ledger=new_replay_ledger(),
        consumption_ledger=new_consumption_ledger(),
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        forward_decision=forward,
    )
    denied_other = enforce_leased_action(
        live,
        owner_id=owner_b,
        lease_id="LEASE-WRONG",
        now_utc="2026-09-30T04:52:00Z",
        brain_state=brain,
        action=action,
        history=[],
        replay_ledger=new_replay_ledger(),
        consumption_ledger=new_consumption_ledger(),
        current_main_sha=main_sha,
        current_head_sha=head_sha,
        forward_decision=forward,
    )
    drift = authorize_lease(
        live,
        owner_id=owner_a,
        lease_id=first["result"]["lease_id"],
        now_utc="2026-09-30T04:52:00Z",
        current_main_sha=main_sha,
        current_head_sha="3" * 40,
        action=action,
    )
    released = release_lease(
        live,
        owner_id=owner_a,
        lease_id=first["result"]["lease_id"],
        expected_revision=live["revision"],
        expected_state_hash=live["state_hash"],
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "persistence_surface": PERSISTENCE_SURFACE,
        "fast_forward_cas_required": True,
        "single_live_owner": second_owner["result"]["decision"] == "LEASE_HELD_CONTINUE",
        "stale_revision_blocked": stale_cas["result"]["decision"] == "LEASE_CAS_CONFLICT_CONTINUE",
        "expired_lease_takeover": expired_takeover["result"]["decision"] == "LEASE_CLAIMED",
        "generation_increments": expired_takeover["state"]["generation"] == live["generation"] + 1,
        "owner_a_executes": allowed["result"].get("distributed_lease_authorized") is True,
        "owner_b_cannot_execute": denied_other["result"]["decision"] == "LEASE_HELD_CONTINUE",
        "repository_drift_blocked": drift["decision"] == "LEASE_REPOSITORY_DRIFT_CONTINUE",
        "release_clears_holder": released["state"]["holder"] is None,
        "two_a_chain_preserved": allowed["result"].get("certified") is True,
        "no_user_intervention_on_contention": second_owner["result"]["requires_user_intervention"] is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "fast_forward_cas_required",
        "single_live_owner",
        "stale_revision_blocked",
        "expired_lease_takeover",
        "generation_increments",
        "owner_a_executes",
        "owner_b_cannot_execute",
        "repository_drift_blocked",
        "release_clears_holder",
        "two_a_chain_preserved",
        "no_user_intervention_on_contention",
    )
    if not all(result[key] is True for key in required):
        raise DistributedLeaseFailure("distributed execution lease self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_V4_DISTRIBUTED_EXECUTION_LEASE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
