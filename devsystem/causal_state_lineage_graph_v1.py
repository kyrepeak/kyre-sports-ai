"""MONSTER V7 Step 1 — Causal State Lineage Graph V1.

Read-only control-plane contract that records exactly which step wrote each
important state field, the write generation it observed, the earlier writes
that caused it, and the downstream steps that consumed it.

The graph is tamper-evident, sequence-ordered, and fail-closed:
- every READ must point at an existing earlier WRITE for the same field;
- a READ may consume only the latest preceding generation for that field;
- every WRITE generation must advance monotonically by exactly one;
- every non-initial WRITE must point at the immediately previous WRITE;
- causal dependencies may reference only earlier WRITE events;
- event hashes form a chain and the graph carries a content fingerprint.

This module never fetches network data and never grants mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping

VERSION = "MONSTER_V7_CAUSAL_STATE_LINEAGE_GRAPH_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class CausalStateLineageFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def value_digest(value: Any) -> str:
    """Return a deterministic digest for state content without storing the value."""
    return _sha256(value)


def _require_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CausalStateLineageFailure(f"{field} is required")
    return text


def _normalize_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CausalStateLineageFailure("lineage event must be an object")
    event = deepcopy(dict(raw))
    event["event_id"] = _require_text(event.get("event_id"), "event_id")
    event["step_id"] = _require_text(event.get("step_id"), "step_id")
    event["field"] = _require_text(event.get("field"), "field")
    kind = _require_text(event.get("kind"), "kind").upper()
    if kind not in {"WRITE", "READ"}:
        raise CausalStateLineageFailure(f"unsupported event kind: {kind}")
    event["kind"] = kind
    try:
        sequence = int(event.get("sequence"))
    except (TypeError, ValueError) as exc:
        raise CausalStateLineageFailure("sequence must be an integer") from exc
    if sequence <= 0:
        raise CausalStateLineageFailure("sequence must be positive")
    event["sequence"] = sequence

    if kind == "WRITE":
        try:
            generation = int(event.get("generation"))
        except (TypeError, ValueError) as exc:
            raise CausalStateLineageFailure("WRITE generation must be an integer") from exc
        if generation <= 0:
            raise CausalStateLineageFailure("WRITE generation must be positive")
        event["generation"] = generation
        digest = str(event.get("value_digest") or "").strip().lower()
        if not _DIGEST.fullmatch(digest):
            raise CausalStateLineageFailure("WRITE value_digest must be sha256:<64 hex>")
        event["value_digest"] = digest
        parent = str(event.get("parent_write_event_id") or "").strip()
        event["parent_write_event_id"] = parent
        dependencies = event.get("depends_on_write_ids") or []
        if not isinstance(dependencies, list):
            raise CausalStateLineageFailure("depends_on_write_ids must be a list")
        normalized_dependencies = [_require_text(item, "depends_on_write_id") for item in dependencies]
        if len(normalized_dependencies) != len(set(normalized_dependencies)):
            raise CausalStateLineageFailure("depends_on_write_ids contains duplicates")
        event["depends_on_write_ids"] = normalized_dependencies
        event.pop("source_write_event_id", None)
        event.pop("observed_generation", None)
    else:
        source = _require_text(event.get("source_write_event_id"), "source_write_event_id")
        event["source_write_event_id"] = source
        try:
            observed = int(event.get("observed_generation"))
        except (TypeError, ValueError) as exc:
            raise CausalStateLineageFailure("READ observed_generation must be an integer") from exc
        if observed <= 0:
            raise CausalStateLineageFailure("READ observed_generation must be positive")
        event["observed_generation"] = observed
        event.pop("generation", None)
        event.pop("value_digest", None)
        event.pop("parent_write_event_id", None)
        event.pop("depends_on_write_ids", None)

    event["previous_event_hash"] = str(event.get("previous_event_hash") or "").strip().lower()
    event["event_hash"] = str(event.get("event_hash") or "").strip().lower()
    return event


def _event_hash(event: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(event))
    payload.pop("event_hash", None)
    return _sha256(payload)


def seal_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Seal an untrusted graph with an event hash chain and graph fingerprint."""
    if not isinstance(graph, Mapping):
        raise CausalStateLineageFailure("graph must be an object")
    raw = deepcopy(dict(graph))
    raw.pop("graph_id", None)
    raw.pop("head_event_hash", None)
    events = raw.get("events")
    if not isinstance(events, list) or not events:
        raise CausalStateLineageFailure("graph requires lineage events")

    sealed_events: list[dict[str, Any]] = []
    previous = ""
    for source in events:
        event = _normalize_event(source)
        event["previous_event_hash"] = previous
        event["event_hash"] = ""
        event["event_hash"] = _event_hash(event)
        previous = event["event_hash"]
        sealed_events.append(event)

    raw["events"] = sealed_events
    raw["head_event_hash"] = previous
    raw["graph_id"] = _sha256(raw)
    return raw


def validate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        raise CausalStateLineageFailure("graph must be an object")
    raw = deepcopy(dict(graph))
    supplied_graph_id = str(raw.pop("graph_id", "") or "").strip().lower()
    supplied_head = str(raw.get("head_event_hash") or "").strip().lower()

    if raw.get("version") != VERSION or int(raw.get("schema_version", 0)) != 1:
        raise CausalStateLineageFailure("graph version/schema mismatch")
    if int(raw.get("revision") or 0) <= 0:
        raise CausalStateLineageFailure("graph revision must be positive")

    protections = raw.get("protections") or {}
    required_true = (
        "exact_writer_required",
        "exact_consumer_required",
        "monotonic_generation_required",
        "stale_consumption_fails_closed",
        "conflicting_generation_fails_closed",
        "causal_dependencies_must_precede",
        "tamper_evident",
        "step_2a_required_for_mutation",
        "scope_lease_required_for_mutation",
    )
    if not all(protections.get(name) is True for name in required_true):
        raise CausalStateLineageFailure("graph protections drift")
    if protections.get("mutation_authority") is not False:
        raise CausalStateLineageFailure("lineage graph may not grant mutation authority")

    events = raw.get("events")
    if not isinstance(events, list) or not events:
        raise CausalStateLineageFailure("graph requires lineage events")

    event_index: dict[str, dict[str, Any]] = {}
    writes_by_field: dict[str, list[dict[str, Any]]] = {}
    previous_hash = ""
    expected_sequence = 1

    for source in events:
        event = _normalize_event(source)
        if event["sequence"] != expected_sequence:
            raise CausalStateLineageFailure("lineage sequence must be contiguous")
        expected_sequence += 1
        if event["event_id"] in event_index:
            raise CausalStateLineageFailure("event_id must be unique")
        if event["previous_event_hash"] != previous_hash:
            raise CausalStateLineageFailure("event hash chain predecessor mismatch")
        expected_hash = _event_hash(event)
        if event["event_hash"] != expected_hash:
            raise CausalStateLineageFailure("event hash mismatch")

        if event["kind"] == "WRITE":
            prior_writes = writes_by_field.setdefault(event["field"], [])
            expected_generation = len(prior_writes) + 1
            if event["generation"] != expected_generation:
                raise CausalStateLineageFailure(
                    f"non-monotonic/conflicting generation for field {event['field']}"
                )
            expected_parent = prior_writes[-1]["event_id"] if prior_writes else ""
            if event["parent_write_event_id"] != expected_parent:
                raise CausalStateLineageFailure(
                    f"WRITE parent does not match previous generation for field {event['field']}"
                )
            for dependency_id in event["depends_on_write_ids"]:
                dependency = event_index.get(dependency_id)
                if dependency is None or dependency["kind"] != "WRITE":
                    raise CausalStateLineageFailure(
                        f"causal dependency {dependency_id} must reference an earlier WRITE"
                    )
            prior_writes.append(event)
        else:
            source_write = event_index.get(event["source_write_event_id"])
            if source_write is None or source_write["kind"] != "WRITE":
                raise CausalStateLineageFailure(
                    f"READ {event['event_id']} is missing its source WRITE"
                )
            if source_write["field"] != event["field"]:
                raise CausalStateLineageFailure("READ field/source WRITE field mismatch")
            if source_write["generation"] != event["observed_generation"]:
                raise CausalStateLineageFailure("READ observed_generation/source mismatch")
            prior_writes = writes_by_field.get(event["field"], [])
            if not prior_writes:
                raise CausalStateLineageFailure("READ has no preceding WRITE")
            latest = prior_writes[-1]
            if latest["event_id"] != source_write["event_id"]:
                raise CausalStateLineageFailure(
                    f"stale state consumption for field {event['field']}: "
                    f"read={source_write['event_id']} latest={latest['event_id']}"
                )

        event_index[event["event_id"]] = event
        previous_hash = event["event_hash"]

    if supplied_head != previous_hash:
        raise CausalStateLineageFailure("head_event_hash mismatch")

    without_graph_id = deepcopy(raw)
    expected_graph_id = _sha256(without_graph_id)
    if supplied_graph_id != expected_graph_id:
        raise CausalStateLineageFailure("graph fingerprint mismatch")

    verified = deepcopy(raw)
    verified["graph_id"] = supplied_graph_id
    return verified


def field_lineage(graph: Mapping[str, Any], field: str) -> dict[str, Any]:
    verified = validate_graph(graph)
    wanted = _require_text(field, "field")
    writers = [
        {
            "event_id": event["event_id"],
            "step_id": event["step_id"],
            "generation": event["generation"],
            "value_digest": event["value_digest"],
            "depends_on_write_ids": list(event["depends_on_write_ids"]),
        }
        for event in verified["events"]
        if event["kind"] == "WRITE" and event["field"] == wanted
    ]
    consumers = [
        {
            "event_id": event["event_id"],
            "step_id": event["step_id"],
            "source_write_event_id": event["source_write_event_id"],
            "observed_generation": event["observed_generation"],
        }
        for event in verified["events"]
        if event["kind"] == "READ" and event["field"] == wanted
    ]
    if not writers:
        raise CausalStateLineageFailure(f"unknown state field: {wanted}")
    latest = writers[-1]
    return {
        "version": VERSION,
        "graph_id": verified["graph_id"],
        "field": wanted,
        "latest_writer_step": latest["step_id"],
        "latest_write_event_id": latest["event_id"],
        "latest_generation": latest["generation"],
        "writers": writers,
        "consumers": consumers,
        "consumer_steps": [item["step_id"] for item in consumers],
        "mutation_authority": False,
    }


def backtrace(graph: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    verified = validate_graph(graph)
    wanted = _require_text(event_id, "event_id")
    index = {event["event_id"]: event for event in verified["events"]}
    if wanted not in index:
        raise CausalStateLineageFailure(f"unknown lineage event: {wanted}")

    visited: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def walk(current_id: str) -> None:
        if current_id in visited:
            return
        current = index[current_id]
        parents: list[str]
        if current["kind"] == "READ":
            parents = [current["source_write_event_id"]]
        else:
            parents = list(current["depends_on_write_ids"])
            if current["parent_write_event_id"]:
                parents.append(current["parent_write_event_id"])
        for parent_id in parents:
            walk(parent_id)
        visited.add(current_id)
        ordered.append(
            {
                "event_id": current["event_id"],
                "kind": current["kind"],
                "step_id": current["step_id"],
                "field": current["field"],
                "sequence": current["sequence"],
            }
        )

    walk(wanted)
    return {
        "version": VERSION,
        "graph_id": verified["graph_id"],
        "target_event_id": wanted,
        "causal_path": ordered,
        "causal_event_ids": [item["event_id"] for item in ordered],
        "mutation_authority": False,
    }


def _sample_graph() -> dict[str, Any]:
    selection_v1 = value_digest({"selection": "V8"})
    selection_v2 = value_digest({"selection": "V9"})
    reason_v1 = value_digest({"reason": "market-adjusted"})
    return seal_graph(
        {
            "schema_version": 1,
            "version": VERSION,
            "revision": 1,
            "protections": {
                "exact_writer_required": True,
                "exact_consumer_required": True,
                "monotonic_generation_required": True,
                "stale_consumption_fails_closed": True,
                "conflicting_generation_fails_closed": True,
                "causal_dependencies_must_precede": True,
                "tamper_evident": True,
                "step_2a_required_for_mutation": True,
                "scope_lease_required_for_mutation": True,
                "mutation_authority": False,
            },
            "events": [
                {
                    "event_id": "write-selection-v1",
                    "sequence": 1,
                    "kind": "WRITE",
                    "step_id": "STEP_6",
                    "field": "market.selection",
                    "generation": 1,
                    "value_digest": selection_v1,
                    "parent_write_event_id": "",
                    "depends_on_write_ids": [],
                },
                {
                    "event_id": "read-selection-v1",
                    "sequence": 2,
                    "kind": "READ",
                    "step_id": "STEP_8",
                    "field": "market.selection",
                    "source_write_event_id": "write-selection-v1",
                    "observed_generation": 1,
                },
                {
                    "event_id": "write-reason-v1",
                    "sequence": 3,
                    "kind": "WRITE",
                    "step_id": "STEP_8",
                    "field": "market.reason",
                    "generation": 1,
                    "value_digest": reason_v1,
                    "parent_write_event_id": "",
                    "depends_on_write_ids": ["write-selection-v1"],
                },
                {
                    "event_id": "write-selection-v2",
                    "sequence": 4,
                    "kind": "WRITE",
                    "step_id": "STEP_9",
                    "field": "market.selection",
                    "generation": 2,
                    "value_digest": selection_v2,
                    "parent_write_event_id": "write-selection-v1",
                    "depends_on_write_ids": ["write-reason-v1"],
                },
                {
                    "event_id": "read-selection-v2",
                    "sequence": 5,
                    "kind": "READ",
                    "step_id": "FINAL_CERT",
                    "field": "market.selection",
                    "source_write_event_id": "write-selection-v2",
                    "observed_generation": 2,
                },
            ],
        }
    )


def contract_self_test() -> dict[str, Any]:
    graph = _sample_graph()
    verified = validate_graph(graph)
    lineage = field_lineage(graph, "market.selection")
    trace = backtrace(graph, "read-selection-v2")

    stale = deepcopy(graph)
    stale.pop("graph_id", None)
    stale.pop("head_event_hash", None)
    stale["events"].append(
        {
            "event_id": "stale-read",
            "sequence": 6,
            "kind": "READ",
            "step_id": "LEGACY_STEP",
            "field": "market.selection",
            "source_write_event_id": "write-selection-v1",
            "observed_generation": 1,
        }
    )
    stale = seal_graph(stale)
    stale_blocked = False
    try:
        validate_graph(stale)
    except CausalStateLineageFailure as exc:
        stale_blocked = "stale state consumption" in str(exc)

    conflict = deepcopy(graph)
    conflict.pop("graph_id", None)
    conflict.pop("head_event_hash", None)
    conflict["events"].append(
        {
            "event_id": "conflicting-write",
            "sequence": 6,
            "kind": "WRITE",
            "step_id": "LEGACY_STEP",
            "field": "market.selection",
            "generation": 2,
            "value_digest": value_digest({"selection": "OLD"}),
            "parent_write_event_id": "write-selection-v1",
            "depends_on_write_ids": [],
        }
    )
    conflict = seal_graph(conflict)
    conflict_blocked = False
    try:
        validate_graph(conflict)
    except CausalStateLineageFailure as exc:
        conflict_blocked = "non-monotonic/conflicting generation" in str(exc)

    missing = deepcopy(graph)
    missing.pop("graph_id", None)
    missing.pop("head_event_hash", None)
    missing["events"].append(
        {
            "event_id": "missing-source-read",
            "sequence": 6,
            "kind": "READ",
            "step_id": "FINAL_CERT_2",
            "field": "unknown.field",
            "source_write_event_id": "does-not-exist",
            "observed_generation": 1,
        }
    )
    missing = seal_graph(missing)
    missing_blocked = False
    try:
        validate_graph(missing)
    except CausalStateLineageFailure as exc:
        missing_blocked = "missing its source WRITE" in str(exc)

    tampered = deepcopy(graph)
    tampered["events"][0]["step_id"] = "TAMPERED"
    tamper_blocked = False
    try:
        validate_graph(tampered)
    except CausalStateLineageFailure:
        tamper_blocked = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "exact_writer_recorded": lineage["latest_writer_step"] == "STEP_9",
        "exact_consumers_recorded": lineage["consumer_steps"] == ["STEP_8", "FINAL_CERT"],
        "generation_history_recorded": [row["generation"] for row in lineage["writers"]] == [1, 2],
        "causal_backtrace_available": trace["causal_event_ids"] == [
            "write-selection-v1",
            "write-reason-v1",
            "write-selection-v2",
            "read-selection-v2",
        ],
        "stale_consumer_fails_closed": stale_blocked,
        "conflicting_generation_fails_closed": conflict_blocked,
        "missing_writer_fails_closed": missing_blocked,
        "tamper_fails_closed": tamper_blocked,
        "event_chain_complete": verified["head_event_hash"] == graph["head_event_hash"],
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = (
        "exact_writer_recorded",
        "exact_consumers_recorded",
        "generation_history_recorded",
        "causal_backtrace_available",
        "stale_consumer_fails_closed",
        "conflicting_generation_fails_closed",
        "missing_writer_fails_closed",
        "tamper_fails_closed",
        "event_chain_complete",
    )
    if not all(result[name] is True for name in required):
        raise CausalStateLineageFailure("causal state lineage self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"] or result["mutation_authority_granted"]:
        raise CausalStateLineageFailure("read-only safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP1_CAUSAL_STATE_LINEAGE_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CausalStateLineageFailure as exc:
        print(f"MONSTER_V7_STEP1_CAUSAL_STATE_LINEAGE_BLOCKED: {exc}")
        raise SystemExit(1)
