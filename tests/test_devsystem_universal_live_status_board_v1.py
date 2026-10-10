import math

import pytest

from devsystem.universal_live_status_board_v1 import (
    StatusBoardValidationFailure,
    render_status_board,
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
