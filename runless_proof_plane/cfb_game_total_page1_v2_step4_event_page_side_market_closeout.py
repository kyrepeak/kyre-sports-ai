from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step4-event-page-side-market-repair"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-event-page-side-market-repair.json"
SOURCE_MAIN_SHA = "38698b8ed33b96547af855780953b414a6d34131"
SOURCE_CANDIDATE_SHA = "be3e23d0fdc5409682ddea029cb36c17a73850d4"
MAIN_SHA = "2a8039a5f2dc9980711674e92b6d7ec35ab5df29"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-event-page-side-market-repair-be3e23d0fdc54096-b27a9b716bd27f44"
PREMERGE_DIGEST = "42cfacabfe2296bcc49d7618c0921139d818e80f66d4ba351ebd6a18edae1364"
PREMERGE_CHECK_ID = 113448338238
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step4-event-page-side-market-repair-2a8039a5f2dc9980-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_EVENT_PAGE_SIDE_MARKET_REPAIR_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1.py",
    "cfb_over_under_market_adapter_v1.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-event-page-side-market-repair.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-event-page-side-market-repair.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-event-page-side-market-repair.json",
    "tests/test_cfb_game_total_page1_v2_step4_event_page_side_market_repair.py",
)
LEASE_ID = "SCOPE-LEASE-6BF74F8BCA88F53A90227FF3"
LEASE_OWNER = "api2-cfb-step4-event-page-side-market-closeout-r1"
EXPECTED_REGISTRY_REVISION = 203
EXPECTED_REGISTRY_HASH = "6878008b2e08d1cd2d7bc53bd16aca0ec0b18c075dca9a443f1e48d60fbd2f59"
EXPECTED_EVENT_HASH = "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"


def _bindings() -> dict[str, object]:
    return {
        "TASK_ID": TASK_ID,
        "WORKSTREAM": WORKSTREAM,
        "PLAN_PATH": PLAN_PATH,
        "SOURCE_MAIN_SHA": SOURCE_MAIN_SHA,
        "SOURCE_CANDIDATE_SHA": SOURCE_CANDIDATE_SHA,
        "MAIN_SHA": MAIN_SHA,
        "PREMERGE_PROOF_ID": PREMERGE_PROOF_ID,
        "PREMERGE_DIGEST": PREMERGE_DIGEST,
        "PREMERGE_CHECK_ID": PREMERGE_CHECK_ID,
        "MERGED_PROOF_ID": MERGED_PROOF_ID,
        "FREEZE_TOKEN": FREEZE_TOKEN,
        "FREEZE_PATHS": FREEZE_PATHS,
        "LEASE_ID": LEASE_ID,
        "LEASE_OWNER": LEASE_OWNER,
        "EXPECTED_REGISTRY_REVISION": EXPECTED_REGISTRY_REVISION,
        "EXPECTED_REGISTRY_HASH": EXPECTED_REGISTRY_HASH,
        "EXPECTED_EVENT_HASH": EXPECTED_EVENT_HASH,
    }


def execute(client):
    saved = {name: getattr(core, name) for name in _bindings()}
    original_build_receipt = core.build_runless_receipt

    def _build_receipt(**kwargs):
        kwargs["step"] = "cfb-game-total-page1-v2-step4-event-page-side-market-repair"
        return original_build_receipt(**kwargs)

    try:
        for name, value in _bindings().items():
            setattr(core, name, value)
        core.build_runless_receipt = _build_receipt
        result = dict(core.execute(client))
    finally:
        core.build_runless_receipt = original_build_receipt
        for name, value in saved.items():
            setattr(core, name, value)

    decision = str(result.get("decision") or "")
    result["decision"] = decision.replace(
        "RUNLESS_TASK17_STEP5",
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_EVENT_PAGE_SIDE_MARKET_REPAIR",
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "4/9"
    return result


def run_and_print(client):
    try:
        result = execute(client)
    except Exception as exc:
        result = {
            "status": "FAIL",
            "error": type(exc).__name__,
            "detail": str(exc)[:1800],
        }
    print(
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_EVENT_PAGE_SIDE_MARKET_CLOSEOUT="
        + json.dumps(result, sort_keys=True, default=str),
        flush=True,
    )
    return result
