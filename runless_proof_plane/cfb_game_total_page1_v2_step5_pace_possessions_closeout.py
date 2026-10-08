from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step5-pace-possessions"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step5-pace-possessions.json"
SOURCE_MAIN_SHA = "53c4bf0aa194befe56934d476f0f1a1a22d3d40d"
SOURCE_CANDIDATE_SHA = "0d5ec9bd4ec10562350693b9fac23cb95541f337"
MAIN_SHA = "a1dfac558c76253f99e2279dd7cb45e944d913a6"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step5-pace-possessions-0d5ec9bd4ec10562-acd7ef88fcd9aaac"
PREMERGE_DIGEST = "cafbef6b56d39ff0157244097a62801efdccc61b62e0dc51d94014f7fb521215"
PREMERGE_CHECK_ID = 113501880910
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step5-pace-possessions-a1dfac558c76253f-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP5_PACE_POSSESSIONS_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_clean_page_v17.py",
    "cfb_game_total_step5_pace_v1.py",
    "data/cfb_step5_pbp_snapshot_v1.json",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step5-pace-possessions.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step5-pace-possessions.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step5-pace-possessions.json",
    "tests/test_cfb_game_total_page1_v2_step5_pace_possessions_v1.py",
)
LEASE_ID = "SCOPE-LEASE-86D1BF4390BC3586AFFD01EA"
LEASE_OWNER = "api2-cfb-step5-pace-closeout-r2"
EXPECTED_REGISTRY_REVISION = 205
EXPECTED_REGISTRY_HASH = "5608b396896c3a1aa5c5f3eae815c8f22141a1d4110593baa1f02ee640a5189b"
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
        kwargs["step"] = "cfb-game-total-page1-v2-step5-pace-possessions"
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP5_PACE_POSSESSIONS",
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "5/9"
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
        "CFB_GAME_TOTAL_PAGE1_V2_STEP5_PACE_POSSESSIONS_CLOSEOUT="
        + json.dumps(result, sort_keys=True, default=str),
        flush=True,
    )
    return result
