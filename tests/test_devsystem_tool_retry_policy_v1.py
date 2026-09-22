"""Contract tests for permission separation and sticky terminal failures."""
from __future__ import annotations

import importlib

import pytest


MODULE = "devsystem.tool_retry_policy_v1"


def _policy():
    try:
        return importlib.import_module(MODULE)
    except ModuleNotFoundError:
        pytest.fail(
            "tool retry policy is missing; approval can still be confused with capability "
            "and terminal failures are not sticky"
        )


def test_user_approval_does_not_override_missing_github_capability():
    policy = _policy()
    result = policy.decide_retry(
        user_approved=True,
        capability_state="PERMISSION_BLOCKED",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123"},
        failure_history=[],
    )
    assert result["decision"] == "DENIED_CAPABILITY"
    assert result["approval_is_not_capability"] is True


def test_terminal_failure_is_sticky_until_relevant_inputs_change():
    policy = _policy()
    failure = policy.record_terminal_failure(
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123", "required_check": "failed"},
        failure_state="POLICY_BLOCKED",
    )

    denied = policy.decide_retry(
        user_approved=True,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123", "required_check": "failed"},
        failure_history=[failure],
    )
    assert denied["decision"] == "DENIED_STICKY_FAILURE"
    assert denied["requires_state_change"] is True

    allowed = policy.decide_retry(
        user_approved=True,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "def456", "required_check": "success"},
        failure_history=[failure],
    )
    assert allowed["decision"] == "ALLOW"
