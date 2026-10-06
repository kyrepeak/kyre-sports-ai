from __future__ import annotations

import base64
import hashlib
import json
import os
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
FREEZE_TOKEN = "WNBA_PRA_REPAIR_V1_STEP9_FROZEN"
STALE_THAW_ID = "THAW-WNBA-PRA-REPAIR-V1-STEP9-GAME-HANDOFF-APP"
RUNLESS_APP_ID = 5204253
SPEED_CERT_PATH = "devsystem/wnba_pra_speed_v3_step9_final_cert.py"
EXPECTED_OLD_SPEED_BLOB = "175c7afd6f171467f9afae0db743d8e03593d7e0"
ARTIFACT_PATHS = (
    "devsystem/runless_proof_plans/wnba-pra-repair-v1-step9-final-cert.json",
    "devsystem/task_ledgers/wnba-pra-repair-v1-step9-final-cert.json",
    "devsystem/wnba_pra_repair_v1_step9_final_cert.py",
    SPEED_CERT_PATH,
    "tests/test_wnba_pra_repair_v1_step9.py",
    "tests/test_wnba_step9_segmented_date_commit.py",
)


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(payload):
    value = deepcopy(payload)
    value.pop("state_hash", None)
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_STEP9_REGISTRY_READ_FAILED")
    try:
        payload = json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError("WNBA_STEP9_REGISTRY_DECODE_FAILED") from exc
    validate_registry(payload)
    return payload, raw["sha"]


def _require_runless_green(client, merged_sha):
    checks = client.request("GET", f"/commits/{merged_sha}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == merged_sha
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
        ):
            return {
                "check_id": int(check["id"]),
                "receipt": str(((check.get("output") or {}).get("summary") or "")).removeprefix("receipt="),
            }
    raise RuntimeError("WNBA_STEP9_MERGED_MAIN_RUNLESS_GREEN_REQUIRED")


def freeze_step9(client, merged_sha, freeze_token=FREEZE_TOKEN):
    merged_sha = str(merged_sha or "").strip().lower()
    if len(merged_sha) != 40:
        raise RuntimeError("WNBA_STEP9_MERGED_SHA_REQUIRED")
    if client.branch_sha("main") != merged_sha:
        raise RuntimeError("WNBA_STEP9_MAIN_SHA_DRIFT")

    runless = _require_runless_green(client, merged_sha)
    tree = client.tree_blobs(merged_sha)
    missing = [path for path in ARTIFACT_PATHS if path not in tree]
    if missing:
        raise RuntimeError("WNBA_STEP9_FREEZE_ARTIFACTS_MISSING:" + ",".join(missing))
    artifacts = {path: tree[path] for path in ARTIFACT_PATHS}
    new_speed_blob = artifacts[SPEED_CERT_PATH]

    current, content_sha = _read_registry(client)
    original_unrelated_thaws = [
        deepcopy(grant)
        for grant in current.get("active_thaws", [])
        if str(grant.get("thaw_id")) != STALE_THAW_ID
    ]
    stale_grants = [
        grant for grant in current.get("active_thaws", [])
        if str(grant.get("thaw_id")) == STALE_THAW_ID
    ]
    if len(stale_grants) > 1:
        raise RuntimeError("WNBA_STEP9_STALE_THAW_DUPLICATED")
    if stale_grants:
        grant = stale_grants[0]
        files = grant.get("files") or {}
        if set(files) != {"app.py"}:
            raise RuntimeError("WNBA_STEP9_STALE_THAW_SCOPE_DRIFT")

    # No unrelated thaw may own any Step-9 freeze artifact.
    thaw_paths = {
        path
        for grant in original_unrelated_thaws
        for path in (grant.get("files") or {})
    }
    overlap = sorted(set(ARTIFACT_PATHS) & thaw_paths)
    if overlap:
        raise RuntimeError("WNBA_STEP9_CONFLICTING_THAW:" + ",".join(overlap))

    updated = deepcopy(current)

    # Forward-port the one previously frozen verifier baseline atomically.
    speed_refs = []
    for checkpoint, entry in updated.get("entries", {}).items():
        entry_artifacts = entry.get("artifacts") or {}
        if SPEED_CERT_PATH in entry_artifacts:
            speed_refs.append((checkpoint, str(entry_artifacts[SPEED_CERT_PATH])))
    if not speed_refs:
        raise RuntimeError("WNBA_STEP9_SPEED_BASELINE_MISSING")
    for checkpoint, blob in speed_refs:
        if blob not in {EXPECTED_OLD_SPEED_BLOB, new_speed_blob}:
            raise RuntimeError("WNBA_STEP9_SPEED_BASELINE_DRIFT:" + checkpoint)
        updated["entries"][checkpoint]["artifacts"][SPEED_CERT_PATH] = new_speed_blob

    existing = updated.get("entries", {}).get(freeze_token)
    if existing is not None:
        if (
            existing.get("status") != "FROZEN"
            or existing.get("checkpoint_id") != freeze_token
            or existing.get("source_main_sha") != merged_sha
            or existing.get("artifacts") != artifacts
        ):
            raise RuntimeError("WNBA_STEP9_FREEZE_TOKEN_CONFLICT")
    else:
        updated["entries"][freeze_token] = {
            "status": "FROZEN",
            "checkpoint_id": freeze_token,
            "source_main_sha": merged_sha,
            "artifacts": dict(sorted(artifacts.items())),
        }

    updated["active_thaws"] = original_unrelated_thaws
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = merged_sha
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(
            REGISTRY_PATH,
            text,
            REGISTRY_BRANCH,
            f"registry: freeze {freeze_token} and retire {STALE_THAW_ID}",
            content_sha,
        )
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc

    readback, _ = _read_registry(client)
    entry = (readback.get("entries") or {}).get(freeze_token) or {}
    if (
        entry.get("status") != "FROZEN"
        or entry.get("source_main_sha") != merged_sha
        or entry.get("artifacts") != dict(sorted(artifacts.items()))
        or any(str(g.get("thaw_id")) == STALE_THAW_ID for g in readback.get("active_thaws", []))
        or readback.get("active_thaws", []) != original_unrelated_thaws
        or (readback.get("entries", {}).get("WNBA_PRA_SPEED_V3_STEP9", {}).get("artifacts", {}).get(SPEED_CERT_PATH) != new_speed_blob)
    ):
        raise RuntimeError("WNBA_STEP9_REGISTRY_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "frozen_token": freeze_token,
        "merged_sha": merged_sha,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(artifacts),
        "retired_thaw": STALE_THAW_ID,
        "active_thaw_count": len(readback.get("active_thaws", [])),
        "runless_check_id": runless["check_id"],
        "runless_receipt": runless["receipt"],
        "speed_baseline_blob": new_speed_blob,
    }


def freeze_from_env(client):
    merged_sha = os.getenv("RPP_WNBA_STEP9_FREEZE_MERGED_SHA", "").strip()
    token = os.getenv("RPP_WNBA_STEP9_FREEZE_TOKEN", FREEZE_TOKEN).strip() or FREEZE_TOKEN
    return freeze_step9(client, merged_sha, token)
