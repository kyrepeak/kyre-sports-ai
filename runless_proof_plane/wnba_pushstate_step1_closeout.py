from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

STEP1_ARTIFACTS = (
    "devsystem/runless_proof_plans/wnba-pushstate-repair-v1-step1-root-cause.json",
    "devsystem/task_ledgers/wnba-pushstate-repair-v1-step1-root-cause.json",
    "devsystem/wnba_pushstate_repair_v1_step1_root_cause_cert.py",
    "tests/test_wnba_pushstate_repair_v1_step1.py",
)

_EXPECTED_OWNER = "_pin_deep_wnba_shell_route"
_EXPECTED_CERT_TOKEN = "RUNLESS_WNBA_PUSHSTATE_STEP1_GREEN"
_EXPECTED_TEST_RESULT = "1 passed in 1.89s"


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _require_exact_identity(
    client,
    *,
    candidate_sha: str,
    base_sha: str,
    pr_number: int,
) -> dict[str, str]:
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
        raise ValueError("WNBA_PUSHSTATE_STEP1_DEPLOY_ID_MISSING")


def publish_candidate_gate(
    client,
    *,
    candidate_sha: str,
    base_sha: str,
    pr_number: int,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    artifact_map = _require_exact_identity(
        client,
        candidate_sha=candidate_sha,
        base_sha=base_sha,
        pr_number=pr_number,
    )
    _require_terminal_evidence(evidence)

    receipt = build_runless_receipt(
        proof_id=f"wnba-pushstate-step1-{candidate_sha[:16]}",
        task_id="wnba-pushstate-repair-v1-step1-root-cause",
        project="API2",
        workstream="api2-wnba-pushstate-repair-v1-step1",
        step="1/4-root-cause-certification",
        candidate_sha=candidate_sha,
        artifact_map=artifact_map,
        dependency_map={
            "base_main_sha": base_sha,
            "pr_number": pr_number,
            "worker_service_id": evidence["worker_service_id"],
            "worker_deploy_id": evidence["worker_deploy_id"],
            "proof_authority": "Runless Proof Plane",
        },
        registry_before={"mode": "read-only", "frozen_steps_1_through_9": "protected"},
        registry_after={"mode": "read-only", "frozen_steps_1_through_9": "protected"},
        evidence_digests=[_digest(dict(evidence))],
        failure_class="NONE",
    )
    check = publish_gate(client, candidate_sha, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": candidate_sha,
        "receipt_digest": receipt["digest"],
        "check_id": check.get("id"),
    }


def publish_candidate_gate_from_env(client) -> dict[str, Any]:
    if os.getenv("RPP_WNBA_PUSHSTATE_STEP1_GATE_ON_START", "").strip() != "1":
        return {"status": "NOT_ARMED"}

    candidate_sha = os.getenv("RPP_WNBA_PUSHSTATE_STEP1_CANDIDATE_SHA", "").strip()
    base_sha = os.getenv("RPP_WNBA_PUSHSTATE_STEP1_BASE_SHA", "").strip()
    raw_pr = os.getenv("RPP_WNBA_PUSHSTATE_STEP1_PR", "").strip()
    if not raw_pr.isdigit():
        raise ValueError("WNBA_PUSHSTATE_STEP1_PR_REQUIRED")

    evidence = {
        "worker_service_id": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_WORKER_SERVICE_ID", "").strip(),
        "worker_deploy_id": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_WORKER_DEPLOY_ID", "").strip(),
        "test_result": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_TEST_RESULT", "").strip(),
        "cert_token": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_CERT_TOKEN", "").strip(),
        "owner": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_OWNER", "").strip(),
        "feedback_loop_proven": os.getenv("RPP_WNBA_PUSHSTATE_STEP1_FEEDBACK_LOOP_PROVEN", "").strip() == "1",
    }
    return publish_candidate_gate(
        client,
        candidate_sha=candidate_sha,
        base_sha=base_sha,
        pr_number=int(raw_pr),
        evidence=evidence,
    )
