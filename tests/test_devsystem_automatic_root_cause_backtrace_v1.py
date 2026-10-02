from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.automatic_root_cause_backtrace_v1 import (
    AutomaticRootCauseBacktraceFailure,
    automatic_backtrace,
    contract_self_test,
)
from devsystem.causal_state_lineage_graph_v1 import seal_graph, value_digest


def _graph():
    good = value_digest({"selection": "V9"})
    bad7 = value_digest({"selection": "V7"})
    bad6 = value_digest({"selection": "V6"})
    other = value_digest({"other": "healthy"})
    graph = seal_graph(
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
                    "event_id": "good",
                    "sequence": 1,
                    "kind": "WRITE",
                    "step_id": "STEP_9",
                    "field": "selection",
                    "generation": 1,
                    "value_digest": good,
                    "parent_write_event_id": "",
                    "depends_on_write_ids": [],
                },
                {
                    "event_id": "good-read",
                    "sequence": 2,
                    "kind": "READ",
                    "step_id": "STEP_8",
                    "field": "selection",
                    "source_write_event_id": "good",
                    "observed_generation": 1,
                },
                {
                    "event_id": "other-write",
                    "sequence": 3,
                    "kind": "WRITE",
                    "step_id": "OTHER_STEP",
                    "field": "other.field",
                    "generation": 1,
                    "value_digest": other,
                    "parent_write_event_id": "",
                    "depends_on_write_ids": [],
                },
                {
                    "event_id": "first-bad",
                    "sequence": 4,
                    "kind": "WRITE",
                    "step_id": "STEP_7",
                    "field": "selection",
                    "generation": 2,
                    "value_digest": bad7,
                    "parent_write_event_id": "good",
                    "depends_on_write_ids": ["good"],
                },
                {
                    "event_id": "bad-read",
                    "sequence": 5,
                    "kind": "READ",
                    "step_id": "STEP_7_CERT",
                    "field": "selection",
                    "source_write_event_id": "first-bad",
                    "observed_generation": 2,
                },
                {
                    "event_id": "later-bad",
                    "sequence": 6,
                    "kind": "WRITE",
                    "step_id": "STEP_6",
                    "field": "selection",
                    "generation": 3,
                    "value_digest": bad6,
                    "parent_write_event_id": "first-bad",
                    "depends_on_write_ids": ["first-bad"],
                },
                {
                    "event_id": "final",
                    "sequence": 7,
                    "kind": "READ",
                    "step_id": "FINAL_CERT",
                    "field": "selection",
                    "source_write_event_id": "later-bad",
                    "observed_generation": 3,
                },
            ],
        }
    )
    return graph, good


def _incident(good, **overrides):
    payload = {
        "incident_id": "stall-97-7",
        "trigger": "PROGRESS_STALL",
        "field": "selection",
        "target_event_id": "final",
        "expected_value_digest": good,
        "last_known_good_write_id": "good",
        "observed_progress_percent": 97.7,
    }
    payload.update(overrides)
    return payload


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["first_divergent_writer_identified"] is True
    assert result["nearest_symptom_writer_not_misblamed"] is True
    assert result["insufficient_evidence_never_guesses"] is True
    assert result["tampered_step1_lineage_fails_closed"] is True


def test_first_bad_writer_is_root_cause_not_nearest_symptom_writer():
    graph, good = _graph()
    result = automatic_backtrace(graph, _incident(good))
    assert result["decision"] == "ROOT_CAUSE_IDENTIFIED"
    assert result["root_cause_event_id"] == "first-bad"
    assert result["root_cause_step_id"] == "STEP_7"
    assert result["target_write_step_id"] == "STEP_6"
    assert result["symptom_step_is_root_cause"] is False
    assert result["patch_owner_step_id"] == "STEP_7"


def test_backtrace_walks_writer_chain_to_proven_good_anchor():
    graph, good = _graph()
    result = automatic_backtrace(graph, _incident(good))
    assert result["writer_parent_chain_from_target"] == [
        "later-bad",
        "first-bad",
        "good",
    ]
    assert [row["step_id"] for row in result["writers_examined"]] == [
        "STEP_6",
        "STEP_7",
        "STEP_9",
    ]


def test_affected_consumers_are_recorded_after_first_divergence():
    graph, good = _graph()
    result = automatic_backtrace(graph, _incident(good))
    assert result["affected_consumer_steps"] == ["STEP_7_CERT", "FINAL_CERT"]


def test_unrelated_field_does_not_pollute_root_cause():
    graph, good = _graph()
    result = automatic_backtrace(graph, _incident(good))
    assert all(row["field"] == "selection" for row in result["causal_path"])
    assert all(row["step_id"] != "OTHER_STEP" for row in result["causal_path"])


def test_target_before_regression_has_no_false_attribution():
    graph, good = _graph()
    result = automatic_backtrace(
        graph,
        _incident(
            good,
            incident_id="before-regression",
            target_event_id="good-read",
            observed_progress_percent=55.0,
        ),
    )
    assert result["decision"] == "NO_CAUSAL_DIVERGENCE_FOUND"
    assert result["root_cause_found"] is False
    assert result["reason"] == "TARGET_PATH_NEVER_DIVERGED_FROM_EXPECTED_VALUE"


def test_missing_proven_good_evidence_never_guesses():
    graph, _ = _graph()
    result = automatic_backtrace(
        graph,
        {
            "incident_id": "insufficient",
            "trigger": "BAD_FINAL_STATE",
            "field": "selection",
            "target_event_id": "final",
            "observed_progress_percent": 99.7,
        },
    )
    assert result["decision"] == "NO_CAUSAL_DIVERGENCE_FOUND"
    assert result["root_cause_found"] is False
    assert result["reason"] == "INSUFFICIENT_PROVEN_GOOD_VALUE_EVIDENCE"
    assert result["next_legal_action"] == "INSPECT_NON_LINEAGE_BLOCKER"


def test_expected_digest_can_find_closest_good_anchor_without_explicit_id():
    graph, good = _graph()
    result = automatic_backtrace(
        graph,
        {
            "incident_id": "digest-only",
            "trigger": "STATE_REGRESSION",
            "field": "selection",
            "target_event_id": "final",
            "expected_value_digest": good,
            "observed_progress_percent": 98.0,
        },
    )
    assert result["root_cause_event_id"] == "first-bad"
    assert result["proven_good_event_id"] == "good"


def test_anchor_digest_mismatch_fails_closed():
    graph, _ = _graph()
    with pytest.raises(
        AutomaticRootCauseBacktraceFailure,
        match="does not match expected_value_digest",
    ):
        automatic_backtrace(
            graph,
            _incident(
                "sha256:" + "f" * 64,
            ),
        )


def test_target_field_mismatch_fails_closed():
    graph, good = _graph()
    with pytest.raises(
        AutomaticRootCauseBacktraceFailure,
        match="field does not match",
    ):
        automatic_backtrace(
            graph,
            _incident(good, target_event_id="other-write"),
        )


def test_last_known_good_after_target_fails_closed():
    graph, good = _graph()
    with pytest.raises(
        AutomaticRootCauseBacktraceFailure,
        match="occurs after target",
    ):
        automatic_backtrace(
            graph,
            _incident(
                good,
                target_event_id="good-read",
                last_known_good_write_id="later-bad",
            ),
        )


def test_tampered_step1_lineage_is_rejected_before_attribution():
    graph, good = _graph()
    tampered = deepcopy(graph)
    tampered["events"][3]["step_id"] = "HIDDEN"
    with pytest.raises(
        AutomaticRootCauseBacktraceFailure,
        match="Step-1 lineage validation failed",
    ):
        automatic_backtrace(tampered, _incident(good))


def test_target_defaults_to_latest_field_event():
    graph, good = _graph()
    incident = _incident(good)
    incident["target_event_id"] = ""
    result = automatic_backtrace(graph, incident)
    assert result["target_event_id"] == "final"
    assert result["root_cause_step_id"] == "STEP_7"


def test_progress_context_is_preserved_but_does_not_change_causality():
    graph, good = _graph()
    low = automatic_backtrace(
        graph,
        _incident(good, incident_id="low", observed_progress_percent=70.0),
    )
    high = automatic_backtrace(
        graph,
        _incident(good, incident_id="high", observed_progress_percent=99.9),
    )
    assert low["root_cause_event_id"] == high["root_cause_event_id"] == "first-bad"
    assert low["observed_progress_percent"] == 70.0
    assert high["observed_progress_percent"] == 99.9


def test_engine_is_read_only_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
