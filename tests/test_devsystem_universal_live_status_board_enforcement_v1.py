import pytest

from devsystem.execution_heartbeat_deadman_recovery_v1 import new_state as new_heartbeat_state, register_worker
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, new_state as new_lease_state
from devsystem.universal_live_status_board_enforcement_v1 import (
    EnforcementGateFailure,
    enforce_execution_update,
)
from devsystem.universal_live_status_board_v1 import render_status_board

WORKSTREAM = "universal-live-status-board-v1"
PACKET_HASH = "a" * 64
WRITE_PATH = "devsystem/universal_live_status_board_enforcement_v1.py"


def _lease(owner="chatgpt:api2:ulsb-step4", *, now="2026-10-10T04:00:00Z", ttl=900):
    state = new_lease_state("kyrepeak/kyre-sports-ai")
    claimed = claim_scope(
        state,
        owner_id=owner,
        now_utc=now,
        scope=build_scope(write_paths=[WRITE_PATH]),
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=ttl,
    )
    assert claimed["result"]["allowed"] is True
    return claimed["state"]


def _heartbeat(lease, owner="chatgpt:api2:ulsb-step4", *, now="2026-10-10T04:00:00Z", ttl=900):
    state = new_heartbeat_state("kyrepeak/kyre-sports-ai")
    scope_lease_id = lease["holders"][0]["lease_id"]
    registered = register_worker(
        state,
        workstream_id=WORKSTREAM,
        owner_id=owner,
        scope_lease_id=scope_lease_id,
        continuation_packet_hash=PACKET_HASH,
        authoritative_run_id=404,
        now_utc=now,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        heartbeat_ttl_seconds=ttl,
    )
    assert registered["result"]["allowed"] is True
    return registered["state"]


def _active_packet(chat="API_2"):
    return {
        "completion_percent": 88,
        "status": "YELLOW",
        "live_active_chat": chat,
        "frozen": False,
        "current_blocker": None,
        "next_legal_action": "continue authoritative execution",
    }


def _update(packet):
    return {"status_board": packet, "visible_board": render_status_board(packet), "message": "execution update"}


def test_missing_status_board_fails_closed():
    lease = _lease()
    heartbeat = _heartbeat(lease)
    with pytest.raises(EnforcementGateFailure, match="status board required"):
        enforce_execution_update(
            {"visible_board": "anything"}, lease, heartbeat,
            workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
            now_utc="2026-10-10T04:05:00Z", observed_run_state="in_progress",
        )


def test_missing_visible_board_fails_closed():
    lease = _lease()
    heartbeat = _heartbeat(lease)
    with pytest.raises(EnforcementGateFailure, match="visible board required"):
        enforce_execution_update(
            {"status_board": _active_packet()}, lease, heartbeat,
            workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
            now_utc="2026-10-10T04:05:00Z", observed_run_state="in_progress",
        )


def test_valid_live_owner_update_is_authoritative_only_with_canonical_visible_board():
    lease = _lease()
    heartbeat = _heartbeat(lease)
    result = enforce_execution_update(
        _update(_active_packet()), lease, heartbeat,
        workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
        now_utc="2026-10-10T04:05:00Z", observed_run_state="in_progress",
    )
    assert result["allowed"] is True
    assert result["decision"] == "AUTHORITATIVE_CONTROL_ROOM_UPDATE"
    assert result["status_board"]["live_active_chat"] == "API_2"
    assert result["requires_step_2a"] is True
    assert result["grants_mutation_authority"] is False


def test_wrong_chat_label_fails_instead_of_becoming_authoritative():
    lease = _lease()
    heartbeat = _heartbeat(lease)
    with pytest.raises(EnforcementGateFailure, match="visible board does not match authoritative board"):
        enforce_execution_update(
            _update(_active_packet(chat="MONSTER")), lease, heartbeat,
            workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
            now_utc="2026-10-10T04:05:00Z", observed_run_state="in_progress",
        )


def test_stale_heartbeat_blocks_execution_update_even_when_run_is_active():
    lease = _lease(ttl=900)
    heartbeat = _heartbeat(lease, ttl=60)
    with pytest.raises(EnforcementGateFailure, match="OWNER_RUN_ACTIVE_HEARTBEAT_STALE"):
        enforce_execution_update(
            _update(_active_packet()), lease, heartbeat,
            workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
            now_utc="2026-10-10T04:01:01Z", observed_run_state="in_progress",
        )


def test_tampered_visible_board_fails_closed():
    lease = _lease()
    heartbeat = _heartbeat(lease)
    update = _update(_active_packet())
    update["visible_board"] += "\nCompletion: 99%"
    with pytest.raises(EnforcementGateFailure, match="visible board does not match authoritative board"):
        enforce_execution_update(
            update, lease, heartbeat,
            workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
            now_utc="2026-10-10T04:05:00Z", observed_run_state="in_progress",
        )


def test_terminal_green_frozen_update_is_allowed_only_with_zero_live_owners():
    empty_lease = new_lease_state("kyrepeak/kyre-sports-ai")
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
        "current_blocker": None,
        "next_legal_action": None,
    }
    result = enforce_execution_update(
        _update(packet), empty_lease, None,
        workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
        now_utc="2026-10-10T04:05:00Z", observed_run_state="success",
    )
    assert result["allowed"] is True
    assert result["status_board"]["live_active_chat"] == "NONE_TERMINAL"


def test_terminal_update_with_live_owner_fails_closed():
    lease = _lease()
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
    }
    with pytest.raises(EnforcementGateFailure, match="terminal packet cannot retain a live owner"):
        enforce_execution_update(
            _update(packet), lease, None,
            workstream_id=WORKSTREAM, continuation_packet_hash=PACKET_HASH,
            now_utc="2026-10-10T04:05:00Z", observed_run_state="success",
        )


def test_step4_gate_is_pure_control_plane_and_never_grants_mutation_authority():
    import devsystem.universal_live_status_board_enforcement_v1 as module
    assert module.NETWORK_CALLS is False
    assert module.AUTO_MUTATE is False
    assert module.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert module.MUTATION_AUTHORITY_GRANTED is False
    assert module.GITHUB_ACTIONS_FALLBACK == 0
    assert module.CREATES_PARALLEL_OWNERSHIP_REGISTRY is False
