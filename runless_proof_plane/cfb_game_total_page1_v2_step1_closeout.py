from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step1-audit-lock"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step1-audit-lock.json"
SOURCE_MAIN_SHA = "371f05b940369c3378ceea8f12fb02e52e5f7f11"
SOURCE_CANDIDATE_SHA = "b54835a412503b4a06a69d84393fe87ac6a65aee"
MAIN_SHA = "8563157c27fe3c13a3084e79230910cdb5e0841a"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step1-audit-lock-b54835a412503b4a-1f113b3d8644ccc7"
PREMERGE_DIGEST = "7a2ec8217900111783903f16837672ac483e2d8b12d96ea169f5969210593b8d"
PREMERGE_CHECK_ID = 113133911939
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step1-audit-lock-8563157c27fe3c13-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP1_AUDIT_LOCK_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/cfb-game-total-page1-v2-step1-audit-lock.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step1-audit-lock.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step1-audit-lock.json",
    "docs/CFB_GAME_TOTAL_PAGE1_V2_STEP1_AUDIT_CONTRACT.md",
    "tests/test_cfb_game_total_page1_v2_step1_audit_lock.py",
)
LEASE_ID = "SCOPE-LEASE-8F71EAE5D4532B25F3E4B243"
LEASE_OWNER = "cfb-game-total-page1-v2-step1-closeout"
EXPECTED_REGISTRY_REVISION = 193
EXPECTED_REGISTRY_HASH = "3e85d01c279ad581e945f2132a6eee14b4ef290a6903aa263fde0172672e71f3"
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
        kwargs["step"] = "cfb-game-total-page1-v2-step1-audit-lock"
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
        "RUNLESS_TASK17_STEP5", "CFB_GAME_TOTAL_PAGE1_V2_STEP1"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "1/9"
    return result


def install_startup(app):
    app.state.cfb_game_total_page1_v2_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step1_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP1_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_page1_v2_step1_closeout, sort_keys=True),
            flush=True,
        )

    return app
