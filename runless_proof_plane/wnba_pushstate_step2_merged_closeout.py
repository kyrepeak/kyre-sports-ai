from __future__ import annotations

import json
from typing import Any

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate
from .wnba_pushstate_step2_closeout import (
    BASE_SHA,
    CANDIDATE_SHA,
    CERT_FILE,
    LEDGER_FILE,
    OWNER_FILE,
    PLAN_FILE,
    STEP2_ARTIFACTS,
    TEST_FILE,
    _digest,
    _execute_candidate_behavior,
    _read_text,
)

MERGED_SHA = "897f0ce90b5105477592a92279a9055ef27afbf8"
CANDIDATE_RECEIPT = "e227e463f1850eb0d5115228488256f28b2be34530b33b02e9baefb5c40254bb"
RUNLESS_APP_ID = 5204253


def _require_candidate_gate(client) -> int:
    payload = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs") or {}
    for check in payload.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == CANDIDATE_SHA
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={CANDIDATE_RECEIPT}"
        ):
            return int(check["id"])
    raise RuntimeError("WNBA_PUSHSTATE_STEP2_CANDIDATE_GATE_MISSING")


def publish_merged_gate(client) -> dict[str, Any]:
    if client.branch_sha("main") != MERGED_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGED_MAIN_DRIFT")

    commit = client.request("GET", f"/commits/{MERGED_SHA}")
    if str(commit.get("sha") or "") != MERGED_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGED_IDENTITY_MISMATCH")
    parents = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if parents != {BASE_SHA, CANDIDATE_SHA}:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGE_PARENT_MISMATCH")

    candidate_blobs = client.tree_blobs(CANDIDATE_SHA)
    merged_blobs = client.tree_blobs(MERGED_SHA)
    candidate_map = {path: str(candidate_blobs.get(path) or "") for path in STEP2_ARTIFACTS}
    merged_map = {path: str(merged_blobs.get(path) or "") for path in STEP2_ARTIFACTS}
    if any(len(blob) != 40 for blob in candidate_map.values()):
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_CANDIDATE_ARTIFACT_MISSING")
    if merged_map != candidate_map:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGED_ARTIFACT_DRIFT")

    candidate_check_id = _require_candidate_gate(client)
    owner_source = _read_text(client, OWNER_FILE, MERGED_SHA)
    test_source = _read_text(client, TEST_FILE, MERGED_SHA)
    cert_source = _read_text(client, CERT_FILE, MERGED_SHA)
    plan = json.loads(_read_text(client, PLAN_FILE, MERGED_SHA))
    ledger = json.loads(_read_text(client, LEDGER_FILE, MERGED_SHA))
    compile(test_source, TEST_FILE, "exec")
    compile(cert_source, CERT_FILE, "exec")
    behavior = _execute_candidate_behavior(owner_source)
    if plan.get("freeze_token") != "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN":
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGED_PLAN_DRIFT")
    if ledger.get("green_plus_frozen_claimed") is not False:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGED_PREMATURE_GREEN_CLAIM")

    evidence = {
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "merged_sha": MERGED_SHA,
        "candidate_check_id": candidate_check_id,
        "candidate_receipt": CANDIDATE_RECEIPT,
        "behavior": behavior,
        "artifact_map": merged_map,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step2-merged-{MERGED_SHA[:16]}",
        task_id="wnba-pushstate-repair-v1-step2-idempotent-query",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step2",
        step="2/4-merged-main-certification",
        candidate_sha=MERGED_SHA,
        artifact_map=merged_map,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "certified_candidate_sha": CANDIDATE_SHA,
            "candidate_receipt_digest": CANDIDATE_RECEIPT,
            "proof_authority": "Runless Proof Plane",
            "proof_mode": "merged-lineage-artifact-equivalence-and-runtime-behavior",
        },
        registry_before={"step1": "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN", "mode": "read-only"},
        registry_after={"step1": "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN", "mode": "read-only"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, MERGED_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "merged_sha": MERGED_SHA,
        "check_id": check.get("id"),
        "receipt_digest": receipt["digest"],
        **behavior,
    }


def install_startup_gate(app):
    app.state.wnba_pushstate_step2_merged_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _publish_wnba_pushstate_step2_merged_gate():
        try:
            app.state.wnba_pushstate_step2_merged_gate = publish_merged_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step2_merged_gate = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
