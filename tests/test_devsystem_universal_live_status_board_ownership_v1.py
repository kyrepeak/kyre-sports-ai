import pytest

from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, new_state
from devsystem.universal_live_status_board_ownership_v1 import (
    OwnershipResolutionFailure,
    bind_status_packet_to_authoritative_ownership,
    resolve_authoritative_chat_ownership,
)


VALID_ACTIVE = {
    "completion_percent": 87,
    "status": "YELLOW",
    "live_active_chat": "API_2",
    "frozen": False,
    "current_blocker": "production SHA convergence",
    "next_legal_action": "consume authoritative deployment result",
}


def _lease_state(*owners: str, now_utc: str = "2026-10-10T04:00:00Z"):
    state = new_state("kyrepeak/kyre-sports-ai")
    for index, owner in enumerate(owners):
        claimed = claim_scope(
            state,
            owner_id=owner,
            now_utc=now_utc,
            scope=build_scope(write_paths=[f"devsystem/status-board-step2-{index}.txt"]),
            expected_revision=state["revision"],
            expected_state_hash=state["state_hash"],
            ttl_seconds=900,
        )
        assert claimed["result"]["allowed"] is True
        state = claimed["state"]
    return state


@pytest.mark.parametrize(
    ("owner_id", "expected_chat"),
    [
        ("chatgpt:monster-v2:monster-v9-step1", "MONSTER"),
        ("chatgpt:api2:wnba-step1", "API_2"),
        ("universal-live-status-board-v1-step2", "THIS_CHAT"),
    ],
)
def test_maps_single_live_authoritative_owner(owner_id, expected_chat):
    state = _lease_state(owner_id)
    resolution = resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")
    assert resolution["live_active_chat"] == expected_chat
    assert resolution["authoritative_owner"] == owner_id
    assert resolution["scope_lease_id"].startswith("SCOPE-LEASE-")
    assert resolution["lease_revision"] == state["revision"]
    assert resolution["lease_state_hash"] == state["state_hash"]


def test_fails_closed_when_no_live_owner_exists():
    state = _lease_state()
    with pytest.raises(OwnershipResolutionFailure, match="no live authoritative owner"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")


def test_fails_closed_when_multiple_live_owners_exist():
    state = _lease_state(
        "chatgpt:monster-v2:monster-v9-step1",
        "chatgpt:api2:wnba-step1",
    )
    with pytest.raises(OwnershipResolutionFailure, match="ambiguous live authoritative ownership"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")


def test_ignores_expired_owner_then_fails_closed():
    state = _lease_state("chatgpt:api2:wnba-step1", now_utc="2026-10-10T03:00:00Z")
    with pytest.raises(OwnershipResolutionFailure, match="no live authoritative owner"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:01Z")


def test_rejects_invalid_authoritative_lease_state():
    state = _lease_state("chatgpt:api2:wnba-step1")
    state["state_hash"] = "0" * 64
    with pytest.raises(OwnershipResolutionFailure, match="invalid authoritative lease state"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")


def test_binding_overrides_manual_chat_label_with_lease_truth():
    state = _lease_state("chatgpt:monster-v2:monster-v9-step1")
    packet = {
        **VALID_ACTIVE,
        "live_active_chat": "API_2",
        "authoritative_owner": "manual-owner",
        "scope_lease_id": "manual-lease",
    }
    bound = bind_status_packet_to_authoritative_ownership(
        packet,
        state,
        now_utc="2026-10-10T04:05:00Z",
    )
    assert bound["live_active_chat"] == "MONSTER"
    assert bound["authoritative_owner"] == "chatgpt:monster-v2:monster-v9-step1"
    assert bound["scope_lease_id"].startswith("SCOPE-LEASE-")


def test_terminal_binding_requires_no_live_owner_and_emits_none_terminal():
    state = _lease_state()
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "THIS_CHAT",
        "frozen": True,
    }
    bound = bind_status_packet_to_authoritative_ownership(
        packet,
        state,
        now_utc="2026-10-10T04:05:00Z",
    )
    assert bound["live_active_chat"] == "NONE_TERMINAL"
    assert bound["authoritative_owner"] is None
    assert bound["scope_lease_id"] is None


def test_terminal_binding_fails_when_live_owner_still_exists():
    state = _lease_state("chatgpt:api2:wnba-step1")
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
    }
    with pytest.raises(OwnershipResolutionFailure, match="terminal packet cannot retain a live owner"):
        bind_status_packet_to_authoritative_ownership(
            packet,
            state,
            now_utc="2026-10-10T04:05:00Z",
        )
