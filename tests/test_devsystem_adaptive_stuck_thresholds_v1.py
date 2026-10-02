from __future__ import annotations

import importlib
import pytest

from devsystem import adaptive_stuck_thresholds_v1 as adaptive
from devsystem import progress_truth_stuck_state_detector_v1 as progress


def _sample(
    run_id: int,
    duration: float,
    *,
    workflow: str = "DevSystem targeted CI",
    job: str = "devsystem-final-gate",
    conclusion: str = "SUCCESS",
    head: str | None = None,
):
    return {
        "workflow_key": workflow,
        "job_key": job,
        "run_id": run_id,
        "head_sha": head or (f"{run_id % 16:x}" * 40),
        "duration_seconds": duration,
        "conclusion": conclusion,
    }


def _history():
    return [
        _sample(201, 92),
        _sample(202, 101),
        _sample(203, 105),
        _sample(204, 113),
        _sample(205, 120),
        _sample(206, 127),
        _sample(207, 2600),
    ]


def test_contract_self_test_is_green_and_safe():
    result = adaptive.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["adaptive_history"] is True
    assert result["cold_start_preserves_existing_timeout"] is True
    assert result["outlier_poisoning_bounded"] is True
    assert result["expected_wait_distinguished"] is True
    assert result["live_authoritative_run_protected"] is True
    assert result["abnormal_stall_detected"] is True
    assert result["frozen_progress_truth_reused"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_cold_start_preserves_existing_timeout_exactly():
    policy = adaptive.derive_threshold(
        _history()[:4],
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    assert policy["mode"] == "COLD_START_FALLBACK"
    assert policy["threshold_seconds"] == 900
    assert policy["sample_count"] == 4
    assert policy["baseline_digest"]


def test_exact_workflow_job_identity_filters_other_history_and_failures():
    samples = _history() + [
        _sample(300, 10, workflow="Other workflow"),
        _sample(301, 10, job="other-job"),
        _sample(302, 999, conclusion="FAILURE"),
    ]
    policy = adaptive.derive_threshold(
        samples,
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    assert policy["mode"] == "ADAPTIVE"
    assert policy["sample_count"] == 7
    assert 300 not in policy["history_run_ids"]
    assert 301 not in policy["history_run_ids"]
    assert 302 not in policy["history_run_ids"]


def test_conflicting_duplicate_run_identity_fails_closed():
    same_head = "a" * 40
    samples = [
        _sample(400, 100, head=same_head),
        _sample(400, 101, head=same_head),
    ]
    with pytest.raises(adaptive.AdaptiveThresholdFailure, match="conflicting history"):
        adaptive.derive_threshold(
            samples,
            workflow_key="DevSystem targeted CI",
            job_key="devsystem-final-gate",
            fallback_seconds=900,
        )


def test_single_slow_success_cannot_poison_threshold_to_ceiling():
    policy = adaptive.derive_threshold(
        _history(),
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    assert policy["mode"] == "ADAPTIVE"
    assert policy["threshold_seconds"] < policy["upper_bound_seconds"]
    assert policy["winsor_cap_seconds"] < 2600


def test_expected_wait_and_live_overdue_run_are_not_stuck():
    policy = adaptive.derive_threshold(
        _history(),
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    expected = adaptive.classify_wait(
        policy,
        elapsed_seconds=policy["threshold_seconds"],
        observed_run_state="IN_PROGRESS",
    )
    assert expected["classification"] == "EXPECTED_WAIT"
    assert expected["stuck"] is False

    live = adaptive.classify_wait(
        policy,
        elapsed_seconds=policy["threshold_seconds"] + 300,
        observed_run_state="IN_PROGRESS",
    )
    assert live["classification"] == "SLOW_BUT_AUTHORITATIVE_RUN_ACTIVE"
    assert live["stuck"] is False
    assert live["duplicate_run_allowed"] is False
    assert live["next_legal_action"] == "WAIT_FOR_TERMINAL_EVENT"


def test_terminal_event_is_consumed_not_called_stuck():
    policy = adaptive.derive_threshold(
        _history(),
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    terminal = adaptive.classify_wait(
        policy,
        elapsed_seconds=policy["threshold_seconds"] + 60,
        observed_run_state="FAILURE",
    )
    assert terminal["classification"] == "TERMINAL_EVENT_AVAILABLE"
    assert terminal["stuck"] is False
    assert terminal["next_legal_action"] == "CONSUME_TERMINAL_EVENT"


def test_overdue_unknown_liveness_routes_to_frozen_detector_without_mutation():
    policy = adaptive.derive_threshold(
        _history(),
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    stalled = adaptive.classify_wait(
        policy,
        elapsed_seconds=policy["threshold_seconds"] + 60,
        observed_run_state="UNKNOWN",
        heartbeat_live=False,
    )
    assert stalled["stuck"] is True
    assert stalled["classification"] == "ABNORMAL_STALL_LIVENESS_UNPROVEN"
    assert stalled["next_legal_action"] == "RUN_FROZEN_STUCK_STATE_DETECTOR"
    assert stalled["mutation_authority"] is False


def test_adaptive_wrapper_changes_only_wait_timeout_on_copy():
    checkpoints = [
        {
            "checkpoint_id": "implementation",
            "label": "Implementation",
            "required": True,
            "weight_bps": 5000,
            "status": "COMPLETE",
            "terminal_evidence": "commit:abc",
        },
        {
            "checkpoint_id": "proof",
            "label": "Exact proof",
            "required": True,
            "weight_bps": 5000,
            "status": "WAITING",
            "owner": "CI",
            "wait_kind": "LEASE_HANDOFF",
            "entered_wait_at_utc": "2026-10-01T00:00:00Z",
            "last_material_event_at_utc": "2026-10-01T00:00:00Z",
            "wait_timeout_seconds": 900,
        },
    ]
    original = [dict(row) for row in checkpoints]
    adapted = adaptive.adapt_waiting_checkpoints(
        checkpoints,
        histories={
            "proof": {
                "workflow_key": "DevSystem targeted CI",
                "job_key": "devsystem-final-gate",
                "samples": _history(),
            }
        },
    )
    assert checkpoints == original
    assert adapted["checkpoints"][0] == checkpoints[0]
    assert adapted["checkpoints"][1]["wait_timeout_seconds"] != 900
    assert adapted["policies"]["proof"]["mode"] == "ADAPTIVE"
    assert adapted["mutation_authority"] is False


def test_frozen_progress_truth_consumes_adaptive_deadline():
    state = progress.new_state("monster-v8-step5-test")
    checkpoints = [
        {
            "checkpoint_id": "implementation",
            "label": "Implementation",
            "required": True,
            "weight_bps": 5000,
            "status": "COMPLETE",
            "terminal_evidence": "commit:abc",
        },
        {
            "checkpoint_id": "proof",
            "label": "Exact proof",
            "required": True,
            "weight_bps": 5000,
            "status": "WAITING",
            "owner": "CI",
            "wait_kind": "LEASE_HANDOFF",
            "entered_wait_at_utc": "2026-10-01T00:00:00Z",
            "last_material_event_at_utc": "2026-10-01T00:00:00Z",
            "wait_timeout_seconds": 900,
        },
    ]
    result = adaptive.evaluate_progress_adaptively(
        state,
        checkpoints=checkpoints,
        now_utc="2026-10-01T00:08:20Z",
        histories={
            "proof": {
                "workflow_key": "DevSystem targeted CI",
                "job_key": "devsystem-final-gate",
                "samples": _history(),
            }
        },
    )
    assert result["result"]["adaptive_stuck_thresholds_version"] == adaptive.VERSION
    assert result["result"]["adaptive_threshold_policies"]["proof"]["mode"] == "ADAPTIVE"
    assert result["result"]["adaptive_threshold_mutation_authority"] is False
    assert result["result"]["stuck"] is True
    assert result["result"]["wait_truth"]["classification"] == "WAIT_DEADLINE_BREACHED"


def test_history_is_bounded_to_latest_fifty_exact_successes():
    samples = [_sample(1000 + i, 100 + (i % 7)) for i in range(70)]
    policy = adaptive.derive_threshold(
        samples,
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    assert policy["sample_count"] == adaptive.MAX_HISTORY_SAMPLES
    assert policy["history_run_ids"][0] == 1020
    assert policy["history_run_ids"][-1] == 1069
