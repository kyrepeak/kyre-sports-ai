"""KYRE GUARDIAN Runless proof for shared-runtime frozen-init closeout V1."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Mapping
from urllib.parse import quote

AUTHORITY = "KYRE_GUARDIAN_ONLY"
TASK_ID = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"
WORKSTREAM = TASK_ID
PR_NUMBER = 1898
BRANCH = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"
BASE_BRANCH = "main"
EXPECTED_MAIN_SHA = "49ee15d2ba9d583373e8981352eac9809cd189d0"
GATE_NAME = "runless-final-gate"
GITHUB_APP_ID = "5204253"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_DIR = "devsystem/runless_proof_receipts"
PLAN_PATH = f"devsystem/runless_proof_plans/{TASK_ID}.json"
ALLOWED_CHANGED_PATHS = frozenset(
    {
        ".github/workflows/guardian-shared-runtime-lifecycle-v1.yml",
        "devsystem/runless_proof_plans/guardian-shared-runtime-lifecycle-freeze-closeout-v1.json",
        "runless_v2/__init__.py",
        "runless_v2/config.py",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "runless_v2/guardian_shared_runtime_freeze_closeout_proof_v1.py",
        "runless_v2/sandbox_executor.py",
        "tests/test_guardian_runless_cleanup_v1.py",
        "tests/test_guardian_runless_proof_v1.py",
        "tests/test_guardian_shared_runtime_freeze_closeout_v1.py",
    }
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.I)


class ProofFailure(RuntimeError):
    pass


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _sha(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise ProofFailure(f"GUARDIAN_CLOSEOUT_{label.upper()}_INVALID")
    return text


def _receipt_path(candidate: str) -> str:
    return f"{RECEIPT_DIR}/{TASK_ID}-{candidate[:16]}.json"


def _read_receipt(github: Any, candidate: str) -> dict[str, Any] | None:
    raw = github._request(
        "GET",
        f"/contents/{quote(_receipt_path(candidate), safe='/')}?ref={quote(RECEIPT_REF, safe='/')}",
        allow_404=True,
    )
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or raw.get("encoding") != "base64":
        raise ProofFailure("GUARDIAN_CLOSEOUT_RECEIPT_READ_FAILED")
    payload = json.loads(base64.b64decode(str(raw["content"])).decode())
    core = dict(payload)
    supplied = str(core.pop("digest", ""))
    if supplied != _digest(core):
        raise ProofFailure("GUARDIAN_CLOSEOUT_RECEIPT_DIGEST_MISMATCH")
    return dict(payload)


def _write_receipt(github: Any, receipt: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _sha(receipt.get("candidate_sha"), "candidate_sha")
    existing = _read_receipt(github, candidate)
    if existing is not None:
        if existing != dict(receipt):
            raise ProofFailure("GUARDIAN_CLOSEOUT_RECEIPT_COLLISION")
        return existing
    github._ensure_receipt_ref(candidate)
    github._request(
        "PUT",
        f"/contents/{quote(_receipt_path(candidate), safe='/')}",
        json={
            "message": f"GUARDIAN freeze closeout proof {candidate[:12]}",
            "content": base64.b64encode((_canon(receipt) + "\n").encode()).decode(),
            "branch": RECEIPT_REF,
        },
    )
    readback = _read_receipt(github, candidate)
    if readback != dict(receipt):
        raise ProofFailure("GUARDIAN_CLOSEOUT_RECEIPT_READBACK_MISMATCH")
    return readback


def _matching_gate(check: Mapping[str, Any], candidate: str, digest: str) -> bool:
    output = check.get("output") if isinstance(check.get("output"), Mapping) else {}
    return (
        check.get("name") == GATE_NAME
        and check.get("conclusion") == "success"
        and str(check.get("head_sha") or "") == candidate
        and str((check.get("app") or {}).get("id")) == GITHUB_APP_ID
        and AUTHORITY in str(output.get("summary") or "")
        and digest in str(output.get("summary") or "")
    )


def _publish_gate(github: Any, candidate: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
    digest = str(receipt["digest"])
    checks = github._request("GET", f"/commits/{candidate}/check-runs?per_page=100")
    for check in (checks or {}).get("check_runs", []):
        if _matching_gate(check, candidate, digest):
            return check
    github._request(
        "POST",
        "/check-runs",
        json={
            "name": GATE_NAME,
            "head_sha": candidate,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "KYRE GUARDIAN Frozen Init Closeout V1",
                "summary": f"authority={AUTHORITY} receipt={digest} task={TASK_ID}",
            },
        },
    )
    checks = github._request("GET", f"/commits/{candidate}/check-runs?per_page=100")
    for check in (checks or {}).get("check_runs", []):
        if _matching_gate(check, candidate, digest):
            return check
    raise ProofFailure("GUARDIAN_CLOSEOUT_GATE_READBACK_FAILED")


async def prove_guardian_shared_runtime_freeze_closeout(
    *, github: Any, sandbox: Any, expected_preview_sha: str
) -> dict[str, Any]:
    preview = _sha(expected_preview_sha, "preview_sha")
    pr = github._request("GET", f"/pulls/{PR_NUMBER}")
    if str(pr.get("state") or "") != "open":
        raise ProofFailure("GUARDIAN_CLOSEOUT_PR_NOT_OPEN")
    head, base = dict(pr.get("head") or {}), dict(pr.get("base") or {})
    candidate = _sha(head.get("sha"), "candidate_sha")
    if candidate != preview:
        raise ProofFailure("GUARDIAN_CLOSEOUT_PREVIEW_HEAD_DRIFT")
    if str(head.get("ref") or "") != BRANCH or str(base.get("ref") or "") != BASE_BRANCH:
        raise ProofFailure("GUARDIAN_CLOSEOUT_PR_IDENTITY_MISMATCH")
    if _sha(base.get("sha"), "base_sha") != EXPECTED_MAIN_SHA or _sha(github.main_sha(), "main_sha") != EXPECTED_MAIN_SHA:
        raise ProofFailure("GUARDIAN_CLOSEOUT_MAIN_DRIFT")

    plan = github._content_json(PLAN_PATH, candidate)
    if plan.get("task_id") != TASK_ID or plan.get("workstream") != WORKSTREAM:
        raise ProofFailure("GUARDIAN_CLOSEOUT_PLAN_IDENTITY_MISMATCH")
    if _sha(plan.get("source_main_sha"), "plan_main_sha") != EXPECTED_MAIN_SHA:
        raise ProofFailure("GUARDIAN_CLOSEOUT_PLAN_MAIN_DRIFT")
    if plan.get("required_check") != GATE_NAME or str(plan.get("required_check_app_id")) != GITHUB_APP_ID:
        raise ProofFailure("GUARDIAN_CLOSEOUT_GATE_POLICY_DRIFT")
    if int(plan.get("github_actions_fallback", -1)) != 0:
        raise ProofFailure("GUARDIAN_CLOSEOUT_GITHUB_ACTIONS_FALLBACK_FORBIDDEN")

    compare = github._request("GET", f"/compare/{EXPECTED_MAIN_SHA}...{candidate}")
    changed = sorted(str(item.get("filename") or "") for item in compare.get("files", []))
    if str(compare.get("status") or "") != "ahead" or not changed or not set(changed).issubset(ALLOWED_CHANGED_PATHS):
        raise ProofFailure("GUARDIAN_CLOSEOUT_SCOPE_VIOLATION")

    tree = github.tree_blobs(candidate)
    artifact_map = {path: str(tree.get(path) or "") for path in plan.get("artifacts") or []}
    dependency_map = {path: str(tree.get(path) or "") for path in plan.get("dependencies") or []}
    if any(not _SHA_RE.fullmatch(blob) for blob in [*artifact_map.values(), *dependency_map.values()]):
        raise ProofFailure("GUARDIAN_CLOSEOUT_BLOB_MAP_INCOMPLETE")

    result = await sandbox.execute(
        candidate_sha=candidate,
        task_id=TASK_ID,
        github_token=github.installation_token(),
        timeout_seconds=int(plan.get("timeout_seconds", 600)),
    )
    evidence = [item.model_dump(mode="json") for item in result.evidence]
    if result.candidate_sha != candidate or result.task_id != TASK_ID or _canon(result.plan) != _canon(plan) or not result.ok or not evidence or any(item.get("ok") is not True for item in evidence):
        raise ProofFailure("GUARDIAN_CLOSEOUT_SANDBOX_NOT_GREEN")

    core = {
        "schema_version": 1,
        "authority": AUTHORITY,
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "candidate_sha": candidate,
        "expected_main_sha": EXPECTED_MAIN_SHA,
        "pr_number": PR_NUMBER,
        "branch": BRANCH,
        "changed_paths": changed,
        "artifact_map": artifact_map,
        "dependency_map": dependency_map,
        "sandbox_evidence_digest": _digest(evidence),
        "plan_digest": _digest(plan),
        "gate_name": GATE_NAME,
        "github_app_id": GITHUB_APP_ID,
        "api2_state_used": False,
        "monster_state_used": False,
        "monster_registry_modified": False,
    }
    receipt = dict(core)
    receipt["digest"] = _digest(core)
    readback = _write_receipt(github, receipt)
    check = _publish_gate(github, candidate, readback)
    return {
        "status": "GREEN",
        "authority": AUTHORITY,
        "candidate_sha": candidate,
        "receipt_digest": readback["digest"],
        "gate_check_run_id": check.get("id"),
        "readback_verified": True,
    }
