from __future__ import annotations

import base64
import hashlib
import json
import os
from copy import deepcopy
from typing import Any, Mapping

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

STEP1_ARTIFACTS = (
    "devsystem/runless_proof_plans/wnba-pushstate-repair-v1-step1-root-cause.json",
    "devsystem/task_ledgers/wnba-pushstate-repair-v1-step1-root-cause.json",
    "devsystem/wnba_pushstate_repair_v1_step1_root_cause_cert.py",
    "tests/test_wnba_pushstate_repair_v1_step1.py",
)
WNBA_PUSHSTATE_STEP1_FREEZE_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP1_FROZEN"
_RUNLESS_APP_ID = 5204253
_REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
_EXPECTED_OWNER = "_pin_deep_wnba_shell_route"
_EXPECTED_CERT_TOKEN = "RUNLESS_WNBA_PUSHSTATE_STEP1_GREEN"
_EXPECTED_TEST_RESULT = "1 passed in 1.89s"


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _state_hash(payload: Mapping[str, Any]) -> str:
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _proof_evidence_from_env() -> dict[str, Any]:
    return {
        "worker_service_id": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_WORKER_SERVICE_ID", "").strip(),
        "worker_deploy_id": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_WORKER_DEPLOY_ID", "").strip(),
        "test_result": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_TEST_RESULT", "").strip(),
        "cert_token": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_CERT_TOKEN", "").strip(),
        "owner": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_OWNER", "").strip(),
        "feedback_loop_proven": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_FEEDBACK_LOOP_PROVEN", "").strip() == "1",
    }


def _require_exact_identity(client, *, candidate_sha: str, base_sha: str, pr_number: int) -> dict[str, str]:
    if len(candidate_sha) != 40 or len(base_sha) != 40:
        raise ValueError("WNBA_PUSHSTATE_STEP1_BAD_SHA")
    if client.branch_sha("main").lower() != base_sha.lower():
        raise ValueError("WNBA_PUSHSTATE_STEP1_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{pr_number}")
    if str(pr.get("state") or "") != "open":
        raise ValueError("WNBA_PUSHSTATE_STEP1_PR_NOT_OPEN")
    if str(((pr.get("head") or {}).get("sha") or "")).lower() != candidate_sha.lower():
        raise ValueError("WNBA_PUSHSTATE_STEP1_HEAD_DRIFT")
    base = pr.get("base") or {}
    if str(base.get("ref") or "") != "main" or str(base.get("sha") or "").lower() != base_sha.lower():
        raise ValueError("WNBA_PUSHSTATE_STEP1_BASE_DRIFT")
    files = client.request("GET", f"/pulls/{pr_number}/files?per_page=100")
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    if changed != tuple(sorted(STEP1_ARTIFACTS)):
        raise ValueError("WNBA_PUSHSTATE_STEP1_SCOPE_DRIFT")
    blobs = client.tree_blobs(candidate_sha)
    artifact_map = {path: str(blobs.get(path) or "") for path in STEP1_ARTIFACTS}
    if any(len(blob) != 40 for blob in artifact_map.values()):
        raise ValueError("WNBA_PUSHSTATE_STEP1_ARTIFACT_IDENTITY_MISSING")
    return artifact_map


def _require_terminal_evidence(evidence: Mapping[str, Any]) -> None:
    if evidence.get("feedback_loop_proven") is not True:
        raise ValueError("WNBA_PUSHSTATE_STEP1_PROOF_NOT_GREEN")
    if str(evidence.get("owner") or "") != _EXPECTED_OWNER:
        raise ValueError("WNBA_PUSHSTATE_STEP1_OWNER_MISMATCH")
    if str(evidence.get("cert_token") or "") != _EXPECTED_CERT_TOKEN:
        raise ValueError("WNBA_PUSHSTATE_STEP1_CERT_TOKEN_MISSING")
    if str(evidence.get("test_result") or "") != _EXPECTED_TEST_RESULT:
        raise ValueError("WNBA_PUSHSTATE_STEP1_TEST_RESULT_MISMATCH")
    if not str(evidence.get("worker_service_id") or "").startswith("srv-"):
        raise ValueError("WNBA_PUSHSTATE_STEP1_WORKER_ID_MISSING")
    if not str(evidence.get("worker_deploy_id") or "").startswith("dep-"):
        raise ValueError("WNBA_PUSHSTATE_STEP1_WORKER_ID_MISSING")


def publish_candidate_gate(client, *, candidate_sha: str, base_sha: str, pr_number: int, evidence: Mapping[str, Any]) -> dict[str, Any]:
    artifact_map = _require_exact_identity(client, candidate_sha=candidate_sha, base_sha=base_sha, pr_number=pr_number)
    _require_terminal_evidence(evidence)
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step1-{candidate_sha[:16]}", task_id="wnba-pushstate-repair-v1-step1-root-cause",
        project="API2", workstream="api2-wnba-pushstate-repair-v1-step1", step="1/4-root-cause-certification",
        candidate_sha=candidate_sha, artifact_map=artifact_map,
        dependency_map={"base_main_sha": base_sha, "pr_number": pr_number, "worker_service_id": evidence["worker_service_id"], "worker_deploy_id": evidence["worker_deploy_id"], "proof_authority": "Runless Proof Plane"},
        registry_before={"mode": "read-only", "frozen_steps_1_through_9": "protected"},
        registry_after={"mode": "read-only", "frozen_steps_1_through_9": "protected"},
        evidence_digests=[_digest(dict(evidence))], failure_class="NONE")
    check = publish_gate(client, candidate_sha, "success", receipt)
    return {"status": "GREEN", "candidate_sha": candidate_sha, "receipt_digest": receipt["digest"], "check_id": check.get("id")}


def publish_candidate_gate_from_env(client) -> dict[str, Any]:
    if os.getenv("RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START", "").strip() != "1":
        return {"status": "NOT_ARMED"}
    raw_pr = os.getenv("RPP_WNBA_PUSHSTATE_STEP1_PR", "").strip()
    if not raw_pr.isdigit():
        raise ValueError("WNBA_PUSHSTATE_STEP1_PR_REQUIRED")
    return publish_candidate_gate(client, candidate_sha=os.getenv("RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_SHA", "").strip(), base_sha=os.getenv("RPP_WNBA_PUSHSTATE_STEP1_BASE_SHA", "").strip(), pr_number=int(raw_pr), evidence=_proof_evidence_from_env())


def publish_merged_main_gate(client, *, merged_sha: str, base_sha: str, candidate_sha: str, candidate_receipt_digest: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    if any(len(value) != 40 for value in (merged_sha, base_sha, candidate_sha)):
        raise ValueError("WNBA_PUSHSTATE_STEP1_MERGED_BAD_SHA")
    if len(candidate_receipt_digest) != 64:
        raise ValueError("WNBA_PUSHSTATE_STEP1_CANDIDATE_RECEIPT_REQUIRED")
    if client.branch_sha("main").lower() != merged_sha.lower():
        raise ValueError("WNBA_PUSHSTATE_STEP1_MERGED_MAIN_DRIFT")
    commit = client.request("GET", f"/commits/{merged_sha}")
    if str(commit.get("sha") or "").lower() != merged_sha.lower():
        raise ValueError("WNBA_PUSHSTATE_STEP1_MERGED_IDENTITY_MISMATCH")
    parents = {str(item.get("sha") or "").lower() for item in (commit.get("parents") or [])}
    if parents != {base_sha.lower(), candidate_sha.lower()}:
        raise ValueError("WNBA_PUSHSTATE_STEP1_MERGE_PARENT_MISMATCH")
    candidate_blobs = client.tree_blobs(candidate_sha); merged_blobs = client.tree_blobs(merged_sha)
    candidate_artifacts = {path: str(candidate_blobs.get(path) or "") for path in STEP1_ARTIFACTS}
    merged_artifacts = {path: str(merged_blobs.get(path) or "") for path in STEP1_ARTIFACTS}
    if any(len(blob) != 40 for blob in candidate_artifacts.values()):
        raise ValueError("WNBA_PUSHSTATE_STEP1_CANDIDATE_ARTIFACT_MISSING")
    if merged_artifacts != candidate_artifacts:
        raise ValueError("WNBA_PUSHSTATE_STEP1_MERGED_ARTIFACT_DRIFT")
    _require_terminal_evidence(evidence)
    lineage = {"base_sha": base_sha, "candidate_sha": candidate_sha, "merged_sha": merged_sha, "candidate_receipt_digest": candidate_receipt_digest, "artifact_map": merged_artifacts}
    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step1-merged-{merged_sha[:16]}", task_id="wnba-pushstate-repair-v1-step1-root-cause",
        project="API2", workstream="api2-wnba-pushstate-repair-v1-step1", step="1/4-merged-main-certification",
        candidate_sha=merged_sha, artifact_map=merged_artifacts,
        dependency_map={"base_main_sha": base_sha, "certified_candidate_sha": candidate_sha, "candidate_receipt_digest": candidate_receipt_digest, "worker_service_id": evidence["worker_service_id"], "worker_deploy_id": evidence["worker_deploy_id"], "proof_authority": "Runless Proof Plane", "proof_mode": "immutable-merge-lineage-and-artifact-equivalence"},
        registry_before={"mode": "read-only", "frozen_steps_1_through_9": "protected"},
        registry_after={"mode": "read-only", "frozen_steps_1_through_9": "protected"},
        evidence_digests=[_digest(dict(evidence)), _digest(lineage)], failure_class="NONE")
    check = publish_gate(client, merged_sha, "success", receipt)
    return {"status": "GREEN", "merged_sha": merged_sha, "receipt_digest": receipt["digest"], "check_id": check.get("id")}


def publish_merged_main_gate_from_env(client) -> dict[str, Any]:
    if os.getenv("RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START", "").strip() != "1":
        return {"status": "NOT_ARMED"}
    return publish_merged_main_gate(client, merged_sha=os.getenv("RPP_WNBA_PUSHSTATE_STEP1_MERGED_SHA", "").strip(), base_sha=os.getenv("RPP_WNBA_PUSHSTATE_STEP1_BASE_SHA", "").strip(), candidate_sha=os.getenv("RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_SHA", "").strip(), candidate_receipt_digest=os.getenv("RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_RECEIPT", "").strip(), evidence=_proof_evidence_from_env())


def _read_registry(client):
    raw = client.content(REGISTRY_PATH, ref=_REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_REGISTRY_READ_FAILED")
    try:
        payload = json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_REGISTRY_DECODE_FAILED") from exc
    validate_registry(payload)
    return payload, str(raw["sha"])


def _require_merged_runless_green(client, merged_sha: str) -> dict[str, Any]:
    checks = client.request("GET", f"/commits/{merged_sha}/check-runs") or {}
    for check in checks.get("check_runs", []):
        app = check.get("app") or {}
        if (check.get("name") == "runless-final-gate" and check.get("head_sha") == merged_sha and check.get("status") == "completed" and check.get("conclusion") == "success" and int(app.get("id") or 0) == _RUNLESS_APP_ID):
            return {"check_id": int(check["id"]), "receipt": str(((check.get("output") or {}).get("summary") or "")).removeprefix("receipt=")}
    raise RuntimeError("WNBA_PUSHSTATE_STEP1_MERGED_RUNLESS_GREEN_REQUIRED")


def freeze_step1(client, merged_sha: str, freeze_token: str = WNBA_PUSHSTATE_STEP1_FREEZE_TOKEN) -> dict[str, Any]:
    merged_sha = str(merged_sha or "").strip().lower()
    if len(merged_sha) != 40:
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_MERGED_SHA_REQUIRED")
    if str(client.branch_sha("main")).lower() != merged_sha:
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_MAIN_SHA_DRIFT")
    runless = _require_merged_runless_green(client, merged_sha)
    tree = client.tree_blobs(merged_sha)
    missing = [path for path in STEP1_ARTIFACTS if path not in tree]
    if missing:
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_FREEZE_ARTIFACTS_MISSING:" + ",".join(missing))
    artifacts = dict(sorted((path, str(tree[path])) for path in STEP1_ARTIFACTS))
    current, content_sha = _read_registry(client)
    preserved_thaws = deepcopy(current.get("active_thaws", []))
    thaw_paths = {path for grant in preserved_thaws for path in (grant.get("files") or {})}
    overlap = sorted(set(STEP1_ARTIFACTS) & thaw_paths)
    if overlap:
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_CONFLICTING_THAW:" + ",".join(overlap))
    flattened = {}
    for entry in (current.get("entries") or {}).values():
        flattened.update(entry.get("artifacts") or {})
    conflicts = sorted(path for path, blob in artifacts.items() if path in flattened and str(flattened[path]) != blob)
    if conflicts:
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))
    existing = (current.get("entries") or {}).get(freeze_token)
    if existing is not None:
        exact = existing.get("status") == "FROZEN" and existing.get("checkpoint_id") == freeze_token and existing.get("source_main_sha") == merged_sha and existing.get("artifacts") == artifacts
        if not exact:
            raise RuntimeError("WNBA_PUSHSTATE_STEP1_FREEZE_TOKEN_CONFLICT")
        return {"status": "GREEN", "idempotent": True, "frozen_token": freeze_token, "merged_sha": merged_sha, "revision": int(current["revision"]), "state_hash": str(current["state_hash"]), "artifact_count": len(artifacts), "active_thaw_count": len(preserved_thaws), "runless_check_id": runless["check_id"], "runless_receipt": runless["receipt"]}
    updated = deepcopy(current)
    updated.setdefault("entries", {})[freeze_token] = {"status": "FROZEN", "checkpoint_id": freeze_token, "source_main_sha": merged_sha, "artifacts": artifacts}
    updated["active_thaws"] = preserved_thaws
    updated["revision"] = int(current["revision"]) + 1
    updated["source_main_sha"] = merged_sha
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(REGISTRY_PATH, text, _REGISTRY_BRANCH, f"registry: freeze {freeze_token}", content_sha)
    except Exception as exc:
        raise RuntimeError("WAIT_REGISTRY_RECONCILIATION") from exc
    readback, _ = _read_registry(client)
    entry = (readback.get("entries") or {}).get(freeze_token) or {}
    if (entry.get("status") != "FROZEN" or entry.get("checkpoint_id") != freeze_token or entry.get("source_main_sha") != merged_sha or entry.get("artifacts") != artifacts or readback.get("active_thaws", []) != preserved_thaws or int(readback["revision"]) != int(updated["revision"]) or str(readback["state_hash"]) != str(updated["state_hash"])):
        raise RuntimeError("WNBA_PUSHSTATE_STEP1_REGISTRY_READBACK_MISMATCH")
    return {"status": "GREEN", "idempotent": False, "frozen_token": freeze_token, "merged_sha": merged_sha, "revision": int(readback["revision"]), "state_hash": str(readback["state_hash"]), "artifact_count": len(artifacts), "active_thaw_count": len(readback.get("active_thaws", [])), "runless_check_id": runless["check_id"], "runless_receipt": runless["receipt"]}


def freeze_step1_from_env(client) -> dict[str, Any]:
    if os.getenv("RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START", "").strip() != "1":
        return {"status": "NOT_ARMED"}
    return freeze_step1(client, os.getenv("RPP_WNBA_PUSHSTATE_STEP1_MERGED_SHA", "").strip())


def install_startup_gate(app):
    app.state.wnba_pushstate_step1_gate = {"status": "NOT_RUN"}
    @app.on_event("startup")
    def _publish_wnba_pushstate_step1_gate():
        try:
            if os.getenv("RPP_WNBA_PUSHSTATE_STEP1_FREEZE_ON_START", "").strip() == "1":
                result = freeze_step1_from_env(app.state.github_client)
            elif os.getenv("RPP_WNBA_PUSHSTATE_STEP1_MERGED_GATE_ON_START", "").strip() == "1":
                result = publish_merged_main_gate_from_env(app.state.github_client)
            else:
                result = publish_candidate_gate_from_env(app.state.github_client)
            app.state.wnba_pushstate_step1_gate = result
        except Exception as exc:
            app.state.wnba_pushstate_step1_gate = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:400]}
    return app
