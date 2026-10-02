from __future__ import annotations

import pytest

from devsystem.monotonic_state_ownership_guard_v1 import (
    BACKTRACE_VERSION,
    LINEAGE_VERSION,
    MonotonicStateOwnershipFailure,
    contract_self_test,
    evaluate_write,
)


GOOD = "sha256:" + "1" * 64
NEW = "sha256:" + "2" * 64


def _state():
    return {
        "field": "market.selection",
        "owner_id": "STEP_9",
        "ownership_epoch": 9,
        "authority_rank": 90,
        "generation": 4,
        "last_write_event_id": "step9-v9",
        "value_digest": GOOD,
    }


def _request(**overrides):
    payload = {
        "request_id": "write",
        "field": "market.selection",
        "writer_id": "STEP_9",
        "writer_epoch": 9,
        "writer_authority_rank": 90,
        "expected_generation": 4,
        "observed_owner_id": "STEP_9",
        "observed_owner_epoch": 9,
        "parent_write_event_id": "step9-v9",
        "write_event_id": "step9-v10",
        "proposed_value_digest": NEW,
        "handoff_from_owner_id": "",
        "handoff_from_event_id": "",
    }
    payload.update(overrides)
    return payload


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["step1_version_bound"] is True
    assert result["step2_version_bound"] is True
    assert result["older_upstream_writer_blocked"] is True
    assert result["forged_handoff_blocked"] is True


def test_same_owner_forward_write_is_allowed_and_advances_generation_once():
    result = evaluate_write(_state(), _request())
    assert result["allowed"] is True
    assert result["transition"] == "SAME_OWNER_FORWARD_WRITE"
    assert result["next_state"]["generation"] == 5
    assert result["next_state"]["owner_id"] == "STEP_9"
    assert result["mutation_authority"] is False


def test_old_upstream_epoch_cannot_overwrite_newer_owner():
    result = evaluate_write(
        _state(),
        _request(
            request_id="old-step6",
            writer_id="STEP_6",
            writer_epoch=6,
            writer_authority_rank=60,
            write_event_id="step6-late",
        ),
    )
    assert result["allowed"] is False
    assert result["reason"] == "STALE_OWNERSHIP_EPOCH"
    assert result["current_owner_id"] == "STEP_9"
    assert result["next_legal_action"] == "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"


def test_stale_generation_is_blocked_before_ownership_logic():
    result = evaluate_write(
        _state(),
        _request(expected_generation=3),
    )
    assert result["allowed"] is False
    assert result["reason"] == "STALE_GENERATION"


def test_stale_owner_snapshot_is_blocked():
    result = evaluate_write(
        _state(),
        _request(observed_owner_id="STEP_8"),
    )
    assert result["allowed"] is False
    assert result["reason"] == "STALE_OWNER_SNAPSHOT"


def test_stale_parent_write_is_blocked():
    result = evaluate_write(
        _state(),
        _request(parent_write_event_id="older-event"),
    )
    assert result["allowed"] is False
    assert result["reason"] == "STALE_PARENT_WRITE"


def test_same_epoch_owner_change_is_blocked():
    result = evaluate_write(
        _state(),
        _request(writer_id="STEP_8", writer_authority_rank=95),
    )
    assert result["allowed"] is False
    assert result["reason"] == "SAME_EPOCH_OWNER_CHANGE"


def test_same_owner_cannot_lower_authority_rank():
    result = evaluate_write(
        _state(),
        _request(writer_authority_rank=80),
    )
    assert result["allowed"] is False
    assert result["reason"] == "LOWER_AUTHORITY_RANK"


def test_valid_next_epoch_handoff_is_allowed():
    result = evaluate_write(
        _state(),
        _request(
            writer_id="FINAL_CERT",
            writer_epoch=10,
            writer_authority_rank=100,
            write_event_id="final-write",
            handoff_from_owner_id="STEP_9",
            handoff_from_event_id="step9-v9",
        ),
    )
    assert result["allowed"] is True
    assert result["transition"] == "FORWARD_OWNERSHIP_HANDOFF"
    assert result["next_state"]["owner_id"] == "FINAL_CERT"
    assert result["next_state"]["ownership_epoch"] == 10
    assert result["next_state"]["authority_rank"] == 100
    assert result["next_state"]["generation"] == 5


def test_forged_handoff_is_blocked():
    result = evaluate_write(
        _state(),
        _request(
            writer_id="FINAL_CERT",
            writer_epoch=10,
            writer_authority_rank=100,
            handoff_from_owner_id="STEP_7",
            handoff_from_event_id="step7-old",
        ),
    )
    assert result["allowed"] is False
    assert result["reason"] == "UNPROVEN_OWNERSHIP_HANDOFF"


def test_epoch_gap_is_blocked_even_with_higher_authority():
    result = evaluate_write(
        _state(),
        _request(
            writer_id="FINAL_CERT",
            writer_epoch=11,
            writer_authority_rank=110,
            handoff_from_owner_id="STEP_9",
            handoff_from_event_id="step9-v9",
        ),
    )
    assert result["allowed"] is False
    assert result["reason"] == "OWNERSHIP_EPOCH_GAP"


def test_forward_handoff_cannot_lower_authority():
    result = evaluate_write(
        _state(),
        _request(
            writer_id="FINAL_CERT",
            writer_epoch=10,
            writer_authority_rank=80,
            handoff_from_owner_id="STEP_9",
            handoff_from_event_id="step9-v9",
        ),
    )
    assert result["allowed"] is False
    assert result["reason"] == "LOWER_AUTHORITY_RANK"


def test_blocked_write_is_prepared_for_step2_backtrace():
    result = evaluate_write(
        _state(),
        _request(
            writer_id="STEP_6",
            writer_epoch=6,
            writer_authority_rank=60,
        ),
    )
    assert result["backtrace_trigger"]["version"] == BACKTRACE_VERSION
    assert result["backtrace_trigger"]["trigger"] == "STATE_REGRESSION"
    assert result["backtrace_trigger"]["field"] == "market.selection"


def test_dependencies_are_bound_to_frozen_v7_contract_versions():
    result = contract_self_test()
    assert LINEAGE_VERSION == "MONSTER_V7_CAUSAL_STATE_LINEAGE_GRAPH_V1"
    assert BACKTRACE_VERSION == "MONSTER_V7_AUTOMATIC_ROOT_CAUSE_BACKTRACE_V1"
    assert result["step1_version_bound"] is True
    assert result["step2_version_bound"] is True


def test_field_mismatch_fails_closed():
    with pytest.raises(
        MonotonicStateOwnershipFailure,
        match="request field/state field mismatch",
    ):
        evaluate_write(_state(), _request(field="other.field"))


def test_invalid_digest_fails_closed():
    with pytest.raises(
        MonotonicStateOwnershipFailure,
        match="proposed_value_digest",
    ):
        evaluate_write(_state(), _request(proposed_value_digest="not-a-digest"))


def test_engine_is_read_only_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
