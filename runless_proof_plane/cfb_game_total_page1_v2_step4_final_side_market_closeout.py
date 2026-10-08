from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step4-final-side-market"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-final-side-market.json"
SOURCE_MAIN_SHA = "2a8039a5f2dc9980711674e92b6d7ec35ab5df29"
SOURCE_CANDIDATE_SHA = "3d1d6a0a7a0be69e252aa5168887f21a72baf6d4"
MAIN_SHA = "53c4bf0aa194befe56934d476f0f1a1a22d3d40d"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-final-side-market-3d1d6a0a7a0be69e-29db586a64ea7da3"
PREMERGE_DIGEST = "fcf21eb830d109158aa74d178fb092bc01d2a2bd6aabe424d6ca5b53cec3daba"
PREMERGE_CHECK_ID = 113471897032
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step4-final-side-market-53c4bf0aa194befe-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_FINAL_SIDE_MARKET_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_clean_page_v16.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-final-side-market.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-final-side-market.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-final-side-market.json",
    "tests/test_cfb_game_total_page1_v2_step4_final_side_market_v1.py",
)
LEASE_ID = "SCOPE-LEASE-8BCD3B7AF0635C060E469C47"
LEASE_OWNER = "api2-cfb-step4-final-side-market-closeout-r1"
EXPECTED_REGISTRY_REVISION = 204
EXPECTED_REGISTRY_HASH = "e91a9cc37d0cda84b16a2d0376e313ee9ed1985369cb782a4ba5ccd0f0d10535"
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
        kwargs["step"] = "cfb-game-total-page1-v2-step4-final-side-market"
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_FINAL_SIDE_MARKET",
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_FINAL_SIDE_MARKET_CLOSEOUT="
        + json.dumps(result, sort_keys=True, default=str),
        flush=True,
    )
    return result
