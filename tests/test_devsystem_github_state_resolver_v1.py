"""Contract tests for explicit GitHub check-state resolution."""
from __future__ import annotations

import importlib

import pytest


MODULE = "devsystem.github_state_resolver_v1"


def _resolver():
    try:
        return importlib.import_module(MODULE)
    except ModuleNotFoundError:
        pytest.fail(
            "GitHub state resolver is missing; orchestration cannot reliably "
            "distinguish missing/queued/running/failed/success/blocked states"
        )


@pytest.mark.parametrize(
    ("check", "error", "expected"),
    [
        (None, None, "MISSING"),
        ({"status": "queued", "conclusion": None}, None, "QUEUED"),
        ({"status": "in_progress", "conclusion": None}, None, "RUNNING"),
        ({"status": "completed", "conclusion": "failure"}, None, "FAILED"),
        ({"status": "completed", "conclusion": "success"}, None, "SUCCESS"),
        (None, {"status_code": 403, "message": "Resource not accessible by integration"}, "PERMISSION_BLOCKED"),
        (None, {"status_code": 422, "message": "Required status check policy blocks merge"}, "POLICY_BLOCKED"),
    ],
)
def test_resolves_github_states_without_collapsing_them_to_pending(check, error, expected):
    resolver = _resolver()
    result = resolver.resolve_github_state(check=check, error=error)
    assert result["state"] == expected


def test_terminal_flag_is_explicit():
    resolver = _resolver()
    assert resolver.resolve_github_state(check={"status": "queued"})["terminal"] is False
    assert resolver.resolve_github_state(check={"status": "completed", "conclusion": "success"})["terminal"] is True
    assert resolver.resolve_github_state(check={"status": "completed", "conclusion": "failure"})["terminal"] is True
    assert resolver.resolve_github_state(error={"status_code": 403, "message": "forbidden"})["terminal"] is True
