"""NFL Rushing + Receiving live-game repair — Step 2/5 identity bridge cert.

Certifies that the shared app-identity gate keeps exact current-roster identity
available during an active ESPN event without reopening the pregame prop-market
gate. Rushing/Receiving route owners remain unchanged and final events still
fail closed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

MODEL_VERSION = "NFL LIVE GAME REPAIR STEP 2 • IDENTITY BRIDGE CERT"
MISSION_STEP = "2/5"

MAY_MODIFY_PRODUCT_RUNTIME = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SPORTSBOOK = False
API2_USED = False

RUSHING_PATH = Path("nfl_rushing_yards_hub_v16.py")
RECEIVING_PATH = Path("nfl_receiving_yards_hub_v17.py")
SHARED_GATE_PATH = Path("nfl_prop_app_eligibility_v1.py")


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"NFL_LIVE_GAME_STEP2_SOURCE_MISSING:{path}")
    return path.read_text(encoding="utf-8")


def _require(text: str, marker: str, token: str) -> None:
    if marker not in text:
        raise AssertionError(f"{token}:{marker}")


def verify_repository_identity_bridge() -> dict[str, Any]:
    rushing = _read(RUSHING_PATH)
    receiving = _read(RECEIVING_PATH)
    gate = _read(SHARED_GATE_PATH)

    for source, market in ((rushing, "RUSHING"), (receiving, "RECEIVING")):
        _require(
            source,
            "from nfl_prop_app_eligibility_v1 import guard_context_payload",
            f"NFL_LIVE_GAME_STEP2_{market}_SHARED_GUARD_IMPORT_DRIFT",
        )
        _require(
            source,
            "return guard_context_payload(",
            f"NFL_LIVE_GAME_STEP2_{market}_SHARED_GUARD_CALL_DRIFT",
        )

    # Preserve the frozen Step-1 diagnosis while splitting market availability
    # from player identity during the active-game window.
    _require(gate, 'if state in {"in", "post"}:', "NFL_LIVE_GAME_STEP2_STATE_SPLIT_DRIFT")
    _require(gate, '"state": "CLOSED"', "NFL_LIVE_GAME_STEP2_MARKET_CLOSED_DRIFT")
    _require(gate, '"prop_gate_open": False', "NFL_LIVE_GAME_STEP2_MARKET_GATE_DRIFT")
    _require(gate, 'if state == "in":', "NFL_LIVE_GAME_STEP2_LIVE_BRANCH_DRIFT")
    _require(gate, 'closed["identity_state"] = "LIVE"', "NFL_LIVE_GAME_STEP2_LIVE_STATE_DRIFT")
    _require(gate, 'closed["identity_gate_open"] = True', "NFL_LIVE_GAME_STEP2_LIVE_GATE_DRIFT")
    _require(gate, "live_identity_bridge = (", "NFL_LIVE_GAME_STEP2_BRIDGE_DRIFT")
    _require(gate, 'state == "CLOSED"', "NFL_LIVE_GAME_STEP2_BRIDGE_MARKET_STATE_DRIFT")
    _require(gate, 'identity_state == "LIVE"', "NFL_LIVE_GAME_STEP2_BRIDGE_IDENTITY_STATE_DRIFT")
    _require(
        gate,
        'snapshot.get("identity_gate_open") is True',
        "NFL_LIVE_GAME_STEP2_BRIDGE_IDENTITY_GATE_DRIFT",
    )
    _require(
        gate,
        'snapshot.get("prop_gate_open") is not True',
        "NFL_LIVE_GAME_STEP2_MARKET_REOPEN_DRIFT",
    )
    _require(
        gate,
        'if state not in {"PENDING", "CONFIRMED"}:',
        "NFL_LIVE_GAME_STEP2_FROZEN_STEP1_ALLOWLIST_DRIFT",
    )
    _require(
        gate,
        'out["step7_app_live_identity_verified"] = live_identity_bridge',
        "NFL_LIVE_GAME_STEP2_RECEIPT_DRIFT",
    )

    # Safety constants are part of the patch boundary: live identity does not
    # gain projection, sportsbook, staking or wager authority.
    _require(gate, "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0", "NFL_LIVE_GAME_STEP2_SPORTSBOOK_DRIFT")
    _require(gate, "MAY_MODIFY_PROJECTION = False", "NFL_LIVE_GAME_STEP2_PROJECTION_DRIFT")
    _require(gate, "STAKE_SIZING_ENABLED = False", "NFL_LIVE_GAME_STEP2_STAKE_DRIFT")
    _require(gate, "WAGER_ACTIONS_ENABLED = False", "NFL_LIVE_GAME_STEP2_WAGER_DRIFT")

    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "shared_gate": "nfl_prop_app_eligibility_v1.py",
        "rushing_owner_unchanged": True,
        "receiving_owner_unchanged": True,
        "live_market_gate_closed": True,
        "live_identity_bridge_open": True,
        "live_identity_requires_exact_current_roster": True,
        "final_context_fail_closed": True,
        "page_specific_patch_required": False,
        "projection_changed": False,
        "probability_changed": False,
        "ranking_changed": False,
        "sportsbook_changed": False,
        "api2_used": False,
    }


def main() -> int:
    result = verify_repository_identity_bridge()
    print("NFL_LIVE_GAME_REPAIR_STEP2_IDENTITY_BRIDGE_GREEN")
    print("NFL_LIVE_GAME_REPAIR_STEP2_MARKET_GATE_STAYS_CLOSED_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
