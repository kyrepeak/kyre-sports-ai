from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "api2-finalization-authority-v1-step5-authority-garbage-collector"
WORKSTREAM = "api2-finalization-authority-v1-step5"
PLAN_PATH = "devsystem/runless_proof_plans/api2-finalization-authority-v1-step5-authority-garbage-collector.json"
SOURCE_MAIN_SHA = "b42b320e69d4894ed2ec5bbd3a065824d35d6fff"
SOURCE_CANDIDATE_SHA = "2dc37818dce15a606168a4cb74c6e322d4a2d630"
MAIN_SHA = "6c193bab72e6b55e1e39558d3322887643b78a87"
PREMERGE_PROOF_ID = "api2-finalization-authority-v1-step5-authority-garbage-collector-2dc37818dce15a60-94a41dddf1b6d71a"
PREMERGE_DIGEST = "17fc58f2dd755e8548279b76b1d2aa8a0ab6a2c73124fbe309a33fba3e9e2881"
PREMERGE_CHECK_ID = 113104300574
MERGED_PROOF_ID = "api2-finalization-authority-v1-step5-authority-garbage-collector-6c193bab72e6b55e-reused"
FREEZE_TOKEN = "API2_FINALIZATION_AUTHORITY_V1_STEP5_FROZEN"
FREEZE_PATHS = (
    "devsystem/authority_garbage_collector_v1.py",
    "devsystem/execution_plans/api2-finalization-authority-v1-step5-authority-garbage-collector.json",
    "devsystem/runless_proof_plans/api2-finalization-authority-v1-step5-authority-garbage-collector.json",
    "devsystem/task_ledgers/api2-finalization-authority-v1-step5-authority-garbage-collector.json",
    "docs/superpowers/plans/2026-10-07-api2-finalization-authority-step5-authority-garbage-collector.md",
    "tests/test_devsystem_authority_garbage_collector_v1.py",
)
LEASE_ID = "SCOPE-LEASE-A3A152588DF5D49023157EDE"
LEASE_OWNER = "api2-finalization-authority-v1-step5-closeout"
EXPECTED_REGISTRY_REVISION = 191
EXPECTED_REGISTRY_HASH = "16fe54db6c99ab205d28225c967b87c2227b8a22e7e93dc5fe10f4e0593a7a5d"
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
        kwargs["step"] = "api2-finalization-authority-v1-step5-authority-garbage-collector"
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
        "RUNLESS_TASK17_STEP5", "API2_FINALIZATION_AUTHORITY_V1_STEP5"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "5/6"
    return result


def install_startup(app):
    app.state.api2_finalization_authority_step5_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step5_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.api2_finalization_authority_step5_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP5_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.api2_finalization_authority_step5_closeout, sort_keys=True),
            flush=True,
        )

    return app
