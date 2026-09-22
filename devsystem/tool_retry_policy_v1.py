"""Permission separation and sticky terminal-failure retry policy."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


_BLOCKED_CAPABILITY_STATES = {
    "PERMISSION_BLOCKED",
    "POLICY_BLOCKED",
    "UNAVAILABLE",
    "DENIED",
    "FORBIDDEN",
}
_TERMINAL_FAILURE_STATES = {
    "PERMISSION_BLOCKED",
    "POLICY_BLOCKED",
    "FAILED",
    "ERROR",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _action_fingerprint(
    *,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
    relevant_inputs: Mapping[str, Any] | None,
) -> str:
    return _fingerprint(
        {
            "tool_name": tool_name,
            "arguments": dict(arguments or {}),
            "relevant_inputs": dict(relevant_inputs or {}),
        }
    )


def record_terminal_failure(
    *,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
    relevant_inputs: Mapping[str, Any] | None,
    failure_state: str,
) -> dict[str, Any]:
    """Record a terminal failure that must remain sticky for identical state."""
    normalized = str(failure_state or "").strip().upper()
    if normalized not in _TERMINAL_FAILURE_STATES:
        raise ValueError(f"failure_state must be terminal, got {failure_state!r}")

    return {
        "tool_name": tool_name,
        "arguments": dict(arguments or {}),
        "relevant_inputs": dict(relevant_inputs or {}),
        "action_fingerprint": _action_fingerprint(
            tool_name=tool_name,
            arguments=arguments,
            relevant_inputs=relevant_inputs,
        ),
        "failure_state": normalized,
        "terminal": True,
    }


def decide_retry(
    *,
    user_approved: bool,
    capability_state: str,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
    relevant_inputs: Mapping[str, Any] | None,
    failure_history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Decide whether an action may be attempted again.

    User approval expresses authorization intent; it never upgrades connector or
    GitHub capability.  Terminal failures remain locked for the exact same
    action + relevant inputs and are released only after meaningful state
    changes produce a different fingerprint.
    """
    capability = str(capability_state or "").strip().upper()

    if capability in _BLOCKED_CAPABILITY_STATES:
        return {
            "decision": "DENIED_CAPABILITY",
            "approval_is_not_capability": True,
            "requires_state_change": True,
            "capability_state": capability,
        }

    if not user_approved:
        return {
            "decision": "DENIED_NOT_APPROVED",
            "approval_is_not_capability": True,
            "requires_state_change": False,
            "capability_state": capability,
        }

    proposed = _action_fingerprint(
        tool_name=tool_name,
        arguments=arguments,
        relevant_inputs=relevant_inputs,
    )

    for failure in reversed(failure_history):
        if failure.get("action_fingerprint") != proposed:
            continue
        failure_state = str(failure.get("failure_state") or "").strip().upper()
        if failure.get("terminal") is True or failure_state in _TERMINAL_FAILURE_STATES:
            return {
                "decision": "DENIED_STICKY_FAILURE",
                "approval_is_not_capability": True,
                "requires_state_change": True,
                "failure_state": failure_state,
                "action_fingerprint": proposed,
            }

    return {
        "decision": "ALLOW",
        "approval_is_not_capability": True,
        "requires_state_change": False,
        "capability_state": capability,
        "action_fingerprint": proposed,
    }
