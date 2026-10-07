from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "api2-finalization-authority-v1-step1-canonical-completion"
WORKSTREAM = "api2-finalization-authority-v1-step1"
PLAN_PATH = "devsystem/runless_proof_plans/api2-finalization-authority-v1-step1-canonical-completion.json"
SOURCE_MAIN_SHA = "7e1d91948caf36e45535259bb5547689f211ce9a"
SOURCE_CANDIDATE_SHA = "765202074708f645f2d06b981771d70f0c3cbba3"
MAIN_SHA = "f9908fb83de2e19d3ff1d47b728dac8ba3fef2e0"
PREMERGE_PROOF_ID = "api2-finalization-authority-v1-step1-canonical-completion-765202074708f645-90535fe9272ce12a"
PREMERGE_DIGEST = "8cfb999e30550e1461c692e2e8dc8d37bd8a53bbc927a947e5ce0ec05e099a5f"
PREMERGE_CHECK_ID = 112967557781
MERGED_PROOF_ID = "api2-finalization-authority-v1-step1-canonical-completion-f9908fb83de2e19d-reused"
FREEZE_TOKEN = "API2_FINALIZATION_AUTHORITY_V1_STEP1_FROZEN"
FREEZE_PATHS = (
    "devsystem/canonical_completion_resolver_v1.py",
    "devsystem/execution_plans/api2-finalization-authority-v1-step1-canonical-completion.json",
    "devsystem/runless_proof_plans/api2-finalization-authority-v1-step1-canonical-completion.json",
    "devsystem/task_ledgers/api2-finalization-authority-v1-step1-canonical-completion.json",
    "docs/superpowers/plans/2026-10-07-api2-finalization-authority-step1-canonical-completion.md",
    "tests/test_devsystem_canonical_completion_resolver_v1.py",
)
LEASE_ID = "SCOPE-LEASE-6329DB546E53EEF330D5F429"
LEASE_OWNER = "api2-finalization-authority-v1-step1"
EXPECTED_REGISTRY_REVISION = 183
EXPECTED_REGISTRY_HASH = "2b16684c9addc8ab2da60aee80bdcfb20199bcabc2b425d519f8ae2bd8843c01"
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
        kwargs["step"] = "api2-finalization-authority-v1-step1-canonical-completion"
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
        "RUNLESS_TASK17_STEP5", "API2_FINALIZATION_AUTHORITY_V1_STEP1"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "1/6"
    return result


def install_startup(app):
    app.state.api2_finalization_authority_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step1_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.api2_finalization_authority_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP1_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.api2_finalization_authority_step1_closeout, sort_keys=True),
            flush=True,
        )

    return app
