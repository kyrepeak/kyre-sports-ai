from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from devsystem.universal_sports_source_finalization_step1_contract_v1 import (
    FREEZE_TOKEN as STEP1_FREEZE_TOKEN,
)
from devsystem.universal_sports_provider_registry_v1 import (
    FREEZE_TOKEN as STEP2_FREEZE_TOKEN,
    validate_registry,
)
from devsystem.universal_sports_field_router_v1 import (
    FREEZE_TOKEN as STEP3_FREEZE_TOKEN,
    route_field,
    validate_router_policy,
)
from devsystem.universal_sports_trust_quorum_v1 import (
    FREEZE_TOKEN as STEP4_FREEZE_TOKEN,
    evaluate_quorum,
    validate_trust_policy,
)
from devsystem.universal_sports_identity_health_v1 import (
    FREEZE_TOKEN as STEP5_FREEZE_TOKEN,
    build_identity_health_context,
    resolve_canonical_identity,
    validate_identity_health_contract,
    validate_identity_health_snapshot,
)
from devsystem.universal_sports_source_receipt_v1 import (
    FREEZE_TOKEN as STEP6_FREEZE_TOKEN,
    build_source_receipt,
    validate_source_receipt,
    validate_source_receipt_contract,
)

VERSION = "UNIVERSAL_SPORTS_FULL_INTEGRATION_CERTIFIER_V1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "8/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP8_FULL_INTEGRATION_CERTIFICATION_FROZEN"
STEP7_FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP7_FINALIZATION_WORKER_LEGACY_BRIDGE_FROZEN"

_ACCEPTED = {
    "ACCEPTED_SINGLE_AUTHORITY",
    "ACCEPTED_QUORUM",
    "ACCEPTED_FALLBACK_QUORUM",
}

_PRIOR_FREEZE_TOKENS = {
    "step1": STEP1_FREEZE_TOKEN,
    "step2": STEP2_FREEZE_TOKEN,
    "step3": STEP3_FREEZE_TOKEN,
    "step4": STEP4_FREEZE_TOKEN,
    "step5": STEP5_FREEZE_TOKEN,
    "step6": STEP6_FREEZE_TOKEN,
    "step7": STEP7_FREEZE_TOKEN,
}

_REQUIRED = {
    "version": VERSION,
    "workstream": WORKSTREAM,
    "step": STEP,
    "program_steps": PROGRAM_STEPS,
    "routing_unit": ROUTING_UNIT,
    "full_integration": True,
    "prior_steps_frozen": True,
    "page_wide_source_authority": False,
    "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
    "health_filters_before_quorum": True,
    "minimum_quorum_early_stop": True,
    "canonical_ids_owned_internally": True,
    "same_semantic_metric_only": True,
    "network_calls": False,
    "fabrication": False,
    "product_runtime_mutation": False,
    "sports_model_mutation": False,
    "legacy_registry_mutation": False,
    "render_dependency": False,
    "github_actions_fallback": 0,
    "freeze_token": FREEZE_TOKEN,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, prefix: str) -> str:
    digest = hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24].upper()
    return prefix + digest


def load_full_integration_contract(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("FULL_INTEGRATION_CONTRACT_NOT_OBJECT")
    return value


def validate_full_integration_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise ValueError("FULL_INTEGRATION_CONTRACT_NOT_OBJECT")
    raw = deepcopy(dict(contract))
    supplied_id = str(raw.pop("contract_id", "") or "").strip().upper()
    expected_id = _fingerprint(raw, "USFI-")
    if supplied_id != expected_id:
        raise ValueError("FULL_INTEGRATION_CONTRACT_FINGERPRINT_MISMATCH")

    for key, expected in _REQUIRED.items():
        if raw.get(key) != expected:
            raise ValueError(f"FULL_INTEGRATION_CONTRACT_DRIFT:{key}")
    if raw.get("prior_freeze_tokens") != _PRIOR_FREEZE_TOKENS:
        raise ValueError("FULL_INTEGRATION_PRIOR_FREEZE_LINEAGE_DRIFT")

    verified = deepcopy(raw)
    verified["contract_id"] = supplied_id
    verified["status"] = "GREEN"
    return verified


def _certification_id(payload: Mapping[str, Any]) -> str:
    return _fingerprint(payload, "USFIC-")


def _result(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    result["certification_id"] = _certification_id(result)
    return result


def _base_result(contract: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "prior_freeze_tokens": deepcopy(dict(contract["prior_freeze_tokens"])),
        "route_id": str(route.get("route_id") or ""),
        "route_primary_provider_id": str(route.get("primary_provider_id") or ""),
        "active_provider_ids": [],
        "selected_provider_ids": [],
        "health_rejected_providers": [],
        "decision_status": "",
        "minimum_quorum_satisfied": False,
        "early_stop": False,
        "receipt": None,
        "network_calls": False,
        "fabrication": False,
        "page_wide_source_authority": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "freeze_token": FREEZE_TOKEN,
    }


def _observation_provider_ids(observations: Sequence[Mapping[str, Any]]) -> list[str]:
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        raise ValueError("FULL_INTEGRATION_OBSERVATIONS_NOT_SEQUENCE")
    out: list[str] = []
    for row in observations:
        if not isinstance(row, Mapping):
            raise ValueError("FULL_INTEGRATION_OBSERVATION_NOT_OBJECT")
        provider_id = str(row.get("provider_id") or "").strip().lower()
        if not provider_id or provider_id in out:
            raise ValueError("FULL_INTEGRATION_OBSERVATION_PROVIDER_INVALID")
        out.append(provider_id)
    return out


def certify_full_integration(
    integration_contract: Mapping[str, Any],
    registry: Mapping[str, Any],
    router_policy: Mapping[str, Any],
    trust_policy: Mapping[str, Any],
    identity_health_contract: Mapping[str, Any],
    identity_health_snapshot: Mapping[str, Any],
    source_receipt_contract: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> dict[str, Any]:
    contract = validate_full_integration_contract(integration_contract)
    validate_registry(registry)
    validate_router_policy(router_policy, registry)
    validate_trust_policy(trust_policy)
    validate_identity_health_contract(identity_health_contract)
    validate_identity_health_snapshot(identity_health_snapshot)
    validate_source_receipt_contract(source_receipt_contract)

    if not isinstance(scenario, Mapping):
        raise ValueError("FULL_INTEGRATION_SCENARIO_NOT_OBJECT")
    sport = str(scenario.get("sport") or "").strip().lower()
    field = str(scenario.get("field") or "").strip().lower()
    route = route_field(registry, router_policy, sport=sport, field=field)
    base = _base_result(contract, route)

    observations = list(scenario.get("observations") or [])
    observation_ids = _observation_provider_ids(observations)
    eligible = [str(value).strip().lower() for value in (route.get("eligible_provider_ids") or [])]
    for provider_id in observation_ids:
        if provider_id not in eligible:
            raise ValueError(f"FULL_INTEGRATION_OFF_ROUTE_OBSERVATION:{provider_id}")

    identity = resolve_canonical_identity(
        identity_health_contract,
        identity_health_snapshot,
        entity_type=str(scenario.get("entity_type") or ""),
        value=str(scenario.get("identity_value") or ""),
        provider_id=str(scenario.get("identity_provider_id") or "") or None,
    )
    if identity.get("status") != "IDENTITY_RESOLVED":
        return _result({
            **base,
            "status": "FAIL_CLOSED",
            "certified": False,
            "terminal_status": str(identity.get("status") or "IDENTITY_UNRESOLVED_FAIL_CLOSED"),
        })

    health_context = build_identity_health_context(
        identity_health_contract,
        identity_health_snapshot,
        route,
        entity_type=str(scenario.get("entity_type") or ""),
        value=str(scenario.get("identity_value") or ""),
        provider_id=str(scenario.get("identity_provider_id") or "") or None,
    )
    if health_context.get("status") != "IDENTITY_HEALTH_READY":
        return _result({
            **base,
            "status": "FAIL_CLOSED",
            "certified": False,
            "terminal_status": str(health_context.get("status") or "IDENTITY_HEALTH_FAIL_CLOSED"),
        })

    usable = set(str(value).strip().lower() for value in health_context.get("usable_provider_ids") or [])
    filtered_observations = [
        deepcopy(dict(row))
        for row in observations
        if str(row.get("provider_id") or "").strip().lower() in usable
    ]

    decision = evaluate_quorum(trust_policy, route, filtered_observations)
    common = {
        **base,
        "health_rejected_providers": deepcopy(list(health_context.get("rejected_providers") or [])),
        "active_provider_ids": deepcopy(list(decision.get("active_provider_ids") or [])),
        "selected_provider_ids": deepcopy(list(decision.get("selected_provider_ids") or [])),
        "decision_status": str(decision.get("status") or ""),
        "minimum_quorum_satisfied": bool(decision.get("minimum_quorum_satisfied")),
        "early_stop": bool(decision.get("early_stop")),
    }

    if decision.get("status") not in _ACCEPTED:
        return _result({
            **common,
            "status": "FAIL_CLOSED",
            "certified": False,
            "terminal_status": str(decision.get("status") or "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"),
        })

    attempted = set(str(value).strip().lower() for value in decision.get("active_provider_ids") or [])
    receipt_observations = [
        deepcopy(dict(row))
        for row in filtered_observations
        if str(row.get("provider_id") or "").strip().lower() in attempted
    ]
    receipt = build_source_receipt(
        source_receipt_contract,
        page=str(scenario.get("page") or ""),
        source_step=str(scenario.get("source_step") or ""),
        route=route,
        quorum_decision=decision,
        identity_resolution=identity,
        identity_health_context=health_context,
        observations=receipt_observations,
        canonical_game_id=str(scenario.get("canonical_game_id") or ""),
    )
    validate_source_receipt(receipt)

    return _result({
        **common,
        "status": "GREEN",
        "certified": True,
        "terminal_status": "FULL_INTEGRATION_CERTIFIED",
        "receipt": receipt,
    })


__all__ = [
    "FREEZE_TOKEN",
    "PROGRAM_STEPS",
    "ROUTING_UNIT",
    "STEP",
    "VERSION",
    "WORKSTREAM",
    "certify_full_integration",
    "load_full_integration_contract",
    "validate_full_integration_contract",
]
