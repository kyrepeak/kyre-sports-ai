from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.distributed_execution_lease_v1 import (
    LEASE_REF,
    PERSISTENCE_SURFACE,
    authorize_lease,
    claim_lease,
    contract_self_test,
    new_lease_state,
    release_lease,
    validate_lease_state,
)


def test_initial_lease_state_is_free_and_hash_valid():
    state = new_lease_state("owner/repo")
    assert validate_lease_state(state)["holder"] is None
    assert state["revision"] == 0
    assert state["generation"] == 0
    assert state["persistence_surface"] == "git_ref_fast_forward_cas"
    assert state["lease_ref"] == LEASE_REF


def test_exactly_one_live_owner_wins():
    state = new_lease_state("owner/repo")
    first = claim_lease(
        state,
        owner_id="chat:A-123",
        now_utc="2026-09-30T04:50:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    second = claim_lease(
        first["state"],
        owner_id="chat:B-456",
        now_utc="2026-09-30T04:51:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    assert first["result"]["decision"] == "LEASE_CLAIMED"
    assert second["result"]["decision"] == "LEASE_HELD_CONTINUE"
    assert second["result"]["allowed"] is False
    assert second["result"]["requires_user_intervention"] is False


def test_stale_cas_observation_cannot_write():
    state = new_lease_state("owner/repo")
    first = claim_lease(
        state,
        owner_id="chat:A-123",
        now_utc="2026-09-30T04:50:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    stale = claim_lease(
        first["state"],
        owner_id="chat:B-456",
        now_utc="2026-09-30T04:51:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    assert stale["result"]["decision"] == "LEASE_CAS_CONFLICT_CONTINUE"
    assert stale["result"]["allowed"] is False


def test_expired_lease_can_be_taken_over_with_new_generation():
    state = new_lease_state("owner/repo")
    first = claim_lease(
        state,
        owner_id="chat:A-123",
        now_utc="2026-09-30T04:50:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
        ttl_seconds=60,
    )
    takeover = claim_lease(
        first["state"],
        owner_id="chat:B-456",
        now_utc="2026-09-30T04:52:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    assert takeover["result"]["decision"] == "LEASE_CLAIMED"
    assert takeover["state"]["holder"]["owner_id"] == "chat:B-456"
    assert takeover["state"]["generation"] == first["state"]["generation"] + 1


def test_repository_drift_invalidates_execution_authority():
    state = new_lease_state("owner/repo")
    first = claim_lease(
        state,
        owner_id="chat:A-123",
        now_utc="2026-09-30T04:50:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    action = {
        "task_id": "t",
        "checkpoint_id": "1",
        "action_type": "merge",
        "target": "github:pr/1",
    }
    result = authorize_lease(
        first["state"],
        owner_id="chat:A-123",
        lease_id=first["result"]["lease_id"],
        now_utc="2026-09-30T04:51:00Z",
        current_main_sha="1" * 40,
        current_head_sha="3" * 40,
        action=action,
    )
    assert result["decision"] == "LEASE_REPOSITORY_DRIFT_CONTINUE"
    assert result["allowed"] is False


def test_non_mutating_observation_does_not_require_lease():
    state = new_lease_state("owner/repo")
    result = authorize_lease(
        state,
        owner_id="chat:A-123",
        lease_id=None,
        now_utc="2026-09-30T04:50:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        action={
            "task_id": "t",
            "checkpoint_id": "1",
            "action_type": "observe_async",
            "target": "github:run/1",
        },
    )
    assert result["decision"] == "LEASE_NOT_REQUIRED"
    assert result["allowed"] is True


def test_only_holder_can_release_lease():
    state = new_lease_state("owner/repo")
    first = claim_lease(
        state,
        owner_id="chat:A-123",
        now_utc="2026-09-30T04:50:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    denied = release_lease(
        first["state"],
        owner_id="chat:B-456",
        lease_id=first["result"]["lease_id"],
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    assert denied["result"]["decision"] == "LEASE_OWNER_MISMATCH_CONTINUE"
    assert denied["state"]["holder"] is not None


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["persistence_surface"] == PERSISTENCE_SURFACE
    assert result["single_live_owner"] is True
    assert result["stale_revision_blocked"] is True
    assert result["expired_lease_takeover"] is True
    assert result["owner_a_executes"] is True
    assert result["owner_b_cannot_execute"] is True
    assert result["repository_drift_blocked"] is True
    assert result["two_a_chain_preserved"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "distributed_execution_lease_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V4_DISTRIBUTED_EXECUTION_LEASE_V1_GREEN" in completed.stdout
