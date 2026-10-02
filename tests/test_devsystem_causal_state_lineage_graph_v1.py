from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.causal_state_lineage_graph_v1 import (
    CausalStateLineageFailure,
    backtrace,
    contract_self_test,
    field_lineage,
    seal_graph,
    validate_graph,
    value_digest,
)


def _graph():
    return seal_graph(
        {
            "schema_version": 1,
            "version": "MONSTER_V7_CAUSAL_STATE_LINEAGE_GRAPH_V1",
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
                    "event_id": "w1",
                    "sequence": 1,
                    "kind": "WRITE",
                    "step_id": "STEP_6",
                    "field": "selection",
                    "generation": 1,
                    "value_digest": value_digest("old"),
                    "parent_write_event_id": "",
                    "depends_on_write_ids": [],
                },
                {
                    "event_id": "r1",
                    "sequence": 2,
                    "kind": "READ",
                    "step_id": "STEP_8",
                    "field": "selection",
                    "source_write_event_id": "w1",
                    "observed_generation": 1,
                },
                {
                    "event_id": "reason",
                    "sequence": 3,
                    "kind": "WRITE",
                    "step_id": "STEP_8",
                    "field": "reason",
                    "generation": 1,
                    "value_digest": value_digest("why"),
                    "parent_write_event_id": "",
                    "depends_on_write_ids": ["w1"],
                },
                {
                    "event_id": "w2",
                    "sequence": 4,
                    "kind": "WRITE",
                    "step_id": "STEP_9",
                    "field": "selection",
                    "generation": 2,
                    "value_digest": value_digest("new"),
                    "parent_write_event_id": "w1",
                    "depends_on_write_ids": ["reason"],
                },
                {
                    "event_id": "r2",
                    "sequence": 5,
                    "kind": "READ",
                    "step_id": "FINAL",
                    "field": "selection",
                    "source_write_event_id": "w2",
                    "observed_generation": 2,
                },
            ],
        }
    )


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["exact_writer_recorded"] is True
    assert result["exact_consumers_recorded"] is True
    assert result["stale_consumer_fails_closed"] is True
    assert result["conflicting_generation_fails_closed"] is True
    assert result["missing_writer_fails_closed"] is True
    assert result["tamper_fails_closed"] is True


def test_field_lineage_names_exact_writer_and_consumers():
    result = field_lineage(_graph(), "selection")
    assert result["latest_writer_step"] == "STEP_9"
    assert result["latest_generation"] == 2
    assert result["consumer_steps"] == ["STEP_8", "FINAL"]


def test_backtrace_returns_dependency_order():
    result = backtrace(_graph(), "r2")
    assert result["causal_event_ids"] == ["w1", "reason", "w2", "r2"]


def test_stale_read_after_newer_write_fails_closed():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    graph.pop("head_event_hash", None)
    graph["events"].append(
        {
            "event_id": "stale",
            "sequence": 6,
            "kind": "READ",
            "step_id": "OLD_STEP",
            "field": "selection",
            "source_write_event_id": "w1",
            "observed_generation": 1,
        }
    )
    graph = seal_graph(graph)
    with pytest.raises(CausalStateLineageFailure, match="stale state consumption"):
        validate_graph(graph)


def test_conflicting_generation_fails_closed():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    graph.pop("head_event_hash", None)
    graph["events"].append(
        {
            "event_id": "conflict",
            "sequence": 6,
            "kind": "WRITE",
            "step_id": "OLD_STEP",
            "field": "selection",
            "generation": 2,
            "value_digest": value_digest("wrong"),
            "parent_write_event_id": "w1",
            "depends_on_write_ids": [],
        }
    )
    graph = seal_graph(graph)
    with pytest.raises(CausalStateLineageFailure, match="non-monotonic/conflicting generation"):
        validate_graph(graph)


def test_missing_writer_fails_closed():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    graph.pop("head_event_hash", None)
    graph["events"].append(
        {
            "event_id": "orphan-read",
            "sequence": 6,
            "kind": "READ",
            "step_id": "FINAL_2",
            "field": "missing",
            "source_write_event_id": "no-write",
            "observed_generation": 1,
        }
    )
    graph = seal_graph(graph)
    with pytest.raises(CausalStateLineageFailure, match="missing its source WRITE"):
        validate_graph(graph)


def test_write_parent_must_be_immediately_previous_generation():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    graph.pop("head_event_hash", None)
    graph["events"].append(
        {
            "event_id": "w3",
            "sequence": 6,
            "kind": "WRITE",
            "step_id": "STEP_10",
            "field": "selection",
            "generation": 3,
            "value_digest": value_digest("newest"),
            "parent_write_event_id": "w1",
            "depends_on_write_ids": [],
        }
    )
    graph = seal_graph(graph)
    with pytest.raises(CausalStateLineageFailure, match="WRITE parent"):
        validate_graph(graph)


def test_causal_dependency_must_reference_earlier_write():
    graph = deepcopy(_graph())
    graph.pop("graph_id", None)
    graph.pop("head_event_hash", None)
    graph["events"].append(
        {
            "event_id": "bad-dep",
            "sequence": 6,
            "kind": "WRITE",
            "step_id": "STEP_10",
            "field": "reason",
            "generation": 2,
            "value_digest": value_digest("updated"),
            "parent_write_event_id": "reason",
            "depends_on_write_ids": ["r2"],
        }
    )
    graph = seal_graph(graph)
    with pytest.raises(CausalStateLineageFailure, match="earlier WRITE"):
        validate_graph(graph)


def test_event_chain_tamper_fails_closed():
    graph = _graph()
    graph["events"][0]["step_id"] = "TAMPERED"
    with pytest.raises(CausalStateLineageFailure, match="event hash"):
        validate_graph(graph)


def test_graph_is_read_only_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
