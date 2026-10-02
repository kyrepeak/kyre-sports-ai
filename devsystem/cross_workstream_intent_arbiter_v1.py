"""MONSTER V8 Step 3 — Cross-Workstream Intent Arbiter V1.

The intent arbiter is the control-plane layer that runs BEFORE branch, PR, CI,
or lease creation. It prevents two chats/workstreams from independently
starting the same mission or unsafe overlapping missions.

Core outcomes:
- ALLOW_NEW_INTENT: a new canonical workstream may proceed to downstream gates.
- JOIN_EXISTING_INTENT: semantic duplicate; join the existing workstream.
- WAIT_ON_CONFLICTING_INTENT: persist a durable waiting intent, create nothing.
- BLOCK_STALE_INTENT_BASE: rebase/replan before starting work.

Conflict semantics reuse the frozen V7 shard-aware scope model. Duplicate
semantics intentionally exclude owner/chat identity, so the same normalized
mission + base + scope collapses to one canonical workstream.

This module performs no network calls and grants no mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.detached_execution_continuation_v1 import (
    VERSION as DETACHED_CONTINUATION_VERSION,
)
from devsystem.pre_mutation_blast_radius_simulator_v1 import (
    VERSION as BLAST_SIMULATOR_VERSION,
)
from devsystem.scope_aware_execution_lease_v1 import (
    VERSION as SCOPE_LEASE_VERSION,
    build_scope,
)
from devsystem.shared_resource_lease_sharding_v1 import (
    VERSION as SHARDING_VERSION,
    shard_aware_scopes_conflict,
)
from devsystem.transactional_rollback_engine_v1 import (
    VERSION as ROLLBACK_VERSION,
)

VERSION = "MONSTER_V8_CROSS_WORKSTREAM_INTENT_ARBITER_V1"
INTENT_REF = "refs/heads/monster-workstream-intent-registry"
INTENT_PATH = "devsystem/cross_workstream_intent_registry_state_v1.json"

REQUIRED_DETACHED_CONTINUATION_VERSION = "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_V1"
REQUIRED_BLAST_SIMULATOR_VERSION = "MONSTER_V8_PRE_MUTATION_BLAST_RADIUS_SIMULATOR_V1"
REQUIRED_SCOPE_LEASE_VERSION = "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_V1"
REQUIRED_SHARDING_VERSION = "MONSTER_V7_SHARED_RESOURCE_LEASE_SHARDING_V1"
REQUIRED_ROLLBACK_VERSION = "MONSTER_V8_TRANSACTIONAL_ROLLBACK_ENGINE_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{2,255}$")
_STATUSES = {"ACTIVE", "WAITING", "COMPLETE", "EXPIRED"}


class CrossWorkstreamIntentFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(value))
    out.pop("state_hash", None)
    return out


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CrossWorkstreamIntentFailure(f"{field} is required")
    return text


def _identifier(value: Any, field: str) -> str:
    text = _nonempty(value, field)
    if not _ID_RE.fullmatch(text):
        raise CrossWorkstreamIntentFailure(f"{field} contains unsupported characters")
    return text


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise CrossWorkstreamIntentFailure(f"{field} must be a full git SHA")
    return text


def _utc(value: Any) -> datetime:
    text = _nonempty(value, "timestamp").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CrossWorkstreamIntentFailure("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _mission_key(value: Any) -> str:
    text = _nonempty(value, "mission").lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", text)
    normalized = " ".join(normalized.split())
    if len(normalized) < 3:
        raise CrossWorkstreamIntentFailure("mission is too short")
    return normalized


def _ttl(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise CrossWorkstreamIntentFailure("ttl_seconds must be an integer") from exc
    if seconds < 60 or seconds > 86400:
        raise CrossWorkstreamIntentFailure("ttl_seconds must be between 60 and 86400")
    return seconds


def _participant(owner_id: Any, workstream_id: Any) -> dict[str, str]:
    return {
        "owner_id": _identifier(owner_id, "owner_id"),
        "workstream_id": _identifier(workstream_id, "workstream_id"),
    }


def _normalize_participants(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise CrossWorkstreamIntentFailure("participants must be a non-empty list")
    participants = [_participant(x.get("owner_id"), x.get("workstream_id")) for x in raw]
    keys = [(x["owner_id"], x["workstream_id"]) for x in participants]
    if len(keys) != len(set(keys)):
        raise CrossWorkstreamIntentFailure("duplicate intent participant")
    return sorted(participants, key=lambda x: (x["owner_id"], x["workstream_id"]))


def _semantic_fingerprint(
    *,
    mission_key: str,
    base_sha: str,
    scope: Mapping[str, Any],
) -> str:
    return _hash(
        {
            "mission_key": mission_key,
            "base_sha": base_sha,
            "scope": build_scope(**dict(scope)),
        }
    )


def build_intent_candidate(
    *,
    owner_id: str,
    workstream_id: str,
    mission: str,
    base_sha: str,
    scope: Mapping[str, Any],
    ttl_seconds: int = 1800,
) -> dict[str, Any]:
    owner = _identifier(owner_id, "owner_id")
    workstream = _identifier(workstream_id, "workstream_id")
    mission_text = _nonempty(mission, "mission")
    key = _mission_key(mission_text)
    base = _sha(base_sha, "base_sha")
    normalized_scope = build_scope(**dict(scope))
    ttl = _ttl(ttl_seconds)
    fingerprint = _semantic_fingerprint(
        mission_key=key,
        base_sha=base,
        scope=normalized_scope,
    )
    return {
        "owner_id": owner,
        "workstream_id": workstream,
        "mission": mission_text,
        "mission_key": key,
        "base_sha": base,
        "scope": normalized_scope,
        "ttl_seconds": ttl,
        "semantic_fingerprint": fingerprint,
    }


def _validate_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CrossWorkstreamIntentFailure("candidate must be an object")
    candidate = build_intent_candidate(
        owner_id=raw.get("owner_id"),
        workstream_id=raw.get("workstream_id"),
        mission=raw.get("mission"),
        base_sha=raw.get("base_sha"),
        scope=raw.get("scope") or {},
        ttl_seconds=raw.get("ttl_seconds", 1800),
    )
    supplied = str(raw.get("semantic_fingerprint") or "").strip().lower()
    if supplied and supplied != candidate["semantic_fingerprint"]:
        raise CrossWorkstreamIntentFailure("candidate semantic fingerprint mismatch")
    return candidate


def _validate_intent(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CrossWorkstreamIntentFailure("intent must be an object")
    status = _nonempty(raw.get("status"), "intent status").upper()
    if status not in _STATUSES:
        raise CrossWorkstreamIntentFailure("unsupported intent status")
    sequence = int(raw.get("sequence", 0))
    if sequence <= 0:
        raise CrossWorkstreamIntentFailure("intent sequence must be positive")
    mission = _nonempty(raw.get("mission"), "intent mission")
    mission_key = _mission_key(mission)
    if mission_key != raw.get("mission_key"):
        raise CrossWorkstreamIntentFailure("intent mission_key mismatch")
    base = _sha(raw.get("base_sha"), "intent base_sha")
    scope = build_scope(**dict(raw.get("scope") or {}))
    fingerprint = _semantic_fingerprint(
        mission_key=mission_key,
        base_sha=base,
        scope=scope,
    )
    if fingerprint != str(raw.get("semantic_fingerprint") or "").lower():
        raise CrossWorkstreamIntentFailure("intent semantic fingerprint mismatch")
    intent_id = _identifier(raw.get("intent_id"), "intent_id")
    expected_id = "intent-" + fingerprint[:24]
    if intent_id != expected_id:
        raise CrossWorkstreamIntentFailure("intent_id mismatch")
    leader_owner = _identifier(raw.get("leader_owner_id"), "leader_owner_id")
    canonical_workstream = _identifier(
        raw.get("canonical_workstream_id"),
        "canonical_workstream_id",
    )
    participants = _normalize_participants(raw.get("participants"))
    if not any(
        p["owner_id"] == leader_owner
        and p["workstream_id"] == canonical_workstream
        for p in participants
    ):
        raise CrossWorkstreamIntentFailure("leader/canonical workstream must be a participant")
    submitted = _fmt(_utc(raw.get("submitted_at_utc")))
    updated = _fmt(_utc(raw.get("updated_at_utc")))
    expires = _fmt(_utc(raw.get("expires_at_utc")))
    if _utc(expires) <= _utc(submitted):
        raise CrossWorkstreamIntentFailure("intent expiry must follow submission")
    blocked_by = sorted(
        {_identifier(x, "blocked_by_intent_id") for x in (raw.get("blocked_by") or [])}
    )
    if intent_id in blocked_by:
        raise CrossWorkstreamIntentFailure("intent cannot block itself")
    return {
        "intent_id": intent_id,
        "sequence": sequence,
        "status": status,
        "mission": mission,
        "mission_key": mission_key,
        "semantic_fingerprint": fingerprint,
        "base_sha": base,
        "scope": scope,
        "leader_owner_id": leader_owner,
        "canonical_workstream_id": canonical_workstream,
        "participants": participants,
        "blocked_by": blocked_by,
        "submitted_at_utc": submitted,
        "updated_at_utc": updated,
        "expires_at_utc": expires,
    }


def _normalized_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    state = deepcopy(dict(payload))
    intents = [_validate_intent(x) for x in (state.get("intents") or [])]
    intents.sort(key=lambda x: (x["sequence"], x["intent_id"]))
    state["intents"] = intents
    return state


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CrossWorkstreamIntentFailure("intent registry state must be an object")
    state = _normalized_state(payload)
    if int(state.get("schema_version", 0)) != 1 or state.get("version") != VERSION:
        raise CrossWorkstreamIntentFailure("intent registry version/schema mismatch")
    repository = str(state.get("repository") or "").strip().lower()
    if "/" not in repository:
        raise CrossWorkstreamIntentFailure("repository invalid")
    if state.get("intent_ref") != INTENT_REF or state.get("intent_state_path") != INTENT_PATH:
        raise CrossWorkstreamIntentFailure("intent registry persistence identity mismatch")
    if int(state.get("revision", -1)) < 0 or int(state.get("generation", -1)) < 0:
        raise CrossWorkstreamIntentFailure("revision/generation invalid")
    next_sequence = int(state.get("next_sequence", 0))
    if next_sequence <= 0:
        raise CrossWorkstreamIntentFailure("next_sequence must be positive")
    sequences = [x["sequence"] for x in state["intents"]]
    if len(sequences) != len(set(sequences)):
        raise CrossWorkstreamIntentFailure("duplicate intent sequence")
    if sequences and next_sequence <= max(sequences):
        raise CrossWorkstreamIntentFailure("next_sequence must exceed all assigned sequences")
    supplied = str(state.get("state_hash") or "").strip().lower()
    if not _HASH64.fullmatch(supplied):
        raise CrossWorkstreamIntentFailure("state_hash invalid")
    expected = _hash(_without_hash(state))
    if supplied != expected:
        raise CrossWorkstreamIntentFailure("intent registry state hash mismatch")
    return state


def _seal(payload: Mapping[str, Any]) -> dict[str, Any]:
    state = _normalized_state(payload)
    state.pop("state_hash", None)
    state["state_hash"] = _hash(state)
    return validate_state(state)


def new_state(repository: str) -> dict[str, Any]:
    repo = str(repository or "").strip().lower()
    if "/" not in repo:
        raise CrossWorkstreamIntentFailure("repository must be owner/name")
    return _seal(
        {
            "schema_version": 1,
            "version": VERSION,
            "repository": repo,
            "intent_ref": INTENT_REF,
            "intent_state_path": INTENT_PATH,
            "revision": 0,
            "generation": 0,
            "next_sequence": 1,
            "intents": [],
        }
    )


def _cas(
    state: Mapping[str, Any],
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any] | None:
    if (
        int(state["revision"]) != int(expected_revision)
        or str(state["state_hash"]) != str(expected_state_hash)
    ):
        return {
            "decision": "INTENT_REGISTRY_STALE_CAS",
            "allowed": False,
            "branch_creation_allowed": False,
            "pr_creation_allowed": False,
            "lease_request_allowed": False,
            "next_legal_action": "REREAD_INTENT_REGISTRY",
        }
    return None


def _is_live(intent: Mapping[str, Any], now: datetime) -> bool:
    return (
        intent["status"] in {"ACTIVE", "WAITING"}
        and now < _utc(intent["expires_at_utc"])
    )


def _active_live(intents: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    return [x for x in intents if x["status"] == "ACTIVE" and _is_live(x, now)]


def _conflicting_active(
    scope: Mapping[str, Any],
    intents: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for intent in _active_live(intents, now):
        conflict, reasons = shard_aware_scopes_conflict(scope, intent["scope"])
        if conflict:
            conflicts.append(
                {
                    "intent_id": intent["intent_id"],
                    "canonical_workstream_id": intent["canonical_workstream_id"],
                    "leader_owner_id": intent["leader_owner_id"],
                    "conflict_reasons": reasons,
                    "sequence": intent["sequence"],
                }
            )
    return sorted(conflicts, key=lambda x: (x["sequence"], x["intent_id"]))


def _reconcile_expired_and_promote(
    intents: list[dict[str, Any]],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[str], list[str], bool]:
    rows = deepcopy(intents)
    expired_ids: list[str] = []
    promoted_ids: list[str] = []
    changed = False

    for row in rows:
        if row["status"] in {"ACTIVE", "WAITING"} and now >= _utc(row["expires_at_utc"]):
            row["status"] = "EXPIRED"
            row["blocked_by"] = []
            row["updated_at_utc"] = _fmt(now)
            expired_ids.append(row["intent_id"])
            changed = True

    active = [
        row for row in rows
        if row["status"] == "ACTIVE" and now < _utc(row["expires_at_utc"])
    ]
    waiting = sorted(
        [
            row for row in rows
            if row["status"] == "WAITING" and now < _utc(row["expires_at_utc"])
        ],
        key=lambda x: (x["sequence"], x["intent_id"]),
    )
    for row in waiting:
        blockers: list[str] = []
        for holder in active:
            conflict, _ = shard_aware_scopes_conflict(row["scope"], holder["scope"])
            if conflict:
                blockers.append(holder["intent_id"])
        blockers = sorted(set(blockers))
        if blockers:
            if blockers != row["blocked_by"]:
                row["blocked_by"] = blockers
                row["updated_at_utc"] = _fmt(now)
                changed = True
            continue
        row["status"] = "ACTIVE"
        row["blocked_by"] = []
        row["updated_at_utc"] = _fmt(now)
        active.append(row)
        promoted_ids.append(row["intent_id"])
        changed = True

    rows.sort(key=lambda x: (x["sequence"], x["intent_id"]))
    return rows, expired_ids, promoted_ids, changed


def _commit_state(
    state: Mapping[str, Any],
    *,
    intents: list[dict[str, Any]],
    next_sequence: int | None = None,
) -> dict[str, Any]:
    updated = deepcopy(dict(state))
    updated["revision"] = int(updated["revision"]) + 1
    updated["generation"] = int(updated["generation"]) + 1
    updated["intents"] = intents
    if next_sequence is not None:
        updated["next_sequence"] = next_sequence
    return _seal(updated)


def submit_intent(
    state: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    current_main_sha: str,
    now_utc: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}

    if (
        DETACHED_CONTINUATION_VERSION != REQUIRED_DETACHED_CONTINUATION_VERSION
        or BLAST_SIMULATOR_VERSION != REQUIRED_BLAST_SIMULATOR_VERSION
        or SCOPE_LEASE_VERSION != REQUIRED_SCOPE_LEASE_VERSION
        or SHARDING_VERSION != REQUIRED_SHARDING_VERSION
        or ROLLBACK_VERSION != REQUIRED_ROLLBACK_VERSION
    ):
        raise CrossWorkstreamIntentFailure("frozen dependency version mismatch")

    item = _validate_candidate(candidate)
    now = _utc(now_utc)
    main_sha = _sha(current_main_sha, "current_main_sha")
    if item["base_sha"] != main_sha:
        return {
            "result": {
                "decision": "BLOCK_STALE_INTENT_BASE",
                "allowed": False,
                "expected_base_sha": main_sha,
                "observed_base_sha": item["base_sha"],
                "branch_creation_allowed": False,
                "pr_creation_allowed": False,
                "lease_request_allowed": False,
                "next_legal_action": "REFRESH_HEAD_AND_REBUILD_INTENT",
            },
            "state": current,
        }

    intents, expired_ids, promoted_ids, reconciled = _reconcile_expired_and_promote(
        current["intents"], now
    )

    duplicate = next(
        (
            row for row in intents
            if _is_live(row, now)
            and row["semantic_fingerprint"] == item["semantic_fingerprint"]
        ),
        None,
    )
    if duplicate is not None:
        participant = _participant(item["owner_id"], item["workstream_id"])
        already = participant in duplicate["participants"]
        if not already:
            duplicate["participants"].append(participant)
            duplicate["participants"].sort(
                key=lambda x: (x["owner_id"], x["workstream_id"])
            )
            duplicate["updated_at_utc"] = _fmt(now)
        if reconciled or not already:
            updated = _commit_state(current, intents=intents)
        else:
            updated = current
        decision = (
            "INTENT_ALREADY_REGISTERED"
            if already
            else (
                "JOIN_EXISTING_INTENT"
                if duplicate["status"] == "ACTIVE"
                else "JOIN_WAITING_INTENT"
            )
        )
        return {
            "result": {
                "decision": decision,
                "allowed": False,
                "canonical_intent_id": duplicate["intent_id"],
                "canonical_workstream_id": duplicate["canonical_workstream_id"],
                "leader_owner_id": duplicate["leader_owner_id"],
                "intent_status": duplicate["status"],
                "expired_intent_ids": expired_ids,
                "promoted_intent_ids": promoted_ids,
                "branch_creation_allowed": False,
                "pr_creation_allowed": False,
                "lease_request_allowed": False,
                "join_existing_continuation": duplicate["status"] == "ACTIVE",
                "next_legal_action": (
                    "HANDOFF_OR_JOIN_EXISTING_CONTINUATION"
                    if duplicate["status"] == "ACTIVE"
                    else "WAIT_FOR_INTENT_PROMOTION_EVENT"
                ),
            },
            "state": updated,
        }

    conflicts = _conflicting_active(item["scope"], intents, now)
    sequence = int(current["next_sequence"])
    intent_id = "intent-" + item["semantic_fingerprint"][:24]
    record = {
        "intent_id": intent_id,
        "sequence": sequence,
        "status": "WAITING" if conflicts else "ACTIVE",
        "mission": item["mission"],
        "mission_key": item["mission_key"],
        "semantic_fingerprint": item["semantic_fingerprint"],
        "base_sha": item["base_sha"],
        "scope": item["scope"],
        "leader_owner_id": item["owner_id"],
        "canonical_workstream_id": item["workstream_id"],
        "participants": [_participant(item["owner_id"], item["workstream_id"])],
        "blocked_by": [x["intent_id"] for x in conflicts],
        "submitted_at_utc": _fmt(now),
        "updated_at_utc": _fmt(now),
        "expires_at_utc": _fmt(now + timedelta(seconds=item["ttl_seconds"])),
    }
    intents.append(record)
    intents.sort(key=lambda x: (x["sequence"], x["intent_id"]))
    updated = _commit_state(
        current,
        intents=intents,
        next_sequence=sequence + 1,
    )

    if conflicts:
        return {
            "result": {
                "decision": "WAIT_ON_CONFLICTING_INTENT",
                "allowed": False,
                "intent_id": intent_id,
                "wait_sequence": sequence,
                "blocked_by": conflicts,
                "expired_intent_ids": expired_ids,
                "promoted_intent_ids": promoted_ids,
                "branch_creation_allowed": False,
                "pr_creation_allowed": False,
                "lease_request_allowed": False,
                "next_legal_action": "WAIT_FOR_INTENT_RELEASE_EVENT",
            },
            "state": updated,
        }

    return {
        "result": {
            "decision": "ALLOW_NEW_INTENT",
            "allowed": True,
            "intent_id": intent_id,
            "canonical_workstream_id": item["workstream_id"],
            "expired_intent_ids": expired_ids,
            "promoted_intent_ids": promoted_ids,
            "branch_creation_allowed": True,
            "pr_creation_allowed": True,
            "lease_request_allowed": True,
            "next_legal_action": "RUN_PRE_MUTATION_BLAST_RADIUS_SIMULATION",
        },
        "state": updated,
    }


def complete_intent(
    state: Mapping[str, Any],
    *,
    intent_id: str,
    owner_id: str,
    now_utc: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}
    iid = _identifier(intent_id, "intent_id")
    owner = _identifier(owner_id, "owner_id")
    now = _utc(now_utc)
    intents, expired_ids, _, _ = _reconcile_expired_and_promote(
        current["intents"], now
    )
    target = next((x for x in intents if x["intent_id"] == iid), None)
    if target is None:
        raise CrossWorkstreamIntentFailure("intent not found")
    if target["leader_owner_id"] != owner:
        return {
            "result": {
                "decision": "INTENT_COMPLETION_OWNER_MISMATCH",
                "allowed": False,
                "next_legal_action": "HANDOFF_EXISTING_CONTINUATION_OR_WAIT_FOR_LEADER",
            },
            "state": current,
        }
    if target["status"] in {"COMPLETE", "EXPIRED"}:
        return {
            "result": {
                "decision": "INTENT_ALREADY_TERMINAL",
                "allowed": False,
                "intent_id": iid,
                "status": target["status"],
                "next_legal_action": "NONE",
            },
            "state": current,
        }

    target["status"] = "COMPLETE"
    target["blocked_by"] = []
    target["updated_at_utc"] = _fmt(now)
    reconciled, expired_after, promoted_ids, _ = _reconcile_expired_and_promote(
        intents, now
    )
    updated = _commit_state(current, intents=reconciled)
    return {
        "result": {
            "decision": "INTENT_COMPLETED",
            "allowed": True,
            "intent_id": iid,
            "expired_intent_ids": sorted(set(expired_ids + expired_after)),
            "promoted_intent_ids": promoted_ids,
            "next_legal_action": (
                "RESUME_PROMOTED_INTENTS"
                if promoted_ids
                else "NONE"
            ),
        },
        "state": updated,
    }


def reconcile_expired_intents(
    state: Mapping[str, Any],
    *,
    now_utc: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    stale = _cas(current, expected_revision, expected_state_hash)
    if stale:
        return {"result": stale, "state": current}
    now = _utc(now_utc)
    intents, expired_ids, promoted_ids, changed = _reconcile_expired_and_promote(
        current["intents"], now
    )
    updated = _commit_state(current, intents=intents) if changed else current
    return {
        "result": {
            "decision": (
                "INTENT_REGISTRY_RECONCILED"
                if changed
                else "INTENT_REGISTRY_NO_CHANGE"
            ),
            "allowed": True,
            "expired_intent_ids": expired_ids,
            "promoted_intent_ids": promoted_ids,
            "next_legal_action": (
                "RESUME_PROMOTED_INTENTS"
                if promoted_ids
                else "NONE"
            ),
        },
        "state": updated,
    }


def contract_self_test() -> dict[str, Any]:
    from devsystem.shared_resource_lease_sharding_v1 import shard_resource

    repo = "owner/repo"
    head = "a" * 40
    state = new_state(repo)

    cfb_scope = build_scope(
        write_paths=["cfb/page.py"],
        dependency_tokens=["sport:cfb"],
        shared_resources=[
            shard_resource("workflow:shared-ci", {"domain": "cfb"})
        ],
        resource_identity={"main:base": head},
    )
    cfb = build_intent_candidate(
        owner_id="chat:cfb",
        workstream_id="ws:cfb-top-picks",
        mission="Repair CFB Top Picks",
        base_sha=head,
        scope=cfb_scope,
    )
    first = submit_intent(
        state,
        candidate=cfb,
        current_main_sha=head,
        now_utc="2026-10-02T04:00:00Z",
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )

    duplicate = build_intent_candidate(
        owner_id="chat:cfb-2",
        workstream_id="ws:duplicate-cfb",
        mission="repair--CFB top picks!!!",
        base_sha=head,
        scope=cfb_scope,
    )
    joined = submit_intent(
        first["state"],
        candidate=duplicate,
        current_main_sha=head,
        now_utc="2026-10-02T04:00:10Z",
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )

    conflict = build_intent_candidate(
        owner_id="chat:cfb-3",
        workstream_id="ws:cfb-other",
        mission="Different CFB repair",
        base_sha=head,
        scope=cfb_scope,
    )
    waiting = submit_intent(
        joined["state"],
        candidate=conflict,
        current_main_sha=head,
        now_utc="2026-10-02T04:00:20Z",
        expected_revision=joined["state"]["revision"],
        expected_state_hash=joined["state"]["state_hash"],
    )

    wnba_scope = build_scope(
        write_paths=["wnba/page.py"],
        dependency_tokens=["sport:wnba"],
        shared_resources=[
            shard_resource("workflow:shared-ci", {"domain": "wnba"})
        ],
        resource_identity={"main:base": head},
    )
    wnba = build_intent_candidate(
        owner_id="chat:wnba",
        workstream_id="ws:wnba-speed",
        mission="Improve WNBA speed",
        base_sha=head,
        scope=wnba_scope,
    )
    parallel = submit_intent(
        waiting["state"],
        candidate=wnba,
        current_main_sha=head,
        now_utc="2026-10-02T04:00:30Z",
        expected_revision=waiting["state"]["revision"],
        expected_state_hash=waiting["state"]["state_hash"],
    )

    completed = complete_intent(
        parallel["state"],
        intent_id=first["result"]["intent_id"],
        owner_id="chat:cfb",
        now_utc="2026-10-02T04:01:00Z",
        expected_revision=parallel["state"]["revision"],
        expected_state_hash=parallel["state"]["state_hash"],
    )

    stale_candidate = build_intent_candidate(
        owner_id="chat:stale",
        workstream_id="ws:stale",
        mission="Stale mission",
        base_sha="b" * 40,
        scope=build_scope(write_paths=["other.py"]),
    )
    stale = submit_intent(
        completed["state"],
        candidate=stale_candidate,
        current_main_sha=head,
        now_utc="2026-10-02T04:01:10Z",
        expected_revision=completed["state"]["revision"],
        expected_state_hash=completed["state"]["state_hash"],
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "detached_continuation_version_bound": (
            DETACHED_CONTINUATION_VERSION
            == REQUIRED_DETACHED_CONTINUATION_VERSION
        ),
        "blast_simulator_version_bound": (
            BLAST_SIMULATOR_VERSION == REQUIRED_BLAST_SIMULATOR_VERSION
        ),
        "scope_lease_version_bound": (
            SCOPE_LEASE_VERSION == REQUIRED_SCOPE_LEASE_VERSION
        ),
        "sharding_version_bound": SHARDING_VERSION == REQUIRED_SHARDING_VERSION,
        "rollback_version_bound": ROLLBACK_VERSION == REQUIRED_ROLLBACK_VERSION,
        "first_intent_allowed": first["result"]["decision"] == "ALLOW_NEW_INTENT",
        "semantic_duplicate_joins": (
            joined["result"]["decision"] == "JOIN_EXISTING_INTENT"
            and joined["result"]["canonical_intent_id"]
            == first["result"]["intent_id"]
        ),
        "conflicting_intent_waits_before_branch": (
            waiting["result"]["decision"] == "WAIT_ON_CONFLICTING_INTENT"
            and waiting["result"]["branch_creation_allowed"] is False
            and waiting["result"]["lease_request_allowed"] is False
        ),
        "disjoint_shard_parallel": parallel["result"]["decision"] == "ALLOW_NEW_INTENT",
        "completion_promotes_waiter": (
            waiting["result"]["intent_id"]
            in completed["result"]["promoted_intent_ids"]
        ),
        "stale_base_blocks_before_branch": (
            stale["result"]["decision"] == "BLOCK_STALE_INTENT_BASE"
            and stale["result"]["branch_creation_allowed"] is False
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "detached_continuation_version_bound",
        "blast_simulator_version_bound",
        "scope_lease_version_bound",
        "sharding_version_bound",
        "rollback_version_bound",
        "first_intent_allowed",
        "semantic_duplicate_joins",
        "conflicting_intent_waits_before_branch",
        "disjoint_shard_parallel",
        "completion_promotes_waiter",
        "stale_base_blocks_before_branch",
    ]
    if not all(result[name] is True for name in required):
        raise CrossWorkstreamIntentFailure("intent arbiter self-test failed")
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise CrossWorkstreamIntentFailure("read-only intent arbiter invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V8_STEP3_CROSS_WORKSTREAM_INTENT_ARBITER_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CrossWorkstreamIntentFailure as exc:
        print("MONSTER_V8_STEP3_CROSS_WORKSTREAM_INTENT_ARBITER_BLOCKED: " + str(exc))
        raise SystemExit(1)
