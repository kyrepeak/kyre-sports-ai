from pathlib import Path

SOURCE = Path("runless_v2/finalization_convergence.py")


def test_step5_is_orchestration_only_and_has_no_second_transport_authority():
    text = SOURCE.read_text()
    assert "httpx" not in text
    assert "requests" not in text
    assert "subprocess" not in text
    assert "api.github.com" not in text
    assert "supabase" not in text.lower()
    assert "merge_exact_candidate" in text
    assert "finalize_certified_candidate" in text
    assert "closeout_green_frozen" in text


def test_step5_preserves_exact_candidate_and_canonical_readback_guards():
    text = SOURCE.read_text()
    assert "MERGE_AUTHORIZED" in text
    assert "MERGE_CANDIDATE_MISMATCH" in text
    assert "MERGED_MAIN_READBACK_MISMATCH" in text
    assert "CANONICAL_READBACK_FAILED" in text
    assert "STEP5_ALREADY_GREEN_FROZEN" in text
