"""NBA Over/Under Step 1 — fail-closed page-isolation contract.

This module owns only the NBA Step-1 isolation boundary. It deliberately does
not activate a Streamlit route, import another sport, or authorize shared-site
mutation. Later NBA steps must expand their own scope explicitly.
"""
from __future__ import annotations

from collections.abc import Iterable


MODEL_VERSION = "NBA_OVER_UNDER_STEP1_PAGE_ISOLATION_V1"
SPORT = "NBA"
PAGE_SCOPE = "NBA_OVER_UNDER"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SHARED_ROUTER = False
MAY_MODIFY_APP_ENTRYPOINT = False
MAY_MODIFY_SHARED_APIS = False

STEP1_OWNED_PATHS = frozenset(
    {
        "devsystem/change_classifier_v1.py",
        "devsystem/task_ledgers/nba-over-under-step1-page-isolation-v1.json",
        "nba_page_isolation_v1.py",
        "tests/test_devsystem_change_classifier_v1.py",
        "tests/test_nba_page_isolation_v1.py",
    }
)


class NBAIsolationViolation(RuntimeError):
    """Raised when a proposed Step-1 write escapes the NBA-owned boundary."""


def _normalize_path(value: object) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("../") or "/../" in path:
        raise NBAIsolationViolation(f"invalid path: {value!r}")
    return path


def assert_nba_only_change(paths: Iterable[object]) -> dict[str, object]:
    """Fail closed unless every proposed write belongs to NBA Step 1."""
    normalized = sorted({_normalize_path(path) for path in paths})
    if not normalized:
        raise NBAIsolationViolation("at least one changed path is required")

    escaped = [path for path in normalized if path not in STEP1_OWNED_PATHS]
    if escaped:
        raise NBAIsolationViolation(
            "NBA Step-1 scope escape blocked: " + ", ".join(escaped)
        )

    return {
        "status": "GREEN",
        "decision": "NBA_ONLY_CHANGE_ALLOWED",
        "sport": SPORT,
        "page_scope": PAGE_SCOPE,
        "changed_paths": normalized,
        "other_sports_modified": False,
        "shared_router_modified": False,
        "app_entrypoint_modified": False,
        "shared_apis_modified": False,
    }


__all__ = [
    "MODEL_VERSION",
    "SPORT",
    "PAGE_SCOPE",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_SHARED_ROUTER",
    "MAY_MODIFY_APP_ENTRYPOINT",
    "MAY_MODIFY_SHARED_APIS",
    "STEP1_OWNED_PATHS",
    "NBAIsolationViolation",
    "assert_nba_only_change",
]
