from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "api2-finalization-authority-v1-step3-terminal-completion-latch"
WORKSTREAM = "api2-finalization-authority-v1-step3"
PLAN_PATH = "devsystem/runless_proof_plans/api2-finalization-authority-v1-step3-terminal-completion-latch.json"
SOURCE_MAIN_SHA = "e313222d0c4e55a6217f4aaf62d3afed7aeead13"
SOURCE_CANDIDATE_SHA = "9658e67e2512b398fda6a7a545b1b2010f0bf184"
MAIN_SHA = "85bfd1031b12318c64ca090be5fd5807f57a2f49"
PREMERGE_PROOF_ID = "api2-finalization-authority-v1-step3-terminal-completion-latch-9658e67e2512b398-d8bfe17706c1b41a"
PREMERGE_DIGEST = "cb7960099518b8a82a92cb01037f8eb445674da2aa435c046c5a4b08b1d079b3"
PREMERGE_CHECK_ID = 113080850994
MERGED_PROOF_ID = "api2-finalization-authority-v1-step3-terminal-completion-latch-85bfd1031b12318c-reused"
FREEZE_TOKEN = "API2_FINALIZATION_AUTHORITY_V1_STEP3_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/api2-finalization-authority-v1-step3-terminal-completion-latch.json",
    "devsystem/runless_proof_plans/api2-finalization-authority-v1-step3-terminal-completion-latch.json",
    "devsystem/task_ledgers/api2-finalization-authority-v1-step3-terminal-completion-latch.json",
    "devsystem/terminal_completion_latch_v1.py",
    "docs/superpowers/plans/2026-10-07-api2-finalization-authority-step3-terminal-completion-latch.md",
    "tests/test_devsystem_terminal_completion_latch_v1.py",
)
LEASE_ID = "SCOPE-LEASE-67048376F53B606480D75ECF"
LEASE_OWNER = "api2-finalization-authority-v1-step3"
EXPECTED_REGISTRY_REVISION = 189
EXPECTED_REGISTRY_HASH = "e5853fb06d339c394f01bf9c7dd2decfbbe187c38c8a2629e6730d7353f5e563"
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
        kwargs["step"] = "api2-finalization-authority-v1-step3-terminal-completion-latch"
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
        "RUNLESS_TASK17_STEP5", "API2_FINALIZATION_AUTHORITY_V1_STEP3"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "3/6"
    return result


def install_startup(app):
    app.state.api2_finalization_authority_step3_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step3_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.api2_finalization_authority_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP3_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.api2_finalization_authority_step3_closeout, sort_keys=True),
            flush=True,
        )

    return app
