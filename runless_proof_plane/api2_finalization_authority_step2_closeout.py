from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "api2-finalization-authority-v1-step2-ledger-auto-heal"
WORKSTREAM = "api2-finalization-authority-v1-step2"
PLAN_PATH = "devsystem/runless_proof_plans/api2-finalization-authority-v1-step2-ledger-auto-heal.json"
SOURCE_MAIN_SHA = "f9908fb83de2e19d3ff1d47b728dac8ba3fef2e0"
SOURCE_CANDIDATE_SHA = "a2346424496c8f4b307c6066028e47fd21b52c68"
MAIN_SHA = "219ed8367207538a909986841e66807e408feede"
PREMERGE_PROOF_ID = "api2-finalization-authority-v1-step2-ledger-auto-heal-a2346424496c8f4b-489ff6b26aef9b3b"
PREMERGE_DIGEST = "03532c1eda454e43d7d9ae09d3d106d8fda8abb483e228a601a00464c5b3e4b0"
PREMERGE_CHECK_ID = 112981011688
MERGED_PROOF_ID = "api2-finalization-authority-v1-step2-ledger-auto-heal-219ed8367207538a-reused"
FREEZE_TOKEN = "API2_FINALIZATION_AUTHORITY_V1_STEP2_FROZEN"
FREEZE_PATHS = (
    "devsystem/canonical_completion_ledger_autoheal_v1.py",
    "devsystem/execution_plans/api2-finalization-authority-v1-step2-ledger-auto-heal.json",
    "devsystem/runless_proof_plans/api2-finalization-authority-v1-step2-ledger-auto-heal.json",
    "devsystem/task_ledgers/api2-finalization-authority-v1-step2-ledger-auto-heal.json",
    "docs/superpowers/plans/2026-10-07-api2-finalization-authority-step2-ledger-auto-heal.md",
    "tests/test_devsystem_canonical_completion_ledger_autoheal_v1.py",
)
LEASE_ID = "SCOPE-LEASE-F76133E0182DB1131C5431A1"
LEASE_OWNER = "api2-finalization-authority-v1-step2"
EXPECTED_REGISTRY_REVISION = 184
EXPECTED_REGISTRY_HASH = "12b4c2cffe693c378c76e5c930538a43d312988c80f89e1d01546a72c04a0167"
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
        kwargs["step"] = "api2-finalization-authority-v1-step2-ledger-auto-heal"
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
        "RUNLESS_TASK17_STEP5", "API2_FINALIZATION_AUTHORITY_V1_STEP2"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "2/6"
    return result


def install_startup(app):
    app.state.api2_finalization_authority_step2_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step2_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.api2_finalization_authority_step2_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP2_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.api2_finalization_authority_step2_closeout, sort_keys=True),
            flush=True,
        )

    return app
