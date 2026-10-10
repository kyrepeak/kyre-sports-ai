"""Universal Live Status Board V1 — Step 2 authoritative chat ownership.

Read-only ownership binding layered on top of the frozen Step-1 status schema.
The existing scope-aware execution lease is the only ownership source of truth.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_lease_state
from devsystem.universal_live_status_board_v1 import validate_status_packet

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

MONSTER_OWNER_PREFIX = "chatgpt:monster-v2:"
API2_OWNER_PREFIX = "chatgpt:api2:"


class OwnershipResolutionFailure(RuntimeError):
    """Raised when authoritative ownership cannot be resolved safely."""


def _utc_timestamp(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise OwnershipResolutionFailure("invalid authoritative lease timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validated_authoritative_lease_state(lease_state: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return validate_lease_state(lease_state)
    except Exception as exc:
        raise OwnershipResolutionFailure("invalid authoritative lease state") from exc


def _live_authoritative_holders(
    lease_state: Mapping[str, Any],
    *,
    now_utc: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = _validated_authoritative_lease_state(lease_state)
    now = _utc_timestamp(now_utc)
    live = [
        dict(holder)
        for holder in state["holders"]
        if now < _utc_timestamp(holder["expires_at_utc"])
    ]
    return state, live


def _chat_for_owner(owner_id: str) -> str:
    owner = str(owner_id or "").strip()
    if owner.startswith(MONSTER_OWNER_PREFIX):
        return "MONSTER"
    if owner.startswith(API2_OWNER_PREFIX):
        return "API_2"
    return "THIS_CHAT"


def resolve_authoritative_chat_ownership(
    lease_state: Mapping[str, Any],
    *,
    now_utc: str,
) -> dict[str, Any]:
    """Resolve exactly one live lease holder; never guess active ownership."""
    state, live = _live_authoritative_holders(lease_state, now_utc=now_utc)
    if not live:
        raise OwnershipResolutionFailure("no live authoritative owner")
    if len(live) != 1:
        raise OwnershipResolutionFailure("ambiguous live authoritative ownership")

    holder = live[0]
    owner = str(holder["owner_id"])
    return {
        "live_active_chat": _chat_for_owner(owner),
        "authoritative_owner": owner,
        "scope_lease_id": str(holder["lease_id"]),
        "lease_revision": int(state["revision"]),
        "lease_state_hash": str(state["state_hash"]),
    }


def _packet_is_terminal(packet: Mapping[str, Any]) -> bool:
    if not isinstance(packet, Mapping):
        return False
    value = packet.get("completion_percent")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    completion = float(value)
    return (
        math.isfinite(completion)
        and completion == 100.0
        and packet.get("status") == "GREEN"
        and packet.get("frozen") is True
    )


def bind_status_packet_to_authoritative_ownership(
    packet: Mapping[str, Any],
    lease_state: Mapping[str, Any],
    *,
    now_utc: str,
) -> dict[str, Any]:
    """Overwrite manual ownership fields with validated lease truth.

    Terminal GREEN + FROZEN packets require zero live holders. Active packets
    require exactly one live holder and inherit its authoritative identity.
    """
    state, live = _live_authoritative_holders(lease_state, now_utc=now_utc)
    bound = dict(packet)

    if _packet_is_terminal(bound):
        if live:
            raise OwnershipResolutionFailure("terminal packet cannot retain a live owner")
        bound.update(
            {
                "live_active_chat": "NONE_TERMINAL",
                "authoritative_owner": None,
                "scope_lease_id": None,
                "lease_revision": int(state["revision"]),
                "lease_state_hash": str(state["state_hash"]),
            }
        )
        return validate_status_packet(bound)

    resolution = resolve_authoritative_chat_ownership(state, now_utc=now_utc)
    bound.update(resolution)
    return validate_status_packet(bound)
