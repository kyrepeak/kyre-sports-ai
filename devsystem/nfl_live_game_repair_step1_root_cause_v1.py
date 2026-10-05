"""NFL Rushing + Receiving live-game repair — Step 1/5 root-cause cert.

Proof-only. This module reads the current repository owners and fails closed if
routing or the shared app-identity gate no longer matches the diagnosed
kickoff-time failure. It does not mutate product/runtime behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

MODEL_VERSION = "NFL LIVE GAME REPAIR STEP 1 • ROOT CAUSE CERT"
MISSION_STEP = "1/5"

MAY_MODIFY_PRODUCT_RUNTIME = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SPORTSBOOK = False
API2_USED = False

ROUTER_PATH = Path("streamlit_memory_lazy_router_v187.py")
RUSHING_PATH = Path("nfl_rushing_yards_hub_v16.py")
RECEIVING_PATH = Path("nfl_receiving_yards_hub_v17.py")
SHARED_GATE_PATH = Path("nfl_prop_app_eligibility_v1.py")

RUSHING_OWNER = "nfl_rushing_yards_hub_v16"
RECEIVING_OWNER = "nfl_receiving_yards_hub_v17"
SHARED_GATE = "nfl_prop_app_eligibility_v1.py"
ROOT_CAUSE_CLASS = "PREGAME_ONLY_APP_IDENTITY_GATE"


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"NFL_LIVE_GAME_STEP1_SOURCE_MISSING:{path}")
    return path.read_text(encoding="utf-8")


def _require(text: str, marker: str, token: str) -> None:
    if marker not in text:
        raise AssertionError(f"{token}:{marker}")


def verify_repository_root_cause() -> dict[str, Any]:
    router = _read(ROUTER_PATH)
    rushing = _read(RUSHING_PATH)
    receiving = _read(RECEIVING_PATH)
    guard = _read(SHARED_GATE_PATH)

    _require(
        router,
        '"Rushing Yards": "nfl_rushing_yards_hub_v16"',
        "NFL_LIVE_GAME_STEP1_RUSHING_ROUTE_DRIFT",
    )
    _require(
        router,
        '"Receiving Yards": "nfl_receiving_yards_hub_v17"',
        "NFL_LIVE_GAME_STEP1_RECEIVING_ROUTE_DRIFT",
    )

    for source, market in ((rushing, "RUSHING"), (receiving, "RECEIVING")):
        _require(
            source,
            "from nfl_prop_app_eligibility_v1 import guard_context_payload",
            f"NFL_LIVE_GAME_STEP1_{market}_SHARED_GUARD_IMPORT_DRIFT",
        )
        _require(
            source,
            "return guard_context_payload(",
            f"NFL_LIVE_GAME_STEP1_{market}_SHARED_GUARD_CALL_DRIFT",
        )

    # Current shared gate explicitly converts live/final ESPN state into a
    # CLOSED pregame identity state before either market can render players.
    _require(
        guard,
        'if state in {"in", "post"}:',
        "NFL_LIVE_GAME_STEP1_LIVE_STATE_CLOSE_DRIFT",
    )
    _require(
        guard,
        '"state": "CLOSED"',
        "NFL_LIVE_GAME_STEP1_CLOSED_STATE_DRIFT",
    )
    _require(
        guard,
        '"pregame player-prop identity closed after kickoff"',
        "NFL_LIVE_GAME_STEP1_KICKOFF_REASON_DRIFT",
    )
    _require(
        guard,
        'state not in {"PENDING", "CONFIRMED"}',
        "NFL_LIVE_GAME_STEP1_PREGAME_STATE_ALLOWLIST_DRIFT",
    )

    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "rushing_owner": RUSHING_OWNER,
        "receiving_owner": RECEIVING_OWNER,
        "shared_gate": SHARED_GATE,
        "both_pages_call_shared_guard": True,
        "live_state_forced_closed": True,
        "guard_accepts_only_pregame_identity_states": True,
        "live_game_context_blocked_by_shared_gate": True,
        "root_cause_class": ROOT_CAUSE_CLASS,
        # PR #1116 was a pregame-only repair whose stated live/final contract
        # remained CLOSED; it cannot own this new live-game mission.
        "old_pregame_fix_not_authoritative": True,
        "next_patch_owner": SHARED_GATE,
        "page_specific_patch_required": False,
        "product_mutation": False,
        "api2_used": False,
    }


def main() -> int:
    result = verify_repository_root_cause()
    print("NFL_LIVE_GAME_REPAIR_STEP1_ROOT_CAUSE_GREEN")
    print("NFL_LIVE_GAME_REPAIR_STEP1_SHARED_GATE_OWNER_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
