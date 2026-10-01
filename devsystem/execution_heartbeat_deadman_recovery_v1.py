"""MONSTER V5 Step 4 — Execution Heartbeat + Dead-Man Recovery V1.

Repository-safe control-plane layer for proving worker liveness and permitting a
single recovery handoff only after both of these are true:
1) the worker heartbeat has expired, and
2) no authoritative async run is still active.

This layer never grants mutation authority. A recovered worker must still pass
MONSTER Step 2A and hold the exact scoped execution lease before mutation.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

VERSION = "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_V1"
STATE_REF = "refs/heads/monster-execution-heartbeat-deadman"
STATE_PATH = "devsystem/execution_heartbeat_deadman_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

ACTIVE_RUN_STATES = frozenset({"queued", "pending", "waiting", "in_progress", "running", "requested"})
TERMINAL_RUN_STATES = frozenset({"success", "failure", "failed", "cancelled", "canceled", "skipped", "completed", "absent"})
_HASH64_LEN = 64


class HeartbeatRecoveryFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(value))
    out.pop("state_hash", None)
    return out


def _utc(value: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HeartbeatRecoveryFailure("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_hash64(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != _HASH64_LEN or any(ch not in "0123456789abcdef" for ch in text):
        raise HeartbeatRecoveryFailure(f"{field} must be a 64-character lowercase hex hash")
    return text


def _require_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HeartbeatRecoveryFailure(f"{field} required")
    return text


def new_state(repository: str) -> dict[str, Any]:
    repo = _require_text(repository, "repository").lower()
    if "/" not in repo:
        raise HeartbeatRecoveryFailure("repository must be owner/name")
    state = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "state_ref": STATE_REF,
        "state_path": STATE_PATH,
        "revision": 0,
        "generation": 0,
        "workers": [],
        "recovery_receipts": [],
        "consumed_recovery_receipts": [],
    }
    state["state_hash"] = _hash(state)
    return validate_state(state)


def _validate_worker(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise HeartbeatRecoveryFailure("worker must be object")
    out = {
        "workstream_id": _require_text(raw.get("workstream_id"), "workstream_id"),
        "owner_id": _require_text(raw.get("owner_id"), "owner_id"),
        "scope_lease_id": _require_text(raw.get("scope_lease_id"), "scope_lease_id"),
        "continuation_packet_hash": _require_hash64(raw.get("continuation_packet_hash"), "continuation_packet_hash"),
        "authoritative_run_id": int(raw.get("authoritative_run_id") or 0),
        "generation": int(raw.get("generation") or 0),
        "heartbeat_at_utc": _fmt(_utc(raw.get("heartbeat_at_utc"))),
        "expires_at_utc": _fmt(_utc(raw.get("expires_at_utc"))),
    }
    if out["authoritative_run_id"] < 0 or out["generation"] <= 0:
        raise HeartbeatRecoveryFailure("worker run/generation invalid")
    if _utc(out["heartbeat_at_utc"]) >= _utc(out["expires_at_utc"]):
        raise HeartbeatRecoveryFailure("heartbeat must precede expiry")
    return out


def _validate_receipt(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise HeartbeatRecoveryFailure("recovery receipt must be object")
    receipt = {
        "receipt_id": _require_text(raw.get("receipt_id"), "receipt_id"),
        "workstream_id": _require_text(raw.get("workstream_id"), "workstream_id"),
        "previous_owner_id": _require_text(raw.get("previous_owner_id"), "previous_owner_id"),
        "new_owner_id": _require_text(raw.get("new_owner_id"), "new_owner_id"),
        "previous_scope_lease_id": _require_text(raw.get("previous_scope_lease_id"), "previous_scope_lease_id"),
        "new_scope_lease_id": _require_text(raw.get("new_scope_lease_id"), "new_scope_lease_id"),
        "continuation_packet_hash": _require_hash64(raw.get("continuation_packet_hash"), "continuation_packet_hash"),
        "observed_run_state": _require_text(raw.get("observed_run_state"), "observed_run_state").lower(),
        "issued_at_utc": _fmt(_utc(raw.get("issued_at_utc"))),
        "requires_step_2a": bool(raw.get("requires_step_2a")),
        "requires_scope_lease": bool(raw.get("requires_scope_lease")),
        "grants_mutation_authority": bool(raw.get("grants_mutation_authority")),
        "receipt_hash": _require_hash64(raw.get("receipt_hash"), "receipt_hash"),
    }
    expected = _hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    if receipt["receipt_hash"] != expected:
        raise HeartbeatRecoveryFailure("recovery receipt hash mismatch")
    if not receipt["requires_step_2a"] or not receipt["requires_scope_lease"] or receipt["grants_mutation_authority"]:
        raise HeartbeatRecoveryFailure("recovery receipt safety contract invalid")
    return receipt


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise HeartbeatRecoveryFailure("state must be object")
    state = deepcopy(dict(payload))
    if state.get("version") != VERSION or int(state.get("schema_version") or 0) != 1:
        raise HeartbeatRecoveryFailure("heartbeat state version/schema mismatch")
    if state.get("state_ref") != STATE_REF or state.get("state_path") != STATE_PATH:
        raise HeartbeatRecoveryFailure("heartbeat persistence identity mismatch")
    if "/" not in str(state.get("repository") or ""):
        raise HeartbeatRecoveryFailure("repository invalid")
    if int(state.get("revision", -1)) < 0 or int(state.get("generation", -1)) < 0:
        raise HeartbeatRecoveryFailure("revision/generation invalid")

    workers = [_validate_worker(x) for x in (state.get("workers") or [])]
    workstreams = [x["workstream_id"] for x in workers]
    if len(workstreams) != len(set(workstreams)):
        raise HeartbeatRecoveryFailure("duplicate workstream worker")
    receipts = [_validate_receipt(x) for x in (state.get("recovery_receipts") or [])]
    receipt_ids = [x["receipt_id"] for x in receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        raise HeartbeatRecoveryFailure("duplicate recovery receipt")
    consumed = sorted({_require_text(x, "consumed receipt") for x in (state.get("consumed_recovery_receipts") or [])})
    if not set(consumed).issubset(set(receipt_ids)):
        raise HeartbeatRecoveryFailure("consumed receipt missing from ledger")

    state["workers"] = sorted(workers, key=lambda x: x["workstream_id"])
    state["recovery_receipts"] = sorted(receipts, key=lambda x: x["receipt_id"])
    state["consumed_recovery_receipts"] = consumed

    supplied = _require_hash64(state.get("state_hash"), "state_hash")
    expected = _hash(_without_hash(state))
    if supplied != expected:
        raise HeartbeatRecoveryFailure("heartbeat state hash mismatch")
    return state


def _cas(state: Mapping[str, Any], expected_revision: int, expected_state_hash: str) -> dict[str, Any] | None:
    if int(state["revision"]) != int(expected_revision) or state["state_hash"] != str(expected_state_hash):
        return {
            "decision": "HEARTBEAT_STATE_STALE_CAS_CONTINUE",
            "allowed": False,
            "next_legal_action": "REREAD_HEARTBEAT_STATE",
        }
    return None


def _commit(state: dict[str, Any]) -> dict[str, Any]:
    state.pop("state_hash", None)
    state["state_hash"] = _hash(state)
    return validate_state(state)


def register_worker(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    owner_id: str,
    scope_lease_id: str,
    continuation_packet_hash: str,
    authoritative_run_id: int,
    now_utc: str,
    expected_revision: int,
    expected_state_hash: str,
    heartbeat_ttl_seconds: int = 900,
) -> dict[str, Any]:
    current = validate_state(state)
    conflict = _cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}
    stream = _require_text(workstream_id, "workstream_id")
    if any(x["workstream_id"] == stream for x in current["workers"]):
        return {
            "result": {
                "decision": "HEARTBEAT_WORKSTREAM_ALREADY_REGISTERED_CONTINUE",
                "allowed": False,
                "next_legal_action": "INSPECT_EXISTING_WORKER",
            },
            "state": current,
        }
    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    now = _utc(now_utc)
    updated["workers"].append({
        "workstream_id": stream,
        "owner_id": _require_text(owner_id, "owner_id"),
        "scope_lease_id": _require_text(scope_lease_id, "scope_lease_id"),
        "continuation_packet_hash": _require_hash64(continuation_packet_hash, "continuation_packet_hash"),
        "authoritative_run_id": int(authoritative_run_id),
        "generation": updated["generation"],
        "heartbeat_at_utc": _fmt(now),
        "expires_at_utc": _fmt(now + timedelta(seconds=int(heartbeat_ttl_seconds))),
    })
    updated = _commit(updated)
    return {
        "result": {
            "decision": "EXECUTION_HEARTBEAT_REGISTERED",
            "allowed": True,
            "generation": updated["generation"],
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def heartbeat_worker(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    owner_id: str,
    scope_lease_id: str,
    continuation_packet_hash: str,
    now_utc: str,
    expected_revision: int,
    expected_state_hash: str,
    heartbeat_ttl_seconds: int = 900,
) -> dict[str, Any]:
    current = validate_state(state)
    conflict = _cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}
    worker = next((x for x in current["workers"] if x["workstream_id"] == str(workstream_id)), None)
    if worker is None:
        return {"result": {"decision": "HEARTBEAT_WORKER_NOT_FOUND", "allowed": False}, "state": current}
    if (
        worker["owner_id"] != str(owner_id)
        or worker["scope_lease_id"] != str(scope_lease_id)
        or worker["continuation_packet_hash"] != str(continuation_packet_hash)
    ):
        return {
            "result": {"decision": "HEARTBEAT_IDENTITY_DRIFT_BLOCKED", "allowed": False},
            "state": current,
        }
    now = _utc(now_utc)
    if now >= _utc(worker["expires_at_utc"]):
        return {
            "result": {
                "decision": "HEARTBEAT_EXPIRED_RENEWAL_BLOCKED",
                "allowed": False,
                "next_legal_action": "RUN_DEAD_MAN_INSPECTION",
            },
            "state": current,
        }
    updated = deepcopy(current)
    updated["revision"] += 1
    target = next(x for x in updated["workers"] if x["workstream_id"] == str(workstream_id))
    target["heartbeat_at_utc"] = _fmt(now)
    target["expires_at_utc"] = _fmt(now + timedelta(seconds=int(heartbeat_ttl_seconds)))
    updated = _commit(updated)
    return {
        "result": {
            "decision": "EXECUTION_HEARTBEAT_RENEWED",
            "allowed": True,
            "state_hash": updated["state_hash"],
        },
        "state": updated,
    }


def inspect_dead_man(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    now_utc: str,
    observed_run_state: str,
) -> dict[str, Any]:
    current = validate_state(state)
    worker = next((x for x in current["workers"] if x["workstream_id"] == str(workstream_id)), None)
    if worker is None:
        return {"decision": "HEARTBEAT_WORKER_NOT_FOUND", "recovery_allowed": False}
    if worker["continuation_packet_hash"] != str(continuation_packet_hash):
        return {"decision": "CONTINUATION_DRIFT_BLOCKED", "recovery_allowed": False}

    run_state = _require_text(observed_run_state, "observed_run_state").lower()
    now = _utc(now_utc)
    if now < _utc(worker["expires_at_utc"]):
        return {
            "decision": "WORKER_HEARTBEAT_LIVE",
            "recovery_allowed": False,
            "next_legal_action": "WAIT_FOR_MATERIAL_EVENT",
        }
    if run_state in ACTIVE_RUN_STATES:
        return {
            "decision": "AUTHORITATIVE_RUN_STILL_ACTIVE",
            "recovery_allowed": False,
            "next_legal_action": "WAIT_FOR_RUN_TERMINAL_EVENT",
        }
    if run_state not in TERMINAL_RUN_STATES:
        return {
            "decision": "RUN_STATE_UNKNOWN_FAIL_CLOSED",
            "recovery_allowed": False,
            "next_legal_action": "VERIFY_AUTHORITATIVE_RUN_STATE",
        }
    return {
        "decision": "DEAD_MAN_RECOVERY_ELIGIBLE",
        "recovery_allowed": True,
        "previous_owner_id": worker["owner_id"],
        "previous_scope_lease_id": worker["scope_lease_id"],
        "authoritative_run_id": worker["authoritative_run_id"],
        "observed_run_state": run_state,
    }


def issue_recovery_receipt(
    state: Mapping[str, Any],
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    now_utc: str,
    observed_run_state: str,
    new_owner_id: str,
    new_scope_lease_id: str,
    expected_revision: int,
    expected_state_hash: str,
    heartbeat_ttl_seconds: int = 900,
) -> dict[str, Any]:
    current = validate_state(state)
    conflict = _cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}
    inspection = inspect_dead_man(
        current,
        workstream_id=workstream_id,
        continuation_packet_hash=continuation_packet_hash,
        now_utc=now_utc,
        observed_run_state=observed_run_state,
    )
    if inspection.get("recovery_allowed") is not True:
        return {"result": {**inspection, "allowed": False}, "state": current}

    new_owner = _require_text(new_owner_id, "new_owner_id")
    new_lease = _require_text(new_scope_lease_id, "new_scope_lease_id")
    worker = next(x for x in current["workers"] if x["workstream_id"] == str(workstream_id))
    if new_owner == worker["owner_id"] or new_lease == worker["scope_lease_id"]:
        return {
            "result": {
                "decision": "RECOVERY_REQUIRES_NEW_OWNER_AND_LEASE",
                "allowed": False,
            },
            "state": current,
        }

    issued = _fmt(_utc(now_utc))
    receipt_seed = {
        "workstream_id": worker["workstream_id"],
        "previous_owner_id": worker["owner_id"],
        "new_owner_id": new_owner,
        "previous_scope_lease_id": worker["scope_lease_id"],
        "new_scope_lease_id": new_lease,
        "continuation_packet_hash": worker["continuation_packet_hash"],
        "observed_run_state": str(observed_run_state).lower(),
        "issued_at_utc": issued,
    }
    receipt_id = "DEADMAN-" + _hash(receipt_seed)[:24].upper()
    receipt = {
        "receipt_id": receipt_id,
        **receipt_seed,
        "requires_step_2a": True,
        "requires_scope_lease": True,
        "grants_mutation_authority": False,
    }
    receipt["receipt_hash"] = _hash(receipt)

    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    target = next(x for x in updated["workers"] if x["workstream_id"] == str(workstream_id))
    target["owner_id"] = new_owner
    target["scope_lease_id"] = new_lease
    target["generation"] = updated["generation"]
    target["heartbeat_at_utc"] = issued
    target["expires_at_utc"] = _fmt(_utc(now_utc) + timedelta(seconds=int(heartbeat_ttl_seconds)))
    updated["recovery_receipts"].append(receipt)
    updated = _commit(updated)
    return {
        "result": {
            "decision": "DEAD_MAN_RECOVERY_RECEIPT_ISSUED",
            "allowed": True,
            "receipt_id": receipt_id,
            "receipt_hash": receipt["receipt_hash"],
            "requires_step_2a": True,
            "requires_scope_lease": True,
            "grants_mutation_authority": False,
        },
        "state": updated,
    }


def consume_recovery_receipt(
    state: Mapping[str, Any],
    *,
    receipt_id: str,
    receipt_hash: str,
    workstream_id: str,
    continuation_packet_hash: str,
    expected_revision: int,
    expected_state_hash: str,
) -> dict[str, Any]:
    current = validate_state(state)
    conflict = _cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}
    rid = _require_text(receipt_id, "receipt_id")
    receipt = next((x for x in current["recovery_receipts"] if x["receipt_id"] == rid), None)
    if receipt is None:
        return {"result": {"decision": "RECOVERY_RECEIPT_NOT_FOUND", "allowed": False}, "state": current}
    if rid in current["consumed_recovery_receipts"]:
        return {
            "result": {"decision": "RECOVERY_RECEIPT_REPLAY_BLOCKED", "allowed": False},
            "state": current,
        }
    if (
        receipt["receipt_hash"] != str(receipt_hash)
        or receipt["workstream_id"] != str(workstream_id)
        or receipt["continuation_packet_hash"] != str(continuation_packet_hash)
    ):
        return {
            "result": {"decision": "RECOVERY_RECEIPT_BINDING_DRIFT_BLOCKED", "allowed": False},
            "state": current,
        }
    updated = deepcopy(current)
    updated["revision"] += 1
    updated["consumed_recovery_receipts"].append(rid)
    updated = _commit(updated)
    return {
        "result": {
            "decision": "RECOVERY_RECEIPT_CONSUMED",
            "allowed": True,
            "mutation_authority": False,
            "next_legal_action": "PASS_STEP_2A_AND_SCOPED_LEASE_GATE",
        },
        "state": updated,
    }


def contract_self_test() -> dict[str, Any]:
    state = new_state("owner/repo")
    packet = "a" * 64
    registered = register_worker(
        state,
        workstream_id="monster-v5-step4",
        owner_id="worker:a",
        scope_lease_id="lease:a",
        continuation_packet_hash=packet,
        authoritative_run_id=101,
        now_utc="2026-10-01T00:00:00Z",
        expected_revision=0,
        expected_state_hash=state["state_hash"],
        heartbeat_ttl_seconds=60,
    )
    live = registered["state"]
    live_check = inspect_dead_man(
        live,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=packet,
        now_utc="2026-10-01T00:00:30Z",
        observed_run_state="running",
    )
    active_after_expiry = inspect_dead_man(
        live,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=packet,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="in_progress",
    )
    eligible = inspect_dead_man(
        live,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=packet,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="failure",
    )
    takeover = issue_recovery_receipt(
        live,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=packet,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="failure",
        new_owner_id="worker:b",
        new_scope_lease_id="lease:b",
        expected_revision=live["revision"],
        expected_state_hash=live["state_hash"],
        heartbeat_ttl_seconds=60,
    )
    recovered = takeover["state"]
    receipt = takeover["result"]
    consumed = consume_recovery_receipt(
        recovered,
        receipt_id=receipt["receipt_id"],
        receipt_hash=receipt["receipt_hash"],
        workstream_id="monster-v5-step4",
        continuation_packet_hash=packet,
        expected_revision=recovered["revision"],
        expected_state_hash=recovered["state_hash"],
    )
    replay = consume_recovery_receipt(
        consumed["state"],
        receipt_id=receipt["receipt_id"],
        receipt_hash=receipt["receipt_hash"],
        workstream_id="monster-v5-step4",
        continuation_packet_hash=packet,
        expected_revision=consumed["state"]["revision"],
        expected_state_hash=consumed["state"]["state_hash"],
    )
    stale = heartbeat_worker(
        recovered,
        workstream_id="monster-v5-step4",
        owner_id="worker:b",
        scope_lease_id="lease:b",
        continuation_packet_hash=packet,
        now_utc="2026-10-01T00:01:10Z",
        expected_revision=0,
        expected_state_hash="0" * 64,
    )
    drift = inspect_dead_man(
        live,
        workstream_id="monster-v5-step4",
        continuation_packet_hash="b" * 64,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="failure",
    )
    result = {
        "status": "GREEN",
        "heartbeat_liveness": live_check["decision"] == "WORKER_HEARTBEAT_LIVE",
        "running_job_blocks_takeover": active_after_expiry["decision"] == "AUTHORITATIVE_RUN_STILL_ACTIVE",
        "dead_worker_terminal_run_recoverable": eligible["recovery_allowed"] is True,
        "safe_takeover_receipt": receipt["decision"] == "DEAD_MAN_RECOVERY_RECEIPT_ISSUED",
        "takeover_never_grants_mutation": receipt["grants_mutation_authority"] is False,
        "step_2a_remains_mandatory": receipt["requires_step_2a"] is True,
        "scope_lease_remains_mandatory": receipt["requires_scope_lease"] is True,
        "recovery_receipt_one_shot": replay["result"]["decision"] == "RECOVERY_RECEIPT_REPLAY_BLOCKED",
        "stale_cas_fails_closed": stale["result"]["decision"] == "HEARTBEAT_STATE_STALE_CAS_CONTINUE",
        "continuation_drift_fails_closed": drift["decision"] == "CONTINUATION_DRIFT_BLOCKED",
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
    }
    if not all(v is True for k, v in result.items() if k not in {"status", "product_runtime_mutation", "network_calls", "auto_mutate"}):
        raise HeartbeatRecoveryFailure(f"contract self-test failed: {result}")
    if any(result[k] for k in ("product_runtime_mutation", "network_calls", "auto_mutate")):
        raise HeartbeatRecoveryFailure(f"unsafe Step-4 capability enabled: {result}")
    return result


def main() -> int:
    print("MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
