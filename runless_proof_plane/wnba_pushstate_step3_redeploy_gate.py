from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "897f0ce90b5105477592a92279a9055ef27afbf8"
CANDIDATE_SHA = "ed5f064db1c731b6559e1695141fd35a349fc6b0"
PR_NUMBER = 1418
TARGET_FILE = "requirements.txt"
EXPECTED_COMMENT = "# WNBA pushState Repair V1 Step 3 full Streamlit redeploy trigger 2026-10-06 R1"


def _read_text(client, path: str, ref: str) -> str:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode()


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _non_comment_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def publish_candidate_gate(client) -> dict[str, Any]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_MAIN_DRIFT")

    pr = client.request("GET", f"/pulls/{PR_NUMBER}")
    if str(pr.get("state")) != "open":
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_PR_NOT_OPEN")
    if str(((pr.get("head") or {}).get("sha") or "")) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_HEAD_DRIFT")
    base = pr.get("base") or {}
    if str(base.get("ref") or "") != "main" or str(base.get("sha") or "") != BASE_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_BASE_DRIFT")

    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100")
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    if changed != (TARGET_FILE,):
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_SCOPE_DRIFT:" + ",".join(changed))
    file_meta = files[0]
    if int(file_meta.get("additions") or 0) != 1 or int(file_meta.get("deletions") or 0) != 0:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_DIFF_SIZE_DRIFT")

    base_text = _read_text(client, TARGET_FILE, BASE_SHA)
    candidate_text = _read_text(client, TARGET_FILE, CANDIDATE_SHA)
    expected = base_text.rstrip("\n") + "\n" + EXPECTED_COMMENT + "\n"
    if candidate_text != expected:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_CONTENT_DRIFT")
    if _non_comment_lines(candidate_text) != _non_comment_lines(base_text):
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_DEPENDENCY_DRIFT")

    blobs = client.tree_blobs(CANDIDATE_SHA)
    target_blob = str(blobs.get(TARGET_FILE) or "")
    if len(target_blob) != 40:
        raise RuntimeError("WNBA_PUSHSTATE_STEP3_REDEPLOY_BLOB_MISSING")

    evidence = {
        "pr": PR_NUMBER,
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": [TARGET_FILE],
        "additions": 1,
        "deletions": 0,
        "dependency_lines_unchanged": True,
        "expected_comment": EXPECTED_COMMENT,
        "github_actions_fallback": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step3-redeploy-{CANDIDATE_SHA[:16]}",
        task_id="wnba-pushstate-repair-v1-step3-streamlit-redeploy",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step3",
        step="3/4-deployment-candidate-certification",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={TARGET_FILE: target_blob},
        dependency_map={
            "base_main_sha": BASE_SHA,
            "pr_number": PR_NUMBER,
            "proof_authority": "Runless Proof Plane",
            "proof_mode": "deployment-only-comment-diff",
        },
        registry_before={"step2": "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN", "mode": "read-only"},
        registry_after={"step2": "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN", "mode": "read-only"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": check.get("id"),
        "receipt_digest": receipt["digest"],
        "changed_files": 1,
        "dependency_lines_unchanged": True,
    }


def install_startup_gate(app):
    app.state.wnba_pushstate_step3_redeploy_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _publish_wnba_pushstate_step3_redeploy_gate():
        try:
            app.state.wnba_pushstate_step3_redeploy_gate = publish_candidate_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step3_redeploy_gate = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
