from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "14fb065eee664a798764a50a4dc2cfb124f273c8"
BRANCH = "api2-wnba-data-step3-streamlit-refresh-r1"
CANDIDATE_SHA = "eae0f0d0839712f199f093c67873dc11c83e2416"
PATH = "requirements.txt"
FROM_BLOB = "7f5cf407662a79cb4c56781195e7bbcaca38d315"
BASE_BLOB = "1b433c1adc5f99f3b394a9aa040a9e1ff553d64c"
TO_BLOB = "2904ed539d5a2e8a195675b96b756fb6ba6a3c74"
COMMENT = "# WNBA Data Completeness Repair V1 Step 3 final merged-main deployment refresh after session-only handoff 2026-10-07 R3"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-STREAMLIT-REFRESH-R1"
PLAYER_THAW_ID = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
REPAIR_HEAD = "72fb0ca7eaad3827f7a9721c193cd59a5acb7f99"
REPAIR_RECEIPT = "1bb95d6d6730670dd1570cc250f4f635b8c4bbb56026e027025e9447a995ffc1"
RUNLESS_APP_ID = 5204253
STALE_PUBLIC_DEPLOY = "dep-db36gj8m7kps73d73hj0"
FOCUSED_GREEN_DEPLOY = "dep-db36dfu7bikc73bqnq40"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _read_text(client, ref: str) -> tuple[str, str]:
    raw = client.content(PATH, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_CONTENT_READ_FAILED")
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _non_comment_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def _registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload


def _require_repair_gate(client) -> int:
    checks = client.request("GET", f"/commits/{REPAIR_HEAD}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == REPAIR_HEAD
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={REPAIR_RECEIPT}"
        ):
            return int(check["id"])
    raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_REPAIR_GATE_MISSING")


def execute(client) -> dict[str, Any]:
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_BRANCH_DRIFT")
    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != (PATH,):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_SCOPE_DRIFT:" + ",".join(changed))
    if int(comparison.get("ahead_by") or 0) != 1 or int(comparison.get("behind_by") or 0) != 0:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_ANCESTRY_DRIFT")

    base_text, base_blob = _read_text(client, MAIN_SHA)
    candidate_text, candidate_blob = _read_text(client, CANDIDATE_SHA)
    if base_blob != BASE_BLOB or candidate_blob != TO_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_BLOB_DRIFT")
    if candidate_text != base_text.rstrip("\n") + "\n" + COMMENT + "\n":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_CONTENT_DRIFT")
    if _non_comment_lines(candidate_text) != _non_comment_lines(base_text):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_DEPENDENCY_DRIFT")

    registry = _registry(client)
    refresh_exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    refresh_matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if refresh_matches != [refresh_exact]:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_EXACT_THAW_MISSING")
    player_matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == PLAYER_THAW_ID]
    if len(player_matches) != 1:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_PLAYER_THAW_MISSING")
    for grant in registry.get("active_thaws", []):
        if grant.get("thaw_id") != THAW_ID and PATH in (grant.get("files") or {}):
            raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_GATE_COMPETING_REQUIREMENTS_THAW")

    repair_check_id = _require_repair_gate(client)
    evidence = {
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": [PATH],
        "dependency_lines_unchanged": True,
        "comment": COMMENT,
        "repair_check_id": repair_check_id,
        "stale_public_deploy": STALE_PUBLIC_DEPLOY,
        "stale_public_result": "WNBA_STEP3_PUBLIC_PROOF_RC=1; public shell still MLB",
        "focused_green_deploy": FOCUSED_GREEN_DEPLOY,
        "focused_green_result": "WNBA_STEP3_PUSHSTATE_GREEN_RC=0",
        "failure_owner": "STALE_PUBLIC_DEPLOYMENT",
        "github_actions_fallback": False,
    }
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step3-streamlit-refresh-r3-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step3-streamlit-refresh-r3",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step3",
        step="3/3-deployment-only-refresh-r3",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={PATH: TO_BLOB},
        dependency_map={
            "base_main_sha": MAIN_SHA,
            "thaw_id": THAW_ID,
            "repair_head": REPAIR_HEAD,
            "repair_check_id": repair_check_id,
            "proof_authority": "Runless Proof Plane",
            "proof_mode": "deployment-only-comment-diff",
            "github_actions_fallback": False,
        },
        registry_before={
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "active_thaw": THAW_ID,
        },
        registry_after={"mode": "candidate_gate_only", "registry_mutated": False},
        evidence_digests=[digest],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt": str(receipt["digest"]),
        "changed_files": [PATH],
        "dependency_lines_unchanged": True,
        "repair_check_id": repair_check_id,
        "thaw_id": THAW_ID,
    }


def install_startup(app):
    app.state.wnba_data_step3_streamlit_refresh_gate = {"status": "NOT_RUN"}
    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_streamlit_refresh_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_streamlit_refresh_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_DATA_STEP3_STREAMLIT_REFRESH_GATE=" + json.dumps(app.state.wnba_data_step3_streamlit_refresh_gate, sort_keys=True), flush=True)
    return app
