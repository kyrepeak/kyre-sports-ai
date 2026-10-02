from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.execution_heartbeat_deadman_recovery_v1 import (
    new_state as new_heartbeat_state,
    register_worker,
)
from devsystem.progress_truth_stuck_state_detector_v1 import (
    ProgressTruthFailure,
    contract_self_test,
    evaluate_progress,
    new_state,
    validate_state,
)


NOW = "2026-10-02T02:00:00Z"


def _state():
    return new_state("test-workstream")


def _near_complete(status="PENDING", **overrides):
    final = {
        "checkpoint_id": "freeze",
        "label": "Authoritative freeze",
        "required": True,
        "weight_bps": 30,
        "status": status,
        "owner": "FROZEN_REGISTRY",
        "next_action": "REGISTER_FROZEN_CHECKPOINT",
    }
    final.update(overrides)
    return [
        {
            "checkpoint_id": "proof",
            "label": "Proof complete",
            "required": True,
            "weight_bps": 9970,
            "status": "COMPLETE",
            "terminal_evidence": "receipt:proof",
        },
        final,
    ]


def _waiting(
    kind,
    *,
    entered="2026-10-02T01:50:00Z",
    last="2026-10-02T01:59:00Z",
    timeout=120,
    owner="OWNER",
):
    return _near_complete(
        status="WAITING",
        wait_kind=kind,
        entered_wait_at_utc=entered,
        last_material_event_at_utc=last,
        wait_timeout_seconds=timeout,
        owner=owner,
    )


def _expired_heartbeat(run_state):
    hb0 = new_heartbeat_state("owner/repo")
    hb = register_worker(
        hb0,
        workstream_id="proof-run",
        owner_id="worker",
        scope_lease_id="LEASE-1",
        continuation_packet_hash="a" * 64,
        authoritative_run_id=77,
        now_utc="2026-10-02T01:00:00Z",
        expected_revision=hb0["revision"],
        expected_state_hash=hb0["state_hash"],
        heartbeat_ttl_seconds=60,
    )["state"]
    return {
        "freeze": {
            "state": hb,
            "workstream_id": "proof-run",
            "continuation_packet_hash": "a" * 64,
            "observed_run_state": run_state,
        }
    }


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["near_complete_is_exactly_99_7"] is True
    assert result["duplicate_escalation_suppressed"] is True


def test_997_percent_never_rounds_to_100_and_names_remainder():
    result = evaluate_progress(
        _state(),
        checkpoints=_near_complete(),
        now_utc=NOW,
    )["result"]
    assert result["progress_bps"] == 9970
    assert result["progress_display"] == "99.7%"
    assert result["exact_remaining_display"] == "0.3%"
    assert result["next_checkpoint_id"] == "freeze"
    assert result["high_progress_incomplete"] is True
    assert "Authoritative freeze" in result["truth_statement"]


def test_100_percent_requires_every_required_checkpoint_complete():
    plan = _near_complete(
        status="COMPLETE",
        terminal_evidence="receipt:freeze",
        owner="",
        next_action="",
    )
    result = evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)["result"]
    assert result["progress_bps"] == 10000
    assert result["progress_display"] == "100%"
    assert result["complete"] is True
    assert result["decision"] == "PROGRESS_COMPLETE"


def test_complete_checkpoint_without_terminal_evidence_fails_closed():
    plan = _near_complete(
        status="COMPLETE",
        terminal_evidence="",
        owner="",
        next_action="",
    )
    with pytest.raises(ProgressTruthFailure, match="terminal_evidence"):
        evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)


def test_required_weights_must_total_exactly_10000():
    plan = _near_complete()
    plan[0]["weight_bps"] = 9969
    with pytest.raises(ProgressTruthFailure, match="exactly 10000"):
        evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)


def test_later_checkpoint_cannot_complete_before_earlier_required_gate():
    plan = [
        {
            "checkpoint_id": "a",
            "label": "A",
            "required": True,
            "weight_bps": 5000,
            "status": "PENDING",
            "owner": "A",
        },
        {
            "checkpoint_id": "b",
            "label": "B",
            "required": True,
            "weight_bps": 5000,
            "status": "COMPLETE",
            "terminal_evidence": "receipt:b",
        },
    ]
    with pytest.raises(ProgressTruthFailure, match="checkpoint order drift"):
        evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)


def test_optional_checkpoint_does_not_distort_progress():
    plan = _near_complete()
    plan.append({
        "checkpoint_id": "deploy",
        "label": "Deployment not required",
        "required": False,
        "weight_bps": 0,
        "status": "NOT_REQUIRED",
    })
    result = evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)["result"]
    assert result["progress_bps"] == 9970
    assert result["remaining_checkpoint_count"] == 1


def test_pending_checkpoint_reports_exact_next_action():
    result = evaluate_progress(_state(), checkpoints=_near_complete(), now_utc=NOW)["result"]
    assert result["decision"] == "PROGRESS_READY"
    assert result["next_legal_action"] == "REGISTER_FROZEN_CHECKPOINT"


def test_blocked_checkpoint_reports_exact_blocker_and_owner():
    plan = _near_complete(
        status="BLOCKED",
        blocker_reason="registry CAS conflict",
        owner="FROZEN_REGISTRY",
        next_action="REREAD_FROZEN_REGISTRY",
    )
    result = evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)["result"]
    assert result["decision"] == "PROGRESS_BLOCKED"
    assert result["health"] == "RED"
    assert result["blocker"]["reason"] == "registry CAS conflict"
    assert result["blocker"]["owner"] == "FROZEN_REGISTRY"


def test_wait_before_deadline_is_healthy():
    result = evaluate_progress(
        _state(),
        checkpoints=_waiting(
            "FREEZE_REGISTRY_EVENT",
            last="2026-10-02T01:59:30Z",
            timeout=120,
        ),
        now_utc=NOW,
    )["result"]
    assert result["decision"] == "PROGRESS_WAITING_HEALTHY"
    assert result["stuck"] is False
    assert result["wait_truth"]["elapsed_seconds"] == 30


def test_material_event_resets_wait_clock():
    plan = _waiting(
        "FREEZE_REGISTRY_EVENT",
        last="2026-10-02T01:59:50Z",
        timeout=20,
    )
    result = evaluate_progress(
        _state(),
        checkpoints=plan,
        now_utc="2026-10-02T02:00:05Z",
    )["result"]
    assert result["stuck"] is False
    assert result["wait_truth"]["elapsed_seconds"] == 15


def test_overdue_freeze_wait_routes_exact_recovery_once():
    plan = _waiting(
        "FREEZE_REGISTRY_EVENT",
        last="2026-10-02T01:55:00Z",
        timeout=60,
        owner="FROZEN_REGISTRY",
    )
    first = evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)
    second = evaluate_progress(first["state"], checkpoints=plan, now_utc=NOW)
    assert first["result"]["decision"] == "STUCK_STATE_ESCALATION_ISSUED"
    assert first["result"]["next_legal_action"] == "VERIFY_FROZEN_REGISTRY"
    assert second["result"]["decision"] == "STUCK_ESCALATION_SUPPRESSED_WAIT_FOR_EVENT"
    assert second["result"]["duplicate_escalation_suppressed"] is True


def test_new_material_event_creates_new_stuck_fingerprint():
    plan = _waiting(
        "FREEZE_REGISTRY_EVENT",
        last="2026-10-02T01:50:00Z",
        timeout=60,
    )
    first = evaluate_progress(_state(), checkpoints=plan, now_utc=NOW)
    changed = deepcopy(plan)
    changed[1]["last_material_event_at_utc"] = "2026-10-02T01:58:00Z"
    second = evaluate_progress(
        first["state"],
        checkpoints=changed,
        now_utc="2026-10-02T02:00:00Z",
    )
    assert first["result"]["stuck_fingerprint"] != second["result"]["stuck_fingerprint"]
    assert second["result"]["decision"] == "STUCK_STATE_ESCALATION_ISSUED"


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("LEASE_HANDOFF", "INSPECT_ATOMIC_WAIT_QUEUE"),
        ("MERGE_EVENT", "INSPECT_PR_MERGE_GATE"),
        ("DEPLOYMENT_EVENT", "RUN_DEPLOYMENT_CONVERGENCE"),
        ("FREEZE_REGISTRY_EVENT", "VERIFY_FROZEN_REGISTRY"),
    ],
)
def test_non_async_overdue_wait_routes_to_correct_owner(kind, expected):
    result = evaluate_progress(
        _state(),
        checkpoints=_waiting(
            kind,
            last="2026-10-02T01:50:00Z",
            timeout=60,
        ),
        now_utc=NOW,
    )["result"]
    assert result["stuck"] is True
    assert result["next_legal_action"] == expected


def test_async_overdue_without_heartbeat_context_requests_heartbeat_inspection():
    result = evaluate_progress(
        _state(),
        checkpoints=_waiting(
            "EXACT_HEAD_PROOF",
            last="2026-10-02T01:50:00Z",
            timeout=60,
            owner="AUTHORITATIVE_PROOF",
        ),
        now_utc=NOW,
    )["result"]
    assert result["stuck"] is True
    assert result["next_legal_action"] == "INSPECT_EXECUTION_HEARTBEAT"


def test_active_authoritative_run_is_not_misclassified_stuck():
    plan = _waiting(
        "EXACT_HEAD_PROOF",
        entered="2026-10-02T01:00:00Z",
        last="2026-10-02T01:00:00Z",
        timeout=60,
        owner="AUTHORITATIVE_PROOF",
    )
    hb = _expired_heartbeat("in_progress")
    hb["freeze"]["state"]["workers"][0]["expires_at_utc"] = "2026-10-02T01:01:00Z"
    # state hash is now invalid, so build a proper heartbeat fixture instead.
    hb0 = new_heartbeat_state("owner/repo")
    live_state = register_worker(
        hb0,
        workstream_id="proof-run",
        owner_id="worker",
        scope_lease_id="LEASE-1",
        continuation_packet_hash="a" * 64,
        authoritative_run_id=77,
        now_utc="2026-10-02T01:55:00Z",
        expected_revision=hb0["revision"],
        expected_state_hash=hb0["state_hash"],
        heartbeat_ttl_seconds=600,
    )["state"]
    result = evaluate_progress(
        _state(),
        checkpoints=plan,
        now_utc=NOW,
        heartbeat_contexts={
            "freeze": {
                "state": live_state,
                "workstream_id": "proof-run",
                "continuation_packet_hash": "a" * 64,
                "observed_run_state": "in_progress",
            }
        },
    )["result"]
    assert result["stuck"] is False
    assert result["wait_truth"]["classification"] == "OVERDUE_BUT_HEARTBEAT_LIVE"


def test_expired_heartbeat_but_run_still_active_is_not_recovered():
    hb0 = new_heartbeat_state("owner/repo")
    hb = register_worker(
        hb0,
        workstream_id="proof-run",
        owner_id="worker",
        scope_lease_id="LEASE-1",
        continuation_packet_hash="a" * 64,
        authoritative_run_id=77,
        now_utc="2026-10-02T01:00:00Z",
        expected_revision=hb0["revision"],
        expected_state_hash=hb0["state_hash"],
        heartbeat_ttl_seconds=60,
    )["state"]
    result = evaluate_progress(
        _state(),
        checkpoints=_waiting(
            "EXACT_HEAD_PROOF",
            entered="2026-10-02T01:00:00Z",
            last="2026-10-02T01:00:00Z",
            timeout=60,
            owner="AUTHORITATIVE_PROOF",
        ),
        now_utc=NOW,
        heartbeat_contexts={
            "freeze": {
                "state": hb,
                "workstream_id": "proof-run",
                "continuation_packet_hash": "a" * 64,
                "observed_run_state": "in_progress",
            }
        },
    )["result"]
    assert result["stuck"] is False
    assert result["wait_truth"]["classification"] == "OVERDUE_BUT_AUTHORITATIVE_RUN_ACTIVE"
    assert result["next_legal_action"] == "WAIT_FOR_RUN_TERMINAL_EVENT"


def test_dead_man_eligible_routes_one_recovery_receipt():
    hb0 = new_heartbeat_state("owner/repo")
    hb = register_worker(
        hb0,
        workstream_id="proof-run",
        owner_id="worker",
        scope_lease_id="LEASE-1",
        continuation_packet_hash="a" * 64,
        authoritative_run_id=77,
        now_utc="2026-10-02T01:00:00Z",
        expected_revision=hb0["revision"],
        expected_state_hash=hb0["state_hash"],
        heartbeat_ttl_seconds=60,
    )["state"]
    result = evaluate_progress(
        _state(),
        checkpoints=_waiting(
            "EXACT_HEAD_PROOF",
            entered="2026-10-02T01:00:00Z",
            last="2026-10-02T01:00:00Z",
            timeout=60,
            owner="AUTHORITATIVE_PROOF",
        ),
        now_utc=NOW,
        heartbeat_contexts={
            "freeze": {
                "state": hb,
                "workstream_id": "proof-run",
                "continuation_packet_hash": "a" * 64,
                "observed_run_state": "completed",
            }
        },
    )["result"]
    assert result["stuck"] is True
    assert result["wait_truth"]["classification"] == "DEAD_MAN_RECOVERY_ELIGIBLE"
    assert result["next_legal_action"] == "ISSUE_DEAD_MAN_RECOVERY_RECEIPT"


def test_tampered_detector_state_fails_closed():
    state = _state()
    tampered = deepcopy(state)
    tampered["revision"] = 4
    with pytest.raises(ProgressTruthFailure, match="state hash mismatch"):
        validate_state(tampered)


def test_detector_is_pure_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
