"""MONSTER V6 Step 6 - Unified Data Identity + Provider Health Graph V1.

Read-only control-plane contract for canonical team/player/event identity,
provider-specific aliases and IDs, provider health, field availability,
field-level routing, and provenance.

The unit of work is DATA_FIELD. Source loyalty is forbidden.

This module does not fetch network data and does not mutate product/runtime
state. Live adapters may build a graph from current provider observations, then
use this contract to resolve identity and choose the next proven source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_V6_UNIFIED_DATA_IDENTITY_PROVIDER_HEALTH_GRAPH_V1"
CASES_VERSION = "MONSTER_V6_UNIFIED_DATA_IDENTITY_PROVIDER_HEALTH_CASES_V1"
UNIT_OF_WORK = "DATA_FIELD"
NO_SOURCE_LOYALTY = True
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_ENTITY_TYPES = {"team", "player", "event"}
_HEALTH_STATES = {"HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"}
_USABLE_HEALTH = {"HEALTHY", "DEGRADED"}
_FIELD_STATES = {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class UnifiedDataIdentityHealthFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, prefix: str) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24].upper()


def _norm_identity(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _proof(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedDataIdentityHealthFailure("successful proof must be an object")
    proof = deepcopy(dict(value))
    sha = str(proof.get("proven_sha") or "").strip().lower()
    digest = str(proof.get("terminal_receipt_digest") or "").strip().lower()
    conclusion = str(proof.get("conclusion") or "").strip().upper()
    try:
        run_id = int(proof.get("workflow_run_id") or 0)
    except (TypeError, ValueError) as exc:
        raise UnifiedDataIdentityHealthFailure("proof workflow_run_id must be an integer") from exc
    if not _SHA40.fullmatch(sha):
        raise UnifiedDataIdentityHealthFailure("proof proven_sha must be a full 40-character SHA")
    if run_id <= 0:
        raise UnifiedDataIdentityHealthFailure("proof workflow_run_id must be positive")
    if not _DIGEST.fullmatch(digest):
        raise UnifiedDataIdentityHealthFailure("proof terminal_receipt_digest is invalid")
    if conclusion != "SUCCESS":
        raise UnifiedDataIdentityHealthFailure("usable provider/field proof must be SUCCESS")
    proof["proven_sha"] = sha
    proof["workflow_run_id"] = run_id
    proof["terminal_receipt_digest"] = digest
    proof["conclusion"] = conclusion
    return proof


def seal_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        raise UnifiedDataIdentityHealthFailure("graph must be an object")
    raw = deepcopy(dict(graph))
    raw.pop("graph_id", None)
    raw["graph_id"] = _fingerprint(raw, "UDIPHG-")
    return raw


def _index_identity(
    index: dict[tuple[str, str, str], set[str]],
    *,
    entity_type: str,
    provider_scope: str,
    value: Any,
    entity_id: str,
) -> None:
    key = (entity_type, provider_scope, _norm_identity(value))
    if not key[2]:
        raise UnifiedDataIdentityHealthFailure("identity aliases may not normalize to empty")
    index.setdefault(key, set()).add(entity_id)


def validate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        raise UnifiedDataIdentityHealthFailure("graph must be an object")
    raw = deepcopy(dict(graph))
    supplied_id = str(raw.pop("graph_id", "") or "").strip().upper()
    if raw.get("version") != VERSION or int(raw.get("schema_version", 0)) != 1:
        raise UnifiedDataIdentityHealthFailure("graph version/schema mismatch")
    if int(raw.get("revision") or 0) <= 0:
        raise UnifiedDataIdentityHealthFailure("graph revision must be positive")
    if raw.get("unit_of_work") != UNIT_OF_WORK:
        raise UnifiedDataIdentityHealthFailure("graph unit_of_work must be DATA_FIELD")
    if raw.get("no_source_loyalty") is not True:
        raise UnifiedDataIdentityHealthFailure("source loyalty is forbidden")

    expected_id = _fingerprint(raw, "UDIPHG-")
    if supplied_id != expected_id:
        raise UnifiedDataIdentityHealthFailure("graph fingerprint mismatch")

    providers = raw.get("providers")
    if not isinstance(providers, list) or not providers:
        raise UnifiedDataIdentityHealthFailure("graph requires providers")
    provider_ids: set[str] = set()
    for provider in providers:
        if not isinstance(provider, Mapping):
            raise UnifiedDataIdentityHealthFailure("provider record must be an object")
        provider_id = str(provider.get("provider_id") or "").strip().lower()
        if not provider_id or provider_id in provider_ids:
            raise UnifiedDataIdentityHealthFailure("provider IDs must be unique and non-empty")
        provider_ids.add(provider_id)
        health = str(provider.get("health") or "").strip().upper()
        if health not in _HEALTH_STATES:
            raise UnifiedDataIdentityHealthFailure(f"invalid provider health for {provider_id}")
        if not str(provider.get("health_reason") or "").strip():
            raise UnifiedDataIdentityHealthFailure(f"provider {provider_id} requires health_reason")
        if health in _USABLE_HEALTH:
            _proof(provider.get("last_successful_proof") or {})
        fields = provider.get("fields")
        if not isinstance(fields, Mapping):
            raise UnifiedDataIdentityHealthFailure(f"provider {provider_id} fields must be an object")
        for field, record in fields.items():
            if not str(field or "").strip() or not isinstance(record, Mapping):
                raise UnifiedDataIdentityHealthFailure(f"provider {provider_id} has invalid field record")
            status = str(record.get("status") or "").strip().upper()
            if status not in _FIELD_STATES:
                raise UnifiedDataIdentityHealthFailure(f"provider {provider_id} field {field} has invalid status")
            if status == "AVAILABLE":
                _proof(record.get("last_successful_proof") or {})
            elif not str(record.get("reason") or "").strip():
                raise UnifiedDataIdentityHealthFailure(
                    f"provider {provider_id} unavailable/unknown field {field} requires reason"
                )

    entities = raw.get("entities")
    if not isinstance(entities, list) or not entities:
        raise UnifiedDataIdentityHealthFailure("graph requires entities")
    entity_ids: set[str] = set()
    identity_index: dict[tuple[str, str, str], set[str]] = {}
    for entity in entities:
        if not isinstance(entity, Mapping):
            raise UnifiedDataIdentityHealthFailure("entity record must be an object")
        entity_id = str(entity.get("entity_id") or "").strip()
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        canonical_key = str(entity.get("canonical_key") or "").strip()
        canonical_name = str(entity.get("canonical_name") or "").strip()
        if not entity_id or entity_id in entity_ids:
            raise UnifiedDataIdentityHealthFailure("entity IDs must be unique and non-empty")
        if entity_type not in _ENTITY_TYPES:
            raise UnifiedDataIdentityHealthFailure(f"unsupported entity type for {entity_id}")
        if not canonical_key or not canonical_name:
            raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} requires canonical key and name")
        entity_ids.add(entity_id)
        _index_identity(identity_index, entity_type=entity_type, provider_scope="*", value=canonical_key, entity_id=entity_id)
        _index_identity(identity_index, entity_type=entity_type, provider_scope="*", value=canonical_name, entity_id=entity_id)

        provider_map = entity.get("provider_ids")
        if not isinstance(provider_map, Mapping):
            raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} provider_ids must be an object")
        for provider_id, provider_entity_id in provider_map.items():
            pid = str(provider_id or "").strip().lower()
            if pid not in provider_ids:
                raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} references unknown provider {pid}")
            if not str(provider_entity_id or "").strip():
                raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} has empty provider identity for {pid}")
            _index_identity(
                identity_index,
                entity_type=entity_type,
                provider_scope=pid,
                value=provider_entity_id,
                entity_id=entity_id,
            )

        aliases = entity.get("aliases")
        if not isinstance(aliases, list):
            raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} aliases must be a list")
        for alias in aliases:
            if not isinstance(alias, Mapping):
                raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} alias must be an object")
            scope = str(alias.get("provider_id") or "*").strip().lower()
            if scope != "*" and scope not in provider_ids:
                raise UnifiedDataIdentityHealthFailure(f"entity {entity_id} alias references unknown provider {scope}")
            _index_identity(
                identity_index,
                entity_type=entity_type,
                provider_scope=scope,
                value=alias.get("value"),
                entity_id=entity_id,
            )

    for key, matches in identity_index.items():
        if len(matches) > 1:
            raise UnifiedDataIdentityHealthFailure(
                f"ambiguous identity alias for type={key[0]} provider={key[1]} value={key[2]}"
            )

    # A provider-specific identity may not collide with another entity's global
    # identity because both would match when resolving for that provider.
    global_by_type_value = {
        (etype, value): next(iter(matches))
        for (etype, scope, value), matches in identity_index.items()
        if scope == "*"
    }
    for (etype, scope, value), matches in identity_index.items():
        if scope == "*":
            continue
        global_entity = global_by_type_value.get((etype, value))
        local_entity = next(iter(matches))
        if global_entity is not None and global_entity != local_entity:
            raise UnifiedDataIdentityHealthFailure(
                f"provider identity collides with global identity for provider={scope} value={value}"
            )

    routes = raw.get("field_routes")
    if not isinstance(routes, Mapping) or not routes:
        raise UnifiedDataIdentityHealthFailure("graph requires field_routes")
    for field, route in routes.items():
        if not str(field or "").strip() or not isinstance(route, list) or not route:
            raise UnifiedDataIdentityHealthFailure("each field route requires at least one provider")
        normalized = [str(pid or "").strip().lower() for pid in route]
        if len(normalized) != len(set(normalized)):
            raise UnifiedDataIdentityHealthFailure(f"field route {field} contains duplicate providers")
        unknown = [pid for pid in normalized if pid not in provider_ids]
        if unknown:
            raise UnifiedDataIdentityHealthFailure(f"field route {field} references unknown providers {unknown}")

    protections = raw.get("protections") or {}
    required_true = [
        "exact_identity_resolution",
        "field_level_routing",
        "provider_health_required",
        "field_availability_required",
        "successful_proof_required_for_usable_source",
        "field_level_provenance_required",
        "all_provider_failure_fails_closed",
        "fabrication_forbidden",
        "source_lock_forbidden",
        "advisory_only",
        "step_2a_required_for_downstream_mutation",
        "scope_lease_required_for_downstream_mutation",
    ]
    if not all(protections.get(name) is True for name in required_true):
        raise UnifiedDataIdentityHealthFailure("graph protections drift")
    if protections.get("mutation_authority") is not False:
        raise UnifiedDataIdentityHealthFailure("graph may not grant mutation authority")

    verified = deepcopy(raw)
    verified["graph_id"] = supplied_id
    return verified


def _provider_map(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(provider.get("provider_id") or "").strip().lower(): deepcopy(dict(provider))
        for provider in graph["providers"]
    }


def _entity_map(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entity.get("entity_id") or "").strip(): deepcopy(dict(entity))
        for entity in graph["entities"]
    }


def resolve_identity(
    graph: Mapping[str, Any],
    *,
    entity_type: str,
    value: str,
    provider_id: str | None = None,
) -> dict[str, Any]:
    verified = validate_graph(graph)
    etype = str(entity_type or "").strip().lower()
    if etype not in _ENTITY_TYPES:
        raise UnifiedDataIdentityHealthFailure("unsupported entity_type")
    wanted = _norm_identity(value)
    if not wanted:
        raise UnifiedDataIdentityHealthFailure("identity value is required")
    pid = str(provider_id or "").strip().lower()
    providers = _provider_map(verified)
    if pid and pid not in providers:
        raise UnifiedDataIdentityHealthFailure(f"unknown provider: {pid}")

    matches: dict[str, dict[str, Any]] = {}
    for entity in verified["entities"]:
        if str(entity.get("entity_type") or "").lower() != etype:
            continue
        candidates = [
            _norm_identity(entity.get("canonical_key")),
            _norm_identity(entity.get("canonical_name")),
        ]
        for alias in entity.get("aliases") or []:
            scope = str(alias.get("provider_id") or "*").strip().lower()
            if scope == "*" or (pid and scope == pid):
                candidates.append(_norm_identity(alias.get("value")))
        if pid:
            provider_entity_id = (entity.get("provider_ids") or {}).get(pid)
            if provider_entity_id:
                candidates.append(_norm_identity(provider_entity_id))
        if wanted in candidates:
            matches[str(entity["entity_id"])] = deepcopy(dict(entity))

    if not matches:
        return {
            "version": VERSION,
            "ready": False,
            "state": "IDENTITY_UNRESOLVED",
            "entity_type": etype,
            "input": value,
            "provider_id": pid,
            "mutation_authority": False,
        }
    if len(matches) != 1:
        raise UnifiedDataIdentityHealthFailure("identity resolution is ambiguous")

    entity = next(iter(matches.values()))
    provider_entity_id = str((entity.get("provider_ids") or {}).get(pid) or "") if pid else ""
    return {
        "version": VERSION,
        "ready": True,
        "state": "IDENTITY_RESOLVED",
        "entity_id": entity["entity_id"],
        "entity_type": entity["entity_type"],
        "canonical_key": entity["canonical_key"],
        "canonical_name": entity["canonical_name"],
        "provider_id": pid,
        "provider_entity_id": provider_entity_id,
        "graph_id": verified["graph_id"],
        "mutation_authority": False,
    }


def route_field(
    graph: Mapping[str, Any],
    *,
    entity_id: str,
    field: str,
    source_lock: str | None = None,
) -> dict[str, Any]:
    verified = validate_graph(graph)
    if str(source_lock or "").strip():
        raise UnifiedDataIdentityHealthFailure("SOURCE_LOYALTY_FORBIDDEN")

    entities = _entity_map(verified)
    providers = _provider_map(verified)
    entity_key = str(entity_id or "").strip()
    field_key = str(field or "").strip()
    if entity_key not in entities:
        raise UnifiedDataIdentityHealthFailure("unknown entity_id")
    if not field_key:
        raise UnifiedDataIdentityHealthFailure("field is required")
    route = [str(pid).strip().lower() for pid in (verified.get("field_routes") or {}).get(field_key, [])]
    if not route:
        return {
            "version": VERSION,
            "ready": False,
            "state": "FIELD_ROUTE_UNDEFINED",
            "entity_id": entity_key,
            "field": field_key,
            "unit_of_work": UNIT_OF_WORK,
            "no_source_loyalty": NO_SOURCE_LOYALTY,
            "attempts": [],
            "fabricated": False,
            "mutation_authority": False,
        }

    entity = entities[entity_key]
    attempts: list[dict[str, Any]] = []
    for rank, provider_id in enumerate(route, start=1):
        provider = providers[provider_id]
        health = str(provider.get("health") or "").upper()
        provider_entity_id = str((entity.get("provider_ids") or {}).get(provider_id) or "")
        field_record = deepcopy(dict((provider.get("fields") or {}).get(field_key) or {}))
        field_status = str(field_record.get("status") or "UNKNOWN").upper()

        attempt = {
            "provider_id": provider_id,
            "rank": rank,
            "provider_health": health,
            "provider_entity_id": provider_entity_id,
            "field_status": field_status,
            "accepted": False,
            "reason": "",
        }

        if health not in _USABLE_HEALTH:
            attempt["reason"] = "PROVIDER_UNHEALTHY" if health == "UNHEALTHY" else "PROVIDER_HEALTH_UNKNOWN"
            attempts.append(attempt)
            continue
        if not provider_entity_id:
            attempt["reason"] = "IDENTITY_MAPPING_MISSING"
            attempts.append(attempt)
            continue
        if field_status != "AVAILABLE":
            attempt["reason"] = "FIELD_UNAVAILABLE" if field_status == "UNAVAILABLE" else "FIELD_AVAILABILITY_UNKNOWN"
            attempts.append(attempt)
            continue

        provider_proof = _proof(provider.get("last_successful_proof") or {})
        field_proof = _proof(field_record.get("last_successful_proof") or {})
        attempt["accepted"] = True
        attempt["reason"] = "ACCEPTED"
        attempts.append(attempt)
        return {
            "version": VERSION,
            "ready": True,
            "state": "FIELD_ROUTED",
            "entity_id": entity_key,
            "entity_type": entity["entity_type"],
            "canonical_key": entity["canonical_key"],
            "field": field_key,
            "unit_of_work": UNIT_OF_WORK,
            "no_source_loyalty": NO_SOURCE_LOYALTY,
            "selected_provider_id": provider_id,
            "selected_provider_entity_id": provider_entity_id,
            "selected_provider_health": health,
            "fallback_rank": rank,
            "fallback_used": rank > 1,
            "attempts": attempts,
            "provenance": {
                "route_chain": route,
                "selected_provider_id": provider_id,
                "selected_provider_entity_id": provider_entity_id,
                "provider_health_proof": provider_proof,
                "field_proof": field_proof,
                "graph_id": verified["graph_id"],
            },
            "fabricated": False,
            "mutation_authority": False,
        }

    return {
        "version": VERSION,
        "ready": False,
        "state": "UNAVAILABLE_AFTER_SOURCE_EXHAUSTION",
        "entity_id": entity_key,
        "entity_type": entity["entity_type"],
        "canonical_key": entity["canonical_key"],
        "field": field_key,
        "unit_of_work": UNIT_OF_WORK,
        "no_source_loyalty": NO_SOURCE_LOYALTY,
        "selected_provider_id": "",
        "fallback_rank": 0,
        "attempts": attempts,
        "provenance": {"route_chain": route, "graph_id": verified["graph_id"]},
        "fabricated": False,
        "mutation_authority": False,
    }


def health_summary(graph: Mapping[str, Any]) -> dict[str, Any]:
    verified = validate_graph(graph)
    rows = [
        {
            "provider_id": provider["provider_id"],
            "health": provider["health"],
            "available_fields": sorted(
                field
                for field, record in (provider.get("fields") or {}).items()
                if str(record.get("status") or "").upper() == "AVAILABLE"
            ),
        }
        for provider in verified["providers"]
    ]
    return {
        "version": VERSION,
        "graph_id": verified["graph_id"],
        "provider_count": len(rows),
        "entity_count": len(verified["entities"]),
        "providers": rows,
        "unit_of_work": UNIT_OF_WORK,
        "no_source_loyalty": NO_SOURCE_LOYALTY,
        "mutation_authority": False,
    }


def _subset(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def evaluate_case(graph: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    operation = str(case.get("operation") or "").strip()
    args = dict(case.get("args") or {})
    if operation == "route_field":
        return route_field(graph, **args)
    if operation == "resolve_identity":
        return resolve_identity(graph, **args)
    if operation == "source_lock":
        try:
            route_field(graph, **args)
        except UnifiedDataIdentityHealthFailure as exc:
            if "SOURCE_LOYALTY_FORBIDDEN" in str(exc):
                return {"status": "BLOCKED", "reason": "SOURCE_LOYALTY_FORBIDDEN"}
            raise
        return {"status": "UNEXPECTEDLY_ALLOWED", "reason": ""}
    if operation == "entity_types":
        verified = validate_graph(graph)
        return {"entity_types": sorted({str(row["entity_type"]) for row in verified["entities"]})}
    raise UnifiedDataIdentityHealthFailure(f"unsupported case operation: {operation}")


def validate_cases(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise UnifiedDataIdentityHealthFailure("cases payload must be an object")
    raw = deepcopy(dict(payload))
    supplied_id = str(raw.pop("cases_id", "") or "").strip().upper()
    if raw.get("version") != CASES_VERSION or int(raw.get("schema_version", 0)) != 1:
        raise UnifiedDataIdentityHealthFailure("cases version/schema mismatch")
    expected_id = _fingerprint(raw, "UDIPHC-")
    if supplied_id != expected_id:
        raise UnifiedDataIdentityHealthFailure("cases fingerprint mismatch")
    basis = raw.get("historical_basis")
    if not isinstance(basis, list) or len(basis) < 4:
        raise UnifiedDataIdentityHealthFailure("cases require historical basis from existing routers")
    graph = validate_graph(raw.get("reference_graph") or {})
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise UnifiedDataIdentityHealthFailure("cases require test cases")
    for case in cases:
        if not isinstance(case, Mapping):
            raise UnifiedDataIdentityHealthFailure("case must be an object")
        expected = case.get("expected")
        if not isinstance(expected, Mapping):
            raise UnifiedDataIdentityHealthFailure("case expected must be an object")
        actual = evaluate_case(graph, case)
        if not _subset(actual, expected):
            raise UnifiedDataIdentityHealthFailure(
                f"case {case.get('case_id')!r} expected {dict(expected)!r} got {actual!r}"
            )
    verified = deepcopy(raw)
    verified["reference_graph"] = graph
    verified["cases_id"] = supplied_id
    return verified


def load_cases(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnifiedDataIdentityHealthFailure(f"unable to load cases: {path}") from exc
    return validate_cases(payload)


def _test_proof(char: str, run_id: int, digest_char: str) -> dict[str, Any]:
    return {
        "proven_sha": char * 40,
        "workflow_run_id": run_id,
        "terminal_receipt_digest": "sha256:" + digest_char * 64,
        "conclusion": "SUCCESS",
    }


def _sample_graph() -> dict[str, Any]:
    p1 = _test_proof("a", 1, "1")
    p2 = _test_proof("b", 2, "2")
    body = {
        "schema_version": 1,
        "version": VERSION,
        "revision": 1,
        "unit_of_work": UNIT_OF_WORK,
        "no_source_loyalty": True,
        "entities": [
            {
                "entity_id": "test:team:a",
                "entity_type": "team",
                "canonical_key": "AAA",
                "canonical_name": "Alpha Team",
                "aliases": [{"value": "A Team", "provider_id": "*"}],
                "provider_ids": {"primary": "P-AAA", "backup": "B-AAA"},
            },
            {
                "entity_id": "test:player:a",
                "entity_type": "player",
                "canonical_key": "player-a",
                "canonical_name": "Alpha Player",
                "aliases": [],
                "provider_ids": {"primary": "P-PLAYER-A"},
            },
            {
                "entity_id": "test:event:a",
                "entity_type": "event",
                "canonical_key": "AAA@BBB",
                "canonical_name": "Alpha at Beta",
                "aliases": [],
                "provider_ids": {"backup": "B-EVENT-A"},
            },
        ],
        "providers": [
            {
                "provider_id": "primary",
                "health": "UNHEALTHY",
                "health_reason": "fixture down",
                "fields": {
                    "roster": {"status": "AVAILABLE", "last_successful_proof": p1},
                    "injuries": {"status": "UNAVAILABLE", "reason": "fixture missing"},
                },
            },
            {
                "provider_id": "backup",
                "health": "HEALTHY",
                "health_reason": "fixture healthy",
                "last_successful_proof": p2,
                "fields": {
                    "roster": {"status": "AVAILABLE", "last_successful_proof": p2},
                    "injuries": {"status": "UNAVAILABLE", "reason": "fixture missing"},
                },
            },
        ],
        "field_routes": {
            "roster": ["primary", "backup"],
            "injuries": ["primary", "backup"],
        },
        "protections": {
            "exact_identity_resolution": True,
            "field_level_routing": True,
            "provider_health_required": True,
            "field_availability_required": True,
            "successful_proof_required_for_usable_source": True,
            "field_level_provenance_required": True,
            "all_provider_failure_fails_closed": True,
            "fabrication_forbidden": True,
            "source_lock_forbidden": True,
            "advisory_only": True,
            "step_2a_required_for_downstream_mutation": True,
            "scope_lease_required_for_downstream_mutation": True,
            "mutation_authority": False,
        },
    }
    return seal_graph(body)


def contract_self_test() -> dict[str, Any]:
    graph = _sample_graph()
    routed = route_field(graph, entity_id="test:team:a", field="roster")
    exhausted = route_field(graph, entity_id="test:team:a", field="injuries")
    identity = resolve_identity(graph, entity_type="team", value="A Team")

    lock_blocked = False
    try:
        route_field(graph, entity_id="test:team:a", field="roster", source_lock="primary")
    except UnifiedDataIdentityHealthFailure as exc:
        lock_blocked = "SOURCE_LOYALTY_FORBIDDEN" in str(exc)

    bad_proof = deepcopy(graph)
    bad_proof.pop("graph_id", None)
    bad_proof["providers"][1].pop("last_successful_proof", None)
    bad_proof = seal_graph(bad_proof)
    missing_proof_blocked = False
    try:
        validate_graph(bad_proof)
    except UnifiedDataIdentityHealthFailure:
        missing_proof_blocked = True

    ambiguous = deepcopy(graph)
    ambiguous.pop("graph_id", None)
    ambiguous["entities"].append(
        {
            "entity_id": "test:team:b",
            "entity_type": "team",
            "canonical_key": "BBB",
            "canonical_name": "Beta Team",
            "aliases": [{"value": "A Team", "provider_id": "*"}],
            "provider_ids": {"primary": "P-BBB"},
        }
    )
    ambiguous = seal_graph(ambiguous)
    ambiguity_blocked = False
    try:
        validate_graph(ambiguous)
    except UnifiedDataIdentityHealthFailure:
        ambiguity_blocked = True

    tampered = deepcopy(graph)
    tampered["revision"] = 2
    tamper_blocked = False
    try:
        validate_graph(tampered)
    except UnifiedDataIdentityHealthFailure:
        tamper_blocked = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "unit_of_work_data_field": routed["unit_of_work"] == UNIT_OF_WORK,
        "unhealthy_primary_falls_back": routed["selected_provider_id"] == "backup" and routed["fallback_rank"] == 2,
        "fallback_provenance_recorded": len(routed["attempts"]) == 2 and routed["provenance"]["field_proof"]["conclusion"] == "SUCCESS",
        "all_provider_failure_unavailable": exhausted["ready"] is False and exhausted["fabricated"] is False,
        "canonical_identity_resolves": identity["ready"] is True and identity["canonical_key"] == "AAA",
        "team_player_event_supported": sorted({row["entity_type"] for row in graph["entities"]}) == ["event", "player", "team"],
        "source_lock_forbidden": lock_blocked,
        "usable_source_requires_proof": missing_proof_blocked,
        "ambiguous_identity_fails_closed": ambiguity_blocked,
        "tamper_fails_closed": tamper_blocked,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "unit_of_work_data_field",
        "unhealthy_primary_falls_back",
        "fallback_provenance_recorded",
        "all_provider_failure_unavailable",
        "canonical_identity_resolves",
        "team_player_event_supported",
        "source_lock_forbidden",
        "usable_source_requires_proof",
        "ambiguous_identity_fails_closed",
        "tamper_fails_closed",
    ]
    if not all(result[name] is True for name in required):
        raise UnifiedDataIdentityHealthFailure("unified identity/provider health self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"] or result["mutation_authority_granted"]:
        raise UnifiedDataIdentityHealthFailure("read-only safety invariant failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="MONSTER V6 unified identity/provider-health graph")
    parser.add_argument("--cases", default="")
    args = parser.parse_args()
    result = contract_self_test()
    if args.cases:
        verified = load_cases(args.cases)
        print(
            "MONSTER_V6_UNIFIED_DATA_IDENTITY_PROVIDER_HEALTH_CASES_GREEN "
            f"id={verified['cases_id']} cases={len(verified['cases'])}"
        )
    print("MONSTER_V6_UNIFIED_DATA_IDENTITY_PROVIDER_HEALTH_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UnifiedDataIdentityHealthFailure as exc:
        print(f"MONSTER_V6_UNIFIED_DATA_IDENTITY_PROVIDER_HEALTH_BLOCKED: {exc}")
        raise SystemExit(1)
