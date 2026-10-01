from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.detached_execution_continuation_v1 import build_packet
from devsystem.event_driven_resume_v1 import (
    EventDrivenResumeFailure,
    build_event,
    build_watch,
    build_watch_from_packet,
    consume_ready,
    contract_self_test,
    ingest_event,
    new_state,
    register_watch,
    resume_decision,
    validate_state,
)


LEASE = {
    "owner_id": "chat:step3",
    "lease_id": "SCOPE-LEASE-STEP3",
    "generation": 1,
    "revision": 1,
    "state_hash": "1" * 64,
}
REGISTRY = {"revision": 11, "state_hash": "2" * 64, "checkpoint_count": 25}


def _packet(workstream: str = "monster-v5-step3"):
    return build_packet(
        workstream_id=workstream,
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        current_step=3,
        total_steps=5,
        step_title="Event-Driven Resume",
        execution_state="READY",
        branch="feature",
        head_sha="a" * 40,
        main_sha="b" * 40,
        pr_number=1300,
        authoritative_run_id=77,
        authoritative_job_id=None,
        async_state="SUCCESS",
        scope_lease=LEASE,
        frozen_registry=REGISTRY,
        blocker=None,
        last_completed_action="watch registered",
        next_legal_action="MERGE_PR_1300",
        worker_id="worker-a",
    )


def _registered():
    packet = _packet()
    state = new_state("owner/repo")
    watch = build_watch_from_packet(
        packet,
        event_kind="WORKFLOW_RUN",
        selector={"run_id": "77"},
        trigger="TERMINAL",
        next_legal_action="CLASSIFY_RUN_77_TERMINAL",
    )
    saved = register_watch(
        state, watch,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    return packet, saved["state"], watch


def test_material_event_wakes_exact_workstream_once():
    packet, state, watch = _registered()
    event = build_event(
        event_kind="WORKFLOW_RUN",
        selector={"run_id": "77"},
        value="SUCCESS",
        source_id="github-run-77",
    )
    fired = ingest_event(
        state, event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    assert fired["result"]["decision"] == "EVENT_MATERIAL_RESUME_READY"
    assert fired["result"]["ready_workstreams"] == [packet["workstream_id"]]
    assert fired["result"]["mutation_authority_granted"] is False
    assert fired["state"]["watches"][watch["watch_id"]]["status"] == "FIRED"

    duplicate = ingest_event(
        fired["state"], event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=fired["state"]["revision"],
        expected_state_hash=fired["state"]["state_hash"],
    )
    assert duplicate["result"]["decision"] == "EVENT_ALREADY_CONSUMED"
    assert duplicate["result"]["duplicate_wake_blocked"] is True


def test_resume_receipt_is_bound_to_current_continuation_hash():
    packet, state, _ = _registered()
    event = build_event(
        event_kind="WORKFLOW_RUN",
        selector={"run_id": "77"},
        value="SUCCESS",
        source_id="github-run-77",
    )
    fired = ingest_event(
        state, event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    ready = resume_decision(
        fired["state"],
        workstream_id=packet["workstream_id"],
        current_continuation_packet_hash=packet["packet_hash"],
    )
    assert ready["decision"] == "EVENT_READY_TO_RESUME"
    assert ready["polling_required"] is False
    assert ready["mutation_authority_granted"] is False
    assert ready["step_2a_required"] is True

    drift = resume_decision(
        fired["state"],
        workstream_id=packet["workstream_id"],
        current_continuation_packet_hash="3" * 64,
    )
    assert drift["decision"] == "EVENT_RESUME_CONTINUATION_DRIFT"


def test_ready_receipt_is_consumed_once():
    packet, state, _ = _registered()
    event = build_event(
        event_kind="WORKFLOW_RUN",
        selector={"run_id": "77"},
        value="FAILURE",
        source_id="github-run-77",
    )
    fired = ingest_event(
        state, event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    consumed = consume_ready(
        fired["state"],
        workstream_id=packet["workstream_id"],
        event_fingerprint=event["event_fingerprint"],
        expected_revision=fired["state"]["revision"],
        expected_state_hash=fired["state"]["state_hash"],
    )
    assert consumed["result"]["decision"] == "EVENT_READY_RECEIPT_CONSUMED"
    assert consumed["result"]["mutation_authority_granted"] is False

    second = consume_ready(
        consumed["state"],
        workstream_id=packet["workstream_id"],
        event_fingerprint=event["event_fingerprint"],
        expected_revision=consumed["state"]["revision"],
        expected_state_hash=consumed["state"]["state_hash"],
    )
    assert second["result"]["decision"] == "EVENT_READY_RECEIPT_NOT_FOUND"


@pytest.mark.parametrize(
    ("kind", "trigger", "value", "selector"),
    [
        ("LEASE_STATE", "FREE", "FREE", {"lease_id": "x"}),
        ("PR_STATE", "MERGED", "MERGED", {"pr": "1300"}),
        ("DEPLOYMENT_STATE", "TERMINAL", "SUCCESS", {"environment": "production"}),
        ("REGISTRY_STATE", "CHANGES", "hash-b", {"registry": "frozen"}),
        ("ARTIFACT_STATE", "APPEARS", "PRESENT", {"artifact": "terminal-receipt"}),
        ("BLOCKER_STATE", "CLEARS", "CLEARED", {"blocker": "selector"}),
        ("GENERIC_STATE", "READY", "READY", {"resource": "provider"}),
    ],
)
def test_supported_event_classes_can_wake(kind, trigger, value, selector):
    packet = _packet(f"stream-{kind.lower()}")
    state = new_state("owner/repo")
    kwargs = {}
    if trigger == "CHANGES":
        kwargs["baseline_value"] = "hash-a"
    watch = build_watch_from_packet(
        packet,
        event_kind=kind,
        selector=selector,
        trigger=trigger,
        next_legal_action="CONTINUE",
        **kwargs,
    )
    saved = register_watch(
        state, watch,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    event = build_event(
        event_kind=kind,
        selector=selector,
        value=value,
        source_id=f"source-{kind.lower()}",
    )
    fired = ingest_event(
        saved["state"], event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=saved["state"]["revision"],
        expected_state_hash=saved["state"]["state_hash"],
    )
    assert fired["result"]["decision"] == "EVENT_MATERIAL_RESUME_READY"


def test_irrelevant_event_does_not_wake_or_advance_state():
    packet, state, _ = _registered()
    event = build_event(
        event_kind="PR_STATE",
        selector={"pr": "1"},
        value="MERGED",
        source_id="github-pr-1",
    )
    result = ingest_event(
        state, event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    assert result["result"]["decision"] == "EVENT_NOT_MATERIAL"
    assert result["state"]["state_hash"] == state["state_hash"]


def test_stale_cas_and_tampering_fail_closed():
    state = new_state("owner/repo")
    watch = build_watch(
        workstream_id="stream-x",
        continuation_packet_hash="4" * 64,
        event_kind="LEASE_STATE",
        selector={"lease": "x"},
        trigger="FREE",
        next_legal_action="CLAIM_SCOPE",
    )
    stale = register_watch(
        state, watch,
        expected_revision=99,
        expected_state_hash="5" * 64,
    )
    assert stale["result"]["decision"] == "EVENT_RESUME_STALE_CAS"

    damaged = deepcopy(state)
    damaged["generation"] += 1
    with pytest.raises(EventDrivenResumeFailure, match="hash mismatch"):
        validate_state(damaged)


def test_contract_self_test_green_and_side_effect_free():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["repository_backed_event_state"] is True
    assert result["continuation_packet_bound"] is True
    assert result["material_event_wakes_once"] is True
    assert result["duplicate_event_blocked"] is True
    assert result["resume_without_polling"] is True
    assert result["continuation_drift_fails_closed"] is True
    assert result["ready_receipt_one_shot"] is True
    assert result["stale_cas_blocked"] is True
    assert result["trigger_matrix_complete"] is True
    assert result["tamper_evident_state"] is True
    assert result["step_2a_still_required"] is True
    assert result["scope_lease_still_required"] is True
    assert result["event_never_grants_mutation"] is True
    assert result["polling_required"] is False
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "event_driven_resume_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V5_EVENT_DRIVEN_RESUME_GREEN" in completed.stdout
