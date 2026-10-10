from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "universal-live-status-board-v1-step4-enforcement-gate"
WORKSTREAM = "universal-live-status-board-v1"
PLAN_PATH = "devsystem/runless_proof_plans/universal-live-status-board-v1-step4-enforcement-gate.json"
SOURCE_MAIN_SHA = "77b6cfb53b5bbb09c88269d366ea0ea075acc91e"
SOURCE_CANDIDATE_SHA = "3f2281c91332afeb2a8d7d8ac6a3d23792b3f200"
MAIN_SHA = "3876d4cbe7fe541c94cf3d8e71cc0103b1a6ec66"
PREMERGE_PROOF_ID = "universal-live-status-board-v1-step4-enforcement-gate-3f2281c91332afeb-60655232a2b8457c"
PREMERGE_DIGEST = "99c47c0a866693c45ee933be982a0196ea3839830f26b1dc16b7686cb3c73d7b"
PREMERGE_CHECK_ID = 114136060340
MERGED_PROOF_ID = "universal-live-status-board-v1-step4-enforcement-gate-3876d4cbe7fe541c-reused"
FREEZE_TOKEN = "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP4_ENFORCEMENT_GATE_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/universal-live-status-board-v1-step4-enforcement-gate.json",
    "devsystem/runless_proof_plans/universal-live-status-board-v1-step4-enforcement-gate.json",
    "devsystem/task_ledgers/universal-live-status-board-v1-step4-enforcement-gate.json",
    "devsystem/universal_live_status_board_enforcement_v1.py",
    "tests/test_devsystem_universal_live_status_board_enforcement_v1.py",
)
LEASE_ID = "SCOPE-LEASE-F4A7E16B32C8D04A98B7C631"
LEASE_OWNER = "universal-live-status-board-v1-step4-closeout"
EXPECTED_REGISTRY_REVISION = 237
EXPECTED_REGISTRY_HASH = "f092e6d5515920d09e3674446c5e320b9def59adbc5b8ebf084d0d54d7785743"
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
        kwargs["step"] = "universal-live-status-board-v1-step4-enforcement-gate"
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
        "RUNLESS_TASK17_STEP5", "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP4"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "4/4"
    return result


def install_startup(app):
    app.state.universal_live_status_board_step4_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step4_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.universal_live_status_board_step4_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP4_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.universal_live_status_board_step4_closeout, sort_keys=True),
            flush=True,
        )

    return app
