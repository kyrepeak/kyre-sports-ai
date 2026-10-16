from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MISSION_STEP = "4/4"
WORKSTREAM = "monster-cfb-game-total-integration-repair-v1"
API2_USED = False
MAY_MODIFY_PAGE = False
MAY_MODIFY_ROUTER = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_PROVIDER = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

REQUIRED_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")
REQUIRED_PAGE1_ROUTE = "cfb_game_total_clean_page_v43"
REQUIRED_RUNTIME_REPAIR = "cfb_game_total_clean_page_v44"
REQUIRED_PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"

PRIOR_STEPS = {
    "step1": {
        "path": "devsystem/task_ledgers/monster-cfb-game-total-shell-integration-step1-v1.json",
        "step": "1/4",
        "freeze_token": "MONSTER_CFB_GAME_TOTAL_SHELL_INTEGRATION_STEP1_V1_FROZEN",
    },
    "step2": {
        "path": "devsystem/task_ledgers/monster-cfb-game-total-runtimeerror-step2-v1.json",
        "step": "2/4",
        "freeze_token": "MONSTER_CFB_GAME_TOTAL_RUNTIMEERROR_STEP2_V1_FROZEN",
    },
    "step3": {
        "path": "devsystem/task_ledgers/monster-cfb-game-total-native-regression-step3-v1.json",
        "step": "3/4",
        "freeze_token": "MONSTER_CFB_GAME_TOTAL_NATIVE_REGRESSION_STEP3_V1_FROZEN",
    },
}

REQUIRED_REGRESSION_TESTS = (
    "tests/test_cfb_game_total_shell_integration_step1_v1.py",
    "tests/test_cfb_game_total_runtimeerror_step2_v1.py",
    "tests/test_monster_cfb_game_total_native_regression_step3_v1.py",
    "tests/test_cfb_game_total_game_cards_step6_v1.py",
    "tests/test_cfb_game_total_step8_page1_event_guard_r1.py",
    "tests/test_cfb_game_total_step8_route_pointer_lock_r1.py",
)


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AssertionError(code)


def verify_repository_contract(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)

    prior: dict[str, bool] = {}
    for name, contract in PRIOR_STEPS.items():
        payload = _read_json(base, contract["path"])
        ok = (
            payload.get("workstream") == WORKSTREAM
            and payload.get("step") == contract["step"]
            and payload.get("freeze_token") == contract["freeze_token"]
        )
        _require(ok, f"STEP4_{name.upper()}_CONTRACT_DRIFT")
        prior[name] = True

    router_text = (
        base / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
    ).read_text(encoding="utf-8")
    repair_text = (base / "cfb_game_total_clean_page_v44.py").read_text(encoding="utf-8")

    _require(
        f'PAGE1_NATIVE_ROUTE = "{REQUIRED_PAGE1_ROUTE}"' in router_text,
        "STEP4_PAGE1_OWNER_DRIFT",
    )
    _require(
        "import cfb_game_total_clean_page_v44 as runtime_repair" in router_text,
        "STEP4_V44_RUNTIME_SEAM_MISSING",
    )
    _require(
        f'PAGE2_RUNTIME = "{REQUIRED_PAGE2_RUNTIME}"' in router_text,
        "STEP4_PAGE2_OWNER_DRIFT",
    )
    _require(
        'CFB_SHELL_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")'
        in router_text,
        "STEP4_CFB_MARKET_SET_DRIFT",
    )
    _require(
        "snapshot_owner.render_game_total_hub = original_snapshot_render" in router_text,
        "STEP4_PAGE1_RUNTIME_SEAM_RESTORE_MISSING",
    )
    _require(
        "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in router_text
        and "live_owner.ACTIVE_PAGE = original_live_page" in router_text
        and "render_owner.ACTIVE_PAGE = original_render_page" in router_text,
        "STEP4_PAGE2_POINTER_RESTORE_MISSING",
    )

    _require(
        "STALE_DOWNSTREAM_DAY_USES_PINNED_SNAPSHOT = True" in repair_text,
        "STEP4_STALE_DATE_REPAIR_DRIFT",
    )
    _require(
        "SELECTED_DAY_SNAPSHOT_OWNS_GAME_LOADING = True" in repair_text,
        "STEP4_SELECTED_DAY_OWNERSHIP_DRIFT",
    )
    _require(
        "snapshot_owner.games_owner._load_games = original_loader" in repair_text,
        "STEP4_V44_LOADER_RESTORE_MISSING",
    )

    for relative in REQUIRED_REGRESSION_TESTS:
        _require((base / relative).is_file(), f"STEP4_REQUIRED_TEST_MISSING:{relative}")

    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "workstream": WORKSTREAM,
        "step1_contract": prior["step1"],
        "step2_contract": prior["step2"],
        "step3_contract": prior["step3"],
        "shared_cfb_shell_preserved": True,
        "cfb_market_set": REQUIRED_MARKETS,
        "page1_owner": REQUIRED_PAGE1_ROUTE,
        "runtime_repair": REQUIRED_RUNTIME_REPAIR,
        "stale_date_runtimeerror_repair_preserved": True,
        "page2_owner": REQUIRED_PAGE2_RUNTIME,
        "temporary_seams_restore": True,
        "product_runtime_mutation": False,
        "model_projection_probability_mutation": False,
        "provider_mutation": False,
        "page2_mutation": False,
        "other_sports_mutation": False,
        "network_calls_added": 0,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "api2_used": API2_USED,
    }


def finalize_closeout(repository_contract: dict[str, Any]) -> dict[str, Any]:
    _require(repository_contract.get("status") == "GREEN", "STEP4_REPOSITORY_NOT_GREEN")
    for key in (
        "step1_contract",
        "step2_contract",
        "step3_contract",
        "shared_cfb_shell_preserved",
        "stale_date_runtimeerror_repair_preserved",
        "temporary_seams_restore",
    ):
        _require(repository_contract.get(key) is True, f"STEP4_REQUIRED_CONTRACT_RED:{key}")
    _require(
        repository_contract.get("page1_owner") == REQUIRED_PAGE1_ROUTE,
        "STEP4_PAGE1_FINAL_IDENTITY_DRIFT",
    )
    _require(
        repository_contract.get("page2_owner") == REQUIRED_PAGE2_RUNTIME,
        "STEP4_PAGE2_FINAL_IDENTITY_DRIFT",
    )
    _require(
        tuple(repository_contract.get("cfb_market_set") or ()) == REQUIRED_MARKETS,
        "STEP4_MARKET_SET_FINAL_DRIFT",
    )
    for key in (
        "product_runtime_mutation",
        "model_projection_probability_mutation",
        "provider_mutation",
        "page2_mutation",
        "other_sports_mutation",
        "api2_used",
    ):
        _require(repository_contract.get(key) is False, f"STEP4_PROTECTED_SCOPE_MUTATED:{key}")
    _require(
        float(repository_contract.get("sportsbook_projection_influence", -1.0)) == 0.0,
        "STEP4_SPORTSBOOK_INFLUENCE_DRIFT",
    )
    return {
        "status": "GREEN",
        "decision": "MONSTER_CFB_GAME_TOTAL_INTEGRATION_REPAIR_MISSION_GREEN",
        "mission_step": MISSION_STEP,
        "workstream": WORKSTREAM,
        "steps_1_3_composed": True,
        "product_runtime_mutation": False,
        "api2_used": False,
    }


__all__ = [
    "API2_USED",
    "MISSION_STEP",
    "NETWORK_CALLS",
    "PRIOR_STEPS",
    "REQUIRED_MARKETS",
    "REQUIRED_PAGE1_ROUTE",
    "REQUIRED_PAGE2_RUNTIME",
    "REQUIRED_REGRESSION_TESTS",
    "REQUIRED_RUNTIME_REPAIR",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "WORKSTREAM",
    "finalize_closeout",
    "verify_repository_contract",
]
