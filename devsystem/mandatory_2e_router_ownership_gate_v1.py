"""MONSTER Step 2E — Canonical Router Ownership Gate V1.

Read-only, registry-driven proof that every live sports route has one reachable
canonical terminal owner, declared route parameters survive canonical query
patching, and the active MONSTER entrypoint/terminal router are not advertising
foreign control ownership.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

from devsystem.monster_system_isolation_v1 import assert_monster_only

VERSION = "MONSTER_STEP2E_CANONICAL_ROUTER_OWNERSHIP_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
TERMINAL_MODULE = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1"
_FOREIGN = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.I)
_OVERRIDE = re.compile(
    r'route\.sport_id\s*==\s*["\']([^"\']+)["\']\s+and\s+route\.market_id\s*==\s*["\']([^"\']+)["\']'
)


class Mandatory2ERouterOwnershipFailure(RuntimeError):
    pass


def _fail(reason: str, **evidence: Any) -> None:
    detail = {"version": VERSION, "status": "BLOCKED", "reason": reason, **evidence}
    raise Mandatory2ERouterOwnershipFailure(str(detail))


def _owner_labels(root: Path) -> list[str]:
    labels: list[str] = []
    app = (root / "app.py").read_text(encoding="utf-8")
    terminal = (root / f"{TERMINAL_MODULE}.py").read_text(encoding="utf-8")
    for line in app.splitlines():
        if "_STREAMLIT_DEPLOYMENT_HEARTBEAT" in line and _FOREIGN.search(line):
            labels.append("app.py:_STREAMLIT_DEPLOYMENT_HEARTBEAT")
    for line in terminal.splitlines():
        if line.startswith("MODEL_VERSION") and _FOREIGN.search(line):
            labels.append(f"{TERMINAL_MODULE}.py:MODEL_VERSION")
    return labels


def verify_repository_routes(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    assert_monster_only({"system": "MONSTER", "gate": VERSION, "root": str(root)})

    registry = importlib.import_module("universal_sports_nav_registry_v1")
    state = importlib.import_module("universal_runtime_v5_state")
    terminal = importlib.import_module(TERMINAL_MODULE)

    registry_errors = list(registry.validate_registry())
    orphan_frontend_routes: list[str] = []
    parameter_drift: list[str] = []
    owner_map: dict[str, str] = {}

    for sport in registry.visible_sports():
        for market in sport.markets:
            if not market.live:
                continue
            key = f"{sport.id}/{market.id}"
            params = {name: f"sample-{name}" for name in market.page_params}
            route = state.RuntimeRoute(sport.id, market.id, params, 1, "monster-step2e")
            adapter = terminal.resolve_destination(route)
            if adapter.route_key != (sport.id, market.id) or str(adapter.source_version).startswith("fail-closed:"):
                orphan_frontend_routes.append(key)
                continue
            if not callable(adapter.loader) or not callable(adapter.renderer):
                orphan_frontend_routes.append(key)
                continue
            owner_map[key] = str(adapter.source_version)
            patch = state.canonical_query_patch(route, route, {})
            for name, value in params.items():
                if patch.get(name) != value:
                    parameter_drift.append(f"{key}:{name}")

    terminal_source = (root / f"{TERMINAL_MODULE}.py").read_text(encoding="utf-8")
    terminal_overrides = sorted(set(_OVERRIDE.findall(terminal_source)))
    unregistered_terminal_routes = [
        f"{sport}/{market}"
        for sport, market in terminal_overrides
        if registry.get_market(sport, market) is None
    ]
    foreign_owner_labels = _owner_labels(root)

    if registry_errors:
        _fail("REGISTRY_INVALID", registry_errors=registry_errors)
    if orphan_frontend_routes:
        _fail("ORPHAN_FRONTEND_ROUTE", orphan_frontend_routes=orphan_frontend_routes)
    if unregistered_terminal_routes:
        _fail("UNREGISTERED_TERMINAL_ROUTE", unregistered_terminal_routes=unregistered_terminal_routes)
    if parameter_drift:
        _fail("ROUTE_PARAMETER_DRIFT", parameter_drift=parameter_drift)
    if foreign_owner_labels:
        _fail("FOREIGN_ROUTER_OWNER_LABEL", foreign_owner_labels=foreign_owner_labels)

    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "route_count": len(owner_map),
        "owner_map": owner_map,
        "orphan_frontend_routes": [],
        "unregistered_terminal_routes": [],
        "route_parameter_drift": [],
        "foreign_owner_labels": [],
        "canonical_terminal_module": TERMINAL_MODULE,
        "registry_driven": True,
        "fail_closed_for_new_unowned_route": True,
    }


def contract_self_test(root: Path | str | None = None) -> dict[str, Any]:
    return verify_repository_routes(root or Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    result = contract_self_test()
    print("MONSTER_STEP2E_CANONICAL_ROUTER_OWNERSHIP_V1_GREEN", result["route_count"])
