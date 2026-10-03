from devsystem.root_cause_collapse_engine_v1 import (
    VERSION,
    collapse_failures,
    self_test,
)
from devsystem import failure_packet_v1


def failure(job, fingerprint, *, layer="control-plane", diagnosis="failure"):
    return {
        "job": job,
        "layer": layer,
        "failure_class": "test-failure",
        "failure_fingerprint": fingerprint,
        "evidence_signal": "test-signal",
        "diagnosis": diagnosis,
        "inspect_first": job,
        "remediation_class": "control-plane",
        "retry_policy": "patch-first",
    }


def test_self_test_is_green_and_non_mutating():
    result = self_test()
    assert result["version"] == VERSION
    assert result["status"] == "GREEN"
    assert result["protections"]["one_active_root_at_a_time"] is True
    assert result["protections"]["network_calls"] is False
    assert result["protections"]["auto_mutate"] is False
    assert result["protections"]["may_modify_product_runtime"] is False


def test_cascade_lanes_collapse_into_direct_root():
    root = failure("permanent-contract", "ROOT-1")
    final_gate = failure("devsystem-final-gate", "FINAL-1", layer="devsystem-final-gate")
    receipt = failure("terminal-proof-receipt", "RECEIPT-1", layer="control-plane")
    result = collapse_failures({"primary": root, "failures": [root, final_gate, receipt]})
    assert result["decision"] == "SINGLE_ROOT_COLLAPSED"
    assert result["root_count"] == 1
    assert result["primary_root"]["job"] == "permanent-contract"
    assert {item["job"] for item in result["collapsed_failures"]} == {
        "devsystem-final-gate",
        "terminal-proof-receipt",
    }
    assert [item["job"] for item in result["repair_queue"]] == ["permanent-contract"]


def test_duplicate_failure_signature_collapses_once():
    one = failure("cfb-critical", "SAME-FP", layer="cfb")
    duplicate = failure("cfb-critical-retry-view", "SAME-FP", layer="cfb")
    result = collapse_failures({"primary": one, "failures": [one, duplicate]})
    assert result["root_count"] == 1
    assert result["collapsed_failure_count"] == 1
    assert result["collapsed_failures"][0]["collapse_reason"] == "DUPLICATE_FAILURE_SIGNATURE"


def test_independent_roots_are_not_falsely_merged():
    cfb = failure("cfb-critical", "CFB-ROOT", layer="cfb")
    ci = failure("permanent-contract", "CI-ROOT", layer="control-plane")
    result = collapse_failures({"primary": ci, "failures": [cfb, ci]})
    assert result["decision"] == "MULTIPLE_INDEPENDENT_ROOTS_PRESERVED"
    assert result["root_count"] == 2
    assert result["primary_root"]["job"] == "permanent-contract"
    assert {item["job"] for item in result["repair_queue"]} == {
        "cfb-critical",
        "permanent-contract",
    }


def test_no_failures_is_green_noop():
    result = collapse_failures({"status": "GREEN", "failures": [], "primary": None})
    assert result["decision"] == "NO_FAILURES"
    assert result["root_count"] == 0
    assert result["next_legal_action"] == "NONE"


def test_failure_packet_embeds_root_cause_collapse_contract():
    needs = {
        "permanent-contract": {
            "result": "failure",
            "log_excerpt": "AssertionError frozen artifact mismatch",
        },
        "devsystem-final-gate": {
            "result": "failure",
            "log_excerpt": "required lane permanent-contract failed",
        },
    }
    packet = failure_packet_v1.build_packet(
        needs,
        run_id="123",
        sha="a" * 40,
        ref="refs/pull/1/head",
        source_created_at="2026-10-03T00:00:00Z",
        failed_steps={
            "permanent-contract": ["Enforce authoritative frozen artifact registry"],
            "devsystem-final-gate": ["Aggregate every required DevSystem lane"],
        },
        history_packets=[],
    )
    collapse = packet["root_cause_collapse"]
    assert collapse["root_count"] >= 1
    assert collapse["primary_root"] is not None
    assert collapse["next_legal_action"] == "PATCH_PRIMARY_ROOT_ONLY"
    markdown = failure_packet_v1.render_markdown(packet)
    assert "## Root-Cause Collapse" in markdown
    assert "**Primary root lane:**" in markdown
