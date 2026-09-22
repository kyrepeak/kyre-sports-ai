from __future__ import annotations

from pathlib import Path

import pytest

from sports_api.monster_failure_memory_v1 import (
    DEFAULT_MEMORY,
    FUZZY_MATCHING,
    MAY_AUTO_WRITE_RUNTIME_MEMORY,
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_SOURCE_DATA,
    PROJECTION_WEIGHT,
    FailureMemoryIndex,
    FailureMemoryRecord,
    candidate_memory_record,
    lookup_failure,
    normalize_signature,
    signature_id,
)

ROOT = Path(__file__).resolve().parents[1]


def _record(
    *,
    memory_id: str = "test-memory",
    signature: str = "api runtime value error on route",
    fingerprint: str = "KYRE-ABCDEF123456",
) -> FailureMemoryRecord:
    return FailureMemoryRecord(
        memory_id=memory_id,
        family="api.runtime",
        title="Test incident",
        signature=signature,
        symptoms=("500 response",),
        root_cause="Verified test root cause.",
        fix_summary="Verified test fix.",
        check_first=("Inspect the route.",),
        fingerprints=(fingerprint,) if fingerprint else (),
        pr_number=100,
        commit_sha="abcdef1",
        tests=("unit",),
    )


def test_exact_error_radar_fingerprint_lookup_returns_prior_fix():
    memory = FailureMemoryIndex((_record(),))

    match = memory.lookup_fingerprint("kyre-abcdef123456")

    assert match.found is True
    assert match.exact is True
    assert match.match_type == "fingerprint_exact"
    assert match.records[0].root_cause == "Verified test root cause."
    assert match.records[0].fix_summary == "Verified test fix."
    assert match.records[0].pr_number == 100


def test_signature_lookup_normalizes_only_case_and_whitespace():
    memory = FailureMemoryIndex((_record(signature="CFB   cache miss after market refresh"),))

    match = memory.lookup_signature("  cfb cache MISS after market refresh ")

    assert match.found is True
    assert match.match_type == "signature_exact"


def test_signature_lookup_never_fuzzy_matches_similar_wording():
    memory = FailureMemoryIndex((_record(signature="cfb cache miss after market refresh"),))

    match = memory.lookup_signature("cfb cache misses after sportsbook refresh")

    assert match.found is False
    assert match.status == "NOT_FOUND"
    assert FUZZY_MATCHING is False


def test_signature_id_is_stable_for_normalized_exact_signature():
    assert signature_id("CFB  cache miss") == signature_id(" cfb cache MISS ")
    assert signature_id("cfb cache miss") != signature_id("cfb cache misses")


def test_signature_id_lookup_is_exact():
    record = _record(signature="provider timeout on totals page")
    memory = FailureMemoryIndex((record,))

    match = memory.lookup_signature_id(record.signature_id.lower())

    assert match.found is True
    assert match.records == (record,)


def test_invalid_runtime_fingerprint_is_rejected_without_guessing():
    memory = FailureMemoryIndex((_record(),))

    match = memory.lookup_fingerprint("not-a-kyre-fingerprint")

    assert match.found is False
    assert match.status == "INVALID_QUERY"


def test_unknown_valid_runtime_fingerprint_is_not_found():
    memory = FailureMemoryIndex((_record(),))

    match = memory.lookup_fingerprint("KYRE-000000000000")

    assert match.found is False
    assert match.status == "NOT_FOUND"


def test_duplicate_memory_id_fails_closed():
    first = _record(memory_id="same", signature="first signature", fingerprint="KYRE-111111111111")
    second = _record(memory_id="same", signature="second signature", fingerprint="KYRE-222222222222")

    with pytest.raises(ValueError, match="duplicate memory_id"):
        FailureMemoryIndex((first, second))


def test_duplicate_signature_fails_closed():
    first = _record(memory_id="one", signature="same signature", fingerprint="KYRE-111111111111")
    second = _record(memory_id="two", signature=" SAME   SIGNATURE ", fingerprint="KYRE-222222222222")

    with pytest.raises(ValueError, match="duplicate signature"):
        FailureMemoryIndex((first, second))


def test_duplicate_fingerprint_fails_closed():
    first = _record(memory_id="one", signature="first signature", fingerprint="KYRE-111111111111")
    second = _record(memory_id="two", signature="second signature", fingerprint="KYRE-111111111111")

    with pytest.raises(ValueError, match="duplicate fingerprint"):
        FailureMemoryIndex((first, second))


def test_family_browse_is_exact_and_can_return_multiple_records():
    first = _record(memory_id="one", signature="first signature", fingerprint="KYRE-111111111111")
    second = FailureMemoryRecord(
        memory_id="two",
        family="api.runtime",
        title="Second incident",
        signature="second signature",
        symptoms=("symptom",),
        root_cause="cause",
        fix_summary="fix",
        check_first=("check",),
        fingerprints=("KYRE-222222222222",),
    )
    memory = FailureMemoryIndex((first, second))

    match = memory.lookup_family(" API.RUNTIME ")

    assert match.found is True
    assert len(match.records) == 2
    assert match.exact is False


def test_default_memory_contains_verified_repository_history():
    snapshot = DEFAULT_MEMORY.snapshot()

    assert snapshot["record_count"] == 5
    assert snapshot["fingerprint_count"] == 0
    assert snapshot["fuzzy_matching"] is False
    prs = {record.pr_number for record in DEFAULT_MEMORY.records}
    assert prs == {325, 328, 329, 330, 331}


def test_default_identity_memory_points_to_real_fix_and_guardrails():
    match = lookup_failure(memory_id="cfb-ou-verified-identity-handoff-gated")

    assert match.found is True
    record = match.records[0]
    assert record.pr_number == 325
    assert record.commit_sha == "2baa57563556dfc463866fd03e29b00aadc9261a"
    assert "Slate V15" in record.fix_summary
    assert any("fuzzy" in item.lower() for item in record.check_first)


def test_default_performance_memories_cover_known_root_causes():
    ids = {record.memory_id for record in DEFAULT_MEMORY.records}

    assert "cfb-ou-market-metadata-cache-churn" in ids
    assert "cfb-ou-serialized-provider-waits" in ids
    assert "cfb-ou-repeat-live-odds-fetch" in ids
    assert "cfb-ou-historical-router-cold-start" in ids


def test_candidate_record_is_review_only_and_does_not_mutate_default_memory():
    before = DEFAULT_MEMORY.snapshot()["record_count"]

    candidate = candidate_memory_record(
        family="api.runtime",
        title="New verified failure",
        signature="new verified failure signature",
        symptoms=("500",),
        root_cause="verified cause",
        fix_summary="verified fix",
        check_first=("route",),
        fingerprint="KYRE-123456ABCDEF",
        pr_number=999,
        commit_sha="abcdef1",
        tests=("unit",),
    )

    assert candidate["persistence"] == "manual_review_required"
    assert candidate["fingerprints"] == ["KYRE-123456ABCDEF"]
    assert DEFAULT_MEMORY.snapshot()["record_count"] == before
    assert MAY_AUTO_WRITE_RUNTIME_MEMORY is False


def test_failure_memory_is_model_and_source_read_only():
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    assert FUZZY_MATCHING is False


def test_normalization_does_not_destroy_punctuation_or_reorder_words():
    assert normalize_signature("A/B: timeout") == "a/b: timeout"
    assert normalize_signature("timeout A/B") != normalize_signature("A/B timeout")
