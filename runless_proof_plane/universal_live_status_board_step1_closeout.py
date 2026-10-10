from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "universal-live-status-board-v1-step1-mandatory-status-schema"
WORKSTREAM = "universal-live-status-board-v1"
PLAN_PATH = "devsystem/runless_proof_plans/universal-live-status-board-v1-step1-mandatory-status-schema.json"
SOURCE_MAIN_SHA = "3065e960d3363bf6f3d70252c906b9590e7293e9"
SOURCE_CANDIDATE_SHA = "7a75423426a92fee5ab98360e9dcea0d578ad971"
MAIN_SHA = "20f23cae36b70ba702657546296560c5432203dc"
PREMERGE_PROOF_ID = "universal-live-status-board-v1-step1-mandatory-status-schema-7a75423426a92fee-54b61a1e486dffbc"
PREMERGE_DIGEST = "afde39a7f75714f26ec388349640615e96165c00220eaf07bffeb1dee35fa069"
PREMERGE_CHECK_ID = 114122781854
MERGED_PROOF_ID = "universal-live-status-board-v1-step1-mandatory-status-schema-20f23cae36b70ba7-reused"
FREEZE_TOKEN = "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP1_MANDATORY_STATUS_SCHEMA_FROZEN"
FREEZE_PATHS = (
    "devsystem/universal_live_status_board_v1.py",
    "tests/test_devsystem_universal_live_status_board_v1.py",
    "devsystem/execution_plans/universal-live-status-board-v1-step1-mandatory-status-schema.json",
    "devsystem/runless_proof_plans/universal-live-status-board-v1-step1-mandatory-status-schema.json",
    "devsystem/task_ledgers/universal-live-status-board-v1-step1-mandatory-status-schema.json",
    "docs/superpowers/specs/2026-10-09-universal-live-status-board-v1-design.md",
    "docs/superpowers/plans/2026-10-09-universal-live-status-board-v1-step1-mandatory-status-schema.md",
)
LEASE_ID = "SCOPE-LEASE-81EB8ACBF4A76544A5BEC9AA"
LEASE_OWNER = "universal-live-status-board-v1-step1-closeout"
EXPECTED_REGISTRY_REVISION = 234
EXPECTED_REGISTRY_HASH = "36c4a0b32ef15ae2548a38b4de5ef96fa38dd10139cd2f81f720fc22b1c1a161"
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
        kwargs["step"] = "universal-live-status-board-v1-step1-mandatory-status-schema"
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
        "RUNLESS_TASK17_STEP5", "UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP1"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "1/4"
    return result


def install_startup(app):
    app.state.universal_live_status_board_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step1_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.universal_live_status_board_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP1_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.universal_live_status_board_step1_closeout, sort_keys=True),
            flush=True,
        )

    return app
