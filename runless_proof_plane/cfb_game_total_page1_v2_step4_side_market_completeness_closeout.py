from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step4-side-market-completeness"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-side-market-completeness.json"
SOURCE_MAIN_SHA = "40b3049f2089833dacafda8c24086b9ef11a2cbd"
SOURCE_CANDIDATE_SHA = "2e5c78f058384f6ba62cca6cd1ff07fc0ce72211"
MAIN_SHA = "38698b8ed33b96547af855780953b414a6d34131"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-side-market-completeness-2e5c78f058384f6b-3bf7845392bbd865"
PREMERGE_DIGEST = "ada04579446729758e2bc31b73ef3b17f82a9dd7c01f5bd3c661f2faa6e0367e"
PREMERGE_CHECK_ID = 113412437001
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step4-side-market-completeness-38698b8ed33b9654-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_SIDE_MARKET_COMPLETENESS_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py",
    "kyre_remaining_pages_theme_v1.py",
    "tests/test_cfb_game_total_page1_v2_step4_side_market_completeness.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-side-market-completeness.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-side-market-completeness.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-side-market-completeness.json",
)
LEASE_ID = "SCOPE-LEASE-27CDF94F1F50D666D2AD3096"
LEASE_OWNER = "api2-cfb-game-total-page1-v2-step4-side-market-completeness-closeout"
EXPECTED_REGISTRY_REVISION = 202
EXPECTED_REGISTRY_HASH = "e01174fb37bae3a99f472952965c2b35c42c9eef7e1390f3913696c350c92cb0"
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
        kwargs["step"] = "cfb-game-total-page1-v2-step4-side-market-completeness"
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_SIDE_MARKET_COMPLETENESS",
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_SIDE_MARKET_COMPLETENESS_CLOSEOUT="
        + json.dumps(result, sort_keys=True, default=str),
        flush=True,
    )
    return result
