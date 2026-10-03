from devsystem.registry_reconciliation_barrier_v1 import (
    evaluate_barrier,
    self_test,
    _sample_registry,
)


def test_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["aligned_registry_ready"] is True
    assert result["unrelated_main_advance_does_not_block"] is True
    assert result["exact_candidate_thaw_allowed"] is True
    assert result["newly_merged_inherited_thaw_waits_for_reconciliation"] is True
    assert result["wait_is_not_hard_failure"] is True
    assert result["unauthorized_drift_blocks"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_registry_source_can_lag_when_frozen_blobs_are_still_aligned():
    registry = _sample_registry()
    result = evaluate_barrier(
        registry,
        {"shared.py": "a" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="9" * 40,
        newly_merged_targets=[],
    )
    assert result["decision"] == "FROZEN_REGISTRY_READY"
    assert result["allow_frozen_verification"] is True


def test_exact_candidate_thaw_is_not_misclassified_as_registry_lag():
    registry = _sample_registry()
    result = evaluate_barrier(
        registry,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="2" * 40,
        current_main_sha="1" * 40,
        newly_merged_targets=[],
    )
    assert result["status"] == "GREEN"
    assert result["exact_candidate_thaw_count"] == 1
    assert result["reconciliation_mismatch_count"] == 0


def test_newly_merged_inherited_thaw_becomes_wait_not_fail():
    registry = _sample_registry()
    result = evaluate_barrier(
        registry,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="4" * 40,
        newly_merged_targets=["2" * 40],
    )
    assert result["status"] == "WAIT"
    assert result["decision"] == "REGISTRY_RECONCILIATION_REQUIRED"
    assert result["allow_frozen_verification"] is False
    assert result["hard_failure"] is False
    assert result["next_legal_action"] == "WAIT_FOR_AUTHORITATIVE_REGISTRY_RECONCILIATION"


def test_unrelated_frozen_drift_stays_hard_blocked():
    registry = _sample_registry()
    result = evaluate_barrier(
        registry,
        {"shared.py": "d" * 40, "keep.py": "c" * 40},
        candidate_head_sha="3" * 40,
        current_main_sha="4" * 40,
        newly_merged_targets=[],
    )
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "UNAUTHORIZED_FROZEN_DRIFT"
    assert result["hard_failure"] is True
    assert result["blocked_mismatch_count"] == 1
