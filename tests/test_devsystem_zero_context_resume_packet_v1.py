from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.zero_context_resume_packet_v1 import (
    ZeroContextResumeFailure,
    bootstrap_view,
    build_packet,
    contract_self_test,
    validate_packet,
    verify_observed_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
MAIN = "1" * 40
REGISTRY = "2" * 64
SCOPE = "3" * 64
DETACHED = "4" * 64
EVENT = "5" * 64
HEARTBEAT = "6" * 64
RECEIPT = "7" * 64


def _packet(*, run_state: str = "SUCCESS", next_action: str = "MONSTER_V5_COMPLETE"):
    return build_packet(
        repository="kyrepeak/kyre-sports-ai",
        generation=1,
        program_id="MONSTER_V5",
        program_title="MONSTER V5",
        mission="A fresh worker resumes the exact mission from one repository object.",
        current_step=5,
        total_steps=5,
        step_title="Zero-Context Resume Packet",
        step_status="FROZEN",
        active_checkpoint="MONSTER_V5_STEP5",
        completed_steps=(1, 2, 3, 4, 5),
        frozen_steps=(1, 2, 3, 4, 5),
        remaining_steps=(),
        main_sha=MAIN,
        head_sha=MAIN,
        branch="main",
        pr_number=None,
        authoritative_run_id=5005,
        authoritative_run_state=run_state,
        last_completed_action="MONSTER_V5_STEP5_FROZEN",
        only_next_legal_action=next_action,
        blocker=None,
        frozen_registry={
            "revision": 14,
            "state_hash": REGISTRY,
            "checkpoint_count": 5,
            "active_thaws": 0,
        },
        frozen_checkpoints=(
            "MONSTER_V5_STEP1",
            "MONSTER_V5_STEP2",
            "MONSTER_V5_STEP3",
            "MONSTER_V5_STEP4",
            "MONSTER_V5_STEP5",
        ),
        scope_lease={
            "revision": 30,
            "generation": 10,
            "state_hash": SCOPE,
            "holder_count": 0,
            "current_owner_id": None,
            "current_lease_id": None,
        },
        detached_continuation={
            "version": "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_V1",
            "revision": 0,
            "generation": 0,
            "state_hash": DETACHED,
            "workstream_count": 0,
        },
        event_driven_resume={
            "version": "MONSTER_V5_EVENT_DRIVEN_RESUME_V1",
            "revision": 0,
            "generation": 0,
            "state_hash": EVENT,
            "active_watch_count": 0,
            "ready_count": 0,
        },
        execution_heartbeat_deadman={
            "version": "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_V1",
            "revision": 0,
            "generation": 0,
            "state_hash": HEARTBEAT,
            "worker_count": 0,
            "recovery_receipt_count": 0,
            "consumed_recovery_receipt_count": 0,
        },
        proof={
            "proof_run_id": 5005,
            "terminal_receipt_digest": "sha256:" + RECEIPT,
        },
    )


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["single_object_bootstrap"] is True
    assert result["mission_embedded"] is True
    assert result["progress_embedded"] is True
    assert result["frozen_items_embedded"] is True
    assert result["authoritative_run_embedded"] is True
    assert result["only_next_legal_action_embedded"] is True
    assert result["packet_tamper_blocked"] is True
    assert result["live_async_forces_wait"] is True
    assert result["packet_never_grants_mutation"] is True
    assert result["product_runtime_mutation"] is False


def test_one_object_contains_complete_resume_context():
    packet = _packet()
    view = bootstrap_view(packet)
    assert view["mission"]
    assert view["step"] == 5
    assert view["total_steps"] == 5
    assert view["completed_steps"] == [1, 2, 3, 4, 5]
    assert view["frozen_steps"] == [1, 2, 3, 4, 5]
    assert view["remaining_steps"] == []
    assert view["authoritative_run_id"] == 5005
    assert view["last_completed_action"] == "MONSTER_V5_STEP5_FROZEN"
    assert view["only_next_legal_action"] == "MONSTER_V5_COMPLETE"
    assert view["mutation_authority"] is False


def test_tampering_any_next_action_fails_hash_validation():
    packet = _packet()
    tampered = deepcopy(packet)
    tampered["execution"]["only_next_legal_action"] = "MERGE_UNPROVEN_HEAD"
    with pytest.raises(ZeroContextResumeFailure):
        validate_packet(tampered)


def test_stale_main_and_registry_fail_closed():
    packet = _packet()
    stale_main = verify_observed_snapshot(
        packet,
        observed_main_sha="8" * 40,
        observed_registry_state_hash=REGISTRY,
    )
    stale_registry = verify_observed_snapshot(
        packet,
        observed_main_sha=MAIN,
        observed_registry_state_hash="9" * 64,
    )
    assert stale_main["decision"] == "ZERO_CONTEXT_MAIN_STALE_CONTINUE"
    assert stale_registry["decision"] == "ZERO_CONTEXT_REGISTRY_STALE_CONTINUE"


def test_matching_snapshot_authorizes_context_but_never_mutation():
    packet = _packet()
    result = verify_observed_snapshot(
        packet,
        observed_main_sha=MAIN,
        observed_registry_state_hash=REGISTRY,
    )
    assert result["allowed"] is True
    assert result["context_authorized"] is True
    assert result["mutation_authority"] is False
    assert result["only_next_legal_action"] == "MONSTER_V5_COMPLETE"


def test_live_authoritative_run_forces_wait_and_duplicate_run_is_impossible():
    with pytest.raises(ZeroContextResumeFailure):
        _packet(run_state="IN_PROGRESS", next_action="START_ANOTHER_RUN")


def test_failed_authoritative_run_forces_classification():
    with pytest.raises(ZeroContextResumeFailure):
        _packet(run_state="FAILURE", next_action="PATCH_IMMEDIATELY")


def test_packet_round_trip_json_preserves_hash():
    packet = _packet()
    decoded = json.loads(json.dumps(packet))
    assert validate_packet(decoded)["packet_hash"] == packet["packet_hash"]


def test_permanent_gate_and_ci_enforce_zero_context_packet():
    permanent = (ROOT / "devsystem/permanent_gate_v1.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "devsystem/zero_context_resume_packet_v1.py" in permanent
    assert "tests/test_devsystem_zero_context_resume_packet_v1.py" in permanent
    assert "MONSTER_V5_ZERO_CONTEXT_RESUME_PACKET_GREEN" in permanent
    assert "python devsystem/zero_context_resume_packet_v1.py" in workflow
    assert "tests/test_devsystem_zero_context_resume_packet_v1.py" in workflow


def test_direct_script_execution_green():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "devsystem/zero_context_resume_packet_v1.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V5_ZERO_CONTEXT_RESUME_PACKET_GREEN" in completed.stdout
