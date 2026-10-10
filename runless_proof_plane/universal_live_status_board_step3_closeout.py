from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "universal-live-status-board-v1-step3-heartbeat-recovery"
WORKSTREAM = "universal-live-status-board-v1"
PLAN_PATH = "devsystem/runless_proof_plans/universal-live-status-board-v1-step3-heartbeat-recovery.json"
SOURCE_MAIN_SHA = "e80be10496112f6b43f4652a64ddecbfc921b87a"
SOURCE_CANDIDATE_SHA = "3f95e35187d7f27990f18a41ff40910e8e86928a"
MAIN_SHA = "77b6cfb53b5bbb09c88269d366ea0ea075acc91e"
PREMERGE_PROOF_ID = "universal-live-status-board-v1-step3-heartbeat-recovery-3f95e35187d7f279-4f706f2dda495605"
PREMERGE_DIGEST = "ebaf8f73f8f4d0e8f9425aa8dba4079fbe78a0f6b47fd5d88330736f74383acf"
PREMERGE_CHECK_ID = 114133779801
MERGED_PROOF_ID = "universal-live-status-board-v1-step3-heartbeat-recovery-77b6cfb53b5bbb09-reused"
FREEZE_TOKEN = "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP3_HEARTBEAT_STALE_OWNER_RECOVERY_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/universal-live-status-board-v1-step3-heartbeat-recovery.json",
    "devsystem/runless_proof_plans/universal-live-status-board-v1-step3-heartbeat-recovery.json",
    "devsystem/task_ledgers/universal-live-status-board-v1-step3-heartbeat-recovery.json",
    "devsystem/universal_live_status_board_recovery_v1.py",
    "docs/superpowers/plans/2026-10-10-universal-live-status-board-v1-step3-heartbeat-recovery.md",
    "tests/test_devsystem_universal_live_status_board_recovery_v1.py",
)
LEASE_ID = "SCOPE-LEASE-17C2C49A9B6F67294461196C"
LEASE_OWNER = "universal-live-status-board-v1-step3-closeout"
EXPECTED_REGISTRY_REVISION = 236
EXPECTED_REGISTRY_HASH = "115ce53d9a0a3ab82786feb31b760d2f4e92bbb9ced1a76349268d826edf581e"
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
        kwargs["step"] = "universal-live-status-board-v1-step3-heartbeat-recovery"
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
        "RUNLESS_TASK17_STEP5", "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP3"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "3/4"
    return result


def install_startup(app):
    app.state.universal_live_status_board_step3_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step3_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.universal_live_status_board_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP3_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.universal_live_status_board_step3_closeout, sort_keys=True),
            flush=True,
        )

    return app
