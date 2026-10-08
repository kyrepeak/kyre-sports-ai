from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step4-public-repair"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-public-repair.json"
SOURCE_MAIN_SHA = "81eab31f78e65728a9b55a5ac578706fd6971bec"
SOURCE_CANDIDATE_SHA = "2063f0152861a0ebfb799837251cd973740eb812"
MAIN_SHA = "40b3049f2089833dacafda8c24086b9ef11a2cbd"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-public-repair-2063f0152861a0eb-c22dd86878121ef1"
PREMERGE_DIGEST = "acbfb68ada05c89b11a1559124f65abf35f3ae342f907ea1f34a21969ef3fdb5"
PREMERGE_CHECK_ID = 113380273936
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step4-public-repair-40b3049f2089833d-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PUBLIC_RUNTIME_REPAIR_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_page1_v2_step4_public_repair_v1.py",
    "streamlit_memory_lazy_router_v191.py",
    "tests/test_cfb_game_total_page1_v2_step4_public_repair.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-public-repair.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-public-repair.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-public-repair.json",
)
LEASE_ID = "SCOPE-LEASE-38737E92BDD76FF66BC2F480"
LEASE_OWNER = "api2-cfb-game-total-page1-v2-step4-public-repair-closeout"
EXPECTED_REGISTRY_REVISION = 201
EXPECTED_REGISTRY_HASH = "64b4a8211fdbe955a5a1435aacebbbf913ee5ce1f672fad5b9ce50cc5e01f873"
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
        kwargs["step"] = "cfb-game-total-page1-v2-step4-public-runtime-repair"
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
        "RUNLESS_TASK17_STEP5", "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PUBLIC_REPAIR"
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PUBLIC_REPAIR_CLOSEOUT="
        + json.dumps(result, sort_keys=True, default=str),
        flush=True,
    )
    return result
