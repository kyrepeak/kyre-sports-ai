from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from .wnba_pushstate_step2_closeout import STEP2_ARTIFACTS

MERGED_SHA = "897f0ce90b5105477592a92279a9055ef27afbf8"
FREEZE_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN"
MERGED_RECEIPT = "857ea4241e80dfa30b9b36654c8fd151a220d41afb986ef4f6489ceeac204553"
RUNLESS_APP_ID = 5204253
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_REGISTRY_READ_FAILED")
    try:
        payload = json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_REGISTRY_DECODE_FAILED") from exc
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_merged_runless_green(client) -> int:
    checks = client.request("GET", f"/commits/{MERGED_SHA}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            check.get("name") == "runless-final-gate"
            and check.get("head_sha") == MERGED_SHA
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={MERGED_RECEIPT}"
        ):
            return int(check["id"])
    raise RuntimeError("WNBA_PUSHSTATE_STEP2_MERGED_RUNLESS_GREEN_REQUIRED")


def freeze_step2(client) -> dict[str, Any]:
    if str(client.branch_sha("main")).lower() != MERGED_SHA:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_MAIN_SHA_DRIFT")
    check_id = _require_merged_runless_green(client)

    tree = client.tree_blobs(MERGED_SHA)
    missing = [path for path in STEP2_ARTIFACTS if path not in tree]
    if missing:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_FREEZE_ARTIFACTS_MISSING:" + ",".join(missing))
    artifacts = dict(sorted((path, str(tree[path])) for path in STEP2_ARTIFACTS))

    current, content_sha = _read_registry(client)
    preserved_thaws = deepcopy(current.get("active_thaws", []))
    thaw_paths = {path for grant in preserved_thaws for path in (grant.get("files") or {})}
    overlap = sorted(set(STEP2_ARTIFACTS) & thaw_paths)
    if overlap:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_CONFLICTING_THAW:" + ",".join(overlap))

    flattened = {}
    for token, entry in (current.get("entries") or {}).items():
        if token == FREEZE_TOKEN:
            continue
        flattened.update(entry.get("artifacts") or {})
    conflicts = sorted(
        path for path, blob in artifacts.items()
        if path in flattened and str(flattened[path]) != blob
    )
    if conflicts:
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))

    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        exact = (
            existing.get("status") == "FROZEN"
            and existing.get("checkpoint_id") == FREEZE_TOKEN
            and existing.get("source_main_sha") == MERGED_SHA
            and existing.get("artifacts") == artifacts
        )
        if not exact:
            raise RuntimeError("WNBA_PUSHSTATE_STEP2_FREEZE_TOKEN_CONFLICT")
        return {
            "status": "GREEN",
            "idempotent": True,
            "frozen_token": FREEZE_TOKEN,
            "merged_sha": MERGED_SHA,
            "revision": int(current["revision"]),
            "state_hash": str(current["state_hash"]),
            "artifact_count": len(artifacts),
            "active_thaw_count": len(preserved_thaws),
            "runless_check_id": check_id,
            "runless_receipt": MERGED_RECEIPT,
        }

    updated = deepcopy(current)
    updated.setdefault("entries", {})[FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_SHA,
        "artifacts": artifacts,
    }
    updated["active_thaws"] = preserved_thaws
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = MERGED_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(
            REGISTRY_PATH,
            text,
            REGISTRY_BRANCH,
            f"registry: freeze {FREEZE_TOKEN}",
            content_sha,
        )
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc

    readback, _ = _read_registry(client)
    entry = (readback.get("entries") or {}).get(FREEZE_TOKEN) or {}
    if (
        entry.get("status") != "FROZEN"
        or entry.get("checkpoint_id") != FREEZE_TOKEN
        or entry.get("source_main_sha") != MERGED_SHA
        or entry.get("artifacts") != artifacts
        or readback.get("active_thaws", []) != preserved_thaws
        or int(readback["revision"]) != int(updated["revision"])
        or str(readback["state_hash"]) != str(updated["state_hash"])
    ):
        raise RuntimeError("WNBA_PUSHSTATE_STEP2_REGISTRY_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "idempotent": False,
        "frozen_token": FREEZE_TOKEN,
        "merged_sha": MERGED_SHA,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(artifacts),
        "active_thaw_count": len(readback.get("active_thaws", [])),
        "runless_check_id": check_id,
        "runless_receipt": MERGED_RECEIPT,
    }


def install_startup_freeze(app):
    app.state.wnba_pushstate_step2_freeze = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _freeze_wnba_pushstate_step2():
        try:
            app.state.wnba_pushstate_step2_freeze = freeze_step2(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pushstate_step2_freeze = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
