from __future__ import annotations

import importlib

import pytest

from devsystem.detached_execution_continuation_v1 import build_packet
from devsystem.event_driven_resume_v1 import build_event, new_state


LEASE = {
    "owner_id": "monster-v2-runless-task17-step4",
    "lease_id": "SCOPE-LEASE-C20C0E7167152850461F299C",
    "generation": 137,
    "revision": 226,
    "state_hash": "8" * 64,
}
REGISTRY = {
    "revision": 173,
    "state_hash": "a" * 64,
    "checkpoint_count": 1,
}


def _bridge():
    try:
        return importlib.import_module("runless_proof_plane.event_resume")
    except ModuleNotFoundError:
        pytest.fail("Runless Task 17 Step 4 event-resume bridge is missing")


def _packet(workstream: str = "runless-task17-step4"):
    return build_packet(
        workstream_id=workstream,
        program_id="RUNLESS_TASK17",
        program_title="Runless Final-Mile Convergence Accelerator V1",
        current_step=4,
        total_steps=6,
        step_title="Event-Driven Resume",
        execution_state="WAITING",
        branch="runless-task17-step4-event-driven-resume-r1",
        head_sha="b" * 40,
        main_sha="7" * 40,
        pr_number=None,
        authoritative_run_id=None,
        authoritative_job_id=None,
        async_state="WAITING",
        scope_lease=LEASE,
        frozen_registry=REGISTRY,
        blocker="deployment pending",
        last_completed_action="registered event watch",
        next_legal_action="VERIFY_DEPLOYMENT_TERMINAL",
        worker_id="runless-step4",
    )


def _registered():
    bridge = _bridge()
    packet = _packet()
    state = new_state("kyrepeak/kyre-sports-ai")
    registered = bridge.register_runless_wait(
        state,
        packet=packet,
        event_kind="DEPLOYMENT_STATE",
        selector={"deployment_id": "dep-123"},
        trigger="TERMINAL",
        next_legal_action="VERIFY_DEPLOYMENT_TERMINAL",
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    return bridge, packet, registered["state"]


def test_register_wait_is_event_driven_and_side_effect_free():
    bridge, _, state = _registered()
    assert state["revision"] == 1
    assert bridge.POLLING_REQUIRED is False
    assert bridge.NETWORK_CALLS is False
    assert bridge.AUTO_MUTATE is False
    assert bridge.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert bridge.MUTATION_AUTHORITY_GRANTED is False


def test_material_event_wakes_exact_runless_workstream_once():
    bridge, packet, state = _registered()
    event = build_event(
        event_kind="DEPLOYMENT_STATE",
        selector={"deployment_id": "dep-123"},
        value="SUCCESS",
        source_id="render-dep-123",
    )
    fired = bridge.ingest_runless_event(
        state,
        event=event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    assert fired["result"]["decision"] == "RUNLESS_EVENT_RESUME_READY"
    assert fired["result"]["ready_workstreams"] == [packet["workstream_id"]]
    assert fired["result"]["polling_required"] is False
    assert fired["result"]["mutation_authority_granted"] is False

    duplicate = bridge.ingest_runless_event(
        fired["state"],
        event=event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=fired["state"]["revision"],
        expected_state_hash=fired["state"]["state_hash"],
    )
    assert duplicate["result"]["decision"] == "RUNLESS_EVENT_DUPLICATE_BLOCKED"
    assert duplicate["result"]["duplicate_wake_blocked"] is True


def test_step2a_is_required_before_ready_receipt_is_consumed():
    bridge, packet, state = _registered()
    event = build_event(
        event_kind="DEPLOYMENT_STATE",
        selector={"deployment_id": "dep-123"},
        value="SUCCESS",
        source_id="render-dep-123",
    )
    fired = bridge.ingest_runless_event(
        state,
        event=event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    ready_state = fired["state"]

    blocked = bridge.claim_runless_resume(
        ready_state,
        workstream_id=packet["workstream_id"],
        current_continuation_packet_hash=packet["packet_hash"],
        step2a_authorized=False,
        expected_revision=ready_state["revision"],
        expected_state_hash=ready_state["state_hash"],
    )
    assert blocked["result"]["decision"] == "RUNLESS_RESUME_STEP2A_REQUIRED"
    assert blocked["state"]["state_hash"] == ready_state["state_hash"]

    consumed = bridge.claim_runless_resume(
        ready_state,
        workstream_id=packet["workstream_id"],
        current_continuation_packet_hash=packet["packet_hash"],
        step2a_authorized=True,
        expected_revision=ready_state["revision"],
        expected_state_hash=ready_state["state_hash"],
    )
    assert consumed["result"]["decision"] == "RUNLESS_RESUME_CONSUMED"
    assert consumed["result"]["next_legal_action"] == "VERIFY_DEPLOYMENT_TERMINAL"
    assert consumed["result"]["mutation_authority_granted"] is False
    assert consumed["state"]["state_hash"] != ready_state["state_hash"]

    second = bridge.claim_runless_resume(
        consumed["state"],
        workstream_id=packet["workstream_id"],
        current_continuation_packet_hash=packet["packet_hash"],
        step2a_authorized=True,
        expected_revision=consumed["state"]["revision"],
        expected_state_hash=consumed["state"]["state_hash"],
    )
    assert second["result"]["decision"] == "RUNLESS_RESUME_NOT_READY"


def test_continuation_drift_fails_closed_without_consuming_ready_receipt():
    bridge, packet, state = _registered()
    event = build_event(
        event_kind="DEPLOYMENT_STATE",
        selector={"deployment_id": "dep-123"},
        value="SUCCESS",
        source_id="render-dep-123",
    )
    fired = bridge.ingest_runless_event(
        state,
        event=event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    ready_state = fired["state"]
    drift = bridge.claim_runless_resume(
        ready_state,
        workstream_id=packet["workstream_id"],
        current_continuation_packet_hash="3" * 64,
        step2a_authorized=True,
        expected_revision=ready_state["revision"],
        expected_state_hash=ready_state["state_hash"],
    )
    assert drift["result"]["decision"] == "RUNLESS_RESUME_CONTINUATION_DRIFT"
    assert drift["state"]["state_hash"] == ready_state["state_hash"]


def test_irrelevant_event_stays_asleep_without_state_advance():
    bridge, packet, state = _registered()
    event = build_event(
        event_kind="PR_STATE",
        selector={"pr": "9999"},
        value="MERGED",
        source_id="github-pr-9999",
    )
    waiting = bridge.ingest_runless_event(
        state,
        event=event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    assert waiting["result"]["decision"] == "RUNLESS_EVENT_WAITING"
    assert waiting["result"]["polling_required"] is False
    assert waiting["state"]["state_hash"] == state["state_hash"]


def test_stale_cas_is_exposed_without_retry_loop():
    bridge, packet, state = _registered()
    event = build_event(
        event_kind="DEPLOYMENT_STATE",
        selector={"deployment_id": "dep-123"},
        value="SUCCESS",
        source_id="render-dep-123",
    )
    stale = bridge.ingest_runless_event(
        state,
        event=event,
        current_continuation_packet_hashes={packet["workstream_id"]: packet["packet_hash"]},
        expected_revision=999,
        expected_state_hash="9" * 64,
    )
    assert stale["result"]["decision"] == "RUNLESS_EVENT_STATE_STALE"
    assert stale["result"]["retry_allowed_now"] is False
