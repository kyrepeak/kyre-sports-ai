from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "ec301504ee74fe247eaf62d992b78929d4b2f6ed"
CANDIDATE_SHA = "0a4341139ef22742bc1440aaa41a6133164eb94c"
MERGED_SHA = "46d3dc27923ec65af7cdce5eb7b548e8b772e51c"
CANDIDATE_CHECK_ID = 112559455993
CANDIDATE_RECEIPT = "d508d245b65524221addbfcea9382ed831c2e69aaddaf53db8cbe573b41780fd"
RUNLESS_APP_ID = 5204253
FREEZE_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_FROZEN"
PUSHSTATE_FINAL_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP4_FROZEN"
EXPECTED_REGISTRY_REVISION = 147
EXPECTED_REGISTRY_HASH = "ce528cf44409cad8f95874bebe5bc3769c3774e160629b67bf0305891737fc3c"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")

ARTIFACTS = {
    "wnba_availability_v27.py": "82468c9b603947c052e726cd8beb9ba1b05b2484",
    "tests/test_wnba_data_completeness_repair_v1_step1.py": "f267498b3869a4c3fad3915102ae1f2de8546e72",
    "devsystem/wnba_data_completeness_repair_v1_step1_source_id_truth_cert.py": "4d109fe648c59a556f5a830dc1f128669379f1d6",
    "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step1-source-id-truth.json": "d065688995c5be46076a005d00d5068efbc0210c",
    "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step1-source-id-truth.json": "8e1da9de13a7942031adf9987e58e91a6eb9e770",
}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP1_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_candidate_gate(client) -> None:
    checks = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        summary = str(((check.get("output") or {}).get("summary") or ""))
        if (
            int(check.get("id") or 0) == CANDIDATE_CHECK_ID
            and check.get("name") == "runless-final-gate"
            and check.get("head_sha") == CANDIDATE_SHA
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and int(app.get("id") or 0) == RUNLESS_APP_ID
            and summary == f"receipt={CANDIDATE_RECEIPT}"
        ):
            return
    raise RuntimeError("WNBA_DATA_STEP1_CANDIDATE_GATE_MISSING")


def _verify_merged_identity(client) -> dict[str, Any]:
    if client.branch_sha("main") != MERGED_SHA:
        raise RuntimeError("WNBA_DATA_STEP1_MAIN_SHA_DRIFT")

    commit = client.request("GET", f"/commits/{MERGED_SHA}") or {}
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if BASE_SHA not in parents or CANDIDATE_SHA not in parents:
        raise RuntimeError("WNBA_DATA_STEP1_MERGE_PARENT_DRIFT")

    _require_candidate_gate(client)

    tree = client.tree_blobs(MERGED_SHA)
    for path, blob in ARTIFACTS.items():
        if str(tree.get(path) or "") != blob:
            raise RuntimeError("WNBA_DATA_STEP1_MERGED_BLOB_DRIFT:" + path)

    return {
        "main_sha": MERGED_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "candidate_check_id": CANDIDATE_CHECK_ID,
        "candidate_receipt": CANDIDATE_RECEIPT,
        "artifact_count": len(ARTIFACTS),
    }


def _publish_main_gate(client, identity: Mapping[str, Any]) -> tuple[int, str]:
    evidence = {
        "identity": dict(identity),
        "artifacts": ARTIFACTS,
        "root_cause": "ESPN roster player ID overwrote matched production player ID",
        "patch": "preserve production ID/source; label ESPN-only rows; sanitize identity text",
        "other_pages_changed": 0,
        "other_sports_changed": 0,
        "navigation_changed": False,
        "projection_math_changed": False,
        "market_math_changed": False,
        "probability_changed": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step1-merged-{MERGED_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step1-source-id-truth",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step1",
        step="1/5-merged-main-closeout",
        candidate_sha=MERGED_SHA,
        artifact_map=ARTIFACTS,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "candidate_sha": CANDIDATE_SHA,
            "candidate_check_id": CANDIDATE_CHECK_ID,
            "candidate_receipt": CANDIDATE_RECEIPT,
            "proof_authority": "Runless Proof Plane",
            "github_actions_fallback": False,
        },
        registry_before={
            "revision": EXPECTED_REGISTRY_REVISION,
            "state_hash": EXPECTED_REGISTRY_HASH,
            "pushstate_final_token": PUSHSTATE_FINAL_TOKEN,
        },
        registry_after={"freeze_token": FREEZE_TOKEN, "mode": "pending_atomic_write"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, MERGED_SHA, "success", receipt)
    return int(check["id"]), str(receipt["digest"])


def _freeze_registry(client, *, check_id: int, receipt_digest: str) -> dict[str, Any]:
    current, content_sha = _read_registry(client)
    desired_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_SHA,
        "artifacts": dict(ARTIFACTS),
    }

    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if existing != desired_entry:
            raise RuntimeError("WNBA_DATA_STEP1_FREEZE_TOKEN_CONFLICT")
        return {
            "status": "GREEN",
            "freeze_token": FREEZE_TOKEN,
            "main_sha": MERGED_SHA,
            "revision": int(current["revision"]),
            "state_hash": str(current["state_hash"]),
            "active_thaw_count": len(current.get("active_thaws", [])),
            "runless_check_id": check_id,
            "runless_receipt": receipt_digest,
            "idempotent": True,
        }

    if int(current.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")
    if str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION")

    pushstate = (current.get("entries") or {}).get(PUSHSTATE_FINAL_TOKEN) or {}
    if pushstate.get("status") != "FROZEN":
        raise RuntimeError("WNBA_DATA_STEP1_PUSHSTATE_PROTECTION_MISSING")

    original_thaws = deepcopy(list(current.get("active_thaws") or []))
    for grant in original_thaws:
        overlap = set((grant.get("files") or {}).keys()) & set(ARTIFACTS.keys())
        if overlap:
            raise RuntimeError("WNBA_DATA_STEP1_ACTIVE_THAW_OVERLAP:" + ",".join(sorted(overlap)))

    # Never silently replace another frozen artifact owner.
    for token, entry in (current.get("entries") or {}).items():
        for path, blob in (entry.get("artifacts") or {}).items():
            if path in ARTIFACTS and str(blob) != ARTIFACTS[path]:
                raise RuntimeError("WNBA_DATA_STEP1_FROZEN_ARTIFACT_CONFLICT:" + token + ":" + path)

    updated = deepcopy(current)
    updated.setdefault("entries", {})[FREEZE_TOKEN] = desired_entry
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = MERGED_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    client.update_content(
        REGISTRY_PATH,
        text,
        REGISTRY_BRANCH,
        f"registry: freeze {FREEZE_TOKEN}",
        content_sha,
    )

    readback, _ = _read_registry(client)
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != desired_entry:
        raise RuntimeError("WNBA_DATA_STEP1_FREEZE_READBACK_MISMATCH")
    if list(readback.get("active_thaws") or []) != original_thaws:
        raise RuntimeError("WNBA_DATA_STEP1_UNRELATED_THAW_DRIFT")
    if int(readback.get("revision") or -1) != EXPECTED_REGISTRY_REVISION + 1:
        raise RuntimeError("WNBA_DATA_STEP1_REGISTRY_REVISION_READBACK_FAILED")
    if str(readback.get("source_main_sha") or "") != MERGED_SHA:
        raise RuntimeError("WNBA_DATA_STEP1_REGISTRY_SOURCE_SHA_READBACK_FAILED")

    return {
        "status": "GREEN",
        "freeze_token": FREEZE_TOKEN,
        "main_sha": MERGED_SHA,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws", [])),
        "runless_check_id": check_id,
        "runless_receipt": receipt_digest,
        "idempotent": False,
    }


def closeout_step1(client) -> dict[str, Any]:
    identity = _verify_merged_identity(client)
    check_id, receipt_digest = _publish_main_gate(client, identity)
    return _freeze_registry(client, check_id=check_id, receipt_digest=receipt_digest)


def install_startup_closeout(app):
    app.state.wnba_data_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _closeout_wnba_data_step1():
        try:
            app.state.wnba_data_step1_closeout = closeout_step1(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
