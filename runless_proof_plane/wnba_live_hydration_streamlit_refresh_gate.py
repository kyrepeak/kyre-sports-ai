from __future__ import annotations

import base64
import hashlib
import json

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "c23faa12367275d19d140460a09d83164ab5de2a"
CANDIDATE_SHA = "9bedbdd848985c42c691018a0952142714f3bf43"
BRANCH = "api2-wnba-data-step2-rebound-streamlit-refresh-r1"
PATH = "requirements.txt"
MARKER = "# WNBA Data Completeness Repair V1 Step 2 rebound hydration full Streamlit redeploy trigger 2026-10-07 R2"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-STREAMLIT-REFRESH-R1"
THAW_FROM_BLOB = "98b621afd372d472784850fed4b603c9989dcf7a"
THAW_TO_BLOB = "7f5cf407662a79cb4c56781195e7bbcaca38d315"
OWNER_TOKEN = "WNBA_PRA_REPAIR_V1_STEP8_FROZEN"
EXPECTED_REGISTRY_REVISION = 155
EXPECTED_REGISTRY_HASH = "a6d78addded88918cb13c08055acd37a5afcd2808c08f402f2866a46170bf372"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _read_text(client, ref: str) -> tuple[str, str]:
    raw = client.content(PATH, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("STREAMLIT_REFRESH_REQUIREMENTS_READ_FAILED")
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _dependency_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _verify_registry(client) -> tuple[int, str]:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("STREAMLIT_REFRESH_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    if int(payload.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("STREAMLIT_REFRESH_REGISTRY_REVISION_DRIFT")
    if str(payload.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("STREAMLIT_REFRESH_REGISTRY_HASH_DRIFT")
    owner = ((payload.get("entries") or {}).get(OWNER_TOKEN) or {}).get("artifacts") or {}
    if str(owner.get(PATH) or "") != THAW_FROM_BLOB:
        raise RuntimeError("STREAMLIT_REFRESH_OWNER_BASELINE_DRIFT")
    matches = [item for item in payload.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("STREAMLIT_REFRESH_REQUIRED_THAW_MISSING")
    grant = matches[0]
    if str(grant.get("target_head_sha") or "") != CANDIDATE_SHA:
        raise RuntimeError("STREAMLIT_REFRESH_THAW_HEAD_DRIFT")
    pair = (grant.get("files") or {}).get(PATH) or {}
    if str(pair.get("from_blob") or "") != THAW_FROM_BLOB or str(pair.get("to_blob") or "") != THAW_TO_BLOB:
        raise RuntimeError("STREAMLIT_REFRESH_THAW_BLOB_DRIFT")
    for item in payload.get("active_thaws", []):
        if item.get("thaw_id") != THAW_ID and PATH in (item.get("files") or {}):
            raise RuntimeError("STREAMLIT_REFRESH_COMPETING_THAW")
    return int(payload["revision"]), str(payload["state_hash"])


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("STREAMLIT_REFRESH_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("STREAMLIT_REFRESH_BRANCH_DRIFT")
    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = [str(item.get("filename") or "") for item in comparison.get("files", [])]
    if changed != [PATH]:
        raise RuntimeError("STREAMLIT_REFRESH_SCOPE_DRIFT:" + ",".join(changed))

    before, before_blob = _read_text(client, MAIN_SHA)
    after, after_blob = _read_text(client, CANDIDATE_SHA)
    if _dependency_lines(before) != _dependency_lines(after):
        raise RuntimeError("STREAMLIT_REFRESH_DEPENDENCY_LINES_CHANGED")
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    additions = [line for line in after_lines if line not in before_lines]
    removals = [line for line in before_lines if line not in after_lines]
    if additions != [MARKER] or removals:
        raise RuntimeError("STREAMLIT_REFRESH_NOT_COMMENT_ONLY")

    revision, state_hash = _verify_registry(client)
    evidence = {
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": changed,
        "before_blob": before_blob,
        "after_blob": after_blob,
        "marker": MARKER,
        "thaw_id": THAW_ID,
        "dependency_versions_changed": False,
        "product_runtime_changed": False,
        "other_pages_changed": 0,
        "other_sports_changed": 0,
    }
    evidence_digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=f"wnba-step2-rebound-streamlit-refresh-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-rebound-streamlit-refresh",
        project="API2",
        workstream=BRANCH,
        step="2/3-deployment-only-rebound-refresh",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={PATH: after_blob},
        dependency_map={"base_main_sha": MAIN_SHA, "github_actions_fallback": False, "deployment_only": True, "thaw_id": THAW_ID},
        registry_before={"revision": revision, "state_hash": state_hash},
        registry_after={"mode": "candidate_gate_only", "thaw_remains_active": True},
        evidence_digests=[evidence_digest],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt": str(receipt["digest"]),
        "changed_files": changed,
        "dependency_versions_changed": False,
        "registry_revision": revision,
        "thaw_id": THAW_ID,
    }


def install_startup(app):
    app.state.wnba_live_hydration_streamlit_refresh_gate = {"status": "NOT_RUN"}
    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_live_hydration_streamlit_refresh_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_live_hydration_streamlit_refresh_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_LIVE_HYDRATION_STREAMLIT_REFRESH_GATE=" + json.dumps(app.state.wnba_live_hydration_streamlit_refresh_gate, sort_keys=True), flush=True)
    return app
