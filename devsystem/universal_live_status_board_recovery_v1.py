"""Universal Live Status Board V1 — Step 3 heartbeat + stale-owner recovery.

Pure control-plane adapter that composes the frozen Step-2 authoritative lease
ownership layer with the existing MONSTER V5 heartbeat/dead-man recovery
engine. It never creates a second ownership registry and never grants mutation
authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from devsystem.execution_heartbeat_deadman_recovery_v1 import (
    ACTIVE_RUN_STATES,
    TERMINAL_RUN_STATES,
    inspect_dead_man,
    issue_recovery_receipt,
    validate_state as validate_heartbeat_state,
)
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_lease_state
from devsystem.universal_live_status_board_ownership_v1 import (
    OwnershipResolutionFailure,
    bind_status_packet_to_authoritative_ownership,
    resolve_authoritative_chat_ownership,
)

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0
CREATES_PARALLEL_OWNERSHIP_REGISTRY = False


class RecoveryResolutionFailure(RuntimeError):
    """Raised when heartbeat, lease, or continuation identity cannot be reconciled."""


def _utc(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise RecoveryResolutionFailure("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validated_lease_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return validate_lease_state(payload)
    except Exception as exc:
        raise RecoveryResolutionFailure("invalid authoritative lease state") from exc


def _validated_heartbeat_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return validate_heartbeat_state(payload)
    except Exception as exc:
        raise RecoveryResolutionFailure("invalid authoritative heartbeat state") from exc


def _worker_for(state: Mapping[str, Any], workstream_id: str) -> dict[str, Any]:
    worker = next(
        (dict(item) for item in state["workers"] if item["workstream_id"] == str(workstream_id)),
        None,
    )
    if worker is None:
        raise RecoveryResolutionFailure("heartbeat worker not found for workstream")
    return worker


def _holder_for_worker(lease_state: Mapping[str, Any], worker: Mapping[str, Any]) -> dict[str, Any]:
    holder = next(
        (
            dict(item)
            for item in lease_state["holders"]
            if item["lease_id"] == worker["scope_lease_id"]
        ),
        None,
    )
    if holder is None:
        raise RecoveryResolutionFailure("heartbeat lease missing from authoritative lease state")
    if holder["owner_id"] != worker["owner_id"]:
        raise RecoveryResolutionFailure("heartbeat owner does not match authoritative lease owner")
    return holder


def _live_holders(lease_state: Mapping[str, Any], now_utc: str) -> list[dict[str, Any]]:
    now = _utc(now_utc)
    return [
        dict(holder)
        for holder in lease_state["holders"]
        if now < _utc(holder["expires_at_utc"])
    ]


def inspect_status_board_owner_liveness(
    lease_state: Mapping[str, Any],
    heartbeat_state: Mapping[str, Any],
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    now_utc: str,
    observed_run_state: str,
) -> dict[str, Any]:
    """Reconcile scope-lease truth with heartbeat/run liveness.

    Recovery is allowed only after the heartbeat is stale, the authoritative run
    is terminal, and the old scope lease is no longer live. Unknown run state,
    continuation drift, identity drift, or a still-live lease all fail closed.
    """

    lease = _validated_lease_state(lease_state)
    heartbeat = _validated_heartbeat_state(heartbeat_state)
    worker = _worker_for(heartbeat, workstream_id)
    holder = _holder_for_worker(lease, worker)

    if worker["continuation_packet_hash"] != str(continuation_packet_hash):
        return {
            "decision": "CONTINUATION_DRIFT_BLOCKED",
            "recovery_allowed": False,
            "next_legal_action": "RESTORE_CANONICAL_CONTINUATION_PACKET",
        }

    run_state = str(observed_run_state or "").strip().lower()
    now = _utc(now_utc)
    heartbeat_live = now < _utc(worker["expires_at_utc"])
    lease_live = now < _utc(holder["expires_at_utc"])

    if heartbeat_live:
        if not lease_live:
            raise RecoveryResolutionFailure("heartbeat live while authoritative scope lease is expired")
        try:
            ownership = resolve_authoritative_chat_ownership(lease, now_utc=now_utc)
        except OwnershipResolutionFailure as exc:
            raise RecoveryResolutionFailure(str(exc)) from exc
        if ownership["authoritative_owner"] != worker["owner_id"]:
            raise RecoveryResolutionFailure("heartbeat owner does not match authoritative lease owner")
        if ownership["scope_lease_id"] != worker["scope_lease_id"]:
            raise RecoveryResolutionFailure("heartbeat lease does not match authoritative scope lease")
        return {
            "decision": "OWNER_HEARTBEAT_LIVE",
            "recovery_allowed": False,
            "next_legal_action": "WAIT_FOR_MATERIAL_EVENT",
            **ownership,
        }

    if run_state in ACTIVE_RUN_STATES:
        return {
            "decision": "OWNER_RUN_ACTIVE_HEARTBEAT_STALE",
            "recovery_allowed": False,
            "next_legal_action": "WAIT_FOR_RUN_TERMINAL_EVENT",
            "authoritative_owner": worker["owner_id"],
            "scope_lease_id": worker["scope_lease_id"],
        }

    if run_state not in TERMINAL_RUN_STATES:
        return {
            "decision": "RUN_STATE_UNKNOWN_FAIL_CLOSED",
            "recovery_allowed": False,
            "next_legal_action": "VERIFY_AUTHORITATIVE_RUN_STATE",
        }

    if lease_live:
        return {
            "decision": "STALE_HEARTBEAT_LIVE_LEASE_BLOCKS_RECOVERY",
            "recovery_allowed": False,
            "next_legal_action": "WAIT_FOR_SCOPE_LEASE_EXPIRY_OR_OWNER_RENEWAL",
            "authoritative_owner": worker["owner_id"],
            "scope_lease_id": worker["scope_lease_id"],
        }

    dead_man = inspect_dead_man(
        heartbeat,
        workstream_id=workstream_id,
        continuation_packet_hash=continuation_packet_hash,
        now_utc=now_utc,
        observed_run_state=run_state,
    )
    if dead_man.get("recovery_allowed") is not True:
        return dead_man

    return {
        "decision": "STALE_OWNER_RECOVERY_ELIGIBLE",
        "recovery_allowed": True,
        "previous_owner_id": worker["owner_id"],
        "previous_scope_lease_id": worker["scope_lease_id"],
        "authoritative_run_id": worker["authoritative_run_id"],
        "observed_run_state": run_state,
        "requires_step_2a": True,
        "requires_new_scope_lease": True,
        "grants_mutation_authority": False,
    }


def issue_status_board_recovery(
    lease_state: Mapping[str, Any],
    heartbeat_state: Mapping[str, Any],
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    now_utc: str,
    observed_run_state: str,
    new_owner_id: str,
    new_scope_lease_id: str,
    expected_heartbeat_revision: int,
    expected_heartbeat_state_hash: str,
) -> dict[str, Any]:
    inspection = inspect_status_board_owner_liveness(
        lease_state,
        heartbeat_state,
        workstream_id=workstream_id,
        continuation_packet_hash=continuation_packet_hash,
        now_utc=now_utc,
        observed_run_state=observed_run_state,
    )
    heartbeat = _validated_heartbeat_state(heartbeat_state)
    if inspection.get("recovery_allowed") is not True:
        return {"result": {**inspection, "allowed": False}, "state": heartbeat}

    return issue_recovery_receipt(
        heartbeat,
        workstream_id=workstream_id,
        continuation_packet_hash=continuation_packet_hash,
        now_utc=now_utc,
        observed_run_state=observed_run_state,
        new_owner_id=new_owner_id,
        new_scope_lease_id=new_scope_lease_id,
        expected_revision=expected_heartbeat_revision,
        expected_state_hash=expected_heartbeat_state_hash,
    )


def bind_status_packet_to_recovered_owner(
    packet: Mapping[str, Any],
    lease_state: Mapping[str, Any],
    heartbeat_state: Mapping[str, Any],
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    now_utc: str,
) -> dict[str, Any]:
    """Bind an active packet only when lease + heartbeat agree on recovered owner."""

    lease = _validated_lease_state(lease_state)
    heartbeat = _validated_heartbeat_state(heartbeat_state)
    worker = _worker_for(heartbeat, workstream_id)

    if worker["continuation_packet_hash"] != str(continuation_packet_hash):
        raise RecoveryResolutionFailure("continuation packet does not match heartbeat identity")

    try:
        ownership = resolve_authoritative_chat_ownership(lease, now_utc=now_utc)
    except OwnershipResolutionFailure as exc:
        raise RecoveryResolutionFailure(str(exc)) from exc

    if worker["owner_id"] != ownership["authoritative_owner"]:
        raise RecoveryResolutionFailure("heartbeat owner does not match authoritative lease owner")
    if worker["scope_lease_id"] != ownership["scope_lease_id"]:
        raise RecoveryResolutionFailure("heartbeat lease does not match authoritative scope lease")
    if _utc(now_utc) >= _utc(worker["expires_at_utc"]):
        raise RecoveryResolutionFailure("recovered owner heartbeat is stale")

    try:
        return bind_status_packet_to_authoritative_ownership(packet, lease, now_utc=now_utc)
    except OwnershipResolutionFailure as exc:
        raise RecoveryResolutionFailure(str(exc)) from exc
