from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "0f54693bea39146747b98cbb7d15c0a4c778f0c8"
CANDIDATE_SHA = "409182156503be0027abb88d0a2bc811bcfccd94"
PATH = "requirements.txt"
FROM_BLOB = "7f5cf407662a79cb4c56781195e7bbcaca38d315"
TO_BLOB = "1b433c1adc5f99f3b394a9aa040a9e1ff553d64c"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-STREAMLIT-REFRESH-R1"
COMMENT = "# WNBA Data Completeness Repair V1 Step 3 final Player handoff full Streamlit redeploy trigger 2026-10-07 R1"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _text(client, ref):
    raw = client.content(PATH, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_CONTENT_READ_FAILED")
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _non_comment_lines(text):
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_MAIN_DRIFT")
    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != (PATH,):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_SCOPE_DRIFT:" + ",".join(changed))
    if int(comparison.get("ahead_by") or 0) != 1 or int(comparison.get("behind_by") or 0) != 0:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_ANCESTRY_DRIFT")

    base_text, base_blob = _text(client, MAIN_SHA)
    candidate_text, candidate_blob = _text(client, CANDIDATE_SHA)
    if base_blob != FROM_BLOB or candidate_blob != TO_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_BLOB_DRIFT")
    expected = base_text.rstrip("\n") + "\n" + COMMENT + "\n"
    if candidate_text != expected:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_CONTENT_DRIFT")
    if _non_comment_lines(candidate_text) != _non_comment_lines(base_text):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_DEPENDENCY_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_DUPLICATE_THAW")
    for item in thaws:
        if PATH in (item.get("files") or {}):
            raise RuntimeError("WNBA_DATA_STEP3_REFRESH_COMPETING_THAW:" + str(item.get("thaw_id") or ""))

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    unrelated_before = deepcopy(thaws)
    updated = deepcopy(registry)
    updated["active_thaws"] = thaws + [grant]
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: thaw {THAW_ID}",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if matches != [grant]:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_UNRELATED_THAW_DRIFT")
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_data_step3_streamlit_refresh_thaw = {"status": "NOT_RUN"}
    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_streamlit_refresh_thaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_streamlit_refresh_thaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_DATA_STEP3_STREAMLIT_REFRESH_THAW=" + json.dumps(app.state.wnba_data_step3_streamlit_refresh_thaw, sort_keys=True), flush=True)
    return app
