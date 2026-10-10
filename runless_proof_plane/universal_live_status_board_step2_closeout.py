from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "universal-live-status-board-v1-step2-authoritative-chat-ownership"
WORKSTREAM = "universal-live-status-board-v1"
PLAN_PATH = "devsystem/runless_proof_plans/universal-live-status-board-v1-step2-authoritative-chat-ownership.json"
SOURCE_MAIN_SHA = "20f23cae36b70ba702657546296560c5432203dc"
SOURCE_CANDIDATE_SHA = "374dbb2a4702a6a5f87b977c8822db93e8481897"
MAIN_SHA = "e80be10496112f6b43f4652a64ddecbfc921b87a"
PREMERGE_PROOF_ID = "universal-live-status-board-v1-step2-authoritative-chat-ownership-374dbb2a4702a6a5-54c88c195c92e0ee"
PREMERGE_DIGEST = "d945e6c3cb6b4457ab9cf01b74e78a16c7123105277797c9306691ccf5085807"
PREMERGE_CHECK_ID = 114130436130
MERGED_PROOF_ID = "universal-live-status-board-v1-step2-authoritative-chat-ownership-e80be10496112f6b-reused"
FREEZE_TOKEN = "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP2_AUTHORITATIVE_CHAT_OWNERSHIP_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/universal-live-status-board-v1-step2-authoritative-chat-ownership.json",
    "devsystem/runless_proof_plans/universal-live-status-board-v1-step2-authoritative-chat-ownership.json",
    "devsystem/task_ledgers/universal-live-status-board-v1-step2-authoritative-chat-ownership.json",
    "devsystem/universal_live_status_board_ownership_v1.py",
    "docs/superpowers/plans/2026-10-09-universal-live-status-board-v1-step2-authoritative-chat-ownership.md",
    "tests/test_devsystem_universal_live_status_board_ownership_v1.py",
)
LEASE_ID = "SCOPE-LEASE-C075387DF04F9897C32FBCB3"
LEASE_OWNER = "universal-live-status-board-v1-step2-closeout"
EXPECTED_REGISTRY_REVISION = 235
EXPECTED_REGISTRY_HASH = "5ffe9963a665cc0ed7688862d4aa51cc5b39487268ba44640ef4971b25d445dc"
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
        kwargs["step"] = "universal-live-status-board-v1-step2-authoritative-chat-ownership"
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
        "RUNLESS_TASK17_STEP5", "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP2"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "2/4"
    return result


def install_startup(app):
    app.state.universal_live_status_board_step2_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step2_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.universal_live_status_board_step2_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP2_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.universal_live_status_board_step2_closeout, sort_keys=True),
            flush=True,
        )

    return app
