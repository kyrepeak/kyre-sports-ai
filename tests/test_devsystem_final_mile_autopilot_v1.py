from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.deployment_convergence_controller_v1 import (
    build_convergence_decision,
)
from devsystem.final_mile_autopilot_v1 import (
    FinalMileAutopilotFailure,
    advance,
    contract_self_test,
    new_state,
    validate_state,
)
from devsystem.terminal_proof_receipt_v1 import build_receipt


HEAD = "a" * 40
MERGE = "b" * 40


def _receipt(sha, run=1):
    return build_receipt(
        repository="owner/repo",
        checkpoint_id="CP",
        head_sha=sha,
        authoritative_run=run,
        authoritative_workflow="proof",
        test_count=7,
        required_lanes={"focused": "success", "devsystem": "success"},
        scope_diff=["devsystem/x.py"],
        freeze_tokens=["GREEN", "FROZEN"],
    )


def _state(deployment=False, ticket=""):
    return new_state(
        task_id="task",
        checkpoint_id="CP",
        target_head_sha=HEAD,
        deployment_required=deployment,
        wait_ticket_id=ticket,
    )


def _to_proof(state=None):
    state = state or _state()
    return advance(
        state,
        {"lease": {"state": "HELD", "head_sha": HEAD}},
    )


def _to_merge(state=None):
    proof = _to_proof(state)
    return advance(
        proof["state"],
        {"exact_head_receipt": _receipt(HEAD, 1)},
    )


def _to_cert(state=None):
    merge = _to_merge(state)
    return advance(
        merge["state"],
        {
            "merge": {
                "merged": True,
                "head_sha": HEAD,
                "merge_sha": MERGE,
            }
        },
    )


def _to_after_cert(deployment=False):
    cert = _to_cert(_state(deployment=deployment))
    return advance(
        cert["state"],
        {"merged_main_receipt": _receipt(MERGE, 2)},
    )


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["static_path_finishes"] is True
    assert result["terminal_proof_failure_routes_to_backtrace"] is True


def test_initial_action_is_acquire_or_queue_once():
    state = _state()
    first = advance(state, {})
    second = advance(first["state"], {})
    assert first["result"]["action"] == "ACQUIRE_OR_QUEUE_SCOPE_LEASE"
    assert second["result"]["decision"] == "WAIT_FOR_LEASE_STATE_EVENT"
    assert second["result"]["duplicate_action_suppressed"] is True


def test_wait_ticket_uses_event_wait_without_polling():
    result = advance(_state(ticket="WAIT-1"), {})
    assert result["result"]["decision"] == "WAIT_FOR_LEASE_HANDOFF_EVENT"
    assert result["result"]["polling_required"] is False
    assert result["state"]["revision"] == 0


def test_exact_handoff_ticket_is_required_when_ticket_exists():
    good = advance(
        _state(ticket="WAIT-1"),
        {
            "lease": {
                "state": "HELD",
                "head_sha": HEAD,
                "wait_ticket_id": "WAIT-1",
            }
        },
    )
    bad = advance(
        _state(ticket="WAIT-1"),
        {
            "lease": {
                "state": "HELD",
                "head_sha": HEAD,
                "wait_ticket_id": "WAIT-2",
            }
        },
    )
    assert good["result"]["action"] == "RUN_EXACT_HEAD_PROOF"
    assert bad["result"]["decision"] == "FINAL_MILE_BLOCKED"
    assert bad["state"]["blocked"]["reason"] == "LEASE_HANDOFF_TICKET_MISMATCH"


def test_lease_wrong_head_blocks():
    result = advance(
        _state(),
        {"lease": {"state": "HELD", "head_sha": "c" * 40}},
    )
    assert result["result"]["decision"] == "FINAL_MILE_BLOCKED"
    assert result["state"]["blocked"]["reason"] == "LEASE_BOUND_TO_WRONG_HEAD"


def test_proof_action_is_single_use():
    proof = _to_proof()
    repeated = advance(proof["state"], {})
    assert proof["result"]["action"] == "RUN_EXACT_HEAD_PROOF"
    assert repeated["result"]["decision"] == "WAIT_FOR_EXACT_HEAD_PROOF_EVENT"
    assert repeated["result"]["duplicate_action_suppressed"] is True


def test_wrong_exact_head_receipt_blocks():
    proof = _to_proof()
    result = advance(
        proof["state"],
        {"exact_head_receipt": _receipt("c" * 40)},
    )
    assert result["state"]["phase"] == "BLOCKED"
    assert result["state"]["blocked"]["reason"] == "EXACT_HEAD_RECEIPT_SHA_MISMATCH"


def test_green_exact_head_receipt_advances_directly_to_merge_action():
    result = _to_merge()
    assert result["state"]["phase"] == "MERGE_EXACT_HEAD"
    assert result["result"]["action"] == "MERGE_EXACT_PROVEN_HEAD"


def test_merge_must_be_exact_proven_head():
    merge = _to_merge()
    result = advance(
        merge["state"],
        {
            "merge": {
                "merged": True,
                "head_sha": "c" * 40,
                "merge_sha": MERGE,
            }
        },
    )
    assert result["state"]["phase"] == "BLOCKED"
    assert result["state"]["blocked"]["reason"] == "MERGED_HEAD_SHA_MISMATCH"


def test_exact_merge_advances_to_merged_main_cert_action():
    result = _to_cert()
    assert result["state"]["merge_sha"] == MERGE
    assert result["state"]["phase"] == "CERTIFY_MERGED_MAIN"
    assert result["result"]["action"] == "RUN_MERGED_MAIN_CERTIFICATION"


def test_wrong_merged_main_receipt_blocks():
    cert = _to_cert()
    result = advance(
        cert["state"],
        {"merged_main_receipt": _receipt("c" * 40, 2)},
    )
    assert result["state"]["phase"] == "BLOCKED"
    assert result["state"]["blocked"]["reason"] == "MERGED_MAIN_RECEIPT_SHA_MISMATCH"


def test_static_path_skips_deployment_and_requests_freeze():
    result = _to_after_cert(deployment=False)
    assert result["state"]["phase"] == "FREEZE"
    assert result["result"]["action"] == "REGISTER_FROZEN_CHECKPOINT"


def test_deployment_path_requests_convergence_after_merged_main_cert():
    result = _to_after_cert(deployment=True)
    assert result["state"]["phase"] == "DEPLOY_CERTIFY"
    assert result["result"]["action"] == "START_OR_RESUME_DEPLOYMENT_CONVERGENCE"


def test_inflight_deployment_waits_on_event_without_polling():
    start = _to_after_cert(deployment=True)
    decision = build_convergence_decision(
        expected_sha=MERGE,
        observed_sha="",
        deploy_phase="BUILDING",
        health_ok=None,
        readiness_ok=None,
        ui_ok=None,
    )
    result = advance(start["state"], {"deployment": decision})
    assert result["result"]["decision"] == "WAIT_FOR_DEPLOYMENT_EVENT"
    assert result["result"]["polling_required"] is False


def test_converged_deployment_advances_to_freeze():
    start = _to_after_cert(deployment=True)
    decision = build_convergence_decision(
        expected_sha=MERGE,
        observed_sha=MERGE,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    result = advance(start["state"], {"deployment": decision})
    assert result["state"]["phase"] == "FREEZE"
    assert result["result"]["action"] == "REGISTER_FROZEN_CHECKPOINT"


def test_deployment_expected_sha_drift_blocks():
    start = _to_after_cert(deployment=True)
    decision = build_convergence_decision(
        expected_sha="c" * 40,
        observed_sha="c" * 40,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    result = advance(start["state"], {"deployment": decision})
    assert result["state"]["phase"] == "BLOCKED"
    assert result["state"]["blocked"]["reason"] == "DEPLOYMENT_EXPECTED_SHA_MISMATCH"


def test_bounded_deployment_action_is_issued_only_once():
    start = _to_after_cert(deployment=True)
    decision = build_convergence_decision(
        expected_sha=MERGE,
        observed_sha="c" * 40,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    first = advance(start["state"], {"deployment": decision})
    second = advance(first["state"], {"deployment": decision})
    assert first["result"]["action"] in {"REFRESH_DEPLOYMENT", "FULL_REDEPLOY"}
    assert second["result"]["decision"] == "WAIT_FOR_DEPLOYMENT_EVENT"
    assert second["result"]["duplicate_action_suppressed"] is True


def test_terminal_failure_never_retries_and_routes_to_backtrace():
    proof = _to_proof()
    result = advance(
        proof["state"],
        {
            "failures": {
                "exact_head_proof": {
                    "terminal": True,
                    "run_id": 9,
                    "class": "DETERMINISTIC",
                }
            }
        },
    )
    assert result["result"]["decision"] == "FINAL_MILE_BLOCKED"
    assert result["result"]["next_legal_action"] == "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"


def test_exact_freeze_evidence_completes_static_path():
    freeze = _to_after_cert(deployment=False)
    result = advance(
        freeze["state"],
        {
            "freeze": {
                "status": "FROZEN",
                "checkpoint_id": "CP",
                "source_main_sha": MERGE,
            }
        },
    )
    assert result["result"]["decision"] == "FINAL_MILE_DONE"
    assert result["state"]["phase"] == "DONE"


def test_wrong_freeze_source_sha_blocks():
    freeze = _to_after_cert(deployment=False)
    result = advance(
        freeze["state"],
        {
            "freeze": {
                "status": "FROZEN",
                "checkpoint_id": "CP",
                "source_main_sha": "c" * 40,
            }
        },
    )
    assert result["state"]["phase"] == "BLOCKED"
    assert result["state"]["blocked"]["reason"] == "FROZEN_SOURCE_SHA_MISMATCH"


def test_state_hash_tamper_fails_closed():
    state = _state()
    tampered = deepcopy(state)
    tampered["phase"] = "DONE"
    with pytest.raises(
        FinalMileAutopilotFailure,
        match="state hash mismatch",
    ):
        validate_state(tampered)


def test_controller_never_grants_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
