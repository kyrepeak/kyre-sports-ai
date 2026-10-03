from devsystem.descendant_thaw_awareness_v1 import (
    _sample_registry,
    evaluate_descendant_authority,
    self_test,
)


def test_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["authorized_inherited_thaw_certified"] is True
    assert result["inherited_thaw_still_requires_registry_reconciliation"] is True
    assert result["candidate_must_descend_from_authoritative_main"] is True
    assert result["thaw_target_must_be_merged_into_main"] is True
    assert result["exact_candidate_thaw_preserved"] is True
    assert result["aligned_state_stays_green"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_valid_lineage_is_authorized_inherited_thaw():
    registry = _sample_registry()
    result = evaluate_descendant_authority(
        registry,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    assert result["status"] == "GREEN"
    assert result["decision"] == "AUTHORIZED_INHERITED_THAW"
    assert result["hard_failure"] is False
    assert result["inherited_authority_count"] == 1
    assert result["registry_reconciliation_required"] is True
    assert result["step1_barrier_decision"] == "REGISTRY_RECONCILIATION_REQUIRED"


def test_candidate_must_descend_from_authoritative_main():
    registry = _sample_registry()
    result = evaluate_descendant_authority(
        registry,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=False,
    )
    assert result["status"] == "BLOCKED"
    assert result["blocked"][0]["reason"] == "CANDIDATE_NOT_DESCENDED_FROM_AUTHORITATIVE_MAIN"


def test_thaw_target_must_be_merged_into_main():
    registry = _sample_registry()
    result = evaluate_descendant_authority(
        registry,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: False},
        candidate_descends_from_main=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["blocked"][0]["reason"] == "THAW_TARGET_NOT_MERGED_INTO_AUTHORITATIVE_MAIN"


def test_exact_candidate_thaw_behavior_is_preserved():
    registry = _sample_registry()
    result = evaluate_descendant_authority(
        registry,
        {"shared.py": "b" * 40, "keep.py": "c" * 40},
        candidate_head_sha="2" * 40,
        current_main_sha="1" * 40,
        main_descends_from_targets={"2" * 40: False},
        candidate_descends_from_main=False,
    )
    assert result["status"] == "GREEN"
    assert result["decision"] == "EXACT_CANDIDATE_THAW_AUTHORITY"
    assert result["registry_reconciliation_required"] is False


def test_unmatched_blob_never_inherits_authority():
    registry = _sample_registry()
    result = evaluate_descendant_authority(
        registry,
        {"shared.py": "d" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["blocked"][0]["reason"] == "NO_UNIQUE_THAW_BLOB_AUTHORITY"
