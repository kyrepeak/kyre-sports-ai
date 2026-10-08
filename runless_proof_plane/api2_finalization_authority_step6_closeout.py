from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "api2-finalization-authority-v1-step6-100-percent-finalizer"
WORKSTREAM = "api2-finalization-authority-v1-step6"
PLAN_PATH = "devsystem/runless_proof_plans/api2-finalization-authority-v1-step6-100-percent-finalizer.json"
SOURCE_MAIN_SHA = "6c193bab72e6b55e1e39558d3322887643b78a87"
SOURCE_CANDIDATE_SHA = "4113a20ed0ecf75132b53f45beda6825cca5c8c3"
MAIN_SHA = "371f05b940369c3378ceea8f12fb02e52e5f7f11"
PREMERGE_PROOF_ID = "api2-finalization-authority-v1-step6-100-percent-finalizer-4113a20ed0ecf751-5ee82f46a2d66c04"
PREMERGE_DIGEST = "a4e32ba93dbb97e092d9e4b831f0efe183d35e79e97498651d472d0ca988136f"
PREMERGE_CHECK_ID = 113117110666
MERGED_PROOF_ID = "api2-finalization-authority-v1-step6-100-percent-finalizer-371f05b940369c33-reused"
FREEZE_TOKEN = "API2_FINALIZATION_AUTHORITY_V1_STEP6_FROZEN"
FREEZE_PATHS = (
    "devsystem/finalization_100_percent_finalizer_v1.py",
    "tests/test_devsystem_finalization_100_percent_finalizer_v1.py",
    "devsystem/runless_proof_plans/api2-finalization-authority-v1-step6-100-percent-finalizer.json",
    "devsystem/execution_plans/api2-finalization-authority-v1-step6-100-percent-finalizer.json",
    "devsystem/task_ledgers/api2-finalization-authority-v1-step6-100-percent-finalizer.json",
    "docs/superpowers/plans/2026-10-07-api2-finalization-authority-step6-100-percent-finalizer.md",
)
LEASE_ID = "SCOPE-LEASE-473B7FBF6B47C99A0B6082E6"
LEASE_OWNER = "api2-finalization-authority-v1-step6-closeout"
EXPECTED_REGISTRY_REVISION = 192
EXPECTED_REGISTRY_HASH = "3cc070a9e710fe3cbe1fee69448b05b1e3117e3b0454fb60ed6dfd2c675b103c"
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
        kwargs["step"] = "api2-finalization-authority-v1-step6-100-percent-finalizer"
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
        "RUNLESS_TASK17_STEP5", "API2_FINALIZATION_AUTHORITY_V1_STEP6"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "6/6"
    return result


def install_startup(app):
    app.state.api2_finalization_authority_step6_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step6_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.api2_finalization_authority_step6_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP6_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.api2_finalization_authority_step6_closeout, sort_keys=True),
            flush=True,
        )

    return app
