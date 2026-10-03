from devsystem.frozen_registry_auto_reconciler_v1 import (
    _sample_registry,
    plan_auto_reconciliation,
    self_test,
)


def test_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["authorized_drift_planned"] is True
    assert result["atomic_all_owner_move"] is True
    assert result["obsolete_thaw_retired"] is True
    assert result["unrelated_thaw_preserved"] is True
    assert result["state_hash_advanced"] is True
    assert result["one_retry_after_state_change_only"] is True
    assert result["idempotent_second_pass"] is True
    assert result["unauthorized_drift_blocked"] is True
    assert result["frozen_deletion_blocked"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False


def test_exact_newly_merged_thaw_can_plan_atomic_reconciliation():
    registry = _sample_registry()
    result = plan_auto_reconciliation(
        registry,
        actual_blobs={"shared.yml": "b" * 40, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=["2" * 40],
    )
    assert result["decision"] == "AUTO_RECONCILIATION_PLANNED"
    assert result["apply_allowed"] is True
    assert result["authorized_mismatch_count"] == 1
    assert len(result["updated_entries"]) == 2
    assert result["retired_empty_thaw_grants"] == ["THAW-SHARED-OLD"]
    assert result["retained_thaw_count"] == 1


def test_same_main_after_reconciliation_is_noop():
    registry = _sample_registry()
    first = plan_auto_reconciliation(
        registry,
        actual_blobs={"shared.yml": "b" * 40, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=["2" * 40],
    )
    second = plan_auto_reconciliation(
        first["planned_registry"],
        actual_blobs={"shared.yml": "b" * 40, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=[],
    )
    assert second["decision"] == "REGISTRY_ALREADY_ALIGNED"
    assert second["apply_allowed"] is False
    assert second["retry_after_apply_allowed"] is False


def test_mismatch_without_newly_merged_exact_thaw_is_blocked():
    result = plan_auto_reconciliation(
        _sample_registry(),
        actual_blobs={"shared.yml": "b" * 40, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=[],
    )
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "UNAUTHORIZED_FROZEN_DRIFT"
    assert result["apply_allowed"] is False


def test_wrong_to_blob_is_blocked_even_with_merged_thaw_target():
    result = plan_auto_reconciliation(
        _sample_registry(),
        actual_blobs={"shared.yml": "e" * 40, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=["2" * 40],
    )
    assert result["decision"] == "UNAUTHORIZED_FROZEN_DRIFT"
    assert result["apply_allowed"] is False


def test_frozen_deletion_is_never_auto_reconciled():
    result = plan_auto_reconciliation(
        _sample_registry(),
        actual_blobs={"shared.yml": None, "keep.py": "c" * 40},
        main_sha="4" * 40,
        merged_authority_heads=[],
    )
    assert result["decision"] == "UNAUTHORIZED_FROZEN_DRIFT"
    assert result["blocked_mismatches"][0]["reason"] == "FROZEN_ARTIFACT_DELETED"


def test_unknown_authority_head_is_rejected():
    import pytest
    from devsystem.frozen_registry_auto_reconciler_v1 import AutoReconciliationFailure

    with pytest.raises(AutoReconciliationFailure, match="not an active thaw target"):
        plan_auto_reconciliation(
            _sample_registry(),
            actual_blobs={"shared.yml": "b" * 40, "keep.py": "c" * 40},
            main_sha="4" * 40,
            merged_authority_heads=["9" * 40],
        )
