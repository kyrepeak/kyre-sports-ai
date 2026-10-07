from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "wnba-pra-history-multisource-v1-step1"
WORKSTREAM = "api2-wnba-pra-history-v1-step1"
PLAN_PATH = "devsystem/runless_proof_plans/wnba-pra-history-multisource-v1-step1.json"
SOURCE_MAIN_SHA = "219ed8367207538a909986841e66807e408feede"
SOURCE_CANDIDATE_SHA = "26091bfa6b37116f0cf170cee407e279b7e8b6a9"
MAIN_SHA = "42b9bcf3465af8aca41141a1d2713d5731ea6c00"
PREMERGE_PROOF_ID = "wnba-pra-history-multisource-v1-step1-26091bfa6b37116f-7f1ddb592167a0fd"
PREMERGE_DIGEST = "6c448379aa1a8c161aed8c724663ebe34a347defb95149a89cf74d9e14955e37"
PREMERGE_CHECK_ID = 113031687571
MERGED_PROOF_ID = "wnba-pra-history-multisource-v1-step1-42b9bcf3465af8ac-reused"
FREEZE_TOKEN = "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1_FROZEN"
FREEZE_PATHS = (
    "devsystem/runless_proof_plans/wnba-pra-history-multisource-v1-step1.json",
    "devsystem/task_ledgers/wnba-pra-history-multisource-v1-step1.json",
    "docs/superpowers/plans/2026-10-07-wnba-pra-history-multisource-step1.md",
    "sports_api/api/wnba_pra_detail_bundle.py",
    "sports_api/wnba_pra_history_multisource_v1.py",
    "tests/test_wnba_pra_history_multisource_v1_step1.py",
)
LEASE_ID = "SCOPE-LEASE-58276A81543E070B30D3D29C"
LEASE_OWNER = "api2-wnba-pra-history-v1-step1"
EXPECTED_REGISTRY_REVISION = 185
EXPECTED_REGISTRY_HASH = "c724272b73372ececa74be33c8310b2fae7586ce9fae4e6bafe735918587bea3"
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
        kwargs["step"] = "wnba-pra-history-multisource-v1-step1-merged-closeout"
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
        "RUNLESS_TASK17_STEP5", "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "1/3"
    return result


def install_startup(app):
    app.state.wnba_pra_history_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_pra_history_step1_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pra_history_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.wnba_pra_history_step1_closeout, sort_keys=True),
            flush=True,
        )

    return app
