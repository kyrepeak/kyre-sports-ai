"""Universal Live Status Board V1 — Step 4 enforcement gate.

Makes the frozen Step-1 visible board contract mandatory for authoritative
execution updates while reusing Step-2 lease ownership and Step-3 heartbeat
liveness. This module is pure control-plane validation and grants no mutation
authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from devsystem.universal_live_status_board_ownership_v1 import (
    OwnershipResolutionFailure,
    bind_status_packet_to_authoritative_ownership,
)
from devsystem.universal_live_status_board_recovery_v1 import (
    RecoveryResolutionFailure,
    inspect_status_board_owner_liveness,
)
from devsystem.universal_live_status_board_v1 import (
    StatusBoardValidationFailure,
    render_status_board,
    validate_status_packet,
)

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0
CREATES_PARALLEL_OWNERSHIP_REGISTRY = False


class EnforcementGateFailure(RuntimeError):
    """Raised when an execution update cannot be authoritative."""


def _terminal(packet: Mapping[str, Any]) -> bool:
    return (
        packet.get("completion_percent") == 100.0
        and packet.get("status") == "GREEN"
        and packet.get("frozen") is True
        and packet.get("live_active_chat") == "NONE_TERMINAL"
    )


def enforce_execution_update(
    update: Mapping[str, Any],
    lease_state: Mapping[str, Any],
    heartbeat_state: Mapping[str, Any] | None,
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    now_utc: str,
    observed_run_state: str,
) -> dict[str, Any]:
    """Authorize one control-room update only when its live board is canonical.

    Active updates must satisfy Step 1, resolve to the exact Step-2 lease owner,
    and have a live Step-3 heartbeat. Terminal GREEN + FROZEN updates require
    zero live lease owners. In both cases, the visible board must exactly equal
    the deterministic Step-1 rendering of authoritative state.
    """

    if not isinstance(update, Mapping):
        raise EnforcementGateFailure("execution update must be a mapping")
    if "status_board" not in update:
        raise EnforcementGateFailure("status board required")
    if "visible_board" not in update:
        raise EnforcementGateFailure("visible board required")

    raw_packet = update["status_board"]
    if not isinstance(raw_packet, Mapping):
        raise EnforcementGateFailure("status board must be a mapping")

    try:
        normalized = validate_status_packet(raw_packet)
    except StatusBoardValidationFailure as exc:
        raise EnforcementGateFailure(f"invalid status board: {exc}") from exc

    if _terminal(normalized):
        try:
            authoritative = bind_status_packet_to_authoritative_ownership(
                normalized,
                lease_state,
                now_utc=now_utc,
            )
        except OwnershipResolutionFailure as exc:
            raise EnforcementGateFailure(str(exc)) from exc
    else:
        if not isinstance(heartbeat_state, Mapping):
            raise EnforcementGateFailure("active execution update requires heartbeat state")
        try:
            liveness = inspect_status_board_owner_liveness(
                lease_state,
                heartbeat_state,
                workstream_id=workstream_id,
                continuation_packet_hash=continuation_packet_hash,
                now_utc=now_utc,
                observed_run_state=observed_run_state,
            )
        except RecoveryResolutionFailure as exc:
            raise EnforcementGateFailure(str(exc)) from exc

        if liveness.get("decision") != "OWNER_HEARTBEAT_LIVE":
            raise EnforcementGateFailure(str(liveness.get("decision") or "OWNER_LIVENESS_NOT_AUTHORITATIVE"))

        try:
            authoritative = bind_status_packet_to_authoritative_ownership(
                normalized,
                lease_state,
                now_utc=now_utc,
            )
        except OwnershipResolutionFailure as exc:
            raise EnforcementGateFailure(str(exc)) from exc

    canonical_visible_board = render_status_board(authoritative)
    supplied_visible_board = update["visible_board"]
    if not isinstance(supplied_visible_board, str) or not supplied_visible_board.strip():
        raise EnforcementGateFailure("visible board required")
    if supplied_visible_board != canonical_visible_board:
        raise EnforcementGateFailure("visible board does not match authoritative board")

    return {
        "allowed": True,
        "decision": "AUTHORITATIVE_CONTROL_ROOM_UPDATE",
        "status_board": authoritative,
        "visible_board": canonical_visible_board,
        "requires_step_2a": True,
        "grants_mutation_authority": False,
        "network_calls": False,
        "github_actions_fallback": 0,
    }
