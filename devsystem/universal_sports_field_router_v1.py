from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from devsystem.universal_sports_provider_registry_v1 import (
    providers_for_capability,
    validate_registry,
)

VERSION = "UNIVERSAL_SPORTS_FIELD_ROUTER_V1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "3/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP3_FIELD_LEVEL_SOURCE_ROUTER_FROZEN"

_REQUIRED_TOP_LEVEL = {
    "version": VERSION,
    "workstream": WORKSTREAM,
    "step": STEP,
    "program_steps": PROGRAM_STEPS,
    "routing_unit": ROUTING_UNIT,
    "page_wide_source_authority": False,
    "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
    "fallback_semantics": "SAME_SEMANTIC_METRIC_ONLY",
    "network_calls": False,
    "product_runtime_mutation": False,
    "sports_model_mutation": False,
    "legacy_registry_mutation": False,
    "github_actions_fallback": 0,
    "fabrication": False,
    "freeze_token": FREEZE_TOKEN,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _router_id(policy_without_id: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(policy_without_id).encode("utf-8")).hexdigest()[:24].upper()
    return f"USFR-{digest}"


def _route_id(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24].upper()
    return f"ROUTE-{digest}"


def load_router_policy(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("ROUTER_POLICY_NOT_OBJECT")
    return value


def validate_router_policy(policy: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ValueError("ROUTER_POLICY_NOT_OBJECT")

    registry_result = validate_registry(registry)
    raw = deepcopy(dict(policy))
    supplied_router_id = str(raw.pop("router_id", "") or "").strip().upper()

    for key, expected in _REQUIRED_TOP_LEVEL.items():
        if raw.get(key) != expected:
            raise ValueError(f"ROUTER_CONTRACT_DRIFT:{key}")

    routes = raw.get("routes")
    capabilities = registry.get("capabilities")
    if not isinstance(routes, Mapping):
        raise ValueError("ROUTER_ROUTES_NOT_OBJECT")
    if not isinstance(capabilities, Mapping):
        raise ValueError("ROUTER_REGISTRY_CAPABILITIES_NOT_OBJECT")
    if set(routes) != set(capabilities):
        raise ValueError("ROUTER_ROUTE_COVERAGE_MISMATCH")

    provider_types_by_capability: dict[str, set[str]] = {str(key): set() for key in capabilities}
    for provider in registry.get("providers") or []:
        if not isinstance(provider, Mapping):
            continue
        source_type = str(provider.get("source_type") or "").strip()
        for capability in provider.get("capabilities") or []:
            capability_key = str(capability)
            if capability_key in provider_types_by_capability and source_type:
                provider_types_by_capability[capability_key].add(source_type)

    for field, route in routes.items():
        if not isinstance(route, Mapping):
            raise ValueError(f"ROUTER_ROUTE_INVALID:{field}")
        registry_metric = str(capabilities[field].get("semantic_metric_id") or "").strip().upper()
        policy_metric = str(route.get("semantic_metric_id") or "").strip().upper()
        if policy_metric != registry_metric:
            raise ValueError(f"ROUTER_SEMANTIC_METRIC_MISMATCH:{field}")
        if route.get("compatible_substitutes") != []:
            raise ValueError(f"ROUTER_INCOMPATIBLE_SUBSTITUTION:{field}")

        preferred = route.get("preferred_source_types")
        if not isinstance(preferred, list) or not preferred:
            raise ValueError(f"ROUTER_SOURCE_TYPE_ORDER_REQUIRED:{field}")
        normalized = [str(item or "").strip() for item in preferred]
        if any(not item for item in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError(f"ROUTER_SOURCE_TYPE_ORDER_INVALID:{field}")
        unknown = set(normalized) - provider_types_by_capability.get(str(field), set())
        if unknown:
            raise ValueError(f"ROUTER_SOURCE_TYPE_UNKNOWN:{field}")

    expected_router_id = _router_id(raw)
    if supplied_router_id != expected_router_id:
        raise ValueError("ROUTER_FINGERPRINT_MISMATCH")

    return {
        "status": "GREEN",
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
        "fallback_semantics": "SAME_SEMANTIC_METRIC_ONLY",
        "network_calls": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "legacy_registry_mutation": False,
        "github_actions_fallback": 0,
        "fabrication": False,
        "registry_id": registry_result["registry_id"],
        "router_id": supplied_router_id,
        "route_count": len(routes),
        "freeze_token": FREEZE_TOKEN,
    }


def _blank_route(*, sport: str, field: str, semantic_metric_id: str, router_id: str, registry_id: str) -> dict[str, Any]:
    base = {
        "status": "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION",
        "sport": sport,
        "field": field,
        "semantic_metric_id": semantic_metric_id,
        "primary_provider_id": "",
        "fallback_provider_ids": [],
        "eligible_provider_ids": [],
        "blocked_providers": [],
        "active_provider_ids": [],
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "router_id": router_id,
        "registry_id": registry_id,
    }
    result = dict(base)
    result["route_id"] = _route_id(base)
    return result


def route_field(
    registry: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    sport: str,
    field: str,
) -> dict[str, Any]:
    validation = validate_router_policy(policy, registry)
    sport_key = str(sport or "").strip().lower()
    field_key = str(field or "").strip().lower()
    supported_sports = {str(item).strip().lower() for item in (registry.get("supported_sports") or [])}
    routes = policy.get("routes") or {}

    semantic_metric_id = ""
    if field_key in routes:
        semantic_metric_id = str(routes[field_key].get("semantic_metric_id") or "").strip().upper()

    if field_key not in routes or sport_key not in supported_sports:
        return _blank_route(
            sport=sport_key,
            field=field_key,
            semantic_metric_id=semantic_metric_id,
            router_id=validation["router_id"],
            registry_id=validation["registry_id"],
        )

    preferred_types = [str(item) for item in routes[field_key]["preferred_source_types"]]
    type_rank = {source_type: rank for rank, source_type in enumerate(preferred_types)}
    approved = providers_for_capability(registry, capability=field_key, sport=sport_key)

    usable: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for provider in approved:
        provider_id = str(provider.get("provider_id") or "").strip()
        source_type = str(provider.get("source_type") or "").strip()
        if source_type not in type_rank:
            continue

        access = provider.get("access") or {}
        if access.get("credential_required") is True and str(access.get("configuration_state") or "").upper() != "CONFIGURED":
            blocked.append({"provider_id": provider_id, "reason": "CREDENTIALS_NOT_CONFIGURED"})
            continue
        usable.append(provider)

    usable.sort(key=lambda row: (type_rank[str(row["source_type"])], str(row["provider_id"])))
    blocked.sort(
        key=lambda row: (
            type_rank.get(
                next(
                    (
                        str(provider.get("source_type") or "")
                        for provider in approved
                        if str(provider.get("provider_id") or "") == row["provider_id"]
                    ),
                    "",
                ),
                len(type_rank),
            ),
            row["provider_id"],
        )
    )

    eligible_provider_ids = [str(provider["provider_id"]) for provider in usable]
    primary_provider_id = eligible_provider_ids[0] if eligible_provider_ids else ""
    fallback_provider_ids = eligible_provider_ids[1:] if eligible_provider_ids else []
    status = "ROUTE_READY" if eligible_provider_ids else "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"

    base = {
        "status": status,
        "sport": sport_key,
        "field": field_key,
        "semantic_metric_id": semantic_metric_id,
        "primary_provider_id": primary_provider_id,
        "fallback_provider_ids": fallback_provider_ids,
        "eligible_provider_ids": eligible_provider_ids,
        "blocked_providers": blocked,
        "active_provider_ids": [],
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "router_id": validation["router_id"],
        "registry_id": validation["registry_id"],
    }
    result = dict(base)
    result["route_id"] = _route_id(base)
    return result


__all__ = [
    "FREEZE_TOKEN",
    "PROGRAM_STEPS",
    "ROUTING_UNIT",
    "STEP",
    "VERSION",
    "WORKSTREAM",
    "load_router_policy",
    "route_field",
    "validate_router_policy",
]
