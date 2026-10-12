"""NBA Spread Step 1 — fail-closed page-isolation contract.

This module owns only the NBA Spread Step-1 mutation boundary. It does not
activate a Streamlit route, import another NBA workstream, touch another sport,
or authorize shared-site/API/control-plane mutation. Later NBA Spread steps
must expand their own scope explicitly.
"""
from __future__ import annotations

from collections.abc import Iterable


MODEL_VERSION = "NBA_SPREAD_STEP1_PAGE_ISOLATION_V1"
SPORT = "NBA"
PAGE_SCOPE = "NBA_SPREAD"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SHARED_ROUTER = False
MAY_MODIFY_APP_ENTRYPOINT = False
MAY_MODIFY_SHARED_APIS = False
MAY_MODIFY_EXISTING_NBA_WORKSTREAMS = False

STEP1_OWNED_PATHS = frozenset(
    {
        "devsystem/execution_plans/nba-spread-step1-page-isolation-v1.json",
        "devsystem/runless_proof_plans/nba-spread-step1-page-isolation-v1.json",
        "devsystem/task_ledgers/nba-spread-step1-page-isolation-v1.json",
        "nba_spread_page_isolation_v1.py",
        "tests/test_nba_spread_page_isolation_v1.py",
    }
)


class NBASpreadIsolationViolation(RuntimeError):
    """Raised when a proposed NBA Spread Step-1 write escapes its boundary."""


def _normalize_path(value: object) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("../") or "/../" in path:
        raise NBASpreadIsolationViolation(f"invalid path: {value!r}")
    return path


def assert_nba_spread_only_change(paths: Iterable[object]) -> dict[str, object]:
    """Fail closed unless every proposed write belongs to NBA Spread Step 1."""
    normalized = sorted({_normalize_path(path) for path in paths})
    if not normalized:
        raise NBASpreadIsolationViolation("at least one changed path is required")

    escaped = [path for path in normalized if path not in STEP1_OWNED_PATHS]
    if escaped:
        raise NBASpreadIsolationViolation(
            "NBA Spread Step-1 scope escape blocked: " + ", ".join(escaped)
        )

    return {
        "status": "GREEN",
        "decision": "NBA_SPREAD_ONLY_CHANGE_ALLOWED",
        "sport": SPORT,
        "page_scope": PAGE_SCOPE,
        "changed_paths": normalized,
        "other_sports_modified": False,
        "shared_router_modified": False,
        "app_entrypoint_modified": False,
        "shared_apis_modified": False,
        "existing_nba_workstreams_modified": False,
    }


__all__ = [
    "MODEL_VERSION",
    "SPORT",
    "PAGE_SCOPE",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_SHARED_ROUTER",
    "MAY_MODIFY_APP_ENTRYPOINT",
    "MAY_MODIFY_SHARED_APIS",
    "MAY_MODIFY_EXISTING_NBA_WORKSTREAMS",
    "STEP1_OWNED_PATHS",
    "NBASpreadIsolationViolation",
    "assert_nba_spread_only_change",
]
