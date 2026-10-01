from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.detached_execution_continuation_v1 import (
    DetachedContinuationFailure,
    build_packet,
    contract_self_test,
    handoff_worker,
    new_state,
    persist_packet,
    resume_decision,
    validate_packet,
)


HEAD = "a" * 40
MAIN = "b" * 40
LEASE = {
    "owner_id": "chat:step2",
    "lease_id": "SCOPE-LEASE-ABC",
    "generation": 1,
    "revision": 1,
    "state_hash": "1" * 64,
}
REGISTRY = {"revision": 8, "state_hash": "2" * 64, "checkpoint_count": 22}


def _packet(**overrides):
    values = dict(
        workstream_id="monster-v5-step2",
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        current_step=2,
        total_steps=5,
        step_title="Detached Execution / Background Continuation",
        execution_state="READY",
        branch="feature",
        head_sha=HEAD,
        main_sha=MAIN,
        pr_number=1279,
        authoritative_run_id=99,
        authoritative_job_id=None,
        async_state="SUCCESS",
        scope_lease=LEASE,
        frozen_registry=REGISTRY,
        blocker=None,
        last_completed_action="proof succeeded",
        next_legal_action="MERGE_PR_1279",
        worker_id="worker-a",
        previous_packet=None,
    )
    values.update(overrides)
    return build_packet(**values)


def test_packet_is_tamper_evident():
    packet = _packet()
    damaged = deepcopy(packet)
    damaged["execution"]["next_legal_action"] = "skip gates"
    with pytest.raises(DetachedContinuationFailure, match="hash mismatch"):
        validate_packet(damaged)


def test_live_async_packet_resumes_as_wait_not_duplicate():
    packet = _packet(
        execution_state="WAITING_ON_ASYNC",
        async_state="IN_PROGRESS",
        next_legal_action="WAIT_FOR_RUN_99_TERMINAL",
    )
    state = new_state("owner/repo")
    saved = persist_packet(
        state, packet,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    decision = resume_decision(
        saved["state"],
        workstream_id=packet["workstream_id"],
        current_branch="feature",
        current_head_sha=HEAD,
        current_main_sha=MAIN,
        current_scope_lease=LEASE,
        current_frozen_registry=REGISTRY,
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )
    assert decision["decision"] == "DETACHED_WAIT_AUTHORITATIVE_ASYNC"
    assert decision["may_mutate_now"] is False
    assert decision["authoritative_run_id"] == 99


def test_failed_async_requires_classification_before_patch():
    packet = _packet(
        execution_state="ACTIVE",
        async_state="FAILURE",
        next_legal_action="CLASSIFY_RUN_99",
    )
    state = new_state("owner/repo")
    saved = persist_packet(
        state, packet,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    decision = resume_decision(
        saved["state"],
        workstream_id=packet["workstream_id"],
        current_branch="feature",
        current_head_sha=HEAD,
        current_main_sha=MAIN,
        current_scope_lease=LEASE,
        current_frozen_registry=REGISTRY,
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )
    assert decision["decision"] == "DETACHED_CLASSIFY_ASYNC_TERMINAL"
    assert decision["may_mutate_now"] is False


def test_worker_handoff_is_cas_bound_and_does_not_authorize_mutation():
    packet = _packet()
    state = new_state("owner/repo")
    saved = persist_packet(
        state, packet,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    handed = handoff_worker(
        saved["state"],
        workstream_id=packet["workstream_id"],
        new_worker_id="worker-b",
        expected_packet_hash=packet["packet_hash"],
        expected_revision=saved["state"]["revision"],
        expected_state_hash=saved["state"]["state_hash"],
    )
    assert handed["result"]["allowed"] is True
    assert handed["result"]["worker_id"] == "worker-b"
    assert handed["result"]["mutation_authority_granted"] is False

    stale = handoff_worker(
        saved["state"],
        workstream_id=packet["workstream_id"],
        new_worker_id="worker-c",
        expected_packet_hash=packet["packet_hash"],
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    assert stale["result"]["decision"] == "DETACHED_CONTINUATION_STALE_CAS"


def test_unrelated_main_movement_is_advisory_when_scoped_identity_is_stable():
    packet = _packet()
    state = new_state("owner/repo")
    saved = persist_packet(
        state, packet,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    decision = resume_decision(
        saved["state"],
        workstream_id=packet["workstream_id"],
        current_branch="feature",
        current_head_sha=HEAD,
        current_main_sha="c" * 40,
        current_scope_lease={**LEASE, "revision": 2, "state_hash": "3" * 64},
        current_frozen_registry={**REGISTRY, "revision": 9, "state_hash": "4" * 64},
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )
    assert decision["decision"] == "DETACHED_READY_TO_RESUME"
    assert decision["main_advanced_advisory"] is True
    assert decision["registry_changed_advisory"] is True


def test_scope_or_frozen_scope_drift_fail_closed():
    packet = _packet()
    state = new_state("owner/repo")
    saved = persist_packet(
        state, packet,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    common = dict(
        state=saved["state"],
        workstream_id=packet["workstream_id"],
        current_branch="feature",
        current_head_sha=HEAD,
        current_main_sha=MAIN,
        current_scope_lease=LEASE,
        current_frozen_registry=REGISTRY,
    )
    assert resume_decision(
        **common, scope_identity_stable=False, frozen_scope_stable=True
    )["decision"] == "DETACHED_REVALIDATE_SCOPE_LEASE"
    assert resume_decision(
        **common, scope_identity_stable=True, frozen_scope_stable=False
    )["decision"] == "DETACHED_REVALIDATE_FROZEN_SCOPE"


def test_head_or_branch_drift_fails_closed():
    packet = _packet()
    state = new_state("owner/repo")
    saved = persist_packet(
        state, packet,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    decision = resume_decision(
        saved["state"],
        workstream_id=packet["workstream_id"],
        current_branch="different",
        current_head_sha=HEAD,
        current_main_sha=MAIN,
        current_scope_lease=LEASE,
        current_frozen_registry=REGISTRY,
        scope_identity_stable=True,
        frozen_scope_stable=True,
    )
    assert decision["decision"] == "DETACHED_REVALIDATE_REPOSITORY_IDENTITY"


def test_contract_self_test_green_and_runtime_safe():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["repository_backed_state_contract"] is True
    assert result["tamper_evident_packet"] is True
    assert result["cas_persistence"] is True
    assert result["live_async_waits_without_duplicate"] is True
    assert result["worker_handoff_is_cas_bound"] is True
    assert result["handoff_does_not_grant_mutation"] is True
    assert result["resume_without_chat_history"] is True
    assert result["unrelated_main_movement_tolerated"] is True
    assert result["scope_drift_fails_closed"] is True
    assert result["frozen_scope_drift_fails_closed"] is True
    assert result["failed_async_forces_classification"] is True
    assert result["multiple_workstreams_supported"] is True
    assert result["step_2a_still_required"] is True
    assert result["scope_lease_still_required"] is True
    assert result["packet_never_grants_mutation"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "detached_execution_continuation_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_GREEN" in completed.stdout
