"""MONSTER Step 2E — Canonical Router Ownership Gate V1.

Read-only, fail-closed verifier for live sports route ownership.  The gate does
not create routes, mount routers, or mutate product runtime.  It consumes a
MONSTER-owned registry plus evidence captured from the authoritative routing
path and proves that each live sport/market identity has exactly one reachable
consumer owner, preserves required route parameters, and (when required) owns
one mounted Kyre Sports API endpoint.

A Step 2E failure is deterministic evidence for Anti-Loop -> Step 2C.  It is
never permission to create a parallel repair lane.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_STEP2E_CANONICAL_ROUTER_OWNERSHIP_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
RECOVERY_SEQUENCE = ("ANTI_LOOP", "STEP_2C", "STEP_2B", "STEP_2A", "EXECUTE", "STEP_2D", "STEP_2E")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _route_key(sport_id: Any, market_id: Any) -> str:
    return f"{str(sport_id or '').strip().lower()}:{str(market_id or '').strip().lower()}"


def _blocked(*, failure_kind: str, reason: str, detail: Any = None, route_key: str | None = None) -> dict[str, Any]:
    evidence = {
        "gate": VERSION,
        "failure_kind": failure_kind,
        "reason": reason,
        "route_key": route_key,
        "detail": detail,
    }
    fingerprint = _digest(evidence)
    return {
        "status": "BLOCKED",
        "version": VERSION,
        "monster_only": True,
        "step2e_enforced": True,
        "failure_kind": failure_kind,
        "reason": reason,
        "route_key": route_key,
        "detail": detail,
        "failure_fingerprint": fingerprint,
        "evidence_digest": fingerprint,
        "step2c_evidence_candidate": {
            "source": "monster-step2e-router-ownership-v1",
            "fingerprint": fingerprint,
            "failure_class": "routing",
            "affected_boundary": route_key or "router-registry",
            "material": True,
            "summary": reason,
            "next_required_gate": "STEP_2C",
        },
        "final_verification_authorized": False,
        "requires_user_intervention": False,
        "next_legal_action": "RETURN_TO_MONSTER_STEP_2C",
        "recovery_sequence": list(RECOVERY_SEQUENCE),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
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
    registered = set(by_key)
    live = set(live_keys)
    if registered != live:
        return _blocked(
            failure_kind="ORPHAN_ROUTE",
            reason="live route registry and authoritative live route set differ",
            detail={"missing_registry": sorted(live - registered), "not_live": sorted(registered - live)},
        )

    backend_verified = True
    verified: list[str] = []
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
            return _blocked(
                failure_kind="ROUTE_PARAMETER_LOSS",
                reason="authoritative route does not preserve every required parameter",
                route_key=key,
                detail={"required": sorted(required_params), "preserved": sorted(preserved_params)},
            )
        if actual.get("legacy_override") is True:
            return _blocked(failure_kind="LEGACY_OVERRIDE_CONFLICT", reason="hidden legacy override still owns the destination", route_key=key)
        if actual.get("generic_fallthrough") is True:
            return _blocked(failure_kind="GENERIC_FALLTHROUGH", reason="route falls through to an unrelated generic owner", route_key=key)
        if expected.get("backend_required") is True:
            endpoint = str(expected.get("backend_endpoint") or "").strip()
            router = str(expected.get("backend_router") or "").strip()
            mount = backend_mounts.get(endpoint)
            if not endpoint or not router or not isinstance(mount, Mapping):
                backend_verified = False
                return _blocked(failure_kind="ORPHAN_BACKEND_ROUTER", reason="backend-required route has no mounted endpoint evidence", route_key=key)
            if mount.get("mounted") is not True or str(mount.get("router") or "").strip() != router:
                backend_verified = False
                return _blocked(failure_kind="BACKEND_ROUTER_NOT_MOUNTED", reason="backend endpoint is not mounted by the expected router", route_key=key)
        verified.append(key)

    proof = {
        "registry_version": registry.get("version"),
        "verified_routes": verified,
        "backend_mounts_verified": backend_verified,
    }
    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "step2e_enforced": True,
        "all_live_routes_owned": True,
        "backend_mounts_verified": backend_verified,
        "route_count": len(verified),
        "verified_routes": verified,
        "evidence_digest": _digest(proof),
        "final_verification_authorized": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    registry = {"version": "MONSTER_ROUTER_REGISTRY_V1", "routes": [{
        "sport_id": "nfl", "market_id": "passing-yards",
        "frontend_module": "nfl_passing_yards_simple_qb_grid_v1",
        "consumer_owner": "nfl_passing_yards_simple_qb_grid_v1",
        "required_params": ["date", "game_id", "player_id"], "backend_required": False,
    }]}
    evidence = {"live_routes": ["nfl:passing-yards"], "destinations": {"nfl:passing-yards": {
        "sport_id": "nfl", "market_id": "passing-yards",
        "frontend_module": "nfl_passing_yards_simple_qb_grid_v1",
        "consumer_owner": "nfl_passing_yards_simple_qb_grid_v1",
        "preserved_params": ["date", "game_id", "player_id"], "reachable": True,
        "legacy_override": False, "generic_fallthrough": False,
    }}, "backend_mounts": {}}
    result = validate_router_registry(registry, evidence)
    if result.get("status") != "GREEN":
        raise RuntimeError(f"Step 2E self-test failed: {result}")
    return result


if __name__ == "__main__":
    print("MONSTER_STEP2E_CANONICAL_ROUTER_OWNERSHIP_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
