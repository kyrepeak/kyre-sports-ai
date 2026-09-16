"""Pre-execution no-progress guard for tool orchestration.

This module complements the repo/task-level Anti-Loop V2 controller.  It models
one narrow but important rule at a connector boundary: when the same proposed
tool call, with the same relevant inputs, has already produced the same
observation twice, the third equivalent call must be denied until strategy or
relevant state changes.

The guard is intentionally dependency-light so CI and other repo-controlled
orchestrators can use it before executing an external tool call.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


NO_PROGRESS_LIMIT = 2


def _canonical_json(value: Any) -> str:
    """Return a deterministic representation for JSON-like orchestration data."""
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


def record_tool_observation(
    *,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
    relevant_inputs: Mapping[str, Any] | None,
    observation: Any,
) -> dict[str, Any]:
    """Create a history record after a tool call has produced an observation."""
    return {
        "tool_name": tool_name,
        "arguments": dict(arguments or {}),
        "relevant_inputs": dict(relevant_inputs or {}),
        "action_fingerprint": _action_fingerprint(
            tool_name=tool_name,
            arguments=arguments,
            relevant_inputs=relevant_inputs,
        ),
        "observation": observation,
        "observation_fingerprint": _fingerprint(observation),
    }


def decide_tool_call(
    *,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
    relevant_inputs: Mapping[str, Any] | None,
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Decide whether a proposed tool call may execute.

    The check is pre-execution.  Relevant-input changes (for example a new head
    SHA) produce a new action fingerprint and therefore reset the no-progress
    counter.  A changed observation also resets the consecutive equivalent
    observation counter.
    """
    proposed = _action_fingerprint(
        tool_name=tool_name,
        arguments=arguments,
        relevant_inputs=relevant_inputs,
    )

    matching = [entry for entry in history if entry.get("action_fingerprint") == proposed]
    equivalent_observations = 0

    if matching:
        latest_observation = matching[-1].get("observation_fingerprint")
        for entry in reversed(matching):
            if entry.get("observation_fingerprint") != latest_observation:
                break
            equivalent_observations += 1

    if equivalent_observations >= NO_PROGRESS_LIMIT:
        return {
            "decision": "DENIED_NO_PROGRESS",
            "equivalent_observations": equivalent_observations,
            "requires_strategy_change": True,
            "action_fingerprint": proposed,
        }

    return {
        "decision": "ALLOW",
        "equivalent_observations": equivalent_observations,
        "requires_strategy_change": False,
        "action_fingerprint": proposed,
    }
