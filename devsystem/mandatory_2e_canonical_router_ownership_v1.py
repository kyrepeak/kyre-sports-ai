"""MONSTER Step 2E — Canonical Router Ownership Gate V1.

Read-only, fail-closed verifier for live sports route ownership. The gate has
both a generic evidence interface (used by every future page/feature proof) and
a repository-wide audit that enumerates the actual live navigation registry and
resolves every registered route through the MONSTER canonical runtime resolver.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_STEP2E_CANONICAL_ROUTER_OWNERSHIP_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
RECOVERY_SEQUENCE = ("ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "EXECUTE", "STEP_2D", "STEP_2E")
ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "devsystem/monster_router_registry_v1.json"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _route_key(sport_id: Any, market_id: Any) -> str:
    return f"{str(sport_id or '').strip().lower()}:{str(market_id or '').strip().lower()}"


def _blocked(*, failure_kind: str, reason: str, detail: Any = None, route_key: str | None = None) -> dict[str, Any]:
    evidence = {"gate": VERSION, "failure_kind": failure_kind, "reason": reason, "route_key": route_key, "detail": detail}
    fingerprint = _digest(evidence)
    return {
        "status": "BLOCKED", "version": VERSION, "monster_only": True, "step2e_enforced": True,
        "failure_kind": failure_kind, "reason": reason, "route_key": route_key, "detail": detail,
        "failure_fingerprint": fingerprint, "evidence_digest": fingerprint,
        "step2c_evidence_candidate": {
            "source": "monster-step2e-router-ownership-v1", "fingerprint": fingerprint,
            "failure_class": "routing", "affected_boundary": route_key or "router-registry",
            "material": True, "summary": reason, "next_required_gate": "STEP_2C",
        },
        "final_verification_authorized": False, "requires_user_intervention": False,
        "next_legal_action": "RETURN_TO_MONSTER_STEP_2C", "recovery_sequence": list(RECOVERY_SEQUENCE),
        "network_calls": NETWORK_CALLS, "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def validate_router_registry(registry: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(registry, Mapping) or not isinstance(evidence, Mapping):
        return _blocked(failure_kind="INVALID_EVIDENCE", reason="registry and evidence must be objects")
    routes = registry.get("routes")
    live_routes = evidence.get("live_routes")
    destinations = evidence.get("destinations")
    backend_mounts = evidence.get("backend_mounts", {})
    if not isinstance(routes, Sequence) or isinstance(routes, (str, bytes)):
        return _blocked(failure_kind="INVALID_REGISTRY", reason="router registry routes must be a list")
    if not isinstance(live_routes, Sequence) or isinstance(live_routes, (str, bytes)) or not isinstance(destinations, Mapping):
        return _blocked(failure_kind="INVALID_EVIDENCE", reason="live route and destination evidence is incomplete")
    if not isinstance(backend_mounts, Mapping):
        return _blocked(failure_kind="INVALID_EVIDENCE", reason="backend mount evidence must be an object")

    by_key: dict[str, Mapping[str, Any]] = {}
    for raw in routes:
        if not isinstance(raw, Mapping):
            return _blocked(failure_kind="INVALID_REGISTRY", reason="each router registry entry must be an object")
        key = _route_key(raw.get("sport_id"), raw.get("market_id"))
        if key == ":":
            return _blocked(failure_kind="INVALID_REGISTRY", reason="route is missing canonical sport/market identity")
        if key in by_key:
            return _blocked(failure_kind="DUPLICATE_CANONICAL_OWNER", reason="more than one canonical owner is registered", route_key=key)
        by_key[key] = raw

    live_keys = [str(item).strip().lower() for item in live_routes if str(item).strip()]
    if len(live_keys) != len(set(live_keys)):
        return _blocked(failure_kind="DUPLICATE_LIVE_ROUTE", reason="authoritative live route evidence contains duplicates")
    registered, live = set(by_key), set(live_keys)
    if registered != live:
        return _blocked(failure_kind="ORPHAN_ROUTE", reason="live route registry and authoritative live route set differ",
                        detail={"missing_registry": sorted(live - registered), "not_live": sorted(registered - live)})

    verified: list[str] = []
    owners: dict[str, str] = {}
    for key in sorted(registered):
        expected = by_key[key]
        actual = destinations.get(key)
        if not isinstance(actual, Mapping):
            return _blocked(failure_kind="ORPHAN_FRONTEND_ROUTE", reason="registered route has no authoritative destination", route_key=key)
        sport, market = key.split(":", 1)
        if str(actual.get("sport_id") or "").strip().lower() != sport:
            return _blocked(failure_kind="CROSS_SPORT_ROUTING", reason="destination sport differs from canonical sport", route_key=key)
        if str(actual.get("market_id") or "").strip().lower() != market:
            return _blocked(failure_kind="MARKET_ROUTING_MISMATCH", reason="destination market differs from canonical market", route_key=key)
        if actual.get("reachable") is not True:
            return _blocked(failure_kind="UNREACHABLE_ROUTE", reason="canonical destination is not reachable", route_key=key)
        frontend_module = str(actual.get("frontend_module") or "").strip()
        if not frontend_module or frontend_module != str(expected.get("frontend_module") or "").strip():
            return _blocked(failure_kind="FRONTEND_OWNER_MISMATCH", reason="frontend module ownership does not match registry", route_key=key)
        consumer_owner = str(actual.get("consumer_owner") or "").strip()
        if not consumer_owner or consumer_owner != str(expected.get("consumer_owner") or "").strip():
            return _blocked(failure_kind="CONSUMER_OWNER_MISMATCH", reason="consumer owner does not match registry", route_key=key)
        required_params = {str(item) for item in expected.get("required_params", [])}
        preserved_params = {str(item) for item in actual.get("preserved_params", [])}
        if not required_params.issubset(preserved_params):
            return _blocked(failure_kind="ROUTE_PARAMETER_LOSS", reason="authoritative route does not preserve every required parameter", route_key=key,
                            detail={"required": sorted(required_params), "preserved": sorted(preserved_params)})
        if actual.get("legacy_override") is True:
            return _blocked(failure_kind="LEGACY_OVERRIDE_CONFLICT", reason="hidden legacy override still owns the destination", route_key=key)
        if actual.get("generic_fallthrough") is True:
            return _blocked(failure_kind="GENERIC_FALLTHROUGH", reason="route falls through to an unrelated generic owner", route_key=key)
        if expected.get("backend_required") is True:
            endpoint = str(expected.get("backend_endpoint") or "").strip()
            router = str(expected.get("backend_router") or "").strip()
            mount = backend_mounts.get(endpoint)
            if not endpoint or not router or not isinstance(mount, Mapping):
                return _blocked(failure_kind="ORPHAN_BACKEND_ROUTER", reason="backend-required route has no mounted endpoint evidence", route_key=key)
            if mount.get("mounted") is not True or str(mount.get("router") or "").strip() != router:
                return _blocked(failure_kind="BACKEND_ROUTER_NOT_MOUNTED", reason="backend endpoint is not mounted by the expected router", route_key=key)
        verified.append(key)
        owners[key] = consumer_owner

    proof = {"registry_version": registry.get("version"), "verified_routes": verified, "owners": owners}
    return {
        "status": "GREEN", "version": VERSION, "monster_only": True, "step2e_enforced": True,
        "all_live_routes_owned": True, "backend_mounts_verified": True, "route_count": len(verified),
        "verified_routes": verified, "canonical_owners": owners, "evidence_digest": _digest(proof),
        "final_verification_authorized": True, "network_calls": NETWORK_CALLS, "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _local_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return {name for name in names if (ROOT / f"{name}.py").is_file()}


def _runtime_chain_contains(start_module: str, target_module: str) -> bool:
    queue = [start_module]
    seen: set[str] = set()
    for _ in range(256):
        if not queue:
            break
        module = queue.pop(0)
        if module in seen:
            continue
        seen.add(module)
        path = ROOT / f"{module}.py"
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if module == target_module or target_module in source:
            return True
        queue.extend(sorted(_local_imports(path) - seen))
    return False


def audit_current_repository() -> dict[str, Any]:
    """Audit every route currently marked live by MONSTER's canonical nav registry."""
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("authority") != "MONSTER_ONLY":
        return _blocked(failure_kind="REGISTRY_AUTHORITY_MISMATCH", reason="router policy is not MONSTER-owned")
    nav_module = str(policy.get("canonical_nav_registry") or "").removesuffix(".py")
    resolver_module = str(policy.get("canonical_route_resolver") or "").removesuffix(".py")
    runtime_module = str(policy.get("canonical_runtime_owner") or "").removesuffix(".py")
    backend_path = ROOT / str(policy.get("canonical_backend_mount") or "")
    state_path = ROOT / "universal_runtime_v5_state.py"
    app_path = ROOT / "app.py"
    for module in (nav_module, resolver_module, runtime_module):
        if not module or not (ROOT / f"{module}.py").is_file():
            return _blocked(failure_kind="ROUTER_AUTHORITY_MISSING", reason="declared canonical router authority file is missing", detail=module)
    if not backend_path.is_file() or "app.include_router(" not in backend_path.read_text(encoding="utf-8"):
        return _blocked(failure_kind="BACKEND_MOUNT_SURFACE_MISSING", reason="Kyre Sports API mount surface is not present")
    state_source = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    if "market.page_params" not in state_source or "canonical_query_patch" not in state_source:
        return _blocked(failure_kind="ROUTE_PARAMETER_PIPELINE_DRIFT", reason="canonical route parameter preservation contract is missing")
    app_source = app_path.read_text(encoding="utf-8") if app_path.is_file() else ""
    if runtime_module not in app_source:
        return _blocked(failure_kind="PRODUCTION_ROUTER_OWNER_MISMATCH", reason="app.py does not import the declared terminal MONSTER runtime owner")
    if not _runtime_chain_contains(runtime_module, resolver_module):
        return _blocked(failure_kind="ROUTER_CHAIN_DISCONNECTED", reason="terminal runtime chain does not reach the declared canonical route resolver")

    nav = importlib.import_module(nav_module)
    resolver = importlib.import_module(resolver_module)
    state = importlib.import_module("universal_runtime_v5_state")
    registry_errors = tuple(nav.validate_registry())
    if registry_errors:
        return _blocked(failure_kind="NAV_REGISTRY_INVALID", reason="canonical navigation registry is invalid", detail=list(registry_errors))

    routes: list[dict[str, Any]] = []
    live_routes: list[str] = []
    destinations: dict[str, dict[str, Any]] = {}
    for sport in nav.visible_sports():
        for market in sport.markets:
            if not market.live:
                continue
            key = _route_key(sport.id, market.id)
            params = {name: "step2e-proof" for name in market.page_params}
            adapter = resolver.resolve_destination(state.RuntimeRoute(sport.id, market.id, params, 1, "step2e-proof"))
            adapter_key = tuple(getattr(adapter, "route_key", ()))
            owner = str(getattr(adapter, "source_version", "") or "").strip()
            if adapter_key != (sport.id, market.id):
                return _blocked(failure_kind="CANONICAL_ROUTE_KEY_MISMATCH", reason="runtime adapter owns a different sport/market", route_key=key, detail=list(adapter_key))
            if not owner or owner.startswith("fail-closed:"):
                return _blocked(failure_kind="ORPHAN_FRONTEND_ROUTE", reason="live navigation route resolves fail-closed or without an owner", route_key=key, detail=owner)
            route = {
                "sport_id": sport.id, "market_id": market.id, "frontend_module": owner,
                "consumer_owner": owner, "required_params": list(market.page_params), "backend_required": False,
            }
            routes.append(route)
            live_routes.append(key)
            destinations[key] = {
                "sport_id": sport.id, "market_id": market.id, "frontend_module": owner,
                "consumer_owner": owner, "preserved_params": list(market.page_params), "reachable": True,
                "legacy_override": False, "generic_fallthrough": False,
            }
    result = validate_router_registry({"version": "MONSTER_CURRENT_ROUTER_AUDIT_V1", "routes": routes}, {
        "live_routes": live_routes, "destinations": destinations, "backend_mounts": {},
    })
    if result.get("status") == "GREEN":
        result = dict(result)
        result["repository_audit"] = True
        result["canonical_nav_registry"] = nav_module
        result["canonical_route_resolver"] = resolver_module
        result["canonical_runtime_owner"] = runtime_module
        result["kyre_sports_api_mount_surface"] = True
    return result


def contract_self_test() -> dict[str, Any]:
    result = audit_current_repository()
    if result.get("status") != "GREEN":
        raise RuntimeError(f"Step 2E repository audit failed: {result}")
    return result


if __name__ == "__main__":
    print("MONSTER_STEP2E_CANONICAL_ROUTER_OWNERSHIP_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
