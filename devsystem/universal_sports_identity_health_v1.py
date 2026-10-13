from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

VERSION = "UNIVERSAL_SPORTS_IDENTITY_HEALTH_V1"
SNAPSHOT_VERSION = "UNIVERSAL_SPORTS_IDENTITY_HEALTH_SNAPSHOT_V1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "5/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP5_PROVIDER_HEALTH_CANONICAL_IDENTITY_FROZEN"

_ENTITY_TYPES = {"game", "player", "team"}
_HEALTH_STATES = {"DEGRADED", "HEALTHY", "UNHEALTHY", "UNKNOWN"}
_USABLE_HEALTH_STATES = {"DEGRADED", "HEALTHY"}
_VALIDATION_RESULTS = {"INVALID", "UNKNOWN", "VALID"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, prefix: str) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24].upper()


def _norm_identity(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _finite_number(name: str, value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError("IDENTITY_HEALTH_NUMERIC_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("IDENTITY_HEALTH_NUMERIC_INVALID") from exc
    if not math.isfinite(number):
        raise ValueError("IDENTITY_HEALTH_NUMERIC_INVALID")
    if minimum is not None and number < minimum:
        raise ValueError("IDENTITY_HEALTH_NUMERIC_INVALID")
    if maximum is not None and number > maximum:
        raise ValueError("IDENTITY_HEALTH_NUMERIC_INVALID")
    return number


def load_identity_health_contract(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_identity_health_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise ValueError("IDENTITY_HEALTH_CONTRACT_NOT_OBJECT")
    raw = deepcopy(dict(contract))
    supplied_id = str(raw.pop("contract_id", "") or "").strip().upper()
    expected_id = _fingerprint(raw, "USIH-")
    if supplied_id != expected_id:
        raise ValueError("IDENTITY_HEALTH_CONTRACT_FINGERPRINT_MISMATCH")

    required = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "canonical_ids_owned_internally": True,
        "provider_aliases_are_canonical_authority": False,
        "ambiguous_identity_fail_closed": True,
        "unresolved_identity_fail_closed": True,
        "provider_health_scope": ROUTING_UNIT,
        "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
        "health_inspection_activates_provider": False,
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "legacy_registry_mutation": False,
        "github_actions_fallback": 0,
        "render_dependency": False,
        "compatibility_reference": "devsystem/unified_data_identity_provider_health_graph_v1.py",
        "freeze_token": FREEZE_TOKEN,
    }
    for key, expected in required.items():
        if raw.get(key) != expected:
            raise ValueError(f"IDENTITY_HEALTH_CONTRACT_DRIFT:{key}")
    if set(raw.get("canonical_entity_types") or []) != _ENTITY_TYPES:
        raise ValueError("IDENTITY_HEALTH_ENTITY_TYPES_DRIFT")
    if set(raw.get("health_states") or []) != _HEALTH_STATES:
        raise ValueError("IDENTITY_HEALTH_STATES_DRIFT")
    if set(raw.get("usable_health_states") or []) != _USABLE_HEALTH_STATES:
        raise ValueError("IDENTITY_HEALTH_USABLE_STATES_DRIFT")
    if set(raw.get("validation_results") or []) != _VALIDATION_RESULTS:
        raise ValueError("IDENTITY_HEALTH_VALIDATION_RESULTS_DRIFT")

    verified = deepcopy(raw)
    verified["contract_id"] = supplied_id
    verified["status"] = "GREEN"
    return verified


def seal_identity_health_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_NOT_OBJECT")
    raw = deepcopy(dict(snapshot))
    raw.pop("snapshot_id", None)
    raw["snapshot_id"] = _fingerprint(raw, "USIHS-")
    return raw


def _index_identity(
    index: dict[tuple[str, str, str], set[str]],
    *,
    entity_type: str,
    provider_scope: str,
    value: Any,
    canonical_id: str,
) -> None:
    normalized = _norm_identity(value)
    if not normalized:
        raise ValueError("IDENTITY_ALIAS_EMPTY")
    index.setdefault((entity_type, provider_scope, normalized), set()).add(canonical_id)


def validate_identity_health_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_NOT_OBJECT")
    raw = deepcopy(dict(snapshot))
    supplied_id = str(raw.pop("snapshot_id", "") or "").strip().upper()
    expected_id = _fingerprint(raw, "USIHS-")
    if supplied_id != expected_id:
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_FINGERPRINT_MISMATCH")
    if raw.get("version") != SNAPSHOT_VERSION or raw.get("workstream") != WORKSTREAM:
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_VERSION_DRIFT")
    if int(raw.get("revision") or 0) <= 0:
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_REVISION_INVALID")
    if raw.get("routing_unit") != ROUTING_UNIT:
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_ROUTING_UNIT_DRIFT")
    if raw.get("network_calls") is not False or raw.get("fabrication") is not False:
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_RUNTIME_DRIFT")
    if raw.get("mutation_authority") is not False:
        raise ValueError("IDENTITY_HEALTH_SNAPSHOT_MUTATION_AUTHORITY_FORBIDDEN")

    entities = raw.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ValueError("IDENTITY_HEALTH_ENTITIES_REQUIRED")
    canonical_ids: set[str] = set()
    identity_index: dict[tuple[str, str, str], set[str]] = {}

    for entity in entities:
        if not isinstance(entity, Mapping):
            raise ValueError("IDENTITY_ENTITY_INVALID")
        canonical_id = str(entity.get("canonical_id") or "").strip()
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        sport = str(entity.get("sport") or "").strip().lower()
        canonical_key = str(entity.get("canonical_key") or "").strip()
        canonical_name = str(entity.get("canonical_name") or "").strip()
        if not canonical_id or canonical_id in canonical_ids:
            raise ValueError("IDENTITY_CANONICAL_ID_INVALID")
        if entity_type not in _ENTITY_TYPES or not sport or not canonical_key or not canonical_name:
            raise ValueError("IDENTITY_ENTITY_INVALID")
        canonical_ids.add(canonical_id)
        _index_identity(identity_index, entity_type=entity_type, provider_scope="*", value=canonical_key, canonical_id=canonical_id)
        _index_identity(identity_index, entity_type=entity_type, provider_scope="*", value=canonical_name, canonical_id=canonical_id)

        provider_ids = entity.get("provider_ids")
        if not isinstance(provider_ids, Mapping):
            raise ValueError("IDENTITY_PROVIDER_IDS_INVALID")
        for provider_id, provider_entity_id in provider_ids.items():
            pid = str(provider_id or "").strip().lower()
            if not pid or not str(provider_entity_id or "").strip():
                raise ValueError("IDENTITY_PROVIDER_IDS_INVALID")
            _index_identity(
                identity_index,
                entity_type=entity_type,
                provider_scope=pid,
                value=provider_entity_id,
                canonical_id=canonical_id,
            )

        aliases = entity.get("aliases")
        if not isinstance(aliases, list):
            raise ValueError("IDENTITY_ALIASES_INVALID")
        for alias in aliases:
            if not isinstance(alias, Mapping):
                raise ValueError("IDENTITY_ALIASES_INVALID")
            scope = str(alias.get("provider_id") or "*").strip().lower()
            if not scope:
                scope = "*"
            _index_identity(
                identity_index,
                entity_type=entity_type,
                provider_scope=scope,
                value=alias.get("value"),
                canonical_id=canonical_id,
            )

    for matches in identity_index.values():
        if len(matches) > 1:
            raise ValueError("IDENTITY_ALIAS_AMBIGUOUS")
    global_index = {
        (etype, value): next(iter(matches))
        for (etype, scope, value), matches in identity_index.items()
        if scope == "*"
    }
    for (etype, scope, value), matches in identity_index.items():
        if scope == "*":
            continue
        global_match = global_index.get((etype, value))
        local_match = next(iter(matches))
        if global_match is not None and global_match != local_match:
            raise ValueError("IDENTITY_ALIAS_AMBIGUOUS")

    provider_health = raw.get("provider_health")
    if not isinstance(provider_health, list):
        raise ValueError("IDENTITY_HEALTH_PROVIDER_HEALTH_INVALID")
    seen_health: set[tuple[str, str]] = set()
    for record in provider_health:
        if not isinstance(record, Mapping):
            raise ValueError("IDENTITY_HEALTH_PROVIDER_HEALTH_INVALID")
        provider_id = str(record.get("provider_id") or "").strip().lower()
        field = str(record.get("field") or "").strip().lower()
        state = str(record.get("health_state") or "").strip().upper()
        validation = str(record.get("validation_result") or "").strip().upper()
        reason = str(record.get("reason") or "").strip()
        if not provider_id or not field or (provider_id, field) in seen_health:
            raise ValueError("IDENTITY_HEALTH_PROVIDER_FIELD_DUPLICATE")
        seen_health.add((provider_id, field))
        if state not in _HEALTH_STATES:
            raise ValueError("IDENTITY_HEALTH_STATE_INVALID")
        if validation not in _VALIDATION_RESULTS:
            raise ValueError("IDENTITY_HEALTH_VALIDATION_RESULT_INVALID")
        if not reason:
            raise ValueError("IDENTITY_HEALTH_REASON_REQUIRED")
        _finite_number("age_seconds", record.get("age_seconds"), minimum=0.0)
        _finite_number("quality_score", record.get("quality_score"), minimum=0.0, maximum=1.0)

    verified = deepcopy(raw)
    verified["snapshot_id"] = supplied_id
    return verified


def _identity_failure(status: str, *, entity_type: str, value: Any, provider_id: str) -> dict[str, Any]:
    base = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "status": status,
        "entity_type": entity_type,
        "input_value": str(value or ""),
        "provider_id": provider_id,
        "active_provider_ids": [],
        "network_calls": False,
        "fabrication": False,
    }
    base["identity_resolution_id"] = _fingerprint(base, "USIHR-")
    return base


def resolve_canonical_identity(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    entity_type: str,
    value: str,
    provider_id: str | None = None,
) -> dict[str, Any]:
    validate_identity_health_contract(contract)
    etype = str(entity_type or "").strip().lower()
    pid = str(provider_id or "").strip().lower()
    if etype not in _ENTITY_TYPES:
        raise ValueError("IDENTITY_ENTITY_TYPE_UNSUPPORTED")
    wanted = _norm_identity(value)
    if not wanted:
        raise ValueError("IDENTITY_VALUE_REQUIRED")
    try:
        verified = validate_identity_health_snapshot(snapshot)
    except ValueError as exc:
        if str(exc) == "IDENTITY_ALIAS_AMBIGUOUS":
            return _identity_failure(
                "AMBIGUOUS_IDENTITY_FAIL_CLOSED", entity_type=etype, value=value, provider_id=pid
            )
        raise

    matches: dict[str, tuple[dict[str, Any], list[dict[str, str]]]] = {}
    for entity in verified["entities"]:
        if str(entity.get("entity_type") or "").strip().lower() != etype:
            continue
        canonical_hits = {
            _norm_identity(entity.get("canonical_key")),
            _norm_identity(entity.get("canonical_name")),
        }
        alias_hits: list[dict[str, str]] = []
        if wanted in canonical_hits:
            matches[str(entity["canonical_id"])] = (deepcopy(dict(entity)), alias_hits)
            continue

        for alias in entity.get("aliases") or []:
            scope = str(alias.get("provider_id") or "*").strip().lower() or "*"
            if scope == "*" or (pid and scope == pid):
                if wanted == _norm_identity(alias.get("value")):
                    alias_hits.append({"provider_id": scope, "value": str(value)})
        if pid:
            provider_entity_id = (entity.get("provider_ids") or {}).get(pid)
            if provider_entity_id and wanted == _norm_identity(provider_entity_id):
                alias_hits = [{"provider_id": pid, "value": str(value)}]
        if alias_hits:
            matches[str(entity["canonical_id"])] = (deepcopy(dict(entity)), alias_hits[:1])

    if not matches:
        return _identity_failure(
            "IDENTITY_UNRESOLVED_FAIL_CLOSED", entity_type=etype, value=value, provider_id=pid
        )
    if len(matches) != 1:
        return _identity_failure(
            "AMBIGUOUS_IDENTITY_FAIL_CLOSED", entity_type=etype, value=value, provider_id=pid
        )

    entity, aliases_used = next(iter(matches.values()))
    result = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "status": "IDENTITY_RESOLVED",
        "entity_type": etype,
        "canonical_entity_id": entity["canonical_id"],
        "canonical_key": entity["canonical_key"],
        "canonical_name": entity["canonical_name"],
        "sport": entity["sport"],
        "provider_id": pid,
        "provider_entity_id": str((entity.get("provider_ids") or {}).get(pid) or "") if pid else "",
        "aliases_used": aliases_used,
        "snapshot_id": verified["snapshot_id"],
        "active_provider_ids": [],
        "network_calls": False,
        "fabrication": False,
    }
    result["identity_resolution_id"] = _fingerprint(result, "USIHR-")
    return result


def _validate_route(route: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(route, Mapping):
        raise ValueError("IDENTITY_HEALTH_ROUTE_NOT_OBJECT")
    raw = deepcopy(dict(route))
    if raw.get("status") != "ROUTE_READY" or raw.get("routing_unit") != ROUTING_UNIT:
        raise ValueError("IDENTITY_HEALTH_ROUTE_NOT_READY")
    if raw.get("page_wide_source_authority") is not False or raw.get("network_calls") is not False:
        raise ValueError("IDENTITY_HEALTH_ROUTE_INVARIANT_DRIFT")
    if raw.get("fabrication") is not False:
        raise ValueError("IDENTITY_HEALTH_ROUTE_INVARIANT_DRIFT")
    if list(raw.get("active_provider_ids") or []) != []:
        raise ValueError("IDENTITY_HEALTH_ROUTE_ACTIVE_PROVIDER_DRIFT")
    field = str(raw.get("field") or "").strip().lower()
    providers = [str(v or "").strip().lower() for v in (raw.get("eligible_provider_ids") or [])]
    if not field or not providers or any(not provider for provider in providers):
        raise ValueError("IDENTITY_HEALTH_ROUTE_INVALID")
    if len(providers) != len(set(providers)):
        raise ValueError("IDENTITY_HEALTH_ROUTE_DUPLICATE_PROVIDER")
    primary = str(raw.get("primary_provider_id") or "").strip().lower()
    fallbacks = [str(v or "").strip().lower() for v in (raw.get("fallback_provider_ids") or [])]
    if primary != providers[0] or fallbacks != providers[1:]:
        raise ValueError("IDENTITY_HEALTH_ROUTE_ORDER_DRIFT")
    raw["field"] = field
    raw["eligible_provider_ids"] = providers
    raw["primary_provider_id"] = primary
    raw["fallback_provider_ids"] = fallbacks
    return raw


def _rejection_reason(record: Mapping[str, Any]) -> str | None:
    state = str(record.get("health_state") or "UNKNOWN").upper()
    validation = str(record.get("validation_result") or "UNKNOWN").upper()
    if state == "UNHEALTHY":
        return "PROVIDER_FIELD_UNHEALTHY"
    if state == "UNKNOWN":
        return "PROVIDER_FIELD_HEALTH_UNKNOWN"
    if validation != "VALID":
        return "PROVIDER_FIELD_VALIDATION_FAILED"
    if state not in _USABLE_HEALTH_STATES:
        return "PROVIDER_FIELD_HEALTH_UNKNOWN"
    return None


def build_identity_health_context(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    route: Mapping[str, Any],
    *,
    entity_type: str,
    value: str,
    provider_id: str | None = None,
) -> dict[str, Any]:
    validated_contract = validate_identity_health_contract(contract)
    validated_route = _validate_route(route)
    identity = resolve_canonical_identity(
        validated_contract,
        snapshot,
        entity_type=entity_type,
        value=value,
        provider_id=provider_id,
    )
    if identity["status"] != "IDENTITY_RESOLVED":
        result = {
            "version": VERSION,
            "workstream": WORKSTREAM,
            "step": STEP,
            "status": identity["status"],
            "identity_resolution_id": identity["identity_resolution_id"],
            "route_id": str(validated_route.get("route_id") or ""),
            "field": validated_route["field"],
            "route_provider_ids": list(validated_route["eligible_provider_ids"]),
            "usable_provider_ids": [],
            "provider_field_health": [],
            "rejected_providers": [],
            "active_provider_ids": [],
            "page_wide_source_authority": False,
            "network_calls": False,
            "fabrication": False,
        }
        result["context_id"] = _fingerprint(result, "USIHC-")
        return result

    verified_snapshot = validate_identity_health_snapshot(snapshot)
    health_map = {
        (str(record["provider_id"]).strip().lower(), str(record["field"]).strip().lower()): deepcopy(dict(record))
        for record in verified_snapshot["provider_health"]
    }
    field = validated_route["field"]
    field_health: list[dict[str, Any]] = []
    usable: list[str] = []
    rejected: list[dict[str, str]] = []
    for rank, pid in enumerate(validated_route["eligible_provider_ids"], start=1):
        record = health_map.get((pid, field))
        if record is None:
            normalized = {
                "provider_id": pid,
                "field": field,
                "health_state": "UNKNOWN",
                "age_seconds": None,
                "quality_score": None,
                "validation_result": "UNKNOWN",
                "reason": "field health not observed",
            }
        else:
            normalized = deepcopy(record)
            normalized["provider_id"] = pid
            normalized["field"] = field
            normalized["health_state"] = str(normalized["health_state"]).upper()
            normalized["validation_result"] = str(normalized["validation_result"]).upper()
        normalized["fallback_rank"] = rank
        rejection = _rejection_reason(normalized)
        normalized["usable"] = rejection is None
        normalized["rejection_reason"] = rejection
        field_health.append(normalized)
        if rejection is None:
            usable.append(pid)
        else:
            rejected.append({"provider_id": pid, "reason": rejection})

    result = {
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "status": "IDENTITY_HEALTH_READY",
        "sport": str(validated_route.get("sport") or identity.get("sport") or "").strip().lower(),
        "field": field,
        "route_id": str(validated_route.get("route_id") or ""),
        "snapshot_id": verified_snapshot["snapshot_id"],
        "identity_resolution_id": identity["identity_resolution_id"],
        "canonical_entity_id": identity["canonical_entity_id"],
        "canonical_key": identity["canonical_key"],
        "canonical_name": identity["canonical_name"],
        "aliases_used": deepcopy(identity["aliases_used"]),
        "route_provider_ids": list(validated_route["eligible_provider_ids"]),
        "usable_provider_ids": usable,
        "provider_field_health": field_health,
        "rejected_providers": rejected,
        "active_provider_ids": [],
        "routing_unit": ROUTING_UNIT,
        "provider_health_scope": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "mutation_authority": False,
    }
    result["context_id"] = _fingerprint(result, "USIHC-")
    return result
