from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "runless-task17-step6-tail-sla-telemetry"
WORKSTREAM = "runless-task17-step6"
PLAN_PATH = "devsystem/runless_proof_plans/runless-task17-step6-tail-sla-telemetry.json"
SOURCE_MAIN_SHA = "299cc72b502285a1fe714c2e513e363013ad3e90"
SOURCE_CANDIDATE_SHA = "4a7bf1142de2d9f2527003395c643013ce67c243"
MAIN_SHA = "3347f77f5b80f79e89a6bcbe675658b32ed52621"
PREMERGE_PROOF_ID = "runless-task17-step6-tail-sla-telemetry-4a7bf1142de2d9f2-13b547e71b901456"
PREMERGE_DIGEST = "d6f347ab13db2ef0768977c5a85aebac506e708d178d9db9b9511ba1344c6d02"
PREMERGE_CHECK_ID = 112690295408
MERGED_PROOF_ID = "runless-task17-step6-tail-sla-telemetry-3347f77f5b80f79e-reused"
FREEZE_TOKEN = "RUNLESS_TASK17_STEP6_TAIL_SLA_TELEMETRY_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/runless-task17-step6-tail-sla-telemetry.json",
    "devsystem/runless_proof_plans/runless-task17-step6-tail-sla-telemetry.json",
    "devsystem/task_ledgers/runless-task17-step6-tail-sla-telemetry.json",
    "runless_proof_plane/tail_sla_telemetry.py",
    "tests/test_runless_task17_step6_tail_sla_telemetry.py",
)
LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
LEASE_OWNER = "monster-v2-runless-task17-step6"
EXPECTED_REGISTRY_REVISION = 177
EXPECTED_REGISTRY_HASH = "73ce8f8b94ad086fe56de94ab9a420a37b99efbebab310d6206191fe81a267c1"
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
    """Run the proven atomic-closeout implementation with exact Step-6 bindings.

    The underlying Step-5 closeout engine is reused deliberately so Step 6 does not
    fork receipt/gate/freeze/CAS semantics. All patched module globals are restored
    after this one invocation.
    """

    saved = {name: getattr(core, name) for name in _bindings()}
    original_build_receipt = core.build_runless_receipt

    def _build_step6_receipt(**kwargs):
        kwargs["step"] = "task17-step6-tail-sla-telemetry"
        return original_build_receipt(**kwargs)

    try:
        for name, value in _bindings().items():
            setattr(core, name, value)
        core.build_runless_receipt = _build_step6_receipt
        result = dict(core.execute(client))
    finally:
        core.build_runless_receipt = original_build_receipt
        for name, value in saved.items():
            setattr(core, name, value)

    decision = str(result.get("decision") or "")
    result["decision"] = decision.replace("RUNLESS_TASK17_STEP5", "RUNLESS_TASK17_STEP6")
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "6/6"
    return result


def install_startup(app):
    app.state.task17_step6_atomic_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step6_atomic_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step6_atomic_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "RUNLESS_TASK17_STEP6_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.task17_step6_atomic_closeout, sort_keys=True),
            flush=True,
        )

    return app
