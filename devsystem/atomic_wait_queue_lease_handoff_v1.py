"""MONSTER V7 Step 5 — Atomic Wait Queue + Lease Handoff V1.

Durable next-in-line reservation for the frozen V5 scope-aware lease system.

The queue is persisted separately from the lease state so waiting workstreams do
not repeatedly poll/reclaim a busy resource. The actual release->claim handoff is
computed as one logical transaction and the resulting lease state is intended to
be persisted with one CAS write to the authoritative V5 lease state file.

Safety:
- queue order is FIFO per queue_key;
- duplicate owner reservations for the same queue_key do not duplicate;
- no leapfrogging: if the head waiter cannot acquire, later waiters stay blocked;
- release is rolled back in-memory if the head waiter cannot claim;
- the queued ticket id is embedded in the eventual lease scope resource_identity;
- queue acknowledgement can be reconciled idempotently from the live lease;
- CAS, frozen-path, TTL, scope conflict, and shard conflict rules delegate to the
  frozen V5 + Step-4 engines;
- this module performs no network calls and grants no mutation authority itself.
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

from devsystem.scope_aware_execution_lease_v1 import (
    VERSION as SCOPE_LEASE_VERSION,
    build_scope,
    claim_scope,
    new_state as new_lease_state,
    release_scope,
    validate_state as validate_lease_state,
)
from devsystem.shared_resource_lease_sharding_v1 import (
    VERSION as SHARDING_VERSION,
    claim_sharded_scope,
    parse_resource,
)

VERSION = "MONSTER_V7_ATOMIC_WAIT_QUEUE_LEASE_HANDOFF_V1"
QUEUE_REF = "refs/heads/monster-lease-wait-queue"
QUEUE_PATH = "devsystem/atomic_wait_queue_state_v1.json"

REQUIRED_SCOPE_LEASE_VERSION = "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_V1"
REQUIRED_SHARDING_VERSION = "MONSTER_V7_SHARED_RESOURCE_LEASE_SHARDING_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_HASH64 = re.compile(r"^[0-9a-f]{64}$")


class AtomicWaitQueueFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(value))
    out.pop("state_hash", None)
    return out


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise AtomicWaitQueueFailure(f"{field} is required")
    return out


def _utc(value: str) -> datetime:
    text = _text(value, "timestamp").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AtomicWaitQueueFailure(f"invalid UTC timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _queue_key(value: Any) -> str:
    token = _text(value, "queue_key").lower()
    parsed = parse_resource(token)
    return str(parsed["resource"])


def _queue_cas(
    state: Mapping[str, Any],
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any] | None:
    if (
        int(state["revision"]) != int(expected_revision)
        or str(state["state_hash"]) != str(expected_state_hash)
    ):
        return {
            "decision": "WAIT_QUEUE_STALE_CAS_CONTINUE",
            "allowed": False,
            "next_legal_action": "REREAD_WAIT_QUEUE_STATE",
        }
    return None


def _validate_ticket(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise AtomicWaitQueueFailure("ticket must be an object")
    scope = build_scope(**dict(raw.get("scope") or {}))
    queue_key = _queue_key(raw.get("queue_key"))
    if queue_key not in scope["shared_resources"]:
        raise AtomicWaitQueueFailure(
            "queue_key must exist in ticket scope shared_resources"
        )
    ticket_id = _text(raw.get("ticket_id"), "ticket_id")
    owner_id = _text(raw.get("owner_id"), "owner_id")
    blocked_by = _text(raw.get("blocked_by_lease_id"), "blocked_by_lease_id")
    try:
        sequence = int(raw.get("sequence"))
    except (TypeError, ValueError) as exc:
        raise AtomicWaitQueueFailure("ticket sequence must be an integer") from exc
    if sequence <= 0:
        raise AtomicWaitQueueFailure("ticket sequence must be positive")

    enqueued = _fmt(_utc(raw.get("enqueued_at_utc")))
    expires = _fmt(_utc(raw.get("expires_at_utc")))
    if _utc(expires) <= _utc(enqueued):
        raise AtomicWaitQueueFailure("ticket expiry must follow enqueue time")

    status = str(raw.get("status") or "").strip().upper()
    if status != "WAITING":
        raise AtomicWaitQueueFailure("active queue ticket status must be WAITING")

    queue_ticket_identity = str(
        scope["resource_identity"].get("queue:ticket") or ""
    ).strip()
    if queue_ticket_identity != ticket_id:
        raise AtomicWaitQueueFailure(
            "ticket scope must carry exact queue:ticket identity"
        )

    return {
        "ticket_id": ticket_id,
        "owner_id": owner_id,
        "queue_key": queue_key,
        "sequence": sequence,
        "blocked_by_lease_id": blocked_by,
        "enqueued_at_utc": enqueued,
        "expires_at_utc": expires,
        "status": "WAITING",
        "scope": scope,
    }


def _validate_handoff_receipt(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise AtomicWaitQueueFailure("handoff receipt must be an object")
    receipt = {
        "ticket_id": _text(raw.get("ticket_id"), "receipt ticket_id"),
        "owner_id": _text(raw.get("owner_id"), "receipt owner_id"),
        "queue_key": _queue_key(raw.get("queue_key")),
        "previous_lease_id": _text(
            raw.get("previous_lease_id"), "previous_lease_id"
        ),
        "new_lease_id": _text(raw.get("new_lease_id"), "new_lease_id"),
        "handed_off_at_utc": _fmt(_utc(raw.get("handed_off_at_utc"))),
        "lease_state_hash": str(raw.get("lease_state_hash") or "").strip().lower(),
    }
    if not _HASH64.fullmatch(receipt["lease_state_hash"]):
        raise AtomicWaitQueueFailure("receipt lease_state_hash invalid")
    return receipt


def new_queue_state(repository: str) -> dict[str, Any]:
    repo = _text(repository, "repository").lower()
    if "/" not in repo:
        raise AtomicWaitQueueFailure("repository must be owner/name")
    state = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "queue_ref": QUEUE_REF,
        "queue_state_path": QUEUE_PATH,
        "revision": 0,
        "generation": 0,
        "tickets": [],
        "handoff_receipts": [],
    }
    state["state_hash"] = _hash(state)
    return validate_queue_state(state)


def validate_queue_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise AtomicWaitQueueFailure("queue state must be an object")
    state = deepcopy(dict(payload))
    if state.get("version") != VERSION or int(state.get("schema_version", 0)) != 1:
        raise AtomicWaitQueueFailure("queue version/schema mismatch")
    if state.get("queue_ref") != QUEUE_REF or state.get("queue_state_path") != QUEUE_PATH:
        raise AtomicWaitQueueFailure("queue persistence identity mismatch")
    if "/" not in str(state.get("repository") or ""):
        raise AtomicWaitQueueFailure("queue repository invalid")
    if int(state.get("revision", -1)) < 0 or int(state.get("generation", -1)) < 0:
        raise AtomicWaitQueueFailure("queue revision/generation invalid")

    tickets = [_validate_ticket(item) for item in (state.get("tickets") or [])]
    ticket_ids = [item["ticket_id"] for item in tickets]
    if len(ticket_ids) != len(set(ticket_ids)):
        raise AtomicWaitQueueFailure("duplicate active ticket_id")
    seqs = [item["sequence"] for item in tickets]
    if len(seqs) != len(set(seqs)):
        raise AtomicWaitQueueFailure("duplicate active ticket sequence")

    owner_keys = [(item["owner_id"], item["queue_key"]) for item in tickets]
    if len(owner_keys) != len(set(owner_keys)):
        raise AtomicWaitQueueFailure("duplicate owner reservation for queue_key")

    receipts = [
        _validate_handoff_receipt(item)
        for item in (state.get("handoff_receipts") or [])
    ]
    receipt_ticket_ids = [item["ticket_id"] for item in receipts]
    if len(receipt_ticket_ids) != len(set(receipt_ticket_ids)):
        raise AtomicWaitQueueFailure("duplicate completed handoff ticket")

    active = set(ticket_ids)
    completed = set(receipt_ticket_ids)
    if active & completed:
        raise AtomicWaitQueueFailure("ticket cannot be active and completed")

    state["tickets"] = sorted(tickets, key=lambda item: item["sequence"])
    state["handoff_receipts"] = sorted(
        receipts,
        key=lambda item: (item["handed_off_at_utc"], item["ticket_id"]),
    )

    supplied = str(state.get("state_hash") or "").lower()
    if not _HASH64.fullmatch(supplied):
        raise AtomicWaitQueueFailure("queue state_hash invalid")
    expected = _hash(_without_hash(state))
    if supplied != expected:
        raise AtomicWaitQueueFailure("queue state hash mismatch")
    return state


def _rehash_queue(state: Mapping[str, Any]) -> dict[str, Any]:
    updated = deepcopy(dict(state))
    updated["tickets"] = sorted(
        list(updated.get("tickets") or []),
        key=lambda item: int(item["sequence"]),
    )
    updated["handoff_receipts"] = sorted(
        list(updated.get("handoff_receipts") or []),
        key=lambda item: (
            str(item["handed_off_at_utc"]),
            str(item["ticket_id"]),
        ),
    )
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    return validate_queue_state(updated)


def _live_tickets(
    state: Mapping[str, Any],
    *,
    now_utc: str,
    queue_key: str | None = None,
) -> list[dict[str, Any]]:
    current = validate_queue_state(state)
    now = _utc(now_utc)
    wanted = _queue_key(queue_key) if queue_key else None
    return [
        deepcopy(item)
        for item in current["tickets"]
        if now < _utc(item["expires_at_utc"])
        and (wanted is None or item["queue_key"] == wanted)
    ]


def queue_position(
    state: Mapping[str, Any],
    *,
    ticket_id: str,
    now_utc: str,
) -> dict[str, Any]:
    current = validate_queue_state(state)
    wanted = _text(ticket_id, "ticket_id")
    ticket = next(
        (item for item in current["tickets"] if item["ticket_id"] == wanted),
        None,
    )
    if ticket is None:
        receipt = next(
            (
                item
                for item in current["handoff_receipts"]
                if item["ticket_id"] == wanted
            ),
            None,
        )
        if receipt:
            return {
                "decision": "WAIT_TICKET_ALREADY_HANDED_OFF",
                "ticket_id": wanted,
                "new_lease_id": receipt["new_lease_id"],
                "position": 0,
            }
        return {
            "decision": "WAIT_TICKET_NOT_FOUND",
            "ticket_id": wanted,
            "position": None,
        }

    live = _live_tickets(
        current,
        now_utc=now_utc,
        queue_key=ticket["queue_key"],
    )
    ids = [item["ticket_id"] for item in live]
    if wanted not in ids:
        return {
            "decision": "WAIT_TICKET_EXPIRED",
            "ticket_id": wanted,
            "position": None,
        }

    position = ids.index(wanted) + 1
    return {
        "decision": "WAIT_TICKET_POSITION",
        "ticket_id": wanted,
        "queue_key": ticket["queue_key"],
        "position": position,
        "queue_depth": len(ids),
        "next_legal_action": (
            "WAIT_FOR_ATOMIC_HANDOFF"
            if position == 1
            else "WAIT_IN_RESERVED_ORDER"
        ),
    }


def enqueue_waiter(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    queue_key: str,
    blocked_by_lease_id: str,
    scope: Mapping[str, Any],
    now_utc: str,
    expected_revision: int,
    expected_state_hash: str,
    ttl_seconds: int = 1800,
) -> dict[str, Any]:
    current = validate_queue_state(state)
    conflict = _queue_cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}

    owner = _text(owner_id, "owner_id")
    key = _queue_key(queue_key)
    blocker = _text(blocked_by_lease_id, "blocked_by_lease_id")
    now = _utc(now_utc)
    ttl = int(ttl_seconds)
    if ttl <= 0:
        raise AtomicWaitQueueFailure("ttl_seconds must be positive")

    active = list(_live_tickets(current, now_utc=now_utc))
    duplicate = next(
        (
            item
            for item in active
            if item["owner_id"] == owner and item["queue_key"] == key
        ),
        None,
    )
    if duplicate:
        return {
            "result": {
                "decision": "WAIT_TICKET_ALREADY_QUEUED",
                "allowed": True,
                "ticket_id": duplicate["ticket_id"],
                "position": queue_position(
                    current,
                    ticket_id=duplicate["ticket_id"],
                    now_utc=now_utc,
                )["position"],
                "next_legal_action": "WAIT_FOR_ATOMIC_HANDOFF",
            },
            "state": current,
        }

    base_scope = build_scope(**dict(scope))
    if key not in base_scope["shared_resources"]:
        raise AtomicWaitQueueFailure(
            "queue_key must exist in requested scope shared_resources"
        )

    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    generation = updated["generation"]
    seed = {
        "repository": updated["repository"],
        "owner_id": owner,
        "queue_key": key,
        "sequence": generation,
        "blocked_by_lease_id": blocker,
        "enqueued_at_utc": _fmt(now),
        "scope": base_scope,
    }
    ticket_id = "WAIT-TICKET-" + _hash(seed)[:24].upper()

    identity = dict(base_scope["resource_identity"])
    if "queue:ticket" in identity and identity["queue:ticket"] != ticket_id:
        raise AtomicWaitQueueFailure(
            "scope already carries a different queue:ticket identity"
        )
    identity["queue:ticket"] = ticket_id
    ticket_scope = build_scope(
        write_paths=base_scope["write_paths"],
        dependency_tokens=base_scope["dependency_tokens"],
        shared_resources=base_scope["shared_resources"],
        resource_identity=identity,
        exclusive=base_scope["exclusive"],
    )
    ticket = {
        "ticket_id": ticket_id,
        "owner_id": owner,
        "queue_key": key,
        "sequence": generation,
        "blocked_by_lease_id": blocker,
        "enqueued_at_utc": _fmt(now),
        "expires_at_utc": _fmt(now + timedelta(seconds=ttl)),
        "status": "WAITING",
        "scope": ticket_scope,
    }

    updated["tickets"] = active + [ticket]
    updated = _rehash_queue(updated)
    pos = queue_position(updated, ticket_id=ticket_id, now_utc=now_utc)
    return {
        "result": {
            "decision": "WAIT_TICKET_RESERVED",
            "allowed": True,
            "ticket_id": ticket_id,
            "queue_key": key,
            "position": pos["position"],
            "queue_depth": pos["queue_depth"],
            "next_legal_action": "WAIT_FOR_ATOMIC_HANDOFF",
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def cancel_waiter(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    ticket_id: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_queue_state(state)
    conflict = _queue_cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}

    owner = _text(owner_id, "owner_id")
    wanted = _text(ticket_id, "ticket_id")
    ticket = next(
        (
            item
            for item in current["tickets"]
            if item["ticket_id"] == wanted and item["owner_id"] == owner
        ),
        None,
    )
    if ticket is None:
        return {
            "result": {
                "decision": "WAIT_TICKET_OWNER_MISMATCH_CONTINUE",
                "allowed": False,
            },
            "state": current,
        }

    updated = deepcopy(current)
    updated["revision"] += 1
    updated["tickets"] = [
        item for item in current["tickets"] if item["ticket_id"] != wanted
    ]
    updated = _rehash_queue(updated)
    return {
        "result": {
            "decision": "WAIT_TICKET_CANCELLED",
            "allowed": True,
            "ticket_id": wanted,
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def _complete_ticket(
    queue_state: Mapping[str, Any],
    *,
    ticket: Mapping[str, Any],
    previous_lease_id: str,
    new_lease_id: str,
    handed_off_at_utc: str,
    lease_state_hash: str,
) -> dict[str, Any]:
    current = validate_queue_state(queue_state)
    updated = deepcopy(current)
    updated["revision"] += 1
    updated["tickets"] = [
        item
        for item in current["tickets"]
        if item["ticket_id"] != ticket["ticket_id"]
    ]
    updated["handoff_receipts"] = list(current["handoff_receipts"]) + [
        {
            "ticket_id": ticket["ticket_id"],
            "owner_id": ticket["owner_id"],
            "queue_key": ticket["queue_key"],
            "previous_lease_id": previous_lease_id,
            "new_lease_id": new_lease_id,
            "handed_off_at_utc": _fmt(_utc(handed_off_at_utc)),
            "lease_state_hash": lease_state_hash,
        }
    ]
    return _rehash_queue(updated)


def atomic_release_and_handoff(
    lease_state: Mapping[str, Any],
    queue_state: Mapping[str, Any],
    *,
    releasing_owner_id: str,
    releasing_lease_id: str,
    queue_key: str,
    now_utc: str,
    expected_lease_revision: int,
    expected_lease_state_hash: str,
    expected_queue_revision: int,
    expected_queue_state_hash: str,
    lease_ttl_seconds: int = 900,
    frozen_paths: Sequence[str] = (),
    thawed_paths: Sequence[str] = (),
) -> dict[str, Any]:
    """Compute an atomic release->claim result with rollback on claim failure."""
    current_lease = validate_lease_state(lease_state)
    current_queue = validate_queue_state(queue_state)

    queue_conflict = _queue_cas(
        current_queue,
        expected_queue_revision,
        expected_queue_state_hash,
    )
    if queue_conflict:
        return {
            "result": queue_conflict,
            "lease_state": current_lease,
            "queue_state": current_queue,
        }

    release = release_scope(
        current_lease,
        owner_id=releasing_owner_id,
        lease_id=releasing_lease_id,
        expected_revision=expected_lease_revision,
        expected_state_hash=expected_lease_state_hash,
    )
    if release["result"].get("allowed") is not True:
        return {
            "result": release["result"],
            "lease_state": current_lease,
            "queue_state": current_queue,
        }

    key = _queue_key(queue_key)
    live = _live_tickets(
        current_queue,
        now_utc=now_utc,
        queue_key=key,
    )
    if not live:
        return {
            "result": {
                "decision": "LEASE_RELEASED_NO_WAITER",
                "allowed": True,
                "handoff": False,
                "released_lease_id": releasing_lease_id,
                "next_legal_action": "RESOURCE_AVAILABLE",
                "lease_state_hash": release["state"]["state_hash"],
            },
            "lease_state": release["state"],
            "queue_state": current_queue,
        }

    head = live[0]

    claim = claim_sharded_scope(
        release["state"],
        owner_id=head["owner_id"],
        now_utc=now_utc,
        scope=head["scope"],
        expected_revision=release["state"]["revision"],
        expected_state_hash=release["state"]["state_hash"],
        ttl_seconds=lease_ttl_seconds,
        frozen_paths=frozen_paths,
        thawed_paths=thawed_paths,
    )
    if claim["result"].get("allowed") is not True:
        return {
            "result": {
                "decision": "ATOMIC_HANDOFF_HEAD_BLOCKED",
                "allowed": False,
                "handoff": False,
                "ticket_id": head["ticket_id"],
                "queue_key": key,
                "head_owner_id": head["owner_id"],
                "claim_decision": claim["result"].get("decision"),
                "next_legal_action": "WAIT_FOR_BLOCKING_CONDITION_TO_CLEAR",
                "original_holder_retained": True,
            },
            "lease_state": current_lease,
            "queue_state": current_queue,
        }

    new_lease_id = _text(claim["result"].get("lease_id"), "new lease_id")
    completed_queue = _complete_ticket(
        current_queue,
        ticket=head,
        previous_lease_id=releasing_lease_id,
        new_lease_id=new_lease_id,
        handed_off_at_utc=now_utc,
        lease_state_hash=claim["state"]["state_hash"],
    )
    return {
        "result": {
            "decision": "ATOMIC_LEASE_HANDOFF_COMMITTED",
            "allowed": True,
            "handoff": True,
            "ticket_id": head["ticket_id"],
            "queue_key": key,
            "previous_owner_id": releasing_owner_id,
            "previous_lease_id": releasing_lease_id,
            "new_owner_id": head["owner_id"],
            "new_lease_id": new_lease_id,
            "lease_revision_before": current_lease["revision"],
            "lease_revision_after": claim["state"]["revision"],
            "logical_revision_span": (
                claim["state"]["revision"] - current_lease["revision"]
            ),
            "queue_revision_before": current_queue["revision"],
            "queue_revision_after": completed_queue["revision"],
            "next_legal_action": "RESUME_RESERVED_WORKSTREAM",
            "lease_state_hash": claim["state"]["state_hash"],
            "queue_state_hash": completed_queue["state_hash"],
        },
        "lease_state": claim["state"],
        "queue_state": completed_queue,
    }


def reconcile_queue_from_lease(
    queue_state: Mapping[str, Any],
    lease_state: Mapping[str, Any],
    *,
    expected_queue_revision: int,
    expected_queue_state_hash: str,
    now_utc: str,
) -> dict[str, Any]:
    current_queue = validate_queue_state(queue_state)
    current_lease = validate_lease_state(lease_state)
    conflict = _queue_cas(
        current_queue,
        expected_queue_revision,
        expected_queue_state_hash,
    )
    if conflict:
        return {"result": conflict, "state": current_queue}

    ticket_by_id = {
        item["ticket_id"]: item for item in current_queue["tickets"]
    }
    for holder in current_lease["holders"]:
        ticket_id = str(
            (holder.get("scope") or {})
            .get("resource_identity", {})
            .get("queue:ticket", "")
        ).strip()
        if not ticket_id or ticket_id not in ticket_by_id:
            continue
        ticket = ticket_by_id[ticket_id]
        updated = _complete_ticket(
            current_queue,
            ticket=ticket,
            previous_lease_id=ticket["blocked_by_lease_id"],
            new_lease_id=holder["lease_id"],
            handed_off_at_utc=now_utc,
            lease_state_hash=current_lease["state_hash"],
        )
        return {
            "result": {
                "decision": "WAIT_QUEUE_HANDOFF_RECONCILED",
                "allowed": True,
                "ticket_id": ticket_id,
                "new_lease_id": holder["lease_id"],
                "next_legal_action": "RESUME_RESERVED_WORKSTREAM",
                "state_hash": updated["state_hash"],
            },
            "state": updated,
        }

    return {
        "result": {
            "decision": "WAIT_QUEUE_RECONCILE_NOOP",
            "allowed": True,
            "next_legal_action": "WAIT_FOR_ATOMIC_HANDOFF",
        },
        "state": current_queue,
    }


def contract_self_test() -> dict[str, Any]:
    if SCOPE_LEASE_VERSION != REQUIRED_SCOPE_LEASE_VERSION:
        raise AtomicWaitQueueFailure("V5 lease version mismatch")
    if SHARDING_VERSION != REQUIRED_SHARDING_VERSION:
        raise AtomicWaitQueueFailure("Step-4 sharding version mismatch")

    now = "2026-10-02T01:00:00Z"
    queue = new_queue_state("owner/repo")
    lease = new_lease_state("owner/repo")
    queue_key = (
        "workflow:devsystem-targeted-ci#shard[domain=cfb,lane=permanent]"
    )

    holder_claim = claim_scope(
        lease,
        owner_id="holder",
        now_utc=now,
        scope=build_scope(
            write_paths=["holder.py"],
            shared_resources=[queue_key],
        ),
        expected_revision=0,
        expected_state_hash=lease["state_hash"],
        ttl_seconds=1800,
    )
    holder = holder_claim["state"]["holders"][0]

    a = enqueue_waiter(
        queue,
        owner_id="waiter-a",
        queue_key=queue_key,
        blocked_by_lease_id=holder["lease_id"],
        scope=build_scope(
            write_paths=["a.py"],
            shared_resources=[queue_key],
        ),
        now_utc=now,
        expected_revision=queue["revision"],
        expected_state_hash=queue["state_hash"],
    )
    b = enqueue_waiter(
        a["state"],
        owner_id="waiter-b",
        queue_key=queue_key,
        blocked_by_lease_id=holder["lease_id"],
        scope=build_scope(
            write_paths=["b.py"],
            shared_resources=[queue_key],
        ),
        now_utc=now,
        expected_revision=a["state"]["revision"],
        expected_state_hash=a["state"]["state_hash"],
    )
    duplicate = enqueue_waiter(
        b["state"],
        owner_id="waiter-b",
        queue_key=queue_key,
        blocked_by_lease_id=holder["lease_id"],
        scope=build_scope(
            write_paths=["b.py"],
            shared_resources=[queue_key],
        ),
        now_utc=now,
        expected_revision=b["state"]["revision"],
        expected_state_hash=b["state"]["state_hash"],
    )

    pos_a = queue_position(
        b["state"],
        ticket_id=a["result"]["ticket_id"],
        now_utc=now,
    )
    pos_b = queue_position(
        b["state"],
        ticket_id=b["result"]["ticket_id"],
        now_utc=now,
    )

    handoff = atomic_release_and_handoff(
        holder_claim["state"],
        b["state"],
        releasing_owner_id="holder",
        releasing_lease_id=holder["lease_id"],
        queue_key=queue_key,
        now_utc=now,
        expected_lease_revision=holder_claim["state"]["revision"],
        expected_lease_state_hash=holder_claim["state"]["state_hash"],
        expected_queue_revision=b["state"]["revision"],
        expected_queue_state_hash=b["state"]["state_hash"],
    )
    new_holder = next(
        h
        for h in handoff["lease_state"]["holders"]
        if h["owner_id"] == "waiter-a"
    )
    pos_b_after = queue_position(
        handoff["queue_state"],
        ticket_id=b["result"]["ticket_id"],
        now_utc=now,
    )

    reconciled = reconcile_queue_from_lease(
        b["state"],
        handoff["lease_state"],
        expected_queue_revision=b["state"]["revision"],
        expected_queue_state_hash=b["state"]["state_hash"],
        now_utc=now,
    )

    blocked_lease = new_lease_state("owner/repo")
    primary = claim_scope(
        blocked_lease,
        owner_id="primary",
        now_utc=now,
        scope=build_scope(
            write_paths=["primary.py"],
            shared_resources=[queue_key],
        ),
        expected_revision=0,
        expected_state_hash=blocked_lease["state_hash"],
    )
    other = claim_scope(
        primary["state"],
        owner_id="dependency-holder",
        now_utc=now,
        scope=build_scope(
            write_paths=["dep.py"],
            dependency_tokens=["provider:shared"],
        ),
        expected_revision=primary["state"]["revision"],
        expected_state_hash=primary["state"]["state_hash"],
    )

    blocked_queue = new_queue_state("owner/repo")
    first = enqueue_waiter(
        blocked_queue,
        owner_id="head",
        queue_key=queue_key,
        blocked_by_lease_id=primary["result"]["lease_id"],
        scope=build_scope(
            write_paths=["head.py"],
            dependency_tokens=["provider:shared"],
            shared_resources=[queue_key],
        ),
        now_utc=now,
        expected_revision=0,
        expected_state_hash=blocked_queue["state_hash"],
    )
    second = enqueue_waiter(
        first["state"],
        owner_id="second",
        queue_key=queue_key,
        blocked_by_lease_id=primary["result"]["lease_id"],
        scope=build_scope(
            write_paths=["second.py"],
            shared_resources=[queue_key],
        ),
        now_utc=now,
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    blocked = atomic_release_and_handoff(
        other["state"],
        second["state"],
        releasing_owner_id="primary",
        releasing_lease_id=primary["result"]["lease_id"],
        queue_key=queue_key,
        now_utc=now,
        expected_lease_revision=other["state"]["revision"],
        expected_lease_state_hash=other["state"]["state_hash"],
        expected_queue_revision=second["state"]["revision"],
        expected_queue_state_hash=second["state"]["state_hash"],
    )

    no_wait_queue = new_queue_state("owner/repo")
    no_wait_lease = new_lease_state("owner/repo")
    no_wait_holder = claim_scope(
        no_wait_lease,
        owner_id="solo",
        now_utc=now,
        scope=build_scope(
            write_paths=["solo.py"],
            shared_resources=[queue_key],
        ),
        expected_revision=0,
        expected_state_hash=no_wait_lease["state_hash"],
    )
    released_no_waiter = atomic_release_and_handoff(
        no_wait_holder["state"],
        no_wait_queue,
        releasing_owner_id="solo",
        releasing_lease_id=no_wait_holder["result"]["lease_id"],
        queue_key=queue_key,
        now_utc=now,
        expected_lease_revision=no_wait_holder["state"]["revision"],
        expected_lease_state_hash=no_wait_holder["state"]["state_hash"],
        expected_queue_revision=0,
        expected_queue_state_hash=no_wait_queue["state_hash"],
    )

    stale_queue = enqueue_waiter(
        b["state"],
        owner_id="stale",
        queue_key=queue_key,
        blocked_by_lease_id=holder["lease_id"],
        scope=build_scope(
            write_paths=["stale.py"],
            shared_resources=[queue_key],
        ),
        now_utc=now,
        expected_revision=0,
        expected_state_hash=queue["state_hash"],
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "v5_scope_lease_version_bound": (
            SCOPE_LEASE_VERSION == REQUIRED_SCOPE_LEASE_VERSION
        ),
        "step4_sharding_version_bound": (
            SHARDING_VERSION == REQUIRED_SHARDING_VERSION
        ),
        "fifo_positions_preserved": (
            pos_a["position"] == 1 and pos_b["position"] == 2
        ),
        "duplicate_reservation_deduped": (
            duplicate["result"]["decision"] == "WAIT_TICKET_ALREADY_QUEUED"
            and duplicate["state"]["state_hash"] == b["state"]["state_hash"]
        ),
        "atomic_release_claim_committed": (
            handoff["result"]["decision"] == "ATOMIC_LEASE_HANDOFF_COMMITTED"
            and handoff["result"]["new_owner_id"] == "waiter-a"
            and handoff["result"]["logical_revision_span"] == 2
        ),
        "ticket_identity_carried_into_lease": (
            new_holder["scope"]["resource_identity"]["queue:ticket"]
            == a["result"]["ticket_id"]
        ),
        "next_waiter_advances_after_handoff": (
            pos_b_after["position"] == 1
        ),
        "handoff_receipt_recorded": (
            handoff["queue_state"]["handoff_receipts"][0]["ticket_id"]
            == a["result"]["ticket_id"]
        ),
        "delayed_queue_ack_reconciles_from_lease": (
            reconciled["result"]["decision"]
            == "WAIT_QUEUE_HANDOFF_RECONCILED"
            and reconciled["result"]["ticket_id"] == a["result"]["ticket_id"]
        ),
        "head_blocked_prevents_leapfrog": (
            blocked["result"]["decision"] == "ATOMIC_HANDOFF_HEAD_BLOCKED"
            and blocked["result"]["original_holder_retained"] is True
            and any(
                h["owner_id"] == "primary"
                for h in blocked["lease_state"]["holders"]
            )
            and queue_position(
                blocked["queue_state"],
                ticket_id=first["result"]["ticket_id"],
                now_utc=now,
            )["position"] == 1
            and queue_position(
                blocked["queue_state"],
                ticket_id=second["result"]["ticket_id"],
                now_utc=now,
            )["position"] == 2
        ),
        "release_without_waiter_still_succeeds": (
            released_no_waiter["result"]["decision"]
            == "LEASE_RELEASED_NO_WAITER"
            and released_no_waiter["lease_state"]["holders"] == []
        ),
        "stale_queue_cas_fails_closed": (
            stale_queue["result"]["decision"]
            == "WAIT_QUEUE_STALE_CAS_CONTINUE"
        ),
        "dedicated_queue_ref": (
            QUEUE_REF == "refs/heads/monster-lease-wait-queue"
            and QUEUE_PATH == "devsystem/atomic_wait_queue_state_v1.json"
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }

    required = (
        "v5_scope_lease_version_bound",
        "step4_sharding_version_bound",
        "fifo_positions_preserved",
        "duplicate_reservation_deduped",
        "atomic_release_claim_committed",
        "ticket_identity_carried_into_lease",
        "next_waiter_advances_after_handoff",
        "handoff_receipt_recorded",
        "delayed_queue_ack_reconciles_from_lease",
        "head_blocked_prevents_leapfrog",
        "release_without_waiter_still_succeeds",
        "stale_queue_cas_fails_closed",
        "dedicated_queue_ref",
    )
    if not all(result[name] is True for name in required):
        raise AtomicWaitQueueFailure(
            "atomic wait queue + lease handoff self-test failed"
        )
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise AtomicWaitQueueFailure("read-only safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP5_ATOMIC_WAIT_QUEUE_HANDOFF_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AtomicWaitQueueFailure as exc:
        print(
            "MONSTER_V7_STEP5_ATOMIC_WAIT_QUEUE_HANDOFF_BLOCKED: "
            + str(exc)
        )
        raise SystemExit(1)
