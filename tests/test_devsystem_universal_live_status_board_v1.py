import math

import pytest

from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, new_state
from devsystem.universal_live_status_board_v1 import (
    OwnershipResolutionFailure,
    StatusBoardValidationFailure,
    bind_status_packet_to_authoritative_ownership,
    render_status_board,
    resolve_authoritative_chat_ownership,
    validate_status_packet,
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


def test_valid_yellow_active_packet_passes():
    out = validate_status_packet(VALID_ACTIVE)
    assert out["completion_percent"] == 87.0
    assert out["status"] == "YELLOW"
    assert out["live_active_chat"] == "API_2"


def test_valid_red_requires_blocker():
    packet = {**VALID_ACTIVE, "status": "RED", "current_blocker": "blocked"}
    assert validate_status_packet(packet)["status"] == "RED"


def test_red_without_real_blocker_fails():
    packet = {**VALID_ACTIVE, "status": "RED", "current_blocker": "   "}
    with pytest.raises(StatusBoardValidationFailure):
        validate_status_packet(packet)


def test_valid_terminal_packet_passes():
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
        "current_blocker": None,
        "next_legal_action": None,
    }
    assert validate_status_packet(packet)["frozen"] is True


@pytest.mark.parametrize(
    "packet",
    [
        {**VALID_ACTIVE, "completion_percent": 100, "status": "YELLOW"},
        {**VALID_ACTIVE, "completion_percent": 99, "status": "GREEN", "frozen": True},
        {**VALID_ACTIVE, "completion_percent": 100, "status": "RED", "frozen": True, "current_blocker": "x"},
        {**VALID_ACTIVE, "completion_percent": 100, "status": "YELLOW", "frozen": True},
        {**VALID_ACTIVE, "live_active_chat": "NONE_TERMINAL"},
        {**VALID_ACTIVE, "status": "PURPLE"},
        {**VALID_ACTIVE, "live_active_chat": "OTHER"},
        {**VALID_ACTIVE, "completion_percent": -1},
        {**VALID_ACTIVE, "completion_percent": 101},
        {**VALID_ACTIVE, "completion_percent": True},
        {**VALID_ACTIVE, "completion_percent": math.nan},
        {**VALID_ACTIVE, "completion_percent": math.inf},
        {**VALID_ACTIVE, "completion_percent": -math.inf},
    ],
)
def test_invalid_packets_fail(packet):
    with pytest.raises(StatusBoardValidationFailure):
        validate_status_packet(packet)


@pytest.mark.parametrize("field", ["completion_percent", "status", "live_active_chat"])
def test_missing_mandatory_field_fails(field):
    packet = dict(VALID_ACTIVE)
    packet.pop(field)
    with pytest.raises(StatusBoardValidationFailure):
        validate_status_packet(packet)


@pytest.mark.parametrize("chat", ["THIS_CHAT", "MONSTER", "API_2"])
def test_terminal_packet_requires_none_terminal_chat(chat):
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": chat,
        "frozen": True,
    }
    with pytest.raises(StatusBoardValidationFailure):
        validate_status_packet(packet)


def test_renderer_displays_all_three_mandatory_fields():
    text = render_status_board(VALID_ACTIVE)
    assert "Completion: 87%" in text
    assert "Status: YELLOW" in text
    assert "Live Active Chat: API_2" in text


def test_renderer_is_deterministic_across_input_order():
    a = render_status_board(VALID_ACTIVE)
    b = render_status_board(dict(reversed(list(VALID_ACTIVE.items()))))
    assert a == b


def test_terminal_renderer_shows_green_frozen():
    text = render_status_board({
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
    })
    assert "Status: GREEN + FROZEN" in text


@pytest.mark.parametrize(
    ("owner_id", "expected_chat"),
    [
        ("chatgpt:monster-v2:monster-v9-step1", "MONSTER"),
        ("chatgpt:api2:wnba-step1", "API_2"),
        ("universal-live-status-board-v1-step2", "THIS_CHAT"),
    ],
)
def test_step2_maps_single_live_authoritative_owner(owner_id, expected_chat):
    state = _lease_state(owner_id)
    resolution = resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")
    assert resolution["live_active_chat"] == expected_chat
    assert resolution["authoritative_owner"] == owner_id
    assert resolution["scope_lease_id"].startswith("SCOPE-LEASE-")
    assert resolution["lease_revision"] == state["revision"]
    assert resolution["lease_state_hash"] == state["state_hash"]


def test_step2_fails_closed_when_no_live_owner_exists():
    state = _lease_state()
    with pytest.raises(OwnershipResolutionFailure, match="no live authoritative owner"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")


def test_step2_fails_closed_when_multiple_live_owners_exist():
    state = _lease_state(
        "chatgpt:monster-v2:monster-v9-step1",
        "chatgpt:api2:wnba-step1",
    )
    with pytest.raises(OwnershipResolutionFailure, match="ambiguous live authoritative ownership"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")


def test_step2_ignores_expired_owner_then_fails_closed():
    state = _lease_state("chatgpt:api2:wnba-step1", now_utc="2026-10-10T03:00:00Z")
    with pytest.raises(OwnershipResolutionFailure, match="no live authoritative owner"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:01Z")


def test_step2_rejects_invalid_authoritative_lease_state():
    state = _lease_state("chatgpt:api2:wnba-step1")
    state["state_hash"] = "0" * 64
    with pytest.raises(OwnershipResolutionFailure, match="invalid authoritative lease state"):
        resolve_authoritative_chat_ownership(state, now_utc="2026-10-10T04:05:00Z")


def test_step2_binding_overrides_manual_chat_label_with_lease_truth():
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


def test_step2_terminal_binding_requires_no_live_owner_and_emits_none_terminal():
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


def test_step2_terminal_binding_fails_when_live_owner_still_exists():
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
