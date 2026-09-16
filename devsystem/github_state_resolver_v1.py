"""Normalize GitHub workflow/check/error observations into explicit states."""
from __future__ import annotations

from typing import Any, Mapping


_TERMINAL_STATES = {"FAILED", "SUCCESS", "PERMISSION_BLOCKED", "POLICY_BLOCKED", "ERROR"}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def resolve_github_state(
    *,
    check: Mapping[str, Any] | None = None,
    error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a GitHub observation without collapsing unlike states to pending."""
    if error:
        status_code = error.get("status_code") or error.get("status") or error.get("code")
        message = _text(error.get("message"))
        code_text = _text(status_code)

        if code_text in {"401", "403"} or any(
            token in message
            for token in (
                "forbidden",
                "permission",
                "not accessible by integration",
                "resource not accessible",
            )
        ):
            state = "PERMISSION_BLOCKED"
        elif code_text == "422" or any(
            token in message
            for token in (
                "branch protection",
                "required status check",
                "policy blocks",
                "protected branch",
            )
        ):
            state = "POLICY_BLOCKED"
        else:
            state = "ERROR"

        return {
            "state": state,
            "terminal": state in _TERMINAL_STATES,
            "source": "error",
        }

    if not check:
        return {"state": "MISSING", "terminal": False, "source": "check"}

    status = _text(check.get("status") or check.get("state"))
    conclusion = _text(check.get("conclusion"))

    if status in {"queued", "pending", "requested", "waiting"}:
        state = "QUEUED"
    elif status in {"in_progress", "running"}:
        state = "RUNNING"
    elif status == "completed":
        if conclusion == "success":
            state = "SUCCESS"
        elif conclusion in {"failure", "cancelled", "timed_out", "startup_failure"}:
            state = "FAILED"
        elif conclusion in {"action_required", "stale"}:
            state = "POLICY_BLOCKED"
        else:
            state = "FAILED"
    elif conclusion == "success":
        state = "SUCCESS"
    elif conclusion in {"failure", "cancelled", "timed_out", "startup_failure"}:
        state = "FAILED"
    else:
        state = "MISSING"

    return {
        "state": state,
        "terminal": state in _TERMINAL_STATES,
        "source": "check",
    }
