from __future__ import annotations

import pytest

from devsystem import authority_garbage_collector_v1 as gc


MAIN = "b42b320e69d4894ed2ec5bbd3a065824d35d6fff"
D1 = "1" * 64
D2 = "2" * 64


def _completion(digest: str = D1):
    return {
        "decision": "TERMINAL_LATCH_ALREADY_COMPLETE",
        "complete": True,
        "terminal_digest": digest,
        "source_main_sha": MAIN,
    }


def _authority(
    authority_id: str,
    *,
    workstream: str = "step4",
    state: str = "ACTIVE",
    mutation_capable: bool = True,
    immutable_evidence: bool = False,
):
    return {
        "authority_id": authority_id,
        "workstream": workstream,
        "authority_type": "SCOPE_LEASE",
        "state": state,
        "mutation_capable": mutation_capable,
        "immutable_evidence": immutable_evidence,
    }


def test_module_has_no_ambient_mutation_authority():
    assert gc.NETWORK_CALLS is False
    assert gc.AUTO_MUTATE is False
    assert gc.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert gc.MUTATION_AUTHORITY_GRANTED is False
    assert gc.GITHUB_ACTIONS_FALLBACK == 0


def test_incomplete_canonical_truth_blocks_collection():
    completion = _completion()
    completion["complete"] = False
    out = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": completion},
        authorities=[_authority("lease-1")],
    )
    assert out["result"]["decision"] == "AUTHORITY_GC_WAIT_CANONICAL_COMPLETION"
    assert out["result"]["mutation_count"] == 0
    assert out["authorities"][0]["state"] == "ACTIVE"


def test_terminal_workstream_retires_all_mutation_capable_authority():
    authorities = [
        _authority("lease-1", state="ACTIVE"),
        _authority("owner-1", state="READY"),
        _authority("resume-1", state="WAITING"),
    ]
    out = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=authorities,
    )
    assert out["result"]["decision"] == "AUTHORITY_GC_COLLECTED"
    assert out["result"]["mutation_count"] == 3
    assert out["result"]["remaining_target_mutation_authority"] == 0
    assert out["result"]["next_legal_action"] == "RUN_100_PERCENT_FINALIZER"
    assert {item["state"] for item in out["authorities"]} == {"RETIRED"}
    assert set(out["receipt"]["retired_authority_ids"]) == {"lease-1", "owner-1", "resume-1"}


def test_unrelated_current_authority_and_immutable_evidence_are_preserved():
    authorities = [
        _authority("old-step4", workstream="step4"),
        _authority("current-step5", workstream="step5"),
        _authority("proof-receipt", workstream="step4", immutable_evidence=True),
        _authority("read-only", workstream="step4", mutation_capable=False),
    ]
    out = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=authorities,
        protected_authority_ids=["current-step5"],
    )
    by_id = {item["authority_id"]: item for item in out["authorities"]}
    assert by_id["old-step4"]["state"] == "RETIRED"
    assert by_id["current-step5"]["state"] == "ACTIVE"
    assert by_id["proof-receipt"]["state"] == "ACTIVE"
    assert by_id["read-only"]["state"] == "ACTIVE"
    assert out["result"]["unrelated_authority_preserved"] is True
    assert out["result"]["immutable_evidence_preserved"] is True


def test_protected_target_authority_is_fail_closed_not_silently_retired():
    out = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=[_authority("protected-step4")],
        protected_authority_ids=["protected-step4"],
    )
    assert out["result"]["decision"] == "AUTHORITY_GC_PROTECTED_AUTHORITY_REMAINS"
    assert out["result"]["mutation_count"] == 0
    assert out["result"]["remaining_target_mutation_authority"] == 1
    assert out["result"]["next_legal_action"] == "RECONCILE_PROTECTED_AUTHORITY"


def test_second_pass_is_idempotent_and_does_not_create_new_retirements():
    first = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=[_authority("lease-1")],
    )
    second = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=first["authorities"],
    )
    assert second["result"]["decision"] == "AUTHORITY_GC_ALREADY_CLEAN"
    assert second["result"]["mutation_count"] == 0
    assert second["authorities"] == first["authorities"]


def test_receipt_is_deterministic_across_input_order():
    items = [_authority("b"), _authority("a")]
    a = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=items,
    )
    b = gc.collect_authority_garbage(
        target_workstreams=["step4"],
        canonical_completion={"step4": _completion()},
        authorities=list(reversed(items)),
    )
    assert a["receipt"]["receipt_digest"] == b["receipt"]["receipt_digest"]
    assert a["receipt"]["retired_authority_ids"] == ["a", "b"]


def test_multiple_terminal_workstreams_can_be_collected_atomically():
    out = gc.collect_authority_garbage(
        target_workstreams=["step3", "step4"],
        canonical_completion={"step3": _completion(D1), "step4": _completion(D2)},
        authorities=[
            _authority("a3", workstream="step3"),
            _authority("a4", workstream="step4"),
            _authority("a5", workstream="step5"),
        ],
    )
    assert out["result"]["decision"] == "AUTHORITY_GC_COLLECTED"
    assert out["result"]["mutation_count"] == 2
    by_id = {item["authority_id"]: item for item in out["authorities"]}
    assert by_id["a3"]["state"] == "RETIRED"
    assert by_id["a4"]["state"] == "RETIRED"
    assert by_id["a5"]["state"] == "ACTIVE"


def test_duplicate_authority_ids_are_rejected_before_any_cleanup():
    with pytest.raises(gc.AuthorityGarbageCollectorFailure, match="duplicate authority_id"):
        gc.collect_authority_garbage(
            target_workstreams=["step4"],
            canonical_completion={"step4": _completion()},
            authorities=[_authority("dup"), _authority("dup")],
        )
