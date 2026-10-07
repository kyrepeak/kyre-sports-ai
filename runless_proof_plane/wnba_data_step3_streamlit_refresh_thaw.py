from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "14fb065eee664a798764a50a4dc2cfb124f273c8"
BRANCH = "api2-wnba-data-step3-streamlit-refresh-r1"
BRANCH_SHA = "7a3073a816608ded207f71a98e66cacc70d3bc10"
OLD_GRANT_TARGET_SHA = "76c352b29d4187392cefcbce2e9df400d5a03b63"
NEW_CANDIDATE_SHA = "eae0f0d0839712f199f093c67873dc11c83e2416"
PATH = "requirements.txt"
FROM_BLOB = "7f5cf407662a79cb4c56781195e7bbcaca38d315"
BASE_BLOB = "1b433c1adc5f99f3b394a9aa040a9e1ff553d64c"
OLD_GRANT_TO_BLOB = "9de7fd6557e99a0b3a4ddb9d69b87bf6ef4df349"
NEW_TO_BLOB = "2904ed539d5a2e8a195675b96b756fb6ba6a3c74"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-STREAMLIT-REFRESH-R1"
COMMENT = "# WNBA Data Completeness Repair V1 Step 3 final merged-main deployment refresh after session-only handoff 2026-10-07 R3"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _text(client, ref):
    raw = client.content(PATH, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_CONTENT_READ_FAILED")
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _non_comment_lines(text):
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != BRANCH_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_BRANCH_DRIFT")

    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{NEW_CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != (PATH,):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_SCOPE_DRIFT:" + ",".join(changed))
    if int(comparison.get("ahead_by") or 0) != 1 or int(comparison.get("behind_by") or 0) != 0:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_ANCESTRY_DRIFT")

    base_text, base_blob = _text(client, MAIN_SHA)
    candidate_text, candidate_blob = _text(client, NEW_CANDIDATE_SHA)
    if base_blob != BASE_BLOB or candidate_blob != NEW_TO_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_BLOB_DRIFT")
    expected = base_text.rstrip("\n") + "\n" + COMMENT + "\n"
    if candidate_text != expected:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_CONTENT_DRIFT")
    if _non_comment_lines(candidate_text) != _non_comment_lines(base_text):
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_DEPENDENCY_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    thaws = deepcopy(list(registry.get("active_thaws") or []))
    expected_old = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": OLD_GRANT_TARGET_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": OLD_GRANT_TO_BLOB}},
    }
    matches = [item for item in thaws if item.get("thaw_id") == THAW_ID]
    if matches != [expected_old]:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_OLD_GRANT_DRIFT")
    for item in thaws:
        if item.get("thaw_id") != THAW_ID and PATH in (item.get("files") or {}):
            raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_COMPETING_THAW:" + str(item.get("thaw_id") or ""))

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": NEW_CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": NEW_TO_BLOB}},
    }
    unrelated_before = [deepcopy(item) for item in thaws if item.get("thaw_id") != THAW_ID]
    updated = deepcopy(registry)
    updated["active_thaws"] = [grant if item.get("thaw_id") == THAW_ID else item for item in thaws]
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: retarget {THAW_ID} to final merged-main refresh R3",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    rb_matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if rb_matches != [grant]:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("WNBA_DATA_STEP3_REFRESH_R3_UNRELATED_DRIFT")

    return {
        "status": "GREEN",
        "candidate_sha": NEW_CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "from_blob": FROM_BLOB,
        "base_blob": BASE_BLOB,
        "old_grant_to_blob": OLD_GRANT_TO_BLOB,
        "to_blob": NEW_TO_BLOB,
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_data_step3_streamlit_refresh_r3 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_streamlit_refresh_r3 = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_streamlit_refresh_r3 = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:900]
            }
        print(
            "WNBA_DATA_STEP3_STREAMLIT_REFRESH_R3="
            + json.dumps(app.state.wnba_data_step3_streamlit_refresh_r3, sort_keys=True),
            flush=True,
        )
    return app
