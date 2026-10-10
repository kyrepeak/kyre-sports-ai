"""Universal Live Status Board V1 — Step 1 mandatory status schema.

Pure validation/rendering only. This module does not infer ownership, acquire
leases, perform network calls, or mutate product/runtime state.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

STATUSES = frozenset({"RED", "YELLOW", "GREEN"})
ACTIVE_CHATS = frozenset({"THIS_CHAT", "MONSTER", "API_2", "NONE_TERMINAL"})
MANDATORY_FIELDS = ("completion_percent", "status", "live_active_chat")


class StatusBoardValidationFailure(RuntimeError):
    """Raised when a status packet violates the Step-1 contract."""


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
