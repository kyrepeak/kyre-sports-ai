"""Regression tests for the tool-orchestration no-progress guard.

These tests live above the existing task/root-cause Anti-Loop V2 controller.
They model the assistant/tool boundary: after two equivalent observations on
unchanged relevant inputs, a third equivalent call must be denied before the
tool executes again.
"""
from __future__ import annotations

import importlib

import pytest


MODULE = "devsystem.tool_orchestration_guard_v1"


def _guard():
    try:
        return importlib.import_module(MODULE)
    except ModuleNotFoundError:
        pytest.fail(
            "tool-orchestration guard is missing; third unchanged connector calls "
            "are not mechanically blocked before execution"
        )


def _observation(guard, *, head_sha: str = "abc123", check_state: str = "pending"):
    return guard.record_tool_observation(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": head_sha},
        observation={"required_check": "devsystem-final-gate", "state": check_state},
    )


def test_third_unchanged_tool_observation_is_denied_before_execution():
    guard = _guard()
    history = [_observation(guard), _observation(guard)]

    result = guard.decide_tool_call(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123"},
        history=history,
    )

    assert result["decision"] == "DENIED_NO_PROGRESS"
    assert result["equivalent_observations"] == 2
    assert result["requires_strategy_change"] is True
