from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "UNIVERSAL_SPORTS_SOURCE_RECEIPT_V1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "6/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP6_SOURCE_RECEIPT_PROVENANCE_FROZEN"
_ACCEPTED = {
    "ACCEPTED_SINGLE_AUTHORITY",
    "ACCEPTED_QUORUM",
    "ACCEPTED_FALLBACK_QUORUM",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _fingerprint(value: Any, prefix: str) -> str:
    return prefix + _sha256(value)[:24].upper()


def _finite_number(name: str, value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(f"SOURCE_RECEIPT_{name.upper()}_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"SOURCE_RECEIPT_{name.upper()}_INVALID") from exc
    if not math.isfinite(number):
        raise ValueError(f"SOURCE_RECEIPT_{name.upper()}_INVALID")
    if minimum is not None and number < minimum:
        raise ValueError(f"SOURCE_RECEIPT_{name.upper()}_INVALID")
    if maximum is not None and number > maximum:
        raise ValueError(f"SOURCE_RECEIPT_{name.upper()}_INVALID")
    return number


def load_source_receipt_contract(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_source_receipt_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise ValueError("SOURCE_RECEIPT_CONTRACT_NOT_OBJECT")
    raw = deepcopy(dict(contract))
    supplied_id = str(raw.pop("contract_id", "") or "").strip().upper()
    expected_id = _fingerprint(raw, "USRP-")
    if supplied_id != expected_id:
        raise ValueError("SOURCE_RECEIPT_CONTRACT_FINGERPRINT_MISMATCH")

    required = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "receipt_kind": "ACCEPTED_FIELD_DECISION",
        "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
        "canonical_ids_owned_internally": True,
        "provider_health_scope": ROUTING_UNIT,
        "deterministic_receipt_digest": True,
        "rejected_attempts_preserved": True,
        "aliases_preserved": True,
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "legacy_registry_mutation": False,
        "github_actions_fallback": 0,
        "render_dependency": False,
        "freeze_token": FREEZE_TOKEN,
    }
    for key, expected in required.items():
        if raw.get(key) != expected:
            raise ValueError(f"SOURCE_RECEIPT_CONTRACT_DRIFT:{key}")
    if set(raw.get("accepted_terminal_states") or []) != _ACCEPTED:
        raise ValueError("SOURCE_RECEIPT_ACCEPTED_STATES_DRIFT")
    required_fields = {
        "workstream","sport","page","source_step","canonical_entity_id","canonical_game_id",
        "field","semantic_metric_id","providers_attempted","selected_provider_ids",
        "fallback_rank","normalized_value_fingerprint","freshness_observation",
        "provider_health_at_decision","agreement_result","quorum_policy_id",
        "rejected_attempts","aliases_used","fabrication","receipt_digest",
    }
    if set(raw.get("required_receipt_fields") or []) != required_fields:
        raise ValueError("SOURCE_RECEIPT_REQUIRED_FIELDS_DRIFT")

    verified = deepcopy(raw)
    verified["contract_id"] = supplied_id
    verified["status"] = "GREEN"
    return verified


def _route_provider_order(route: Mapping[str, Any]) -> list[str]:
    if not isinstance(route, Mapping):
        raise ValueError("SOURCE_RECEIPT_ROUTE_NOT_OBJECT")
    if route.get("status") != "ROUTE_READY" or route.get("routing_unit") != ROUTING_UNIT:
        raise ValueError("SOURCE_RECEIPT_ROUTE_NOT_READY")
    if route.get("page_wide_source_authority") is not False:
        raise ValueError("SOURCE_RECEIPT_PAGE_WIDE_AUTHORITY_FORBIDDEN")
    if route.get("network_calls") is not False or route.get("fabrication") is not False:
        raise ValueError("SOURCE_RECEIPT_ROUTE_INVARIANT_DRIFT")
    if list(route.get("active_provider_ids") or []) != []:
        raise ValueError("SOURCE_RECEIPT_ROUTE_ACTIVE_PROVIDER_DRIFT")
    providers = [str(v or "").strip().lower() for v in (route.get("eligible_provider_ids") or [])]
    if not providers or any(not p for p in providers) or len(providers) != len(set(providers)):
        raise ValueError("SOURCE_RECEIPT_ROUTE_PROVIDER_ORDER_INVALID")
    return providers


def _observation_map(observations: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        raise ValueError("SOURCE_RECEIPT_OBSERVATIONS_NOT_SEQUENCE")
    out: dict[str, dict[str, Any]] = {}
    for row in observations:
        if not isinstance(row, Mapping):
            raise ValueError("SOURCE_RECEIPT_OBSERVATION_NOT_OBJECT")
        provider_id = str(row.get("provider_id") or "").strip().lower()
        if not provider_id or provider_id in out:
            raise ValueError("SOURCE_RECEIPT_OBSERVATION_PROVIDER_INVALID")
        _finite_number("age_seconds", row.get("age_seconds"), minimum=0.0)
        _finite_number("quality_score", row.get("quality_score"), minimum=0.0, maximum=1.0)
        out[provider_id] = deepcopy(dict(row))
    return out


def _health_map(identity_health_context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(identity_health_context, Mapping):
        raise ValueError("SOURCE_RECEIPT_HEALTH_CONTEXT_NOT_OBJECT")
    if identity_health_context.get("status") != "IDENTITY_HEALTH_READY":
        raise ValueError("SOURCE_RECEIPT_HEALTH_CONTEXT_NOT_READY")
    if identity_health_context.get("fabrication") is not False or identity_health_context.get("network_calls") is not False:
        raise ValueError("SOURCE_RECEIPT_HEALTH_CONTEXT_INVARIANT_DRIFT")
    rows = identity_health_context.get("provider_field_health")
    if not isinstance(rows, list):
        raise ValueError("SOURCE_RECEIPT_PROVIDER_HEALTH_REQUIRED")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("SOURCE_RECEIPT_PROVIDER_HEALTH_INVALID")
        provider_id = str(row.get("provider_id") or "").strip().lower()
        if not provider_id or provider_id in out:
            raise ValueError("SOURCE_RECEIPT_PROVIDER_HEALTH_INVALID")
        _finite_number("age_seconds", row.get("age_seconds"), minimum=0.0)
        _finite_number("quality_score", row.get("quality_score"), minimum=0.0, maximum=1.0)
        out[provider_id] = deepcopy(dict(row))
    return out


def build_source_receipt(
    contract: Mapping[str, Any],
    *,
    page: str,
    source_step: str,
    route: Mapping[str, Any],
    quorum_decision: Mapping[str, Any],
    identity_resolution: Mapping[str, Any],
    identity_health_context: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    canonical_game_id: str = "",
) -> dict[str, Any]:
    validate_source_receipt_contract(contract)
    provider_order = _route_provider_order(route)

    if not isinstance(quorum_decision, Mapping):
        raise ValueError("SOURCE_RECEIPT_QUORUM_DECISION_NOT_OBJECT")
    status = str(quorum_decision.get("status") or "").strip().upper()
    if status not in _ACCEPTED:
        raise ValueError("SOURCE_RECEIPT_ACCEPTED_DECISION_REQUIRED")
    if quorum_decision.get("fabrication") is not False or quorum_decision.get("network_calls") is not False:
        raise ValueError("SOURCE_RECEIPT_QUORUM_INVARIANT_DRIFT")
    if quorum_decision.get("routing_unit") != ROUTING_UNIT:
        raise ValueError("SOURCE_RECEIPT_QUORUM_ROUTING_UNIT_DRIFT")
    if str(quorum_decision.get("route_id") or "") != str(route.get("route_id") or ""):
        raise ValueError("SOURCE_RECEIPT_ROUTE_DECISION_MISMATCH")

    field = str(route.get("field") or "").strip().lower()
    metric = str(route.get("semantic_metric_id") or "").strip().upper()
    if str(quorum_decision.get("field") or "").strip().lower() != field:
        raise ValueError("SOURCE_RECEIPT_FIELD_MISMATCH")
    if str(quorum_decision.get("semantic_metric_id") or "").strip().upper() != metric:
        raise ValueError("SOURCE_RECEIPT_METRIC_MISMATCH")

    if not isinstance(identity_resolution, Mapping) or identity_resolution.get("status") != "IDENTITY_RESOLVED":
        raise ValueError("SOURCE_RECEIPT_CANONICAL_IDENTITY_REQUIRED")
    if identity_resolution.get("fabrication") is not False or identity_resolution.get("network_calls") is not False:
        raise ValueError("SOURCE_RECEIPT_IDENTITY_INVARIANT_DRIFT")
    canonical_entity_id = str(identity_resolution.get("canonical_entity_id") or "").strip()
    if not canonical_entity_id:
        raise ValueError("SOURCE_RECEIPT_CANONICAL_ENTITY_ID_REQUIRED")

    attempted = [str(v or "").strip().lower() for v in (quorum_decision.get("active_provider_ids") or [])]
    selected = [str(v or "").strip().lower() for v in (quorum_decision.get("selected_provider_ids") or [])]
    if not attempted or any(not p for p in attempted) or len(attempted) != len(set(attempted)):
        raise ValueError("SOURCE_RECEIPT_ATTEMPTED_PROVIDERS_INVALID")
    if not selected or any(p not in attempted for p in selected) or len(selected) != len(set(selected)):
        raise ValueError("SOURCE_RECEIPT_SELECTED_PROVIDERS_INVALID")
    if any(p not in provider_order for p in attempted):
        raise ValueError("SOURCE_RECEIPT_OFF_ROUTE_ATTEMPT")

    obs = _observation_map(observations)
    health = _health_map(identity_health_context)
    missing_obs = [p for p in attempted if p not in obs]
    missing_health = [p for p in attempted if p not in health]
    if missing_obs:
        raise ValueError("SOURCE_RECEIPT_ATTEMPT_OBSERVATION_MISSING")
    if missing_health:
        raise ValueError("SOURCE_RECEIPT_PROVIDER_HEALTH_MISSING")

    value_fp = str(quorum_decision.get("value_fingerprint") or "").strip()
    if not value_fp:
        raise ValueError("SOURCE_RECEIPT_VALUE_FINGERPRINT_REQUIRED")
    policy_id = str(quorum_decision.get("trust_policy_id") or "").strip()
    if not policy_id:
        raise ValueError("SOURCE_RECEIPT_QUORUM_POLICY_REQUIRED")

    rank_map = {provider_id: provider_order.index(provider_id) + 1 for provider_id in selected}
    deepest_rank = max(rank_map.values())
    freshness = [
        {
            "provider_id": p,
            "age_seconds": obs[p]["age_seconds"],
            "quality_score": obs[p]["quality_score"],
        }
        for p in attempted
    ]
    provider_health = [
        {
            "provider_id": p,
            "field": str(health[p].get("field") or field).strip().lower(),
            "health_state": str(health[p].get("health_state") or "").strip().upper(),
            "age_seconds": health[p]["age_seconds"],
            "quality_score": health[p]["quality_score"],
            "validation_result": str(health[p].get("validation_result") or "").strip().upper(),
            "reason": str(health[p].get("reason") or "").strip(),
        }
        for p in attempted
    ]
    if any(row["field"] != field or not row["health_state"] or not row["validation_result"] or not row["reason"] for row in provider_health):
        raise ValueError("SOURCE_RECEIPT_PROVIDER_HEALTH_FIELD_DRIFT")

    aliases_used = deepcopy(list(identity_resolution.get("aliases_used") or []))
    rejected = deepcopy(list(quorum_decision.get("rejected_attempts") or []))
    page_value = str(page or "").strip()
    source_step_value = str(source_step or "").strip()
    if not page_value or not source_step_value:
        raise ValueError("SOURCE_RECEIPT_PAGE_STEP_REQUIRED")

    receipt = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "producer_step": STEP,
        "sport": str(route.get("sport") or "").strip().lower(),
        "page": page_value,
        "source_step": source_step_value,
        "canonical_entity_id": canonical_entity_id,
        "canonical_game_id": str(canonical_game_id or "").strip(),
        "field": field,
        "semantic_metric_id": metric,
        "route_id": str(route.get("route_id") or ""),
        "quorum_decision_id": str(quorum_decision.get("decision_id") or ""),
        "providers_attempted": attempted,
        "selected_provider_ids": selected,
        "provider_fallback_ranks": rank_map,
        "fallback_rank": deepest_rank,
        "normalized_value_fingerprint": value_fp,
        "freshness_observation": freshness,
        "provider_health_at_decision": provider_health,
        "agreement_result": status,
        "quorum_policy_id": policy_id,
        "rejected_attempts": rejected,
        "aliases_used": aliases_used,
        "fabrication": False,
        "network_calls": False,
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
    }
    receipt["receipt_id"] = _fingerprint(receipt, "USR-")
    receipt["receipt_digest"] = "sha256:" + _sha256(receipt)
    return validate_source_receipt(receipt)


def validate_source_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise ValueError("SOURCE_RECEIPT_NOT_OBJECT")
    raw = deepcopy(dict(receipt))
    supplied_digest = str(raw.pop("receipt_digest", "") or "").strip().lower()
    expected_digest = "sha256:" + _sha256(raw)
    if supplied_digest != expected_digest:
        raise ValueError("SOURCE_RECEIPT_DIGEST_MISMATCH")
    supplied_id = str(raw.pop("receipt_id", "") or "").strip().upper()
    expected_id = _fingerprint(raw, "USR-")
    if supplied_id != expected_id:
        raise ValueError("SOURCE_RECEIPT_ID_MISMATCH")

    if raw.get("version") != VERSION or raw.get("workstream") != WORKSTREAM or raw.get("producer_step") != STEP:
        raise ValueError("SOURCE_RECEIPT_VERSION_IDENTITY_DRIFT")
    if raw.get("fabrication") is not False or raw.get("network_calls") is not False:
        raise ValueError("SOURCE_RECEIPT_RUNTIME_INVARIANT_DRIFT")
    if raw.get("routing_unit") != ROUTING_UNIT or raw.get("page_wide_source_authority") is not False:
        raise ValueError("SOURCE_RECEIPT_ROUTING_INVARIANT_DRIFT")
    if str(raw.get("agreement_result") or "").strip().upper() not in _ACCEPTED:
        raise ValueError("SOURCE_RECEIPT_AGREEMENT_RESULT_INVALID")
    attempted = list(raw.get("providers_attempted") or [])
    selected = list(raw.get("selected_provider_ids") or [])
    if not attempted or not selected or any(p not in attempted for p in selected):
        raise ValueError("SOURCE_RECEIPT_PROVIDER_RELATION_INVALID")
    ranks = raw.get("provider_fallback_ranks")
    if not isinstance(ranks, Mapping) or set(ranks) != set(selected):
        raise ValueError("SOURCE_RECEIPT_FALLBACK_RANKS_INVALID")
    if int(raw.get("fallback_rank") or 0) != max(int(v) for v in ranks.values()):
        raise ValueError("SOURCE_RECEIPT_FALLBACK_RANK_INVALID")
    if len(raw.get("freshness_observation") or []) != len(attempted):
        raise ValueError("SOURCE_RECEIPT_FRESHNESS_COVERAGE_INVALID")
    if len(raw.get("provider_health_at_decision") or []) != len(attempted):
        raise ValueError("SOURCE_RECEIPT_HEALTH_COVERAGE_INVALID")
    if not str(raw.get("normalized_value_fingerprint") or "").strip():
        raise ValueError("SOURCE_RECEIPT_VALUE_FINGERPRINT_REQUIRED")
    if not str(raw.get("quorum_policy_id") or "").strip():
        raise ValueError("SOURCE_RECEIPT_QUORUM_POLICY_REQUIRED")
    if not str(raw.get("canonical_entity_id") or "").strip():
        raise ValueError("SOURCE_RECEIPT_CANONICAL_ENTITY_ID_REQUIRED")

    verified = deepcopy(raw)
    verified["receipt_id"] = supplied_id
    verified["receipt_digest"] = supplied_digest
    return verified
