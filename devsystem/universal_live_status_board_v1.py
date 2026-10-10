"""Universal Live Status Board V1 — mandatory schema + ownership binding.

Steps 1-2 are deliberately pure/read-only. This module validates and renders
status packets, then binds active-chat identity to the existing scope-aware
execution lease truth. It does not acquire/renew/release leases, perform
network calls, or mutate product/runtime state.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_lease_state

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

STATUSES = frozenset({"RED", "YELLOW", "GREEN"})
ACTIVE_CHATS = frozenset({"THIS_CHAT", "MONSTER", "API_2", "NONE_TERMINAL"})
MANDATORY_FIELDS = ("completion_percent", "status", "live_active_chat")

MONSTER_OWNER_PREFIX = "chatgpt:monster-v2:"
API2_OWNER_PREFIX = "chatgpt:api2:"


class StatusBoardValidationFailure(RuntimeError):
    """Raised when a status packet violates the Step-1 contract."""


class OwnershipResolutionFailure(RuntimeError):
    """Raised when authoritative Step-2 ownership cannot be resolved safely."""


def _completion_percent(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StatusBoardValidationFailure("completion_percent must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0 or normalized > 100.0:
        raise StatusBoardValidationFailure("completion_percent must be finite and within 0..100")
    return normalized


def validate_status_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        raise StatusBoardValidationFailure("status packet must be a mapping")

    missing = [field for field in MANDATORY_FIELDS if field not in packet]
    if missing:
        raise StatusBoardValidationFailure("missing mandatory field: " + ",".join(missing))

    out = dict(packet)
    out["completion_percent"] = _completion_percent(packet["completion_percent"])

    status = str(packet["status"])
    if status not in STATUSES:
        raise StatusBoardValidationFailure("unknown status")
    out["status"] = status

    active_chat = str(packet["live_active_chat"])
    if active_chat not in ACTIVE_CHATS:
        raise StatusBoardValidationFailure("unknown live_active_chat")
    out["live_active_chat"] = active_chat

    frozen = packet.get("frozen", False)
    if not isinstance(frozen, bool):
        raise StatusBoardValidationFailure("frozen must be boolean")
    out["frozen"] = frozen
    out["current_blocker"] = packet.get("current_blocker")
    out["next_legal_action"] = packet.get("next_legal_action")
    out["current_step"] = packet.get("current_step")
    out["overall_progress_percent"] = packet.get("overall_progress_percent")
    out["authoritative_owner"] = packet.get("authoritative_owner")
    out["scope_lease_id"] = packet.get("scope_lease_id")

    completion = out["completion_percent"]

    if completion == 100.0 and status != "GREEN":
        raise StatusBoardValidationFailure("100 percent requires GREEN")

    if status == "RED":
        blocker = out["current_blocker"]
        if not isinstance(blocker, str) or not blocker.strip():
            raise StatusBoardValidationFailure("RED requires current_blocker")

    if status == "YELLOW" and frozen:
        raise StatusBoardValidationFailure("YELLOW cannot be frozen")

    if frozen and (status != "GREEN" or completion != 100.0):
        raise StatusBoardValidationFailure("frozen requires GREEN at 100 percent")

    terminal = status == "GREEN" and completion == 100.0 and frozen
    if active_chat == "NONE_TERMINAL" and not terminal:
        raise StatusBoardValidationFailure("NONE_TERMINAL requires terminal state")
    if terminal and active_chat != "NONE_TERMINAL":
        raise StatusBoardValidationFailure("terminal state requires NONE_TERMINAL")

    return out


def _format_percent(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return format(value, ".12g")


def render_status_board(packet: Mapping[str, Any]) -> str:
    normalized = validate_status_packet(packet)
    status_text = normalized["status"]
    if normalized["frozen"] and status_text == "GREEN":
        status_text = "GREEN + FROZEN"

    blocker = normalized["current_blocker"]
    action = normalized["next_legal_action"]
    blocker_text = str(blocker) if blocker is not None else "none"
    action_text = str(action) if action is not None else "none"

    return "\n".join(
        [
            "UNIVERSAL LIVE STATUS BOARD",
            f"Completion: {_format_percent(normalized['completion_percent'])}%",
            f"Status: {status_text}",
            f"Live Active Chat: {normalized['live_active_chat']}",
            f"Current Blocker: {blocker_text}",
            f"Next Legal Action: {action_text}",
        ]
    )


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
    """Resolve one live lease holder to the board's authoritative chat label.

    This is fail-closed: an active board must never guess when ownership is
    absent or ambiguous.
    """

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

    Terminal GREEN + FROZEN packets are only legal after all live holders have
    disappeared. Active packets require exactly one live holder.
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
