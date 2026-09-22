"""Adversarial regression tests for the Monster Agent Anti-Loop stack."""
from __future__ import annotations

from devsystem import github_state_resolver_v1 as resolver
from devsystem import tool_orchestration_guard_v1 as guard
from devsystem import tool_retry_policy_v1 as retry


def _observation(*, head_sha: str, state: str, args=None):
    return guard.record_tool_observation(
        tool_name="GitHub.get_pr_info",
        arguments=args or {"repository_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": head_sha},
        observation={"required_check": "devsystem-final-gate", "state": state},
    )


def test_changed_head_sha_releases_no_progress_lock():
    history = [
        _observation(head_sha="abc123", state="pending"),
        _observation(head_sha="abc123", state="pending"),
    ]
    result = guard.decide_tool_call(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "def456"},
        history=history,
    )
    assert result["decision"] == "ALLOW"
    assert result["equivalent_observations"] == 0


def test_changed_observation_resets_equivalent_observation_counter():
    history = [
        _observation(head_sha="abc123", state="queued"),
        _observation(head_sha="abc123", state="running"),
    ]
    result = guard.decide_tool_call(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123"},
        history=history,
    )
    assert result["decision"] == "ALLOW"
    assert result["equivalent_observations"] == 1


def test_argument_key_order_does_not_evade_duplicate_detection():
    history = [
        _observation(
            head_sha="abc123",
            state="pending",
            args={"repository_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        ),
        _observation(
            head_sha="abc123",
            state="pending",
            args={"pr_number": 508, "repository_full_name": "kyrepeak/kyre-sports-ai"},
        ),
    ]
    result = guard.decide_tool_call(
        tool_name="GitHub.get_pr_info",
        arguments={"pr_number": 508, "repository_full_name": "kyrepeak/kyre-sports-ai"},
        relevant_inputs={"head_sha": "abc123"},
        history=history,
    )
    assert result["decision"] == "DENIED_NO_PROGRESS"


def test_resolver_preserves_meaningful_state_transitions():
    assert resolver.resolve_github_state(check={"status": "pending"})["state"] == "QUEUED"
    assert resolver.resolve_github_state(check={"status": "running"})["state"] == "RUNNING"
    assert resolver.resolve_github_state(
        check={"status": "completed", "conclusion": "cancelled"}
    )["state"] == "FAILED"
    assert resolver.resolve_github_state(
        check={"status": "completed", "conclusion": "action_required"}
    )["state"] == "POLICY_BLOCKED"


def test_permission_and_policy_blocks_are_terminal():
    permission = resolver.resolve_github_state(
        error={"status_code": 403, "message": "Resource not accessible by integration"}
    )
    policy = resolver.resolve_github_state(
        error={"status_code": 422, "message": "branch protection required status check"}
    )
    assert permission == {"state": "PERMISSION_BLOCKED", "terminal": True, "source": "error"}
    assert policy == {"state": "POLICY_BLOCKED", "terminal": True, "source": "error"}


def test_sticky_failure_releases_only_after_relevant_state_change():
    failure = retry.record_terminal_failure(
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123", "required_check": "failed"},
        failure_state="POLICY_BLOCKED",
    )

    denied = retry.decide_retry(
        user_approved=True,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123", "required_check": "failed"},
        failure_history=[failure],
    )
    assert denied["decision"] == "DENIED_STICKY_FAILURE"

    allowed = retry.decide_retry(
        user_approved=True,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123", "required_check": "success"},
        failure_history=[failure],
    )
    assert allowed["decision"] == "ALLOW"


def test_unapproved_action_stays_denied_even_when_capability_exists():
    result = retry.decide_retry(
        user_approved=False,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": "kyrepeak/kyre-sports-ai", "pr_number": 508},
        relevant_inputs={"head_sha": "abc123"},
        failure_history=[],
    )
    assert result["decision"] == "DENIED_NOT_APPROVED"
