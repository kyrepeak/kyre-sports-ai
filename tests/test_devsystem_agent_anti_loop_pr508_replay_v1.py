"""End-to-end replay of the PR #508 assistant/tool loop failure pattern.

This certifies the repo-controlled orchestration policy. It intentionally does
not claim that repository code can intercept arbitrary native ChatGPT connector
calls unless the caller routes actions through these guards.
"""
from __future__ import annotations

from devsystem import github_state_resolver_v1 as resolver
from devsystem import tool_orchestration_guard_v1 as guard
from devsystem import tool_retry_policy_v1 as retry


REPO = "kyrepeak/kyre-sports-ai"
PR = 508


def _record_check(*, head_sha: str, poll_epoch: str, state: str):
    return guard.record_tool_observation(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": head_sha, "poll_epoch": poll_epoch},
        observation={"required_check": "devsystem-final-gate", "state": state},
    )


def test_pr508_replay_observe_diagnose_fix_verify_without_blind_loop():
    # First two reads see the same queued state.
    assert resolver.resolve_github_state(check={"status": "queued"})["state"] == "QUEUED"
    history = [
        _record_check(head_sha="head-a", poll_epoch="initial", state="QUEUED"),
        _record_check(head_sha="head-a", poll_epoch="initial", state="QUEUED"),
    ]

    # A third equivalent read is denied before execution.
    third = guard.decide_tool_call(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-a", "poll_epoch": "initial"},
        history=history,
    )
    assert third["decision"] == "DENIED_NO_PROGRESS"
    assert third["requires_strategy_change"] is True

    # After an intentional wait/external-event boundary, a fresh observation is
    # allowed. This prevents the circuit breaker from becoming a permanent lock.
    after_wait = guard.decide_tool_call(
        tool_name="GitHub.get_pr_info",
        arguments={"repository_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-a", "poll_epoch": "after-wait-1"},
        history=history,
    )
    assert after_wait["decision"] == "ALLOW"
    assert resolver.resolve_github_state(check={"status": "in_progress"})["state"] == "RUNNING"

    # The eventual branch-protection failure is a policy state, not generic
    # 'pending', and user approval cannot override it.
    blocked = resolver.resolve_github_state(
        error={"status_code": 422, "message": "Required status check policy blocks merge"}
    )
    assert blocked["state"] == "POLICY_BLOCKED"
    assert blocked["terminal"] is True

    capability_denial = retry.decide_retry(
        user_approved=True,
        capability_state=blocked["state"],
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-a", "required_check": "failure"},
        failure_history=[],
    )
    assert capability_denial["decision"] == "DENIED_CAPABILITY"
    assert capability_denial["approval_is_not_capability"] is True

    # Once observed, the terminal policy failure is sticky: simply trying the
    # merge again with the same state is denied even if capability later reports
    # available.
    failure = retry.record_terminal_failure(
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-a", "required_check": "failure"},
        failure_state="POLICY_BLOCKED",
    )
    blind_retry = retry.decide_retry(
        user_approved=True,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-a", "required_check": "failure"},
        failure_history=[failure],
    )
    assert blind_retry["decision"] == "DENIED_STICKY_FAILURE"

    # A meaningful state change (the real fix/new head/check success) releases
    # the lock and allows forward motion.
    assert resolver.resolve_github_state(
        check={"status": "completed", "conclusion": "success"}
    )["state"] == "SUCCESS"
    fixed_retry = retry.decide_retry(
        user_approved=True,
        capability_state="AVAILABLE",
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-b", "required_check": "success"},
        failure_history=[failure],
    )
    assert fixed_retry["decision"] == "ALLOW"


def test_permission_block_remains_separate_from_user_approval():
    state = resolver.resolve_github_state(
        error={"status_code": 403, "message": "Resource not accessible by integration"}
    )
    result = retry.decide_retry(
        user_approved=True,
        capability_state=state["state"],
        tool_name="GitHub.merge_pull_request",
        arguments={"repo_full_name": REPO, "pr_number": PR},
        relevant_inputs={"head_sha": "head-a"},
        failure_history=[],
    )
    assert state["state"] == "PERMISSION_BLOCKED"
    assert result["decision"] == "DENIED_CAPABILITY"
